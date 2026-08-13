# Quant/finance failure-map middleware for Evolver search

Date: 2026-08-13

Status: implemented and locally tested; not yet used in a paid Evolver or
QuantCodeEval candidate run

## Decision

The next QuantCodeEval search will first enhance the Evolver with a
finance-specific diagnostic middleware. The middleware does not choose a
Worker fix. It exposes a compact two-axis failure map and requires a legal ACT
to state:

1. the earliest observable breakdown stage;
2. the finance-semantic failure class;
3. the concrete public/process symptoms;
4. at least one adjacent class considered and why it fits less well; and
5. the component state the intervention should change or preserve.

The full harness mutation surface remains open. Component priors are advisory,
and the Evolver may reject A and B, propose another mechanism, or ABSTAIN.

## Why two axes

The earlier QuantCodeEval contract used five broad classes. They were useful as
prompt-mutation labels and rough component routing, but they collapsed two
different questions:

- Did the Worker fail while retrieving, understanding, retaining, implementing,
  or delivering the requirement?
- What finance behavior was wrong?

That collapse is especially costly for component localization. A wrong formula
caused by initial misunderstanding suggests an independent definition probe or
task-family skill. The same final formula error caused by later replacement of
a correct decision suggests memory, checkpoint, or finalization state. A final
property failure alone does not distinguish these interventions.

The new first axis follows the earliest-breakdown analysis in the QuantCodeEval
paper:

- `source_retrieval`;
- `requirement_comprehension`;
- `specification_preservation`;
- `implementation_realization`;
- `execution_completion`; and
- `unable_to_decide` for calibrated abstention.

The second axis follows the public strategy pipeline and measured failure
patterns from QuantCodeEval, with QFBench's dirty-data, stateful workflow, and
verifiable-delivery surface added:

- `interface_delivery`;
- `data_universe_preprocessing`;
- `temporal_causality`;
- `formula_parameterization`;
- `signal_direction`;
- `portfolio_accounting`;
- `runtime_completion`;
- `isolated_task_specific`; and
- `unknown`.

This is a search aid, not a claim that the classes are mutually exclusive true
causes. The Evolver must choose the earliest supported stage and compare the
selected semantic class with an adjacent alternative. If available evidence
cannot do that, ABSTAIN remains correct.

## Relationship to A and B

Direction A, an independent public-definition fixture, is now a mechanism
pattern rather than a top-level error class. It is most plausible when the
breakdown is requirement comprehension or implementation realization and the
semantic class is formula/parameterization, temporal causality, or signal
direction.

Direction B, decision-state retention, is specifically tied to
`specification_preservation`. It should be selected only when the trace shows a
correct requirement or supported intermediate implementation being replaced,
forgotten, or omitted from final assembly. Without that transition evidence,
B remains a weaker hypothesis.

The third open mechanism family is `failure_specialized_component`: if a
recurring finance error reveals missing reusable state or an executable
operation, the Evolver may design a tool, validator, memory, middleware, skill,
or routing component around that state. This keeps the search broader than A
and B without returning to unconstrained generic brainstorming.

## Implementation

- `qea/evolve_agent_full/quant_failure_map.json` contains the full map and
  optional mechanism patterns.
- `QuantFailureMapMiddleware` injects a compact map only for
  `quant_property_v2` runs.
- QuantCodeEval v2 evidence exposes the full map under
  `guidance/quant_failure_map.json`.
- The decision schema and guarded ACT path require the two-axis localization
  fields when the new contract flag is active.
- Existing historical PGBS prompt-mutation classes remain unchanged so prior
  experiments retain their original meaning.

The implementation adds no new digest, content-addressed identity, or
exhaustive defensive machinery. Tests cover the quant-only middleware path,
map exposure, valid ACT, and the observed risk of selecting a component without
distinguishing the failure stage or a neighboring finance class.

## Next experiment

Run one autonomous, variable-length Evolver activation from the same diagnostic
parent and accumulated answer-free history used by r3. Do not prescribe A, B,
or a component. Inspect whether the decision now localizes:

- T12 to a supported stage and semantic class;
- a competing adjacent explanation;
- the component state that needs to change; and
- a local component smoke whose observation tests that state.

If a candidate is admitted, evaluate T12 first and T19 as protection. Repeat an
apparent T12 solve immediately before promotion or panel expansion. If the
Evolver cannot distinguish the stage/class pair, accept ABSTAIN and use the
missing evidence it names to design the next evidence view.

## Public sources used

- QuantCodeEval paper and public abstract:
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6801618>
- QFBench public repository:
  <https://github.com/QF-Bench/QuantitativeFinance-Bench>
- Agentic Harness Engineering:
  <https://arxiv.org/abs/2604.25850>

QuantCodeEval supplies the finance reproduction stages and its reported
temporal, definition, and trading-direction errors. QFBench motivates explicit
data, workflow-state, runtime, and deliverable classes. AHE motivates keeping
component, experience, and decision observability aligned rather than treating
a failure label as a fixed component prescription.
