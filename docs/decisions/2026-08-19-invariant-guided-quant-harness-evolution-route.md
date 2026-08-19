# Invariant-Guided Quant Harness Evolution Route

Status: accepted research-route revision, 2026-08-19. This record supersedes
the immediate emphasis of the same-day broad Quant Research Reviewer proposal.
It preserves the Reviewer as a supporting mechanism but narrows the next
quant-specific experiment to task-conditioned executable research invariants.
It does not report a new experiment result.

## Decision

Do not require a general Research State Graph, causal component mediation, or a
large diagnosis benchmark before the next mechanism canary. Harness-evolution
outer loops will naturally resemble AHE and Meta-Harness; the immediate domain
contribution should instead test whether quantitative-research invariants
provide a better feedback and search signal than trajectories and official task
scores alone.

The working method direction is:

> **Invariant-Guided Harness Evolution for Quantitative Research Agents.**

The Quant Research Reviewer remains optional support. Its first role is to
select and instantiate applicable invariants from the public task contract and
to choose a low-cost executable audit. It does not need to establish a complete
latent-state ontology or make a strong causal attribution claim.

## This direction predates the current story revision

The invariant idea is not newly introduced by this decision. Earlier work
already used public-definition fixtures and executable quant-invariant probes
to test quantity semantics, temporal windows, sign, portfolio relations, and
artifact behavior. The T12 continuation showed why the public definition must
bind the invariant: a free-form probe could pass across substantially different
official outcomes, while a task-grounded quantity binding produced the intended
property behavior in repeated Workers. Existing component history also
distinguishes registration, selection, activation, target outcome, repeat,
protection, and transfer.

The new decision is to promote this earlier mechanism into the main
quant-specific search hypothesis rather than treat it as one auxiliary probe or
one fixed failure class.

## Improvement has multiple evidence levels

Do not collapse harness improvement into whether the final answer is completely
correct. Record at least three levels separately:

1. **Invariant-level mechanism improvement:** a predeclared, applicable
   quantitative invariant changes from `FAIL` or `UNKNOWN` to `PASS` in a fresh
   Worker artifact, and the relevant component was actually used. This supports
   a mechanism result, not a benchmark solve.
2. **Official task improvement:** official property completion or task reward
   improves under the unchanged benchmark verifier. Only this supports a
   benchmark-performance claim.
3. **Stable or reusable harness improvement:** the effect repeats, preserves a
   declared protection task, or appears on a task with a matched invariant
   failure. This supports a stronger harness-capability claim.

An invariant transition without an official gain may still be useful evidence
that the component changed the intended Worker process, but it must be labeled
`mechanism_helpful`, not `benchmark_helpful`. Conversely, an official gain with
no predicted invariant change remains useful performance evidence but has
unresolved mechanism attribution.

## Quant Research Invariant Signature

For a public task, Worker trajectory, and final artifact, construct a small
task-conditioned signature:

```text
temporal_prefix_consistency    PASS / FAIL / N-A / UNKNOWN
future_data_invariance         PASS / FAIL / N-A / UNKNOWN
fit_scope_boundary             PASS / FAIL / N-A / UNKNOWN
quantity_relation              PASS / FAIL / N-A / UNKNOWN
portfolio_accounting           PASS / FAIL / N-A / UNKNOWN
cost_monotonicity              PASS / FAIL / N-A / UNKNOWN
artifact_fresh_replay          PASS / FAIL / N-A / UNKNOWN
```

This list is a library of possible invariant families, not a requirement that
every task run every check. The public contract determines applicability. A
task may also synthesize another invariant from the same public evidence. The
signature stores executable observations rather than treating a language
failure label as the root cause.

Useful invariant families include:

- temporal prefix consistency and future-data perturbation;
- preprocessing or estimator fit-scope boundaries;
- unit, scale, aggregation, and quantity metamorphic relations;
- signal, position, execution, exposure, and PnL accounting identities;
- transaction-cost monotonicity and simple stress relations;
- asset-order or irrelevant-universe perturbations when applicable;
- fresh-process replay of the final artifact.

## Invariant-conditioned component experience

An Evolver candidate should connect:

```text
observed invariant signature
    -> missing reusable Worker operation or policy
    -> selected or synthesized harness component
    -> component applicability condition
    -> predicted invariant transition
    -> predicted official outcome or protected behavior
```

Component history should be retrievable by invariant and task state, not only
by task ID or broad failure label. Record which invariant failures were present,
whether a component was selected and activated, which invariants changed, the
official outcome, and repeat, protection, or matched-transfer evidence.

The longer-term harness state may pair each component with an applicability or
routing condition. Temporal audit components should not burden artifact-only
tasks; portfolio validators should not activate on non-portfolio tasks. This
supports conditional reuse and limits component interference without requiring
one globally active collection of every discovered quant tool.

## Revised experiment path

Keep AP-2M unchanged. It tests whether the Evolver can choose one Worker
experiment and make a feedback-grounded second decision. After AP-2M, replace
the immediate broad Reviewer emphasis with two bounded invariant canaries:

```text
AP-2M warm-history autonomous-probe canary
    -> QI-1 task-conditioned invariant synthesis canary
    -> QI-2 invariant-guided component-search canary
    -> AP-3 H0 bootstrap using invariant feedback only if QI-1/QI-2 help
```

### QI-1: invariant synthesis

On a small panel of existing public tasks and known right/wrong artifacts,
ask the Reviewer or Evolver to select at most a few applicable invariants from
the public contract and materialize executable checks. Measure:

- applicability, including correct `N-A` decisions;
- whether the check distinguishes the intended wrong and right artifacts;
- whether the relation is grounded in public task semantics rather than a
  hidden answer;
- whether an observed result changes or narrows the diagnosis;
- calls, runtime, and cost.

This is a mechanism canary, not a calibration or generalization study.

### QI-2: invariant-guided search

On one unresolved optimize task, compare under the same Worker and Evolver
routes and bounded candidate budget:

- generic trajectory and official diagnostic evidence; and
- the same evidence plus an executable invariant signature.

The Evolver retains the full harness mutation surface. Compare component
relevance, actual activation, predicted invariant transition, official property
or reward change, protection where available, and Worker or verifier calls.

The minimum positive result is that invariant evidence changes the search in a
grounded way and produces the predicted invariant transition in a fresh Worker.
Official improvement is reported separately and remains the stronger result.

### AP-3 integration

Only if QI-1 produces useful task-conditioned checks and QI-2 improves search
or avoids an observed mislocalized intervention should AP-3 insert invariant
synthesis between its run-local H0 Worker and Evolver round one. Otherwise keep
the original generic AP-3 evidence path and preserve QI-1/QI-2 as negative
mechanism results.

## Paper positioning

Relative to AQuA-style systems, the project evolves the Quant Research Worker
harness rather than only research hypotheses, factors, models, or outputs.
Relative to AHE and Meta-Harness, the proposed quant-specific contribution is
the use of public, executable quantitative invariants as intermediate search,
routing, and cumulative-experience signals rather than a claim to have invented
the outer evolution loop.

The working question is:

> Can task-conditioned quantitative research invariants guide harness evolution
> more effectively than generic trajectories and sparse task outcomes alone?

The later faithful AHE or Meta-Harness-style baseline should match task evidence,
models, mutation surface, and budget. The immediate QI canaries only test
mechanism feasibility and should not be presented as that final comparison.
