# QFBench Train/Validation/Test V4 Flash Evolution Design

**Date:** 2026-08-05  
**Status:** Approved for autonomous implementation and paid execution  
**Branch:** `qfbench-selfhosted-vm-backend`  
**Runtime:** trusted `bc-server` coordinator with rootless Docker worker and verifier sandboxes

## Objective

Measure whether ten iterations of full-harness evolution improve QFBench task performance without using final-test evidence for selection. The experiment uses an explicit train/validation/test protocol:

- **Train (30 tasks):** public instruction, public rubric, worker-observable trajectory, produced artifacts, and sanitized criterion evidence may reach the evolver. Train scores drive improvement.
- **Validation/confirm (15 tasks):** scored at seed and every iteration. Task identities, scores, domain deltas, artifacts, and verifier evidence are hidden from the evolver. Validation only confirms that a train-improving candidate has not regressed beyond baseline sampling noise.
- **Test (40 tasks):** scored only at seed and final and never affects keep/rollback. The 32 non-copy-oracle tasks are the authoritative outcome; eight copy-oracle tasks are reported separately as diagnostics.

Official tests and reference data remain inside independent, no-network verifier containers. Official solutions are not uploaded or run. Credentials and `.env` never enter proposer, worker-visible bundles, verifier reports, or ordinary result mirrors.

## Fixed Task Split

The task manifest is pinned before the first evolver proposal. Tasks are stratified across the six QFBench domains and must be pairwise disjoint.

### Train: 30 tasks

`historical-var-data-prep`, `evt-pot-var`, `credit-migration-matrix`, `credit-spread-decomposition`, `momentum-backtest`, `bollinger-backtest-aapl`, `brinson-sector-attribution`, `etf-cross-asset-lead-lag`, `cme-hdd-option-pricing`, `delta-hedging-pnl-simulation`, `localvol-barrier`, `fomc-tone-event-study`, `swap-curve-bootstrap-ois`, `yield-curve-bond-immunization`, `zero-coupon-bootstrapping`, `crypto-funding-rate-basis-carry`, `prediction-markets-cross-venue-dislocation`, `13f-amendment-aware-crowding`, `corporate-action-adjustment`, `earnings-surprise-calculator`, `bs-greeks-pde`, `cliquet-ratchet-pricing`, `merton-jump-diffusion`, `spread-option-kirk-margrabe`, `variance-swap-replication`, `realized-vol-estimators`, `var-es-estimation`, `sma-crossover-spy`, `residual-momentum`, `binance-btc-participation-tca`.

Domain counts: data 3, derivatives 8, execution 3, rates 4, risk 6, systematic 6.

### Validation/confirm: 15 tasks

`dcc-garch-portfolio-var`, `fft-compound-poisson`, `pca-factor-portfolio`, `bl-regime-hmm`, `option-put-call-parity-forward-audit`, `interest-rate-cap-floor`, `fx-forward-cross-rate`, `cir-bond-pricing`, `intraday-volume-fitting-and-execution-scheduling`, `form4-cross-sectional-sale-pressure`, `implied-vol-approximations`, `ou-jump-commodity`, `standard-var-methods`, `double-sort`, `fx-carry-forward-hedge`.

Domain counts: data 1, derivatives 4, execution 1, rates 3, risk 3, systematic 3.

### Authoritative test: 32 tasks

`alpha-hedge-strategy`, `american-option-fd-new`, `asian-option-levy-curran`, `barone-adesi-whaley`, `compound-option-geske`, `copula-equity-fitting`, `copula-sampling-rank-correlation`, `credit-portfolio-var-cvar`, `creditmetrics-portfolio-var`, `cross-sectional-momentum`, `digital-barrier-options`, `dupire-local-vol`, `etf-overlap-redemption-pressure`, `event-study-earnings`, `ewma-portfolio-risk-decomposition`, `fama-french-factor-model-new`, `first-passage-time`, `geometric-mean-reverting-jd`, `hull-white-swaption`, `ipca-latent-factors`, `lob-pc-signal`, `lookback-options`, `mc-greek-surface-1`, `mtm-xccy-basis-desk`, `multimodal-alpha-fusion-edgar-cot-gdelt`, `ohlc-realized-vol-estimators`, `polars-api-migration`, `smith-tail-index`, `stable-residual`, `stochvol-implied-surface-new`, `yield-curve-bootstrap-immunization`, `yield-curve-pca-dynamics`.

Domain counts: data 1, derivatives 11, execution 1, rates 4, risk 7, systematic 8.

### Diagnostic test: 8 copy-oracle tasks

`barrier-garch-var`, `cta-basel-capital`, `kelly-var-sizing`, `regime-cta-vol-target`, `regime-riskparity-cvar`, `sec-10k-report-long`, `sentiment-factor-alpha`, `structured-note-risk`.

These tasks may be executed in the same seed/final test phase for operational efficiency, but their aggregate and deltas must never be combined with the 32-task primary metric. `sec-8k-event-alpha` remains excluded as inoperable.

## Scoring Schedule and Budget

The fixed schedule is:

| Phase | Train | Validation | Test | Attempts |
|---|---:|---:|---:|---:|
| Seed | 30 | 15 | 40 | 85 |
| Iterations 1-10 | 300 | 150 | 0 | 450 |
| Final | 0 | 0 | 40 | 40 |
| **Total** | **330** | **165** | **80** | **575** |

Each scoring attempt has an isolated worker container and a separate isolated verifier container. There are ten evolver model calls plus worker model calls. The model identity is fixed to OpenRouter model `deepseek/deepseek-v4-flash-0731`, pinned to the official DeepSeek provider with fallback disabled.

## Candidate Selection Contract

The incumbent stores train and validation summaries. Every iteration proposes exactly one candidate full harness and evaluates all 30 train tasks and all 15 validation tasks, including no-op or repeated edits.

A candidate is kept only when both gates pass:

1. **Train gate:** the existing QFBench domain-macro improvement rule passes: positive gain beyond the configured train noise floor and no train-domain regression beyond the configured limit.
2. **Blind validation gate:** candidate validation domain-macro score is at least `incumbent_validation_score - validation_noise_tolerance`.

Before evolution begins, calculate the tolerance from the completed five-repetition base-worker baseline:

```text
V_r = domain-macro score on the fixed 15 validation tasks in repetition r
validation_noise_tolerance = max(0.02, max_r(abs(V_r - mean(V))))
```

The baseline run ID, five repetition summaries, formula version, and resulting scalar are bound into the immutable experiment manifest. A retained candidate updates both incumbent summaries. A rejected candidate updates neither.

The evolver may observe the ultimate keep/rollback event because it determines the next harness, but it receives no validation identity, score, delta, failure domain, task artifact, criterion evidence, or validation-specific rejection reason. Exposed history uses the generic reason `confirm_failed` when the blind gate is decisive.

## Full-Harness Evolution and Feedback

The mutable object is the full NexAU/GDPval-style worker harness, not a prompt-only proxy. Existing mutation admission rules continue to reject changes outside the authorized harness surface, symlink/path escapes, credentials, verifier material, official tests, reference data, and all validation/test task identities or artifacts.

Rich train feedback follows the answer-free contract: public task goals and rubrics, worker-visible trajectories, generated artifacts, and sanitized criterion-level evidence are permitted. Gold answers, official tests, test reference data, official solutions, raw rubric verdicts, secrets, and any validation/test evidence are forbidden.

## Concurrency and Automatic Downshift

Run a paid preflight/canary ladder in order: `20 workers / 3 verifiers`, then `16/3`, then `12/3`. Accept the highest tier that satisfies all of the following under the formal image, model route, resource weights, and verifier isolation:

- no resource-lease timeout, provider replay, 429 loop, or coordinator crash;
- verifier network isolation and worker/verifier separation remain intact;
- no residual containers or networks after exact-ID cleanup;
- at least 16 GiB host memory remains available and the host does not sustain unsafe load or memory pressure;
- observed worker overlap reaches the tier rather than merely configuring it.

Healthy resource contention must queue instead of failing after the old 120-second lease timeout. The accepted tier is recorded and frozen for the formal run. If a later infrastructure failure requires a lower tier, restart only from an exact committed iteration boundary under a new scheduler epoch; record the identity change and never reinterpret mixed scheduler epochs as one uninterrupted run.

## Launch Gate, Recovery, and Evidence Preservation

Evolution starts only after the current `qfbench-rootless-base-85x5-official-deepseek-v4-flash-0731-all12x3-20260804` baseline satisfies all completion gates:

- 425/425 official scores and all five repetitions complete;
- provider/model audit passes with no fallback or replay;
- exact-ID dry reaper and residual container/network audit are clean;
- cost/usage audit is persisted even though cost is not an acceptance metric;
- the exact run is mirrored additively to the Mac with 425 durable score artifacts.

The evolution must launch together with the existing coordinator supervisor, formal sentinel/watch units, bounded recovery policy, Mac caffeinate repair controller, and additive exact-ID local mirror. Resume state binds source commit, manifest hashes, split identities, model/provider, feedback contract, tolerance provenance, scheduler tier/epoch, images, and immutable run ID. Recovery may resume only the exact run and may never silently rescore a completed attempt.

## Outcome Interpretation

The primary effectiveness result is the seed-to-final change on the 32-task authoritative test domain macro, with task and domain deltas. The eight copy-oracle diagnostics are shown in a separate table. Train and validation trajectories explain selection behavior but do not replace the final-test result.

The completed five-repeat base-worker baseline supplies a sampling reference, not extra evolution observations. With one seed and one final evolved-harness test pass, conclusions are directional unless the effect is clearly larger than observed baseline variability. Report all failures, timeouts, retained/rolled-back iterations, scheduler epochs, and missing attempts; do not silently exclude them.

## Required Verification

Before the paid launch, automated tests must prove:

- split disjointness, exact counts, domain counts, copy-oracle separation, and 575-attempt accounting;
- validation runs at seed and every iteration while test runs only at seed/final;
- validation/test evidence and identities cannot reach proposer inputs or mutation admission;
- train plus blind-confirm keep/rollback semantics and tolerance calibration/resume binding;
- fixed V4 Flash official-provider routing with fallback disabled;
- queued resource acquisition, concurrency-tier canaries, exact-ID cleanup, watchdogs, and additive local mirroring.

