# Main-experiment ablation plan

Date: 2026-08-23

## Objective

Use the smallest set of ablations that identifies QEA's proposed mechanism:
Quant Research State reconstruction, relation-conditioned experience reuse,
and property-wise intervention verification. Do not enumerate the six states
or every harness file. The fixed lifecycle controller is infrastructure and is
not an ablation treatment.

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

## A0: Full QRS versus matched generic

Priority: P0; required for the main paper.

Treatment difference:

| Surface | Full QRS | Matched generic |
|---|---|---|
| Quant-H0 Worker and six high-level state names | same | same |
| Current runtime trajectory and optimize diagnostic | same | same |
| Raw candidate/component history | same | same |
| Model, budget, mutation surface, Worker and verifier | same | same |
| Operational State Card | enabled | not required |
| Relation-conditioned retrieval and routing | enabled | unavailable |
| ACT bound to state/relation/component locus | required | generic causal ACT |

The generic arm remains a strong full-harness Evolver. It may freely inspect
the same history and infer finance mechanisms; it is not restricted to prompt
mutation or given a smaller context.

Question:

> Does operational QRS provide an incremental domain search prior beyond
> generic access to the same quant runtime evidence?

Primary metrics are task-level official binary/property gain, useful-candidate
rate, ACT-to-activation, ACT-to-predeclared-relation correction, protection
property regression, calibrated ABSTAIN, and requests/cost to the first useful
candidate. A useful candidate requires fresh Worker activation, at least one
predeclared relation observation, and no official regression; benchmark-helpful
additionally requires an official property or binary gain.

Paper target: three optimize tasks, at least two relation families and both
benchmarks, two Evolver proposal seeds per arm: 12 proposal sessions. Full-QRS
sessions are the main-method runs, not duplicated ablation runs.

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

Paper target: two tasks from distinct relation families, each with at least one
positive and one negative/inactive historical episode, two proposal seeds per
arm. This is 12 sessions, of which four Full-QRS sessions are reused from A0;
the incremental budget is eight proposals plus only admitted Worker paths.

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

1. Complete A2 immediately by offline replay of retained protection cases.
2. Use A0 Full-QRS runs as the main-method runs and add only the matched generic
   arms.
3. Select two history-rich A0 tasks for A1.
4. Run A3 only if source screening finds a second genuine residual-risk task.
5. Freeze the selected harness before any sealed final evaluation.

