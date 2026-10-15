# Order exception model comparison

A [Pydantic AI](https://pydantic.dev/docs/ai/models/overview/) agent proposes resolutions for the same synthetic order cases using configurable OpenAI, Anthropic and Gemini models. Each run uses the same order, customer-request and policy tools. A separate rubric checks exact action and amount, order identity, policy constraints, tool use, request counts, token usage and elapsed time.

## Run

Requires Python 3.12+ and `uv`:

```sh
uv sync --extra test
uv run pytest -q
uv run python -m order_compare --model openai:YOUR_MODEL --model anthropic:YOUR_MODEL
```

That command is a dry run and reports the planned five cases per model. For a live comparison, set the matching provider keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`) and choose enabled model IDs:

```sh
uv run python -m order_compare \
  --model openai:YOUR_MODEL --model anthropic:YOUR_MODEL --model google:YOUR_MODEL \
  --live --max-runs 15 --output comparison.report.json
```

The harness runs sequentially and records per-case failures rather than substituting canned answers. The report file is ignored by Git. `--max-runs` must cover the planned number of case/model pairs; an agent run can make multiple provider requests to use tools, and the report records those requests. The example never changes an order or issues a real refund. `grader/expected.json` stays outside the model prompt.

Local tests exercise the grade logic and Pydantic AI path without provider keys. They do not provide a live comparison or measured provider usage. A real comparison needs keys, model availability and a deliberate call budget. Firedrill integration awaits the qualified new release. Dependencies are pinned in `uv.lock`.
