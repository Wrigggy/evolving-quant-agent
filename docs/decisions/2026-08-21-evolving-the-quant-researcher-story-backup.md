# Evolving the Quant Researcher: story backup

**Date:** 2026-08-21

**Status:** Accepted story backup and proposed research direction. This record
does not report a new experiment, claim that the method below is implemented,
or supersede measured benchmark outcomes.

## Central story

The paper's central idea is:

> **Evolving the Quant Researcher, Not the Strategy.**

Most quantitative agents repeatedly improve factors, models, portfolios,
strategies, or executable research artifacts inside a largely fixed research
scaffold. QEA studies a different persistent object: the harness-mediated
capabilities of the Quant Research Worker Agent that produces and validates
those artifacts.

The base language model remains frozen. The editable object is the Worker
harness: prompts, tools, skills, memory, middleware, validators, routing, and
workflow. A factor or strategy is an episode output. A harness component is a
potentially reusable research capability, such as point-in-time data
resolution, fit-scope validation, market-convention normalization,
calibration auditing, portfolio reconciliation, or artifact closure.

This motivation is not sufficient by itself as a novelty claim. Agentic
Harness Engineering already evolves a frozen model's harness from accumulated
trajectories, while AQuA, RD-Agent(Q), QuantaAlpha, and related quantitative
systems already improve later research from evaluated attempts. The proposed
quant-specific difference must therefore alter the search and verification
process, not merely rename the Worker, trajectories, or failure fields.

## Quant research as constrained state transformation

A quantitative-research task is treated as a sequence of stateful
transformations under an information set. For task \(q\) at research step
\(k\), write a task-conditioned research state as

\[
\mathcal{R}_{q,k}
=
\left(
I_{q,k},
X_{q,k},
C_{q,k},
\Theta_{q,k},
Y_{q,k},
A_{q,k}
\right),
\]

where:

- \(I\), **Information State**, records as-of time, availability time, data
  vintage, calendar, universe, windows, and missing-data policy;
- \(X\), **Economic State**, records the effective economic object, such as
  holdings, positions, curves, surfaces, orders, or adjusted series;
- \(C\), **Convention State**, records units, currency, numeraire, quote
  direction, sign, tenor, day count, frequency, and annualization;
- \(\Theta\), **Estimation State**, records fit sample, fold, transforms,
  estimator, calibration parameters, random state, and hyperparameters;
- \(Y\), **Derived Result State**, records factors, signals, portfolios,
  prices, Greeks, risk measures, PnL, attribution, and summaries; and
- \(A\), **Artifact State**, records the final code, tables, figures, reports,
  and whether those deliverables close over one consistent final state.

A Worker action induces a transition

\[
\mathcal{R}_{q,k+1}
=
T_k\left(\mathcal{R}_{q,k};H_i\right),
\]

where \(H_i\) is the current harness. A consequential failure may be a wrong
state, a violated transition relation, or a stale downstream artifact even
when each local code fragment appears plausible.

The six states are an open task-conditioned representation, not a mandatory
linear pipeline or a closed error taxonomy. A task may omit, revisit, or
combine states. The useful object is the concrete state and relation inferred
for the current task, not the fact that the report contains six finance-like
labels.

## Theoretical and practitioner foundations

### Information sets and non-anticipativity

At decision time \(t\), a legitimate research state must be adapted to the
information available at that time:

\[
I_t = \{x_j : \operatorname{available\_time}(x_j) \le t\}.
\]

Features, estimators, signals, portfolios, and hedges for \(t\) must not depend
on later observations, later revisions, future universe membership, or
evaluation-fold information. This covers point-in-time language models,
regulatory filings and amendments, corporate actions, event studies, rolling
windows, fold-local preprocessing, and vintage-aware macro data.

Point-in-time validity is one quantitative obligation, not the overall method
name. The 13F branch should therefore be described as **point-in-time
effective-state reconciliation**, not "point-in-time lineage evolution."

### Econometric and quantitative restrictions

Quantitative models and artifacts often imply testable relations even when the
complete answer is unknown. In the spirit of moment-condition methods, a
researcher may test restrictions of the form

\[
\mathbb{E}[g(Z_t,\theta)] = 0
\]

or task-local realized relations such as repricing residuals, portfolio
budgets, PnL decompositions, exposure aggregation, loss-tail ordering, or
calibration admissibility. QEA calls an instantiated public relation a
**quantitative reconciliation**. It is not an answer oracle and does not
replace the official evaluator.

### Economic consistency and no-arbitrage

Pricing, curve, volatility, risk, carry, and hedging tasks impose economic
constraints in addition to numerical accuracy. Examples include put--call
parity, cross-rate triangulation, discount-factor positivity, instrument
repricing, option-surface admissibility, self-financing relations, and
consistent long/short or receive/pay signs. These constraints motivate
reusable Worker-side research controls rather than task-specific expected
values.

### Model development, effective challenge, and outcome analysis

Financial model-risk practice distinguishes model development, conceptual
soundness, process verification, effective challenge, outcome analysis, and
ongoing monitoring. QEA borrows this decomposition as a research-process
analogy, not as a regulatory-compliance claim:

| Model-validation concept | QEA analogue |
|---|---|
| model development | Worker executes the task and produces artifacts |
| conceptual soundness | mandate, information, representation, and assumptions |
| process verification | component activation and state-transition observation |
| effective challenge | Evolver compares competing explanations |
| corrective action | Evolver changes a reachable harness component |
| outcome analysis | unchanged official property or task result |
| ongoing monitoring | repeat, protection, and matched transfer |

The Evolver is therefore closer to a research lead or model challenger than a
second strategy generator. It improves the process and controls through which
the Worker conducts research.

### Adaptive research and multiple testing

Each Worker evaluation is a research trial. Once an optimize-task outcome
influences candidate selection, that task is adaptive development evidence and
is not out of sample. Candidate history is therefore a research-trial ledger:
it records the attempted research-process modifications, observed outcomes,
cost, and selection path. The harness must be frozen before sealed final
evaluation, and sealed results must never return to search or retrieval.

This is the real experimental use of candidate history. Versioning, rollback,
and caching remain infrastructure rather than quant-specific novelty.

## Quant Research Worker flow

The high-level Worker flow is:

```text
Research Mandate
    -> Information-Set Construction
    -> Economic and Market Representation
    -> Estimation / Calibration / Pricing / Portfolio Operation
    -> Economic Validation and Reconciliation
    -> Research Artifact Closure
```

### Research Mandate

The Worker identifies the economic object, target quantity, as-of or decision
time, units and measure, evaluation meaning, and required deliverables.

### Information-Set Construction

The Worker constructs the admissible data vintage, calendar, universe,
revision state, windows, and train/validation/test scope.

### Economic and Market Representation

The Worker binds entity identity, effective holdings or positions, quote and
currency convention, sign, tenor, frequency, and portfolio normalization.

### Research Operation

The Worker performs feature construction, estimation, calibration, pricing,
simulation, optimization, backtesting, risk analysis, or attribution while
retaining the relevant estimator and transformation state.

### Economic Validation and Reconciliation

The Worker tests applicable moment, accounting, no-arbitrage, repricing,
aggregation, sensitivity, and upstream-to-downstream consistency relations.

### Research Artifact Closure

The Worker ensures that final tables, metrics, summaries, code, and reports are
all derived from the same final upstream state and are delivered through the
required interface.

This flow is not a claim that all tasks are trading strategies. It applies to
QFBench and QuantCodeEval tasks involving data preparation, estimation,
pricing, calibration, portfolio construction, backtests, risk, and executable
research artifacts.

## Quant-state-guided intervention loop

The proposed Evolver loop is:

```text
Worker trajectory and artifacts
    -> reconstruct expected and observed Quant Research State
    -> compare competing explanations
    -> identify one violated or uncertain quantitative relation
    -> select a reachable harness component
    -> predict one state transition and official or protected effect
    -> implement and locally smoke the component
    -> run a fresh answer-blind Worker
    -> observe activation, state correction, official outcome, and scope
    -> promote, refine, reuse, revert, archive, or abstain
```

The method conditions component search on state and relation:

\[
p(c\mid\tau)
\quad\longrightarrow\quad
p(c\mid\tau,s,g),
\]

where \(\tau\) is the trajectory, \(s\) is the task-conditioned state, \(g\)
is the suspected relation, and \(c\) is a harness component. The hypothesis is
that informative \((s,g)\) reduces the number of inactive or mislocalized
candidate edits. This is an empirical efficiency hypothesis, not a theorem.

Quant Research State must affect four operational surfaces:

1. **Evidence retrieval:** retrieve related positive, negative, inactive, and
   unstable experience by state and relation rather than only task ID.
2. **Component routing:** use the state mismatch to narrow likely prompt, tool,
   skill, validator, middleware, memory, routing, or workflow loci while
   allowing Evolver override.
3. **Probe selection:** choose the cheapest observation that discriminates the
   leading explanations or return calibrated insufficiency.
4. **Intervention verdict:** distinguish creation, activation, predicted state
   correction, official outcome, and repeat/protection scope.

If state labels do not alter these four surfaces, the method is only a
quant-themed report schema.

## Intervention evidence ladder

For every candidate, keep these observations distinct:

1. **Admitted:** a material candidate exists and passes its local component
   check.
2. **Activated:** a fresh Worker reaches and uses the component when
   applicable.
3. **State-correcting:** the predeclared quantitative relation changes as
   predicted.
4. **Benchmark-helpful:** the unchanged official verifier reports a property
   or binary gain.
5. **Stable or reusable:** the gain repeats and survives protection or matched
   transfer under a declared scope.

A local invariant, component smoke, or Evolver `ACT` is not a benchmark result.
An official gain without the predicted state correction is performance
evidence with unresolved mechanism attribution. A protection task that does
not activate the component establishes non-regression, not mechanism reuse.

## Relationship to adjacent work

- Relative to quantitative self-improvement systems, the hook is **evolving
  the researcher rather than only the strategy, factor, model, or program**.
- Relative to AHE and other generic harness evolution, the proposed difference
  is the quant-research inductive bias over failure localization, component
  routing, probe design, and intervention verification.
- Relative to TTT-Discover, evaluated attempts are retained, but the base model
  weights remain frozen and adaptation occurs in harness space.
- Candidate history, runtime experience, rollback, independent replicates,
  caching, and scheduling are required substrate and must not be claimed as
  the domain contribution.

## Baseline and claim boundary

The intended generic full-harness baseline should be strong and matched, not
artificially weakened. It receives the same public tasks, allowed trajectories,
optimize diagnostics, mutation surface, model routes, answer policy, and total
budget. The controlled difference is that it uses generic layered diagnosis
and task-delta evidence, whereas QEA receives the operational state card,
state-conditioned retrieval/routing, quantitative-reconciliation primitives,
and activation/state/outcome verdict.

The primary claim need not be a large final-score win. A defensible result is:

> QEA reaches comparable frozen official performance with fewer Worker or
> verifier calls, fewer inactive or mislocalized interventions, or fewer
> protection regressions.

Useful metrics are candidates, Worker calls, verifier calls, tokens, cost, and
wall time to the first activated state correction and first official gain;
admission-to-activation yield; activation-to-state-correction yield;
state-correction-to-official-gain yield; protection-regression rate; and final
frozen official reward.

## Current evidence and boundary

Current retained evidence motivates but does not prove this story:

- a public quantity-semantic relation produced two independent T12 full solves
  with T19 protection, but the decisive relation was investigator seeded;
- the certificate canary showed that finance-shaped wording alone did not
  improve generic diagnosis;
- a local-vol component produced one fresh binary target gain but regressed on
  protection;
- a 13F effective-state component produced one property-gain event, but its
  protection Worker did not activate the component and the next refinement
  regressed;
- copula activation tied its retained target comparator.

The remaining scientific question is therefore whether operational
quant-state conditioning makes Evolver search more efficient or better scoped
than matched generic full-harness evolution. The remaining engineering
question is whether the bounded candidate controller can run proposal,
evaluation, repeat, protection, promotion/rollback, resume, and freeze without
manual stage repair.

## Research sequence retained by this backup

```text
Story backup
    -> executable method specification
    -> implement state-conditioned search on the existing Evolver
    -> bounded mechanism-localization canary
    -> simplify and rehearse the pre-main controller
    -> return to the Main-0 / Main-1 runway
```

Do not start the earlier broad Main-0 directly from this story record. First
show that the state card changes retrieval, routing, probe choice, or verdict in
a bounded real candidate search. Then return to the already prepared scale
runway with the method and story frozen.

## Sources

- [Revised Supervisory Guidance on Model Risk Management](https://www.federalreserve.gov/frrs/guidance/supervisory-guidance-on-model-risk-management.htm)
- [Scaling Point-in-Time Language Models](https://www.nber.org/papers/w35247)
- [Too Good to Be True: Look-ahead Bias in Empirical Options Research](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4590083)
- [Generalized Method of Moments Estimation](https://larspeterhansen.org/lph_research/generalized-method-of-moments-estimation/)
- [Arbitrage-free neural-SDE market models](https://arxiv.org/abs/2105.11053)
- [Backtesting Strategies Based on Multiple Signals](https://www.nber.org/papers/w21329)
- [Agentic Harness Engineering](https://arxiv.org/abs/2604.25850)
- [AQuA](https://arxiv.org/abs/2608.12841)
- [R&D-Agent-Quant](https://arxiv.org/abs/2505.15155)
- [QuantaAlpha](https://arxiv.org/abs/2602.07085)
- [Learning to Discover at Test Time](https://arxiv.org/abs/2601.16175)
