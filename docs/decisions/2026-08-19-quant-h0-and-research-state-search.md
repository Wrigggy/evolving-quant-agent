# Quant-H0 and Research-State-Guided Search

Status: accepted design and local implementation, 2026-08-19. This record
refines the invariant-guided route without replacing its measured experiment
history. No benchmark run is reported here.

## Decision

Create an independent `Quant-H0` rather than modifying the historical
shell-only H0. Quant-H0 contains only the Quant Research Worker Agent identity,
the names and short explanations of six Research States, one shell tool, and
basic task execution. It does not include additional finance-discipline hints,
prior history, diagnosis, component selection, or task-specific content.

The Research States are a general task representation rather than the six
fixed stages of a trading-strategy pipeline:

1. Research Mandate & Contract;
2. Research Evidence & Data;
3. Quantitative Representation;
4. Research Operation;
5. Evaluation & Reconciliation; and
6. Research Artifact & Completion.

Preserve all historical results under the former shell-only H0 identity. Use
Quant-H0 as the common seed for future matched AHE-on-quant and QEA campaigns.
Do not describe Quant-H0 as an official benchmark-native baseline.

## Search-mechanism change

For the existing `quant_property_v2` protocol, Research State becomes the
primary search representation. An `ACT` under a Research-State-enabled contract
must record one `research_state_transition`:

- the applicable `state_id`;
- the task-conditioned expected state;
- the state observed in the Worker trajectory or artifact;
- the target state predicted after intervention; and
- a concrete observable showing whether the transition occurred.

The existing finance failure map remains optional diagnostic vocabulary.
Research State does not prescribe a harness role. The Evolver still compares
competing mechanisms and chooses from the complete prompt, tool, memory,
middleware, validator, routing, skill, and configuration surface.

Task-conditioned quantitative invariants remain part of the route, but their
role is now clearer: an invariant is one possible executable observation of a
predicted Research State transition. Component activation, state transition,
official benchmark outcome, and repeat/protection/transfer remain separate
evidence levels.

## Source grounding and claim boundary

QuantCodeEval directly motivates stage-aware strategy integrity and
cross-stage property checking. QFBench motivates a broader representation
covering heterogeneous quant operations, multi-step state construction,
financial invariants, and complete artifacts. Our six Research States are an
outer abstraction across those task families, not a claim that either
benchmark defines the same six-state method.

The outer harness-evolution loop, accumulated trajectories, and candidate
adaptation are attributed to AHE and related harness-optimization work. The
proposed relative contribution is Research-State-guided component search and
state-transition verification. It remains unmeasured until compared with a
matched AHE-on-quant baseline.

## Adversarial AHE-author-style review

A story-only reviewer was given only this project's current story and the AHE
paper. Its verdict was that the outer loop and most infrastructure remain AHE-
overlapping. The strongest potentially real distinction is the mediator chain
`component activation -> predicted Research State transition -> official
outcome`. Research State names, Quant Research Trajectory terminology, and
expected-versus-observed prose are not sufficient by themselves.

The review identified one concrete implementation gap. The current change
makes `research_state_transition` a binding prerequisite for a proposal-side
`ACT`, but it does not yet use the fresh Worker's observed transition as an
independent candidate retain/rollback signal. That outcome-side rule is the
next method requirement. The matched baseline must give AHE-on-quant the same
Quant-H0 so the six-state seed is not a confound. An essential ablation keeps
the labels but removes executable transition admission; another replaces the
state contract with AHE-style generic root-cause evidence under the same
budget.

## Outcome-side transition control implemented

The variable-length search now has a distinct `research_state_promoted`
selection. A candidate receives it only when the predeclared component is
observed as activated, the predicted Research State transition is supported,
the official panel was evaluated, and no official incumbent task regresses.
This selection advances only the diagnostic search parent. The official
incumbent still changes only after a binary-reward Pareto improvement.

Inactive, unsupported, or unknown transition results are retained as history
but do not advance the search parent. An official improvement may still advance
the official incumbent when its proposed Research State mechanism is
unresolved; that run is performance evidence with unresolved attribution. This
is a locally tested control-flow mechanism, not a live benchmark result.

## Proposed Evolver-callable Quant Research Reviewer

Record a future callable capability, tentatively
`investigate_research_state`, rather than making the Reviewer an always-on
coordinator stage. The Evolver may invoke it when the current runtime evidence
does not clearly locate a Research State mismatch.

The Reviewer receives only the evidence already authorized for the Evolver:
the public task contract, selected Worker trajectory slices, Worker artifact,
component-use observations, accumulated candidate history, and allowed runtime
diagnostics. It investigates where the expected and observed research states
diverge and returns:

- the candidate `state_id`, expected state, and observed state;
- exact runtime-evidence references supporting the mismatch;
- at least two plausible explanations when the evidence permits;
- an observation that could discriminate those explanations; or
- `insufficient_evidence` when the state cannot be located.

The Reviewer does not edit the harness, select the final component, submit
`ACT`, or promote a candidate. Those decisions remain with the Evolver and the
outer transition-verdict rule. This callable design lets the Evolver spend a
specialized investigation only when useful and makes Reviewer use itself part
of the observable search trajectory. It is recorded as proposed and is not yet
implemented or measured.
