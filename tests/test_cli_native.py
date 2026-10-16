import json
import os
import signal
import subprocess
import sys
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import pytest
from test_comparison import CASES, EXPECTED
from test_native import provider_body


@contextmanager
def receiver(stop=False, block=False):
    requests = []
    indices = {"openai": 0, "anthropic": 0, "google": 0}
    ready = threading.Event()
    release = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            path = self.path.split("?", 1)[0]
            provider = (
                "openai"
                if path.endswith("/chat/completions")
                else "anthropic"
                if path.endswith("/messages")
                else "google"
            )
            index = indices[provider]
            indices[provider] += 1
            requests.append(
                {"provider": provider, "body": body, "headers": dict(self.headers)}
            )
            ready.set()
            if block:
                release.wait(15)
            raw = json.dumps(
                provider_body(
                    provider,
                    index,
                    "length" if stop and provider == "openai" and index == 1 else None,
                )
            ).encode()
            try:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            except (BrokenPipeError, ConnectionResetError):
                pass

    service = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    service.daemon_threads = True
    thread = threading.Thread(target=service.serve_forever, daemon=True)
    thread.start()
    try:
        yield {
            "url": f"http://127.0.0.1:{service.server_port}",
            "requests": requests,
            "ready": ready,
            "release": release,
        }
    finally:
        release.set()
        service.shutdown()
        service.server_close()
        thread.join(2)


def environment(keys=True):
    env = {
        **os.environ,
        "PYDANTIC_AI_NO_BANNER": "1",
        "HTTP_PROXY": "http://127.0.0.1:1",
        "HTTPS_PROXY": "http://127.0.0.1:1",
        "NO_PROXY": "",
    }
    for key in (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GOOGLE_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_GENAI_USE_VERTEXAI",
        "GOOGLE_GENAI_USE_ENTERPRISE",
    ):
        env.pop(key, None)
    if keys:
        env.update(
            OPENAI_API_KEY="synthetic-openai-key",
            ANTHROPIC_API_KEY="synthetic-anthropic-key",
            GOOGLE_API_KEY="synthetic-google-key",
        )
    env.update(
        ANTHROPIC_AUTH_TOKEN="ambient-token-must-not-be-used",
        OPENAI_ORG_ID="ambient-org",
        OPENAI_PROJECT_ID="ambient-project",
    )
    return env


def command(tmp_path, service, providers):
    cases = tmp_path / "cases.json"
    oracle = tmp_path / "expected.json"
    cases.write_text(json.dumps([CASES[0].model_dump()]))
    oracle.write_text(json.dumps({CASES[0].case_id: EXPECTED[CASES[0].case_id]}))
    args = [
        sys.executable,
        "-m",
        "order_compare",
        "--cases",
        str(cases),
        "--expectations",
        str(oracle),
        "--output",
        str(tmp_path / "comparison.report.json"),
        "--output-root",
        str(tmp_path / "runs"),
    ]
    names = {
        "openai": "gpt-synthetic",
        "anthropic": "claude-synthetic",
        "google": "gemini-synthetic",
    }
    for provider in providers:
        args.extend(
            [
                "--model",
                provider + ":" + names[provider],
                "--" + provider + "-base-url",
                service["url"] + ("/v1" if provider == "openai" else ""),
            ]
        )
    return args


@pytest.mark.parametrize(
    "providers,stop",
    [
        (["openai"], False),
        (["openai", "anthropic", "google"], False),
        (["openai", "anthropic"], True),
    ],
)
def test_normal_cli_actual_native_http_same_sources_and_failed_provider_continuation(
    tmp_path, providers, stop
):
    with receiver(stop=stop) as service:
        args = command(tmp_path, service, providers) + [
            "--live",
            "--max-runs",
            str(len(providers)),
            "--max-provider-requests",
            str(len(providers) * 6),
        ]
        child = subprocess.run(
            args, env=environment(), capture_output=True, text=True, timeout=20
        )
        assert child.returncode == (1 if stop else 0), child.stdout + child.stderr
        result = json.loads(child.stdout)
        report = json.loads(Path(result["output"]).read_text())
        assert (
            len(service["requests"]) == 2 * len(providers)
            and len({row["case_sha256"] for row in report["results"]}) == 1
        )
        assert report["status"] == ("completed_with_errors" if stop else "completed")
        assert all(
            row["grade"]["success"]
            for row in report["results"]
            if row["status"] == "completed"
        )
        if stop:
            assert (
                report["results"][0]["usage"]["requests"] == 2
                and report["results"][1]["grade"]["success"]
            )
        for row in report["results"]:
            trace = json.loads(Path(row["receipt_path"]).read_text())
            assert trace["native_clients_closed"] and trace["configuration"][
                "requested_model"
            ].endswith("synthetic")
            assert "synthetic-openai-key" not in json.dumps(trace)
        assert Path(result["output"]).stat().st_mode & 0o777 == 0o600
        for item in service["requests"]:
            headers = {key.lower(): value for key, value in item["headers"].items()}
            assert (
                "openai-organization" not in headers and "openai-project" not in headers
            )
            if item["provider"] == "anthropic":
                assert (
                    "authorization" not in headers
                    and headers["x-api-key"] == "synthetic-anthropic-key"
                )


@pytest.mark.parametrize("name", ["SIGINT", "SIGTERM", "SIGHUP"])
def test_cli_signal_drains_case_and_publishes_partial_study_with_unstarted_models(
    tmp_path, name
):
    with receiver(block=True) as service:
        args = command(tmp_path, service, ["openai", "anthropic"]) + [
            "--live",
            "--max-runs",
            "2",
            "--max-provider-requests",
            "12",
        ]
        child = subprocess.Popen(
            args,
            env=environment(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            assert service["ready"].wait(8)
            child.send_signal(getattr(signal, name))
            stdout, stderr = child.communicate(timeout=8)
            assert child.returncode == 128 + int(getattr(signal, name)), stderr
            result = json.loads(stdout)
            report = json.loads(Path(result["output"]).read_text())
            assert report["status"] == "interrupted" and report["signal"] == name
            assert [row["status"] for row in report["results"]] == [
                "interrupted",
                "not_started",
            ] and len(service["requests"]) == 1
            case_trace = json.loads(
                Path(report["results"][0]["receipt_path"]).read_text()
            )
            assert (
                case_trace["native_clients_closed"] and case_trace["status"] == "failed"
            )
            assert (
                json.loads(Path(result["receipt_path"]).read_text())["status"]
                == "failed"
            )
        finally:
            if child.poll() is None:
                child.kill()
                child.communicate(timeout=2)


def test_dry_run_is_keyfree_and_live_budget_or_collision_failure_never_dispatches(
    tmp_path,
):
    with receiver() as service:
        args = command(tmp_path, service, ["openai"])
        plan = subprocess.run(
            args, env=environment(False), capture_output=True, text=True, timeout=8
        )
        assert plan.returncode == 0, plan.stderr
        assert (
            json.loads(plan.stdout)["maximum_prepared_provider_attempts"] == 6
            and service["requests"] == []
            and not (tmp_path / "runs").exists()
        )
        budget = subprocess.run(
            args + ["--live", "--max-runs", "1", "--max-provider-requests", "5"],
            env=environment(),
            capture_output=True,
            text=True,
            timeout=8,
        )
        assert (
            budget.returncode == 2
            and service["requests"] == []
            and not (tmp_path / "runs").exists()
        )
        output = tmp_path / "comparison.report.json"
        output.write_text("original human report")
        collision = subprocess.run(
            args + ["--live", "--max-runs", "1", "--max-provider-requests", "6"],
            env=environment(),
            capture_output=True,
            text=True,
            timeout=8,
        )
        assert (
            collision.returncode == 1
            and output.read_text() == "original human report"
            and service["requests"] == []
        )


def test_missing_key_is_a_failed_case_with_private_zero_prepared_attempts_and_unknown_cost(
    tmp_path,
):
    with receiver() as service:
        child = subprocess.run(
            command(tmp_path, service, ["openai"])
            + ["--live", "--max-runs", "1", "--max-provider-requests", "6"],
            env=environment(False),
            capture_output=True,
            text=True,
            timeout=8,
        )
        assert child.returncode == 1, child.stdout + child.stderr
        result = json.loads(child.stdout)
        report = json.loads(Path(result["output"]).read_text())
        row = report["results"][0]
        assert (
            row["status"] == "error"
            and row["usage"]["requests"] == 0
            and row["cost_usd"] is None
            and row["usage"]["input_tokens"] is None
        )
        assert (
            service["requests"] == []
            and json.loads(Path(row["receipt_path"]).read_text())[
                "native_clients_closed"
            ]
        )
