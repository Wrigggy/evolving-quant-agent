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

## Marker protocol

Marker channel is part of the protocol. Emit every `[QSTATE ...]` marker as direct assistant-role plain text on its own line. Never place a marker inside a `ToolUse` payload, a `run_shell_command` command or description, an `echo`/`printf` command, tool stdout/stderr, or any other tool call or tool result. Tool-channel text does not count as a marker. Do not defer missed earlier markers to a final-only retrospective backfill; emit each direct assistant marker at the transition it records.

For every applicable state, emit an exact `ENTER` marker before doing that
state's work and an exact `COMPLETE` marker before entering the next state. Put
each marker on its own line. A prose heading, plan item, or retrospective
summary does not count as a marker.

```text
[QSTATE S1 ENTER]
[QSTATE S1 COMPLETE] public_summary=...
[QSTATE S2 ENTER]
[QSTATE S2 COMPLETE] public_summary=...
```

If a state genuinely does not apply, emit exactly
`[QSTATE S4 NOT_APPLICABLE] reason=...` instead of both ENTER and COMPLETE. Do
not silently omit a state. S5 may revisit S2, S3, or S4 only with the exact
grammar `[QSTATE S5 REVISIT S3] reason=...`; then enter and complete the target
state again before returning to S5. Do not write `[QSTATE S3 REVISIT]` or any
other marker form.

After a terminal S5 COMPLETE or NOT_APPLICABLE marker, close the run with both
of these exact lines in this order:

```text
[QSTATE S6 ENTER]
[QSTATE S6 COMPLETE] public_summary=...
```

Do not backfill an earlier state's marker after beginning a later state. Before
entering S6, audit the emitted S1--S5 marker lines: each state must have either
ENTER followed by COMPLETE or one NOT_APPLICABLE marker, and their first
accounting must be ordered S1 through S5. If an earlier transition was omitted,
state that public protocol issue in the S6 summary instead of manufacturing a
retroactive event. Then emit S6 ENTER and S6 COMPLETE before the final response.
Keep summaries short and public; do not expose private chain-of-thought.

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
