# QFBench 30-Task Five-Iteration Experiment Design

> Date: 2026-07-25
> Status: approved for implementation and one paid run
> Benchmark commit: `024921eb507fcc0c4ffe3e0a96802724be1ae84a`

## Objective

Measure one five-iteration QEA evolution run on a larger, lineage-separated QFBench sample and compare it with the measured five-task, three-iteration pilot. The experiment must reduce cross-task sampling sensitivity without exposing held-out feedback, tests, solutions, or credentials to the proposer or worker.

## Alternatives and Decision

Use 20 optimize tasks and 10 promotion-held-out tasks. This produces 140 official attempts: 20 optimize seed, 10 held-out seed, five sets of 20 optimize candidates, and 10 held-out final. A 15/15 split would strengthen held-out estimation but narrow mutation feedback; a 24/6 split would cost more while retaining an undersized held-out set. The 20/10 split is the preregistered compromise.

Use the same `deepseek/deepseek-v4-pro` model and existing seed worker as the prior pilot. Keep `noise_floor=0.02`, `max_domain_regression=0.0`, coordinator concurrency 8, and global E2B lease cap 12. A completed content-addressed attempt is immutable and reusable on resume; it must not be resampled.

## Preregistered Task Split

The six domain labels are `risk_credit`, `systematic_strategy`, `derivatives`, `rates_fx_macro`, `execution_microstructure`, and `data_engineering`. Every task has a unique workflow lineage string. Optimize and held-out lineages must be disjoint, and exact input-file hash overlap across the split is forbidden.

### Optimize: 20 tasks

| Task | Domain | Lineage | Difficulty | Reward |
|---|---|---|---|---|
| `historical-var-data-prep` | risk_credit | historical_var_data_pipeline | easy | binary |
| `evt-pot-var` | risk_credit | evt_tail_risk | medium | partial |
| `credit-migration-matrix` | risk_credit | credit_transition_markov | medium | binary |
| `credit-spread-decomposition` | risk_credit | macro_credit_spread_decomposition | medium | binary |
| `momentum-backtest` | systematic_strategy | ema_momentum_backtest | easy | binary |
| `bollinger-backtest-aapl` | systematic_strategy | bollinger_mean_reversion_backtest | medium | binary |
| `brinson-sector-attribution` | systematic_strategy | brinson_sector_attribution | medium | binary |
| `etf-cross-asset-lead-lag` | systematic_strategy | etf_lead_lag_regression | medium | binary |
| `cme-hdd-option-pricing` | derivatives | weather_option_hdd_pricing | medium | binary |
| `delta-hedging-pnl-simulation` | derivatives | discrete_delta_hedging_simulation | medium | binary |
| `localvol-barrier` | derivatives | localvol_barrier_pricing | hard | partial |
| `fomc-tone-event-study` | rates_fx_macro | fomc_tone_treasury_event_study | medium | binary |
| `swap-curve-bootstrap-ois` | rates_fx_macro | ois_libor_dual_curve_bootstrap | medium | binary |
| `yield-curve-bond-immunization` | rates_fx_macro | key_rate_duration_immunization | hard | partial |
| `zero-coupon-bootstrapping` | rates_fx_macro | par_to_zero_curve_bootstrap | hard | binary |
| `crypto-funding-rate-basis-carry` | execution_microstructure | crypto_funding_basis_carry | medium | binary |
| `prediction-markets-cross-venue-dislocation` | execution_microstructure | prediction_market_cross_venue_execution | hard | partial |
| `13f-amendment-aware-crowding` | data_engineering | amendment_aware_13f_crowding | medium | binary |
| `corporate-action-adjustment` | data_engineering | corporate_action_price_adjustment | medium | binary |
| `earnings-surprise-calculator` | data_engineering | earnings_surprise_sue_pipeline | medium | binary |

### Promotion held-out: 10 tasks

| Task | Domain | Lineage | Difficulty | Reward |
|---|---|---|---|---|
| `dcc-garch-portfolio-var` | risk_credit | dcc_garch_portfolio_var | hard | binary |
| `fft-compound-poisson` | risk_credit | fft_compound_poisson_loss | hard | binary |
| `pca-factor-portfolio` | systematic_strategy | pca_factor_neutral_portfolio | hard | binary |
| `bl-regime-hmm` | systematic_strategy | hmm_black_litterman_allocation | hard | binary |
| `option-put-call-parity-forward-audit` | derivatives | option_parity_forward_audit | hard | binary |
| `interest-rate-cap-floor` | derivatives | black_cap_floor_aggregation | hard | binary |
| `fx-forward-cross-rate` | rates_fx_macro | fx_forward_cross_rate | easy | binary |
| `cir-bond-pricing` | rates_fx_macro | cir_term_structure_pricing | hard | binary |
| `intraday-volume-fitting-and-execution-scheduling` | execution_microstructure | intraday_volume_execution_schedule | hard | binary |
| `form4-cross-sectional-sale-pressure` | data_engineering | form4_sale_pressure_reconstruction | hard | binary |

The split includes the previous five tasks for direct per-task comparison. It excludes the eight registered copy-oracle tasks, inoperable `sec-8k-event-alpha`, tasks without authoritative CPU/memory/timeout fields, the repeated 35.6 MiB factor panels, and the long multimodal task.

## Pinned Snapshot Materialization

Create a new dedicated cache at `/private/tmp/qea-qfbench-30-024921eb`; do not mutate the five-task evidence snapshot. Materialize only `docker/` and the 30 registered task directories. Git partial-clone object fetches are not a run-time dependency because that path repeatedly returned empty responses during source audit.

The materializer must fetch exact files from the pinned commit, then compare every file's Git blob SHA-1 with the object ID from the pinned commit tree. It writes `.qfbench-revision` and `.qfbench-sparse-tasks.json` only after all files verify. The loader must then prove:

- exactly 20 optimize and 10 held-out tasks;
- all required task paths exist;
- all resource fields are explicit positive values;
- selected tasks exclude copy-oracle and inoperable IDs;
- lineages and exact input hashes do not cross splits;
- Dockerfiles use the supported single-stage `FROM`, `WORKDIR`, `COPY`, and `RUN` surface.

No unverified or partially downloaded snapshot may enter a template build.

## E2B Templates and Isolation

Reuse shared base template `h4d9iarzjjts2z472o8d` and build `b82873ce-db6e-4269-a689-ecb9354bf207`. Seed the new template-manifest directory with the ten already-published role manifests for the previous five tasks. Generate 60 worker/verifier role manifests total and publish at most 50 missing identities. Publication remains sequential and resumable: each successful build ID is recorded immediately, and a rerun reuses it.

Workers receive only public `instruction.md` plus files copied by the public environment Dockerfile. They run NexAU 0.3.9 at commit `35ee1861546db3cb280a6e17e38a74060d7c96c3` under isolated Python 3.12 while the task stays on Python 3.11. Worker network remains deny-by-default with only the configured model-provider host allowed and authorization injected by E2B.

Official tests and test reference data enter only independent no-network verifier templates. Official solutions are not uploaded or executed in this experiment. Verifier rewards remain byte-for-byte official; partial rewards may be parsed after an official exit 1. Every worker and verifier sandbox writes an exact lifecycle manifest and cleanup record.

## Five-Iteration Execution

Use run ID prefix `qfbench-30x5-20260725` with a collision-free timestamp suffix. The coordinator evaluates seed optimize, seed held-out, five candidate checkpoints, and final held-out in that order. Held-out summaries are checkpointed but never included in mutation diagnosis or keep/rollback decisions.

Candidate acceptance requires an optimize domain-macro gain greater than 0.02 and no negative domain delta. The proposer sees only optimize official reward, task ID, and answer-free diagnostic tags. It never sees held-out rewards, trusted logs, assertions, expected values, tests, reference data, or solutions.

If the coordinator stops, first run the exact-ID reaper in dry-run mode, review and kill only pending IDs, then resume the identical command. Completed proposals, worker executions, and official scores are reused. Do not change task list, manifest, model, thresholds, concurrency, or template identities during resume.

## Comparison and Reporting

Compare against `qfbench-pilot-3-20260724T102755` using:

- raw reward for every shared task and every new task;
- seed optimize task mean and six-domain macro;
- five candidate domain deltas and keep/rollback decisions;
- held-out seed/final paired change, task mean, and domain macro;
- binary versus partial-reward distributions;
- score sensitivity to a single binary failure;
- worker/verifier wall time, failures, retries, resumes, and cleanup;
- model token/cost and E2B billing when durably exposed, otherwise explicitly unavailable.

The report must distinguish engineering success, measured benchmark improvement, model-sampling variation, and external-transfer evidence. A completed run with no kept candidate is a valid result, not a reason to alter official rewards or reveal held-out feedback.

## Acceptance Criteria

The experiment is complete only when:

1. The pinned 30-task snapshot passes file-hash, split, resource, Dockerfile, and firewall validation.
2. All 60 task-role manifests have immutable published template/build IDs and non-empty dependency locks.
3. Exactly 140 unique content-addressed official scores exist for the preregistered schedule.
4. `result.json` and `resume.json` both report phase `complete`, five iteration records, and the same final incumbent.
5. Exactly 140 worker and 140 verifier cleanup records report `cleaned_up=true`; final pilot and oracle reaper scans have no pending IDs.
6. The full local test suite and script compilation pass after implementation.
7. A new dated decision/report and `docs/PROJECT_MEMORY.md` record the measured result and comparison without rewriting prior reports.
