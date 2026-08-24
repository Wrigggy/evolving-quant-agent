# QRS mini scheduler R3 retained Review-non-PASS result

> Date: 2026-08-25 · Experiment: `qf-qrs-mini-scheduler-canary-20260825-r3` · Decision: `RETAIN_REVIEW_NONPASS`; Main `NO-GO`; no R4

## Measured setup and outcome

R3 was the final separately frozen setup recovery, not an R2 repeat. It
deployed repository revision `49c924c`; the generic evidence-interface fix base
was revision `2676e38`. The only experimental engineering delta was bounded
partial `trace_slice` returns, a 64 KB `read_workspace` return cap,
narrow-JSONL guidance, immutable `evidence_refs`, and explicit legal-ABSTAIN
carry semantics. The four tasks,
Primitive-H0 treatment, model/provider/runtime, families and anchors, answer
boundary, Reviewer, matched gate, caps, concurrency, stop after panel one, and
no-main-reuse rule remained fixed. No R1 or R2 execution or access state was
reused.

All four H0 Worker/verifier cells and runtime histories were valid. Their
descriptive official records were 44/51, 66/68, 39/39, and 19/19. These are
fresh canary observations, not a stable baseline or an evolved comparison.

The evidence interface materially worked: the Evolver completed three bounded
`trace_slice` calls returning 9,693, 119, and 29,627 bytes with zero return-limit
failure, alongside 29 bounded workspace reads. It reached a legal admitted
`ACT` that changed exactly one file,
`skills/quant-research-six-stage-workflow/SKILL.md`, adding 32 lines and 2,032
bytes. This establishes interface reach and structured admission, not the
truth or usefulness of the proposed state-span rule.

Exactly one genuine answer-free Candidate Information-Set Review ran. It
returned overall `INCONCLUSIVE`, coverage `PASS`, and four of four claim
verdicts `INCONCLUSIVE`. Coverage PASS means the declared inventory covered the
decision-changing diff. Overall INCONCLUSIVE means the supplied public
contracts did not entail the candidate's state-specific execution and revisit
rules. The Reviewer had no promotion authority and its output was never
Worker-visible. This is the historical verdict under the Review policy deployed
for R3; the later policy-v2 correction does not reinterpret it.

The lineage controller recorded `HOLD_FOR_REFINE`, and the stopped-after-panel
global scheduler resolved that non-PASS outcome as `RETAIN_REVIEW_NONPASS`. It
dispatched zero candidate matched Worker cells, preserved the exact Primitive
parent, and wrote one clean `retained_incumbent_history_carry` with zero
candidate-history entries into the next answer-free panel view. The bounded scheduler record
remains `status=RUNNING`, `phase=PANELS`, with `stopped_after_panel=1`; no later
panel or sealed action was dispatched.

A same-stop resume created zero new action. The before-resume and after-resume
copies of `RUNNER-INPUTS.json`, `SCHEDULER-RESULT.json`, and
`scheduler-state.json` were byte-identical. This is a zero-work-resume
observation, not a candidate or benchmark result.

## Exact accounting and artifacts

The four H0 cells used 148 completed requests, 7,264,862 tokens, and
$0.229676040. The Evolver used 23 completed requests, 2,771,430 tokens, and
$0.081515784. The single Reviewer request contributed 52,094 scheduler-accounted
tokens and $0.041553600. The exact run total was 172 completed requests,
10,088,386 tokens, and $0.352745424. Candidate matched Worker accounting was
zero.

The compact retained record is
[`QF_QRS_MINI_SCHEDULER_CANARY_R3_RESULT.json`](../../data/breadth/QF_QRS_MINI_SCHEDULER_CANARY_R3_RESULT.json).
The scheduler/bank mirror is
[`results/bc-mirror/qf-qrs-mini-scheduler-canary-20260825-r3/`](../../results/bc-mirror/qf-qrs-mini-scheduler-canary-20260825-r3/),
the proposal mirror is
[`results/bc-mirror/qf-qrs-mini-scheduler-canary-20260825-r3-panel-01-proposal/`](../../results/bc-mirror/qf-qrs-mini-scheduler-canary-20260825-r3-panel-01-proposal/),
and the genuine Review is
[`RESULT.json`](../../results/bc-mirror/qf-qrs-mini-scheduler-canary-20260825-r3-panel-01-review/RESULT.json).
The pre-resume snapshot was held at `/private/tmp/qf-r3-resume-before/` for the
local zero-work comparison; the compact result retains the canonical
observation and exact compared filenames.

## Decision and boundary

R3 closes the observed setup interfaces but does not clear the mini scientific
gate. The frozen gate required overall Review PASS followed by all 12 matched
parent/candidate cells, answer-free handoff, and zero-work resume. R3 reached
Review but not PASS, so no candidate Worker was legally dispatchable. That
complete matched path may end in PROMOTE or a scientifically valid
RETAIN/ROLLBACK; retained gain is not required to clear the mini engineering
path, because utility is measured in Main.

Main remains `NO-GO`. There is no R4 setup recovery. R1, R2, and R3 histories,
candidates, claims, access state, scores, and decisions are not reusable in
Main. A fresh positive-Review path must be live-validated after the Review
policy correction; R3 cannot be reinterpreted or reused to satisfy it. The
retained result supports only fresh banking, bounded evidence access, one
admitted proposal, genuine pre-Worker Review, safe non-PASS retention, clean
carry, exact accounting, and idempotent resume. It supports no matched gain,
promotion, reusable candidate, sealed performance, main readiness, benchmark
improvement, or QRS-effectiveness claim.
