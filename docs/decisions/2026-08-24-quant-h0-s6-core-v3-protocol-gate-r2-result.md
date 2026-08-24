# Quant-H0-S6-Core-v3 R2 protocol gate retained negative result

> Date: 2026-08-24 · Experiment: `qf-quant-h0-s6-core-v3-protocol-gate-20260824-r2` · Status: retained negative; breadth no-go

## 1. Process and Results

### Goal

The protocol gate failed: Core-v3 produced three valid official observations,
but it did not produce three traces whose direct assistant markers occurred at
the S1--S6 transitions they claimed to record. The experiment tested a narrow
repair for Core-v2's shell-echo channel mismatch; official scores were retained
but could not authorize breadth.

### Method and process

The frozen plan at
`data/breadth/QF_QUANT_H0_S6_CORE_V3_BREADTH_PLAN.json` ran one fresh Core-v3
Worker sequentially on each of the three disclosed development tasks. The
human-readable deploy identity was
`qf-quant-h0-s6-core-v3-breadth-20260824-r2`; every cell used the same pinned
QFBench base85 runtime snapshot, `deepseek-v4-flash-main0` route,
`deepseek/deepseek-v4-flash-0731` model, shell tool, verifier, and single-Worker,
single-verifier concurrency. No Evolver, candidate, Reviewer, protection task,
sealed task, or breadth Worker ran.

The trusted parser accepted exact QSTATE lines in assistant-role messages and
checked S1--S6 grammar and event order. The manual transition audit added the
frozen semantic requirement that ENTER precede the corresponding stage work
and that earlier stages not be manufactured in a final-only backfill. It also
examined whether a marker-bearing assistant message contained a ToolUse, since
the current agent loop treats an assistant-only message as final.

### Data and results

The headline result is a split diagnostic: runner syntax passed on 2/3 cells,
while manual transition timing passed on 0/3. All three official observations
were valid, but the gate failed and breadth dispatch remained zero.

| Task | Official | Parser complete | Manual timing complete | Turns / tools / errors / artifacts | Completed / total request rows | Tokens / cost |
|---|---:|---:|---:|---:|---:|---:|
| `swap-curve-bootstrap-ois` | 19/19, reward 1 | yes | no: all stages backfilled in final | 11 / 13 / 3 / 5 | 11 / 11 | 253,447 / $0.018685124 |
| `13f-amendment-aware-crowding` | 0/11, reward 0 | no | no: marker-only turn ended Worker | 2 / 3 / 0 / 0 | 2 / 2 | 6,945 / $0.001030628 |
| `fx-forward-cross-rate` | 37/37, reward 1 | yes | no: initial evidence preceded S1/S2 markers | 17 / 18 / 2 / 1 | 17 / 21 | 606,551 / $0.032449964 |

Run-level accounting reconciled 30 completed logical requests against 34
provider audit rows. Four FX rows were rate-limited and not accepted; there
were no other nonaccepted or unreconciled requests. The completed calls used
808,773 input tokens, 58,170 output tokens, 866,943 total tokens, and
$0.052165716 over 9 minutes 58 seconds.

All 12 lifecycle records were cleaned by exact ID. No related process,
container, network, volume, run-specific namespace, main unit, health timer,
or breadth directory remained at the final audit. The zero-byte coordinator
lock had no owner.

### Case studies

**Swap and holdings expose the runtime bifurcation.** Swap's only
QSTATE-bearing message was the final assistant response: it had no ToolUse and
contained all 12 S1--S6 events after the substantive work. The parser reported
complete syntax, but the S6 summary itself disclosed that markers were
consolidated at the terminal audit. Holdings instead emitted a direct
assistant-only `[QSTATE S1 ENTER]` after its initial inspection. Because that
message contained no ToolUse, the agent loop treated it as final. The Worker
ended after two turns with no artifact, leaving S1 unclosed and S2--S6 absent.

**FX demonstrates the viable continuation pattern and its remaining limit.**
Four marker-bearing assistant messages also contained the next ToolUse, so the
runtime continued; the assistant-only S6 COMPLETE message then ended the run
normally. This yielded 37/37 and a syntax-complete trace. However, the Worker
had already listed and read the spot, deposit, portfolio, history, and parameter
inputs before its first S1 ENTER and S2 ENTER. The later boundaries are useful
mechanism evidence, but the complete trace is not transition-timed from S1.

## 2. Analysis

Core-v3 fixed the shell channel but not the agent-loop contract. Direct
assistant marker text can be parsed, yet a nonterminal assistant-only marker is
indistinguishable from a final response to the current runtime. The Worker
therefore found two workarounds: postpone every marker until the final response,
as in swap, or combine markers with a continuing ToolUse, as in FX. The first
violates the no-backfill rule; the second can work only when the marker is
emitted before the stage's substantive tool operation.

The parser's 2/3 result is real but insufficient. It proves exact direct-channel
grammar and order, not temporal correspondence between labels and work. Treating
it as a gate pass would turn a retrospective narrative into an indexed process
history. The manual 0/3 timing result is therefore the construct-level outcome,
while the parser rate remains a separately reported implementation diagnostic.

The official vector `[19/19, 0/11, 37/37]` is also real. Holdings' zero is an
effect of the Core-v3/runtime interaction rather than evidence that its quant
method was attempted and failed. The three values are retained, but this
Core-v3-only purposive gate has no matched Legacy arm or repetition and supports
no stable gain claim. Zero breadth dispatch is evidence that the prerequisite
gate contained the failure, not evidence of Worker quality.

## 3. Problems and Open Questions

- **Prompt-only continuation is possible but brittle.** Requiring every
  nonterminal marker to share an assistant message with the next ToolUse fits
  the current loop and keeps the shell tool unchanged, but model compliance and
  stage boundaries may still vary across tasks.
- **Runtime continuation would be cleaner but changes infrastructure.** A
  middleware could recognize a marker-only nonterminal response and request the
  next Worker turn. That avoids forcing an artificial no-op tool call, but it
  creates a new runtime treatment and must define a safe terminal condition.
- **Temporal auditing needs an operational definition.** A future trusted audit
  must distinguish allowed setup such as skill loading from substantive stage
  work, detect final-only batch backfill, and flag evidence reads before S2
  ENTER without trying to judge private reasoning or quantitative correctness.
- **Parser completeness remains distinct from correctness.** Even a fully
  transition-timed trace would not prove that evidence, representation,
  operation, or evaluation was adequate.

## 4. Next Plan

1. Retain R2 as the terminal Core-v3 gate record and keep every Core-v3 breadth
   run undispatched.
2. Choose one new treatment identity: either a prompt-level marker-plus-ToolUse
   convention or a bounded runtime continuation rule for nonterminal markers.
   Do not add task-specific quant methods or expand the task panel from scores.
3. Add no-model fixtures for all three observed modes: final-only batch
   backfill must fail, marker-only premature termination must continue or fail
   explicitly, and transition marker plus substantive ToolUse must pass only in
   the correct order.
4. Freeze and run a fresh three-cell gate. Report parser syntax and manual or
   trusted transition timing separately; require all three valid cells to pass
   both before creating a separately frozen breadth authorization.
5. Keep Candidate Information-Set Review, the answer-free Worker boundary,
   matched gain, repetition, protection, and sealed evaluation as separate
   blockers before the QRS main experiment.

The complete local mirror is retained at
`results/bc-mirror/qf-quant-h0-s6-core-v3-protocol-gate-20260824-r2/`. The
compact result is
`data/breadth/QF_QUANT_H0_S6_CORE_V3_PROTOCOL_GATE_R2_RESULT.json`.
