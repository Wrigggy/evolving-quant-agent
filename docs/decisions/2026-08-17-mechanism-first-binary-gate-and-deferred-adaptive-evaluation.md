# Mechanism-First Binary Gate and Deferred Adaptive Evaluation

**Date:** 2026-08-17

**Status:** Accepted experiment direction; not yet implemented or run

**Scope:** QuantCodeEval mechanism completion, followed by a frozen from-zero
evaluation

**Supersedes:** The proposal to implement a progressive asynchronous scheduler
before completing the current mechanism experiment. It does not supersede the
answer-rich Evolver / blind Worker boundary or the Level-A-to-Level-B fallback.

## Decision

QEA will finish the small-scale discovery mechanism before building a
large-panel evaluation scheduler. The immediate experimental gate is an
official task-level binary improvement: an Evolver-produced harness must move
at least one optimization task from official reward `0` to `1` with a fresh
blind Worker.

The repeated T26 `16/17` result remains positive component and property-level
evidence, but it does not satisfy this binary gate. T26 remains the immediate
answer-rich optimization task. The Evolver may use the retained r2/r4 A10
expected-versus-observed diagnostics, candidate history, component traces, and
prior edits; the Worker remains blind. The mutation surface remains the full
harness, and the Evolver may refine, replace, or compose multiple components.

Do not implement a new progressive, asynchronous, or cost-aware scheduler
before this gate. For the current mechanism experiment, use the simplest useful
sequence:

```text
retained T26 history
    -> Evolver component revision
    -> local component smoke
    -> one fresh blind T26 Worker
    -> official result and answer-rich diagnostic returned to Evolver history
    -> another revision only when needed
```

Search length is evidence-driven rather than fixed at five rounds. Every round
retains the candidate change, execution evidence, official property result,
cost, and failure lesson. A first `17/17` result triggers an independent blind
Worker repeat. Protection and transfer are evaluated only after an official
binary success rather than on every intermediate candidate.

## Answer visibility and final evaluation

Answer exposure is split by experimental role rather than prohibited
universally:

- a declared optimization task may provide answer-rich post-run diagnostics to
  the Evolver;
- no answer is provided to the Worker;
- a final test task does not provide answers or scores to candidate selection
  before the harness is frozen;
- if every benchmark task is made answer-rich adaptive evidence, the setup is
  Level B closed-benchmark optimization and those tasks are no longer described
  as an unseen test set.

After the binary mechanism gate, freeze the method and run a fresh lineage from
a shell-only H0 through optimization evidence, Evolver search, candidate
selection, and blind Workers. The primary final success condition is an
improvement in official task-level binary reward on the declared test set. The
property vector remains a diagnostic and attribution measure, not a substitute
for that final official gain.

## Deferred large-scale evaluation design

The earlier L0-L4 idea is retained only as a future scale-up hypothesis. These
levels describe how deeply to evaluate one candidate; they are not Evolver
iterations:

- L0: local component smoke and reachability;
- L1: one relevant optimization-task Worker;
- L2: an independent optimization-task repeat;
- L3: protection or matched transfer;
- L4: the frozen final test panel.

When task breadth makes evaluation cost a measured bottleneck, the early
L0-L2 cycle should not necessarily be a fixed coordinator pipeline. The
Evolver may be given a budgeted evaluation action that lets it decide when a
candidate is ready for a benchmark call, which allowed optimization task is
most informative, and whether an independent repeat is worth the cost. L0
itself remains local; the Evolver's decision concerns promotion from local
testing to L1/L2 benchmark execution.

The coordinator would remain responsible only for executing allowed requests,
enforcing the declared budget and task roles, and recording the returned
evidence. This could turn evaluation choice into part of bidirectional search:
the Evolver selects a task because its outcome discriminates between competing
component hypotheses, not merely because the task is next in a fixed list.

This adaptive evaluation policy is **proposed and not tested**. Do not build it
until the current binary mechanism works and broader task runs demonstrate
that long-tail evaluation is the active bottleneck.

## Gates and claim boundaries

Record the following separately:

1. `property_mechanism_positive`: a component activates and repeatedly repairs
   predicted properties. The current T26 `16/17` repeat satisfies this.
2. `binary_mechanism_positive`: a fresh blind Worker moves an optimization task
   from official reward `0` to `1` after an Evolver-produced harness change.
3. `binary_mechanism_repeated`: an independent blind Worker repeats the
   official success. One success followed by a failure is reported as unstable.
4. `frozen_test_positive`: after a fresh from-zero lineage with the method
   frozen, the selected harness improves official binary reward on the declared
   test set relative to the matched H0.

Do not treat property progress as official task completion, and do not treat an
answer-rich optimization success as unseen-test improvement. Conversely, do
not discard the current T26 trajectory: it is valid mechanism-development
evidence and supplies the failure history needed for the next autonomous
component revision.

## Immediate next experiment

Continue T26 from the retained admitted candidate and answer-rich A10 history.
Let the Evolver choose the component locus and whether to refine, synthesize, or
compose; do not prescribe a numeric-reconciliation implementation as the
answer. Run one fresh blind T26 Worker for each admitted revision. On the first
official `17/17`, run one independent blind repeat, then protection and matched
transfer as warranted.

No scheduler implementation, paid model call, Worker run, or benchmark run is
authorized or launched by this documentation update.
