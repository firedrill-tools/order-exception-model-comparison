import asyncio
import json
from pathlib import Path
import httpx
import httpx2
import pytest
from order_compare.worker import propose_async
from order_compare.native import OUTPUT_TOOL
from order_compare.benchmark import grade
from test_comparison import CASES, EXPECTED


def provider_body(provider, index, stop=None, order_id="ORD-101"):
    calls = (
        [
            ("read_order", {"order_id": order_id}),
            ("read_request", {}),
            ("read_policy", {}),
        ]
        if index == 0
        else [
            (
                OUTPUT_TOOL,
                {
                    "order_id": "ORD-101",
                    "action": "replace",
                    "amount_cents": 0,
                    "reason": "Controlled original source proposal",
                },
            )
        ]
    )
    if provider == "openai":
        return {
            "id": f"chatcmpl_controlled_{index}",
            "object": "chat.completion",
            "created": 1792144800,
            "model": "gpt-observed",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": f"call_{index}_{n}",
                                "type": "function",
                                "function": {
                                    "name": name,
                                    "arguments": json.dumps(args),
                                },
                            }
                            for n, (name, args) in enumerate(calls)
                        ],
                    },
                    "finish_reason": stop or "tool_calls",
                }
            ],
            "usage": {"prompt_tokens": 11, "completion_tokens": 5, "total_tokens": 16},
        }
    if provider == "anthropic":
        return {
            "id": f"msg_controlled_{index}",
            "type": "message",
            "role": "assistant",
            "model": "claude-observed",
            "content": [
                {
                    "type": "tool_use",
                    "id": f"call_{index}_{n}",
                    "name": name,
                    "input": args,
                }
                for n, (name, args) in enumerate(calls)
            ],
            "stop_reason": stop or "tool_use",
            "stop_sequence": None,
            "usage": {"input_tokens": 11, "output_tokens": 5},
        }
    return {
        "responseId": f"gemini_controlled_{index}",
        "modelVersion": "gemini-observed",
        "candidates": [
            {
                "index": 0,
                "content": {
                    "role": "model",
                    "parts": [
                        {"functionCall": {"name": name, "args": args}}
                        for name, args in calls
                    ],
                },
                "finishReason": stop or "STOP",
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 11,
            "candidatesTokenCount": 5,
            "totalTokenCount": 16,
        },
    }


class Transport(httpx.AsyncBaseTransport):
    def __init__(
        self,
        provider,
        stop=None,
        stop_index=1,
        order_id="ORD-101",
        delay=None,
        change=None,
        status=200,
    ):
        self.delay = delay
        self.change = change
        self.status = status
        self.provider = provider
        self.requests = []
        self.closed = False
        self.stop = stop
        self.stop_index = stop_index
        self.order_id = order_id

    async def handle_async_request(self, request):
        index = len(self.requests)
        self.requests.append(json.loads(await request.aread()))
        if self.delay:
            await self.delay()
        body = provider_body(
            self.provider,
            index,
            self.stop if index == self.stop_index else None,
            self.order_id,
        )
        if self.change:
            body = self.change(body, index)
        return httpx.Response(
            self.status if index == 1 else 200,
            json=body,
            headers={"x-request-id": "req_controlled"},
        )

    async def aclose(self):
        self.closed = True


class ModernTransport(httpx2.AsyncBaseTransport):
    def __init__(
        self,
        provider,
        stop=None,
        stop_index=1,
        order_id="ORD-101",
        delay=None,
        change=None,
        status=200,
    ):
        self.delay = delay
        self.change = change
        self.status = status
        self.provider = provider
        self.requests = []
        self.closed = False
        self.stop = stop
        self.stop_index = stop_index
        self.order_id = order_id

    async def handle_async_request(self, request):
        index = len(self.requests)
        self.requests.append(json.loads(await request.aread()))
        if self.delay:
            await self.delay()
        body = provider_body(
            self.provider,
            index,
            self.stop if index == self.stop_index else None,
            self.order_id,
        )
        if self.change:
            body = self.change(body, index)
        return httpx2.Response(
            self.status if index == 1 else 200,
            json=body,
            headers={"request-id": "req_controlled"},
        )

    async def aclose(self):
        self.closed = True


def transport_for(provider, **options):
    return (
        Transport(provider, **options)
        if provider == "google"
        else ModernTransport(provider, **options)
    )


def options(provider, transport, tmp_path):
    return {
        "model": provider
        + ":"
        + {
            "openai": "gpt-synthetic",
            "anthropic": "claude-synthetic",
            "google": "gemini-synthetic",
        }[provider],
        "api_key": "synthetic-key",
        "base_url": "http://127.0.0.1:19/v1"
        if provider == "openai"
        else "http://127.0.0.1:19",
        "transport": transport,
        "output_root": tmp_path / "runs",
    }


@pytest.mark.parametrize("provider", ["openai", "anthropic", "google"])
def test_actual_pinned_provider_tools_output_usage_and_private_owner(
    provider, tmp_path
):
    transport = transport_for(provider)
    proposal, usage, reads = asyncio.run(
        propose_async(CASES[0], **options(provider, transport, tmp_path))
    )
    assert grade(CASES[0], proposal, EXPECTED[CASES[0].case_id], reads)["success"]
    assert len(transport.requests) == 2 and transport.closed and usage["requests"] == 2
    assert (
        usage["input_tokens"] == 22
        and usage["output_tokens"] == 10
        and usage["total_tokens"] == (None if provider == "anthropic" else 32)
    )
    data = json.loads(Path(usage["receipt_path"]).read_text())
    assert (
        data["native_clients_closed"]
        and data["status"] == "completed"
        and data["sdk_usage"] is not None
        and len(data["tool_attempts"]) == 3
    )
    assert all(
        item["source_case_sha256"] == data["case_sha256"] and item["successful"]
        for item in data["tool_attempts"]
    )
    assert (
        all(item["status"] == "accepted" for item in data["native"])
        and data["cost_usd"] is None
    )
    assert "synthetic-key" not in json.dumps(data)
    assert CASES[0].case_id not in json.dumps(transport.requests)


@pytest.mark.parametrize(
    "provider,stop",
    [("openai", "length"), ("anthropic", "max_tokens"), ("google", "MAX_TOKENS")],
)
@pytest.mark.parametrize("turn", [0, 1])
def test_unfinished_original_turn_cannot_release_tools_or_final_proposal(
    provider, stop, turn, tmp_path
):
    transport = transport_for(provider, stop=stop, stop_index=turn)
    with pytest.raises(Exception) as error:
        asyncio.run(propose_async(CASES[0], **options(provider, transport, tmp_path)))
    data = json.loads(Path(error.value.receipt_path).read_text())
    assert (
        data["status"] == "failed"
        and data["proposal"] is None
        and data["native_clients_closed"]
        and transport.closed
    )
    assert len(transport.requests) == turn + 1 and len(data["tool_attempts"]) == (
        0 if turn == 0 else 3
    )
    assert error.value.usage["requests"] == turn + 1 and error.value.usage[
        "input_tokens"
    ] == 11 * (turn + 1)
    assert data["native"][-1]["status"] == "rejected"


def test_wrong_order_lookup_stays_failed_evidence_and_does_not_earn_success(tmp_path):
    transport = transport_for("openai", order_id="OTHER-ORDER")
    proposal, usage, reads = asyncio.run(
        propose_async(CASES[0], **options("openai", transport, tmp_path))
    )
    assert (
        grade(CASES[0], proposal, EXPECTED[CASES[0].case_id], reads)["success"] is False
        and "read_order" not in reads
    )
    data = json.loads(Path(usage["receipt_path"]).read_text())
    attempt = next(
        item for item in data["tool_attempts"] if item["name"] == "read_order"
    )
    assert attempt["successful"] is False and json.loads(attempt["result"]) == {
        "error": "order not found"
    }


@pytest.mark.parametrize("provider", ["openai", "anthropic", "google"])
def test_failed_http_preserves_original_partial_effort_and_does_not_retry(
    provider, tmp_path
):
    transport = transport_for(provider, status=503)
    with pytest.raises(Exception) as error:
        asyncio.run(propose_async(CASES[0], **options(provider, transport, tmp_path)))
    data = json.loads(Path(error.value.receipt_path).read_text())
    assert (
        len(transport.requests) == 2
        and transport.closed
        and data["native_clients_closed"]
        and data["status"] == "failed"
    )
    assert (
        error.value.usage["requests"] == 2
        and error.value.usage["input_tokens"] == 22
        and error.value.usage["output_tokens"] == 10
    )
    assert (
        len(data["tool_attempts"]) == 3
        and data["proposal"] is None
        and data["native"][-1]["http_status"] == 503
    )


@pytest.mark.parametrize("cancel", [False, True])
def test_deadline_or_parent_cancellation_drains_native_before_final_failed_receipt(
    tmp_path, cancel
):
    async def scenario():
        ready = asyncio.Event()
        drained = asyncio.Event()

        async def delay():
            ready.set()
            try:
                await asyncio.sleep(30)
            finally:
                drained.set()

        transport = transport_for("openai", delay=delay)
        task = asyncio.create_task(
            propose_async(
                CASES[0],
                **options("openai", transport, tmp_path),
                timeout_seconds=10 if cancel else 0.25,
            )
        )
        await asyncio.wait_for(ready.wait(), 3)
        if cancel:
            task.cancel()
        with pytest.raises(asyncio.CancelledError if cancel else TimeoutError) as error:
            await task
        data = json.loads(Path(error.value.receipt_path).read_text())
        assert (
            drained.is_set()
            and transport.closed
            and data["status"] == "failed"
            and data["native_clients_closed"]
        )
        assert (
            data["tool_attempts"] == []
            and data["proposal"] is None
            and error.value.usage["requests"] == 1
        )
        assert (
            error.value.usage["input_tokens"] is None
            and data["native"][0]["status"] == "failed"
        )
        before = Path(error.value.receipt_path).read_bytes()
        await asyncio.sleep(0.03)
        assert Path(error.value.receipt_path).read_bytes() == before

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "stage",
    ["prepared", "request", "response", "tool", "release_prepared", "completed"],
)
def test_recording_failure_prevents_later_paid_work_or_proposal_release(
    tmp_path, stage
):
    failed = False

    def writer(path, data):
        nonlocal failed
        triggers = {
            "prepared": data["status"] == "prepared" and data["configuration"] is None,
            "request": bool(data["native"])
            and data["native"][-1]["status"] == "prepared",
            "response": bool(data["native"])
            and data["native"][-1].get("response") is not None,
            "tool": bool(data["tool_attempts"]),
            "release_prepared": data["status"] == "release_prepared",
            "completed": data["status"] == "completed",
        }
        if triggers[stage] and not failed:
            failed = True
            raise OSError("controlled recording failure")
        path.write_text(json.dumps(data))

    transport = transport_for("openai")
    with pytest.raises(Exception) as error:
        asyncio.run(
            propose_async(
                CASES[0], **options("openai", transport, tmp_path), writer=writer
            )
        )
    data = json.loads(Path(error.value.receipt_path).read_text())
    assert data["status"] == "failed" and data["proposal"] is None
    assert len(transport.requests) == (
        0
        if stage in {"prepared", "request"}
        else 1
        if stage in {"response", "tool"}
        else 2
    )
    if stage != "prepared":
        assert transport.closed


def test_original_zero_unknown_invalid_usage_remains_separate_from_framework_normalization(
    tmp_path,
):
    def change(body, index):
        body["usage"] = {
            "prompt_tokens": 0,
            "completion_tokens": False,
            "total_tokens": 16,
            "unmodeled_counter": 9,
        }
        return body

    transport = transport_for("openai", change=change)
    try:
        _, usage, _ = asyncio.run(
            propose_async(CASES[0], **options("openai", transport, tmp_path))
        )
    except Exception as error:
        usage = error.usage
    data = json.loads(Path(usage["receipt_path"]).read_text())
    fields = data["native"][0]["reported_usage"]["fields"]
    assert fields["prompt_tokens"] == {"state": "observed", "value": 0} and fields[
        "completion_tokens"
    ] == {"state": "invalid", "value": None}
    assert (
        data["native"][0]["reported_usage"]["raw"]["unmodeled_counter"] == 9
        and usage["output_tokens"] is None
        and usage["cost_usd"] is None
    )


def test_failed_close_remains_unknown_even_after_async_stack_has_been_emptied(tmp_path):
    class CloseFault(ModernTransport):
        async def aclose(self):
            raise RuntimeError("controlled close failure")

    transport = CloseFault("openai")
    with pytest.raises(RuntimeError, match="close failure") as error:
        asyncio.run(propose_async(CASES[0], **options("openai", transport, tmp_path)))
    data = json.loads(Path(error.value.receipt_path).read_text())
    assert (
        not data["native_clients_closed"]
        and data["status"] == "failed"
        and data["proposal"] is None
    )


def test_source_guard_change_after_dispatch_blocks_read_release(tmp_path):
    changed = False

    def guard():
        if changed:
            raise ValueError("controlled source changed")

    async def delay():
        nonlocal changed
        changed = True

    transport = transport_for("openai", delay=delay)
    with pytest.raises(Exception) as error:
        asyncio.run(
            propose_async(
                CASES[0], **options("openai", transport, tmp_path), source_guard=guard
            )
        )
    data = json.loads(Path(error.value.receipt_path).read_text())
    assert (
        len(transport.requests) == 1
        and data["tool_attempts"] == []
        and data["proposal"] is None
        and transport.closed
    )


def test_synchronous_source_check_cannot_dispatch_after_consuming_the_operation_deadline(
    tmp_path,
):
    import time

    def slow_source():
        time.sleep(0.04)

    transport = transport_for("openai")
    with pytest.raises(TimeoutError) as error:
        asyncio.run(
            propose_async(
                CASES[0],
                **options("openai", transport, tmp_path),
                source_guard=slow_source,
                timeout_seconds=0.01,
            )
        )
    assert (
        transport.requests == []
        and error.value.usage["requests"] == 0
        and error.value.evidence["status"] == "failed"
    )
