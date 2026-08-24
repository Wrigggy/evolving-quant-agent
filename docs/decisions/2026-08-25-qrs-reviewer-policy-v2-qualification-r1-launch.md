# QRS Reviewer-policy-v2 qualification R1 launch decision

Date: 2026-08-25

## Decision

Authorize the separately frozen engineering canary
`qf-qrs-reviewer-policy-v2-qualification-20260825-r1` through exactly
`stop_after_panel=1`. This decision is not Main authorization and does not
authorize a later panel, feedback-sealed task, recovery attempt, or reuse of
R1--R3 mini material.

The tested engineering source is repository revision
`701ceac236e454b94f08eb7ed5fc8e9ba322fa31`. The source-freeze commit contains
the Reviewer-policy-v2 implementation, exact reviewed-snapshot binding,
bounded Reviewer package, read-only frozen-base enforcement, launch-authority
gate, focused tests, and the qualification plan. The subsequent documentation
commit changes no executable source.

## Fixed execution

- Build four fresh Primitive-H0 cells on the four metadata-selected public
  development tasks and retain complete answer-free trajectories.
- Permit one `workflow_global` proposal using only the panel-1 focus and two
  other-family anchors.
- Permit exactly one answer-free Candidate Information-Set Review.
- If and only if overall and coverage verdicts are both `PASS`, evaluate the
  exact read-only reviewed snapshot on three tasks, two arms, and two fresh
  repetitions: twelve matched cells.
- Stop after panel 1. Later panels and the two schema-only sealed placeholders
  remain unauthorized and undispatched.

The incremental hard envelope is sixteen QFBench cells, one Evolver call, one
Reviewer call, at most 800 completed requests, 60,000,000 tokens, USD 4.00,
86,400 seconds, concurrency one, and zero automatic recovery cells.

## Terminal interpretation

`ABSTAIN`, Review `REJECT`/`INCONCLUSIVE`, invalid execution, accounting
incompleteness, cleanup failure, or answer-boundary failure retains the exact
result, clears no engineering gate, leaves Main `NO-GO`, and authorizes no
automatic retry. A Review `PASS` must still traverse all twelve matched cells,
answer-free handoff, cleanup/accounting, and same-stop zero-work resume.
The complete matched path may end in `PROMOTE`, `RETAIN`, or `ROLLBACK`; this
engineering qualification does not require a benchmark gain and cannot support
QRS utility, generalization, or Main claims.

## Validation before activation

The source-freeze cycle passed 324 focused and adjacent tests, Python compile
preflight with a run-scoped cache, JSON parsing, and `git diff --check`. The
local LaTeX source preflight passed; PDF compilation was unavailable because
`latexmk` is not installed. The activation changes only the plan's resolved
source and launch-authority fields plus this dated decision.
