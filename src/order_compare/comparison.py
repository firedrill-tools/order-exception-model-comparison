"""Sequential comparison with private partial evidence and one immutable study."""

import asyncio
import math
import time
import uuid
from copy import deepcopy
from pathlib import Path
from .agent import POLICY
from .benchmark import grade, report_results
from .evidence import Receipt, now, sha
from .source import Study, validate_models
from .native import REQUEST_LIMIT, TOOL_LIMIT, configuration
from .worker import propose_async


class ComparisonReceipt(Receipt):
    def __init__(self, study, models, output_root, timeout, writer):
        self.deadline = time.monotonic() + timeout
        self.writer = writer
        self.recording_error = None
        self.native_failure = None
        self.source_guard = study.guard
        root = Path(output_root or ".runs")
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory = root / str(uuid.uuid4())
        directory.mkdir(mode=0o700)
        self.path = directory / "comparison.json"
        self.data = {
            "schema_version": 1,
            "run_id": directory.name,
            "status": "prepared",
            "execution_kind": "native_comparison_suite",
            "started_at": now(),
            "finished_at": None,
            "study": study.public(),
            "source_documents": list(study.sources),
            "cases_snapshot": [case.model_dump(mode="json") for case in study.cases],
            "external_expectations_snapshot": {
                key: value.model_dump() for key, value in study.expectations.items()
            },
            "models": list(models),
            "policy_sha256": sha(POLICY.encode()),
            "limits": {
                "case_model_pairs": len(study.cases) * len(models),
                "prepared_provider_attempts": len(study.cases)
                * len(models)
                * REQUEST_LIMIT,
                "per_case_requests": REQUEST_LIMIT,
                "per_case_read_calls": TOOL_LIMIT,
                "requested_output_tokens_per_turn": 1024,
            },
            "active": None,
            "results": [],
            "report": None,
            "error": None,
            "cost_usd": None,
        }

    def finish(self, report, failure):
        self.data.update(
            status="failed" if failure else report["status"],
            finished_at=now(),
            report=report,
            error=None
            if failure is None
            else {"name": type(failure).__name__, "message": str(failure)},
        )
        self.save(final=True)


async def run_suite_async(
    study,
    models,
    *,
    output_root=None,
    timeout_seconds=300,
    case_timeout_seconds=60,
    provider_options=None,
    transport_factory=None,
    writer=None,
):
    if not isinstance(study, Study):
        raise ValueError("a validated immutable Study is required")
    models = validate_models(models)
    if (
        type(timeout_seconds) not in (int, float)
        or not 0 < timeout_seconds <= 3600
        or not math.isfinite(timeout_seconds)
    ):
        raise ValueError("suite timeout must be finite and in (0,3600]")
    if (
        type(case_timeout_seconds) not in (int, float)
        or not 0 < case_timeout_seconds <= 120
        or not math.isfinite(case_timeout_seconds)
    ):
        raise ValueError("case timeout must be finite and in (0,120]")
    supplied = deepcopy(provider_options or {})
    if set(supplied) - set(models):
        raise ValueError("provider options name an unplanned model")
    if any(
        set(value) - {"api_key", "base_url", "config"} for value in supplied.values()
    ):
        raise ValueError(
            "provider options support only explicit key/endpoint/configuration"
        )
    configs = {
        identifier: supplied.get(identifier, {}).get("config")
        or configuration(
            identifier,
            api_key=supplied.get(identifier, {}).get("api_key"),
            base_url=supplied.get(identifier, {}).get("base_url"),
            validate=False,
        )
        for identifier in models
    }
    receipt = ComparisonReceipt(study, models, output_root, timeout_seconds, writer)
    results = []
    report = None
    failure = None
    try:
        receipt.save()
        receipt.guard()
        for model in models:
            for case in study.cases:
                receipt.guard()
                receipt.data.update(
                    active={"model": model, "case_id": case.case_id},
                    status="case_prepared",
                )
                receipt.save()
                receipt.guard()
                started = time.perf_counter()
                row = None
                case_error = None
                try:
                    remaining = receipt.deadline - time.monotonic()
                    proposal, usage, reads = await propose_async(
                        case.model_copy(deep=True),
                        model,
                        output_root=receipt.path.parent / "cases",
                        timeout_seconds=min(case_timeout_seconds, remaining),
                        source_guard=study.guard,
                        config=configs[model],
                        transport=transport_factory(model, case.model_copy(deep=True))
                        if transport_factory
                        else None,
                    )
                    row = {
                        "model": model,
                        "case_id": case.case_id,
                        "status": "completed",
                        "proposal": proposal.model_dump(),
                        "usage": usage,
                        "receipt_path": usage.get("receipt_path"),
                        "tool_calls": reads,
                        "grade": grade(
                            case, proposal, study.expectations[case.case_id], reads
                        ),
                    }
                except BaseException as error:
                    case_error = error
                    row = {
                        "model": model,
                        "case_id": case.case_id,
                        "status": "error"
                        if isinstance(error, Exception)
                        else "interrupted",
                        "error": {"name": type(error).__name__, "message": str(error)},
                        "usage": getattr(error, "usage", None),
                        "receipt_path": getattr(error, "receipt_path", None),
                        "grade": None,
                    }
                row.update(
                    case_sha256=sha(case.model_dump(mode="json")),
                    usage_source="original_provider_fields_and_prepared_attempts",
                    cost_usd=None,
                    elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
                )
                results.append(row)
                receipt.data["results"] = results
                receipt.save()
                if case_error is not None and (
                    not isinstance(case_error, Exception)
                    or getattr(case_error, "recording_failed", False)
                    or not getattr(case_error, "cleanup_confirmed", True)
                ):
                    raise case_error
                receipt.guard()
        receipt.data["active"] = None
        receipt.guard()
    except BaseException as error:
        failure = error
    finally:
        completed = {(row["model"], row["case_id"]) for row in results}
        for model in models:
            for case in study.cases:
                if (model, case.case_id) not in completed:
                    results.append(
                        {
                            "model": model,
                            "case_id": case.case_id,
                            "status": "not_started",
                            "usage": None,
                            "grade": None,
                            "case_sha256": sha(case.model_dump(mode="json")),
                            "cost_usd": None,
                            "reason": "suite stopped before dispatch",
                        }
                    )
        report = report_results(
            study.cases,
            models,
            results,
            "native_provider_comparison",
            receipt.data["started_at"],
        )
        report.update(
            status="failed"
            if failure
            else "completed_with_errors"
            if any(row["status"] == "error" for row in results)
            else "completed",
            receipt_path=str(receipt.path),
            run_id=receipt.data["run_id"],
            study=study.public(),
            policy_sha256=receipt.data["policy_sha256"],
            limits=receipt.data["limits"],
        )
        receipt.data["results"] = results
        try:
            receipt.finish(report, failure)
        except BaseException as error:
            failure = failure or error
            report["status"] = "failed"
            receipt.data.update(
                status="failed",
                report=report,
                durable_status="failed",
                recording_error={"name": type(error).__name__, "message": str(error)},
            )
            try:
                receipt.save(final=True)
            except BaseException:
                receipt.data["durable_status"] = "unknown"
    if failure is not None:
        failure.report = report
        failure.receipt_path = str(receipt.path)
        failure.evidence = receipt.data
        raise failure
    return report
