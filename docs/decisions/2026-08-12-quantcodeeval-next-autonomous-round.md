# QuantCodeEval next autonomous full-harness round

> Date: 2026-08-12
>
> Status: accepted next experiment direction; not yet launched

## Objective

Find a QuantCodeEval-specific evolution mechanism that actually improves the
two-task engineering canary. The immediate target is to preserve T16 while
making T24 reliably deliver `strategy.py`; quant correctness is evaluated after
artifact delivery works. This is mechanism discovery, not a paper result.

## Evolver authority

The Evolver receives the answer-free r1, r4, r5, and r6 histories and an open
full-harness workspace. It may inspect, edit, bind, and test prompt, tools,
validator, middleware, memory, routing, skills, and agent configuration. It may
change several files when they implement one coherent mechanism.

The investigator will not prescribe an artifact finalizer or completion
middleware. That remains an investigator hypothesis. The Evolver must choose
the component, propose the mechanism, implement it, and design the local smoke
that tests the component state it intends to change.

## Search and selection

- The search is variable length, not fixed to five rounds.
- The published H0 score is reused rather than rerun in the first round.
- Every later round can inspect prior rejected edits, ineffective edits,
  successful local tests, admission results, and answer-free task outcomes.
- A candidate first runs its own focused component smoke, then independent
  admission, then the T16/T24 panel.
- A candidate that improves diagnosis or artifact delivery without beating H0
  may be retained as a diagnostic search parent, but it is not promoted to the
  official incumbent.
- The outer loop stops when the target is reached, repeated rounds add no new
  information, the Evolver identifies a concrete operator gap, or the agreed
  request and cost budget is exhausted.

## Fast execution order

1. Run focused deterministic unit and mechanism tests for the search/history
   plumbing.
2. Launch one real autonomous Evolver round with the accumulated history.
3. If it produces a non-empty candidate and its local component smoke passes,
   run independent admission.
4. Score only an admitted candidate on T16 and T24.
5. Feed the answer-free result back into the next round and continue while the
   search is producing new information.
6. Expand beyond T16/T24 only after the mechanism works on this canary.

## Evidence to retain

Retain enough evidence to reconstruct the setup and trajectory: run identity,
model and provider, request and cost totals, parent/candidate files and diff,
history entries read by the Evolver, local component tests, admission result,
answer-free task scores, and keep/rollback decision. Do not add exhaustive
identity or contract checks for this engineering experiment.
