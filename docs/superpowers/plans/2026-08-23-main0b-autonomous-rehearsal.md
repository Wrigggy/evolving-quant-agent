# Main-0B autonomous rehearsal plan

Date: 2026-08-23

## Goal

Close the remaining gap between the retained thin controller and a small main
experiment: begin from Quant-H0, let the existing Evolver autonomously produce
at most one candidate per lineage, and let the fixed controller own every
subsequent evaluation and terminal decision.

This is an engineering and autonomy rehearsal. It does not compare generic and
QRS search, does not run sealed evaluation, and does not implement the deferred
large-panel scheduler.

## Scope

Run two pre-screened QFBench relation families:

1. `13f-amendment-aware-crowding` target with
   `brinson-sector-attribution` protection; and
2. `dupire-local-vol` target with `localvol-barrier` protection.

Each lineage has one Quant-H0 parent, one quant-state evidence view, one fresh
Evolver proposal budget, and at most one admitted candidate. The two lineages
run in separate systemd services and separate state directories. Their starts
are staggered by roughly 30 seconds to reduce provider bursts.

## Controller path

```text
PROPOSAL
  ABSTAIN ------------------------------> FROZEN
  ACT but not admitted -----------------> ROLLBACK / FROZEN
  admitted ACT -> TARGET
      no gain --------------------------> ROLLBACK / FROZEN
      gain -> REPEAT
          no repeated gain ------------> ROLLBACK / FROZEN
          repeated gain -> PROTECTION
              property unsafe ---------> ROLLBACK / FROZEN
              property safe -----------> PROMOTE / FROZEN
```

The controller reuses the existing discovery and component-pilot runners. It
does not dispatch the short selected probe. Target, repeat, and protection are
normal-budget parent/candidate comparisons.

## Resume exercise

The holdings controller starts with `--stop-after-stage proposal`. It must save
the admitted proposal and real candidate path before exiting at `TARGET`. The
same plan, lineage, and state directory are then invoked without the stop flag.
Resume must not rerun or recount the completed Evolver proposal.

The local-vol controller runs normally in its own state directory. The two
services may overlap, but promotion within either lineage remains serialized.
If a child is interrupted unexpectedly, rerunning the same controller command
uses the same child run ID and lets the existing rootless runner recover its
own completed attempts.

## Limits and interpretation

- maximum two Evolver sessions and two candidate versions in total;
- maximum one candidate per lineage;
- no refinement round;
- `$0.90` stage-start limit per lineage;
- six-hour wall-time limit per service;
- no generic arm and no sealed task;
- no experimenter candidate edits or score-based override.

An autonomous `ABSTAIN` or correct rollback is a valid search outcome. It
passes the controller path but does not establish a performance improvement.
At least one admitted proposal reaching a truthful evaluation decision is
needed to call the proposal-to-terminal autonomous loop observed. Main-0B is
successful as a scale rehearsal only if both lineage states remain isolated
and the holdings boundary resume reuses completed work.

The executable plan is
`data/breadth/QF_MAIN0B_AUTONOMOUS_PLAN.json`.
