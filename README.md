# Order exception model comparison with Pydantic AI

A [Pydantic AI](https://pydantic.dev/docs/ai/models/overview/) agent proposes resolutions for the same synthetic order cases using configurable OpenAI, Anthropic and Gemini models. Each run uses the same order, customer-request and policy tools. A separate rubric checks exact action and amount, order identity, policy constraints, tool use, request counts, token usage and elapsed time.

Simulate this Pydantic AI AI agent with [Firedrill](https://firedrill.run/), a simulation platform for AI agents. Start with the [Firedrill setup and simulation guide](firedrill/README.md); your coding agent can operate it while this application's runner stays in your repository or CI.

This example repository is publicly viewable. A project license has not been selected.

## Run

Requires Python 3.12+ and `uv`:

```sh
uv sync --locked --extra test
PYDANTIC_AI_NO_BANNER=1 uv run --locked pytest -q
uv run python -m order_compare --model openai:YOUR_MODEL --model anthropic:YOUR_MODEL
```

That command is a dry run and reports the planned five cases per model. For a live comparison, set the matching provider keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`) and choose enabled model IDs:

```sh
uv run python -m order_compare \
  --model openai:YOUR_MODEL --model anthropic:YOUR_MODEL --model google:YOUR_MODEL \
  --live --max-runs 15 --max-provider-requests 90 --output comparison.report.json
```

The harness runs sequentially and records per-case failures rather than substituting canned answers. The report file is ignored by Git. `--max-runs` must cover the planned number of case/model pairs; an agent run can make multiple provider requests to use tools, and the report records those requests. The example never changes an order or issues a real refund. `grader/expected.json` stays outside the model prompt.

Local tests exercise the grade logic and Pydantic AI path without provider keys. They do not provide a live comparison or measured provider usage. A real comparison needs keys, model availability and a deliberate call budget. A checked-in Firedrill adapter uses the released CLI/SDK; authenticated persisted-run verification remains separate. Dependencies are pinned in `uv.lock`.

Explore related applications in the [Firedrill examples](https://docs.firedrill.run/guides/examples). Product and setup references: [Firedrill](https://firedrill.run/) and the [official developer documentation](https://docs.firedrill.run/). Use documentation matching the qualified release; this repository records its current integration limits above.


## Development checkpoint

17 local checks now qualify strict bounded immutable case/proposal/expectation contracts, coherent captured/refunded amounts, successful read credit, independent per-model case snapshots, immutable external oracle input, unique configuration labels and partial/unknown usage aggregation. A nonexistent order read does not satisfy read_order. Actual controlled FunctionModel reads qualify the positive three-tool path; external case labels and expectations are excluded from order-tool output. These remain scripted framework checks, not paid model measurements.

Failed caller/framework usage is retained when available; absent fields remain null and coverage records the known subtotal/observed rows. Overflowed totals remain unknown. Costs are unknown. This initial accounting checkpoint does not yet establish original provider HTTP measurements; normalized framework/caller provenance stays explicit. A comparison's first proposer cannot alter the next model's input or grading source. Original five business cases and external expectations are unchanged.

At the initial integrity checkpoint, an actual pinned OpenAI/Pydantic AI loopbackHTTP probe returned a valid final structured proposal with finish_reason length and graded success. Owned native completion/measurement/lifecycle/private failure evidence, normal CLI budgets/signals, richer cases/private workspaces and fresh locked distributions remain in [PLAN.md](PLAN.md). No paid provider or real order/payment action was used. At that checkpoint, live semantic/billing/Firedrill/publication gates remained parked.


## Native case checkpoint

41 checks pass locally, including actual pinned Pydantic AI2.56.0/OpenAI3.31.0/Anthropic1.14.0/Google GenAI2.31.0 native tool/proposal paths. `propose` with a model identifier owns its native resources; `propose_async` is the async API. Explicit keys/endpoints support HTTPS or loopbackHTTP without URL credentials/query/fragment. Ambient token/profile credentials, proxies and redirects are not borrowed; Gemini uses its explicit Developer API backend. No model is substituted. Injected TestModel/FunctionModel instances remain caller-owned and framework-only evidence is labeled separately. Native Model instances and direct native builders cannot bypass the owned identifier entry point.

Every original provider turn must be a coherent completed tool turn before tools/output are released. OpenAI requires tool_calls, Anthropic tool_use, Gemini unblocked STOP function calls. Unknown/refused/truncated/pending/mixed output-read content fails before release. The output tool is submit_proposal; actual three read functions remain identical across providers. Tool receipts preserve actual arguments, source case/policy hashes, original result/hash and success; wrong order reads remain failed attempts without read credit. External case labels/expectations are excluded from prompts and tool results. The model proposes only; no order/payment changes occur.

Owned clients/SDKs use public provider constructors, zero SDK retries, nonstreaming JSON and explicit requested30-second HTTP phases/default60-second operation budget (up to120). Each case permits at most6 prepared HTTP attempts/12 read-tool calls and requests1024 output tokens per turn. Original decoded bytes/JSON/unknown fields/status/IDs/model/usage/errors precede SDK normalization. Original unknown/0/invalid counters remain distinct. Canonical report fields name their provider-specific source counters; cache/reasoning meanings differ and Anthropic total remains unknown when absent. Prepared attempts do not infer upstream receipt or billing. SDK messages/counters are separate, cost is unknown, and failed partial effort survives into the comparison.

Private0700 directories/0600 atomic flushed traces precede credentials/provider work. Recording faults prevent later calls or proposal release; native cancellation/deadline/client cleanup finishes before final failed evidence. Failed close cannot become a false closed proof through an emptied-stack retry. Source guard failures block later work. Persistent final recording failure exposes failed in-memory evidence/unknown durable status. Actual controlled tests qualify all three providers, truncation before reads/final output, HTTP failure usage, wrong-order evidence, recording/deadline/cancellation/close/source faults and normalization differences. Retained1MiB bounds do not establish hard wire/peak-memory/whole-run wall promises; synchronous local serialization/recording and cleanup remain outside them.

Normal comparison CLI budgets/signals/private suite receipts, full original source/oracle-file continuity, richer versioned cases/private workspaces and fresh distributions remain active. [PLAN.md](PLAN.md) retains these tasks. No paid provider or actual order/payment action has been used; at that checkpoint, live semantic/billing/Firedrill/publication gates remained parked.


## Immutable study and native comparison CLI

62 checks pass locally. [Native41 passed Linux at9ec7dde](https://github.com/firedrill-tools/order-exception-model-comparison/actions/runs/38897547635). The async comparison uses one validated immutable Study with64-case/eight-model support limits. It snapshots original case/expectation bytes, typed facts and hashes privately; external oracle data never enters model prompts/tools. Every configuration sees the same case order/source/policy, and native keys/endpoints are captured once for the suite. Optional transport factories receive independent case copies. Source changes stop the suite before further dispatch.

Dry-run remains key-free and reports both case/model pairs and the worst-case prepared HTTP ceiling (six per pair). Making native requests requires `--live`, sufficient `--max-runs` and sufficient `--max-provider-requests`. These are prepared attempt bounds, not inferred upstream receipt or a price quote. `--openai-base-url`, `--anthropic-base-url`, `--google-base-url`, `--case-timeout-seconds`, `--timeout-seconds` and `--output-root` configure explicit endpoints/budgets/evidence. Native models, exact policy/tool behavior and case order are preserved; provider-specific usage meanings remain labeled rather than treated as equivalent billed units.

A provider/case failure with confirmed cleanup is recorded and the suite continues. Source, recording, unconfirmed cleanup or parent interruption stops later work. Remaining population rows become not_started, with no fake usage or grade. Partial raw token subtotals survive even when an interrupted later request makes full totals unknown. Original SDK usage stays separate. Every actual case has a private attempt trace; a separate private suite trace preserves original source bytes, oracle snapshot, case results and the final/partial report.

Normal CLI local HTTP qualifies all three providers, same input/policy authority, explicit auth/proxy policy, continuation after rejected length output, request-ceiling/collision preflight, missing-key evidence and SIGINT/SIGTERM/SIGHUP cleanup. The signal path saves a partial comparison containing interrupted/unstarted rows after native drain. `--output` publishes a new0600 report exclusively; existing reports are preserved. A successful complete comparison returns0, completed policy/exact failures2, provider/infrastructure failure1, and signals130/143/129. Private traces distinguish original source/protocol/measurement evidence from structural grading; no semantic or billing quality is inferred.

Data/private workspace and distribution qualification follows below; [PLAN.md](PLAN.md) retains final CI and the portfolio handoff. This is a standalone proposal/comparison application; all actual test endpoints were local/synthetic, no paid provider or order/payment mutation. Live semantic/billing review, authenticated Firedrill persistence verification and license remain parked.


## Versioned study populations

97 checks pass locally. `order-comparison-studies`1.0.0 contains twelve hash-bound populations/four profiles. All customers, payments, shipment histories and stock snapshots are fictional imported business source; prior model/token/authentication/actual payment/paid-provider observations are unavailable. External expected answers remain in a separate file and never enter the model context.

| Profile | Populations |
| --- | --- |
| Starter | original-five (unchanged business cases/oracle), replacement, partial-refund |
| Busy | busy-operations:24 orders,12 customers,44 coherent capture/refund events |
| Ambiguous | conflicting-request, unfunded-refund, unconfirmed-loss |
| Boundary | hostile-request, fully-refunded-stock, one-cent-remaining, maximum-safe-cents, address-before-shipment |

All twelve populations run through the actual owned native SDK path with controlled responses. The largest supported cent value and one-cent remainder also pass actual Anthropic/Gemini SDK parsing without coercion. Controlled responses qualify source/protocol/accounting behavior, not live model arithmetic, obedience or semantic quality.

Model-free setup:

```sh
uv run --locked compare-orders datasets
uv run --locked compare-orders init --case busy-operations --directory /tmp/order-study
uv run --locked compare-orders workspace /tmp/order-study
uv run --locked compare-orders --cases /tmp/order-study/cases.json --expectations /tmp/order-study/expected.json --model openai:YOUR_ENABLED_MODEL
```

The last command is a key-free dry-run. Making native requests still needs deliberate live/run/request budgets and provider access. Initialization validates source-pinned index/population hashes and coherent customer/payment/shipping/stock relationships, then exclusively creates a0700 directory with0600 `cases.json`, external `expected.json`, `source-history.json`, `workspace.json` and `TASK.md`. The model reads current case facts, requests and policy; imported detailed history/task/fixture identity stay outside its tools. Source history describes the original seed snapshot, with explicit fictional provenance.

Readback validates current cases/oracle and shows source hashes and seed match. Valid human edits are preserved and distinguishable from the seed; historical source is not rewritten to pretend it measured those edits. Malformed/missing input or changed dataset identity is refused without repair. Reset creates a fresh copy/new instance while preserving old source/work/evidence:

```sh
uv run --locked compare-orders reset /tmp/order-study --to /tmp/order-study-fresh --instance CURRENT_INSTANCE_UUID
```

Existing directories/files/symlinks are preserved. Caller-injected proposer evidence is explicitly labeled and cannot claim live/native evidence. The CLI uses Pydantic AI's documented public banner control so JSON output does not depend on the caller's banner environment flag; embedding APIs retain the caller's setting.

## Distribution qualification

```sh
uv run --locked python scripts/build_datasets.py --check
uv build
PYDANTIC_AI_NO_BANNER=1 uv run --locked python scripts/check_distribution.py
```

Wheel data includes all thirteen population/index JSON files and the exact original five-case/expected files. The sdist includes all source/data/original fixtures/grader/tests/helpers/scripts/docs/CI/lockfiles. The deterministic complete source archive adds an exact per-file SHA256/size/mode manifest and is generated independently of Git/installed caches. Fresh locked wheel/sdist/complete-source environments outside checkout qualify console/module/default key-free planning, all twelve private populations/reset, original five native CLI cases over owned HTTP, exclusive private output and missing-key failed case receipts. Full97 suite runs from complete archived source and every original file hash remains unchanged. Repeated source bytes agree. CI uploads distributions and qualification.json; no package publication/license is implied.

Independent application implementation is complete; final exact Linux/artifact portability and catalog evidence are recorded in [COMPATIBILITY.md](COMPATIBILITY.md). Live provider availability/semantic billing review, authenticated Firedrill persistence verification and license remain parked. No actual order/payment mutation is implemented or authorized. Continue the portfolio with Wave3.

## Current Firedrill integration

Released CLI/SDK 2.2.2, current command invocation, remote operator MCP and recovery are documented in [firedrill/README.md](firedrill/README.md). Offline checks preserve actual private source/native-key behavior and explicit model/budget selection. Authenticated persisted runs and live quality/cost remain separate parked gates.
