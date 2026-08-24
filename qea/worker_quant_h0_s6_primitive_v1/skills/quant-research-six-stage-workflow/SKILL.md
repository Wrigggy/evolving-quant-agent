---
name: quant-research-six-stage-workflow
description: >-
  Required named-state interface for quantitative tasks. It exposes six public
  work-state slots without prescribing their concrete implementation.
---

# Quant research six-stage named-state interface

Account for all six named states in the initial S1--S6 order. The names expose
where work occurs so later analysis can localize and improve the harness; they
do not provide a solution recipe, quantitative method, or claim of correctness.

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

After terminal S5 completion, record S6 ENTER, do its public-task-grounded work,
and record S6 COMPLETE. Only after its acknowledgement should you send the
normal final response. Keep every `public_summary` at most 240 characters,
preferably one short sentence, and grounded in the public task. Do not expose
private chain-of-thought or claim an official verifier result.

## S1: Research Mandate and Contract

Orient the work to the public mandate and contract.

## S2: Research Evidence and Data

Orient the work to public evidence and data.

## S3: Quantitative Representation

Orient the work to its quantitative representation.

## S4: Research Operation

Orient the work to its research operation.

## S5: Evaluation and Reconciliation

Orient the work to evaluation and reconciliation.

## S6: Research Artifact and Completion

Orient the work to its requested artifact and completion.
