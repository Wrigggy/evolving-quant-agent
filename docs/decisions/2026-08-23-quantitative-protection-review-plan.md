# Quantitative protection review plan

**Date:** 2026-08-23

**Status:** Proposed mechanism and pending experiment. This record uses retained
results as inputs, but does not report a new Reviewer run, controller change,
promotion, or benchmark result.

## Decision

Add a small answer-free **Quantitative Regression Reviewer** only at an
ambiguous protection boundary. It should distinguish stochastic Worker
variation, tolerance-level numerical movement, a broken public quantitative
relation, and unsafe candidate integration. It may recommend one additional
paired protection observation or a refinement locus, but it may not promote a
candidate. A fixed controller continues to own `PASS`, `INCONCLUSIVE`, `FAIL`,
promotion, and incumbent selection.

The immediate controller extension is:

```text
repeated target gain
    -> protection comparison
        -> PASS: PROMOTE
        -> INCONCLUSIVE: answer-free quantitative review
             -> at most one predeclared paired protection repeat
             -> PASS, HOLD_FOR_REFINE, or remain unresolved
        -> FAIL: reject current candidate promotion
             -> HOLD_FOR_REFINE when target gain repeated
             -> RETIRE when target gain did not repeat
```

`HOLD_FOR_REFINE` is a search-lineage state, not a deployment decision. The
official incumbent stays unchanged. The useful component, exact candidate,
activation evidence, protection trace, and suspected integration defect remain
available to the Evolver for one bounded child refinement.

The compact rule is:

> Retain the component, reject the current candidate promotion, and continue
> one evidence-directed refinement of the same lineage.

## Why this is quant-specific without denying general randomness

Trajectory stochasticity is general. Repeated code-model sampling and modern
agentic-evaluation studies already show that one run is an unstable estimate of
capability. QEA does not claim that repeated sampling or variance estimation is
new.

The proposed domain mechanism starts one level later. A Quant Research Worker
constructs continuous and coupled states: data vintages, quotes and units,
calibration parameters, curves or surfaces, differentiated quantities,
simulation outputs, portfolios, and final artifacts. Small upstream changes can
propagate through calibration, interpolation, differentiation, simulation, or
aggregation. A property-based verifier then discretizes those continuous
movements through tolerances and parameterized assertions. Consequently, a
small numerical change can exchange one failed property for another without
showing a meaningful loss of research capability, while an unchanged aggregate
score can conceal a newly broken economic relation.

Local-volatility calibration is a concrete example rather than the whole
method. It is an ill-posed inverse problem for which regularization is used to
obtain stable solutions. That structure makes score-only or
any-property-regression selection especially weak: the controller needs to
reason about upstream-to-downstream quantitative reconciliation, not merely the
count of green checks.

The proposed contribution is therefore not "quant tasks are random." It is:

> An answer-free protection review that interprets candidate regressions through
> public quantitative relations and Research-State propagation, separating
> stochastic trajectory variation from structural inconsistency and unsafe
> component integration.

## Evidence and answer boundary

The Reviewer may inspect:

- the public task specification;
- parent and candidate harness source or diff;
- answer-free parent and candidate Worker trajectories;
- component registration, routing, activation, and artifact changes;
- aggregate reward and passed-property counts;
- answer-free failure-family movement when the official interface exposes it;
- same-configuration baseline variability already retained as development
  evidence; and
- public relations such as information-time validity, unit and numeraire
  consistency, put--call or forward parity, no-arbitrage, calibration-to-
  valuation reconciliation, portfolio closure, and artifact consistency.

It may not inspect checker expected values, hidden tests, reference solutions,
raw answer-rich rubric, property-level expected-versus-observed answers, sealed
outcomes, or credentials. It may not write a task answer or task-specific patch
into a reusable Worker component.

## Protection states

### `PASS`

The candidate remains inside a predeclared non-inferiority band and introduces
no critical public-relation break. The fixed controller may promote it after
all other target and repeat gates pass.

### `INCONCLUSIVE`

The movement is small, the aggregate is stable while property identities swap,
or the retained evidence cannot separate stochastic variation from a candidate
effect. The Reviewer may request at most one predeclared paired protection
repeat. It cannot select the better of several samples.

### `FAIL`

The candidate clearly exceeds the non-inferiority band or breaks a critical
public quantitative relation. It is not promoted. If the target gain repeated,
the controller should retain the component under `HOLD_FOR_REFINE`; otherwise
it should retire the current candidate.

For the first mechanism canary only, a three-property band on the 39-property
`localvol-barrier` task is a provisional operational threshold derived from the
retained 38/39 and 35/39 Quant-H0 observations. It is not a confidence interval
and is not a frozen main-experiment margin. Any critical public-relation break
overrides that count-based band. A later main experiment must predeclare its
margin from matched Quant-H0 repeats before observing candidate protection.

## Retained anchors and intended classifications

### Main-0B is a clear candidate-integration regression

The retained Main-0B local-vol protection moved from 35/39 to 29/39. The trace
also shows an upstream forward/unit inconsistency followed by downstream
surface modification. This is not a light numerical fluctuation and must not be
reclassified as `PASS`. The intended result is:

```yaml
protection_state: FAIL
outcome_severity: MEANINGFUL_CANDIDATE_REGRESSION
causal_attribution: HARNESS_WORKER_INTERACTION
quantitative_diagnosis:
  - UPSTREAM_STATE_UNVERIFIED
  - DOWNSTREAM_RECONCILIATION_WITHOUT_UPSTREAM_VALIDITY
controller_action: HOLD_FOR_REFINE
```

This rejects the current candidate integration. It does not establish that the
target-helpful component is intrinsically useless.

### Search-v2 is the gray case

The retained Search-v2 protection stayed at 38/39 and the same aggregate
reward, but the failed property changed. Aggregate-only selection would promote
it; strict property-wise selection rolls it back. This is the appropriate
`INCONCLUSIVE` case for Reviewer analysis and, at most, one paired protection
repeat. The Reviewer must not choose a favorable sample or infer stability from
an unchanged count alone.

## Reviewer output and authority

Use a compact structured report:

```yaml
outcome_severity: >-
  WITHIN_PROVISIONAL_VARIABILITY |
  MEANINGFUL_CANDIDATE_REGRESSION |
  UNRESOLVED
causal_attribution: >-
  COMPONENT_CAUSAL |
  WORKER_TRAJECTORY |
  HARNESS_WORKER_INTERACTION |
  UNRESOLVED
quantitative_diagnosis: >-
  NUMERIC_TOLERANCE_ONLY |
  PUBLIC_RELATION_BROKEN |
  UPSTREAM_STATE_UNVERIFIED |
  DOWNSTREAM_RECONCILIATION_WITHOUT_UPSTREAM_VALIDITY |
  COMPONENT_NOT_APPLICABLE |
  NO_QUANT_SPECIFIC_EVIDENCE
next_evidence: >-
  NO_EXTRA_RUN |
  PAIRED_PROTECTION_REPEAT |
  HOLD_FOR_REFINE |
  RETIRE_CURRENT_INTEGRATION
evidence_refs: ["answer-free evidence locations"]
```

The Reviewer diagnoses and recommends evidence. The controller applies a
frozen rule and owns promotion. The same controller, Reviewer availability,
protection margin, repeat limit, evidence access, and cost accounting must be
used for the generic and QRS arms. Otherwise a search-treatment effect would
be confounded with a different selection policy.

## Experiment plan

### QPR-0: zero-model rule replay

Build four answer-free evidence cards and exercise the deterministic triage:

1. retained same-task Quant-H0 observations at 38/39 and 35/39, used only as
   an illustration of baseline variation rather than a variance estimate;
2. a synthetic one-property candidate movement without a public-relation break;
3. the retained Main-0B 35/39 to 29/39 integration failure; and
4. an aggregate tie with a newly broken public relation.

Compare aggregate-only, strict property-wise, and quantitative-review policies.
The replay is positive only if it avoids calling ordinary baseline variation a
proven capability loss, does not wash away Main-0B, distinguishes candidate
integration failure from component uselessness, and catches the structural
break under an aggregate tie.

### QPR-1: one answer-free Reviewer canary

Present the four frozen cards in one Reviewer session. Require structured
output, evidence references, and no hidden answer access. Main-0B must remain a
meaningful regression with `HOLD_FOR_REFINE`; Search-v2 must remain gray rather
than being promoted from its tied aggregate score. If the Reviewer adds no
discrimination beyond the fixed score rules, retain that neutral result and do
not insert it into the controller.

### QPR-2: one real ambiguous protection confirmation

Only after QPR-0 and QPR-1 pass, freeze the Search-v2 candidate and run one
matched parent/candidate `localvol-barrier` protection pair under the same
model route, budget, and execution contract. Do not rerun Main-0B: its retained
regression is already outside the gray zone. Do not use best-of-two selection.

Predeclare the terminal mapping:

- repeated candidate regression outside the margin or a repeated critical
  relation break: no promotion and `HOLD_FOR_REFINE`;
- candidate inside the provisional band with no critical relation break:
  provisional non-inferiority, eligible for experimental promotion after the
  fixed controller checks all gates; or
- conflicting evidence: remain `INCONCLUSIVE`, stop additional repeats, and
  retain the component for scope refinement.

### Controller integration

Only after the replay and canary demonstrate added discrimination should the
thin lineage controller add `INCONCLUSIVE`, Reviewer evidence, and
`HOLD_FOR_REFINE`. Resume must cover a completed review before repeat dispatch
and a completed repeat before terminal selection. Do not add a general
scheduler, RAG system, database, or multi-branch search for this bounded gate.

## Claim boundary

QPR-0 is a rule preflight. QPR-1 is Reviewer behavior evidence. QPR-2 is one
development protection comparison. None is a sealed result, benchmark-level
gain, stable capability estimate, or proof that QRS beats generic harness
evolution. The mechanism claim requires that the Reviewer improve
classification or refinement localization under the frozen policy; a Reviewer
that merely adds finance vocabulary is neutral.

## Sources

- [Evaluating Large Language Models Trained on Code](https://arxiv.org/abs/2107.03374)
- [On Randomness in Agentic Evals](https://arxiv.org/abs/2602.07150)
- [Calibration of the Local Volatility in a Generalized Black--Scholes Model Using Tikhonov Regularization](https://doi.org/10.1137/S0036141001400202)
