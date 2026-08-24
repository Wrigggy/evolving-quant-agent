# Primitive-H0 protocol canary retained positive result

> Date: 2026-08-24 · Experiment: `qf-primitive-h0-protocol-canary-20260824-r1` · Status: protocol gate pass; main still no-go

## 1. Process and Results

### Goal and setup

The exact Primitive-H0 passed its live structured-protocol prerequisite. This
was a three-task engineering gate, not a baseline-capability or QRS-effect
experiment. It used the excluded construct tasks
`13f-amendment-aware-crowding`, `fx-forward-cross-rate`, and
`swap-curve-bootstrap-ois`, one Worker and one verifier at a time, the pinned
`deepseek-v4-flash-main0` route, and no Evolver, Reviewer, candidate, or sealed
task.

The deployed source was the first repository commit containing the frozen plan,
Primitive Worker, schema-v2 structured parser, and component-pilot runner
(`46e4a2d`). The exact Worker source is:

- [`systemprompt.md`](../../qea/worker_quant_h0_s6_primitive_v1/systemprompt.md);
- [`SKILL.md`](../../qea/worker_quant_h0_s6_primitive_v1/skills/quant-research-six-stage-workflow/SKILL.md);
- [`agent.yaml`](../../qea/worker_quant_h0_s6_primitive_v1/agent.yaml); and
- [`record_quant_state.tool.yaml`](../../qea/worker_quant_h0_s6_primitive_v1/tool_descriptions/record_quant_state.tool.yaml).

The frozen protocol required a valid Worker/verifier terminal plus genuine
schema-v2 structured recorder calls: twelve successful events, S1--S6 initial
order, one ENTER and COMPLETE per stage, no missing stage, no issue, no
malformed call, and one terminal S6 COMPLETE before the final response.

### Measured results

All three cells passed that rule.

| Task | Official, descriptive only | Turns / tools / errors / artifacts | Worker seconds | Structured protocol |
|---|---:|---:|---:|---:|
| Holdings | 40/51, reward 0 | 38 / 38 / 1 / 8 | 561.461 | PASS: 12 events, 0 issue, 0 malformed |
| FX forward | 36/37, reward 0 | 27 / 27 / 5 / 1 | 367.092 | PASS: 12 events, 0 issue, 0 malformed |
| Swap curve | 19/19, reward 1 | 28 / 28 / 2 / 5 | 220.441 | PASS: 12 events, 0 issue, 0 malformed |

The run reconciled 93/93 completed requests, 3,290,289 input tokens,
119,965 output tokens, 3,410,254 total tokens, and $0.117787104. There were
zero rate-limited retries, other nonaccepted requests, unreconciled requests,
or unreconciled attempts. Wall time was 19 minutes 53 seconds.

All 12 lifecycle records were cleaned. The service exited successfully with
zero restarts; the health timer was stopped after recording `complete`; final
process, container, and network residue was zero. The additive no-delete local
mirror is retained at
`results/bc-mirror/qf-primitive-h0-protocol-canary-20260824-r1/`.

## 2. Analysis

This result closes the specific interface failure seen in earlier Core variants.
The Worker no longer emits shell-echo markers, final-only marker batches, or
overlong recorder payloads. Each cell contains a real isolated structured call
for every stage transition, and task-directed work occurs between the relevant
acknowledged transitions.

The result also preserves the intended ambiguity. Primitive-H0 supplies stage
names and telemetry mechanics but no holdings formula, FX rounding rule, curve
method, S5 revisit prescription, or S6 deliverable checklist. The task summaries
show that the Worker used the slots to organize real work, but the trusted gate
does not treat a plausible summary as proof that the quantitative work was
correct.

The official vector is therefore secondary. It shows that all three attempts
were ordinary valid benchmark executions; it does not measure Primitive-H0
against another harness, establish stable task capability, or determine whether
the substrate should be weakened. Protocol completion authorizes only the next
control-plane canary.

## 3. Problems and Remaining Boundary

- Three excluded construct tasks establish executability, not broad protocol
  compliance over the 45-task development bank.
- The recorder still imposes sequencing and token overhead, so Primitive-H0 is
  a disclosed human-authored initialization rather than a no-treatment agent.
- No changed candidate was reviewed or run. The positive Candidate Review
  path, exact reviewed snapshot, mutation boundary, matched panel runner,
  answer-free handoff, accounting, and resume remain live-unvalidated.
- The task scores are single stochastic observations and cannot be used to
  choose, retune, weaken, or replace Primitive-H0 inside the scheduler.

## 4. Next Plan

1. Keep this run and its Primitive identity fixed; do not rerun the protocol
   gate for a different score.
2. Materialize the separately frozen four-task mini trajectory bank and one
   authorized workflow-global panel.
3. Require a real overall Candidate Information-Set Review PASS with coverage
   PASS, then run only the exact reviewed candidate against the retained parent
   over two reversed-order matched repetitions.
4. Audit the QRS mutation boundary, answer-free history handoff, complete cost,
   cleanup, and zero-work resume.
5. Keep the full 45-task main blocked unless the mini exercises that complete
   PASS-to-blind-Worker path. A legal ABSTAIN or Review non-PASS remains useful
   negative evidence but is not enough to authorize main.

The compact retained record is
`data/breadth/QF_PRIMITIVE_H0_PROTOCOL_CANARY_RESULT.json`.
