# QuantCodeEval v2 variable-length full-harness search

> Date: 2026-08-12
>
> Status: implemented and measured with a deterministic no-model mechanism
> canary; real one-round Evolver activation runner implemented; live activation
> and QuantCodeEval candidate scoring not yet run through v2

## Decision

Replace the fixed five-round, coordinator-scripted, prompt-only PGBHS search
definition with a variable-length outer search and an Evolver-controlled
full-harness inner engineering loop.

This decision supersedes only the **search mechanism** used by the earlier
five-round canary. It does not invalidate or overwrite its measured H0,
candidate, score, cost, runtime, or negative-result evidence.

The new mechanism has two nested loops:

1. Within one outer round, the Evolver may inspect evidence, edit one primary
   component and all files required to bind it, run component smoke tests,
   repair a failed draft, or delete the draft before submission.
2. Between outer rounds, the coordinator independently admits the complete
   candidate, runs an activation gate, evaluates the fixed task panel, records
   the exact experience, and selects an official incumbent, a diagnostic
   search parent, an archive entry, a rollback, or calibrated ABSTAIN.

The outer loop stops on target achievement, repeated no-new-information,
repeated ABSTAIN, an explicit operator gap, a request/cost budget, or a
configurable safety cap. Five is no longer a protocol constant.

## Historical experience contract

Every ACT stores a content-addressed, answer-free experience containing:

- complete parent and candidate worker snapshots;
- the exact unified diff;
- the selected mechanism, primary components, and all declared binding roles;
- independent component/admission tests and activation status;
- the answer-free evaluation vector and selection/rollback reason.

From round two onward this store is projected into the Evolver's immutable
evidence workspace. The Evolver must read at least one exact prior entry, diff,
or candidate source before it can ACT. Rejected and ineffective edits therefore
remain directly inspectable experience rather than disappearing into a compact
score summary. Checker code, property IDs, expected values, golden code, and
raw verdicts remain forbidden.

## Component autonomy and attribution

The Evolver may mutate all nine harness roles: `systemprompt`, `agent_config`,
`tool_descriptions`, `tools`, `validator`, `skills`, `memory`, `middleware`,
and `routing`. It declares:

- one or two `primary_components` representing the causal intervention locus;
- a larger `components` set containing only files needed to bind and activate
  that same mechanism.

For example, one deterministic quant operation normally has primary role
`tools` and binding roles `tool_descriptions` and `agent_config`. That is one
mechanism across several files, not three unrelated mutations. Failure-class
component routing is an advisory prior; an Evolver may override it when exact
evidence supports another locus, but must record the reason.

The most urgent measured T24 state update remains deterministic early artifact
checkpointing. Its primary component should be `middleware`, with any required
`agent_config` binding, because the five-round run localized a resource and
termination failure rather than a lack of prompt prose. After artifact
reliability is fixed, the remaining quant-correctness work should be separated
into executable `tools` or `validator` components for units, lag/timing, and
portfolio accounting.

## Measured no-model mechanism canary

The deterministic canary uses fixture rewards and makes no benchmark-score
claim. It measured this state transition:

1. round 1 changed only `systemprompt`; the fixture returned no property-family
   change and the candidate was rejected;
2. round 2 received and read round 1's exact rejected patch;
3. round 2 changed a coherent `tools + tool_descriptions + agent_config`
   component, passed independent full-harness admission, and reached the
   fixture target;
4. the search stopped after two rounds with `target_reached`, demonstrating
   that the mechanism is not fixed to five iterations.

The persisted final artifact is
`results/quantcodeeval-v2-mechanism-canary-20260812-v5/`:

- `PLAN.json` SHA-256:
  `9dfbd6f691de739f80c3de446b1f9d92b1860e08f8390c785f0f56c6e80095e7`;
- `RESULT.json` SHA-256:
  `2e6ef538917d7408479d0413b6787cb89d74ff755994179750a1c95de39d563b`;
- `SEARCH-STATE.json` SHA-256:
  `bab4679f7b7017a36be42ab61120f63a5a29df9f38399c40db4cd593c64d6193`;
- 58 regular files, no symlinks, pytest `1 passed`.

Four earlier local runner artifacts are retained as superseded engineering
negatives. Their test passed, but pytest's runner-created `*current` symlink
made exact artifact-root discovery ambiguous in the first; later versions were
superseded while adding exact component-smoke evidence and resumable search
state validation. v4 removed only generated links before manifesting the
result. v5 additionally binds each component smoke to the exact full candidate
digest, so editing after a successful test invalidates activation until the
component is tested again.

## Live-run boundary

The mechanism layer now has a bespoke real activation runner. It reuses the
published H0 and measured generic Evolver/proxy images, but deliberately does
not invoke the worker or verifier. One real round can therefore test whether
the Evolver chooses, binds, and activates an executable component without first
completing the still-QFBench-specific generic rootless factory.

A benchmark-scored v2 candidate remains gated on the existing isolated
QuantCodeEval worker/verifier path, or on completing the generic adapter work:
uppercase task IDs, QuantCodeEval parser injection, exact `strategy.py`
contract, answer-free evidence sanitizer, and checker/strategy isolation. Do
not spend a multi-round score budget until the one-round activation result is
usable and the scoring path is identity-bound.
