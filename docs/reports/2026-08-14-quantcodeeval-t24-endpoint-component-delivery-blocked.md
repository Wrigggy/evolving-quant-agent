# QuantCodeEval T24 Endpoint Component: Evaluation Blocked by Worker Delivery

Date: 2026-08-14

## Question

Could the Evolver reuse the prior T24 unit-scale component, identify a residual
public Type-A mechanism, extend the executable harness, and improve T24 without
damaging T16?

This was an engineering canary on the fixed
`deepseek/deepseek-v4-flash-0731` route through the DeepSeek provider. H0 and
the prior scored history were reused rather than resampled. The prior T24
candidate had passed 6/7 Type-A and 10/10 Type-B properties, compared with the
T24 H0 result of 6/7 Type A and 9/10 Type B. T16 had passed 18/18 as the
protection task.

## Autonomous component search

Run:
`/data/qea-julius-storage/runs/qce-component-refine-t24-20260814-r1`

The Evolver imported the prior activation and scored Worker history, returned
legal `ACT`, and selected a residual `temporal_causality` mechanism. It observed
that the prior Worker strategy combined a current-row-inclusive cumulative
window with an expanding mean shifted by one period. It refined the existing
static strategy audit into a generic AST-based window-endpoint consistency
check and updated the Worker routing instructions.

This was not prompt-only mutation. The final harness changed agent
configuration, system prompt, tool description, and executable Python tool.
The Evolver iterated through four failing tool self-tests, repaired them, then
passed the final executable self-test, agent-graph smoke, and independent
full-harness admission. The final self-test distinguished:

- a mixed current-inclusive/strictly-causal expression, which it warned on;
- an aligned causal expression, which it left silent;
- a raw-minus-lagged demean expression, which it left silent; and
- an unrelated grouped-monthly example without such windows, which it left
  silent.

The activation used 28 completed model requests, 2,546,172 tokens, and
$0.0623815864. Three additional requests were rejected with provider 429s
before acceptance and were not charged. The selected candidate was admitted
and the endpoint-audit component was executable, but this is only component
activation evidence.

## Worker evaluation attempts

The first official T24 attempt was:
`/data/qea-julius-storage/runs/qce-component-refine-t24-candidate-20260814-r1`.
It made six completed requests, used 101,455 tokens, and cost $0.0164936856.
The final request consumed 32,000 reasoning tokens and returned an empty
assistant message with no tool call. No `strategy.py` was produced, so the
verifier did not run and there is no official property score.

One preregistered replacement attempt used the same activation, candidate,
task, model route, and runtime with a new run ID:
`/data/qea-julius-storage/runs/qce-component-refine-t24-candidate-20260814-retry1`.
It made seven completed requests, used 162,549 tokens, and cost $0.0203747656.
It reproduced the same failure: the final request consumed 32,000 reasoning
tokens, returned empty content and no tool call, and left no `strategy.py`.
The raw Worker trace and final response files were empty in both attempts.

Both attempts were therefore invalid delivery attempts rather than official
T24 reward-zero results. They do not measure whether endpoint consistency
improves T24. No third replacement, independent success repeat, or T16
protection resample was run.

## Cost and interpretation

Across the Evolver and two Worker attempts, there were 41 completed requests,
2,810,176 tokens, and $0.0992500376 in provider cost. Including the three
uncharged rate-limited requests, there were 44 logical requests. All containers
were cleaned after their runs.

Measured conclusions:

1. The Evolver reused prior runtime experience, localized the residual failure
   to a new public finance/quant mechanism, implemented an executable component,
   repaired its own failing smokes, and activated it.
2. The benchmark effect is **not measured** because two same-candidate Worker
   attempts ended in the same terminal empty-response delivery failure before
   producing an artifact.
3. The endpoint component must remain `pending_evaluation`; it is neither
   supported nor refuted by these attempts.
4. The repeated delivery failure is now sufficient evidence for the next
   autonomous search question: choose and test a harness component that saves a
   valid partial artifact early and makes terminal completion recoverable. The
   Evolver should choose the component; an investigator should not prescribe a
   finalizer implementation.

This is a mechanism-localization experiment, not a QuantCodeEval benchmark
estimate.
