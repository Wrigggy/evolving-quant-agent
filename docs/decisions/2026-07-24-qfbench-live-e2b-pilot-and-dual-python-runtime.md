# Decision Record: QFBench Live E2B Pilot and Dual-Python Runtime

> Date: 2026-07-24
> Status: accepted and measured for the five-task pilot
> Supersedes: the cloud-validation-pending evidence boundary in the earlier 2026-07-24 template hardening decision; it does not change the pinned benchmark, split, or official rewards

## Decision

Retain the local coordinator, complete in-E2B NexAU worker, separate no-network verifier, content-addressed attempts, and seed/final-only held-out policy. Published worker templates use two Python runtimes: QFBench stays on the official Python 3.11 base, while NexAU 0.3.9 runs under isolated Python 3.12 at `/opt/qea/nexau-venv`. NexAU is pinned to commit `35ee1861546db3cb280a6e17e38a74060d7c96c3` because 0.3.9 is not published on PyPI and its current package metadata conflicts with Python 3.11.

Worker egress is deny-by-default and permits only the configured model-provider host with the authorization header injected by E2B. Python 3.12 explicitly trusts `/etc/ssl/certs/ca-certificates.crt`; TLS verification remains enabled. Verifier networking remains disabled. Official tests are introduced only into verifier sandboxes, and the official solution was introduced only for the isolated oracle-parity run.

The E2B SDK raises on nonzero commands, so the executor normalizes its exact `CommandExitException` into an exit-code result. Worker and oracle commands still fail closed; verifiers may parse official partial rewards after exit 1. Sandbox file uploads retry once only for HTTP/2 `LocalProtocolError` in `ConnectionState.CLOSED`, an idempotent transport failure observed during resume.

## Published Runtime Identities

The shared base is template `h4d9iarzjjts2z472o8d`, build `b82873ce-db6e-4269-a689-ecb9354bf207`, identity `4f07291f4e37…`. The ten role templates are recorded under `output/qfbench-e2b-images/20260724T095950+0800_024921eb/`:

| Task | Worker template | Verifier template | CPU / memory |
|---|---|---|---:|
| `historical-var-data-prep` | `ovqxcb0b6uks2ic8po5d` | `plac6ysit48lsgulqxx3` | 4 / 8192 MB |
| `momentum-backtest` | `5y6vl0gmj414r8s76s62` | `02z3hu66vo4atiwmaatz` | 2 / 4096 MB |
| `evt-pot-var` | `nvd43rhfo3rtcdrylgvk` | `5h8jad7hhkidabbjhxfm` | 2 / 4096 MB |
| `fx-forward-cross-rate` | `wkksb453senqy1vbu96s` | `p70o1x4mgnlq54mw5dla` | 4 / 8192 MB |
| `option-put-call-parity-forward-audit` | `4lud3y4c3mfjhiuoulps` | `fgxtuxvhn5w3bnrxjyar` | 2 / 4096 MB |

Every one of the 16 pilot attempts copied the same NexAU lock hash, `2a1a6d213cf8295c89967a8b0dc04b0fa33c0fde6cd1831a9869316adc69a018`. Role-specific verifier locks are also present in every attempt.

## Measured Parity and Recovery

Oracle run `qfbench-oracle-20260724T1025` passed `historical-var-data-prep` at reward 1.0 with 12/12 tests and exact canonical parity for `results.json` and `solution.json`.

Pilot `qfbench-pilot-3-20260724T102755` included a real coordinator `SIGKILL` (exit 137). The exact orphan `i9aja3c47fejiokwvi4pt` was found in dry-run, killed by the exact-ID reaper, and the unfinished `evt-pot-var` task resumed in `iw4jnf0w9sfinglqome6z`. Completed historical-VaR and momentum attempts retained identical execution and score hashes and were not rerun. Final dry-runs found no pending pilot or oracle sandboxes.

## Three-Iteration Result

The model was `deepseek/deepseek-v4-pro` through the configured OpenRouter account. The preregistered schedule completed exactly 16 official attempts.

| Checkpoint | Historical VaR | Momentum | EVT-POT VaR | Optimize domain macro |
|---|---:|---:|---:|---:|
| Seed | 1.0 | 1.0 | 1.0 | 1.0000 |
| Candidate 1 | 1.0 | 1.0 | 0.833333 | 0.95833325 |
| Candidate 2 | 1.0 | 1.0 | 0.833333 | 0.95833325 |
| Candidate 3 | 1.0 | 1.0 | 0.833333 | 0.95833325 |

All three candidates regressed in the risk domain by `0.0833335` and were rolled back. The incumbent remained the seed worker.

Held-out rewards were `1.0/1.0` at seed and `1.0/0.0` at final for FX/option audit, so the two-task held-out macro moved from 1.0 to 0.5. This is observed model-sampling variation, not an evolved-worker regression: both checkpoints used the identical worker digest in independent model runs. The option run produced identical `results.json`, `parity_audit.csv`, and `violations.csv`; only four nested `solution.json` key names differed, causing one of five binary checks to fail. Therefore this pilot establishes end-to-end execution and rollback behavior, not an evolution gain.

## Next Experiment

Do not run the five-iteration pilot from this evidence: the optimize set begins at a ceiling and the two held-out tasks have excessive binary variance. The preferred next paid experiment is a preregistered, lineage-stratified 30-task screen followed by a fixed 20-optimize/10-held-out, three-iteration pilot. That schedule is 100 official attempts (`20 × 4 + 10 × 2`) and requires 60 task-role templates in total, minus any reusable templates from this pilot. Include multiple domains, difficulties, and both partial/binary rewards; continue excluding copy-oracle and inoperable tasks. Repeated model seeds on a fixed subset are still needed to estimate stochastic variance. This expansion requires separate task-list, cost, and paid-run authorization.

## Evidence and Limits

Primary artifacts are `results/qfbench/qfbench-pilot-3-20260724T102755/`, `results/qfbench-oracle/qfbench-oracle-20260724T1025/parity.json`, and the published image manifests. Local verification passes `132 passed, 1 skipped`; all seven QFBench/E2B scripts compile. Raw model token/cost totals and E2B billing were not emitted by the provider/SDK into run artifacts, so no cost claim is made. A five-iteration run was not executed.
