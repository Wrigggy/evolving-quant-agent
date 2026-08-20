# AP-3 run-local activation probe and formal fresh-Worker boundary

Status: accepted protocol repair; bounded intermediate r1 measured, 2026-08-20

## Observed problem

AP-3 r3 asked a twelve-iteration from-scratch T26 Worker to complete the full
task and then invoke an Evolver-created artifact checker near submission. The
Worker spent all eleven completed model requests reading the paper and data,
produced no `strategy.py`, and therefore never reached the checker's applicable
state.

Read-only reconstruction found an additional orchestration defect. The probe
overlay copied the public data but replaced the complete public T26 instruction
with the Evolver's short experiment instruction. The Worker therefore did not
receive the required-function table or complete IO and convention contract.
This is a probe-construction failure, not evidence that the registered component
was unavailable or unhelpful.

## Superseding AP-3 probe protocol

The intermediate AP-3 Worker call is a short component-activation experiment,
not a second formal fresh Worker run:

1. Keep the complete official public task instruction unchanged and append the
   Evolver-authored experiment directive under a separate heading.
2. Expose only the artifact produced by the fresh H0 Worker inside the same AP-3
   run, under the fixed name `run_local_h0`.
3. Require the round-one experiment specification to use `mode=repair` and
   `seed_experience=run_local_h0`. Historical artifacts and expert repairs
   remain unavailable.
4. Pre-stage that artifact at `/app/output/strategy.py`, retain its public-data
   backup, and keep the probe within the existing twelve-iteration cap; four to
   eight iterations are preferred.
5. Give round two the original H0 artifact, the delivered probe artifact when
   present, the predeclared prediction, and the actual probe observation.

This short probe can establish component reach, invocation, predicted state
transition, and seeded repair behavior. It is not a from-scratch benchmark
result.

## Formal fresh-Worker boundary

If round two submits an admitted candidate and the cost gate permits, AP-3 still
runs exactly one independent formal candidate evaluation. That Worker starts
with an empty output directory, receives the complete public task, uses the
normal Worker budget, and is scored by the unchanged official verifier. Only
this stage can support a fresh candidate-harness performance claim. A later
fresh repeat remains necessary for initial stability.

The protocol identifier advances from `quantcodeeval-ap3-v1` to
`quantcodeeval-ap3-v2`. Historical AP-3 r3 evidence remains unchanged and must
continue to be reported as bootstrap-loop feasibility without component
activation or benchmark benefit.

## Local validation

Focused tests cover preservation of the official instruction, explicit
experiment-directive composition, optional seed staging, rejection of a
missing official instruction, exact use of the run-local H0 artifact, delivery
of before/after artifacts to round two, and separation of an ABSTAIN path from
the formal fresh Worker. The focused suite passed 27 tests. No model, remote
runtime, or official verifier was invoked by this local repair.

## Bounded intermediate r1 result

Run `qce-t26-ap3-v2-intermediate-activation-20260820-r1` exercised only the
intermediate Worker call. It reused AP-3 r3's same-run fresh Quant-H0 artifact
(12/17) and autonomous round-one candidate; Quant-H0, Evolver round one, Evolver
round two, and the formal no-seed Worker were not rerun. The complete public
instruction was present, but the live deploy lacked the already-committed
Worker runner helper that pre-stages the seed at `/app/output/strategy.py`.

The Worker initially found an empty output directory, read the backup under
`/app/data`, and copied it to the output itself. It then successfully invoked
`check_strategy_artifact` once. The component reported zero errors, seven
warnings, and one info. The call occurred on the final model request, so the
iteration cap ended the run before the Worker could reconcile the findings or
edit and recheck the artifact. The final file was unchanged and remained
12/17, reward zero. This measures component reach and invocation, but it is not
a valid test of the complete intended pre-stage intervention and does not
measure a post-audit Research-State transition, seeded repair, component
helpfulness, or benchmark gain.

The run used seven completed requests, 113,110 tokens, and $0.015230112. Its
immediate lesson is deployment-local: repeat the same bounded probe only after
the committed pre-stage runner is synchronized, before increasing the general
Worker budget or changing search logic. That sync and a no-model staging smoke
were completed after r1; no second model run was launched.
The tracked result is
`data/quantcodeeval/AP3_V2_INTERMEDIATE_ACTIVATION_RESULT.json`; detailed
evidence is mirrored under
`results/bc-mirror/qce-t26-ap3-v2-intermediate-activation-20260820-r1/`.

## Paired intermediate r2 result

R2 held the task, seed, candidate, instructions, model route, images, and
eight-iteration cap fixed and changed only the remote deployment of the
committed seed-prestage helper. The first Worker turn found the seed at the
promised output path. The checker was invoked on model request five of seven,
and two subsequent requests reconciled its findings and attempted additional
functional checks. This validates the intended pre-stage, component reach,
activation, and post-audit reconciliation path; no explicit post-audit reserve
is needed on this evidence.

The component returned zero errors and only period/join-key warnings. The
artifact stayed identical to the 12/17 seed and official T26 remained 12/17,
reward zero. Trusted optimize-only diagnostics for the five failures did not
overlap the component findings. Therefore the next unresolved mechanism is
diagnostic coverage rather than component availability or terminal timing.

R2 used seven completed requests, 116,504 tokens, and $0.01515752 with no
rate-limit retry. The next bounded experiment may expose the answer-rich
optimize mismatch to the Evolver only, ask it to refine or replace the
component, and then run one paired blind-Worker probe. Do not expose those
diagnostics to the Worker or encode the property answers into a reusable
candidate.
