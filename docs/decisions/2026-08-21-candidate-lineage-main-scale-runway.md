# Candidate-lineage runway to the main experiment

**Date:** 2026-08-21

**Status:** Accepted implementation direction; point-in-time refinement is live,
the scale controller and Main-0 rehearsal are not yet run

> **Same-day sequencing update:** preserve this runway, but do not implement or
> launch its broad Main-0 directly. The accepted next gate is to operationalize
> Quant Research State as a search prior and run the bounded mechanism canary in
> the [method specification](../superpowers/specs/2026-08-21-quant-research-state-guided-search-method-spec.md).
> After that result is retained, return here with a simplified controller and
> lineage terminology treated as infrastructure. The full rationale is in the
> [story backup](2026-08-21-evolving-the-quant-researcher-story-backup.md).

## Current position

The project is no longer blocked on whether an Evolver can produce a useful
finance component. Across four independent QFBench pairs, it produced three
executable candidates and one calibrated abstention. A normal-budget 13F
Worker loaded the autonomously written effective-state skill and improved from
the corrected retained 46/51 trajectory to 50/51. The local-vol lineage has a
separate fresh binary target gain, although that candidate failed protection.

The missing step is not a larger prompt or a longer single conversation. We
need to turn these bounded runs into a repeatable candidate-lineage controller
that can launch, resume, compare, promote, and stop without experimenter repair.

## Search unit and parent state

A material harness edit creates one candidate version. Each search lineage has
exactly one current parent:

```text
parent v0 -> candidate v1 -> measured decision -> promote v1 or retain v0
          -> candidate v2 -> measured decision -> promote v2 or retain parent
```

Worker calls are observations attached to a candidate version; they are not
called evolution rounds. Within one lineage, parent promotion is serialized so
that every score has an unambiguous comparator. Independent replicate lineages
may run concurrently, and eligible Worker evaluations within a lineage may run
concurrently.

## Fixed evaluation path for one candidate

1. The Evolver reads allowed optimize evidence, edits the current parent, and
   names one target whose outcome should discriminate its hypothesis.
2. The candidate passes the existing local smoke and admission checks.
3. A normal-budget, answer-blind Worker runs that target. The earlier short
   probes remain useful for activation and completion-distance diagnostics, but
   a zero-artifact short probe is not a score gate when the task normally needs
   many more turns.
4. A property or binary gain triggers one independent candidate repeat. A fresh
   parent comparator is added only when the cached comparator does not match the
   current parent and run contract.
5. A repeated gain triggers one matched protection task. Protection checks
   non-regression and records whether the component activated or made an
   evidence-grounded skip.
6. Only a repeat-confirmed, protection-safe candidate becomes the next parent.
   Neutral candidates can remain in the component research archive but do not
   silently enter the main harness.

This keeps numerical benefit as the promotion condition while still retaining
activation-only results as evidence about the search mechanism.

## How this avoids every-task evaluation

The controller caches a completed comparator by current parent version, task,
Worker route, and Worker budget. Rejected candidates do not invalidate that
cache. A parent promotion invalidates only the old parent entries. Therefore a
long-tail task is not rerun for every candidate merely to rediscover the same
parent score.

The Evolver still selects a target from the allowed optimize panel using the
declared quant mechanism and Research-State evidence. It does not see sealed
test results. Tasks that repeatedly reach full reward under the current parent
are removed from target selection and retained as low-frequency protection
sentinels. This is a scheduling rule, not a claim that full reward makes future
regression impossible.

## Parallel trajectories

The first main-scale controller will not merge several simultaneously mutated
branches into one parent. That creates attribution and conflict problems before
we need them. We instead parallelize two independent lineages and their Worker
evaluations. Within each lineage, promotions remain serial. A later composition
experiment may rebase two independently supported components and rerun their
two target checks, but composition is not a prerequisite for Main-0.

## Stable-scale gates

Before a headline run, Main-0 uses four already screened optimize/protection
pairs, two independent lineages, and at most six candidate versions per
lineage. It must demonstrate the whole operational path without manual command
repair:

- coordinator restart and resume preserve the current parent and completed
  observations;
- every run has one setup, candidate change, score, cost, runtime, and failure
  record;
- rejected candidates leave the parent unchanged;
- a positive target automatically schedules repeat and protection;
- a protection-safe candidate is promoted exactly once;
- the final parent is frozen before any sealed evaluation; and
- remote health monitoring, keep-awake, additive mirroring, and cleanup finish
  normally.

Main-0 is an engineering rehearsal. Its task scores remain useful measured
results, but it is not the main benchmark claim.

## Proposed Main-1 shape

After Main-0, preregister a workflow-lineage-separated panel with an initial 12
optimize tasks, six matched protection tasks, and 12 sealed test tasks. Run
three independent search lineages if the measured Main-0 cost and failure rate
support it. Fix the candidate-version, provider-cost, and wall-time caps before
launch. The provider may change between separately declared experiments, but
Quant-H0, baselines, and QEA must share one route inside a comparison arm.

The primary result is the frozen evolved harness versus Quant-H0 on official
sealed reward. Report per-task reward vectors and property counts alongside the
aggregate. Sealed results are collected after freeze and never returned to the
Evolver, retrieval store, or candidate selector.

The compact machine-readable runway is
[`data/breadth/QF_MAIN_SCALE_RUNWAY.json`](../../data/breadth/QF_MAIN_SCALE_RUNWAY.json).

## Immediate sequence

1. Finish the live point-in-time 50/51 feedback refinement and retain its
   decision, whether it refines, reuses, reverts, or abstains.
2. Implement the small lineage controller around the existing discovery runner;
   do not rewrite the Worker or verifier runtime.
3. Dry-run the controller with fake outcomes, then use the point-in-time branch
   as the first real positive-path candidate.
4. Run Main-0 over four screened pairs. Use its observed throughput and failure
   rate to finalize Main-1 task count, concurrency, and budget.

This record supersedes the blanket deferral of all selective scheduling after
the mechanism gate. It does not authorize using sealed outcomes for selection
or expanding directly to all 86 QFBench tasks.
