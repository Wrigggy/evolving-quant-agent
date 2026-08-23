# QFBench A0 matched generic--QRS experiment

Date: 2026-08-23

Status: frozen, not run

Executable plan: `data/breadth/QF_A0_MATCHED_GENERIC_QRS_PLAN.json`

## What this experiment answers

A0 is the smallest fresh comparison needed after the controller and parent-
reuse runway. It asks whether an operational Quant Research State (QRS)
representation helps the Evolver search the full harness, beyond giving a
strong generic Evolver the same quant task trajectory, optimize diagnostics,
component history, model, budget, and mutation freedom.

It contains two mechanism families and four independent candidate lineages:

| Family | Target | Protection | Search arms |
|---|---|---|---|
| holdings final-state reconciliation | `13f-amendment-aware-crowding` | `brinson-sector-attribution` | generic, QRS |
| local-vol maturity/surface coverage | `dupire-local-vol` | `localvol-barrier` | generic, QRS |

Each arm may propose one candidate, so the whole experiment has at most four
fresh proposals. There is no refinement round and no experimenter edit to a
candidate.

## The one treatment difference

Both arms start from the same Quant-H0 Worker Agent. They receive the same
underlying authorized runtime evidence, optimize diagnostic, raw candidate and
component history, Evolver model and reasoning setting, normal Worker budget,
official verifier, full harness mutation surface, and answer boundary. The
generic arm is allowed to infer any finance mechanism and edit any mutable
harness component; it is not restricted to prompt mutation.

The QRS arm alone must construct an operational State Card and use its state
and quantitative-relation coordinates to retrieve experience and route toward
a component locus. This must change an observable search action---retrieval,
routing, component choice, or calibrated verdict. Merely using finance-shaped
labels is a neutral result.

The already materialized paired evidence roots are used:

- holdings generic and `quant-state` views under
  `/data/qea-julius-storage/evidence/quant-state-canary-views-20260821-r1/holdings/`;
- local-vol generic and `quant-state` views under the corresponding
  `/localvol/` root.

Those views were built from the same underlying task and component catalogs;
the arm contract and operational QRS interface are the controlled difference.
The prelaunch check should confirm the two catalog views are still paired and
that both optimize diagnostics are present. It does not need a new exhaustive
identity system.

## Fixed lifecycle and resource bound

Each admitted proposal follows the existing controller without a new search
scheduler:

```text
proposal
  -> official target gain
  -> one independent target repeat
  -> property-wise protection
  -> promote or rollback, then freeze
```

Failure to gain on target stops that lineage. Failure to repeat stops it before
protection. Only a repeated gain reaches protection, and only a strict
property-wise-safe protection result may promote. `ABSTAIN`, rejected `ACT`,
inactive components, rollback, and budget stop are retained outcomes rather
than setup failures.

Generic and QRS lineages reuse the exact same completed Quant-H0 comparator for
each family and stage. The live child therefore runs only the new candidate
arm. This gives zero new parent Workers and at most twelve candidate Worker and
verifier sessions: four arms times target, repeat, and protection. The fixed
lineage cap is USD 0.55 and the campaign cap is USD 2.20 before starting new
work; the four lineages use separate state directories so they may be launched
as independent services.

## Answer and sealed boundaries

Optimize answers and expected-versus-observed diagnostics may supervise only
the Evolver after a blind Worker attempt. They never enter the Worker prompt or
candidate as a task-specific expected-value patch. Protection is answer-free.

A0 contains no sealed task. If a candidate is eventually frozen for a sealed
evaluation, the sealed outcome is run once after the freeze and never returns
to candidate retrieval, selection, or QPR.

## QPR authority and the one narrow integration gap

QPR is not an alternative promotion rule in A0. It may be called only when an
answer-free protection comparison is prospectively classified as
`INCONCLUSIVE`. It may diagnose the quantitative mismatch and request at most
one paired confirmation, but it cannot promote. The terminal action from this
branch is `HOLD_FOR_REFINE`; the candidate remains available for later scope
work while Quant-H0 remains the incumbent.

The existing controller can execute the four ordinary proposal--target--
repeat--protection lineages now. Its QPR branch, however, consumes an already
materialized triage and Reviewer result; it does not create that result after
seeing a previously unknown live protection comparison. Therefore the frozen
JSON keeps QPR as a non-promoting protocol rule rather than setting
`quantitative_protection_review: true` prematurely. If a live A0 protection is
classified as the predeclared gray case, pause that lineage, materialize one
answer-free QPR record for the exact report, and resume through a small
continuation plan. This is the only execution gap, and it does not block the
ordinary strict property-wise A0 selection path.

## Execution and preflight

The existing command is sufficient for each independent lineage:

```bash
/home/julius/qea/runtime/venvs/rootless/bin/python \
  /data/qea-julius-storage/deploy/qf-a0-matched-20260823-r1/scripts/run_qfbench_lineage_controller.py \
  --plan /data/qea-julius-storage/deploy/qf-a0-matched-20260823-r1/data/breadth/QF_A0_MATCHED_GENERIC_QRS_PLAN.json \
  --state-dir /data/qea-julius-storage/runs/qf-a0-matched-generic-qrs-20260823-r1/a0-holdings-generic-controller \
  --lineage a0-holdings-generic \
  --approve-external-run
```

Use the same command with the matching lineage ID and a distinct controller
state-directory suffix for each of the other three services. Combine the four
frozen results only after the services stop; concurrent services must not
write the same `CONTROLLER-RESULT.json`. Before paid
launch, run the existing local/remote JSON and argument-construction preflight,
confirm the four evidence directories and six retained parent reports exist,
and confirm no previous result directory uses these run IDs. This is a fast
setup check, not a new experimental result.

## What counts as a useful result

Report each family and arm separately before any aggregate. The primary
observations are proposal/admission, component activation, predeclared relation
observation, official property or binary gain, repeat, protection failed-
property set, terminal decision, and requests/tokens/cost/time to the first
useful candidate.

A0 supports a QRS search-prior claim only if QRS changes a real retrieval,
routing, component, or verdict decision and does at least one of the following
without worse official target behavior: reaches an activated useful component
with less search work, realizes a relation correction missed by generic,
avoids an inactive or mislocalized intervention, avoids a protection
regression, or reaches a better-calibrated `ABSTAIN`. One unrepeated target
gain is not stability; one protection-safe repeated gain supports only this
two-family development panel. A0 is not a sealed, benchmark-wide, or
cross-benchmark result.
