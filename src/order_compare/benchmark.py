"""Same-case, same-rubric sequential comparison with measured usage."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from time import perf_counter

from .agent import propose
from .schema import OrderCase, Proposal


REQUIRED_TOOLS = {"read_order", "read_request", "read_policy"}


def grade(case: OrderCase, proposal: Proposal, expected: dict, tool_calls: list[str]) -> dict:
    issues = []
    if proposal.order_id != case.order_id:
        issues.append("wrong order ID")
    if proposal.action == "refund":
        remaining = case.captured_cents - case.refunded_cents
        if case.issue != "damaged" or case.replacement_stock > 0:
            issues.append("refund is not indicated by this policy")
        if remaining <= 0 or proposal.amount_cents <= 0 or proposal.amount_cents > remaining:
            issues.append("refund exceeds or ignores remaining captured amount")
    elif proposal.action == "replace":
        if case.issue != "damaged" or case.replacement_stock <= 0 or (
            case.refunded_cents >= case.captured_cents):
            issues.append("replacement is unavailable or inappropriate")
        if proposal.amount_cents != 0:
            issues.append("non-refund action has an amount")
    elif proposal.amount_cents != 0:
        issues.append("non-refund action has an amount")
    missing_tools = sorted(REQUIRED_TOOLS - set(tool_calls))
    if missing_tools:
        issues.append("required read tools not called: " + ", ".join(missing_tools))
    exact = proposal.action == expected["action"] and proposal.amount_cents == expected["amount_cents"]
    return {"exact_match": exact, "constraints_pass": not issues, "success": exact and not issues,
            "issues": issues}


def run_suite(cases: list[OrderCase], expectations: dict[str, dict], models: list[str],
              proposer=propose, execution: str = "live") -> dict:
    if not cases or not models:
        raise ValueError("cases and models must be nonempty")
    if len({case.case_id for case in cases}) != len(cases):
        raise ValueError("case IDs must be unique")
    if {case.case_id for case in cases} != set(expectations):
        raise ValueError("every case needs exactly one external expectation")
    results = []
    for model in models:
        for case in cases:
            started = perf_counter()
            try:
                proposal, usage, tool_calls = proposer(case, model)
                proposal = Proposal.model_validate(proposal)
                result = {"model": model, "case_id": case.case_id, "status": "completed",
                          "proposal": proposal.model_dump(), "usage": usage,
                          "tool_calls": tool_calls,
                          "grade": grade(case, proposal, expectations[case.case_id], tool_calls)}
            except Exception as exc:
                result = {"model": model, "case_id": case.case_id, "status": "error",
                          "error": str(exc), "usage": None, "grade": None}
            result["elapsed_ms"] = round((perf_counter() - started) * 1000, 2)
            results.append(result)
    summaries = {}
    for model in models:
        rows = [row for row in results if row["model"] == model]
        completed = [row for row in rows if row["status"] == "completed"]
        summaries[model] = {
            "cases": len(rows), "completed": len(completed),
            "exact_matches": sum(row["grade"]["exact_match"] for row in completed),
            "constraint_passes": sum(row["grade"]["constraints_pass"] for row in completed),
            "successes": sum(row["grade"]["success"] for row in completed),
            "usage": {
                field: sum((row["usage"] or {}).get(field, 0) for row in completed)
                for field in ("requests", "input_tokens", "output_tokens", "total_tokens")
            },
        }
    choices = defaultdict(dict)
    for row in results:
        if row["status"] == "completed":
            choices[row["case_id"]][row["model"]] = (
                row["proposal"]["action"], row["proposal"]["amount_cents"])
    variation = {case_id: {model: {"action": action, "amount_cents": amount}
                           for model, (action, amount) in values.items()}
                 for case_id, values in choices.items() if len(set(values.values())) > 1}
    return {"execution": execution, "started_at": datetime.now(timezone.utc).isoformat(),
            "models": models, "case_count": len(cases), "results": results,
            "summaries": summaries, "behavior_variation": variation}
