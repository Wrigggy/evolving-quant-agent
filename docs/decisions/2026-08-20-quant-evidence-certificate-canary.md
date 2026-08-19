# Quant Evidence Certificate Canary

Status: accepted immediate mechanism experiment, 2026-08-20. This record
refines QR-1/QI-1 without replacing the Research-State-guided outer loop.

## Decision

Add an optional, task-conditioned `quant_evidence_certificate` to the existing
Research State transition and verdict. The certificate is evidence used to
locate and test a proposed harness intervention; it is not a seventh Research
State, a new official reward, or a closed finance failure taxonomy.

The certificate may contain one or more of three open evidence forms:

1. **quantitative semantic coordinates** for units, scale, quote convention,
   information time, valuation time, compounding or day-count basis, currency,
   or probability measure when those fields are applicable;
2. a **reconciliation bridge** between two economically equivalent views of an
   artifact, retaining the explained terms and unexplained residual; and
3. a **residual-and-sensitivity fingerprint** that records a task-derived
   residual and its response to one or two controlled perturbations.

The Reviewer chooses only the evidence form supported by the public task and
runtime evidence. `not_applicable` and `insufficient_evidence` are valid. A
certificate must not contain an optimization answer as reusable Worker
guidance or redefine official benchmark success.

## Why this fits the current method

The Evolver, Worker, official evaluator, mutable full-harness surface, and
variable-length outer loop remain unchanged. The certificate attaches to the
already implemented chain:

```text
expected Research State -> observed mismatch -> competing explanations
    -> selected component -> predeclared transition observable
    -> component activation -> observed state transition -> official outcome
```

It raises the resolution of the middle observation. A Boolean invariant may
show that a relation failed; semantic coordinates, a reconciliation residual,
or a perturbation response can help distinguish why it failed and therefore
which harness component is reachable and relevant.

## Immediate controlled experiment: QEC-1

Before adding the certificate to AP-3, run a small paired Reviewer canary. Give
the generic and certificate arms the same public contract, artifact/trajectory
evidence, audit choices, model route, and call budget.

Use three minimal cases:

- a percentage-scale mismatch versus a wrong-formula explanation;
- a missing transaction-cost term versus a holdings-timing explanation; and
- an ambiguous case in which the available audits cannot discriminate the
  explanations.

Each arm first chooses one audit. The coordinator executes only that declared
audit and returns its observation. The arm then gives a final diagnosis. The
trusted canary scorer checks whether the known mechanism remains, the adjacent
explanation is eliminated when the audit permits it, the chosen audit is
discriminating, and the ambiguous case is handled with calibrated
insufficiency.

QEC-1 is positive only if the certificate arm adds diagnostic discrimination
beyond a generic structured root-cause response under the same evidence and
calls. Merely producing more finance vocabulary is negative.

## Next experiment gate

If QEC-1 is positive, run one live QI-2/QR-1B intervention on an unresolved
optimize task and require a fresh Worker to activate the selected component and
move the predeclared quantitative observation in the predicted direction.
Only then insert certificate evidence into AP-3. If QEC-1 is neutral or
negative, preserve the result and run AP-3 through the existing generic
Research-State evidence path.

Official property or reward improvement, repeat/protection, and transfer remain
separate evidence levels. QEC-1 alone is a Reviewer-mechanism result, not a
benchmark-performance result.

## Prior-art correction

Do not claim first quantitative harness evolution. Recursive Harness
Self-Improvement already evolves prompt-represented harnesses on a quantitative
finance task family, while AQuA and related quantitative systems adapt memory,
policy, research state, or scheduling. The narrower working contribution is
full-harness evolution made more identifiable through predeclared,
task-conditioned quantitative state-transition evidence and separate
activation, state-correction, official-outcome, and scope verdicts.

## Measured QEC-1 and AP-3 results

QEC-1 r1 completed all twelve planned Reviewer calls with
`deepseek/deepseek-v4-pro`. Both arms selected the discriminating audit on all
three cases, correctly handled the ambiguous case, and correctly resolved the
rate-scale case. Neither arm explicitly eliminated the holdings-timing
alternative in the transaction-cost case. The generic and certificate arms
therefore tied at two of three successful cases; there was no improved or
regressed paired case. The mechanism gate is `not_positive`, so no QI-2/QR-1B
certificate intervention was run and AP-3 used generic Research-State evidence.

The first AP-3 launch was rejected before model execution because the verifier
image argument was mistyped. The corrected retained run is
`results/bc-mirror/qce-t26-ap3-20260820-r3/`. Its fresh Quant-H0 Worker scored
12/17 on T26 with reward zero. Evolver round one autonomously identified an
Evaluation-and-Reconciliation gap, created and smoked an executable artifact
checker, and authored a from-scratch twelve-iteration Worker probe. The probe
made eleven model requests but produced no `strategy.py`. Round two cited that
`missing_artifact` observation, shifted the predicted mismatch to Research
Artifact and Completion, and submitted a calibrated `ABSTAIN` because the
short-probe budget and missing trace contrast did not justify another edit.

AP-3 therefore measured a minimal feedback-driven bootstrap loop from
Quant-H0, but no activated helpful component, admitted final candidate,
official candidate score, property gain, or binary gain. The run used 48 H0,
22 first-round Evolver, 11 probe-Worker, and 18 second-round Evolver requests.
The corrected total provider cost is $0.259885044. The original coordinator
total omitted the H0 and probe values because they were serialized as numeric
strings; the cost parser is repaired for later runs.

One orchestration gap remains: round two received the round-one candidate and
probe result but not the round-one prediction record. It could respond to the
observed failure, but could not perform the intended explicit
prediction-versus-observation comparison. Repair that handoff before repeating
AP-3. This result supports autonomous bootstrap-loop feasibility only, not
harness benefit or benchmark improvement.
