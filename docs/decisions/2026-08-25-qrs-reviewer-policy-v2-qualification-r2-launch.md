# QRS Reviewer-policy-v2 qualification R2 launch decision

Date: 2026-08-25

## Decision

Authorize the separately frozen setup-recovery canary
`qf-qrs-reviewer-policy-v2-qualification-20260825-r2` through exactly
`stop_after_panel=1`. This is not an R1 resume or repeat, is not Main
authorization, and does not authorize an R3, later panel, feedback-sealed task,
or reuse of any R1 scientific material.

The tested source is repository revision
`4c1ce03d798c646c76d97b07c75462eff01062f7`. Relative to the setup-invalid
R1, the scientific treatment, four metadata-selected task strata, Primitive-H0,
model/runtime, answer-free evidence policy, Reviewer policy v2, matched gate,
and budget are unchanged. The allowed engineering repairs are limited to:

1. the controller's 24-line and 24,000-byte trajectory excerpt boundary is
   enforced by `decide_candidate` before ACT admission, so an Evolver can remove
   redundant exact citations and retry within the same fresh proposal;
2. a residual Review-package construction error becomes an accounted
   `HOLD_FOR_REFINE` and outer `STOP_PANEL_REVIEW_PACKAGE_INVALID`, with zero
   Reviewer and candidate Worker calls, rather than an uncaught stale-RUNNING
   failure;
3. the health watcher does not report a collected or unavailable unit as a
   default success, and the launch must retain the main transient unit until
   terminal scheduler and journal status have been audited.

## Fixed execution

- Run four entirely fresh Primitive-H0 cells. Do not copy any R1 path, trace,
  candidate, claim, score, outcome, verdict, or evidence-access state.
- Build a fresh answer-free trajectory bank and run one fresh
  `workflow_global` proposal on the panel-1 focus plus two other-family anchors.
- Permit at most one answer-free Candidate Information-Set Review, only after a
  fresh admitted ACT and a compact valid Review package.
- If and only if overall and coverage are both `PASS`, evaluate the exact
  read-only reviewed snapshot on three tasks, two arms, and two fresh
  repetitions: twelve matched cells.
- Stop after panel 1. Later panels and sealed placeholders remain unauthorized.

The incremental hard envelope is sixteen QFBench cells, one Evolver call, one
Reviewer call, at most 800 completed requests, 60,000,000 tokens, USD 4.00,
86,400 seconds, concurrency one, and zero recovery cells.

## Interpretation

R1 remains `FAIL_ENGINEERING_PRE_REVIEW`; only its aggregate request, token, and
cost totals may be used for budget sizing. R2 `ABSTAIN`, Review non-PASS,
package-invalid HOLD, runtime/accounting/cleanup failure, or answer-boundary
failure clears no engineering gate and leaves Main `NO-GO`. A Review `PASS`
still must traverse all twelve matched cells, answer-free handoff, reconciled
accounting, cleanup, and same-stop zero-work resume. The complete engineering
path may end in `PROMOTE` or executable `RETAIN_NO_STABLE_GAIN`; qualification
does not require gain and cannot support benchmark-wide utility or Main claims.

## Validation before activation

The integrated recovery cycle passed 228 focused and adjacent tests, JSON and
Python compile preflight, and `git diff --check`. The activation changes only
the resolved source and qualification-only authority fields, their focused
assertions, and this dated decision. `main_authority` remains `false`.
