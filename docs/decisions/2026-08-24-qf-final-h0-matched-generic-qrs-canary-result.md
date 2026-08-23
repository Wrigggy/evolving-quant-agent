# QFBench Final-H0 matched cumulative canary result

Date: 2026-08-24
Status: retained development canary; both terminal incumbents remain Quant-H0

## Decision

Retain the Final-H0 matched cumulative canary as a controller-complete negative
comparison with one useful target-stage binary gain. The generic arm admitted
one candidate in each of the holdings and local-volatility families, but both
candidates failed the fixed resolved-property repeat gate and rolled back. The
QRS arm abstained in both rounds and launched no Worker. Neither arm promoted a
harness, so both campaigns finished with Quant-H0 as the official incumbent.

This result does not establish QRS or generic superiority. It diagnoses an
important search-policy mismatch: on local volatility, QRS precisely recovered
the SVI parameter-admissibility failure that the later R4 refinement repaired,
but `COORDINATED_BREADTH` required the protection trajectory to share the
mechanism and required a positive reusable component episode. Those conditions
made a target-local but reusable quantitative mechanism ineligible for ACT and
reduced search recall in this canary.

## Frozen setup

- Both arms started from the same Quant-H0 harness and followed holdings first,
  then local volatility.
- They used the same authorized evidence, optimize diagnostics, model routes,
  mutation surface, official verifier, reused stage-specific Quant-H0
  comparators, and fixed lifecycle controller.
- Optimize answers were available only to the Evolver after blind Worker runs.
  No Worker or reusable candidate received answer-rich diagnostics.
- This was a development canary. It did not include sealed evaluation.

## Generic arm

### Holdings

The Evolver added and activated `reconcile_outputs`. Target improved from 46/51
to 50/51, resolving four properties. The independent repeat improved from
44/51 to 46/51, but it reproduced only three of the four anchored properties
and introduced a different five-property failure set. The semantic repeat
verdict was `INCONSISTENT`, so the controller rolled the candidate back without
running protection.

This lineage used 81 completed requests, 5,415,621 tokens, and $0.181935356.

### Local volatility

The Evolver added and activated `check_vol_surface_admissibility`. Target
improved from 66/68, reward zero, to 68/68, reward one. It resolved both
`test_forward_variance_local_vol_atm_positive` and `test_svi_a_positive`.
The independent repeat improved only to 67/68: the SVI-`a` property reproduced,
but the forward-variance property did not. The semantic repeat verdict was
therefore `INCONSISTENT`, and the controller again rolled back before
protection.

This is a real official target-stage binary gain, but not a stable promotion.
The lineage used 84 completed requests, 3,907,873 tokens, and $0.127902060.

Across both rounds, generic used 165 completed requests, 9,323,494 tokens, and
$0.309837416.

## QRS arm

The holdings round ended in calibrated `ABSTAIN`: after comparing the target
and successful Brinson trajectory, the Evolver concluded that the remaining
target defects depended on conventions not supported as one reusable shared
mechanism. It launched no Worker. This round used 14 completed requests,
1,245,090 tokens, and $0.049751256.

The local-volatility round also ended in `ABSTAIN`, but its diagnosis was more
specific. The Evolver located the failure in `evaluation_reconciliation`: the
Worker audited derived diagnostics but not fitted SVI parameters, leaving
`a=0.0` on all six expiries. Its discriminating probe found no matching
fitted-parameter boundary in `localvol-barrier`, and State Card retrieval found
no positive reusable calibration-admissibility episode. Under the hard
`COORDINATED_BREADTH` ACT gate, the absence of a shared protection mechanism
blocked the intervention even though the target mechanism itself was correctly
localized. This round used 19 completed requests, 858,394 tokens, and
$0.036081504.

Across both rounds, QRS used 33 completed requests, 2,103,484 tokens, and
$0.085832760. Its lower cost mostly reflects two abstentions and zero Worker
dispatches, not greater search efficiency on successful candidates.

## Accounting and operations

Together the two arms used 198 completed requests, 11,426,978 tokens, and
$0.395670176. Terminal resume dispatched no child and added no request, token,
or cost. Both campaigns completed with zero service restart and zero related
runtime residue.

## Interpretation and boundary

The canary demonstrates the full from-H0 cumulative controller, two-family
continuation, candidate activation, repeat-footprint rollback, calibrated
abstention, incumbent preservation, and idempotent resume. It also shows why
target diagnosis, promotion safety, and search admission should remain distinct:
QRS can correctly identify a finance-specific defect without possessing a
matched protection trajectory that exhibits the same defect.

The generic local-vol target gain is not a promotion or stable harness result;
its repeat lost the forward-variance footprint. The QRS abstentions are not
evidence of poor diagnosis, but they also produce no candidate-quality result.
This experiment supports neither method superiority, sealed or out-of-sample
improvement, benchmark-wide gain, nor causal attribution of a component.

## Artifacts

- Compact result: `data/breadth/QF_FINAL_H0_MATCHED_GENERIC_QRS_CANARY_RESULT.json`
- Frozen plan: `data/breadth/QF_FINAL_H0_MATCHED_GENERIC_QRS_CANARY_PLAN.json`
- Generic campaign mirror:
  `results/bc-mirror/qf-final-h0-matched-generic-qrs-20260824-r1-generic-campaign/`
- QRS campaign mirror:
  `results/bc-mirror/qf-final-h0-matched-generic-qrs-20260824-r1-qrs-campaign/`
