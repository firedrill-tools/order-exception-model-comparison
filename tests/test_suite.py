import asyncio
import json
from pathlib import Path
import pytest
from order_compare.source import Study, SourceChanged
from order_compare.comparison import run_suite_async
from test_comparison import CASES, EXPECTED
from test_native import transport_for


def study_files(tmp_path):
    cases = tmp_path / "cases.json"
    oracle = tmp_path / "expected.json"
    cases.write_text(json.dumps([CASES[0].model_dump()]))
    oracle.write_text(json.dumps({CASES[0].case_id: EXPECTED[CASES[0].case_id]}))
    return Study.from_files(cases, oracle), cases, oracle


def provider_options():
    return {
        "openai:gpt-synthetic": {
            "api_key": "synthetic-key",
            "base_url": "http://127.0.0.1:19/v1",
        },
        "anthropic:claude-synthetic": {
            "api_key": "synthetic-key",
            "base_url": "http://127.0.0.1:19",
        },
    }


def test_same_immutable_study_and_native_policy_across_configurations(tmp_path):
    study, _, _ = study_files(tmp_path)
    clients = []

    def factory(model, case):
        client = transport_for(model.split(":")[0])
        clients.append(client)
        return client

    report = asyncio.run(
        run_suite_async(
            study,
            list(provider_options()),
            provider_options=provider_options(),
            transport_factory=factory,
            output_root=tmp_path / "runs",
        )
    )
    assert (
        report["status"] == "completed"
        and len(report["results"]) == 2
        and all(row["grade"]["success"] for row in report["results"])
    )
    assert len({row["case_sha256"] for row in report["results"]}) == 1 and all(
        client.closed for client in clients
    )
    assert (
        report["limits"]["prepared_provider_attempts"] == 12
        and report["summaries"]["anthropic:claude-synthetic"]["usage"]["total_tokens"]
        is None
    )
    trace = json.loads(Path(report["receipt_path"]).read_text())
    assert trace["status"] == "completed" and trace["active"] is None
    assert Path(report["receipt_path"]).stat().st_mode & 0o777 == 0o600


def test_provider_failure_retains_effort_and_other_configuration_can_complete(tmp_path):
    study, _, _ = study_files(tmp_path)
    clients = []

    def factory(model, case):
        client = transport_for(
            model.split(":")[0], status=503 if model.startswith("openai:") else 200
        )
        clients.append(client)
        return client

    report = asyncio.run(
        run_suite_async(
            study,
            list(provider_options()),
            provider_options=provider_options(),
            transport_factory=factory,
            output_root=tmp_path / "runs",
        )
    )
    assert [row["status"] for row in report["results"]] == ["error", "completed"]
    assert (
        report["results"][0]["usage"]["requests"] == 2
        and report["summaries"]["openai:gpt-synthetic"]["usage"]["input_tokens"] == 22
    )
    assert report["results"][1]["grade"]["success"] and all(
        client.closed for client in clients
    )


def test_source_change_stops_suite_and_marks_remaining_population_unstarted(tmp_path):
    study, case_path, _ = study_files(tmp_path)
    clients = []

    async def change():
        case_path.write_text(case_path.read_text() + " ")

    def factory(model, case):
        client = transport_for("openai", delay=change)
        clients.append(client)
        return client

    with pytest.raises(SourceChanged) as error:
        asyncio.run(
            run_suite_async(
                study,
                list(provider_options()),
                provider_options=provider_options(),
                transport_factory=factory,
                output_root=tmp_path / "runs",
            )
        )
    report = error.value.report
    assert [row["status"] for row in report["results"]] == ["error", "not_started"]
    assert (
        len(clients) == 1
        and clients[0].closed
        and report["summaries"]["anthropic:claude-synthetic"]["not_started"] == 1
    )
    assert (
        report["status"] == "failed" and report["results"][0]["usage"]["requests"] == 1
    )


def test_cancelled_suite_drains_current_case_and_preserves_unstarted_models(tmp_path):
    async def scenario():
        study, _, _ = study_files(tmp_path)
        ready = asyncio.Event()
        drained = asyncio.Event()
        clients = []

        async def delay():
            ready.set()
            try:
                await asyncio.sleep(30)
            finally:
                drained.set()

        def factory(model, case):
            client = transport_for("openai", delay=delay)
            clients.append(client)
            return client

        task = asyncio.create_task(
            run_suite_async(
                study,
                list(provider_options()),
                provider_options=provider_options(),
                transport_factory=factory,
                output_root=tmp_path / "runs",
            )
        )
        await asyncio.wait_for(ready.wait(), 3)
        task.cancel()
        with pytest.raises(asyncio.CancelledError) as error:
            await task
        report = error.value.report
        assert (
            drained.is_set()
            and clients[0].closed
            and [row["status"] for row in report["results"]]
            == ["interrupted", "not_started"]
        )
        assert (
            json.loads(Path(error.value.receipt_path).read_text())["status"] == "failed"
        )

    asyncio.run(scenario())


def test_transport_factory_cannot_change_original_next_model_facts(tmp_path):
    study, _, _ = study_files(tmp_path)
    seen = []

    def factory(model, case):
        seen.append(case.captured_cents)
        object.__setattr__(case, "captured_cents", 999999)
        return transport_for(model.split(":")[0])

    report = asyncio.run(
        run_suite_async(
            study,
            list(provider_options()),
            provider_options=provider_options(),
            transport_factory=factory,
            output_root=tmp_path / "runs",
        )
    )
    assert (
        seen == [7200, 7200]
        and study.cases[0].captured_cents == 7200
        and all(row["grade"]["success"] for row in report["results"])
    )


def test_cancellation_after_one_response_keeps_known_partial_token_subtotal(tmp_path):
    async def scenario():
        study, _, _ = study_files(tmp_path)
        ready = asyncio.Event()
        clients = []

        async def delay():
            if len(clients[0].requests) == 2:
                ready.set()
                await asyncio.sleep(30)

        def factory(model, case):
            client = transport_for("openai", delay=delay)
            clients.append(client)
            return client

        task = asyncio.create_task(
            run_suite_async(
                study,
                ["openai:gpt-synthetic"],
                provider_options={
                    "openai:gpt-synthetic": provider_options()["openai:gpt-synthetic"]
                },
                transport_factory=factory,
                output_root=tmp_path / "runs",
            )
        )
        await asyncio.wait_for(ready.wait(), 3)
        task.cancel()
        with pytest.raises(asyncio.CancelledError) as error:
            await task
        usage = error.value.report["results"][0]["usage"]
        assert (
            usage["input_tokens"] is None
            and usage["field_coverage"]["input_tokens"]["known_subtotal"] == 11
        )
        coverage = error.value.report["summaries"]["openai:gpt-synthetic"][
            "usage_coverage"
        ]["input_tokens"]
        assert (
            coverage["known_subtotal"] == 11
            and coverage["partially_observed_rows"] == 1
            and clients[0].closed
        )

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "phase", ["prepared", "case_prepared", "after_case", "completed"]
)
def test_suite_recording_failure_stops_later_configurations_and_preserves_actual_results(
    tmp_path, phase
):
    study, _, _ = study_files(tmp_path)
    clients = []
    failed = False

    def writer(path, data):
        nonlocal failed
        trigger = (
            bool(data["results"]) if phase == "after_case" else data["status"] == phase
        )
        if trigger and not failed:
            failed = True
            raise OSError("controlled suite recording failure")
        path.write_text(json.dumps(data))

    def factory(model, case):
        client = transport_for(model.split(":")[0])
        clients.append(client)
        return client

    with pytest.raises(OSError) as error:
        asyncio.run(
            run_suite_async(
                study,
                list(provider_options()),
                provider_options=provider_options(),
                transport_factory=factory,
                output_root=tmp_path / "runs",
                writer=writer,
            )
        )
    report = error.value.report
    count = (
        0
        if phase in {"prepared", "case_prepared"}
        else 1
        if phase == "after_case"
        else 2
    )
    assert len(clients) == count and all(client.closed for client in clients)
    assert sum(row["status"] == "completed" for row in report["results"]) == count
    assert (
        report["status"] == "failed"
        and json.loads(Path(error.value.receipt_path).read_text())["status"] == "failed"
    )


def test_original_file_bytes_and_external_oracle_snapshot_remain_private_after_source_edit(
    tmp_path,
):
    import base64

    study, case_path, oracle_path = study_files(tmp_path)
    original_cases = case_path.read_bytes()
    original_oracle = oracle_path.read_bytes()
    report = asyncio.run(
        run_suite_async(
            study,
            ["openai:gpt-synthetic"],
            provider_options={
                "openai:gpt-synthetic": provider_options()["openai:gpt-synthetic"]
            },
            transport_factory=lambda *_: transport_for("openai"),
            output_root=tmp_path / "runs",
        )
    )
    private = json.loads(Path(report["receipt_path"]).read_text())
    assert (
        base64.b64decode(private["source_documents"][0]["original_bytes_base64"])
        == original_cases
    )
    assert (
        base64.b64decode(private["source_documents"][1]["original_bytes_base64"])
        == original_oracle
    )
    assert private["external_expectations_snapshot"] == {
        CASES[0].case_id: EXPECTED[CASES[0].case_id]
    }
    assert all(
        "original_bytes_base64" not in source for source in report["study"]["sources"]
    )
    case_path.write_text("human changed after completed comparison")
    oracle_path.write_text("human changed oracle after completed comparison")
    assert (
        json.loads(
            base64.b64decode(private["source_documents"][1]["original_bytes_base64"])
        )
        == private["external_expectations_snapshot"]
    )
