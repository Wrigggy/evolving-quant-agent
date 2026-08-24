# QRS mini scheduler R2 retained oversized-retrieval ABSTAIN result

> Date: 2026-08-25 · Experiment: `qf-qrs-mini-scheduler-canary-20260825-r2` · Decision: retrieval/compaction-corrupted; Main `NO-GO`

## Measured setup and outcome

R2 was a separately frozen setup recovery, not a repeat of R1. It rebuilt the
same four-task Primitive-H0 bank with fresh Workers and no R1 histories,
proposal, scores, controller decision, or evidence-access state. All four
Worker/verifier cells and all four runtime histories were valid. The
descriptive official records were 48/51, 67/68, 38/39, and 19/19.

The repaired structured decision path reached one genuine Evolver proposal
session. During answer-free evidence inspection, two otherwise valid broad
`trace_slice` calls constructed repeated long-JSONL context windows and then
failed with `trace slice exceeds bounded return limit`. The final Evolver
decision said that the direct reads were empty, but the retained tool-event
audit corrects that account: two `read_workspace` calls returned 195,919 and
113,955 bytes at tool time, and a later `trace_slice` succeeded with 131,999
bytes. The pre-decision prompt reached 141,971 tokens; terminal compaction
reduced it to 28,399 and replaced the earlier oversized tool content with empty
`bounded_text`. No discriminating probe was recorded. Under that corrupted
terminal view, the Evolver correctly failed closed with a contract-valid
`ABSTAIN`, zero changed candidate files, and no admission requirement.

That ABSTAIN is a legal control decision, but its scientific interpretation is
limited. Large trace observations did reach the tool boundary but were not
preserved faithfully through terminal compaction, so R2 does not show that the
underlying public evidence was intrinsically insufficient. Evidence sufficiency
remains indeterminate.

The controller retained `decision=ABSTAIN` and `status=abstained`, but the
outer scheduler treated the absence of a Review-bound candidate as a missing
Review and stopped at `STOP_PANEL`. A legal ABSTAIN should instead retain the
unchanged parent and clean answer-free history without dispatching Review or a
candidate Worker. Genuine Reviewer calls, candidate matched Worker cells,
panel results, and curriculum handoffs were all zero.

## Exact accounting and artifacts

The four H0 cells used 144 completed requests, 6,122,268 tokens, and
$0.184157872. The Evolver proposal used 11 completed requests, 481,637 tokens,
and $0.056217292. The exact total was 155 completed requests, 6,603,905
tokens, and $0.240375164. Reviewer and candidate-Worker accounting were zero.

The compact retained record is
[`QF_QRS_MINI_SCHEDULER_CANARY_R2_RESULT.json`](../../data/breadth/QF_QRS_MINI_SCHEDULER_CANARY_R2_RESULT.json).
The local mirrors are
[`results/bc-mirror/qf-qrs-mini-scheduler-canary-20260825-r2/`](../../results/bc-mirror/qf-qrs-mini-scheduler-canary-20260825-r2/)
and
[`results/bc-mirror/qf-qrs-mini-scheduler-canary-20260825-r2-panel-01-proposal/`](../../results/bc-mirror/qf-qrs-mini-scheduler-canary-20260825-r2-panel-01-proposal/).
The latter retains `proposal-report.json`, the legal ABSTAIN payload, and the
observed tool-boundary errors; the scheduler mirror retains the bank,
controller, and outer state records.

## Decision and boundary

R2 is retained as `FAIL_OVERSIZED_RETRIEVAL_COMPACTION_CORRUPTED`. It
establishes fresh H0 banking, the repaired structured decision path, and a
calibrated fail-closed action under a corrupted terminal evidence view.
It does not establish public-evidence insufficiency, a Candidate Review,
matched gain, reusable candidate, promotion, sealed performance, or QRS
effectiveness.

One final separately frozen R3 was permitted to change only the generic bounded
trace/read interface, JSONL-use guidance, immutable evidence-reference
namespace, and legal ABSTAIN retain/carry semantics. R3 had to rebuild all H0
and evidence surfaces fresh. R2 material was not eligible for R3 or Main.
