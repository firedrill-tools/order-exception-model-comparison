import asyncio
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
import httpx
import httpx2
import pytest
from order_compare.datasets import (
    list_cases,
    load_case,
    initialize_workspace,
    inspect_workspace,
    reset_workspace,
    data_root,
)
from order_compare.fixture_source import validate_bundle
from order_compare.source import Study
from order_compare.comparison import run_suite_async
from test_native import provider_body


def response_for(provider, index, case, expected):
    body = provider_body(provider, index, order_id=case.order_id)
    if index == 1:
        args = {
            "order_id": case.order_id,
            **expected,
            "reason": "Controlled source-based proposal; this is not semantic model proof",
        }
        if provider == "openai":
            body["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"] = (
                json.dumps(args)
            )
        elif provider == "anthropic":
            body["content"][0]["input"] = args
        else:
            body["candidates"][0]["content"]["parts"][0]["functionCall"]["args"] = args
    return body


class CaseTransport(httpx2.AsyncBaseTransport):
    def __init__(self, provider, case, expected):
        self.provider = provider
        self.case = case
        self.expected = expected
        self.requests = []
        self.closed = False

    async def handle_async_request(self, request):
        index = len(self.requests)
        self.requests.append(json.loads(await request.aread()))
        return httpx2.Response(
            200, json=response_for(self.provider, index, self.case, self.expected)
        )

    async def aclose(self):
        self.closed = True


class GoogleCaseTransport(httpx.AsyncBaseTransport):
    def __init__(self, case, expected):
        self.case = case
        self.expected = expected
        self.requests = []
        self.closed = False

    async def handle_async_request(self, request):
        index = len(self.requests)
        self.requests.append(json.loads(await request.aread()))
        return httpx.Response(
            200, json=response_for("google", index, self.case, self.expected)
        )

    async def aclose(self):
        self.closed = True


def provider_options(provider):
    model = (
        provider
        + ":"
        + {
            "openai": "gpt-synthetic",
            "anthropic": "claude-synthetic",
            "google": "gemini-synthetic",
        }[provider]
    )
    return model, {
        model: {
            "api_key": "synthetic-key",
            "base_url": "http://127.0.0.1:19/v1"
            if provider == "openai"
            else "http://127.0.0.1:19",
        }
    }


@pytest.mark.parametrize(
    "identifier", [row["case_id"] for row in list_cases()["cases"]]
)
def test_every_population_initializes_private_with_original_business_oracle_and_history(
    tmp_path, identifier
):
    population, entry = load_case(identifier)
    result = initialize_workspace(identifier, tmp_path / identifier)
    directory = Path(result["directory"])
    assert (
        result["matches_seed"]
        and result["identity"]["case_sha256"] == entry["sha256"]
        and result["orders"] == len(population["population"]["cases"])
    )
    assert (
        json.loads(Path(result["cases"]).read_text())
        == population["population"]["cases"]
    )
    assert (
        json.loads(Path(result["expectations"]).read_text())
        == population["population"]["expectations"]
    )
    assert directory.stat().st_mode & 0o777 == 0o700 and all(
        path.stat().st_mode & 0o777 == 0o600 for path in directory.iterdir()
    )
    assert (
        inspect_workspace(directory) == result
        and population["task"] in (directory / "TASK.md").read_text()
    )
    validate_bundle(population["population"])


@pytest.mark.parametrize(
    "identifier", [row["case_id"] for row in list_cases()["cases"]]
)
def test_every_population_runs_actual_native_sdk_with_external_oracle_and_stable_source(
    tmp_path, identifier
):
    initialized = initialize_workspace(identifier, tmp_path / identifier)
    population, _ = load_case(identifier)
    study = Study.from_files(initialized["cases"], initialized["expectations"])
    model, options = provider_options("openai")
    clients = []

    def factory(_, case):
        client = CaseTransport(
            "openai", case, population["population"]["expectations"][case.case_id]
        )
        clients.append(client)
        return client

    report = asyncio.run(
        run_suite_async(
            study,
            [model],
            provider_options=options,
            transport_factory=factory,
            output_root=tmp_path / "runs",
        )
    )
    assert (
        report["status"] == "completed"
        and len(report["results"]) == initialized["orders"]
        and all(row["grade"]["success"] for row in report["results"])
    )
    assert all(client.closed and len(client.requests) == 2 for client in clients)
    for client in clients:
        body = json.dumps(client.requests)
        assert (
            client.case.case_id not in body
            and population["task"] not in body
            and initialized["identity"]["instance_id"] not in body
        )
    assert inspect_workspace(initialized["directory"])["matches_seed"]


@pytest.mark.parametrize("identifier", ["maximum-safe-cents", "one-cent-remaining"])
@pytest.mark.parametrize("provider", ["anthropic", "google"])
def test_boundary_integer_amounts_survive_actual_other_native_sdks(
    tmp_path, identifier, provider
):
    initial = initialize_workspace(identifier, tmp_path / identifier)
    population, _ = load_case(identifier)
    study = Study.from_files(initial["cases"], initial["expectations"])
    clients = []

    def factory(_, case):
        expected = population["population"]["expectations"][case.case_id]
        client = (
            GoogleCaseTransport(case, expected)
            if provider == "google"
            else CaseTransport(provider, case, expected)
        )
        clients.append(client)
        return client

    model, options = provider_options(provider)
    report = asyncio.run(
        run_suite_async(
            study,
            [model],
            provider_options=options,
            transport_factory=factory,
            output_root=tmp_path / "runs",
        )
    )
    assert (
        report["results"][0]["grade"]["success"]
        and type(report["results"][0]["proposal"]["amount_cents"]) is int
    )
    assert all(client.closed and len(client.requests) == 2 for client in clients)


def test_busy_source_relationships_and_original_five_are_coherent():
    population, _ = load_case("busy-operations")
    data = population["population"]
    assert (
        len(data["cases"]) == 24
        and len(data["customers"]) == 12
        and len(data["source_history"]) == 24
    )
    assert sum(len(row["payments"]) for row in data["source_history"]) == 44
    assert all(
        row["provenance"] == "fictional_imported_business_facts"
        for row in data["source_history"]
    )
    original, _ = load_case("original-five")
    root = Path(__file__).resolve().parents[1]
    assert original["population"]["cases"] == json.loads(
        (root / "fixtures/cases.json").read_text()
    )
    assert original["population"]["expectations"] == json.loads(
        (root / "grader/expected.json").read_text()
    )


@pytest.mark.parametrize("index_changed", [False, True])
def test_corrupt_population_refused_before_workspace_creation(tmp_path, index_changed):
    root = tmp_path / "data"
    shutil.copytree(data_root(), root)
    path = root / ("index.json" if index_changed else "original-five.json")
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="hash differs"):
        initialize_workspace("original-five", tmp_path / "uncreated", root)
    assert not (tmp_path / "uncreated").exists()
    with pytest.raises(ValueError, match="hash differs"):
        list_cases(root)


def test_keyfree_cli_init_readback_reset_preserves_old_work_and_collisions(tmp_path):
    env = {**os.environ, "PYDANTIC_AI_NO_BANNER": "1"}
    for key in (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GOOGLE_API_KEY",
        "GEMINI_API_KEY",
    ):
        env.pop(key, None)

    def cli(*args):
        return subprocess.run(
            [sys.executable, "-m", "order_compare", *args],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )

    listed = cli("datasets")
    assert listed.returncode == 0, listed.stderr
    assert (
        len(json.loads(listed.stdout)["cases"]) == 12
        and not (tmp_path / ".runs").exists()
    )
    initialized = cli(
        "init", "--case", "busy-operations", "--directory", str(tmp_path / "workspace")
    )
    assert initialized.returncode == 0, initialized.stderr
    value = json.loads(initialized.stdout)
    directory = Path(value["directory"])
    before = {path.name: path.read_bytes() for path in directory.iterdir()}
    assert (
        cli("init", "--case", "original-five", "--directory", str(directory)).returncode
        == 1
    )
    readback = cli("workspace", str(directory))
    assert readback.returncode == 0 and json.loads(readback.stdout) == value
    assert (
        cli(
            "reset",
            str(directory),
            "--to",
            str(tmp_path / "bad"),
            "--instance",
            "stale",
        ).returncode
        == 1
        and not (tmp_path / "bad").exists()
    )
    fresh = cli(
        "reset",
        str(directory),
        "--to",
        str(tmp_path / "fresh"),
        "--instance",
        value["identity"]["instance_id"],
    )
    assert fresh.returncode == 0, fresh.stderr
    result = json.loads(fresh.stdout)
    assert (
        result["identity"]["instance_id"] != value["identity"]["instance_id"]
        and result["orders"] == 24
        and result["matches_seed"]
    )
    assert {path.name: path.read_bytes() for path in directory.iterdir()} == before


def test_case_regeneration_is_exact_without_git():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "scripts/build_datasets.py"), "--check"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr
