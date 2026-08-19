# Future self-evolve scenario and evidence split

Status: accepted future-method direction, not the current AP-2M/AP-3 protocol,
2026-08-18

## Scenario boundary

This record describes a later, more open-ended self-evolve method. It is not a
reinterpretation of the current evolution protocol. AP-2M and AP-3 remain
bounded mechanism canaries with two Evolver decisions, one intermediate Worker
probe, and an independently arranged final evaluation.

In the future self-evolve scenario, the Evolver receives a budget and generic
experiment interfaces, then decides when and why to call a Worker, which
candidate or component to test, whether to branch or revise, and when to submit
an incumbent. Candidate versions record material harness changes; Worker calls
are experiment events attached to those versions rather than fixed mandatory
rounds.

## Training-like intuition

This future scenario may be understood as a training-like optimization process,
without claiming that a harness is literally a learned parameter tensor:

- a candidate version is the current mutable harness state;
- the Evolver is the optimizer that proposes a state transition;
- a Worker experiment is a costly, noisy evaluation sample;
- the artifact, trace, score, runtime, and cost are the feedback signal;
- the experiment ledger and retrieval layer are external optimizer state;
- freezing an incumbent and evaluating it on an unseen surface is the final
  evaluation step.

## Why this direction may help

- It spends Worker calls only when the Evolver expects useful information,
  instead of evaluating every candidate on every task in every round.
- It can search deeply within one unresolved component and broadly across
  several component hypotheses without forcing an arbitrary iteration count.
- It can accumulate reusable positive, negative, and contradictory runtime
  experience across candidate versions.
- It gives the Evolver room to test whether a component is reachable and useful
  before committing to a larger evaluation.

## Main problems

- Repeatedly observing one optimize task and retaining the best candidate can
  fit that task well without establishing out-of-sample generalization.
- The end of a search is no longer implied by a fixed round count, so submission
  needs explicit budget, incumbent, and stopping rules.
- A lucky Worker sample can influence candidate selection; repeat and protection
  evidence must therefore remain distinguishable from one-off improvement.
- Long histories can become difficult to navigate and can bias retrieval toward
  supporting evidence unless counterevidence is preserved.

## Evidence surfaces

Use the following labels consistently:

- `optimize`: the Evolver may repeatedly inspect rich diagnostics and use the
  result to choose, refine, or reject candidate versions;
- `development/protection`: optional limited feedback used to detect obvious
  regression or matched transfer; once consulted adaptively, it is development
  evidence rather than out-of-sample evidence;
- `sealed_final`: never available to the Evolver, its retrieval index, or the
  candidate-selection controller before the harness is frozen.

The Worker remains answer-blind on every surface. Optimize-task answer-rich
diagnostics may be returned to the Evolver after verification. A task becomes
part of the optimization surface as soon as its observed result changes search
or candidate selection, regardless of what the split was originally called.

## Candidate versions and search events

A material harness change creates a new candidate version. Any number of
bounded Worker experiments may be attached to that version without pretending
that each call is a new evolution round. The lineage therefore records:

```text
candidate version -> Worker experiment(s) -> observed feedback ->
retain / refine / branch / rollback / submit
```

Search is bounded by cost, time, and information value rather than by an
arbitrary fixed count such as five iterations. The final result is the frozen
incumbent selected under the declared optimize protocol, not necessarily the
last candidate produced.

## Retrieval for long-horizon search

RAG is used as persistent external search memory, not as a source of new
answers. It should retrieve compact candidate, experiment, task-state, and
component records, including both supporting and contradicting evidence. It
must exclude all `sealed_final` results. This helps the Evolver search a deep
and broad history without one unbounded conversation, but it does not by itself
prevent adaptive overfitting.

## Relationship to the current path

Do not claim that AP-2M already implements this open-ended self-evolve scenario.
AP-2M only checks the smallest prerequisite: can the Evolver choose one real
Worker experiment and update its second decision from the result? AP-3 then
checks the same bounded mechanism from shell-only H0. Only after those canaries
work should the project test variable numbers of Worker calls, branching
candidate versions, RAG-backed long-horizon search, and autonomous submission.
