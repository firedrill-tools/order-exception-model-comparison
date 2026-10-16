# Order exception comparison development audit

## Required application

A proposal-only Pydantic AI order agent runs identical controlled business cases, policy and tools across explicit OpenAI/Anthropic/Gemini configurations. Keep external expectations outside model context and separate exact match from independent policy/source/tool constraints. Compare original actual behavior and measured usage, including failed calls; unknown is not zero. No real order/payment actions and no Firedrill evaluation engine.

## Reproduced atcf1a649ae01f441838f2833c54dd20229afa96e1

Original5 tests pass. Actual Pydantic AI TestModel invoked read_order with a nonexistent order, received an error, yet the name-only tool gate and a valid proposal produced success. A failure carrying synthetic observed usage was discarded and summarized as all-zero usage. A first proposer mutated captured_cents and the next model received different facts. Private proof /tmp/firedrill-order-compare-baselines.json. These caller/TestModel probes are not paid provider observations.

A separate actual pinned Pydantic AI/native OpenAI loopbackHTTP probe performed three valid reads, then returned a final structured tool call with finish_reason length. The proposal was returned and graded success. Private proof /tmp/firedrill-order-compare-terminal-baseline.json. Two controlled synthetic HTTP calls, no paid provider.

## Plan

1. Strict bounded immutable case/proposal/expectation contracts, coherent captured/refunded/stock facts, deep per-model input snapshots and external oracle authority, unique model/configuration labels, source-bound successful reads and unchanged source/policy/case order. Preserve original five cases/grader; richer data later. Correct unknown/partial failed usage aggregation without asserting fabricated costs or provider observations.
2. Actual owned cancellable Pydantic AI/native providers with explicit model/key/endpoint/configuration, terminal/original HTTP authority before tool/output release, original bytes/model/IDs/usage/errors and SDK defaults separated, one private prepared/final receipt per case/configuration, partial failed effort retained. Bound prepared provider requests/read tools/output/budgets, disable retries/implicit repairs; native cleanup before final failure. Support parent signals, deadline, recording faults and safe sequential progress. Never pass grading labels/answers/task metadata into model tools/prompts.
3. Qualify actual native OpenAI/Anthropic/Gemini SDK/HTTP tool/final paths and normal dry-run/live-gated CLI against controlled endpoints only. Preserve exact policy and tools across providers; report SDK/HTTP measurement provenance/coverage, failed cases and behavior variation without treating missing data as zero. Budget plans must bound requests, not just case/model pairs. Exclusive private output and full source/expectation hash continuity.
4. Rich coherent hash-bound starter/busy/ambiguous/boundary order/customer/payment/history cases and immutable external expectations; exclusive private key-free CLI/init/readback/reset and fresh locked wheel/sdist/complete source outside checkout, full suite and exact Linux/catalog evidence. Then Wave3.

## Parked

Live provider keys/enabled models/budget and semantic/billing comparison, qualified new Firedrill contract/persisted scenarios, publication/license. No paid model or actual order/payment action is authorized. Continue independent development; external gates do not block it.


## Integrity17 local checkpoint

17 checks pass. Strict bounded/revalidated/frozen source/proposal/oracle models reject unsafe cents/coercion/incoherent captures. Snapshot/copy authority protects identical model inputs and original grading facts, even if a caller deliberately bypasses a model's frozen flag. Unique model labels and source hashes preserve comparison identity. Successful read credit now excludes nonexistent orders; attempted calls remain separately observed in context. External case labels are excluded from order-tool content and proposal prompts. Original five cases/expected data unchanged.

Failed partial caller/framework usage is retained; incomplete/overflowed summaries stay unknown with known subtotals/coverage, and cost stays unknown. This is not original provider HTTP measurement qualification. Native length-finished output still needs terminal guards/owned SDK lifecycle/partial evidence. Push/exact LinuxCI next, then task2 native/CLI/source/data/distribution. User gates remain parked; no paid provider/real order action.


## Native41 local checkpoint

41 local checks pass. Public owned actual PydanticAI/native OpenAI3.31/Anthropic1.14/GoogleGenAI2.31 tool/final paths now require coherent original terminal content before tools/proposals. Wrong lookups remain failed attempts with source/policy/result hashes and no read credit. Original raw usage/error/model/ID/unknown fields survive before SDK normalization; cache/reasoning meanings and unknown Anthropic total/cost are explicit.6 prepared HTTP attempts/12 read intents/1024 requested output/zero SDK retries and requested budgets are enforced. Private prepared/final evidence, recording/source/deadline/parent cancel/close and failed partial usage are qualified. Instrumentation is explicitly off per Agent. Paid providers never called.

Push/exact Linux/native41 CI and catalog next. Then normal async comparison suite/CLI: bounded paid-call plan, all-case/config source/oracle continuity, private partial/final suite evidence, signal drain, failed provider continuation versus storage/source/cleanup stop, explicit unfinished/skipped population and coverage, exclusive output. Rich versioned data/private key-free CLI/init/readback/reset/fresh full distribution follow. Overall goal active; all external gates stay parked.
