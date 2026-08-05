# 2026-08-06 — Remove the Forced Evolver Component-Switch Prior (v2.1)

Status: **proposed, not tested**.

This record supersedes only the prompt-v2 instruction in
[2026-08-05 evolver exposure and scheduler capacity](2026-08-05-evolver-exposure-and-scheduler-capacity.md)
that required the evolver to change components after two rejected edits to the
same component. All other findings and decisions in that record remain in
effect.

## Decision

Remove the hard rule:

> If the same component was edited and rejected on the two most recent
> iterations, change component.

The evolver must still name its diagnosed failure kind and chosen component
before editing. Prompt v2.1 also retains the complete component inventory, the
distinction between one hypothesis and one file, explicit authorization for
structural edits, and required tool smoke tests.

## Rationale

Two rejected candidates do not establish that a component-level hypothesis is
exhausted. A rejection may reflect a correct component choice with an
over-broad, incomplete, or otherwise poor implementation. A fixed two-round
threshold can therefore force a premature pivot, prevent useful refinement,
and make component diversity an objective even when the current evidence does
not support changing axes.

The rule was an untested search prior introduced alongside several exposure
fixes. Removing it isolates the less prescriptive part of prompt v2: expose the
available search space and require an observable diagnosis, but leave the next
component choice to the evolver's evidence-based judgment. This is not a claim
that repeated same-component edits are desirable; repetition remains visible in
the trace and can be measured before a softer or evidence-conditioned mechanism
is added.

## Scope and interpretation

This change does not alter the permitted candidate files, admission policy,
keep gate, evaluator firewall, benchmark split, model, runtime, or reward. It
does not claim a performance improvement. It is a v2.1 search-prior adjustment
to be evaluated before adding another steering mechanism.

Future guidance will be introduced incrementally. A staged autonomy ladder may
organize the investigation, but it is not a mandatory experimental sequence.
The engineering mechanism should first work in this setup; the research story
will be revised alongside the evidence rather than fixed in advance.
