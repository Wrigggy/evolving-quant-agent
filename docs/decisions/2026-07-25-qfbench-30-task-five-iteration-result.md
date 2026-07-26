# Decision Record: QFBench 30-Task, Five-Iteration Result

> Date: 2026-07-25
> Status: accepted as an end-to-end engineering result; benchmark scores are provisional
> Supersedes: the proposed 30-task next experiment in the 2026-07-24 live-pilot decision

## Decision

Keep the preregistered `data/qfbench/MANIFEST_30.json`, 20-optimize/10-held-out split, domain-macro reward, no-domain-regression firewall, and `0.02` noise floor. Run `qfbench-30x5-20260725` establishes that the 30-task E2B path, five-iteration scheduler, exact-ID recovery, and both keep/rollback gates execute at scale. It does **not** establish an evolution gain: all five candidates were rolled back and the final worker remained the seed.

Treat the reported scores as provisional. Three verifier templates failed to warm dependencies because their official scripts use `if uvx ...`, while template parsing recognized only a bare `uvx ...` command. This produced 14 offline cache failures across `delta-hedging-pnl-simulation`, `swap-curve-bootstrap-ois`, and `form4-cross-sectional-sale-pressure`. Do not reuse those three published verifier template IDs. The local parser now recognizes the official wrapper, rejects unknown `uvx` wrappers, and fails closed on the observed offline dependency-resolution error; no additional paid template build or score repair was authorized.

## Measured Run

- Benchmark commit: `024921eb507fcc0c4ffe3e0a96802724be1ae84a`.
- Model: `deepseek/deepseek-v4-pro`; concurrency 8; global E2B cap 12.
- Templates: shared base plus 60 task-role templates; 10 reused and 50 published on 2026-07-25.
- Schedule: 20 optimize seed + 10 held-out seed + `5 × 20` candidates + 10 held-out final = 140 official score records.
- Lifecycles: 140 worker and 136 verifier sandboxes. Four worker timeouts skipped verifier creation. All 276 lifecycle records are cleaned; final exact-ID reaper dry-run reports zero pending IDs.
- Attempt-artifact span: approximately 5 h 17 min. Provider token totals, model cost, and E2B billing totals were not emitted and remain unmeasured.

## Results

| Iteration | Candidate domain macro | Decision | Reason |
| ---: | ---: | --- | --- |
| 1 | 0.490278 | rollback | `risk_credit` regression |
| 2 | 0.418452 | rollback | `systematic_strategy` regression |
| 3 | 0.465278 | rollback | `systematic_strategy` regression |
| 4 | 0.529167 | rollback | overall improved, but `systematic_strategy` fell 0.25 |
| 5 | 0.513194 | rollback | gain 0.013194 did not exceed 0.02 noise floor |

The observed incumbent optimize score stayed at 0.500000. Held-out domain macro moved from 0.666667 to 0.583333; task mean moved from 0.7 to 0.6. These values include the verifier-cache contamination and must not be promoted as authoritative performance estimates.

## Comparison and Consequences

The earlier three-task pilot used 3 optimize tasks, 2 held-out tasks, 3 iterations, and 16 attempts. The new panel uses 20/10 tasks, 5 iterations, and 140 attempts; one binary held-out task changes task mean by 0.1 instead of 0.5. The overall scores across runs are contextual because the panels differ. On shared optimize tasks, historical VaR and momentum remain 1.0 while EVT-POT VaR is 1.0 in the old pilot and 0.833333 in the new seed.

Before another formal score claim:

1. Publish corrected verifier templates for the three affected tasks and perform a separately authorized repair run.
2. Treat missing CTRF caused by offline dependency resolution as infrastructure failure, not an ordinary official zero.
3. Repeat a fixed subset across independent model seeds; more tasks reduce task-panel sensitivity but do not estimate stochastic model variance.
4. Persist provider tokens/cost and E2B billing metadata in the run artifact.

Primary evidence: `results/qfbench/qfbench-30x5-20260725/`, its `validity-audit.json`, `comparison-to-pilot-3.{json,md}`, and the experiment report dated 2026-07-25.
