import json
from pathlib import Path

import pytest
from pydantic_ai.models.test import TestModel

from order_compare.agent import propose
from order_compare.benchmark import grade, run_suite
from order_compare.schema import OrderCase, Proposal


ROOT = Path(__file__).parent.parent
CASES = [OrderCase.model_validate(item) for item in json.loads(
    (ROOT / "fixtures" / "cases.json").read_text())]
EXPECTED = json.loads((ROOT / "grader" / "expected.json").read_text())
TOOLS = ["read_order", "read_request", "read_policy"]


def correct(case):
    target = EXPECTED[case.case_id]
    return Proposal(order_id=case.order_id, action=target["action"],
                    amount_cents=target["amount_cents"], reason="Grounded synthetic resolution")


def test_actual_pydantic_ai_agent_uses_all_three_tools_without_provider():
    output, usage, tool_calls = propose(CASES[0], TestModel())
    assert isinstance(output, Proposal)
    assert set(tool_calls) == set(TOOLS)
    assert usage["requests"] >= 1


def test_same_case_set_and_measurements_are_kept_separate_by_model():
    def scripted(case, model):
        if model == "scripted-correct":
            return correct(case), {"requests": 1, "input_tokens": 10,
                                   "output_tokens": 5, "total_tokens": 15}, TOOLS
        return Proposal(order_id=case.order_id, action="contact", amount_cents=0,
                        reason="Ask customer to confirm details"), {
                            "requests": 1, "input_tokens": 8, "output_tokens": 4,
                            "total_tokens": 12}, TOOLS

    report = run_suite(CASES, EXPECTED, ["scripted-correct", "scripted-contact"],
                       proposer=scripted, execution="offline_fixture")
    assert report["execution"] == "offline_fixture"
    assert len(report["results"]) == 10
    assert report["summaries"]["scripted-correct"]["successes"] == 5
    assert report["summaries"]["scripted-correct"]["usage"]["total_tokens"] == 75
    assert "damage-stock" in report["behavior_variation"]
    assert "delivery-delay" not in report["behavior_variation"]


def test_exact_match_does_not_override_policy_or_tool_constraints():
    case = CASES[1]
    overrefund = Proposal(order_id=case.order_id, action="refund", amount_cents=9000,
                          reason="Refund beyond capture")
    result = grade(case, overrefund, {"action": "refund", "amount_cents": 9000}, TOOLS)
    assert result["exact_match"] is True
    assert result["success"] is False
    assert "remaining captured amount" in " ".join(result["issues"])
    no_reads = grade(CASES[0], correct(CASES[0]), EXPECTED[CASES[0].case_id], [])
    assert no_reads["exact_match"] is True
    assert no_reads["success"] is False


def test_provider_error_is_recorded_not_scored_as_success():
    def broken(case, model):
        raise RuntimeError("synthetic provider unavailable")

    report = run_suite(CASES[:1], {CASES[0].case_id: EXPECTED[CASES[0].case_id]},
                       ["broken"], proposer=broken, execution="offline_fixture")
    assert report["results"][0]["status"] == "error"
    assert report["results"][0]["usage"] is None
    assert report["summaries"]["broken"]["completed"] == 0
    assert report["summaries"]["broken"]["successes"] == 0


def test_case_expectations_must_match_exactly():
    with pytest.raises(ValueError, match="exactly one"):
        run_suite(CASES, {}, ["unused"], proposer=lambda *_: None)
