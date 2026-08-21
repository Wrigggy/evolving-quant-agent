# Search-v2 and pre-main gates

Date: 2026-08-21

## Decision

Proceed with one bounded Search-v2 canary. Do not start Main-0 or Main-1 from
this decision.

The quant-specific method contribution is not the outer harness-evolution
loop, the six state names, or the candidate-lineage machinery. It is the use of
task-conditioned quantitative relations to reconstruct a Research State
mismatch, retrieve component experience, localize an intervention, and define
its scope. The six Research States are open coordinates. Activation, relation
change, official outcome, and repeated scope are evidence levels rather than a
new optimization algorithm.

Search-v2 adds one optional residual-risk relation to the existing primary
intervention relation. The residual is selected only when task-local evidence
supports an orthogonal risk that primary success would not settle. It is not a
mandatory checklist entry or a closed finance failure taxonomy.

## Why this revision is needed

The first matched canary showed that one selected relation can locate a real
defect but still be too narrow. The local-vol quant-state candidate corrected
its selected SVI admissibility relation while leaving a forward-variance
relation unresolved. The generic candidate initially covered both but did not
repeat its full score. Holdings produced a repeated property gain and safe
protection, but the component skipped on protection rather than executing the
same reconciliation relation.

The next question is therefore not whether a longer prompt helps. It is:

> Can one primary quantitative relation plus at most one evidence-supported
> residual-risk relation produce a better-scoped candidate whose relation is
> actually exercised on a matched second task?

## Story gate before Main-0

The paper can defend the following minimum contribution:

> Quantitative Research States are operationalized as a task-conditioned search
> representation for full-harness evolution. Expected and observed state are
> connected through public quantitative relations to component experience,
> intervention scope, and activation--relation--outcome evidence.

Before Main-0, four gates remain:

1. **Task coverage.** Source-screen the proposed Main panel before adaptive
   search. Most mechanism-analysis tasks must admit at least one public,
   observable quantitative relation across at least three relation families.
   Tasks with only generic artifact completion may remain evaluation tasks but
   do not support the quant-specific mechanism claim.
2. **Matched treatment.** Strong generic and quant-state Evolvers receive the
   same tasks, evidence, history, model routes, mutation surface, candidate
   budget, explicit component-use experiment contract, and evaluation gates.
   The treatment is relation reconstruction, relation-conditioned retrieval
   and routing, and primary-plus-residual coverage.
3. **Domain-specific observation.** Search-v2 must obtain a repeatable binary
   gain, a second repeatable mechanism-family property gain, or genuine
   execution of the selected relation on a pre-screened second task. A
   component skip is scope safety, not reuse.
4. **Lifecycle rehearsal.** A thin controller must complete proposal, target,
   conditional repeat, conditional protection, promote or rollback, and resume
   once without experimenter stage repair. This is an engineering gate, not
   the quant novelty.

## Search-v2 task pair

Target: `corporate-action-adjustment`.

Matched second task: `momentum-backtest`.

Both public tasks require an adjusted-price state to propagate through an
event-time boundary. They share two independently testable relations:

- `adjusted_price_basis_consistency` is the primary relation. Prices, volume,
  cash flows, signals, execution prices, valuation, and summaries must use the
  price/share basis declared by the task. Corporate actions bind split and
  dividend adjustment; momentum binds `adj_close` for signal/valuation and
  `adj_open` for execution.
- `event_to_execution_time_alignment` is the residual-risk relation when
  supported. Corporate-action adjustments apply only before the declared
  action boundary, including prior-trading-day handling. Momentum signals at
  date t execute on the next trading day's adjusted open, except for the
  declared final close.

Correct basis does not imply correct event timing, and correct timing does not
imply correct adjusted/raw price usage. The relations are therefore
orthogonal. On the matched task, actual relation execution requires a callable
component observation or an explicit pre-delivery workflow audit of both basis
and event timing. Prompt presence, full score, or a grounded skip alone is not
reuse evidence.

This is within-panel reuse evidence, not unseen-task or sealed generalization:
both trajectories are authorized coordinated evidence for the Evolver.

## Matched arms and gates

Run two proposal arms from the same Quant-H0 and evidence bundle:

- strong generic full-harness diagnosis; and
- quant-state-v2 with the primary relation and optional residual-risk relation.

Do not dispatch the known-unrepresentative short Worker probe. Each admitted
candidate instead enters the same normal-budget path:

```text
concurrent target with Quant-H0
    -> if official property or binary gain and predicted relation observation
independent repeat with a fresh Quant-H0 comparator
    -> if the same directional gain repeats
matched second task with a fresh Quant-H0 comparator
```

The matched-task gate requires non-regression and actual observation of the
declared relation. A skip may establish safety but does not satisfy reuse.

Hard limits for the canary:

- two Evolver proposal sessions;
- two candidate versions;
- at most nine normal-budget Worker sessions;
- at most nine official verifier executions;
- no additional refinement round;
- provider-cost cap of $0.75 before starting a new stage; and
- campaign wall-time cap of six hours.

If neither candidate improves the target, stop. If improvement does not repeat,
stop that arm. Do not run the matched second task for a failed repeat.

## Scale readiness after Search-v2

The bottom runtime is ready for this canary: task attempts are isolated,
Worker and verifier results resume independently, completed attempts are
reused, cost is recorded, and two run namespaces may execute concurrently.
The repository does not yet contain the Main-0 candidate-lineage controller.

Before Main-0, implement only a small JSON-backed state machine:

```text
PROPOSE -> TARGET -> REPEAT -> PROTECTION -> PROMOTE
                    \-> ROLLBACK on any failed gate
```

It needs one current parent, one active candidate, child run references,
stage-boundary cost checks, a simple parent-task comparator cache, and resume
that reads completed child reports. It does not need branching, DAG merge,
open-ended Worker calls, RAG, a general scheduler, a Reviewer, distributed
leases, or a database.

Main-0 should be reduced to two screened pairs, two lineages, and at most two
candidate versions per lineage: one live promote path and one rollback path.
Main-1 panel size remains proposed until Main-0 measures cost and long-tail
wall time.

Compact preregistration:
`data/breadth/QSTATE_SEARCH_V2_PLAN.json`.
