"""Fresh locked distributions, original/default source and complete archived suite."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
from pathlib import Path
from zipfile import ZipFile
from package_source import build

ROOT = Path(__file__).resolve().parents[1]
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
UV = os.environ.get("UV") or shutil.which("uv")
if not UV:
    raise RuntimeError("uv is required")
ENV = {**os.environ, "PYDANTIC_AI_NO_BANNER": "1"}
for key in (
    "OPENAI_API_KEY",
    "OPENAI_ORG_ID",
    "OPENAI_PROJECT_ID",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "GOOGLE_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_GENAI_USE_VERTEXAI",
    "GOOGLE_GENAI_USE_ENTERPRISE",
    "VIRTUAL_ENV",
    "PYTHONPATH",
    "PYTHONHOME",
):
    ENV.pop(key, None)


def run(command, cwd, check=True):
    result = subprocess.run(
        [str(x) for x in command],
        cwd=cwd,
        env=ENV,
        capture_output=True,
        text=True,
        timeout=240,
    )
    if check and result.returncode:
        raise RuntimeError(
            f"command failed: {command[0]}\n{result.stdout[-12000:]}\n{result.stderr[-12000:]}"
        )
    return result


PROGRAM = r"""
import json,os,subprocess,sys,threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import order_compare
from order_compare.datasets import list_cases,initialize_workspace,inspect_workspace,reset_workspace,original_paths
from order_compare.source import Study
base=Path(sys.argv[1]);assert Path(order_compare.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
manifest=list_cases();assert len(manifest['cases'])==12
for entry in manifest['cases']:
 result=initialize_workspace(entry['case_id'],base/entry['case_id']);assert result['identity']['case_sha256']==entry['sha256'] and result['matches_seed'] and Path(result['cases']).stat().st_mode&0o777==0o600
busy=inspect_workspace(base/'busy-operations');assert busy['orders']==24
fresh=reset_workspace(base/'busy-operations',base/'fresh',busy['identity']['instance_id']);assert fresh['identity']['instance_id']!=busy['identity']['instance_id'] and fresh['matches_seed']
study=Study.from_files(*original_paths());assert len(study.cases)==5
requests=[]
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_POST(self):
  body=json.loads(self.rfile.read(int(self.headers['Content-Length'])));index=len(requests);requests.append(body);case=study.cases[index//2]
  if index%2==0:
   calls=[{'id':f'order_{index}','type':'function','function':{'name':'read_order','arguments':json.dumps({'order_id':case.order_id})}},{'id':f'request_{index}','type':'function','function':{'name':'read_request','arguments':'{}'}},{'id':f'policy_{index}','type':'function','function':{'name':'read_policy','arguments':'{}'}}]
  else:
   args={'order_id':case.order_id,**study.expectations[case.case_id].model_dump(),'reason':'Controlled installed native proposal from supplied source'}
   calls=[{'id':f'final_{index}','type':'function','function':{'name':'submit_proposal','arguments':json.dumps(args)}}]
  raw=json.dumps({'id':f'chatcmpl_dist_{index}','object':'chat.completion','created':1792144800,'model':'gpt-observed-dist','choices':[{'index':0,'message':{'role':'assistant','content':None,'tool_calls':calls},'finish_reason':'tool_calls'}],'usage':{'prompt_tokens':11,'completion_tokens':5,'total_tokens':16}}).encode()
  self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
service=ThreadingHTTPServer(('127.0.0.1',0),Handler);service.daemon_threads=True;thread=threading.Thread(target=service.serve_forever,daemon=True);thread.start()
env={**os.environ,'OPENAI_API_KEY':'synthetic-dist-key'}
cli=[sys.executable,'-I','-m','order_compare','--model','openai:gpt-synthetic-dist','--live','--max-runs','5','--max-provider-requests','30','--openai-base-url',f'http://127.0.0.1:{service.server_port}/v1','--output-root',str(base/'runs'),'--output',str(base/'qualified.report.json')]
try:
 child=subprocess.run(cli,env=env,capture_output=True,text=True,timeout=30);assert child.returncode==0,child.stdout+child.stderr
 output=json.loads(child.stdout);report=json.loads(Path(output['output']).read_text())
 assert report['status']=='completed' and len(requests)==10 and all(row['grade']['success'] for row in report['results'])
 assert [row['case_id'] for row in report['results']]==[case.case_id for case in study.cases]
 assert report['summaries']['openai:gpt-synthetic-dist']['usage']['requests']==10 and report['summaries']['openai:gpt-synthetic-dist']['cost_usd'] is None
 for row in report['results']:
  trace=json.loads(Path(row['receipt_path']).read_text());assert trace['native_clients_closed'] and trace['native'][-1]['response_model']=='gpt-observed-dist' and trace['successful_reads']==['read_order','read_request','read_policy']
 assert Path(output['output']).stat().st_mode&0o777==0o600
finally:service.shutdown();service.server_close();thread.join(2)
print('installed twelve populations/private reset and original five native CLI HTTP/grades passed')
"""


def exercise(python, base):
    base.mkdir()
    run([python.parent / "compare-orders", "--help"], base)
    manifest = json.loads(
        run([python, "-I", "-m", "order_compare", "datasets"], base).stdout
    )
    assert len(manifest["cases"]) == 12
    dry = json.loads(
        run(
            [
                python,
                "-I",
                "-m",
                "order_compare",
                "--model",
                "openai:gpt-synthetic-dist",
            ],
            base,
        ).stdout
    )
    assert (
        dry["mode"] == "dry_run"
        and dry["planned_agent_runs"] == 5
        and dry["maximum_prepared_provider_attempts"] == 30
    )
    run([python, "-I", "-c", PROGRAM, base], base)
    missing = run(
        [
            python.parent / "compare-orders",
            "--model",
            "openai:gpt-synthetic-dist",
            "--live",
            "--max-runs",
            "5",
            "--max-provider-requests",
            "30",
            "--output",
            base / "missing-key.report.json",
            "--output-root",
            base / "missing-key-runs",
        ],
        base,
        False,
    )
    assert missing.returncode == 1, missing.stdout + missing.stderr
    result = json.loads(missing.stdout)
    report = json.loads(Path(result["output"]).read_text())
    assert all(
        row["status"] == "error"
        and row["usage"]["requests"] == 0
        and row["usage"]["input_tokens"] is None
        for row in report["results"]
    )
    for row in report["results"]:
        trace = json.loads(Path(row["receipt_path"]).read_text())
        assert (
            trace["native"] == []
            and trace["native_clients_closed"]
            and trace["proposal"] is None
        )


def extract(path, destination):
    destination.mkdir()
    with tarfile.open(path) as archive:
        assert all(member.isfile() or member.isdir() for member in archive.getmembers())
        archive.extractall(destination, filter="data")
    (source,) = destination.iterdir()
    return source


def verify_source(source):
    manifest = json.loads((source / "source-manifest.json").read_text())
    assert {
        str(path.relative_to(source)) for path in source.rglob("*") if path.is_file()
    } == {row["path"] for row in manifest["files"]} | {"source-manifest.json"}
    for row in manifest["files"]:
        path = source / row["path"]
        assert (
            hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]
            and path.stat().st_size == row["bytes"]
            and path.stat().st_mode & 0o777 == row["mode"]
        )
    return manifest


def main():
    wheel = (
        ROOT / "dist" / f"order_exception_model_comparison-{VERSION}-py3-none-any.whl"
    )
    sdist = ROOT / "dist" / f"order_exception_model_comparison-{VERSION}.tar.gz"
    bundle = build()
    with tempfile.TemporaryDirectory(
        prefix="order-comparison-distribution-"
    ) as directory:
        temp = Path(directory)
        assert not temp.is_relative_to(ROOT)
        assert build(temp / "repeat.tar.gz")["sha256"] == bundle["sha256"]
        with ZipFile(wheel) as archive:
            assert (
                len(
                    [
                        name
                        for name in archive.namelist()
                        if name.startswith("order_compare/sample_data/")
                        and name.endswith(".json")
                    ]
                )
                == 13
            )
            assert all(
                "order_compare/original_data/" + name in archive.namelist()
                for name in ("cases.json", "expected.json")
            )
        requirements = temp / "requirements.txt"
        requirements.write_text(
            run(
                [
                    UV,
                    "export",
                    "--locked",
                    "--extra",
                    "test",
                    "--no-dev",
                    "--no-emit-project",
                    "--format",
                    "requirements-txt",
                ],
                ROOT,
            ).stdout
        )
        environment = temp / "wheel-env"
        run([UV, "venv", "--python", sys.executable, environment], temp)
        python = environment / "bin/python"
        run([UV, "pip", "sync", "--python", python, requirements], temp)
        run([UV, "pip", "install", "--python", python, "--no-deps", wheel], temp)
        exercise(python, temp / "wheel-case")
        source = extract(sdist, temp / "sdist")
        assert all(
            (source / name).exists()
            for name in (
                "uv.lock",
                "data/index.json",
                "fixtures/cases.json",
                "grader/expected.json",
                "scripts/build_datasets.py",
                "tests/test_cli_native.py",
                ".github/workflows/check.yml",
                "COMPATIBILITY.md",
            )
        )
        run(
            [
                UV,
                "sync",
                "--locked",
                "--extra",
                "test",
                "--no-editable",
                "--project",
                source,
            ],
            temp,
        )
        exercise(source / ".venv/bin/python", temp / "sdist-case")
        run(
            [source / ".venv/bin/python", "scripts/build_datasets.py", "--check"],
            source,
        )
        complete = extract(bundle["path"], temp / "complete")
        manifest = verify_source(complete)
        run(
            [
                UV,
                "sync",
                "--locked",
                "--extra",
                "test",
                "--no-editable",
                "--project",
                complete,
            ],
            temp,
        )
        exercise(complete / ".venv/bin/python", temp / "complete-case")
        run(
            [complete / ".venv/bin/python", "scripts/build_datasets.py", "--check"],
            complete,
        )
        suite = run([complete / ".venv/bin/python", "-m", "pytest", "-q"], complete)
        assert "97 passed" in suite.stdout, suite.stdout
        for row in manifest["files"]:
            assert (
                hashlib.sha256((complete / row["path"]).read_bytes()).hexdigest()
                == row["sha256"]
            )
    report = {
        **bundle,
        "checks": "fresh locked wheel/sdist/complete source, twelve private populations/reset, original five actual native CLI cases, default dry-run and missing-key receipts, complete97 suite",
    }
    (ROOT / "dist/qualification.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
