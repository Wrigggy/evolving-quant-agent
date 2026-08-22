# Main-0B autonomous rehearsal result

**Date:** 2026-08-23

**Status:** Retained engineering and autonomy result; no candidate promoted.

## Question

Can the existing Evolver begin from Quant-H0, author an executable harness
candidate, and hand control to a fixed resumable controller that runs normal
target, repeat, protection, and terminal selection without experimenter edits
or score-based overrides?

## Setup

Main-0B used two pre-screened QFBench lineages. Holdings paired
`13f-amendment-aware-crowding` with `brinson-sector-attribution`; local-vol
paired `dupire-local-vol` with `localvol-barrier`. Each lineage allowed one
fresh quant-state Evolver proposal and one admitted candidate. The controller,
not the Evolver or experimenter, owned evaluation dispatch, repeat and
protection gates, and the terminal promote-or-rollback decision. Workers ran
at the normal budget; no short probe, generic arm, or sealed evaluation was
used.

The holdings proposal intentionally stopped at the saved proposal boundary and
was resumed with the same plan and state directory. Both terminal states were
also invoked again after completion to test reuse of finished child reports.

## Results

### Holdings: first gain did not repeat

The Evolver returned `ACT`, passed admission, selected
`final_state_recomputable_aggregates`, and added the executable
`reconcile_final_state` tool with Worker activation instructions. On the first
target comparison, Quant-H0 scored 46/51 with reward 0 and the candidate scored
51/51 with reward 1. The candidate called the new tool once.

The independent repeat changed the concurrent comparison to 44/51 versus
44/51, both reward 0. The candidate again called the component, but the target
gain did not reproduce. The controller therefore skipped protection and
automatically froze the lineage as `ROLLBACK`, reason
`repeat_gain_not_observed`. Quant-H0 remained the current parent.

The lineage used 110 completed requests, 6,311,081 tokens, and $0.237994508.

### Local-vol: repeated target gain but unsafe protection

The Evolver returned `ACT`, passed admission, selected
`svi_parameter_admissibility`, and added the executable
`surface_contract_audit` tool plus activation instructions. On the first target
comparison, Quant-H0 scored 66/68 with reward 0 and the candidate scored 68/68
with reward 1. The same frozen candidate repeated 68/68 against another
66/68 Quant-H0 sample. It called the component twice in each candidate run.

On `localvol-barrier`, however, Quant-H0 scored 35/39 with reward 0.9 and the
candidate scored 29/39 with reward 0.768857. The candidate called the audit
three times. Its first call found a 27.919% gap between the local-vol Monte
Carlo vanilla value and the surface vanilla value, above the component's 5%
tolerance. The Worker explicitly acted on the finding, changed and reran its
pipeline, and the next two audit calls passed. Despite that internal pass, the
official protection failures increased from four parameterized properties to
ten. The controller automatically froze the lineage as `ROLLBACK`, reason
`protection_not_property_safe`. Quant-H0 remained the current parent.

The lineage used 270 completed requests, 22,087,058 tokens, and $0.627694992.

## Resume and operations

The holdings proposal-boundary resume reused the admitted candidate and did
not dispatch a Worker before the explicit resume. Re-invoking both terminal
controllers preserved their state, accounted run IDs, child reports, and cost;
no child was rerun and no promotion or rollback was applied twice.

Across both lineages, the campaign used 380 completed requests, 28,398,139
tokens, and $0.865689500. There were zero runtime restarts, rate-limit retries,
unreconciled requests, or residual processes, containers, and networks after
completion. The local monitor, mirror, and caffeinate jobs were unloaded after
the final evidence mirror.

## Interpretation

Main-0B closes the small-scale autonomous lifecycle gap: Evolver proposal,
candidate admission, ordinary Worker evaluation, independent repeat,
protection, terminal rollback, cost accounting, cleanup, and resume all ran as
one fixed-controller workflow. It also shows why the controller must own
selection. A first target success can be stochastic, and a component can be
reachable, actively diagnose a numerical inconsistency, change Worker
behavior, and still degrade a related quantitative task.

The local-vol result is especially useful for the method. A component's own
audit passing after intervention is not a completion certificate. Its
quantitative relation covered aggregate price reconciliation but did not
protect the wider pointwise surface contract checked by the second task. This
motivates an observed relation-and-outcome layer that measures what state was
corrected and what neighboring properties moved, rather than treating tool
activation or an internal green audit as sufficient.

This result does **not** establish a promoted stable harness, generic-versus-QRS
superiority, sealed or benchmark-wide gain, or full both-benchmark main-run
readiness. The next bounded implementation should use these retained reports
for a zero-model Main-0C preflight: materialize an observed relation/outcome
record, replay parent-comparison reuse, and normalize one credential-free
QuantCodeEval result into the lifecycle schema. No additional paid rehearsal
is required before the first frozen A0 QFBench wave. Within A0, at least one
new `ACT` candidate must repeat its target gain, avoid expanding the protection
failed-property set, and be autonomously promoted before claiming a stable
improved researcher. A calibrated `ABSTAIN` remains useful search evidence but
does not close that claim. The remaining licensed QuantCodeEval tasks are not
required.

Compact record:
`data/breadth/QF_MAIN0B_AUTONOMOUS_RESULT.json`.
