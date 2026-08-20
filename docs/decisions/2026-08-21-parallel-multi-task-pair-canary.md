# Parallel multi-task pair canary

Date: 2026-08-21

## Objective

Run several isolated Evolver branches in parallel to test whether bounded
multi-task coordination can complete on at least one fixed pair without turning
the pilot into a benchmark-wide scheduler or main experiment.

The panel is fixed before any live call. Every branch and negative result stays
in the denominator. The aggregate is reported as `x/3`, not as an average
effect or an estimate of generalization.

## Fixed pair panel

1. `rates_curve_repricing`: `zero-coupon-bootstrapping` target and
   `swap-curve-bootstrap-ois` protection. The shared object is quote-to-curve
   construction closed by instrument repricing under consistent conventions.
2. `adjusted_price_event_time`: `corporate-action-adjustment` target and
   `momentum-backtest` protection. The shared object is point-in-time
   adjusted-price state propagated through event, price-field, and execution
   timing.
3. `forward_consistent_option_surface`: `localvol-barrier` target and
   `variance-swap-replication` protection. The shared object is a unit- and
   forward-consistent OTM option surface before downstream valuation.

The third branch is intentionally the long-tail branch. It runs independently
so it cannot block interpretation of the first two branches.

Machine-readable panel:
`data/breadth/MT_PARALLEL_PAIR_CANARY.json`.

## Per-branch contract

Each Evolver receives only its own two answer-free Quant Research
Trajectories. ACT requires it to:

- inspect and cite evidence from both tasks;
- name a concrete shared mechanism narrower than a Research-State label;
- generate an admitted reusable candidate;
- select exactly the predeclared target as `probe_task_key`;
- author one answer-free, from-scratch Worker probe with no seed and at most 12
  iterations;
- predeclare the component activation or action that would support or reject
  the mechanism.

The coordinator dispatches one experiment-directed Worker on that target. It
does not run the protection task automatically. A target screen must first be
positive. A positive screen then triggers a normal Fresh Quant-H0 comparator,
a normal candidate confirmation without the experiment directive, and finally
the unchanged candidate on the protection task.

ABSTAIN, no candidate, failed admission, no component activation, no artifact
action, target non-improvement, protection regression, timeout, and
infrastructure failure are all retained terminal outcomes.

## Success and claim boundary

The panel gate is at least one complete bounded chain among the three fixed
pairs. A complete chain requires both-task evidence use, a concrete matched
mechanism, admitted ACT, singleton target probe, observable component action,
target improvement over the retained screen and a Fresh Quant-H0 comparator,
and the predeclared protection floor.

Passing this gate supports one existence-style claim: bounded multi-task
coordination was observed on one predeclared pair. It does not establish an
average performance gain, stability, scheduling efficiency, task-family
generalization, or an unbiased estimate for the winning pair. Any winning
candidate is selected on this pilot.

## Preflight

All six real retained QFBench trajectories were materialized into three
isolated coordinated views. The decision contract now requires both-task
evidence, `shared_mechanism`, one target `probe_task_key`, and a seedless
from-scratch experiment. The proposal runner can dispatch only that singleton
target and applies the Evolver-authored directive and bounded iteration budget
to a derived probe Worker. Protection remains separate.

The focused local suite passed 181 tests with no model or Worker request.
Compact evidence:
`data/breadth/MT_PARALLEL_PAIR_PREFLIGHT_RESULT.json`.
