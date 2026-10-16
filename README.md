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

Explore related applications in the [Firedrill example catalog](https://github.com/firedrill-tools/firedrill-example-catalog). Product and setup references: [Firedrill](https://firedrill.run/) and the [official developer documentation](https://docs.firedrill.run/). Use documentation matching the qualified release; this repository records its current integration limits above.


## Development checkpoint

17 local checks now qualify strict bounded immutable case/proposal/expectation contracts, coherent captured/refunded amounts, successful read credit, independent per-model case snapshots, immutable external oracle input, unique configuration labels and partial/unknown usage aggregation. A nonexistent order read does not satisfy read_order. Actual controlled FunctionModel reads qualify the positive three-tool path; external case labels and expectations are excluded from order-tool output. These remain scripted framework checks, not paid model measurements.

Failed caller/framework usage is retained when available; absent fields remain null and coverage records the known subtotal/observed rows. Overflowed totals remain unknown. Costs are unknown. This initial accounting checkpoint does not yet establish original provider HTTP measurements; normalized framework/caller provenance stays explicit. A comparison's first proposer cannot alter the next model's input or grading source. Original five business cases and external expectations are unchanged.

Native work remains active: an actual pinned OpenAI/Pydantic AI loopbackHTTP probe still returned a valid final structured proposal with finish_reason length and graded success. Owned native completion/measurement/lifecycle/private failure evidence, normal CLI budgets/signals, richer cases/private workspaces and fresh locked distributions remain in [PLAN.md](PLAN.md). No paid provider or real order/payment action was used. Live semantic/billing/Firedrill/publication gates remain parked.
