# QuantCodeEval T26 Binary-Gate Continuation — 2026-08-17

## Conclusion

The multi-round search mechanism is now implemented and locally validated, and
the Evolver produced an admitted, executable refinement from the accumulated
T26 history. The refinement adds a cross-pipeline second-moment scale
consistency check to the existing quant-contract auditor and updates the tool
description and Worker revision instruction. This was an autonomous
three-component change, not a prompt-only mutation.

The round did not produce an official benchmark result. Both blind Worker
attempts ended at the provider rate-limit retry deadline before writing
`strategy.py`, so the official checker never ran. They are infrastructure
outcomes, not zero-reward candidate samples. Consequently, the binary 0-to-1
gate remains open and the new component's T26 effect is unmeasured.

The experiment exposed a concrete search-efficiency bottleneck: a late provider
failure currently discards a long Evolver or Worker trajectory even after many
successful model and tool interactions. Before spending another full redraw,
the next engineering priority is resumable model/tool checkpoints. The admitted
candidate should then be evaluated unchanged; the Evolver does not need to be
rerun.

## Implemented mechanism

The implementation adds three capabilities.

1. A new answer-rich diagnostic can extend an earlier diagnostic instead of
   rebuilding from the original H0. The T26 packet now retains five attempts:
   13/17, 14/17, 12/17, 16/17, and an independent 16/17 repeat.
2. The Evolver assignment explicitly permits `REFINE`, `SPLIT`, `SYNTHESIZE`,
   `COMPOSE`, or `ABSTAIN`, while keeping task answers out of the reusable Worker
   harness.
3. The candidate evaluator can reuse all final Evolver component tests and all
   declared primary components. It also evaluates the mutation relative to the
   immediate 16/17 parent rather than incorrectly measuring the cumulative diff
   from shell-only H0.

The retained evidence exposed answers only to the Evolver. The blind Worker
continued to receive the public T26 task and candidate harness without the
five-attempt diagnostic, property expected values, or checker details.

## Validation

The focused local suite passed 50 tests. It covered diagnostic extension,
answer-rich view construction, component experience, multi-component candidate
input reuse, candidate admission, terminal middleware, and the QuantCodeEval
live loop. Python compilation and `git diff --check` also passed.

On the personal `bc-server`, the dependency-light focused suite passed 17
tests. A no-model rootless preflight then succeeded with the same base85
runtime, DeepSeek route, and current 16/17 parent used by the prior T26 work.
Candidate preflight independently confirmed admission, the incremental
three-component mutation, and the Evolver's final tools smoke.

## Evolver result

The first Evolver attempt completed 21 model requests but ended on a provider
rate-limit/transport failure before a legal terminal artifact. It used
1,184,207 recorded tokens and cost $0.157007080. No candidate was recovered.

One same-setup replacement was allowed. It completed successfully with a legal
`ACT`, passed admission, and changed:

- `tools/quant_contract_audit.py`;
- `tool_descriptions/audit_strategy_source.tool.yaml`;
- `systemprompt.md`.

Its selected operator was `REFINE`, with `tools` as the primary component. The
new state target was consistent second-moment scale across cross-validation and
the final coefficient fit. The executable auditor now checks whether the
pipeline uses one shared scale rather than allowing model selection and the
final fit to operate in different units. The Evolver predicted that this would
reduce or remove A10's remaining end-to-end discrepancy while preserving the
already stable Type-B properties.

The successful Evolver used 22 completed requests, 1,200,530 tokens, 880.138
seconds, and $0.165047632. Its final candidate was admitted and its final tools
import smoke passed.

## Blind Worker outcomes

The frozen candidate was passed to a fresh blind T26 Worker only after
preflight.

| Run | Completed requests | Recorded tokens | Cost | Artifact | Official score |
| --- | ---: | ---: | ---: | --- | --- |
| `qce-t26-binary-gate-candidate-20260817-r1` | 15 | 388,717 | $0.105720504 | missing | unavailable |
| `qce-t26-binary-gate-candidate-20260817-r2` | 8 | 133,140 | $0.012312928 | missing | unavailable |

Both attempts ended with the same provider
`rate_limit_retry_deadline_expired` failure before `strategy.py` existed. No
partial submission was extracted, no official verifier ran, and no benchmark
score is claimed. All recorded containers were cleaned.

The replacement was intentionally limited to one. A third Worker was not
started. Across the two Evolver attempts and two Worker attempts, this phase
used 66 completed requests, 2,906,594 recorded tokens, and $0.440088144.

## Claim boundary

Measured in this round:

- multi-round answer-rich evidence is retained and delivered to the Evolver;
- the Worker remains blind to that answer-rich evidence;
- the Evolver autonomously refined an executable component across three harness
  surfaces;
- the candidate passed admission, local component smoke, and no-model runtime
  preflight;
- late provider failures can waste a long search trajectory under the current
  non-resumable execution model.

Not measured in this round:

- T26 property change for the new component;
- official T26 binary reward;
- repeat stability of the new component;
- protection or matched-task transfer.

The earlier repeated 16/17 result remains the latest valid T26 performance
evidence. It must not be replaced by either unscored Worker attempt.

## Next experiment

Add a lightweight resumable checkpoint at completed model/tool boundaries for
both Evolver and Worker execution. The checkpoint needs to preserve the current
candidate workspace, conversation/tool state needed for continuation, completed
request accounting, and the fact that no official score exists yet. It should
resume the same run and same candidate after a provider delivery failure rather
than starting a new sample.

After a focused failure-injection test proves continuation, evaluate the already
admitted candidate once. If it produces a valid 17/17 result, freeze it and run
one independent blind repeat. If it produces a valid non-17/17 result, append
that property vector to the answer-rich diagnostic and let the next Evolver
round decide whether to refine, compose, split, or abstain. The progressive
large-panel scheduler remains deferred.

Complete run evidence is mirrored under:

- `results/bc-mirror/qce-t26-binary-gate-evolver-20260817-r1`;
- `results/bc-mirror/qce-t26-binary-gate-evolver-20260817-r2`;
- `results/bc-mirror/qce-t26-binary-gate-candidate-20260817-r1`;
- `results/bc-mirror/qce-t26-binary-gate-candidate-20260817-r2`.

