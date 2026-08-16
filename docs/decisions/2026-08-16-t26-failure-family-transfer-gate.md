# T26 Failure-Family Transfer Eligibility Gate

**Date:** 2026-08-16

**Status:** Accepted amendment

**Supersedes:** Treating T27 as an automatic transfer task in
[`2026-08-16-t26-answer-rich-evolver-experiment-design.md`](2026-08-16-t26-answer-rich-evolver-experiment-design.md)

## Decision

An improvement on a task outside T26 counts as positive component transfer only
when the source and destination baselines exhibit a matched failure mechanism.
Being in QuantCodeEval, sharing a finance domain, or failing a Type A/Type B
property is not enough.

The match is defined at the level at which one reusable component could
plausibly act on both tasks without storing either task's answer:

```text
semantic primitive or state
    + pipeline phase where it is mishandled
    + observable failure produced by that mistake
```

Examples include a public formula interpreted with the wrong units during
portfolio scaling, a temporal state used at the wrong fit/forecast phase, or an
end-to-end result inconsistent with the task's declared intermediate formula.
Two tasks need not use the same numerical formula, but the candidate must
implement the same abstract capability on both, such as task-conditioned
formula extraction plus independent reconciliation. A fixed HJ-metric repair
does not match a volatility-normalization task merely because both eventually
change Sharpe ratio.

## Current compatibility audit

### T26 — observed Worker failures

The retained shell-only T26 H0 scored 13/17. Its actual failed properties fall
into three mechanisms:

- training/CV temporal scope: a model-selection step likely consumes data
  outside the training window;
- model-selection objective semantics: the required HJ-metric residual and
  weighting formula is absent;
- end-to-end reconciliation: final strategy metrics disagree with the expected
  pipeline behavior.

The two candidate samples continued to fail the objective-semantics and
end-to-end mechanisms. The repeated candidate also lost an additional ridge-
objective property. These are measured failures, not categories inferred from
the task title.

### T19 — partially matched, already development data

The retained shell-only T19 H0 scored 16/18. Its two failures are:

- the normalization constant does not implement the declared volatility-
  matching formula;
- the end-to-end annual return and volatility do not reconcile with the
  intended pipeline.

T19 therefore matches T26 only when the proposed component is the broader
task-conditioned capability to extract a public mathematical contract, track
its scale/state, and independently reconcile the final pipeline. T19 does not
match a component specialized to HJ-metric CV, cross-sectional residual
weighting, or T26's training cutoff.

T19 has already affected candidate decisions and remains development/
protection data. It can localize a matched formula-semantics mechanism or catch
regression, but it is not sealed transfer evidence.

### T27 — source-compatible but failure compatibility unmeasured

The official T27 contract contains properties for future-data access, causal
consistency, temporal ordering, frequency alignment, signal delay, transaction
timing, exact predictive formulas, and end-to-end metric consistency. This
makes it a plausible source-level match for a task-conditioned temporal or
formula-reconciliation component.

No blind T27 Worker H0 has been run. Its official golden 18/18 result validates
the runtime and checker, not the failure behavior of the Worker. Therefore T27
is currently an **unconfirmed transfer candidate**, not a confirmed matched
task.

## Eligibility procedure

Before spending a candidate Worker on any transfer task:

1. Name the source component's predicted failure mechanism from observed T26
   failures and the Evolver's component hypothesis.
2. Obtain or reuse a blind H0 Worker result for the proposed destination task.
3. Map both failures using the three fields above: semantic primitive/state,
   pipeline phase, and observable.
4. Record whether the same candidate component is reachable and expected to
   act in both tasks without task constants.
5. Run the unchanged candidate only when the match is positive.

If the destination H0 passes the relevant mechanism, it may be used as a
preservation/protection task, but cannot demonstrate an improvement on that
mechanism. If it fails only an unrelated mechanism, do not spend the candidate
call and select another task with a measured matching H0 failure.

This is a small eligibility table in the experiment record, not an exhaustive
failure ontology or a new defensive subsystem.

## Amendment to the T26 live sequence

The T26 target and repeat gates remain unchanged. After a repeated improvement:

1. T19 may still be run as an answer-free protection task regardless of
   failure-family match.
2. T19 counts as matched mechanism evidence only if the new component targets
   task-conditioned formula/scale reconciliation rather than a T26-specific HJ
   or CV operation.
3. Run the T27 shell-only H0 before the T27 candidate.
4. Classify the T27 H0 failure without exposing its expected answers to the
   Evolver.
5. Run the unchanged candidate only if the predeclared component mechanism and
   observed T27 failure match. Otherwise stop T27 and choose another task.

The maximum paid path remains six model executions because the planned T27 H0
was already part of the prior budget. The change is that the T27 candidate call
is now conditional on failure-family compatibility rather than automatic.

## Claim boundary

A candidate that improves T26 and preserves unrelated tasks is
`protected_candidate`. A candidate becomes `reusable_candidate` only after it
improves or repairs the same abstract failure mechanism on a different task
using unchanged component code. Merely preserving a solved task, changing an
unrelated score, or sharing the generic `A10` label is not positive transfer.

No model call or benchmark run is launched by this amendment.
