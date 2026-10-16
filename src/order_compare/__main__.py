"""Dry-run plan or explicitly budgeted live model comparison."""

import argparse
import json
from pathlib import Path

from .agent import _check_key
from .benchmark import run_suite
from .schema import OrderCase


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare models on the same order exceptions"
    )
    parser.add_argument("--cases", type=Path, default=Path("fixtures/cases.json"))
    parser.add_argument(
        "--expectations", type=Path, default=Path("grader/expected.json")
    )
    parser.add_argument(
        "--model",
        action="append",
        required=True,
        help="repeat for openai:, anthropic: or google: model IDs",
    )
    parser.add_argument(
        "--live", action="store_true", help="make actual paid provider calls"
    )
    parser.add_argument(
        "--max-runs", type=int, help="maximum allowed case/model agent runs"
    )
    parser.add_argument("--output", type=Path, default=Path("comparison.report.json"))
    args = parser.parse_args()
    cases = [
        OrderCase.model_validate(case) for case in json.loads(args.cases.read_text())
    ]
    expectations = json.loads(args.expectations.read_text())
    count = len(cases) * len(args.model)
    if not args.live:
        print(
            json.dumps(
                {
                    "mode": "dry_run",
                    "models": args.model,
                    "cases": len(cases),
                    "planned_agent_runs": count,
                    "output": str(args.output),
                },
                indent=2,
            )
        )
        return
    if args.max_runs is None or count > args.max_runs:
        parser.error(f"live run needs --max-runs at least {count}")
    if len(set(args.model)) != len(args.model):
        parser.error("model IDs must be unique")
    for model in args.model:
        _check_key(model)
    report = run_suite(cases, expectations, args.model)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "summaries": report["summaries"],
                "behavior_variation": report["behavior_variation"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
