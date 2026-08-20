# QDR-1 quant diagnostic refinement result

Date: 2026-08-20

## Question

Can answer-rich optimize-only mismatch evidence help the Evolver replace a
generic artifact audit with a quant-specific, discriminating component, and
does that component then change a blind seeded Worker and its official T26
outcome?

## Fixed setup

QDR-1 reused the AP-3 r3 12/17 T26 artifact, the current AP-3 diagnostic
candidate, the r2 blind Worker trajectory, and the same public/trusted runtime.
The optimization diagnostic was visible only to the Evolver. The Worker saw the
public task, the seed artifact, the evolved harness, and the Evolver-authored
answer-blind repair instruction. The older 16/17 answer-rich candidate was not
given to the Evolver.

## Measured result

The Evolver compared three explanations: relation observability, a genuine
numeric convention mismatch, and late activation/stopping. It selected the
first while retaining the A10 numeric mismatch as counterevidence. It then
synthesized a reusable `check_quant_relations` tool covering training-boundary
information time, identity-ridge estimator geometry, and metric-weighted
validation residuals, plus the tool schema, registration, and prompt binding.

The local discriminating smoke was positive. A correct fixture realized all
three relations with zero truncation and OOS-permutation residuals. Removing
only the training-boundary gate produced two localized failures and a 0.0947
truncation residual while the other two relations still passed. This is direct
evidence that quant semantics changed the Evolver's diagnosis and component
design; it is not an official benchmark result.

The six-iteration blind Worker probe did not call the new component. It spent
five model requests reading the task and seed, left the artifact unchanged,
and remained 12/17 with reward zero. A follow-up held the candidate, seed,
instruction, runtime, and task fixed and increased only the cap to ten
iterations. It used nine model requests but again never called the component;
it repeated broad file and paper inspection, ran the existing pipeline, left
the artifact unchanged, and remained 12/17 with reward zero.

The Evolver used 30 requests, 2,840,576 tokens, and $0.186782712. The two Worker
probes used 5 and 9 requests and cost $0.005077364 and $0.013176676. Corrected
total cost was $0.205036752. No rate-limit retry occurred, and scoped runtime
containers and networks were gone at completion. The first generated aggregate
omitted the Worker numeric-string cost; the result writer was repaired after
the run, and this record reports the corrected arithmetic.

## Decision

Retain the component and the negative Worker trajectories as search experience,
but do not promote it as Worker-helpful or benchmark-helpful. The next bounded
test must change activation/tool selection so that the Worker reaches the
predeclared Evaluation and Reconciliation transition. Merely increasing the
generic Worker budget again is not supported by the 6-versus-10 comparison.

Artifacts:

- `results/bc-mirror/qce-t26-qdr1-diagnostic-refinement-20260820-r1/`
- `results/bc-mirror/qce-t26-qdr1-activation10-20260820-r2/`
- `data/quantcodeeval/QDR1_DIAGNOSTIC_REFINEMENT_RESULT.json`
