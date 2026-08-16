# Transfer-First Search and Closed-Benchmark Fallback

**Date:** 2026-08-16

**Status:** Accepted research path

**Scope:** QuantCodeEval first; applicable to QFBench after a working mechanism is localized

**Related decision:**
[`2026-08-16-answer-rich-evolver-and-task-conditioned-harness.md`](2026-08-16-answer-rich-evolver-and-task-conditioned-harness.md)

## Decision

QEA will begin with a strict reusable-transfer experiment, but it will not make
held-out improvement an indefinite blocker to learning a useful benchmark
optimizer. If repeated, activated component interventions improve held-in tasks
but do not transfer, the project may deliberately move to a closed-benchmark
objective. The claim must change when the objective changes.

The path has three levels:

| Level | Search unit | What may guide search | Final artifact | Valid claim |
|---|---|---|---|---|
| A. Reusable transfer | one shared harness component | answer-rich optimization evidence plus answer-free protection | one shared harness | measured task transfer within the benchmark; broader finance generalization still unproven |
| B. Closed-benchmark shared harness | one shared harness for the full benchmark | outcomes from every benchmark task may become adaptive development evidence | one benchmark-wide harness | higher adaptive/full-corpus benchmark performance at a stated budget; no held-out generalization claim |
| C. Per-task test-time discovery | a separate search lineage for each task | that task's runtime feedback | a portfolio of task-conditioned solutions or harness states | stronger task-solving performance under test-time compute; no reusable-harness claim |

Level B is not described as held-out evaluation after its task outcomes have
affected search. Level C is not described as harness generalization. Both can
still be practically valuable and scientifically reportable when compared with
matched-compute baselines.

## Why start with Level A

The current method hypothesis is stronger than “spend more attempts on each
task.” It asks whether an Evolver can turn a scored failure into a component
that changes a fresh blind Worker's behavior on another task. A positive result
would support reusable harness learning and would be more informative than an
aggregate score alone.

A within-benchmark transfer split does not prove universal quant or finance
generalization. It is an internal transfer test. Cross-benchmark tasks, live
workflows, and later sealed tasks would be needed for broader claims.

## When to move from A to B

Do not switch because one candidate is noisy. Switch after two genuinely
different component hypotheses have each completed the following path:

1. legal Evolver decision and an admitted, reachable component change;
2. observed activation in a fresh blind Worker;
3. positive target result followed by an independent target repeat;
4. unchanged-code answer-free protection and transfer measurement.

If the repeated target gains are real but answer-free transfer remains null or
negative across both component hypotheses, record reusable transfer as a
negative result for this setup and make the full QuantCodeEval corpus adaptive
development data. This is a practical engineering switch condition, not a
statistical theorem.

If the target gains themselves do not repeat, remain at Level A and improve
component discovery, evidence quality, or stability rather than blaming the
transfer split.

## When to move from B to C

Level B keeps the scientifically interesting constraint of one shared harness.
Move to per-task lineages only after measured task interference makes that
constraint counterproductive: for example, two admitted component attempts
improve their source task but consistently damage distinct task families even
after routing or composition is tried.

At Level C, task-specific plans and code are allowed because the objective is
explicitly the best result for each task. Reusable component cards may still be
mined from the trajectories, but they are a secondary artifact rather than a
promotion requirement.

## Comparisons and reporting

For Levels B and C, report an anytime curve rather than only the best final
score:

- benchmark score versus model requests, verifier calls, cost, and wall time;
- incumbent score after every accepted or rejected intervention;
- valid-artifact and completed-evaluation rates;
- per-task outcomes so an aggregate gain cannot hide broad regressions;
- the exact feedback available to Evolver and Worker.

The smallest useful matched-budget comparisons are:

- the unchanged seed harness;
- independent best-of-N Worker attempts;
- sequential task-solution refinement with the same feedback budget;
- QEA shared-harness evolution;
- QEA per-task discovery only if Level C is activated.

This follows the useful distinction in
[Learning to Discover at Test Time](https://arxiv.org/abs/2601.16175): a
problem-specific discovery policy may optimize a solution without claiming
that the adapted policy transfers. It also preserves the shared-harness and
regression-testing question emphasized by
[Self-Harness](https://arxiv.org/abs/2606.09498) while that question remains
empirically productive.

## Immediate experiment

Remain at Level A. Run the T26 answer-rich Evolver experiment specified in
[`2026-08-16-t26-answer-rich-evolver-experiment-design.md`](2026-08-16-t26-answer-rich-evolver-experiment-design.md).
The immediate goal is to learn whether answer-bearing diagnostics let the
Evolver abstract and stabilize a reusable component, not to establish a final
QuantCodeEval score.

No paid or benchmark run is launched by this decision record.
