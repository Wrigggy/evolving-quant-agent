# QRS main 72-hour engineering execution plan

Date: 2026-08-24 (Asia/Singapore)

Status: active implementation plan; no P0 gate may be waived to meet the time target

## Objective

Within 72 hours, convert the prospective Primitive-H0 global QRS specification
from `scheduler_wrapper_support=not_implemented` and `launch_authorized=false`
to an executable, locally verified and live-canary-validated main scheduler.
The endpoint is a frozen launch manifest capable of starting the 393-cell
QFBench main without another design or implementation decision.

## Non-negotiable launch gates

1. One externally selected base harness is materialized through the frozen-base
   adapter and imported as the exact Primitive-H0 parent.
2. Primitive-H0 completes a bounded live structured S1--S6 protocol canary.
3. Every changed or evolved candidate fails closed before Worker dispatch unless
   Candidate Information-Set Review returns overall `PASS` with complete
   coverage.
4. The Worker executes the exact run-scoped candidate snapshot that the
   Reviewer inspected. No post-review instruction or runtime overlay is added.
5. The H0 bank and panel views exclude official scores, verifier materials,
   expected values, failed properties, checker output and all sealed tasks from
   Evolver evidence.
6. The outer scheduler is deterministic, ordinary-JSON, resumable and
   idempotent in child import and cost accounting.
7. A local mock end-to-end run and a bounded live mini-scheduler canary pass
   before the full main launch manifest is activated.

## Current checkpoint

WP-A through WP-D and the launch/public-contract materializers are implemented
locally. The current focused and adjacent suite covers the adapter, Primitive
Worker, workflow-global Evolver guard, universal reviewed snapshot, trajectory
bank, mutation boundary, dynamic incumbent scheduler, operational runner,
public contracts, launch builder, 393-cell method contract and both frozen
canary plans. The remaining critical path is live rather than architectural:

1. deploy the exact committed source;
2. pass the three-cell Primitive protocol canary;
3. materialize and run the four-bank-task mini scheduler through one live
   Review-PASS candidate and blind matched Worker;
4. audit zero-work resume, accounting and cleanup;
5. freeze the measured main caps and launch Phase 0 only if all gates pass.

## Work packages and ownership

### WP-A: frozen base-harness adapter

Deliver:

- `qea/frozen_base_harness.py`;
- `scripts/freeze_qrs_base_harness.py`;
- `tests/test_frozen_base_harness.py`;
- one ordinary-JSON handoff schema compatible with
  `QF_GLOBAL_S6_PRIMITIVE_H0_TRAJECTORY_SCHEDULER_PLAN.json`.

Acceptance: a contract-compatible Worker tree is copied to one run-scoped
frozen directory; missing prompt, shell, recorder, six-state or runtime material
fails before any Worker; no model or benchmark call occurs.

### WP-B: universal Candidate Information-Set Review

Deliver:

- changed candidates default to Review-required;
- preconstructed candidates enter Review before target;
- missing Review can never use the legacy direct-to-target path in main mode;
- selected-probe direct dispatch is disabled for main, or its complete effective
  Worker is materialized and reviewed first;
- Review and Worker point to the same run-scoped reviewed snapshot;
- Review result, import and accounting remain resume-idempotent.

Acceptance: focused tests prove missing/non-PASS Review starts zero candidate
Workers, PASS starts exactly the reviewed material, post-review mutation cannot
run, and Frozen H0 remains the only no-Review Worker.

### WP-C: all-N trajectory bank and panel evidence

Deliver:

- `qea/qfbench_trajectory_bank.py`;
- `scripts/build_qfbench_trajectory_bank.py`;
- `tests/test_qfbench_trajectory_bank.py`;
- complete task entries, explicit empty artifacts, retained invalid attempts,
  six family panels and five frozen cross-family anchors per panel.

Acceptance: controller-only outcomes remain outside the Evolver tree; sealed
tasks are absent; rebuild is idempotent; all 45 development tasks are indexed
exactly once as focus evidence.

### WP-D: global outer scheduler

Deliver:

- `qea/qrs_global_scheduler.py`;
- `scripts/run_qrs_global_scheduler.py`;
- `tests/test_qrs_global_scheduler.py`;
- phases for H0 import, bank children, panel proposal, Review, two matched
  repetitions over focus tasks plus five cross-family anchors, dynamic
  incumbent promotion/retention, final freeze, sealed blocks and
  terminal report.

Acceptance: fixed child IDs; no duplicate dispatch on resume; dynamic parent
binding to the actual retained incumbent; reversed arm order; repeated strict
focus gain plus zero task regression over focus and all five anchors; legal
scientific non-promotion retains the incumbent and continues; sealed outcomes
never affect dispatch, search or another run; ordinary-JSON accounting
reconciles every imported child exactly once.

### WP-E: integration and live gates

Deliver:

1. full local focused suite and mock end-to-end scheduler;
2. three-cell Primitive-H0 live protocol canary;
3. bounded mini scheduler with four H0-bank tasks, one global proposal, one
   Review and a twelve-cell focus-plus-anchor two-repetition matched panel gate;
4. final deployment source, runtime manifest, service units, run IDs, budgets,
   health/watchdog/mirror commands and frozen main launch manifest.

Acceptance: no unresolved provider accounting, duplicate dispatch, live process,
container or network residue; mini canary reaches a valid terminal HOLD,
ROLLBACK or PROMOTE by the same predicates as main.

## 72-hour critical path

### T+0 to T+12 hours

- implement WP-A, WP-B and WP-C in parallel;
- implement WP-D state and schema skeleton;
- keep file scopes disjoint and run focused tests in each branch of work;
- publish no remote artifacts.

### T+12 to T+30 hours

- integrate adapter, Review snapshot and bank builder into WP-D;
- implement bank dispatch/import, panel proposal/Review and matched gate;
- add resume, cost and `stop-after-phase` tests;
- exercise all failure terminals using deterministic fake children.

### T+30 to T+44 hours

- implement checkpoint, final freeze, sealed blocks and terminal report;
- run full local focused/adjacent tests, JSON parse and diff preflight;
- materialize a local frozen Primitive-H0 handoff;
- freeze deploy inputs for live canaries.

### T+44 to T+54 hours

- run the three-cell Primitive protocol canary;
- audit structured state chronology, validity, cost and cleanup;
- fix only observed interface/runner failures and rerun one separately recorded
  setup recovery if required.

### T+54 to T+66 hours

- run the bounded mini-scheduler canary;
- audit exact candidate Review, zero leakage, matched parent/candidate children,
  resume, accounting and cleanup;
- stop if any P0 invariant fails.

### T+66 to T+72 hours

- freeze executable main plan and deployment revision;
- start coordinator, remote health, watchdog and additive mirror together;
- launch the 45-task H0-bank phase of the complete main;
- record launch identity, budget and initial health in PROJECT_MEMORY and the
  manuscript experimental protocol.

## Main execution envelope after launch

- 45 Primitive-H0 development-bank cells;
- 300 focus-plus-five-anchor panel parent/proposal fitness cells;
- 48 feedback-sealed Primitive-H0/final-QRS cells;
- 393 primary QFBench cells and at most three setup-only recovery cells;
- six Evolver and six Candidate Reviewer calls;
- Worker/verifier concurrency one;
- provisional hard envelopes: 900M tokens, USD 60, 15 days; tighten these
  after the mini-scheduler canary rather than treating them as cost forecasts.

The external exploratory Primitive-H0 selection is outside this scheduler and
outside these counts. AHE reproduction, QRS-no-State, a second independent
lineage, QuantCodeEval and complex branching are not launch blockers.

## Stop rules

- `STOP_ADAPTER` on incomplete or mutable base-harness handoff.
- `STOP_REVIEW` on missing, malformed, provenance-invalid or
  material-mismatched Candidate Review. A well-formed `REJECT` or
  `INCONCLUSIVE` retains the incumbent and continues to the next family with
  zero candidate Worker.
- `STOP_BANK` on incomplete development indexing or forbidden provenance.
- `STOP_SCHEDULER` on duplicate dispatch, non-idempotent resume/accounting or
  unresolved invalid child.
- `STOP_PROTOCOL` on Primitive or candidate structured S1--S6 failure.
- `STOP_CANARY` on any mini-scheduler P0 failure.
- `STOP_MAIN` before launch if any of the preceding stops remains active.

The 72-hour objective does not authorize bypassing a stop condition.
