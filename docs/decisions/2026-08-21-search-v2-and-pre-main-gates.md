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

Launch preflight rejected the initially proposed
`corporate-action-adjustment` target. Its historical 3/7 outcome preceded two
evaluator-integration repairs; corrected replay made that low-score screen
invalid. It is not used as V2 search evidence.

The superseding target is `dupire-local-vol` and the matched second task is
`localvol-barrier`. Both public tasks propagate a fitted implied-volatility
surface through maturity to local-volatility quantities and downstream
pricing. They share two independently testable relations:

- `calibration_parameter_admissibility` is the primary relation already
  selected by the prior quant-state candidate. The fitted surface parameters
  must remain strictly inside the public admissible region before the surface
  is differentiated or delivered.
- `forward_variance_maturity_consistency` is the residual-risk relation when
  supported. Total variance must evolve consistently across maturities so that
  forward variance and the derived at-the-money local volatility remain finite
  and positive, including the terminal maturity row.

An admissible parameter vector does not imply a valid maturity derivative, and
a positive forward-variance path does not imply admissible fitted parameters.
The prior quant-state Worker provides the discriminating observation: it fixed
the selected admissibility relation but still delivered a terminal
`local_vol_atm` missing value and scored 67/68. Both proposal arms receive that
same prior candidate, trace, official score, and Evolver-only optimize
diagnostic. On the matched task, actual relation execution requires a callable
component observation or explicit pre-delivery audit of both parameter bounds
and maturity propagation. Prompt presence, a full score, or a grounded skip
alone is not reuse evidence.

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
