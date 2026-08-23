# Public-only holdings R2 Information-Set Review result

Date: 2026-08-24  
Status: Reviewer `INCONCLUSIVE`; controller `HOLD_FOR_REFINE`

## Decision

Retain R2 as one completed Reviewer-only replay that corrects prompt-family
review eligibility without rewriting R1. The arm-blind Candidate
Information-Set Reviewer covered all three declared Worker-visible claims and
found no undeclared exposures, but returned `INCONCLUSIVE` overall. The
controller therefore chose `HOLD_FOR_REFINE` with reason
`information_set_review_inconclusive`.

The existing candidate did not pass review. R2 launched zero Worker sessions,
zero verifier executions, and zero new Evolver proposals. It provides no
Worker-uptake, process-gain, official-gain, or main-readiness result.

## Relationship to R1

R1 remains a frozen historical result: its prompt-only candidate did not meet
the then-predeclared singleton callable-tool activation-binding gate and
stopped at `NON-SINGLETON -> STOP`. R2 does not retroactively replace that
decision.

Instead, R2 applies the corrected procedural distinction that a prompt-family
candidate may be reviewed for semantic provenance without being mislabeled as
a registered callable-tool mutation. Passing review would still be required
before any Worker dispatch. In this replay the candidate reached review, but
did not receive `PASS`.

## Reviewer result

Coverage was `PASS`: the complete candidate diff and all three declared claims
covered the four numbered prompt rules, and the Reviewer found no undeclared
decision-changing exposure.

The claim verdicts were:

- `cross_table_key_canonicalization`: `INCONCLUSIVE`. The public contract
  implies comparable keys and exact-universe coverage but does not directly
  entail the candidate's specific pre-filter inventory and canonicalization
  procedure.
- `numeric_column_coercion`: `INCONCLUSIVE`. The public contract requires
  numeric analytics but does not directly prescribe the missing-value sentinel
  and explicit dtype-coercion procedure added by the candidate.
- `filing_totals_reconciliation`: `PASS`. The public contract directly requires
  reconciliation against summary-page data and the associated reconciliation
  outputs.

Complete coverage is therefore not the same as sufficient provenance. The two
inconclusive claims prevent overall `PASS`, even though there is no undeclared
exposure.

The Reviewer was Worker-invisible and had no promotion authority.

## Accounting

The Reviewer made one request. Response usage reported 4,569 prompt and 12,888
completion tokens, totaling 17,457 tokens. Provider accounting separately
reported 4,565 prompt and 15,390 completion tokens, totaling 19,955. Both token
surfaces are retained rather than treated as interchangeable.

The controller uses response usage for lineage accounting. It therefore added
17,457 tokens to R1's inherited 2,093,270 tokens. Reviewer cost was
$0.02853378, and wall time was 163.786 seconds.

Inherited R1 accounting was 22 requests, 2,093,270 tokens, and $0.061361376.
After the Reviewer, cumulative lineage accounting was 23 requests, 2,110,727
tokens, and $0.089895156.

## Terminal resume audit

The first terminal resume cleared only the `stopped_after_stage` marker. It
created no new dispatch, request, token, cost, or result change. The second
resume observed identical post-marker controller state and result, again with
zero new work or accounting.

This establishes idempotent terminal handling for the recorded hold. It does
not turn the hold into a pass or authorize another stage.

Systemd reported success with `NRestarts=0`, and the post-run audit found zero
related residue.

## Interpretation boundary

R2 demonstrates that the corrected controller can submit a prompt-family
candidate to the mandatory semantic-provenance review and preserve calibrated
`INCONCLUSIVE` rather than forcing `PASS` or `REJECT`. It also shows that claim
inventory coverage and claim support are independent checks.

This is not evidence that the Reviewer is universally correct. More
importantly, it is not candidate success: two of three claims remained
insufficiently entailed by the supplied public contract. No Worker or verifier
ran, so neither uptake nor gain was measured. The candidate remains held for
refinement, and main-experiment readiness is unchanged.

## Artifacts

- Compact result:
  `data/breadth/QF_PUBLIC_ONLY_HOLDINGS_INFORMATION_SET_REVIEW_R2_RESULT.json`
- Reviewer artifact:
  `results/bc-mirror/qf-public-only-holdings-information-set-review-20260824-r2/RESULT.json`
- Controller state:
  `results/bc-mirror/qf-public-only-holdings-information-set-review-replay-20260824-r2-controller-state/CONTROLLER-RESULT.json`
- R1 compact result:
  `data/breadth/QF_PUBLIC_ONLY_HOLDINGS_LINEAGE_R1_PROPOSAL_RESULT.json`
