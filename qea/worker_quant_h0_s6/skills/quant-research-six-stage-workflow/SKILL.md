---
name: quant-research-six-stage-workflow
description: >-
  Required for every quantitative task. It exposes a concise six-stage research
  workflow for mandate, evidence, representation, operation, evaluation, and
  artifact completion while keeping every rule grounded in public information.
---

# Quant research six-stage workflow

Use all six stages for every task. The stages make the research process
observable and comparable; they do not prescribe a task answer, asset class,
formula, or strategy. Keep each marker summary short and factual. Do not reveal
private chain-of-thought.

The current task can require exact task-specific behavior when the public
contract states it. Do not convert a hidden checker result, remembered score,
reference answer, or unstated expected value into a workflow rule. When public
evidence is ambiguous, record the ambiguity instead of reverse-engineering an
evaluator.

## Marker protocol

Use one marker per line with an optional concise public summary after it:

```text
[QSTATE S1 ENTER]
[QSTATE S1 COMPLETE] deliverables=...; public_constraints=...
[QSTATE S5 REVISIT S3] reason=public unit relation needs correction
[QSTATE S6 COMPLETE] artifacts=...; unresolved_caveats=...
```

For a genuinely inapplicable stage, use:

```text
[QSTATE S4 NOT_APPLICABLE] reason=the public task requests inspection only
```

Do not silently skip a stage. `NOT_APPLICABLE` needs a public, task-grounded
reason. S5 may revisit S2, S3, or S4. After a revisit, emit a new `ENTER` and
`COMPLETE` pair for the revisited stage. Enter S6 only after the relevant S5
checks have run.

## S1: Research Mandate and Contract

Emit `[QSTATE S1 ENTER]`, then identify:

- requested deliverables and output locations;
- public methods, interfaces, schemas, units, signs, dates, and rounding rules;
- completion conditions that can be checked from the public task.

Emit `[QSTATE S1 COMPLETE]` with a compact contract summary. Public task
requirements are authoritative even when they are task-specific.

## S2: Research Evidence and Data

Emit `[QSTATE S2 ENTER]`, then inspect the supplied public inputs once:

- files, columns, shapes, date ranges, identifiers, and units;
- missingness, duplicates, ordering, and information-time constraints;
- available dependencies and any task-relevant runtime limitation.

Emit `[QSTATE S2 COMPLETE]` with the usable evidence and unresolved public-data
limitations. Do not search for tests, solutions, reference outputs, credentials,
or hidden evaluator artifacts.

## S3: Quantitative Representation

Emit `[QSTATE S3 ENTER]`, then state the task-conditioned representation:

- quantitative objects and their units;
- assumptions and parameterization supported by the public task;
- public identities, formulas, mappings, windows, or accounting relations;
- competing conventions when the public sources do not uniquely select one.

Emit `[QSTATE S3 COMPLETE]` with the selected public basis and any ambiguity.
Do not turn a plausible implementation into its own oracle.

## S4: Research Operation

Emit `[QSTATE S4 ENTER]`, then perform the task-appropriate operation: data
construction, estimation, calibration, pricing, risk analysis, backtesting,
portfolio construction, execution analysis, or another public task operation.
Write the smallest structurally valid deliverables early and keep the
implementation deterministic where the task permits.

Emit `[QSTATE S4 COMPLETE]` with the operation performed and draft artifact
paths. The implementation may be task-conditioned; the workflow rule must
remain public-grounded and reusable.

## S5: Evaluation and Reconciliation

Emit `[QSTATE S5 ENTER]`, then independently inspect the draft using public
relations:

- parseability, schema, shapes, keys, units, finite values, and rounding;
- identities, constraints, and reconciliation rules stated by the task;
- a small independently computed example or perturbation when it distinguishes
  plausible definitions;
- consistency between leaf artifacts, summaries, and stated assumptions.

If a check fails because evidence, representation, or operation was wrong,
emit `[QSTATE S5 REVISIT S2]`, `[QSTATE S5 REVISIT S3]`, or
`[QSTATE S5 REVISIT S4]`, repair that stage, and return to S5. Emit
`[QSTATE S5 COMPLETE]` with checks run, findings, and remaining public
uncertainty. Do not describe a self-check as an official verifier result.

## S6: Research Artifact and Completion

Emit `[QSTATE S6 ENTER]` only after S5. Re-open the final deliverables and
confirm they exist at the requested paths and satisfy the public completion
contract. Leave only the requested deliverables unless the task explicitly asks
for supporting files.

Emit `[QSTATE S6 COMPLETE]` with final artifact paths and unresolved caveats,
then finish. Do not start a new exploratory loop after the public completion
checks pass.
