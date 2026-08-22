# Thin Main-0 controller result

Date: 2026-08-22

## Decision

Retain the thin Main-0 controller as the lifecycle controller for the next
QFBench campaign. It is deliberately a fixed outer loop: the Evolver diagnoses
runtime evidence and proposes a harness candidate, while ordinary code owns
target evaluation, independent repeat, protection, promotion or rollback,
cost accounting, freeze, and resume. This hybrid division is consistent with
the controller structure used by the harness-evolution and quant-agent systems
screened for this project; it is infrastructure, not the quant-specific method
claim.

The controller is now ready for a bounded multi-lineage rehearsal. It is not
yet evidence for a complete autonomous campaign from Quant-H0 or for sealed
benchmark improvement.

## What was implemented

The minimal implementation consists of:

- `qea/qfbench_lineage.py`: a plain JSON state machine with
  `TARGET -> REPEAT -> PROTECTION -> PROMOTE/ROLLBACK -> FROZEN`;
- `scripts/run_qfbench_lineage_controller.py`: report ingestion, existing
  child-runner dispatch, property-set comparison, state saving, and resume;
- `data/breadth/QF_MAIN0_THIN_REPLAY_PLAN.json`: two retained lifecycle paths;
- `data/breadth/QF_MAIN0_THIN_LIVE_PLAN.json`: one real controller-owned
  protection child; and
- `data/breadth/QF_MAIN0_RELATION_APPLICABILITY.json`: the small public
  relation applicability and claim-boundary record for the two task families.

The controller does not introduce a second scheduler, database, or benchmark
implementation. It calls the existing component pilot and consumes its normal
`pilot-report.json` plus the adjacent trusted failed-property names. Eight
focused controller tests passed; the focused suite together with the existing
full-harness script tests passed 27 tests.

## Replay of both lifecycle decisions

The no-model replay consumed retained official reports and reproduced both
terminal paths:

| Lineage | Target | Repeat | Protection | Decision |
|---|---:|---:|---:|---|
| Holdings | 48/51 to 50/51 | 37/51 to 50/51 | 42/42 to 42/42 | `PROMOTE` |
| Local-vol | 65/68 to 68/68 | 66/68 to 68/68 | 38/39 to 38/39 with a failed-property swap | `ROLLBACK` |

The holdings replay accounted for 158 completed requests, 5,749,416 tokens,
and $0.577590464 from the three retained reports. The local-vol replay
accounted for 201 requests, 11,654,192 tokens, and $0.400868176. Running the
same controller state again did not duplicate costs, archive entries,
promotion, or rollback.

The local-vol path is important because aggregate equality alone would have
promoted it incorrectly. Quant-H0 failed `barrier_outputs_reasonable`, whereas
the candidate failed `vanilla_mc_close_to_surface`; the candidate therefore
changed the failed-property set and remained a rollback.

## Real controller-owned protection child

The live path imported the retained holdings target and repeat reports, then
the controller itself dispatched a new normal-budget comparison on
`brinson-sector-attribution`:

| Arm | Official reward | Properties | Failed properties | Component calls |
|---|---:|---:|---|---:|
| Quant-H0 parent | 1 | 42/42 | none | 0 |
| `holdings-qrs-v1` candidate | 1 | 42/42 | none | 1 |

The candidate called `reconcile_portfolio_deliverables` once. The tool found
that the Brinson task did not contain the target holdings-file deliverable set,
returned a grounded skip, and the Worker completed the ordinary attribution
checks. This establishes component reachability, task-applicability judgment,
and protection non-regression. It is not execution or reuse of the target
holdings relation on Brinson.

The controller observed aggregate and property-set safety, automatically
recorded `PROMOTE`, changed the current parent to `holdings-qrs-v1`, and froze
the lineage. The new live child used 16 completed requests, 167,113 tokens,
and $0.015420772. Including the retained target and repeat reports, the
controller accounted for 151 requests, 5,619,133 tokens, and $0.533176724,
below its $0.75 stage-start limit.

The successful service had zero restarts, retries, unreconciled requests,
active processes, containers, or Docker-network residue. A post-terminal
resume left the controller at `PROMOTE/FROZEN`, retained three accounted runs
and one archive entry, and did not modify or rerun the protection report.

## Observed setup repair

The first live service pointed the child runner at the incremental Main-0
deploy, which intentionally contained only the new controller files rather
than the existing component runner. It failed three service starts before any
Worker, container, or model request existed. The live plan was corrected to
use the existing full deploy and restarted from the saved `PROTECTION` phase.
This is retained as setup evidence: the repair did not alter the candidate,
scores, or decision rule, and the successful service itself had zero restarts.

## What this result supports

The retained claim is:

> A small fixed controller can consume retained target and repeat evidence,
> dispatch a real protection comparison, evaluate aggregate and property-set
> safety, account for cost, promote or roll back exactly once, freeze the
> lineage, and resume without repeating completed Worker work.

This closes the immediate lifecycle-engineering gap before a small concurrent
rehearsal. It does not establish:

- a fully autonomous proposal-to-freeze campaign from Quant-H0;
- matched quantitative-relation transfer for the holdings candidate;
- sealed or benchmark-wide performance improvement;
- general superiority over generic harness evolution; or
- that the controller itself is the quant-specific novelty.

The compact result is
`data/breadth/QF_MAIN0_THIN_RESULT.json`. Mirrored evidence is under
`results/bc-mirror/main0-thin-live-20260822-r1/` and
`results/bc-mirror/main0-thin-holdings-protection-live-20260822-r1/`.

## QuantCodeEval expansion boundary

Do not run the remaining 20 QuantCodeEval tasks before the QFBench Main-0
rehearsal. The current adapter intentionally supports the ten
credential-free public tasks: T01, T12, T16, T18, T19, T24, T26, T27, T28,
and T29. The remaining tasks depend on licensed WRDS panels, are rejected by
the current adapter, and the bc runtime has neither those panels nor an active
WRDS credential. A CUHK account is not itself the technical requirement; an
active WRDS entitlement and permitted dataset export are.

T28 and T29 still need materialization/parity work, while eight of the ten
credential-free tasks are already materialized. If additional breadth is
needed after Main-0, run one blind normal-budget Quant-H0 canary on T27 before
expanding the adapter. The licensed 20-task path is a later data-access and
benchmark-expansion decision, not a prerequisite for validating the present
search mechanism.

