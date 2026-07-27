# Decision Record: QFBench Full-Harness Feedback A/B Result

> Date: 2026-07-27
> Status: accepted as completed matched-protocol adaptation evidence; insufficient for a stable evolution-gain or transfer claim
> Scope: Control versus Rich optimize-only feedback exposure in the GDPval-style full harness
> Preserves: the immutable 2026-07-25 historical run and the 2026-07-26 verifier repair identities

## Decision Summary

Accept the completed Control/Rich pair as evidence that the secure full-harness feedback pipeline can produce, admit, falsify, and keep a useful optimize-task harness edit. Do not promote the Rich candidate to the canonical worker and do not report `+0.155556` as a stable causal or generalization effect until the matched experiment is repeated across independent model seeds.

The current result supersedes the prior *unfinished A/B* state. It does not rewrite or repair the 14 contaminated scores in `qfbench-30x5-20260725`.

## Fixed Identity

| Field | Value |
|---|---|
| Benchmark commit | `024921eb507fcc0c4ffe3e0a96802724be1ae84a` |
| Control run | `qfbench-30x5-full-control-20260727-024921eb` |
| Rich run | `qfbench-30x5-full-rich-20260727-024921eb` |
| Model | `deepseek/deepseek-v4-pro` |
| Task manifest digest | `9eae45988c1d5d6cedc670d3cc23a6f210ae13c78a3d7f5092ff9a5932244295` |
| Template identity digest | `d1f0272f452e13c3314648f3b570e8ca60edb5e35bb733c6da3026212cf60a99` |
| Verifier mapping digest | `b748cfb96455a7ca1fd63936e3b9e91588fc666fa9e74c5ef6e8948ab79ace9f` |
| Seed digest | `4ad9cd8d8450dabc845e7bbc6467127d2405f2db156da2d89f152f06887ac46c` |
| Admission policy digest | `6712f152063127a760f31768b44c62b032ba91191575af21bc4352f2e40e92bb` |
| Control / Rich feedback digests | `9a2e4bb98ddcf4f003d630d3460777b4a06890582417ac85c14030e95bd925d4` / `73ae3310058b19b49dfad367d3d6e21ac9c02e09dcbd09512fb3a334b35be8d3` |

The feedback digest is the only intended arm-level treatment difference. Each arm completed the preregistered 20 optimize tasks across seed plus five candidates and ten held-out tasks at seed/final: 140 official score records per arm.

## Measured Result

| Metric | Control | Rich |
|---|---:|---:|
| Optimize seed → final | 0.612500 → 0.612500 | 0.564583 → 0.720139 |
| Adaptation gain | 0.000000 | +0.155556 |
| Keeps / rollbacks | 0 / 5 | 1 / 4 |
| Held-out seed → final | 0.583333 → 0.750000 | 0.666667 → 0.583333 |
| Evidence records read | 94 | 203 |
| Recorded execution seconds | 48,872.566 | 56,485.222 |
| Clean lifecycle identities | 278 / 278 | 276 / 276 |

The primary matched-protocol point estimate is `RichFeedbackGain = +0.155556`. Rich iteration 3 was kept because it improved the incumbent by `+0.155556` with no domain regression. Iteration 4 scored still higher overall but was correctly rolled back for an execution/microstructure domain regression.

## Interpretation Boundary

The result establishes the following:

- optimize-only public instruction/environment/rubric and worker-observable evidence can be consumed by an isolated evolver without exposing hidden verifier inputs;
- deterministic admission and keep/rollback gates operate on the emitted full-harness candidate;
- the Rich arm found one useful prompt edit where Control found none;
- both completed arms passed exact schedule, identity, leak-scan, checkpoint/resume, and lifecycle cleanup audits.

The result does **not** establish the following:

- a statistically stable feedback treatment effect from one paired run;
- held-out transfer, because Rich held-out fell while unchanged Control held-out rose;
- improvement from tool, middleware, skill, validator, memory, or routing changes, because admitted edits were prompt-only;
- cost efficiency, because token totals and monetary billing were not recorded.

The comparison artifact's `causal_comparison: true` means that the intended treatment identity was isolated by the preregistered protocol. It must not be interpreted as a statistical significance flag.

## Accepted Follow-up

1. Repeat the same matched Control/Rich protocol for at least three independent preregistered model seeds before any stable gain claim.
2. Add provider/model cost telemetry before another full paid run.
3. Keep the Rich iteration-3 worker as an experimental candidate only.
4. Preserve `qfbench-30x5-20260725` unchanged. Historical rescore is optional and must use a new content-addressed result identity.
5. Keep E2B as the official runtime reference while Daytona VM and Vercel undergo the separately recorded parity/cost canaries.

Full analysis: [2026-07-27 experiment report](../reports/2026-07-27-qfbench-full-harness-feedback-ab-report.md). Machine-readable comparison: [`comparison.json`](../../results/qfbench_feedback_ab/20260727-024921eb/comparison.json).
