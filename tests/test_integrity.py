import pytest
from pydantic import ValidationError
from order_compare.benchmark import run_suite
from order_compare.schema import OrderCase
from test_comparison import CASES, EXPECTED, TOOLS, correct


def test_each_model_receives_the_same_independent_original_case_snapshot():
    seen = []

    def mutate(case, model):
        seen.append(case.captured_cents)
        if model == "first":
            object.__setattr__(case, "captured_cents", 999999)
        return (
            correct(case),
            {"requests": 1, "input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            TOOLS,
        )

    original = CASES[0].model_copy(deep=True)
    report = run_suite(
        [original],
        {original.case_id: EXPECTED[original.case_id]},
        ["first", "second"],
        proposer=mutate,
        execution="offline_fixture",
    )
    assert seen == [7200, 7200] and original.captured_cents == 7200
    assert len({row["case_sha256"] for row in report["results"]}) == 1


def test_failed_partial_usage_is_counted_and_missing_measurements_remain_unknown():
    class ObservedFailure(RuntimeError):
        usage = {
            "requests": 1,
            "input_tokens": 7,
            "output_tokens": 0,
            "total_tokens": 7,
        }

    def failed(*args):
        raise ObservedFailure("controlled failure after synthetic observed usage")

    case = CASES[0]
    report = run_suite(
        [case],
        {case.case_id: EXPECTED[case.case_id]},
        ["failed"],
        proposer=failed,
        execution="offline_fixture",
    )
    assert (
        report["results"][0]["status"] == "error"
        and report["summaries"]["failed"]["usage"] == ObservedFailure.usage
    )

    def unknown(*args):
        raise RuntimeError("no measurement")

    report = run_suite(
        [case],
        {case.case_id: EXPECTED[case.case_id]},
        ["unknown"],
        proposer=unknown,
        execution="offline_fixture",
    )
    assert all(
        value is None for value in report["summaries"]["unknown"]["usage"].values()
    )


@pytest.mark.parametrize(
    "change",
    [
        {"captured_cents": True},
        {"refunded_cents": 999999},
        {"replacement_stock": 1.5},
        {"captured_cents": 2**53},
        {"customer_request": " "},
    ],
)
def test_unsafe_case_facts_are_refused_without_repair(change):
    with pytest.raises(ValidationError):
        OrderCase.model_validate(CASES[0].model_copy(update=change))


def test_duplicate_model_labels_are_rejected_before_proposing():
    def forbidden(*args):
        raise AssertionError("must not call")

    with pytest.raises(ValueError, match="unique"):
        run_suite(
            CASES,
            EXPECTED,
            ["same", "same"],
            proposer=forbidden,
            execution="offline_fixture",
        )


@pytest.mark.parametrize(
    "expected",
    [
        {"action": "refund", "amount_cents": True},
        {"action": "replace", "amount_cents": 0, "hidden_answer": "extra"},
    ],
)
def test_invalid_external_expectation_is_refused_before_proposing(expected):
    def forbidden(*args):
        raise AssertionError("must not call provider")

    with pytest.raises(ValidationError):
        run_suite(
            CASES[:1],
            {CASES[0].case_id: expected},
            ["unused"],
            proposer=forbidden,
            execution="offline_fixture",
        )


def test_partial_and_overflowed_measurements_do_not_become_complete_totals():
    def partial(case, model):
        if case.case_id == CASES[1].case_id:
            raise RuntimeError("unmeasured failure")
        return (
            correct(case),
            {"requests": 1, "input_tokens": 7, "output_tokens": 0, "total_tokens": 7},
            TOOLS,
        )

    expected = {case.case_id: EXPECTED[case.case_id] for case in CASES[:2]}
    report = run_suite(
        CASES[:2], expected, ["partial"], proposer=partial, execution="offline_fixture"
    )
    assert report["summaries"]["partial"]["usage"]["input_tokens"] is None
    assert report["summaries"]["partial"]["usage_coverage"]["input_tokens"] == {
        "observed_rows": 1,
        "rows": 2,
        "known_subtotal": 7,
        "overflow": False,
    }

    def overflow(case, model):
        return (
            correct(case),
            dict.fromkeys(
                ("requests", "input_tokens", "output_tokens", "total_tokens"), 2**53 - 1
            ),
            TOOLS,
        )

    report = run_suite(
        CASES[:2],
        expected,
        ["overflow"],
        proposer=overflow,
        execution="offline_fixture",
    )
    assert all(
        value is None for value in report["summaries"]["overflow"]["usage"].values()
    )
    assert (
        report["summaries"]["overflow"]["usage_coverage"]["requests"]["overflow"]
        is True
    )


def test_actual_framework_successful_reads_exclude_external_case_label_and_oracle():
    import json
    from pydantic_ai.models.function import FunctionModel
    from pydantic_ai.messages import (
        ModelResponse,
        ToolCallPart,
        ToolReturnPart,
        UserPromptPart,
    )
    from order_compare.agent import CaseContext, build_agent

    case = CASES[0]
    calls = []

    def model(messages, info):
        calls.append(messages)
        if len(calls) == 1:
            return ModelResponse(
                parts=[
                    ToolCallPart("read_order", {"order_id": case.order_id}, "order"),
                    ToolCallPart("read_request", {}, "request"),
                    ToolCallPart("read_policy", {}, "policy"),
                ]
            )
        return ModelResponse(
            parts=[
                ToolCallPart(
                    info.output_tools[0].name, correct(case).model_dump(), "final"
                )
            ]
        )

    context = CaseContext(case)
    result = build_agent(FunctionModel(model)).run_sync(
        f"Resolve order {case.order_id}", deps=context
    )
    assert set(context.tool_calls) == set(TOOLS) and all(
        item["successful"] for item in context.tool_attempts
    )
    assert grade_result(case, result.output, context.tool_calls)["success"]
    order_parts = [
        part
        for message in result.all_messages()
        for part in message.parts
        if isinstance(part, ToolReturnPart) and part.tool_name == "read_order"
    ]
    facts = json.loads(order_parts[0].content)
    assert (
        facts["order_id"] == case.order_id
        and "case_id" not in facts
        and "customer_request" not in facts
    )
    assert "expected" not in facts and "action" not in facts


def grade_result(case, proposal, tool_calls):
    from order_compare.benchmark import grade

    return grade(case, proposal, EXPECTED[case.case_id], tool_calls)
