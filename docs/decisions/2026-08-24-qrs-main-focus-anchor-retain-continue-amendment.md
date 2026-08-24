# QRS main focus-anchor and retain-continue amendment

Date: 2026-08-24 (Asia/Singapore)

Status: accepted and implemented locally; Primitive live protocol gate passed; mini-scheduler gate remains pending

Supersedes only the focus-only fitness and stop-on-scientific-nonpromotion parts
of `2026-08-24-primitive-h0-bank-and-panelized-global-qrs.md`. It preserves the
Primitive-H0 adapter, 45-task answer-free trajectory bank, six-family curriculum,
exact Candidate Information-Set Review, sealed partition, and all retained
historical results.

## Decision

The QRS main remains one cumulative lineage. Each of its six family rounds may
produce one global-workflow candidate, but promotion is no longer decided from
the focus family alone. After Review `PASS`, the exact incumbent and reviewed
candidate are evaluated twice on:

- every task in the current focus family; and
- one fixed development anchor from each of the other five families.

Arm order is reversed between repetitions. Promotion requires all cells to be
valid and protocol-complete, candidate native reward to be no lower on every
focus and anchor task in both repetitions, a strictly higher focus-family mean
in both repetitions, and at least one identical focus task to be a candidate
win in both repetitions. Anchor wins cannot substitute for a focus-family gain.

This is **task-reward-nonregressing panel promotion**. It is not a
failed-property-set or property-safe guarantee. Leaf official diagnostics stay
controller-only and are not translated into Evolver evidence.

## Continue semantics

A legal scientific nonpromotion does not terminate the curriculum:

- `ABSTAIN`;
- Review `REJECT` or `INCONCLUSIVE`;
- a valid tie-only result;
- a gain that does not repeat; or
- a valid task-reward regression

retains the current incumbent, records the round and its cost, carries forward
only previously accepted answer-free history, and advances to the next family.
Only malformed provenance, candidate/snapshot mismatch, invalid runtime after
its frozen recovery, protocol failure, incomplete accounting, budget exhaustion,
or sealed-boundary violation terminates the scheduler. The final sealed arm is
the actually retained incumbent after panel six; it may still be Primitive-H0
or any earlier promoted candidate.

## Executable accounting

The revised primary envelope is:

- 45 Primitive-H0 development-bank cells;
- 300 matched panel cells: for each family, `(focus tasks + 5 anchors) x 2 arms x 2 repetitions`;
- 48 sealed cells: 12 tasks x 2 arms x 2 repetitions;
- 393 primary Worker/verifier cells in total, excluding at most three separately
  recorded setup-only recovery cells.

The sealed report includes 24 repetition-level paired W/T/L outcomes, 12
task-mean paired W/T/L outcomes, complete task vectors, and family rows. Because
the sealed panel has exactly two tasks per family, the equal-task mean and
equal-family macro are numerically identical by construction and are not
presented as independent evidence.

## Implementation status and remaining gate

The local implementation now includes dynamic incumbent resolution, exact
run-scoped reviewed candidates, fail-closed changed/preconstructed candidates,
answer-free trajectory-bank views, cross-family anchor fitness, scientific
retain-and-continue outcomes, complete accounting checks, resume-stable child
imports, QRS mutation boundaries, public-contract materialization, launch
materialization, and sealed W/T/L summaries. The related local suite passes
269 tests.

The three-task Primitive-H0 structured protocol canary has now passed 3/3 valid
cells with strict schema-v2 S1--S6 telemetry. This satisfies the substrate
interface prerequisite only; its single descriptive scores are not a matched
baseline or QRS result.

Main remains `NO-GO` until the bounded mini scheduler exercises a real
Candidate Review `PASS`, exact reviewed-snapshot blind Worker, matched repeated
panel terminal, accounting, cleanup, and zero-work resume.

No QRS main, stable-promotion, sealed-performance, or superiority claim exists
before those gates and the prospective campaign complete.
