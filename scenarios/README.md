# Shared case set

`fixtures/cases.json` is the exact model-visible case population. `grader/expected.json` is loaded by the harness only after each response; it is never included in the agent prompt. All models receive the same instructions, tools, records and case order. Runs are sequential, and each model sees five fresh, independent cases. One agent run may make multiple provider requests while using tools.

The cases cover damage with stock, damage without stock, an address change after shipping, a fully refunded order, and a delayed but still moving parcel. The rubric checks action, integer amount, order identity, policy constraints and whether the order, request and policy tools were called. The report retains per-case outputs, errors, measured token usage and latency, plus per-model totals and any action/amount variation across models.

Live results depend on the chosen model versions and keys. Offline tests use scripted proposals and a Pydantic AI test model; they must not be reported as provider comparisons.
