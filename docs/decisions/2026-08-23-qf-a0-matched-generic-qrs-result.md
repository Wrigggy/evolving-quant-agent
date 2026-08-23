# QFBench A0 matched generic--QRS result

Date: 2026-08-23  
Status: four lineages complete; one scientific promotion and one mechanical-only promotion

## Decision

Retain A0 as the first fresh matched generic-versus-QRS search result. The four
independent lineages completed and froze under the same Quant-H0 parent,
authorized evidence, model routes, normal Worker budget, full harness mutation
surface, parent-comparator reuse, answer boundary, and fixed selection
controller.

The local-vol generic candidate is the only scientifically repeated promotion
in this wave. It improved `dupire-local-vol` from 66/68 to 67/68 on target and
to 68/68 with reward 1 on the independent repeat. On answer-free
`localvol-barrier` protection it improved 35/39, reward 0.9, to 38/39, reward
0.96 without losing a parent-passed property. The frozen controller therefore
promoted it, and the mechanism/outcome evidence is consistent with that
decision.

Keep the QRS local-vol controller result exactly as recorded--`PROMOTE`--but do
not count it as a scientifically repeated promotion. Its target improvement
was relation-aligned: the Worker called `check_parameter_admissibility`, moved
all delivered SVI intercepts to 0.001, and removed the strict-positivity
failure. On repeat, however, the candidate again delivered SVI intercepts at
zero or effectively zero and failed `test_svi_a_positive`; its 66/68 to 67/68
gain came from resolving the retained parent's separate flat-vol-consistency
failure.
The simple frozen controller saw a positive count delta and safe protection,
so it mechanically promoted. The stricter footprint interpretation is
post-hoc, motivated by this observed gap, and must not be represented as the
frozen controller's original rule.

## Frozen setup

- Benchmark: QFBench.
- Families: holdings final-state reconciliation and local-vol surface
  calibration/pricing.
- Arms: strong generic full-harness Evolver and operational QRS Evolver.
- Parent: Quant-H0.
- Candidate allowance: one proposal per lineage.
- Parent observations were reused exactly; new stages dispatched only the
  candidate Worker.
- Optimization diagnostics could supervise the Evolver after a blind Worker
  attempt. Workers and protection remained answer-blind.
- No sealed evaluation was included.

The only intended treatment difference was the operational Quant Research
State Card plus state-and-relation-conditioned retrieval and component
routing. Candidate history, evidence, model and budget, mutation surface,
controller, resume behavior, and answer access were matched.

## Four retained lineages

### Holdings generic

The generic Evolver returned `ABSTAIN` and authored no candidate. It found the
five target failures to be heterogeneous reference-convention mismatches--the
turnover definition, issuer canonicalization, and pair serialization--while
the Worker's delivered artifacts were internally self-consistent. The
successful Brinson trajectory supplied no shared failure mechanism that an
answer-free reusable component could address.

This lineage used 13 completed requests, 1,025,314 tokens, and $0.043881888.
No Worker evaluation stage was dispatched. Its terminal state is
`ABSTAIN`/`FROZEN` with Quant-H0 unchanged.

### Holdings QRS

The QRS Evolver also returned `ABSTAIN`. Its State Card probe confirmed the
same internal consistency and additionally rejected an unsupported relation
and component locus: teaching the missing checker conventions would encode
task-specific reference behavior rather than a reusable capability.

This lineage used 19 completed requests, 2,035,103 tokens, and $0.063065348.
No Worker evaluation stage was dispatched. Its terminal state is
`ABSTAIN`/`FROZEN` with Quant-H0 unchanged. The result supports calibrated
abstention, but QRS was more expensive and did not improve the decision in this
one holdings proposal.

### Local-vol generic

The generic Evolver admitted `audit_surface_artifacts`, a broad audit over
delivered fitted parameters, local-vol and call surfaces, barrier relations,
and summary coherence.

| Stage | Official comparison | Raw component evidence | Requests | Tokens | Cost |
|---|---:|---|---:|---:|---:|
| Proposal | `ACT`, candidate admitted | executable audit authored and smoked | 37 | 3,284,516 | $0.089906400 |
| Target | 66/68 to 67/68, reward 0 to 0 | audit called three times | 30 | 1,404,262 | $0.058186288 |
| Repeat | 66/68 to 68/68, reward 0 to 1 | audit called twice | 32 | 1,545,302 | $0.056568336 |
| Protection | 35/39 to 38/39, reward 0.9 to 0.96 | audit called three times; parent-passed property set preserved | 25 | 1,381,857 | $0.059890756 |
| Total | `PROMOTE`/`FROZEN` | scientifically consistent | 124 | 7,615,937 | $0.264551780 |

The target's only remaining failure was forward-variance ATM local-vol
positivity; repeat passed all 68 properties. Protection's only remaining
failure was barrier-output reasonableness, which the retained parent also
failed. This is a repeated binary gain with property-safe answer-free
protection.

The structured activation ledger stored a false zero because the live runner
had not bound the new proposal tool as the stage's activation token. The raw
Worker traces directly show two calls in repeat and three in protection (and
three in target). This is an observation/accounting gap, not component
non-use.

### Local-vol QRS

The QRS Evolver used the runtime State Card to select
`evaluation_reconciliation`, the relation
`calibrated_surface_parameter_admissibility`, and the narrow tool
`check_parameter_admissibility`.

| Stage | Official comparison | Relation footprint | Requests | Tokens | Cost |
|---|---:|---|---:|---:|---:|
| Proposal | `ACT`, candidate admitted | State Card and relation-conditioned routing used | 32 | 1,926,466 | $0.063865752 |
| Target | 66/68 to 67/68, reward 0 to 0 | tool called twice; all SVI `a` values became 0.001; SVI failure removed | 23 | 1,114,814 | $0.053678792 |
| Repeat | 66/68 to 67/68, reward 0 to 0 | tool called twice, but SVI `a` returned to zero/effectively zero and the SVI property failed | 35 | 1,620,487 | $0.054308484 |
| Protection | 35/39 to 38/39, reward 0.9 to 0.96 | tool called six times; parent-passed property set preserved | 29 | 1,979,835 | $0.064618324 |
| Total | controller `PROMOTE`/`FROZEN` | scientific repeat `INCONSISTENT` | 119 | 6,641,602 | $0.236471352 |

The target retained the forward-variance ATM failure while fixing the selected
SVI admissibility property. The repeat instead resolved its retained parent's
flat-vol-consistency failure but again failed SVI strict positivity. Therefore
the same numeric +1 did not represent the same predicted state transition.

The controller's `PROMOTE` is mechanically correct under the frozen rule:
target and repeat both beat their retained 66/68 parents, and protection was
aggregate- and property-set-safe. Scientifically, the repeated mechanism claim
is unsupported because the predeclared artifact footprint did not recur. We
retain both facts instead of rewriting the controller outcome.

The runtime State Card affected evidence retrieval and component routing, but
the pre-fix uploader did not preserve the complete State Card as a standalone
artifact. Proposal summaries and traces retain the operative state and
relation; complete independent State Card replay is unavailable for this run.

## Campaign accounting and resume

The complete campaign used 275 completed requests, 17,317,956 tokens, and
$0.607970368. It had zero rate-limit retry, unreconciled request, runtime
restart, or remaining runtime residue. Resuming all four terminal lineages
added zero child dispatch, request, token, or cost.

The QRS local-vol lineage was cheaper than the generic lineage in this sample:
119 versus 124 requests, 6.64M versus 7.62M tokens, and $0.2365 versus $0.2646.
That does not establish search-efficiency superiority because its selected
mechanism failed the independent-repeat footprint while the generic candidate
reached 68/68.

## Interpretation and next boundary

A0 establishes a complete fresh matched four-lineage run, calibrated
abstention in a non-identifiable family, one repeated binary gain, one safe
cross-task protection, and terminal resume without duplicate work. It also
exposes why quantitative harness verification cannot rely on score deltas
alone: the same +1 may arise from a different property and leave the predicted
quantitative state unchanged or broken.

This post-hoc diagnosis motivates the next predeclared gate: a repeat should
count as mechanism-consistent only when the candidate reproduces the predicted
state, artifact, or relation footprint in addition to improving the official
score. Official performance, footprint consistency, and protection should
remain separate fields; footprint failure should retain the candidate for
refinement rather than silently relabel the score.

This result does not establish QRS superiority over generic evolution,
benchmark-wide or cross-family improvement, sealed/OOS gain, or causal benefit
from tool activation alone. It is one two-family A0 wave. The generic arm won
the scientific local-vol comparison; holdings tied at calibrated abstention;
the QRS target was relation-aligned but did not repeat that relation.

## Evidence

- Compact result: `data/breadth/QF_A0_MATCHED_GENERIC_QRS_RESULT.json`
- Frozen plan: `data/breadth/QF_A0_MATCHED_GENERIC_QRS_PLAN.json`
- Local artifact mirror:
  `results/bc-mirror/qf-a0-matched-generic-qrs-20260823-r1-artifacts`
- Four controller results:
  `results/bc-mirror/qf-a0-matched-generic-qrs-20260823-r1-artifacts/qf-a0-matched-generic-qrs-20260823-r1`
