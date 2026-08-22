# Property-wise protection ablation result

**Date:** 2026-08-23

**Status:** Retained offline verification ablation.

## Question

Does property-wise protection prevent a harness promotion that an aggregate
reward and passed-property-count rule would accept?

## Setup

The ablation replays two retained official protection comparisons under two
policies. The aggregate-only policy accepts a candidate when reward and total
passed-property count do not decrease. The property-wise policy additionally
requires the candidate to retain every property passed by the parent. No new
Evolver, Worker, or verifier call was made.

## Result

- On `brinson-sector-attribution`, Quant-H0 and the holdings candidate both
  passed 42/42 properties with reward 1. Both policies produce `PROMOTE`.
- On `localvol-barrier`, Quant-H0 and the Search-v2 candidate both passed 38/39
  properties with reward 0.96. Quant-H0 failed
  `barrier_outputs_reasonable`, while the candidate failed
  `vanilla_mc_close_to_surface`. Aggregate-only produces `PROMOTE`; the
  property-wise policy produces `ROLLBACK`.

Across the two retained cases, the policies disagree once, and aggregate-only
would make one false promotion relative to the accepted property-preservation
criterion.

## Interpretation and boundary

Property identity is not interchangeable with aggregate count. The local-vol
tie hides a regression in a previously passing research-object check, so the
property-wise rule changes an actual lifecycle decision. This supports the
verification design; it does not show that Quant Research State search
outperforms a generic Evolver and it is not a new benchmark run.

Compact record:
`data/breadth/QF_PROTECTION_POLICY_ABLATION_RESULT.json`.
