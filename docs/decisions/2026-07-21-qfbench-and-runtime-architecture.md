# Decision Record: QFBench Benchmark and Remote Execution Architecture

> Date: 2026-07-21
> Status: accepted for staged pilot; implementation and paid cloud runs not yet performed
> Scope: QFBench task design, evolution reward, evaluator integrity, NexAU/QEA placement, E2B, and AutoDL no-GPU feasibility

## Decision Summary

QFBench is selected as the leading **high-frequency quant optimization benchmark**, but not as the sole proof of finance-agent quality. Use its deterministic task environments behind an evaluator firewall, then confirm transfer on FINCH/BankerToolBench and frozen GDPval/PRBench tasks.

For execution, move the **entire per-task NexAU worker process**—not only its shell commands—into E2B task sandboxes. Keep QEA’s lightweight coordinator local or on a persistent CPU host during the first stage. Moving the coordinator to E2B is feasible only after Level-B checkpoint/resume and secret isolation are hardened. AutoDL public no-GPU mode is rejected as a high-parallel or QFBench runtime because it supplies only 0.5 CPU/2 GB RAM, permits one instance per account, cannot run Docker inside the container, and cannot currently be booted in no-GPU mode through its API.

These are architecture decisions, not measured cloud-performance claims.

## Evidence Scope and Precedence

The QFBench audit is pinned to commit:

```text
024921eb507fcc0c4ffe3e0a96802724be1ae84a
```

The audit covered all task instructions, `task.toml` files, input assets, Dockerfiles, solution scripts, test launchers, and pytest verifiers. Source-backed cloud conclusions use:

- [AHE official repository](https://github.com/china-qijizhifeng/agentic-harness-engineering)
- [Harbor core concepts](https://www.harborframework.com/docs/core-concepts)
- [Harbor cloud sandboxes](https://www.harborframework.com/docs/run-jobs/cloud-sandboxes)
- [Harbor task lifecycle](https://www.harborframework.com/docs/tasks)
- [E2B lifecycle and persistence](https://e2b.dev/docs/sandbox/persistence)
- [E2B billing and limits](https://e2b.dev/docs/billing)
- [E2B pricing](https://e2b.dev/pricing)
- [AutoDL no-GPU mode](https://www.autodl.com/docs/save_money/)
- [AutoDL container environment](https://www.autodl.com/docs/env/)
- [AutoDL container instance API](https://www.autodl.com/docs/instance_pro_api/)

The earlier [benchmark authority report](../reports/2026-07-21-qea-benchmark-authority-screen-report.md) remains the authority/provenance record. This decision record supersedes its provisional QFBench task-count and reward-shape description.

## QFBench Task Contract

QFBench tasks are file-producing quant coding projects rather than short-form questions. A typical task supplies an instruction, a Docker environment and frozen input files, a reference solution, and pytest-based verification. The agent explores `/app`, writes and executes code, and produces required JSON/CSV/HTML/PNG/source artifacts.

The verifier may check:

- artifact existence and schema;
- numerical values within tolerances;
- financial identities, parity, risk decomposition, or monotonicity;
- execution timing and transaction-cost conventions;
- deterministic checkpoints or reference outputs;
- source/implementation traces in a small subset.

Snapshot statistics:

| Dimension | Audited result |
|---|---:|
| Tasks | 86 |
| Difficulty | 47 hard, 29 medium, 5 easy, 1 very hard, 1 medium-hard, 3 missing |
| Input files | 228; 168,210,760 bytes (about 160.4 MiB) |
| Inputs by type | 125 CSV, 69 JSON, 9 Python, 4 TSV, 4 XML, 4 HTML, 3 XLSX, 3 Pqt, 3 ZIP, 3 Markdown, 1 JSONL |
| Tasks with no input data | 8 |
| Required output files | About 353; median 4 per task |
| Common outputs | 83 tasks require JSON, 59 CSV, 5 PNG, 3 HTML, 1 Python source; categories overlap |
| Verifier scale | About 2,240 `test_*` functions and 3,301 assertions |
| Reward | 72 strict `0/1`; 14 partial credit |
| Resources | 67 at 2 CPU/4 GB; 8 at 4 CPU/8 GB; 11 unspecified |
| Agent timeout | Median 1,800 seconds; range 1,200–5,400 seconds where declared |

The instructions are unusually long: the median is about 152.5 lines/753 words, and several exceed 400 lines. The benchmark therefore measures long-specification compliance as well as finance and coding ability.

## Complete Task Inventory

Legend: `E/M/H/VH/MH/?` means easy/medium/hard/very-hard/medium-hard/unlabelled. `P` means partial-credit reward. `O` means the shipped oracle solution copies preset expected/reference artifacts and must not be used as authoritative held-out evidence until independently recomputed.

### Derivatives, Stochastic Processes, and Hedging (25)

- `american-option-fd-new` `[H]`: Crank–Nicolson/PSOR American options with discrete dividends, Greeks, and exercise boundary.
- `asian-option-levy-curran` `[H]`: SPY-calibrated GBM; Monte Carlo versus Levy and Curran arithmetic Asian prices.
- `barone-adesi-whaley` `[?]`: BAW American approximation compared with Black–Scholes and CRR.
- `barrier-garch-var` `[H][P][O]`: GARCH volatility, barrier pricing/Greeks, and portfolio VaR decomposition.
- `bs-greeks-pde` `[M]`: Black–Scholes Greek surfaces and PDE residual checks.
- `cliquet-ratchet-pricing` `[H]`: cliquet, ratchet, and forward-start option valuation.
- `cme-hdd-option-pricing` `[M]`: HDD weather option historical burn, OU Monte Carlo, and bump Greeks.
- `compound-option-geske` `[H]`: Geske compound and chooser options with parity and Monte Carlo checks.
- `delta-hedging-pnl-simulation` `[M]`: discrete hedging with fees, dividends, and time-varying implied volatility.
- `digital-barrier-options` `[MH]`: digital, gap, and barrier-digital options with parity tests.
- `dupire-local-vol` `[?]`: SPY option SVI smoothing, Dupire local volatility, and forward variance.
- `first-passage-time` `[?]`: GBM extrema and first-hitting-time analytic distributions versus Monte Carlo.
- `hull-white-swaption` `[VH]`: Hull–White calibration and European/Bermudan swaption valuation.
- `implied-vol-approximations` `[H]`: five implied-volatility approximation/inversion methods against a numerical benchmark.
- `interest-rate-cap-floor` `[H]`: Black caplet/floorlet aggregation for caps and floors.
- `localvol-barrier` `[H][P]`: frozen Deribit BTC option cleaning, local-vol surface, and barrier pricing.
- `lookback-options` `[H]`: fixed/floating lookback closed forms and Monte Carlo validation.
- `mc-greek-surface-1` `[H]`: pathwise, likelihood-ratio, and finite-difference Greek surfaces.
- `merton-jump-diffusion` `[H]`: SPY Merton calibration, prices, and implied-volatility smile.
- `option-put-call-parity-forward-audit` `[H]`: dirty-chain cleaning, synthetic forwards, and parity violations.
- `ou-jump-commodity` `[H]`: OU jump calibration, stationary distribution, and Monte Carlo.
- `spread-option-kirk-margrabe` `[H]`: Kirk spread and Margrabe exchange options using AAPL/MSFT data.
- `stochvol-implied-surface-new` `[H]`: two-factor stochastic-volatility pricing and implied/local-vol surfaces.
- `structured-note-risk` `[H][P][O]`: structured-note decomposition, valuation, VaR, and ES.
- `variance-swap-replication` `[M]`: dirty-chain cleaning and model-free variance-swap replication.

Strength: broad numerical-finance coverage and strong economic invariants. Weakness: many textbook/recipe tasks, high difficulty, tolerance sensitivity, and sparse binary reward.

### Risk, Volatility, and Credit (17)

- `copula-equity-fitting` `[H]`: Gaussian/t/Clayton/Gumbel equity copulas, AIC/BIC, and tail dependence.
- `copula-sampling-rank-correlation` `[M]`: five copula samplers with rank and tail-dependence checks.
- `credit-migration-matrix` `[M]`: multi-year PDs, Markov tests, and generator matrices.
- `credit-portfolio-var-cvar` `[H]`: 990-name copula credit VaR/CVaR, marginal risk, and concentration.
- `credit-spread-decomposition` `[M]`: FRED rolling OLS, Newey–West inference, and variance attribution.
- `creditmetrics-portfolio-var` `[H]`: rating migration and CreditMetrics VaR under a one-factor copula.
- `cta-basel-capital` `[H][P][O]`: CTA trend strategy, multi-step GARCH VaR, and Basel capital.
- `dcc-garch-portfolio-var` `[H]`: five-asset DCC-GARCH, dynamic VaR/ES, and coverage backtests.
- `evt-pot-var` `[M][P]`: POT/GPD and GARCH-EVT VaR/ES with coverage and independence tests.
- `ewma-portfolio-risk-decomposition` `[M]`: repair a faulty EWMA template and compute Euler risk contributions.
- `fft-compound-poisson` `[H]`: FFT compound-Poisson aggregation versus Monte Carlo.
- `historical-var-data-prep` `[E]`: dirty ETF/calendar cleaning and 95%/99% historical VaR.
- `ohlc-realized-vol-estimators` `[M]`: close-to-close, Parkinson, GK, RS, and Yang–Zhang estimators.
- `realized-vol-estimators` `[M]`: multi-frequency realized volatility, bipower variation, and noise correction.
- `smith-tail-index` `[H]`: Hill/Smith-GPD tail-index stability on S&P 500 losses.
- `standard-var-methods` `[H]`: AAPL/JPM one-day and ten-day VaR methods with backtesting.
- `var-es-estimation` `[M]`: historical, parametric, KDE/MLE, and simulation VaR/ES comparisons.

Strength: directly relevant to quant risk and contains useful invariants/partial reward. Weakness: Monte Carlo seeds, library versions, and tolerances can create reproducibility drift; genuine future holdouts are rare.

### Factors, Portfolio Construction, Strategy, and Backtesting (21)

- `alpha-hedge-strategy` `[H]`: cross-sectional signal, frictional long/short backtest, factor hedging, and residual alpha.
- `bl-regime-hmm` `[H]`: HMM regime detection and regime-aware Black–Litterman allocation.
- `bollinger-backtest-aapl` `[M]`: Bollinger mean reversion with fees, sizing, and trailing stops.
- `brinson-sector-attribution` `[M]`: Brinson–Fachler attribution with rebalancing and weight drift.
- `cross-sectional-momentum` `[H]`: ten-stock monthly 12-1 long/short momentum.
- `double-sort` `[H]`: beta-by-momentum dependent double sorts and turnover costs.
- `etf-cross-asset-lead-lag` `[M]`: rolling and residual lead/lag across ten ETFs.
- `etf-overlap-redemption-pressure` `[M]`: SPDR holdings overlap, redemption pressure, and liquidity concentration.
- `event-study-earnings` `[H]`: market-model AR/CAR/CAAR and significance tests.
- `fama-french-factor-model-new` `[E]`: CAPM/FF3, rolling betas, sector summaries, and plots.
- `ipca-latent-factors` `[H]`: characteristic-driven IPCA, ALS, R-squared, and GRS tests.
- `kelly-var-sizing` `[H][P][O]`: multi-asset Kelly, VaR constraint, and drawdown simulation.
- `momentum-backtest` `[E]`: SPY EMA crossover with next-open execution, trades, equity, and HTML.
- `multimodal-alpha-fusion-edgar-cot-gdelt` `[H]`: frozen EDGAR/COT/GDELT/vendor feature fusion and backtest.
- `pca-factor-portfolio` `[H]`: PCA factors and factor-neutral portfolio construction.
- `regime-cta-vol-target` `[H][P][O]`: GARCH regimes and static versus adaptive vol targeting.
- `regime-riskparity-cvar` `[H][P][O]`: RMT/absorption regimes, risk parity, and CVaR.
- `residual-momentum` `[M]`: Fama–MacBeth OOS comparison of residual and raw momentum.
- `sentiment-factor-alpha` `[H][P][O]`: social text, engagement weighting, IC, and OLS alpha.
- `sma-crossover-spy` `[E]`: SPY SMA crossover with trades, equity curve, and HTML.
- `stable-residual` `[M]`: residual alpha, beta neutrality, turnover cap, and transaction costs.

Strength: best match for an agent that must explore data, write/debug code, backtest, and deliver several artifacts. Weakness: public fixed inputs/tests and weak hidden temporal evaluation make benchmark-specific overfitting likely under repeated evolution.

### Fixed Income, Curves, FX, and Macro (11)

- `cir-bond-pricing` `[H]`: CIR calibration and zero/yield/forward curves.
- `fomc-tone-event-study` `[M]`: FOMC tone surprise and Treasury-yield HAC event study.
- `fx-carry-forward-hedge` `[H][P]`: G10 carry, forwards/options/NDFs, conventions, and risk.
- `fx-forward-cross-rate` `[E]`: cross rates, forward portfolio valuation, and sensitivities.
- `geometric-mean-reverting-jd` `[H]`: geometric mean-reverting jump-diffusion calibration and simulation.
- `mtm-xccy-basis-desk` `[H][P]`: USD-collateralized GBP/USD MtM cross-currency basis desk analytics.
- `swap-curve-bootstrap-ois` `[M]`: repair OIS/3M LIBOR dual-curve bootstrap and swap valuation.
- `yield-curve-bond-immunization` `[H][P]`: t0/t1 Treasury curves, KRD/PCA hedges, stresses, and rebalancing.
- `yield-curve-bootstrap-immunization` `[H]`: par bootstrap, bond analytics, Nelson–Siegel, immunization, and stress.
- `yield-curve-pca-dynamics` `[M]`: Treasury level/slope/curvature PCA dynamics.
- `zero-coupon-bootstrapping` `[H]`: discount factors and zero curve from par coupon rates.

Strength: rich desk conventions and multi-step professional reasoning. Weakness: long specifications, many convention branches, difficult error attribution, and some constructed rather than tradeable inputs.

### Execution, Microstructure, and Alternative Markets (5)

- `binance-btc-participation-tca` `[H]`: Binance BBO/trades, POV fills, VWAP, implementation shortfall, and spread TCA.
- `crypto-funding-rate-basis-carry` `[M]`: BTC perpetual funding, OU regimes, and basis-carry Monte Carlo.
- `intraday-volume-fitting-and-execution-scheduling` `[H]`: tick data, five-minute volume models, rolling selection, and scheduling.
- `lob-pc-signal` `[M]`: 15-level ADA order-flow imbalance, PCA, and rolling next-minute regression.
- `prediction-markets-cross-venue-dislocation` `[H][P]`: cross-venue matching, fee-adjusted locked edge, and capital-constrained paired trades.

Strength: closest to execution-aware agentic workflows. Weakness: frozen snapshots do not test live adaptation, and timestamp/sorting details make scoring brittle.

### Regulatory Filings, Fundamentals, and Data Engineering (7)

- `13f-amendment-aware-crowding` `[M]`: amendment-aware 13F holdings, turnover, overlap, and crowding.
- `corporate-action-adjustment` `[M]`: split and dividend price adjustments.
- `earnings-surprise-calculator` `[M]`: cross-company/quarter earnings surprise and SUE.
- `form4-cross-sectional-sale-pressure` `[H]`: Form 4 XML, position reconstruction, and insider-sale pressure.
- `polars-api-migration` `[M]`: migrate a Polars 0.x pipeline to 1.39.3 and deliver executable source.
- `sec-10k-report-long` `[M][O]`: multi-year SEC XBRL ZIP extraction of numeric, boolean, and text facts.
- `sec-8k-event-alpha` `[M][P]`: local 8-K HTML classification, numeric extraction, and event alpha.

Strength: file discovery, parsing, code repair, and complex deliverables. Weakness: small frozen samples and brittle regulatory/text gold; the 10-K oracle is not independently computed.

## Reward Audit and Composite Upgrade Score

Fourteen tasks return partial reward:

```text
barrier-garch-var
cta-basel-capital
evt-pot-var
fx-carry-forward-hedge
kelly-var-sizing
localvol-barrier
mtm-xccy-basis-desk
prediction-markets-cross-venue-dislocation
regime-cta-vol-target
regime-riskparity-cvar
sec-8k-event-alpha
sentiment-factor-alpha
structured-note-risk
yield-curve-bond-immunization
```

The partial schemes are heterogeneous: eight roughly split deliverables/checkpoints 50/50, three use pytest pass fractions, and the remaining tasks use passed-test or stage-weighted schemes. A score of 0.5 therefore does not have a uniform semantic meaning across tasks.

Formal aggregation must preserve the official `r_i` and use a stratified domain macro-average:

```text
R_domain(d) = mean(r_i for sealed held-out tasks i in domain d)
R_overall   = mean(R_domain(d) for the six domains)
```

Upgrade criteria:

1. paired improvement in held-out domain-macro reward beyond the declared uncertainty/noise threshold;
2. no material regression in a domain or safety gate;
3. success across repeated task/model seeds where stochasticity exists;
4. declared token, wall-clock, and sandbox-cost budgets;
5. immutable external-confirm and blind-final sets.

An optional headroom-normalized suite index may be reported, but its weights must be preregistered and raw scores must remain visible:

```text
u_b = clip((S_candidate - S_base) / max(1 - S_base, 0.05), -1, 1)
```

Do not modify QFBench task rewards to manufacture a gradient. Internal diagnostics may expose answer-free stage/pass counts, but official held-out reward remains the publication metric.

## Data Authority, Leakage, and Realism

Only two tasks contain a dedicated `environment/data/provenance.md`, and only three metadata files explicitly name a data source. Some inputs resemble or state frozen public sources—SEC filings, FRED, Treasury, SPDR, Deribit, and Binance—but many are synthetic, deterministic, or insufficiently documented. The benchmark cannot be described as uniformly bank-grade or uniformly real-market data.

Data duplication reduces effective diversity: eleven tasks share the same SPY file, seven share one glossary, three copy the same 35.6 MiB factor panel, and three share the same FRED file.

Execution realism is sparse. Only a minority explicitly model transaction costs, next-period execution, turnover, OOS evaluation, or uncertainty. Many tasks prove specification-following and numerical reconstruction, not future alpha discovery.

The public repository exposes tests, solutions, and reference artifacts. Required firewall:

```text
worker/evolver input = instruction + allowed task files + tools
verifier input       = worker artifacts + hidden tests + trusted original data
proposer feedback    = scalar reward + answer-free process/failure tags
forbidden feedback   = tests, gold, reference values, rubric answer text, raw diagnostic gold
```

Use task-family/workflow lineage splits rather than random task splits. Repeated variants and shared data must remain in the same partition.

## Curriculum and Held-Out Roles

Recommended stages:

1. **Smoke:** `historical-var-data-prep`, `momentum-backtest`, `fx-forward-cross-rate`.
2. **Dense reward:** `evt-pot-var`, `fx-carry-forward-hedge`, `localvol-barrier`, `mtm-xccy-basis-desk`, `prediction-markets-cross-venue-dislocation`, `sec-8k-event-alpha`, `yield-curve-bond-immunization`.
3. **Agentic workflow:** `13f-amendment-aware-crowding`, `polars-api-migration`, `event-study-earnings`, `binance-btc-participation-tca`.
4. **High-order held-out candidates:** `ipca-latent-factors`, `dcc-garch-portfolio-var`, `yield-curve-bootstrap-immunization`, `option-put-call-parity-forward-audit`.
5. **Deferred:** 35.6 MiB factor-panel tasks, very-long multimodal tasks, Hull–White, and all `O` tasks until the pipeline is stable or the oracle is rebuilt.

Do not run all 86 tasks on every edit. Use multi-fidelity scheduling: small train/dev batches for proposal selection, broader QF held-out evaluation for promotion, then low-frequency workflow and frozen external checks.

## Runtime and Network Audit

All 86 tasks are Linux single-container tasks with one single-stage Dockerfile. There are no Compose/sidecar, GPU, desktop, or database requirements. Dockerfiles primarily use `FROM`, `RUN`, `COPY`, and `WORKDIR`, structurally compatible with E2B templates.

Base-image references are not remotely resolvable:

- 77 use `finance-bench-sandbox:latest`;
- 2 use that local tag with a digest;
- 7 use `quantitative-finance-bench-sandbox:latest`.

Build the fixed QF base environment once, publish a registry-visible digest-pinned image, and generate a temporary overlay that rewrites `FROM`. Do not modify the pinned upstream snapshot.

Verifier network behavior contradicts an air-gapped interpretation:

- 79 verifier scripts download `uv` with `curl`;
- `cross-sectional-momentum` runs a package install;
- `credit-spread-decomposition` assumes `uvx`/packages are available.

Operationally, 81/86 verifiers require or assume runtime dependency access. The five clearly self-contained launchers are `binance-btc-participation-tca`, `double-sort`, `option-put-call-parity-forward-audit`, `residual-momentum`, and `stable-residual`.

Smoke policy: agent phase no-network; verifier phase temporary allowlist/public access. Publication policy: bake and pin `uv`, pytest, pytest plugins, and numerical dependencies; run verifier no-network.

## Why NexAU Itself Must Move to E2B

The current worker creates a new NexAU `Agent` per task in [`qea/worker_runtime.py`](../../qea/worker_runtime.py). Worker and evolve configs allow 200k context, up to 60/30 iterations, 32k output tokens, and `InMemoryTracer`. During high parallelism, each active Agent retains its own conversation and raw trace. GDPval-style office rendering also invokes LibreOffice/PyMuPDF locally.

Moving only shell execution to E2B leaves Agent state and trace memory local. To remove the actual concurrency multiplier, run the NexAU process inside each task sandbox. This follows the official AHE architecture, which preinstalls NexAU/Harbor in task templates and writes full rollout traces inside E2B.

Recommended stage-one topology:

```text
local or persistent-VM QEA coordinator
  -> account-level task lease
  -> E2B task sandbox: NexAU + worker snapshot + task environment
  -> separate verifier sandbox
  -> reward + compact answer-free summary + artifact/trace references
  -> kill/reap child sandboxes
```

The evolve agent may initially remain coordinator-side because it runs once per outer iteration. It should later move to an isolated editor sandbox for stronger secret and filesystem boundaries.

## Whole-QEA-on-E2B Feasibility

A QEA coordinator can run in a dedicated E2B sandbox and call the E2B API to spawn child sandboxes. This is an API-control pattern, not nested virtualization. It removes nearly all local resource use but adds a continuously billed control sandbox and another failure/security boundary.

Preconditions before moving the coordinator:

1. Port the complete `resume.json` semantics from the older soft loop to Level-B. Current Level-B only writes per-iteration `manifest.json` and `edit.diff`, and the CLI `--resume` flag does not apply to Level-B.
2. Make task attempts idempotent with stable `run_id/task_id/attempt_id` keys.
3. Persist incumbent worker, rejected-edit buffer, task table, rewards, artifact manifest, and cost ledger after every task/iteration.
4. Store durable state outside the sandbox. E2B pause preserves memory/filesystem, but active connections drop; E2B Volumes are currently private beta.
5. Add sandbox metadata, heartbeats, global leases, and orphan reaping.
6. Isolate secrets. The coordinator alone holds `E2B_API_KEY`; worker/evolve shells receive no control-plane credential and use scrubbed or short-lived model-access tokens.
7. Force-kill and resume the coordinator in a pilot before long experiments.

Current E2B limits and cost are temporally unstable and must be rechecked before each run. At this decision date, Hobby supports 20 concurrent sandboxes, 8 vCPU/8 GB maximum, and one-hour continuous sessions; Pro supports 100 concurrent sandboxes and 24-hour sessions for a USD 150 monthly base fee plus usage. A 2 CPU/4 GB sandbox is about USD 0.1656/hour and a 4 CPU/8 GB sandbox about USD 0.3312/hour.

Historical project evidence shows that launching at the nominal 20-sandbox cap caused many 429 failures. A later run used concurrency 16 and completed 26/30 tasks but still saw infrastructure errors. Use one global lease across workers, verifiers, renderers, and any E2B coordinator; start at 12–16 and add jitter/backoff.

## Minimal Implementation Surface

No change to evolve/falsify/rollback semantics is required. Expected changes are:

- split `run_worker()` behind `LocalNexAUExecutor` and `E2BNexAUExecutor`;
- build/pin a NexAU runner template and QF task templates;
- declare a pinned NexAU dependency (currently absent from `pyproject.toml`);
- upload worker snapshots and task bundles with stable hashes;
- write raw traces remotely and return compact summaries;
- move GDPval/FINCH rendering off the coordinator;
- add a global E2B lease and reaper;
- add Level-B checkpoint/resume and forced-failure tests;
- guarantee reconnect retries only the sandbox operation and never resamples the LLM;
- add parity, no-secret, no-test-leakage, and artifact-integrity tests.

## AutoDL No-GPU Feasibility

AutoDL’s public no-GPU mode is an inexpensive maintenance mode, not a configurable CPU server. The documented allocation is 0.5 CPU core, 2 GB RAM, no GPU, RMB 0.1/hour, and one no-GPU instance per main account. Existing data persists across mode changes.

This is insufficient for high-parallel NexAU because each active task may retain a large conversation/trace, while pandas/pyarrow, LibreOffice, PyMuPDF, and verifier processes add memory and CPU demand. It may run one lightweight coordinator or watchdog, but not 4–20 active agents.

More importantly, AutoDL instances are themselves containers and officially do not support Docker inside the instance. QFBench relies on per-task Dockerfiles and Harbor lifecycle/isolation. Flattening 86 environments into conda/venv would introduce dependency conflicts, weaken test/gold isolation, and break official environment comparability; that would be a large framework change.

Automation is also limited: the Pro API can query and power instances but currently documents only GPU-mode power-on and explicitly says no-GPU API startup is unsupported. Therefore a watchdog cannot autonomously recreate/boot a no-GPU coordinator. SSH/tmux works, but local SSD storage has no redundancy guarantee and must be backed up externally.

Accepted uses for AutoDL no-GPU:

- manual log inspection;
- repository/data storage with external backup;
- a cheap watchdog or single low-frequency coordinator after all heavy work is elsewhere;
- maintenance between GPU-mode sessions.

Rejected uses:

- high-parallel NexAU workers;
- official QFBench Docker/Harbor execution;
- concurrent office-document rendering;
- autonomous horizontal scaling;
- a complete no-E2B replacement.

If E2B must be avoided, use a persistent Docker-capable CPU VM, initially around 8 vCPU and 16–32 GB RAM. AutoDL bare metal could technically provide Docker, but it is outside no-GPU mode and is likely an inefficient GPU-oriented procurement for this workload.

## Deployment Decision Matrix

| Topology | Local memory relief | QFBench fidelity | Parallelism | Durability | Decision |
|---|---|---|---|---|---|
| Local QEA + E2B NexAU/task/verifier | High | High | High within account quota | External checkpoints on coordinator | **Adopt first** |
| E2B QEA coordinator + E2B children | Complete | High | Medium/high; coordinator consumes a slot | Conditional on external state/resume | **Second-stage pilot** |
| One large E2B for all tasks | Complete | Low isolation | Limited by one sandbox | Single failure domain | Reject |
| AutoDL no-GPU all-in-one | Complete local relief | No Docker fidelity | Very low | Persistent disk but weak automation | Reject |
| AutoDL no-GPU coordinator + E2B children | Complete | High | E2B-limited; coordinator weak | Manual no-GPU lifecycle | Optional, low value |
| Docker-capable CPU VM all-in-one | Complete | High | Machine-limited | Strong persistent host | Preferred no-E2B alternative |

## Pilot and Acceptance Gates

### Pilot 1: E2B Oracle Parity

Use `historical-var-data-prep` because the [saved local oracle](../../results/qfbench_smoke/20260721T144046+0800_024921eb/run_status.json) passed 12/12 tests at reward 1.0. Run the same pinned task/oracle in E2B and compare reward, pytest count, required outputs, and hashes or canonicalized contents. Then run the unchanged seed worker. Add `momentum-backtest` and `evt-pot-var` to cover multi-output and partial-reward behavior.

Acceptance:

- exact official reward parity where deterministic;
- no tests/solution/reference gold visible during agent execution;
- no `E2B_API_KEY` or unrestricted model key visible to shell;
- complete artifacts and logs recovered;
- no orphan sandbox after success/failure.

### Pilot 2: Concurrency and Memory

Run concurrency 1, 4, 8, and 16 while measuring coordinator RSS, per-sandbox peak memory, trace bytes, artifact bytes, task latency, 429/connection failures, and sandbox cost. The coordinator should retain compact summaries rather than a concurrency-proportional set of full traces.

### Pilot 3: Coordinator Migration

Only if Pilot 2 shows the coordinator remains a bottleneck, run one outer iteration with three tasks in a 4 CPU/8 GB coordinator sandbox. Checkpoint at task and iteration boundaries, deliberately kill the coordinator, resume from external state, and verify that incumbent, buffer, rewards, and attempt counts are identical and non-duplicated.

## Research-Integrity Gate

Engineering smoke is ready with warnings. Publication-scale QFBench evolution is not ready until the lineage split, independent verifier, copy-oracle disposition, pinned offline dependencies, repeated-run uncertainty, and E2B parity are complete. Do not report a QFBench seed score, cloud equivalence, or aggregate agent upgrade until its raw run artifact exists.
