# QuantCodeEval T24 Delivery Recovery and Component Interaction

Date: 2026-08-14

## Question

Can the Evolver use two failed Worker deliveries as runtime experience, choose
the correct harness component, recover the observed empty-response failure,
and then combine that component with the pending T24 endpoint audit?

This was an engineering canary on
`deepseek/deepseek-v4-flash-0731` through the pinned DeepSeek provider. The
existing H0 and prior T24/T16 evidence were reused. It is not a benchmark-wide
estimate.

## First autonomous design: correct component, unreachable hook

Run:
`/data/qea-julius-storage/runs/qce-component-delivery-t24-20260814-r1`

The Evolver read both unscored delivery failures and the prior scored history.
It correctly classified the repeated failure as runtime completion rather than
a quant formula error, selected middleware plus its agent-configuration
binding, and returned legal `ACT`. It implemented an `after_model` completion
guard and passed its local fabricated-input smoke.

The activation used 50 completed requests, 5,149,317 tokens, and
$0.0579361384. A source-level check against the installed NexAU runtime then
falsified the implementation locus: the LLM caller raises `No response content
or tool calls` before the executor invokes `after_model`. The local smoke had
tested the guard's decision logic but not whether the observed exception could
reach that hook. No Worker evaluation was launched on this candidate.

This is useful negative design evidence. The Evolver found the right component
family but needed a runtime-reachability observation to find the right hook.

## Second autonomous design: reachable model-call recovery

Run:
`/data/qea-julius-storage/runs/qce-component-delivery-t24-20260814-r2`

The next round received the failed guard, endpoint-audit source, and the exact
reachability diagnosis. It selected `COMPOSE`, replaced the unreachable hook
with a `wrap_model_call` middleware, registered it in the agent configuration,
and retained the endpoint-audit tool. Its runtime smokes showed:

- one empty-response exception followed by success: two calls and continued
  execution;
- a normal response: exactly one call and no injected recovery; and
- persistent empty responses: three bounded calls followed by propagation.

The Evolver used 53 completed requests, 5,029,608 tokens, and $0.0535214568.
Its candidate failed the automated activation gate only because it did not
repeat the unchanged endpoint tool's final smoke after the last composition.
The investigator ran that omitted endpoint smoke plus the real NexAU
middleware-manager smoke and admission on an unchanged copy. All passed. This
manual validation supplement is explicitly labeled in
`qce-component-delivery-t24-20260814-r2-supplemented`; it is not presented as an
autonomous final-gate pass.

## Real T24 Worker result

Run:
`/data/qea-julius-storage/runs/qce-component-delivery-t24-candidate-20260814-r2`

The composed Worker used 39 completed requests, 1,554,118 tokens, and
$0.0667760408. It encountered the exact prior failure twice in succession:
requests 5 and 6 each used 32,000 reasoning tokens and returned no content or
tool calls. The new wrapper caught both exceptions, injected its bounded
completion directive, and request 7 succeeded. The Worker continued for 37
turns, delivered `strategy.py`, and reached the official checker. This is
direct live evidence that the delivery component works at the intended runtime
boundary, not merely a unit-smoke result.

The quant result nevertheless regressed:

| Result | Type A | Type B | Total | Reward |
|---|---:|---:|---:|---:|
| Best prior T24 candidate | 6/7 | 10/10 | 16/17 | 0 |
| Recovery + endpoint-audit composition | 5/7 | 6/10 | 11/17 | 0 |

Because the target regressed, no T16 protection run was launched.

The final artifact provides a plausible component-interaction explanation. Its
percent-to-decimal helper mutates a DataFrame in place, and four successive
pipeline functions each invoke that helper on the DataFrame passed from the
previous stage. A column can therefore be divided by 100 repeatedly. The
endpoint audit checked expression endpoints and visible unit conversion, but
did not represent whether a stateful conversion had already happened. This is
an artifact-based causal hypothesis, not a revealed checker answer.

## Interpretation

Measured:

1. Runtime experience changed the Evolver's action from quant prompt/tool edits
   to a new middleware component.
2. The first middleware design was falsified by runtime reachability before a
   Worker run.
3. After refinement, `wrap_model_call` recovered two real empty responses and
   enabled artifact delivery and official evaluation.
4. The resulting multi-component harness scored 11/17 on T24, below the prior
   16/17 candidate. Component composition therefore did not improve Worker
   ability in this trial.

Inferred but not yet tested:

- The next missing capability is a unit-state or transformation-lifecycle
  contract: conversions should be once-only, idempotent, or explicitly tracked
  across pipeline components.
- The next Evolver round should inspect the exact 11/17 Worker artifact and the
  16/17 prior artifact, preserve delivery recovery, and autonomously decide
  whether that state-transition component is justified. It should not be given
  a hard-coded repair.

The delivery phase used 142 completed requests, 11,733,043 tokens, and
$0.178233636 total provider cost across the two Evolver rounds and one Worker
run. All run artifacts are under `/data/qea-julius-storage/runs`, and no
containers remained running after completion.

An observed accounting issue also affected the failed second activation: its
top-level proxy audit correctly recorded 53 requests and $0.0535214568, while
the internal search round retained the earlier provisional one-request,
zero-cost value. The controller now reconciles finalized proxy usage for every
terminal decision, not only `ABSTAIN`; focused tests cover both paths.
