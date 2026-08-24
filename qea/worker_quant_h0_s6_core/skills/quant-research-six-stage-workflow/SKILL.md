---
name: quant-research-six-stage-workflow
description: >-
  Required state interface for quantitative tasks. It labels mandate, evidence,
  representation, operation, evaluation, and artifact completion without
  prescribing how any stage must be implemented.
---

# Quant research six-stage state interface

Account for all six states in the initial S1--S6 order. The states expose where
work occurs so later analysis can localize and improve the harness; they are not
a solution recipe, checklist, formula, strategy, or claim of correctness.

Emit one concise marker per line:

```text
[QSTATE S1 ENTER]
[QSTATE S1 COMPLETE] public_summary=...
[QSTATE S5 REVISIT S3] reason=...
[QSTATE S6 COMPLETE] public_summary=...
```

If a state genuinely does not apply, emit
`[QSTATE S4 NOT_APPLICABLE] reason=...` using a reason grounded in the public
task. Do not silently omit a state. S5 may revisit S2, S3, or S4; re-enter and
complete the revisited state before returning to S5. Enter S6 only after a
terminal S5 marker. Keep summaries short and public; do not expose private
chain-of-thought.

## S1: Research Mandate and Contract

State what the public task asks for and what must be delivered.

## S2: Research Evidence and Data

Identify and inspect the public evidence or data needed for the task.

## S3: Quantitative Representation

State the quantitative objects, assumptions, and relations used to represent
the task, including unresolved public ambiguity.

## S4: Research Operation

Perform the task-appropriate quantitative research operation.

## S5: Evaluation and Reconciliation

Evaluate the work against the public task and revisit S2--S4 when necessary.
Do not describe a self-check as an official verifier result.

## S6: Research Artifact and Completion

Confirm the requested deliverables and complete the task with any unresolved
public caveat stated plainly.
