# QFBench A0.2 QRS refinement R4 result

Date: 2026-08-24
Status: retained positive; `PROMOTE` / `FROZEN`

## Decision

Promote and retain `qf-a02-localvol-qrs-c3-r4`. The Evolver began from the R3
c2 harness and its exact no-gain runtime evidence, selected `REFINE`, and
authored a general standard-SVI parameter profile inside
`check_parameter_admissibility`. Against the retained c1 selection reference,
the candidate resolved the same sole SVI-`a` property on target and independent
repeat, reached 68/68 with reward one twice, and introduced no protection
regression. The fixed controller therefore returned `PROMOTE`, updated the
lineage parent to c3, and froze the lineage.

This is the first positive result in the A0.1/A0.2 refinement chain after the
R3 contract-to-predicate omission. It remains one development family and does
not establish QRS superiority, sealed performance, or benchmark-wide gain.

## Frozen setup

- Refinement backbone: `qf-a01-localvol-qrs-c2-r3`.
- Selection reference: retained `qf-a0-localvol-qrs-c1` outcomes.
- New candidate: `qf-a02-localvol-qrs-c3-r4`.
- Target and repeat: `dupire-local-vol`, each compared against the same c1
  67/68, reward-zero reference whose sole failure was
  `TestSVIParams::test_svi_a_positive`.
- Protection: `localvol-barrier`, compared against the c1 38/39, reward-0.96
  reference.
- The R3 property-level diagnostic was Evolver-only. Every R4 Worker remained
  answer-blind. No sealed task was used.

## Proposal: admitted standard-SVI profile

The Evolver returned `ACT` with `REFINE`. It changed `systemprompt.md`, the
checker descriptor, and executable `tools/admissibility.py`; declared and
actual component roles matched. The central addition was a signature-gated
standard parameterization registry. For a table recognized as SVI, the checker
automatically applies non-weakenable strict positivity to `a`, `b`, and
`sigma`, while retaining `rho` and `m` as signed-free. This makes certification
independent of whether the Worker remembers to enumerate `a`.

The proposal used 24 completed requests, 2,714,302 tokens, and $0.086027048.

## Target: first relation-consistent binary gain

The c1 selection reference was 67/68, reward zero, failing only
`test_svi_a_positive`. The c3 Worker activated the checker on the SVI table;
the returned finding recorded `standard_parameterization.name="svi"` and
automatically checked `a`, `b`, and `sigma`. Its final artifact passed all 68
properties with reward one, resolving the SVI-`a` property and introducing no
failure. The controller anchored this empirical relation footprint.

The target used 40 completed requests, 3,302,024 tokens, and $0.099933064.

## Repeat: same property footprint reproduced

The independent c3 Worker again activated the SVI profile and reached 68/68,
reward one, against the same c1 67/68 selection reference. It resolved the same
`test_svi_a_positive` property with no introduced or unrelated resolved
property. The predeclared `resolved_property_footprint_v1` policy therefore
returned `CONSISTENT` with reason `repeat_relation_footprint_reproduced`.

The repeat used 38 completed requests, 2,197,372 tokens, and $0.071670192.

Target and repeat do not show a violation-to-refit causal chain. In both runs,
the observed SVI-profile findings were already admissible and contained zero
violations; no trace event showed the checker rejecting a fitted table and the
Worker subsequently refitting it. The supported statement is therefore an
association between profile activation and the same repeated official property
correction, not complete causal isolation of the checker.

## Protection: safe, better, and not SVI-attributable

The c1 `localvol-barrier` reference was 38/39, reward 0.96, failing only
`test_barrier_outputs_reasonable`. The c3 fresh Worker reached 39/39 with
reward one, introduced no failed property, and passed both aggregate and
property-set safety gates.

The checker was called on `cleaned_quotes.csv`, `surface_nodes.csv`,
`call_surface.csv`, and `local_vol_surface.csv`. Every finding had
`standard_parameterization=null` and zero violation. This is useful evidence
that the SVI registry did not falsely match four non-SVI tables. It also means
the protection +1 cannot be attributed to the SVI relation; it is retained only
as a safe, improved fresh-Worker outcome.

Protection used 27 completed requests, 1,712,327 tokens, and $0.063065884.

## Terminal state, accounting, and cleanup

The complete R4 lineage used 129 completed requests, 9,926,025 tokens, and
$0.320696188. All four run IDs were accounted exactly once. The controller
returned `PROMOTE` for `repeat_and_protection_safe`, set c3 as the current
parent, and entered `FROZEN`.

A terminal resume dispatched no child, added no request, token, or cost, and
left the terminal state unchanged. The active-lineage marker was cleared.
Cleanup verification found zero related containers, networks, or processes.

## Interpretation and boundary

R4 demonstrates that the Evolver can use a failed activated component trace to
move the missing relation coverage into a general executable profile, then
obtain the same official property correction twice and pass protection. This
is stronger than R3 activation without gain and stronger than a score-only
repeat because the resolved property footprint is identical.

The result does not isolate the checker as the sole cause: neither successful
Worker exposed a violation followed by refitting. Protection demonstrates
non-regression and absence of false SVI matching, not SVI mechanism transfer.
No matched generic refinement, sealed panel, broad benchmark, or independent
campaign is included, so QRS superiority and benchmark-wide improvement remain
unsupported.

## Evidence

- Compact result: `data/breadth/QF_A02_QRS_REFINEMENT_R4_RESULT.json`
- Frozen plan: `data/breadth/QF_A02_QRS_REFINEMENT_R4_PLAN.json`
- Complete local mirror:
  `results/bc-mirror/qf-a02-localvol-qrs-refine-20260824-r4-artifacts`
- Controller:
  `results/bc-mirror/qf-a02-localvol-qrs-refine-20260824-r4-artifacts/controller/CONTROLLER-RESULT.json`
- Proposal, target, repeat, and protection reports are under the corresponding
  subdirectories of the same mirror.
