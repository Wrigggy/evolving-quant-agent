# Autonomous component discovery with a paired repair probe

Status: accepted engineering protocol, 2026-08-18

## Current result and remaining gap

The QuantCodeEval T26 line has established three different facts that must not
be conflated:

- an autonomous Evolver produced and admitted a multi-surface harness component;
- a manually guided Worker artifact adopted the intended estimator semantics,
  but crashed and scored 3/17 because its implementation mixed monthly and
  daily row indices;
- an earlier quant-contract component reached 16/17 twice, while a trusted
  zero-model repair reached 17/17.  The fresh autonomous lineage has not yet
  produced an official binary reward improvement.

The next gap is therefore not another prompt-only search.  It is to determine
whether an autonomously discovered component helps a Worker diagnose and repair
a real artifact more effectively than its parent harness.

## AP-1 validation

AP-1 compares two short Worker runs:

1. Parent harness + the same failed T26 `strategy.py`.
2. Candidate harness + the same failed T26 `strategy.py`.

Both Workers receive the public T26 task, public data, the same answer-free
runtime symptom, and the same repair instruction.  Neither Worker receives
checker code, expected values, property verdicts, or a reference solution.
The coordinator may run the trusted verifier after each Worker finishes; those
results are evidence for the Evolver and experimenter, not Worker input.

The repair instruction asks the Worker to preserve correct work, reproduce the
failure, localize it, repair it, smoke-run the result, and save
`/app/output/strategy.py`.  A common low iteration limit is applied to both
harnesses so the comparison measures efficient use of the component rather
than unconstrained test-time compute.

## Interpretation

The component lifecycle is deliberately less strict than the benchmark claim:

- `activated`: the Worker actually invokes or follows the component;
- `repair-helpful`: it localizes or repairs the known runtime failure without a
  new severe regression;
- `efficiency-helpful`: it achieves at least as good a repair with fewer model
  calls, tokens, or elapsed time than the parent;
- `score-helpful`: it improves the trusted property count;
- `binary-helpful`: it reaches 17/17 and changes official reward from 0 to 1.

A component may be retained for refinement or composition when it is
repair-helpful even if it is not yet score-helpful.  An official benchmark
claim still requires score improvement, and a binary claim requires 17/17.

If the candidate is not activated or is no better than the parent on repair,
AP-1 stops before another from-scratch T26 run.  If it is repair- or
score-helpful, the next experiment is a fresh blind T26 Worker run followed by
an independent repeat on success.

## Deferred work

The progressive asynchronous scheduler remains a scaling direction, not part
of AP-1.  It should be implemented only after a component has demonstrated a
real repair or score benefit on this small paired experiment.
