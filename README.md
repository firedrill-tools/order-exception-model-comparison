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

At the initial integrity checkpoint, an actual pinned OpenAI/Pydantic AI loopbackHTTP probe returned a valid final structured proposal with finish_reason length and graded success. Owned native completion/measurement/lifecycle/private failure evidence, normal CLI budgets/signals, richer cases/private workspaces and fresh locked distributions remain in [PLAN.md](PLAN.md). No paid provider or real order/payment action was used. Live semantic/billing/Firedrill/publication gates remain parked.


## Native case checkpoint

41 checks pass locally, including actual pinned Pydantic AI2.56.0/OpenAI3.31.0/Anthropic1.14.0/Google GenAI2.31.0 native tool/proposal paths. `propose` with a model identifier owns its native resources; `propose_async` is the async API. Explicit keys/endpoints support HTTPS or loopbackHTTP without URL credentials/query/fragment. Ambient token/profile credentials, proxies and redirects are not borrowed; Gemini uses its explicit Developer API backend. No model is substituted. Caller-supplied Model instances remain caller-owned and framework-only evidence is labeled separately.

Every original provider turn must be a coherent completed tool turn before tools/output are released. OpenAI requires tool_calls, Anthropic tool_use, Gemini unblocked STOP function calls. Unknown/refused/truncated/pending/mixed output-read content fails before release. The output tool is submit_proposal; actual three read functions remain identical across providers. Tool receipts preserve actual arguments, source case/policy hashes, original result/hash and success; wrong order reads remain failed attempts without read credit. External case labels/expectations are excluded from prompts and tool results. The model proposes only; no order/payment changes occur.

Owned clients/SDKs use public provider constructors, zero SDK retries, nonstreaming JSON and explicit requested30-second HTTP phases/default60-second operation budget (up to120). Each case permits at most6 prepared HTTP attempts/12 read-tool calls and requests1024 output tokens per turn. Original decoded bytes/JSON/unknown fields/status/IDs/model/usage/errors precede SDK normalization. Original unknown/0/invalid counters remain distinct. Canonical report fields name their provider-specific source counters; cache/reasoning meanings differ and Anthropic total remains unknown when absent. Prepared attempts do not infer upstream receipt or billing. SDK messages/counters are separate, cost is unknown, and failed partial effort survives into the comparison.

Private0700 directories/0600 atomic flushed traces precede credentials/provider work. Recording faults prevent later calls or proposal release; native cancellation/deadline/client cleanup finishes before final failed evidence. Failed close cannot become a false closed proof through an emptied-stack retry. Source guard failures block later work. Persistent final recording failure exposes failed in-memory evidence/unknown durable status. Actual controlled tests qualify all three providers, truncation before reads/final output, HTTP failure usage, wrong-order evidence, recording/deadline/cancellation/close/source faults and normalization differences. Retained1MiB bounds do not establish hard wire/peak-memory/whole-run wall promises; synchronous local serialization/recording and cleanup remain outside them.

Normal comparison CLI budgets/signals/private suite receipts, full original source/oracle-file continuity, richer versioned cases/private workspaces and fresh distributions remain active. [PLAN.md](PLAN.md) retains these tasks. No paid provider or actual order/payment action has been used; live semantic/billing/Firedrill/publication gates stay parked.
