"""Owned real Pydantic AI case execution; source and output remain proposal-only."""

import asyncio
import math
from contextlib import AsyncExitStack
from pydantic import TypeAdapter
from pydantic_ai import capture_run_messages
from pydantic_ai.messages import ModelMessagesTypeAdapter
from pydantic_ai.usage import RunUsage, UsageLimits
from .schema import OrderCase, Proposal
from .agent import CaseContext, build_agent, POLICY
from .evidence import Receipt
from .native import configuration, create_model, aggregate, REQUEST_LIMIT, TOOL_LIMIT


async def propose_async(
    case,
    model,
    *,
    api_key=None,
    base_url=None,
    config=None,
    transport=None,
    output_root=None,
    timeout_seconds=60,
    writer=None,
    source_guard=None,
):
    case = OrderCase.model_validate(case).model_copy(deep=True)
    if (
        type(timeout_seconds) not in (int, float)
        or not 0 < timeout_seconds <= 120
        or not math.isfinite(timeout_seconds)
    ):
        raise ValueError("case timeout must be finite and in (0,120]")
    receipt = Receipt(
        case, model, POLICY, output_root, timeout_seconds, writer, source_guard
    )
    context = CaseContext(case, receipt=receipt, policy=POLICY)
    usage = RunUsage()
    messages = []
    stack = AsyncExitStack()
    close_attempted = False
    proposal = None
    failure = None
    provider = None
    try:
        receipt.save()
        receipt.guard()
        config = config or configuration(model, api_key=api_key, base_url=base_url)
        config.validate()
        provider = config.provider
        if config.identifier != model:
            raise ValueError("configuration differs from requested comparison model")
        receipt.data["configuration"] = config.public()
        receipt.save()
        receipt.guard()
        native, _ = await create_model(config, receipt, stack, transport)
        agent = build_agent(native, _native_owner=receipt)
        async with asyncio.timeout_at(receipt.deadline):
            with capture_run_messages() as messages:
                async with agent:
                    result = await agent.run(
                        f"Resolve order {case.order_id}. Call read_order, read_request and read_policy before proposing an action.",
                        deps=context,
                        usage=usage,
                        usage_limits=UsageLimits(
                            request_limit=REQUEST_LIMIT, tool_calls_limit=TOOL_LIMIT
                        ),
                    )
                proposal = Proposal.model_validate(result.output)
        receipt.guard()
        close_attempted = True
        await stack.aclose()
        receipt.data["native_clients_closed"] = True
        receipt.data["status"] = "release_prepared"
        receipt.save()
        receipt.guard()
    except BaseException as error:
        failure = error
    finally:
        if not close_attempted:
            try:
                close_attempted = True
                await stack.aclose()
                receipt.data["native_clients_closed"] = True
            except BaseException as error:
                failure = failure or error
                receipt.data["close_error"] = {
                    "name": type(error).__name__,
                    "message": str(error),
                }
        try:
            receipt.data["sdk_usage"] = TypeAdapter(RunUsage).dump_python(
                usage, mode="json"
            )
            receipt.data["sdk_messages"] = ModelMessagesTypeAdapter.dump_python(
                messages, mode="json"
            )
            receipt.data["tool_attempts"] = context.tool_attempts
            receipt.data["successful_reads"] = context.tool_calls
            receipt.finish(proposal, failure)
        except BaseException as error:
            failure = failure or error
            receipt.data.update(
                status="failed",
                proposal=None,
                durable_status="failed",
                recording_error={"name": type(error).__name__, "message": str(error)},
            )
            try:
                receipt.save(final=True)
            except BaseException:
                receipt.data["durable_status"] = "unknown"
    measured = (
        aggregate(provider, receipt.data["native"])
        if provider is not None
        else {
            "requests": 0,
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "cost_usd": None,
        }
    )
    measured.update(
        receipt_path=str(receipt.path),
        run_id=receipt.data["run_id"],
        sdk_usage=receipt.data["sdk_usage"],
        source="original provider fields; prepared native request attempts; sdk_usage normalized separately",
    )
    if failure is not None:
        failure.usage = measured
        failure.receipt_path = str(receipt.path)
        failure.recording_failed = receipt.recording_error is not None
        failure.cleanup_confirmed = receipt.data["native_clients_closed"]
        failure.evidence = receipt.data
        raise failure
    return proposal, measured, list(context.tool_calls)
