# Quant-H0-S6-Core-v3 R2 protocol repair and breadth plan

Date: 2026-08-24
Status: Frozen, not yet run

## Retained R1 observation

The Core-v2 protocol gate
`qf-quant-h0-s6-core-v2-protocol-gate-20260824-r1` stopped before breadth.
Its three cells have different evidentiary roles:

| Task | Execution | Official result | Protocol observation |
|---|---|---|---|
| `swap-curve-bootstrap-ois` | valid | 19/19, reward 1 | PASS: 12 ordered S1--S6 events appeared as direct assistant-role text. |
| `13f-amendment-aware-crowding` | valid | 42/51, reward 0 | REJECT: every marker was embedded in `run_shell_command` `echo` calls and appeared only in ToolUse/tool stdout; the trusted assistant-role parser correctly recorded zero events. |
| `fx-forward-cross-rate` | invalid | 0/16, reward 0 but invalid for selection | NOT OBSERVED: `model_empty_response_before_worker_progress`, zero turns, tool calls, and artifacts. This is not protocol evidence. |

The R1 Worker therefore showed a specific marker-output-channel failure, not a
need for another quantitative workflow. No R1 score, failed-property identity,
or artifact content selects or changes the breadth panel. These observations
remain controller-side and are not Worker-visible.

## Core-v3 decision

`Quant-H0-S6-Core-v3` copies Core-v2 under a new identity. Its only semantic
change is an explicit marker-channel rule:

- each `[QSTATE ...]` marker is direct assistant-role plain text on its own line;
- markers inside ToolUse, `run_shell_command`, `echo`/`printf`, tool
  descriptions, tool stdout/stderr, or other tool calls/results do not count;
- missed earlier markers cannot be backfilled retrospectively in the final
  response; each marker is emitted at the transition it records.

Core-v3 does not add or change a quantitative method, formula, estimator,
data-cleaning heuristic, artifact checklist, task identifier, expected value,
hidden property, benchmark convention, stage definition, marker grammar, model,
provider, tool, descriptor, binding, budget, runtime, or verifier.

## Separately frozen R2 execution

The executable record is
`data/breadth/QF_QUANT_H0_S6_CORE_V3_BREADTH_PLAN.json`.

1. Resolve the future source revision and complete the no-model preflight.
2. Run the new Core-v3-only three-cell protocol gate
   `qf-quant-h0-s6-core-v3-protocol-gate-20260824-r2`.
3. Proceed only if all three Worker/verifier observations are valid and all
   three traces realize the direct-assistant S1--S6 protocol without malformed
   markers or sequence issues. Official scores are retained but cannot
   authorize breadth.
4. Only after that gate, run the unchanged frozen Legacy-versus-Core breadth
   repetition 1. Repetition 2 remains separately conditional on complete,
   valid, budget-reconciled repetition-1 evidence.

The 12-task selector, exact tasks, grouping, task order, matched arm-order
reversal, metrics, overhead thresholds, terminal decisions, and budgets are
unchanged from the Core-v2 breadth plan except for the necessary Core-v3/R2
identities. No task may be replaced after an outcome.

## Claim boundary

R2 remains Worker-substrate protocol calibration followed conditionally by a
descriptive development breadth map. It contains no Evolver, candidate,
Candidate Information-Set Reviewer, promotion, AHE comparison, or sealed
evaluation. A successful R2 does not clear the QRS-only Main gate and does not
support benchmark-wide superiority. Core-v3 remains a disclosed human-authored
thin state/protocol scaffold.
