# Quant-research-state-guided search method specification

**Date:** 2026-08-21

**Status:** No-model implementation preflight complete. No live mechanism
canary or main experiment is reported by this document.

**Story source:**
[Evolving the Quant Researcher story backup](../../decisions/2026-08-21-evolving-the-quant-researcher-story-backup.md)

## Implementation checkpoint

The first implementation now reuses the existing Evolver and component catalog:

- one guarded tool materializes the open State Card after its selected relation
  cites evidence the Evolver has read;
- the same component catalog available to the generic arm is filtered by state,
  relation, component, task-mechanism, and desired-observation coordinates;
- retrieval returns at most one positive, negative, inactive, and unstable
  episode per class by default;
- `ACT` must bind the card's selected relation and component locus to the
  terminal decision and primary harness component;
- generic and quant-state coordinated views retain the same history and
  diagnostics, with the operational State Card helper as the treatment; and
- the bounded Worker receives only the Evolver-authored activation instruction,
  not the State Card or optimize-only diagnostics.

A 138-test relevant compatibility run passed in the repository development
environment. This checkpoint demonstrates executable wiring only. It does not
show that the quant-state treatment is faster or better than the generic arm;
that remains the purpose of the four-initial-candidate live canary below.

## Objective

Make Quant Research State an operational search prior for the existing full-
harness Evolver. The implementation succeeds only if the state representation
changes at least one of evidence retrieval, component routing, probe selection,
or intervention verdict. Adding finance vocabulary to the terminal decision is
not sufficient.

The immediate research question is:

> Under a matched candidate and evaluation budget, does a task-conditioned
> quantitative-state representation help the Evolver reach an activated,
> state-correcting, officially useful harness component with fewer search and
> evaluation calls than generic structured trajectory diagnosis?

## Non-goals

This phase does not:

- implement the full Main-0 scheduler;
- run a sealed test panel;
- add an exhaustive finance failure taxonomy;
- prescribe a task answer or fixed task-specific checker;
- change the official evaluator;
- expose optimize answers to the Worker;
- claim regulatory compliance;
- replace the full harness mutation surface with prompt-only search;
- make candidate history or lineage a method contribution; or
- require open-ended Evolver-controlled Worker scheduling.

## Existing substrate to reuse

Reuse the current:

- Quant-H0 Worker identity and six high-level Research States;
- full editable Worker harness;
- guarded Evolver workspace and structured `decide_candidate` action;
- `research_state_transition`, `probe_task_key`, and `experiment_spec` fields;
- answer-rich optimize / answer-blind Worker evidence boundary;
- QFBench coordinated target dispatch and normal-budget Worker runner;
- QuantCodeEval and QFBench official verifiers;
- component activation evidence and local component smokes; and
- retained positive, negative, inactive, and unstable experiment records.

Do not introduce a second candidate controller in this phase. The method layer
should feed the existing bounded proposal and evaluation path.

## Quant Research State Card

Before an `ACT`, the Evolver must materialize one compact state card for the
selected target. Fields may be `N-A` or `UNKNOWN` when unsupported; unsupported
fields must not be invented.

```yaml
schema_version: 1
task_key: qfbench:example
research_mandate:
  economic_object: "what is being estimated, priced, or constructed"
  target_quantity: "quantity and measure requested by the task"
  decision_or_as_of_time: "time semantics or N-A"
  required_artifacts: ["public deliverable names"]
information_state:
  available_data: "relevant public inputs"
  vintage_or_revision_rule: "rule or N-A"
  calendar_and_universe: "scope or UNKNOWN"
  fit_evaluation_split: "scope or N-A"
economic_state:
  effective_object: "holdings, curve, surface, portfolio, etc."
  identity_and_grouping: "keys, entities, pair identity, grouping"
convention_state:
  units_and_scale: "decimal, percent, bps, currency, etc."
  sign_and_quote: "long/short, receive/pay, base/quote, etc."
  frequency_and_calendar: "frequency, tenor, day count, annualization"
estimation_state:
  operation: "fit, calibrate, price, simulate, optimize, backtest, etc."
  fit_scope: "sample, fold, windows, transforms, parameters"
derived_state:
  upstream_objects: ["authoritative upstream states"]
  downstream_outputs: ["prices, risks, metrics, summaries, artifacts"]
candidate_relations:
  - relation_id: "open descriptive identifier"
    applicability: "public reason it applies"
    expected_relation: "executable or observable requirement"
    observed_evidence: ["allowed evidence locations"]
    status: PASS | FAIL | N-A | UNKNOWN
competing_explanations:
  - hypothesis: "state or transition explanation"
    support: ["evidence locations"]
    counterevidence: ["evidence locations"]
selected_intervention:
  relation_id: "one selected candidate relation"
  state_locus: "one primary state or transition"
  component_locus: "one harness role such as tools, skills, middleware, or routing"
  predicted_transition: "fresh Worker behavior expected to change"
  discriminating_observation: "cheapest observation that changes the decision"
```

The card is open and task conditioned. `relation_id` values are not drawn from
a closed benchmark-answer lookup. The Evolver may propose a new relation when
it can justify applicability from public task semantics or authorized optimize
evidence.

## State and relation vocabulary

The method supplies a small open vocabulary for navigation, not mandatory
failure labels:

- `information_admissibility`: availability time, vintage, revision,
  calendar, universe, fold leakage;
- `quantity_semantics`: target quantity, aggregation, grouping, units, scale,
  annualization;
- `market_representation`: currency, numeraire, quote direction, sign, tenor,
  identity;
- `estimation_scope`: fit sample, preprocessing, parameter support,
  calibration, random state;
- `economic_reconciliation`: moment, accounting, no-arbitrage, repricing,
  PnL, exposure, or risk relation;
- `derived_state_closure`: downstream outputs and summaries derive from one
  final upstream state; and
- `artifact_closure`: executable replay, complete delivery, and consistent
  final artifacts.

These coordinates help retrieval and routing. They do not determine the final
component or count as evidence without task-local support.

## Search behavior

### 1. Reconstruct the state

Read the public task and selected trajectory/artifact evidence. Fill only the
fields relevant to the earliest consequential mismatch. Record at least two
explanations when evidence supports them; otherwise explain why a single
explanation dominates or return insufficiency.

### 2. Select a relation

Select one relation whose observation would materially distinguish the leading
explanations or verify the intended intervention. The relation may be a public
semantic fixture, temporal perturbation, fit-scope audit, dimensional or sign
reconciliation, repricing residual, portfolio identity, sensitivity test, or
artifact replay.

Reject self-confirming relations. A check is self-confirming when the Worker
chooses the very definition that the check later validates and the public task
does not bind that definition. The T12 quantity-semantic history is the
canonical observed example.

### 3. Route to a component locus

Use the state and relation as a prior:

| Suspected locus | Candidate component examples |
|---|---|
| mandate / quantity semantics | prompt policy, public-definition binder |
| information admissibility | as-of resolver, temporal audit tool, workflow |
| market representation | convention normalizer, typed intermediate state |
| estimation scope | fit-scope tool, estimator workflow, semantic validator |
| economic reconciliation | executable audit or repair tool |
| derived-state closure | reconciliation skill, final-state workflow |
| artifact closure | completion middleware, finalizer, replay validator |

The Evolver may override the table when it records evidence for another locus.
The mutation surface remains the complete harness.

### 4. Retrieve experience

The initial implementation uses a compact retrieval query containing:

- selected state locus;
- selected relation family;
- candidate component locus;
- relevant task mechanism; and
- desired observation.

Return at most the most relevant positive, negative, inactive, and unstable
episodes plus the exact current parent component. Do not default to the full
history tree. Candidate history remains available for drill-down.

Retrieval must exclude sealed-final outcomes and trusted evaluator answers.
Optimize-task expected-versus-observed diagnostics may be returned to the
Evolver under the accepted answer-rich policy; they must never enter the Worker
prompt, reusable component, or transfer/protection evidence.

### 5. Choose a probe

The Evolver chooses one predeclared optimize target and a bounded Worker
experiment. The probe instruction must name the new component and ask the
Worker to use it when applicable while still completing the task. A short
probe may diagnose reach and completion distance, but normal-budget fresh
Worker evaluation remains the performance authority for observed long-tail
tasks.

Probe selection is guided by expected discrimination per cost, but this phase
does not implement a general cost-aware scheduler. The Evolver selects one
bounded experiment within the existing coordinator contract.

### 6. Decide and retain evidence

Each candidate receives one intervention verdict:

- `INACTIVE`: the component was not reached or used when expected;
- `MISLOCALIZED`: it activated but the predicted state did not change;
- `STATE_CORRECTING`: the relation changed as predicted without official gain;
- `TASK_HELPFUL`: predicted state correction and official target gain agree;
- `STABLE_OR_REUSABLE`: target gain repeats and protection or matched transfer
  supports the declared scope;
- `UNRESOLVED`: official behavior changed without adequate mechanism
  attribution; or
- `ABSTAIN`: evidence does not support a bounded intervention.

Only official property or task outcomes support benchmark-performance claims.
Only repeat/protection/transfer supports stability or reuse.

## Minimal candidate decision payload

Extend the current structured decision conceptually with:

```yaml
quant_research_state_card: "relative evidence path"
selected_relation:
  relation_id: "open identifier"
  applicability: "public or optimize-evidence support"
  predicted_status_change: "FAIL/UNKNOWN -> PASS or another observable change"
component_routing:
  selected_locus: "one primary component locus"
  rejected_loci:
    - locus: "alternative"
      reason: "evidence or reachability reason"
research_state_transition:
  state_id: "existing high-level state"
  expected_state: "task-conditioned expected state"
  observed_state: "trajectory-supported observed state"
  target_state: "state expected after intervention"
  transition_observable: "selected quantitative relation or behavior"
probe_task_key: "one allowed optimize target"
experiment_spec: "existing bounded Worker experiment"
```

Do not require duplicate prose when the state card already contains the same
information. The implementation should expose a relative path and a compact
terminal summary rather than copy the entire card into every record.

## Generic comparison arm

The generic full-harness arm is a strong matched baseline:

- same Quant-H0;
- same public tasks and authorized evidence;
- same answer-rich Evolver / blind Worker policy;
- same Evolver and Worker routes and reasoning settings;
- same full mutation surface;
- same maximum candidate, Worker, verifier, token, cost, and wall-time budget;
- same official evaluator and sealed split; and
- same opportunity to refine, reuse, revert, or abstain.

The generic arm uses layered trajectory diagnosis, generic causal hypotheses,
and task-delta prediction. It does not receive the operational state card,
state-conditioned retrieval/routing, or reconciliation-relation helper. It is
still free to discover equivalent components from the raw authorized evidence.

The intended paper result may be official-performance non-inferiority plus
search-efficiency improvement. Do not weaken the baseline through shorter
Worker budgets, missing diagnostics, restricted components, weaker models, or
different answer access.

## Mechanism-localization canary

Before returning to Main-0, run one bounded matched canary on two distinct
quantitative mechanisms:

1. an information/effective-state/derived-state task family; and
2. an estimation/calibration/economic-reconciliation task family.

For each family, run one generic proposal arm and one quant-state-guided arm
from the same Quant-H0 and corrected evidence. Allow one candidate initially:

```text
2 task families x 2 proposal arms x 1 initial candidate
= at most 4 initial candidates
```

Only an official target gain schedules an independent repeat. Only a repeated
gain schedules protection or matched transfer. Retain all `ACT`, `ABSTAIN`,
inactive, negative, neutral, and positive outcomes.

The canary is positive for the search mechanism when quant-state conditioning
produces at least one of the following without worse official target behavior:

- fewer candidates or Worker/verifier calls to an activated component;
- a predeclared relation correction that the generic arm misses;
- fewer inactive or mislocalized candidates;
- a narrower component with less protection regression; or
- a faster calibrated `ABSTAIN` when the evidence cannot discriminate.

A finance-shaped state report without a changed retrieval, routing, probe, or
verdict is neutral. One target gain without repeat is not stable. A protection
task that does not activate the component is non-regression evidence only.

## Metrics

Record per arm and task family:

- proposed and admitted candidate count;
- Evolver, Worker, and verifier calls;
- tokens, cost, wall time, and Worker turns;
- component activation;
- selected relation and observed status change;
- official property and binary outcomes;
- candidate-to-activation yield;
- activation-to-state-correction yield;
- state-correction-to-official-gain yield;
- repeat and protection outcomes;
- protection regression or evidence-grounded skip;
- number of repeated previously negative mutations; and
- final promote, rollback, archive, or abstain decision.

## Implementation order

1. Add a compact state-card builder and validator using existing public and
   Evolver-authorized evidence.
2. Add one guarded Evolver tool to inspect/materialize the state card; do not
   create a separate Reviewer agent in the first version.
3. Extend evidence retrieval with state/relation/component coordinates while
   preserving current exact-parent access.
4. Extend the system prompt and terminal decision so `ACT` references the
   state card, relation, routing choice, and discriminating observation.
5. Project the selected component and activation instruction into the bounded
   Worker experiment without projecting answers or private diagnostics.
6. Build an intervention verdict from activation, relation observation,
   official outcome, repeat, and protection evidence.
7. Add focused tests for the happy path and observed failures: missing state
   support, self-confirming relation, component not activated, predicted state
   unchanged, and protection regression.
8. Run a no-model fixture through the complete path.
9. Run the four-candidate mechanism-localization canary.
10. If the canary is positive, simplify and implement the pre-main controller,
    then return to the Main-0/Main-1 runway.

## Pre-main gate

Do not return to broad Main-0 merely because the state-card schema validates.
Return when all of the following are true:

- the state card changes a real Evolver search decision or calibrated
  insufficiency;
- an admitted candidate references one supported relation and reachable
  component locus;
- a fresh Worker is given an explicit but answer-free activation instruction;
- activation, state correction, and official outcome are recorded separately;
- the bounded matched canary has a retained interpretation and cost record;
- generic and quant-state arms use matched evidence and budgets; and
- the method story and claim boundary are frozen before the scale rehearsal.

After that gate, reuse the existing candidate-scale runway but reduce lineage
terminology to infrastructure. The controller should maintain one incumbent
plus a searchable archive, automatically execute target, repeat, protection,
promotion/rollback, resume, and freeze, and use a small Main-0 before any
Main-1 campaign.
