# QDR-1 directed component-impact follow-up

Date: 2026-08-20

## Question

QDR-1 had produced a locally discriminating `check_quant_relations` component,
but two blind seeded Workers with six and ten iteration caps never called it.
This follow-up asked the Evolver to diagnose those retained trajectories and
author one bounded Worker instruction that tests the component's impact rather
than starting another broad research run.

The measured chain was deliberately separated into component call, action after
the call, artifact change, property change, and binary reward. The Worker stayed
answer-blind and the official T26 result was not used to choose among multiple
candidates.

## Evolver result and observed orchestration repairs

R1 used 22 Evolver requests and cost $0.10219428. The Evolver independently
selected activation timing, changed the component from a late finalization
check to an early reconciliation step, and authored an eight-iteration repair
experiment. Its graph and import smokes passed. The Worker did not run because
candidate admission unnecessarily froze the descriptive agent `name` field.
The field was removed from the protected set while model route, budget, API
configuration, and other experimental controls remained fixed.

R2 repeated the full Evolver step rather than manually promoting R1. It again
selected activation timing and authored a directed early-audit experiment. The
candidate passed full admission. The old activation-only gate nevertheless
reported failure because `systemprompt` was the primary change and the gate
recognized only locally executable primary components. This gate did not fit a
prompt-led treatment whose actual activation test is the Worker trajectory.
R2 used 22 requests and cost $0.128972568.

The R2 decision and candidate were retained unchanged. A separate resume ran
only the blind seeded Worker and official verifier after confirming full
candidate admission. The original R2 failure record remains intact; the resume
is experimenter-arranged and is not labeled end-to-end autonomous search.

## Measured Worker result

The seven-request Worker ran for 109.375 seconds and called
`check_quant_relations` once. This is a real activation change relative to the
two preceding zero-call probes. It was not the predicted early activation:
seven shell calls occurred first and the component appeared on assistant turn
6. The Worker had expanded the requested bounded inventory into repeated code,
paper, and data inspection.

The component returned two blocking errors and one warning. It localized a
training-boundary observability gap and a metric-weighted-residual observability
gap in `select_gamma_by_cv`, plus a non-canonical ridge-symbol warning. The next
and final Worker turn only reread the target function; it did not edit or
re-audit the module. The delivered artifact was unchanged from the seed. The
official result remained 12/17, five failures, reward zero.

Worker cost was $0.0268286. Across the superseded R1, retained R2, and resumed
Worker, the campaign used 51 model requests and cost $0.257995448, with no
rate-limited retry.

## Conclusion and next mechanism

This is a positive result for Evolver diagnosis and directed component
activation, but a negative result for decision-changing use, artifact repair,
property gain, and binary gain. Natural-language routing made the component
available enough to be called once, but did not make Evaluation and
Reconciliation early or make the Worker act on the observation.

Do not respond with another generic budget increase or a longer activation
paragraph. The next bounded comparison should hold the component and seed
fixed and test one of two smaller mechanisms:

1. a generic one-shot state checkpoint that requires the task-conditioned
   audit decision immediately after a fixed small inventory; or
2. a simpler audit call surface that derives relation declarations from the
   public instruction and module, reducing the amount of call construction the
   Worker must perform.

Measure first-call position, the immediately following action, edit/re-audit,
artifact change, official property delta, and reward separately. Full
multi-task scheduling remains deferred until one such mechanism changes the
artifact or score.

Evidence is mirrored under
`results/bc-mirror/qce-t26-component-impact-20260820/`.
