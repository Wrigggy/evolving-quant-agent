# Quant-H0-S6-Core-v2 protocol gate retained negative result

> Date: 2026-08-24 · Experiment: `qf-quant-h0-s6-core-v2-protocol-gate-20260824-r1` · Status: retained negative; breadth no-go

## 1. Process and Results

### Goal

The gate failed: Quant-H0-S6-Core-v2 did not produce three valid Worker/verifier
observations with complete, ordered, well-formed S1--S6 traces. This gate tested
whether the repaired Worker exposed a reliably indexable six-state trajectory;
official score was recorded but could not authorize the breadth phase.

### Method and process

The frozen plan at
`data/breadth/QF_QUANT_H0_S6_CORE_V2_BREADTH_PLAN.json` dispatched one fresh
Core-v2 Worker per task, sequentially, on the three disclosed development tasks
from the antecedent construct calibration. Every Worker used source revision
`14a9696e8ea8dbbb8d14189653a76753c7d209d8`, QFBench revision
`024921eb507fcc0c4ffe3e0a96802724be1ae84a`,
route `deepseek-v4-flash-main0`, model
`deepseek/deepseek-v4-flash-0731`, Worker concurrency one, and verifier
concurrency one. No Evolver, Reviewer, candidate mutation, protection task, or
sealed task ran.

The trusted parser accepted only an exact QSTATE marker on its own line in an
`assistant`-role trace message. Marker text embedded in a tool call or returned
as `tool`-role stdout was deliberately not an assistant state transition. The
frozen proceed condition required all three executions to be valid and all
three parsed protocols to be complete. The runner completed the three-cell gate
from 14:32:25 to 14:50:23 SGT and dispatched no breadth run.

### Data and results

The headline result is one protocol-complete cell out of three, with one
additional valid official observation and one invalid Worker execution.

| Task | Valid official observation | Official record | Strict S1--S6 parser | Turns / tools / errors | Requests / tokens / cost |
|---|---:|---:|---:|---:|---:|
| `swap-curve-bootstrap-ois` | yes | 19/19, reward 1 | complete; no missing, malformed, or protocol issue | 13 / 16 / 5 | 13 / 379,863 / $0.021322788 |
| `13f-amendment-aware-crowding` | yes | 42/51, reward 0 | failed; all S1--S6 missing; `first_stage_entries_out_of_order_or_missing` | 26 / 37 / 4 | 26 / 1,242,233 / $0.045299788 |
| `fx-forward-cross-rate` | no | verifier wrote 0/16 after the invalid execution | failed on an empty trace; all S1--S6 missing | 0 / 0 / 0 | 2 / 39,630 / $0.022108688 |

Run-level accounting reconciled 41 completed requests, 1,561,677 input
tokens, 100,049 output tokens, 1,661,726 total tokens, and $0.088731264.
There were zero rate-limited retries, other nonaccepted requests, unreconciled
requests, or unreconciled attempts. The FX verifier value is retained as
failure diagnostics only: the canonical Worker outcome was
`model_empty_response_before_worker_progress`, so 0/16 is not an interpretable
benchmark result and is not pooled with the two valid cells.

Cleanup completed for all 12 lifecycle records by exact ID. No related process,
container, network, volume, run-specific namespace, or transient unit remained.
The zero-byte coordinator lock had no owner. The run root contained no frozen
breadth run directory, and breadth dispatch count was zero.

### Case studies

**The swap cell shows that the target interface is feasible.** Its trusted
`research-state-trace.json` contains S1 through S6 in first-accounted order,
with exactly one ENTER and one COMPLETE for every stage. The parser reported
`marker_protocol_complete=true`, `missing_stages=[]`, `issues=[]`, and no
malformed marker, while the independent verifier recorded 19/19.

**The holdings cell shows why visible marker text is not enough.** The Worker
loaded the six-stage skill and its raw trace contains all intended S1--S6 text,
but each marker was issued through a `run_shell_command` such as
`echo '[QSTATE S1 ENTER]'`. The text then appeared as tool stdout rather than an
assistant-role standalone marker. The trusted parser consequently returned no
events, all six stages missing, and
`first_stage_entries_out_of_order_or_missing`. This is a directly observed
channel mismatch in the Worker treatment, not a parser omission and not a
quantitative-correctness judgment.

The FX cell supplies a separate execution-validity failure: the model consumed
its request budget but returned an empty assistant response with zero tool
calls and zero trace bytes. Its later verifier score cannot distinguish
quantitative capability from the absent Worker execution.

## 2. Analysis

The protocol construct remains unrealized because the gate failed on two
independent requirements. Holdings completed real work and produced a valid
official result, but its state text never crossed the frozen assistant-role
interface. FX did not produce a valid Worker attempt at all. Swap proves that
Core-v2 can realize the interface in one trajectory, but 1/3 completion is not
reliable enough to make its history consistently retrievable by QRS.

The holdings mismatch supports a narrow repair, not a broader quant workflow.
The next Worker may clarify that markers must be direct assistant text and must
not be emitted through shell commands. It may not add holdings conventions,
FX formulae, curve checks, hidden properties, expected values, or any
task-specific method. Expanding the trusted parser after observing this run to
accept arbitrary shell commands or tool stdout would change the measured
construct and could count text that was never an assistant state transition.

The zero breadth dispatch is a positive governance result, not a performance
result. The frozen gate prevented an invalid and protocol-incomplete substrate
from generating 48 downstream breadth cells. Conversely, the valid 19/19 and
42/51 records remain useful execution evidence, but they do not form a
three-task aggregate because FX is invalid, and they do not establish stable
gain because the gate contains no matched Legacy arm or repetition.

## 3. Problems and Open Questions

- **The marker channel is underspecified to the model in practice.** The skill
  states the exact grammar, yet one competent long trajectory treated shell
  stdout as marker emission. The discussion point is how strongly to require
  direct assistant-role lines without adding a new quantitative checklist or
  making ordinary tool use awkward.
- **The FX failure is operationally distinct from protocol failure.** The
  canonical error was an empty model response before Worker progress. The
  stderr also contained sandbox/E2B notices, but the retained artifacts do not
  establish those notices as the cause. A fresh gate should treat any repeated
  invalid execution under its predeclared validity rule rather than
  retroactively interpreting 0/16.
- **A repaired Worker is a new treatment identity.** The current breadth plan
  is frozen to Core-v2. Even a marker-only Core-v3 repair cannot inherit this
  failed gate or silently dispatch the Core-v2 breadth runs.
- **Marker completeness remains separate from stage correctness.** A future
  green parser proves observable transitions only; it does not prove that S2
  used adequate evidence, that S3 represented the task correctly, or that S5
  performed a meaningful reconciliation.

## 4. Next Plan

1. Retain this compact result and decision as the terminal Core-v2 gate record;
   keep every frozen Core-v2 breadth run undispatched.
2. Define a new marker-channel-only Worker treatment that requires direct
   assistant-role QSTATE lines and explicitly rejects shell-echo emission,
   without adding a quantitative method or task-specific instruction.
3. Before paid execution, use no-model fixtures to show that direct assistant
   markers pass while tool-call payloads and tool stdout remain excluded; then
   freeze a new executable gate and source revision.
4. Run the full three-task gate with fresh independent Workers. Proceed to a
   separately frozen breadth plan only if all three Worker/verifier
   observations are valid and all three strict traces are complete with no
   issue. Official scores remain descriptive and cannot override this gate.
5. Preserve the universal Candidate Information-Set Reviewer, answer-free
   Worker boundary, matched baseline, repeat, protection, and sealed-evaluation
   requirements as separate main-experiment blockers.

The canonical remote artifacts are retained at
`/data/qea-julius-storage/runs/qf-quant-h0-s6-core-v2-protocol-gate-20260824-r1`.
The compact machine-readable result is
`data/breadth/QF_QUANT_H0_S6_CORE_V2_PROTOCOL_GATE_RESULT.json`.
