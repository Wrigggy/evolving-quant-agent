# Public-only holdings R3 review-refinement result

Date: 2026-08-24  
Status: proposal `ACT` admitted; mandatory Review `REJECT`; controller `HOLD_FOR_REFINE`

## Decision

Retain R3 as one complete answer-free proposal-to-review lineage that correctly
stopped an insufficient candidate before Worker evaluation. The
`LINEAGE_REFINEMENT` Evolver produced an admitted prompt-only `ACT` with three
declared Worker-visible claims. The mandatory arm-blind Candidate
Information-Set Reviewer then evaluated cumulative Quant-H0-to-c2 material,
returned `REJECT` overall and for coverage, and left the controller at
`HOLD_FOR_REFINE` with reason `information_set_review_reject`.

No Worker, verifier, or selected probe ran. R3 therefore establishes a
proposal-and-review control-flow result, not candidate effectiveness or
benchmark gain.

## Process and measured result

Stage A started from the exact retained R1 c1 prompt candidate and supplied the
Evolver with the answer-free R3 `LINEAGE_REFINEMENT` evidence view. Reviewer
feedback in that view was Worker-hidden and could guide removal, narrowing, or
regrounding, but it was not public support for a Worker-visible rule.

The Evolver returned `ACT`, and all nine admission checks passed. The only
changed file was `systemprompt.md`. Four existing lines were replaced by four
refined lines, for a net increase of 442 bytes. Declared and actual roles were
both `systemprompt`; no executable code, registered tool, or other candidate
file changed.

The refined proposal declared three prompt claims:

- `cross_table_key_canonicalization_and_universe_coverage`;
- `numeric_and_missing_value_discipline`;
- `summary_page_reconciliation`.

The proposal made 17 completed requests, used 1,688,240 tokens, and cost
$0.060657984. It recorded zero incomplete requests and no missing token or cost
accounting. The frozen proposal stop dispatched neither the selected probe nor
any Worker or verifier.

Stage B resumed the same controller state and issued exactly one arm-blind
DeepSeek V4 Pro Reviewer request. The trusted package reconstructed cumulative
Quant-H0-to-c2 Worker-visible material rather than only c1-to-c2 changes. It
contained the three declared claims, one complete 5,355-character public target
instruction that exactly matched the pre-existing evidence file, and zero
optimize-only sources. Search-arm identity and the answer-free refinement
feedback were absent from the package.

## Reviewer outcome

The Reviewer returned overall `REJECT`. At claim level:

- canonicalization plus universe coverage was `INCONCLUSIVE`: the public
  instruction states the exact universe and mutually consistent report-period
  fields but does not directly require mandatory pre-join encoding inspection
  and canonicalization;
- numeric and missing-value discipline was `INCONCLUSIVE`: the instruction
  requires numeric analytics and row filtering but does not prescribe the
  candidate's string-`nan`, coercion, and post-aggregation dtype procedure;
- summary-page reconciliation was `PASS`: both the comparison and its recorded
  differences and checks are explicit public requirements.

Coverage was separately `REJECT`, demonstrating that plausible claim support
does not repair an incomplete exposure inventory. The candidate prompt required
two additional operations that its claims omitted:

1. report retained-set cardinalities after universe-coverage verification;
2. confirm dtypes after aggregation.

The Reviewer was Worker-invisible and had no promotion authority. The
controller recorded `HOLD_FOR_REFINE`; the candidate did not pass and no later
stage was eligible.

## Accounting

The Reviewer response reported 4,872 prompt and 13,293 completion tokens,
totaling 18,165. Provider accounting separately reported 4,877 prompt and
15,744 completion tokens, totaling 20,621. Both token surfaces are retained;
the controller consistently used response usage. The single Reviewer request
cost $0.028964012 and took 162.231 seconds.

Stage A plus Stage B cumulative accounting was 18 completed requests,
1,706,405 controller-accounted tokens, and $0.089621996. This is exactly 17
proposal requests, 1,688,240 proposal tokens, and $0.060657984 plus one Review
request, 18,165 response-usage tokens, and $0.028964012.

## Terminal and cleanup audit

Two same-state terminal resumes ran without external-run approval. The first
cleared only `stopped_after_stage`; it left the candidate hold, accounted
proposal and review identities, and all cost fields unchanged. The second was
exactly stable. Both remained `candidate_hold` / `HOLD_FOR_REFINE` at 18
requests, 1,706,405 tokens, and $0.089621996, with zero new run directory,
dispatch, request, token, or cost.

Both systemd stages completed successfully with `NRestarts=0`. Evolver and
proxy sandbox and network cleanup completed, no experiment process or later
stage remained, and related residue was zero. A public-instruction comparison
temporarily created `/tmp/qf-r3-review-public-source-check`; root removed it
successfully, so final residue remained zero.

## Analysis

R3 is a useful negative result because the mandatory Reviewer detected two
different defects before any expensive or potentially misleading Worker
evaluation. It withheld support from two procedures that remained engineering
priors rather than direct consequences of the supplied public instruction, and
it independently detected two Worker-visible instructions missing from the
claim inventory.

The result also shows that refinement against Reviewer feedback is not
automatically self-correcting. The Evolver narrowed and regrounded the prompt,
but preserved procedures that the supplied public source could not entail and
failed to make its declared claims coextensive with the full prompt. A later
candidate would need to remove or separately and safely support those
procedures and enumerate every remaining decision-changing exposure. That is a
new proposal question, not permission to send c2 to a Worker.

## Interpretation boundary

R3 measures proposal construction, candidate admission, trusted package
construction, claim and coverage classification, controller hold, dual
accounting, terminal idempotence, and cleanup. It does not measure Worker
uptake, task score, process gain, official benchmark improvement, stable reuse,
transfer, or main-experiment readiness. No benchmark-gain claim is available
because no Worker or verifier ran.

## Next step

Do not evaluate c2. If work continues, freeze a new refinement whose prompt and
claim inventory are mechanically coextensive and whose normative rules are
either directly entailed by the supplied public instruction or removed. The
new candidate must again pass the same mandatory arm-blind cumulative review
before any separately frozen Worker plan becomes eligible.

## Artifacts

- Compact result:
  `data/breadth/QF_PUBLIC_ONLY_HOLDINGS_REVIEW_REFINEMENT_R3_RESULT.json`
- Frozen plan:
  `data/breadth/QF_PUBLIC_ONLY_HOLDINGS_REVIEW_REFINEMENT_R3_PLAN.json`
- Proposal:
  `results/bc-mirror/qf-public-only-holdings-refine-proposal-20260824-r3/proposal-report.json`
- Reviewer:
  `results/bc-mirror/qf-public-only-holdings-information-set-review-20260824-r3/RESULT.json`
- Controller:
  `results/bc-mirror/qf-public-only-holdings-review-refinement-20260824-r3-controller-state/CONTROLLER-RESULT.json`
