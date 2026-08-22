# Thin Main-0 Candidate-Lineage Controller

Date: 2026-08-22

## Goal

Replace the experimenter-arranged QFBench candidate lifecycle with one small,
resumable outer loop.  The Evolver retains freedom over diagnosis and harness
mutation.  The controller owns only evaluation dispatch, mechanical credit
assignment, promotion or rollback, budget, and freeze.

This is experiment infrastructure, not the quant-specific method contribution.
The Quant Research State Card, relation-conditioned retrieval and routing, and
activation--relation--outcome evidence remain the proposed method.

## State path

```text
PROPOSE
  -> TARGET
  -> REPEAT when the target has a strict official gain
  -> PROTECTION when the gain repeats independently
  -> PROMOTE when protection is reward-, count-, and property-safe
  -> ROLLBACK after any failed gate
  -> FROZEN
```

The first implementation uses one parent and one candidate per lineage.  State
is ordinary JSON with readable version names and paths.  It reuses the existing
discovery and component-pilot runners and adds no database, generic scheduler,
RAG, branching search, or new content identity.

## Implementation

1. Add `qea/qfbench_lineage.py` as the pure state machine and report parser.
2. Add `scripts/run_qfbench_lineage_controller.py` as the thin child-runner
   adapter.  Completed reports are ingested without launching a child again.
3. Add focused deterministic tests for target/repeat advancement, safe
   promotion, property regression rollback, cost accounting on resume, and
   the stage budget boundary.
4. Materialize two Main-0 replay plans from retained evidence:
   - holdings: 13F target/repeat plus Brinson protection, expected promotion;
   - local-vol: Dupire target/repeat plus `localvol-barrier` property swap,
     expected rollback.
5. Run one controller-owned live component child on bc after replay passes.
   Use the holdings protection path because it is already measured as safe;
   do not pay to rediscover either candidate.

## Promotion semantics

Target and repeat require a scored parent and candidate, no reward or passed-
property regression, and at least one strict gain.  Protection additionally
requires that the candidate retain every property passed by the parent when a
trusted failed-property summary is available.  Aggregate ties with exchanged
failed properties are rollback outcomes.

Component activation and declared-relation observation are retained separately
for mechanism interpretation.  They do not replace the performance promotion
gate.

## Evidence and claim gates

The replay demonstrates real-report parsing, phase transitions, promotion,
rollback, freeze, and idempotent resume.  It does not demonstrate live dispatch
or end-to-end autonomy.

The controller-owned live child demonstrates dispatch, report ingestion, cost
accounting, and terminal transition without experimenter stage repair.  A later
small H0-to-proposal-to-freeze canary is required before claiming that a full
search campaign can run autonomously from H0.

No Main-0 result is a sealed benchmark claim.  Worker inputs remain answer-
blind, protection evidence remains unavailable to the Evolver, and sealed
evaluation remains deferred until after harness freeze.

## QuantCodeEval breadth decision

Audit the remaining tasks in parallel, but do not make a 20-task expansion a
Main-0 prerequisite.  Run only credential-free tasks whose public/trusted
runtime is already supported and whose relation family adds evidence not
already supplied by QFBench or the existing QuantCodeEval panel.  Defer tasks
requiring unavailable licensed data or a new runtime build until after the
controller can sustain the smaller campaign.
