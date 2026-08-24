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

## Structured telemetry protocol

Record every transition with the real structured `record_quant_state` tool.
Make each recorder call alone in its assistant turn and wait for the tool
acknowledgement before doing the recorded state work. Never combine a recorder
call with `run_shell_command` or another tool. Text in assistant prose, a tool
payload, shell `echo`/`printf`, stdout/stderr, or the final response is not a
state event. Do not backfill an omitted transition after beginning a later
state.

After loading this skill, the first task-directed tool call must be:

```text
record_quant_state(stage="S1", action="ENTER", public_summary="...")
```

For each applicable state, call `ENTER` before its work and `COMPLETE` before
entering the next state. If a state genuinely does not apply, use one
`NOT_APPLICABLE` call instead. S6 cannot be not applicable.

S5 may revisit S2, S3, or S4. While S5 is active, call `REVISIT` with the target
stage in `stage`, then call ENTER and COMPLETE for that target before completing
S5. No other revisit target is valid.

After terminal S5 completion, record S6 ENTER, audit the requested public
deliverables, and record S6 COMPLETE. Only after its acknowledgement should you
send the normal final response. Keep every `public_summary` concise and grounded
in the public task; do not expose private chain-of-thought or claim an official
verifier result.

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
