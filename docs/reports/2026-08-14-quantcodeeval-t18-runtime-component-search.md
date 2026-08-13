# QuantCodeEval T18 Runtime-Experience Component Search

Date: 2026-08-14  
Status: measured engineering canary; negative benchmark result

## Question

Can the Evolver use a failed H0 Worker's final implementation, answer-free
property-family counts, and prior component-stability evidence to autonomously
localize a QuantCodeEval failure, modify more than a generic prompt, activate
the resulting component in a fresh Worker, and improve T18 without regressing a
passed T19 protection task?

## Setup

- Evolver and Worker route: `deepseek/deepseek-v4-flash-0731`, required
  provider `deepseek`, no fallback.
- Target/protection evidence panel: T18/T19.
- H0 was reused, not resampled: T18 Type A `2/4`, Type B `14/14`, reward `0`;
  T19 `18/18`, reward `1`.
- The Evolver received the scored T18 H0 `strategy.py` as read-only runtime
  experience, the answer-free component ledger, and the measured T12 component
  source. It did not receive checker details or reference answers.
- Activation run:
  `/data/qea-julius-storage/runs/qce-component-route-t18-20260814-r1`.
- Candidate run:
  `/data/qea-julius-storage/runs/qce-component-route-t18-candidate-20260814-r1`.

## Autonomous intervention

The Evolver chose legal `ACT` rather than globally reusing the T12 component.
It classified the leading hypothesis as a temporal-causality / warmup-boundary
problem: H0 deferred classification until the 121st monthly observation even
though the public contract can be read as classifying the 120th observation.
It retained early-NaN and percentile-method behavior as unresolved alternatives
and eliminated an explicit last-trading-day output anchor as unsupported by the
T18 wording.

The candidate changed two harness components:

- extended `skills/quant-contract-arbitration/SKILL.md` with an explicit
  minimum-history flip-index workflow and exactly-N fixture;
- extended `systemprompt.md` so the Worker must state and execute that boundary
  interpretation and check output-date anchors.

The candidate added 28 lines across those two files. Skill loading and full
harness admission passed before Worker evaluation.

## Measured activation and result

The fresh T18 Worker loaded `quant-contract-arbitration` on its first turn. It
then constructed an exactly-120 synthetic fixture, stated that the 120th
observation was the first classified row, executed the fixture successfully,
and changed the final `strategy.py` accordingly. This is positive evidence that
the evolved component changed the Worker's reasoning and implementation, not
merely that the file existed.

The official result nevertheless remained unchanged:

| Run | Type A | Type B | Total | Reward |
|---|---:|---:|---:|---:|
| H0 | 2/4 | 14/14 | 16/18 | 0 |
| Evolved candidate | 2/4 | 14/14 | 16/18 | 0 |

The target did not improve, so the planned repeat and T19 protection evaluation
were not run. This follows the preregistered stop condition and avoids spending
more compute on an unsupported target mechanism.

## Cost

| Stage | Requests | Tokens | Provider cost |
|---|---:|---:|---:|
| Evolver activation | 28 | 1,454,428 | $0.0403022424 |
| T18 Worker evaluation | 21 | 641,753 | $0.0253538264 |
| Total | 49 | 2,096,181 | $0.0656560688 |

Both stages reported complete provider accounting. All run data was written
under `/data`; all experiment containers were cleaned after completion.

## Interpretation and next step

This is a successful discovery-and-activation mechanism canary but a negative
harness-benefit result. Runtime experience let the Evolver identify a concrete
component state, implement a bounded domain component, and cause the next
Worker to execute the predicted fixture. The unchanged official vector rules
out the warmup-fencepost intervention as a sufficient cause of T18's two Type A
failures.

The component ledger now records `warmup_boundary_arbitration` as an
Evolver-discovered, fully activated, unsupported target hypothesis. A next
autonomous round may use this negative evidence to refine toward the unresolved
percentile-method or first-observation NaN mechanisms. It should not repeat the
same warmup-boundary intervention, and it should still stop on calibrated
`ABSTAIN` if public evidence cannot discriminate those alternatives.

