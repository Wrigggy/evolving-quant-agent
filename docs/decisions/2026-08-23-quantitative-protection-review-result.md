# Quantitative protection review result

**Date:** 2026-08-23

**Status:** Retained QPR-0/QPR-1/QPR-2 development result. The quantitative
review mechanism is positive for calibrated triage, Reviewer escalation, and
evidence-efficient stopping. The Search-v2 candidate remains inconclusive and
is not promoted.

**Protocol:**
[quantitative protection review plan](2026-08-23-quantitative-protection-review-plan.md)

**Compact result:** `data/breadth/QPR_QUANTITATIVE_PROTECTION_REVIEW_RESULT.json`

## Decision

Retain the three-stage Quantitative Protection Review canary:

- QPR-0 matched all four predeclared deterministic classifications;
- one answer-free QPR-1 Reviewer call returned all four expected directional
  classifications, including escalation of the Search-v2 gray case and
  `HOLD_FOR_REFINE` for the Main-0B hard negative; and
- QPR-2 ran the one authorized paired protection repeat. The exact frozen
  Search-v2 candidate remained at 38/39 while its failed leaf rotated, and the
  matched parent moved from its prior 38/39 observation to 39/39.

Under the predeclared conflicting-evidence branch, QPR-2 is therefore
**still `INCONCLUSIVE`**. Stop additional repeats, do not promote the
candidate, and retain the component plus both protection observations for
scope refinement.

## QPR-0 deterministic replay

The zero-model replay exercised four answer-free cases:

| Case | Retained outcome |
|---|---|
| same-harness 38/39 to 35/39 | `INCONCLUSIVE`, within provisional variability, no extra run |
| Search-v2 38/39 to 38/39 property swap | `INCONCLUSIVE`, unresolved, paired protection repeat |
| Main-0B 35/39 to 29/39 | `FAIL`, meaningful candidate regression, harness--Worker interaction, `HOLD_FOR_REFINE` |
| aggregate tie with a critical public-relation break | `FAIL`, meaningful candidate regression, `HOLD_FOR_REFINE` |

All four matched their predeclared classifications. QPR-0 made no model call,
Worker call, or official-verifier execution. This is a rule preflight, not
evidence that a learned Reviewer can discover those distinctions.

Artifact: `data/breadth/QPR0_REPLAY_RESULT.json`.

## QPR-1 answer-free Reviewer canary

One `deepseek/deepseek-v4-pro` Reviewer request processed the four frozen
development-protection cases. It returned:

- same-harness variability: `WITHIN_PROVISIONAL_VARIABILITY`, attributed to
  `WORKER_TRAJECTORY`, with no extra run;
- Search-v2 property swap: `UNRESOLVED`, requesting a paired protection repeat;
- Main-0B: `MEANINGFUL_CANDIDATE_REGRESSION`, attributed to
  `HARNESS_WORKER_INTERACTION`, diagnosing `UPSTREAM_STATE_UNVERIFIED`, with
  `HOLD_FOR_REFINE`; and
- aggregate tie plus public-relation break: meaningful regression with
  `PUBLIC_RELATION_BROKEN` and `HOLD_FOR_REFINE`.

The call used 6,364 response-accounted tokens, cost $0.00966108, and took
56.969 seconds. The Main-0B case was deliberately constrained as a hard
negative in the Reviewer prompt. QPR-1 therefore validates structured
discrimination, schema compliance, and calibrated escalation under that
contract; it does not establish autonomous discovery of the Main-0B diagnosis.

Artifacts:

- `data/breadth/QPR1_REVIEW_CASES.json`;
- `results/qpr1-reviewer-20260823-r1/RESULT.json`.

## QPR-2 paired protection repeat

QPR-2 froze the exact Search-v2 candidate and ran one matched
`localvol-barrier` parent/candidate pair:

| Arm | Official result | Failed leaf |
|---|---:|---|
| matched Quant-H0 parent | 39/39, reward 1 | none |
| frozen Search-v2 candidate | 38/39, reward 0.96 | `barrier_outputs_reasonable` |

The prior protection observation for the same candidate was also 38/39 and
reward 0.96, but failed `vanilla_mc_close_to_surface`. The prior parent was
38/39 and failed `barrier_outputs_reasonable`; the new parent passed 39/39.
Thus neither the candidate aggregate nor a single recurring failed leaf
identifies a stable candidate effect.

The answer-free candidate trajectory nevertheless exhibited the relevant
public quantitative relations: unit-consistent forward parity, complete
35-node call and local-vol surfaces without missing values, Monte Carlo vanilla
within 0.9 percent of the surface value, nonnegative barrier value no greater
than vanilla, and barrier-hit plus survival-probability closure. No stable
critical public-relation break was observed.

The candidate's one-property deficit is inside the preregistered provisional
margin of three, but that count is not sufficient for promotion. The two
candidate failures rotated across different downstream leaves while the parent
also varied. This activates the predeclared conflicting-evidence outcome:

```yaml
protection_state: INCONCLUSIVE
terminal_interpretation: STILL_INCONCLUSIVE
additional_repeat: STOP
candidate_promotion: false
component_disposition: RETAIN_FOR_SCOPE_REFINEMENT
```

The pair used 66 completed requests, 4,492,623 tokens, and $0.164949156, with
zero rate-limit retry, unreconciled request, or runtime restart.

Artifact:
`results/bc-mirror/qpr1-searchv2-localvol-barrier-protection-repeat-20260823-r1/`.

## Cost and interpretation

QPR-0 cost zero. QPR-1 and QPR-2 together cost $0.174610236. The measured
Quant-H0 observations on this protection task are now 35/39, 38/39, and 39/39,
a four-property observed range. This is not a variance estimate. The margin of
three was an explicit mechanism-canary rule, not a statistically calibrated
main-experiment non-inferiority threshold. Any main experiment must predeclare
its margin from additional matched Quant-H0 repetitions.

The positive mechanism result is narrow:

1. deterministic triage does not collapse ordinary baseline movement, an
   ambiguous property swap, and a clear six-property integration failure into
   one rollback rule;
2. the answer-free Reviewer escalates the ambiguous case while preserving the
   hard negative; and
3. one paid repeat resolves the next action even though it does not resolve the
   candidate: stop spending, retain the component, and refine scope.

This is calibrated protection triage and evidence-efficient stopping. It is
not a promoted stable researcher, proof of component reuse, formal statistical
non-inferiority, autonomous failure discovery, sealed gain, or benchmark-level
improvement. The fixed controller remains the promotion authority, and the same
review policy must apply to generic and QRS arms.

## Controller integration

The thin lineage controller now supports this path behind an explicit opt-in:
`PROTECTION` to `PROTECTION_REVIEW`, at most one `PROTECTION_REPEAT`, and then
either ordinary promotion or `HOLD_FOR_REFINE`. The measured Search-v2 replay
ends in `HOLD_FOR_REFINE`, keeps Quant-H0 as the incumbent, retains the candidate
source, and does not archive or promote it. Saved review and child-run IDs make
resume idempotent; the Reviewer request, tokens, and provider cost are counted
once. This is deterministic infrastructure validation, not another benchmark
result or a claim that the next refinement will succeed.

Compact campaign record:
`data/breadth/QPR_QUANTITATIVE_PROTECTION_REVIEW_RESULT.json`.
