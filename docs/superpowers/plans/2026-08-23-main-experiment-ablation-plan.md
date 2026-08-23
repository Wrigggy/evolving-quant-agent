# Main-experiment ablation plan

Date: 2026-08-23
Updated: 2026-08-24

## Objective

Use the smallest set of ablations that identifies QEA's proposed mechanism:
Quant Research State reconstruction, relation-conditioned experience reuse,
and property-wise intervention verification. Do not enumerate the six states
or every harness file. The fixed lifecycle controller is infrastructure and is
not an ablation treatment.

The comparison unit is now a **cumulative from-Quant-H0 campaign**. Generic and
QRS each maintain their own official incumbent while traversing the same frozen
task-family order. A family-level Worker call is an observation inside that
campaign, not an independent evolution replicate. The retained two-family A0
result remains a matched mechanism-localization canary; it is not relabeled as
a cumulative main-campaign replicate.

The design follows the useful pattern in prior systems: ablate the claimed
search operation or evidence interface rather than every implementation file.
AHE reports final-harness component ablations; Meta-Harness ablates proposer
evidence depth; TTT-Discover separates training signal from reuse; MLEvolve
ablates retrospective/global memory; QuantaAlpha ablates its trajectory-search
operators; and R&D-Agent-Quant compares research scheduling policies under a
matched budget. Primary sources:

- AHE: https://arxiv.org/html/2604.25850v4
- Meta-Harness: https://arxiv.org/html/2603.28052
- TTT-Discover: https://arxiv.org/pdf/2601.16175
- MLEvolve: https://arxiv.org/html/2606.06473
- QuantaAlpha: https://arxiv.org/html/2602.07085v3
- R&D-Agent-Quant: https://arxiv.org/html/2505.15155

## A0: Full QRS versus matched generic cumulative campaigns

Priority: P0; required for the main paper.

Treatment difference:

| Surface | Full QRS | Matched generic |
|---|---|---|
| Quant-H0 Worker and six high-level state names | same | same |
| Current runtime trajectory and optimize diagnostic | same | same |
| Raw candidate/component history | same | same |
| Model, budget, mutation surface, Worker and verifier | same | same |
| Frozen task-family order | same | same |
| Initial official incumbent | Quant-H0 | Quant-H0 |
| Later official incumbent | own promoted harness | own promoted harness |
| Operational State Card | enabled | not required |
| Relation-conditioned retrieval and routing | enabled | unavailable |
| ACT bound to state/relation/component locus | required | generic causal ACT |

The generic arm remains a strong full-harness Evolver. It may freely inspect
the same history and infer finance mechanisms; it is not restricted to prompt
mutation or given a smaller context.

Both methods begin with the same frozen initial history snapshot and the same
Quant-H0. After the first proposal, their promoted components and runtime
episodes may differ; that divergence is part of the end-to-end treatment. The
family order, candidate opportunity, conditional repeat/protection gates,
model routes, answer policy, and stage-start budget remain matched. An
activated but non-promoted search parent may support at most one predeclared
within-family refinement; it does not carry into the next family unless a
repeat-confirmed, property-safe candidate updates the official incumbent.

Question:

> Does operational QRS provide an incremental domain search prior beyond
> generic access to the same quant runtime evidence?

Primary metrics are task-level official binary/property gain, useful-candidate
rate, ACT-to-activation, ACT-to-predeclared-relation correction, protection
property regression, calibrated ABSTAIN, and requests/cost to the first useful
candidate. A useful candidate requires fresh Worker activation, at least one
predeclared relation observation, and no official regression; benchmark-helpful
additionally requires an official property or binary gain.

Paper target: four frozen QFBench task families spanning at least three public
quantitative relation families, with two independently initialized cumulative
campaign seeds per method when budget permits. Full-QRS campaigns are the
main-method runs, not duplicated ablation runs. The immediate bounded canary is
QFBench-only. QuantCodeEval breadth can be added later under the same frozen
contract, but licensed or unfinished QCE coverage does not block this
mechanism-scale campaign. With only one campaign seed per method, report a
bounded system canary rather than a stable superiority estimate.

## Campaign and frozen-evaluation boundary

Each campaign follows one fixed outer sequence:

```text
Quant-H0
  -> fixed family 1: propose / conditional refine / repeat / protection
  -> fixed family 2: propose / conditional refine / repeat / protection
  -> fixed family 3: propose / conditional refine / repeat / protection
  -> fixed family 4: propose / conditional refine / repeat / protection
  -> freeze the final official incumbent
  -> frozen no-feedback evaluation
```

Every optimize target, repeat, protection task, and diagnostic that can change
the incumbent is development evidence. Protection is a selection guard, not an
out-of-sample result. The final panel is workflow-lineage separated, scheduled
only after all compared incumbents are frozen, and never returned to the
Evolver, history store, task selector, or promotion rule. If prior project
exploration means a panel is not globally untouched, describe it as
**frozen no-feedback evaluation**, not pristine OOS.

## A1: Experience decomposition

Priority: P1; run after A0 on two history-rich tasks.

Use one three-arm block:

| Arm | State Card | Current task evidence | Prior episodes | Retrieval |
|---|---:|---:|---:|---|
| Full QRS | yes | yes | yes | state/relation/component-conditioned |
| QRS-unconditioned | yes | yes | yes | generic similarity/recency |
| Cold QRS | yes | yes | no | none |

The unconditioned arm keeps the same episode-count and approximate evidence
budget; only the retrieval coordinates change. Cold QRS removes accumulated
candidate/component outcomes but retains the current failed Worker trajectory
and optimize diagnostic. This separates the value of accumulated runtime
experience from the value of QRS-guided reuse.

Questions:

1. Does relation-conditioned retrieval find more applicable past interventions
   than generic history access?
2. Does accumulated positive, negative, inactive, and unstable runtime
   experience improve proposals beyond the current task trajectory alone?

Metrics add repeated-known-failure rate, inactive/mislocalized component rate,
episode use in the Evolver's decision, and relation/component-locus stability.

Paper target, if this causal history claim is retained: two family boundaries
from the cumulative campaigns, each with at least one positive and one
negative/inactive historical episode. Reuse the Full-QRS campaign paths and add
only the matched unconditioned/cold proposal paths. If this ablation is skipped,
limit the claim to the measured ability to use runtime history for refinement;
do not claim that history itself improves search.

## A2: Property-wise versus aggregate-only protection

Priority: P0; offline and nearly free.

Replay every retained protection report under two policies:

- full: reward/count non-regression plus candidate failed-property set being a
  subset of the parent failed-property set; and
- ablated: reward and aggregate property count only.

Report policy disagreement and aggregate-only false promotions. The minimum
discriminating panel already exists:

- holdings: 42/42 to 42/42 with no failed properties, safely promoted; and
- Search-v2 local-vol: 38/39 to 38/39 with a failed-property swap, rolled back
  only by the property-wise policy.

This ablation supports the verification claim that scalar or aggregate ties
can hide a quantitative research-object regression. It does not establish QRS
search superiority and requires no new model call.

## A3: Primary plus residual relation versus primary only

Priority: P2 unless a second genuine task family supports an independent
residual risk before launch.

Hold State Card, history, primary relation, routing, mutation surface, model,
budget, and protection fixed. Remove only residual-relation selection,
retrieval, activation instruction, and completion verification.

Question:

> When evidence shows a primary correction can leave an orthogonal terminal or
> artifact-coverage risk, does one optional residual relation improve coverage
> without disproportionate cost or protection regression?

Metrics separate primary correction, residual correction, terminal/artifact
coverage, official outcome, edit size, additional cost, and protection safety.
Only run a paper ablation if at least two tasks prospectively support two
nonredundant public relations. Otherwise retain the local-vol Search-v2 result
as a single-task mechanism canary and do not manufacture a residual slot.

## Deferred or rejected ablations

Do not run in the current submission sprint:

- removing the six Research States one by one;
- removing every relation family one by one;
- prompt/tool/middleware/skill combination enumeration before a final harness
  actually retains several components;
- controller on/off;
- random/LLM/bandit scheduling before scheduling becomes a method claim;
- Reviewer/certificate on/off after its neutral canary;
- best-of-N for every candidate; or
- a score-only/summary/raw-trace replication unrelated to QEA's central claim.

If the final frozen harness contains several independently retained components,
add one AHE-style final-component contribution audit after the main experiment.
It is not a prerequisite for Main-0B.

## Execution order

1. Retain the completed A2 offline replay as the verification-policy ablation.
2. Freeze the QFBench family order, relation-applicability record, initial
   history snapshot, matched budgets, and answer boundary.
3. Run matched Generic and Full-QRS cumulative campaigns from Quant-H0; do not
   count family-level observations as independent campaign seeds.
4. Add A1 only if the paper claims a causal benefit from accumulated history.
5. Run A3 only if source screening finds a second genuine residual-risk task.
6. Freeze every final official incumbent before the no-feedback panel; sealed
   outcomes never select, refine, or rank candidates.
