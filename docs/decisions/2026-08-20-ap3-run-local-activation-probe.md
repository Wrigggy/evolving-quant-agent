# AP-3 run-local activation probe and formal fresh-Worker boundary

Status: accepted protocol repair, locally tested, no new paid run, 2026-08-20

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
runtime, or official verifier was invoked by this repair.
