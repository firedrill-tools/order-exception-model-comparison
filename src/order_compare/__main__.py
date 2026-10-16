"""Key-free plan or explicit bounded native comparison with private partial proof."""

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
import uuid
from pathlib import Path
from .comparison import run_suite_async
from .source import Study, validate_models
from .native import DEFAULT_URLS, REQUEST_LIMIT
from .datasets import (
    list_cases,
    initialize_workspace,
    inspect_workspace,
    reset_workspace,
    original_paths,
)


def publish_report(path, report):
    staged = path.with_name("." + str(uuid.uuid4()) + ".tmp")
    owned = False
    try:
        with staged.open("xb") as file:
            owned = True
            os.chmod(staged, 0o600)
            file.write(
                (
                    json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False)
                    + "\n"
                ).encode()
            )
            file.flush()
            os.fsync(file.fileno())
        os.link(staged, path)
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if owned:
            staged.unlink(missing_ok=True)


async def execute(study, models, args):
    loop = asyncio.get_running_loop()
    task = asyncio.current_task()
    previous = {}
    seen = []

    def stop(number, frame):
        if not seen:
            seen.append(number)
            task.cancel(f"Received {signal.Signals(number).name}")
            loop.call_soon_threadsafe(lambda: None)

    for name in ("SIGINT", "SIGTERM", "SIGHUP"):
        if hasattr(signal, name):
            number = getattr(signal, name)
            previous[number] = signal.getsignal(number)
            signal.signal(number, stop)
    provider_options = {
        model: {"base_url": getattr(args, model.split(":", 1)[0] + "_base_url")}
        for model in models
    }
    try:
        report = await run_suite_async(
            study,
            models,
            output_root=args.output_root,
            timeout_seconds=args.timeout_seconds,
            case_timeout_seconds=args.case_timeout_seconds,
            provider_options=provider_options,
        )
        code = (
            1
            if any(row["status"] == "error" for row in report["results"])
            else 2
            if any(not row["grade"]["success"] for row in report["results"])
            else 0
        )
        return report, code
    except asyncio.CancelledError as error:
        number = seen[0] if seen else None
        report = getattr(
            error, "report", {"receipt_path": getattr(error, "receipt_path", None)}
        )
        report.update(
            status="interrupted",
            signal=signal.Signals(number).name if number is not None else None,
        )
        return report, 128 + number if number is not None else 130
    except Exception as error:
        if not hasattr(error, "report"):
            raise
        report = error.report
        report.update(
            status="failed", error={"name": type(error).__name__, "message": str(error)}
        )
        return report, 1
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)


def main():
    import pydantic_ai

    # Public console-output setting; embedding APIs keep the caller's setting.
    pydantic_ai.BANNER_ENABLED = False
    logging.disable(logging.CRITICAL)
    arguments = sys.argv[1:]
    if arguments and arguments[0] in {"datasets", "init", "workspace", "reset"}:
        parser = argparse.ArgumentParser(
            description="Private model-free comparison studies"
        )
        commands = parser.add_subparsers(dest="command", required=True)
        commands.add_parser("datasets")
        initialize = commands.add_parser("init")
        initialize.add_argument("--case", required=True)
        initialize.add_argument("--directory", type=Path, required=True)
        inspect = commands.add_parser("workspace")
        inspect.add_argument("directory", type=Path)
        reset = commands.add_parser("reset")
        reset.add_argument("directory", type=Path)
        reset.add_argument("--to", type=Path, required=True)
        reset.add_argument("--instance", required=True)
        args = parser.parse_args(arguments)
        if args.command == "datasets":
            result = list_cases()
        elif args.command == "init":
            result = initialize_workspace(args.case, args.directory)
        elif args.command == "workspace":
            result = inspect_workspace(args.directory)
        else:
            result = reset_workspace(args.directory, args.to, args.instance)
        print(json.dumps(result, indent=2))
        return 0
    default_cases, default_expected = original_paths()
    parser = argparse.ArgumentParser(
        description="Compare the same immutable order cases with bounded native requests"
    )
    parser.add_argument("--cases", type=Path, default=default_cases)
    parser.add_argument("--expectations", type=Path, default=default_expected)
    parser.add_argument(
        "--model",
        action="append",
        required=True,
        help="repeat for openai:, anthropic: or google: enabled model IDs",
    )
    parser.add_argument(
        "--live", action="store_true", help="make actual native provider requests"
    )
    parser.add_argument(
        "--max-runs", type=int, help="explicit case/model execution ceiling"
    )
    parser.add_argument(
        "--max-provider-requests",
        type=int,
        help="explicit worst-case prepared native HTTP attempt ceiling",
    )
    parser.add_argument("--timeout-seconds", type=float, default=300)
    parser.add_argument("--case-timeout-seconds", type=float, default=60)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--output", type=Path, default=Path("comparison.report.json"))
    for provider, url in DEFAULT_URLS.items():
        parser.add_argument("--" + provider + "-base-url", default=url)
    args = parser.parse_args()
    models = validate_models(args.model)
    study = Study.from_files(args.cases, args.expectations)
    study.guard()
    count = len(study.cases) * len(models)
    attempts = count * REQUEST_LIMIT
    if not args.live:
        print(
            json.dumps(
                {
                    "mode": "dry_run",
                    "models": models,
                    "cases": len(study.cases),
                    "planned_agent_runs": count,
                    "maximum_prepared_provider_attempts": attempts,
                    "per_case_request_limit": REQUEST_LIMIT,
                    "output": str(args.output),
                    "output_exists": os.path.lexists(args.output),
                    "study": study.public(),
                    "cost_usd": None,
                },
                indent=2,
            )
        )
        return 0
    if args.max_runs is None or args.max_runs < count:
        parser.error(f"live run needs --max-runs at least {count}")
    if args.max_provider_requests is None or args.max_provider_requests < attempts:
        parser.error(
            f"live run needs --max-provider-requests at least {attempts} (prepared attempts; upstream billing is unknown)"
        )
    if os.path.lexists(args.output):
        raise FileExistsError("comparison output already exists")
    if not args.output.parent.is_dir():
        raise ValueError("comparison output parent must exist")
    report, code = asyncio.run(execute(study, models, args))
    try:
        publish_report(args.output, report)
    except Exception as error:
        error.receipt_path = report.get("receipt_path")
        raise
    print(
        json.dumps(
            {
                "output": str(args.output),
                "status": report["status"],
                "receipt_path": report["receipt_path"],
                "summaries": report["summaries"],
                "behavior_variation": report["behavior_variation"],
            },
            indent=2,
            allow_nan=False,
        )
    )
    return code


def cli():
    try:
        return main()
    except Exception as error:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error": {"name": type(error).__name__, "message": str(error)},
                    "receipt_path": getattr(error, "receipt_path", None),
                }
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(cli())
