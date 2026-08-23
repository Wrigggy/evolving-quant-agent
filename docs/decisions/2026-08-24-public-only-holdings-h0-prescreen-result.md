# Public-only holdings Quant-H0 prescreen result

Date: 2026-08-24  
Status: valid fresh headroom observation; no follow-on in this plan

## Decision

Retain `qf-public-only-holdings-h0-prescreen-20260824-r1` as one valid fresh
stochastic Quant-H0 observation on `13f-amendment-aware-crowding`. The Worker
completed and the official verifier reported 47/51 with reward 0. Under the
frozen classification rule, the terminal decision is
`HOLDINGS_HEADROOM_FOR_SEPARATE_PUBLIC_ONLY_PLAN`.

This decision identifies aggregate headroom; it does not authorize a proposal
or candidate. The run consumed 47 completed requests, exceeding the frozen
post-run threshold of 40. The completed execution and accounting are retained,
but this plan dispatches no follow-on. Any later public-only proposal requires
a separately frozen plan.

## Frozen scope

The deployment used source version `694eea8`. The frozen prescreen authorized
one unchanged Quant-H0 Worker and one official verifier execution on the public
QFBench holdings task. It launched no Evolver, Candidate Information-Set
Reviewer, proposal, candidate Worker, repeat, protection task, or sealed
evaluation.

The fresh Worker received only the public task, public task data, and unchanged
Quant-H0 harness. Prior results, contaminated candidates, official answers,
verifier feedback, and follow-on design were not Worker-visible.

## Measured execution

The preflight completed with zero model requests. The single live Worker
attempt completed in 47 turns with 52 tool calls and 13 tool errors. It created
eight files, all retained as artifacts:

- `cleaning_audit.csv`;
- `crowded_securities_latest.csv`;
- `effective_holdings.csv`;
- `filing_resolution.csv`;
- `manager_metrics.csv`;
- `overlap_latest.csv`;
- `summary.json`;
- `turnover.csv`.

The official verifier reported 47 passed and 4 failed tests, reward 0, and exit
code 0. This is a valid Worker observation and establishes score headroom, but
one stochastic run is not a stable H0 baseline estimate.

The 47 completed provider requests used 2,409,646 input tokens, 54,930 output
tokens, and 2,464,576 total tokens at a provider cost of $0.061991920. There
were zero retries, failed requests, and unreconciled attempts or requests.

The request count exceeded the frozen post-run threshold of 40. Total tokens
remained below the 3,000,000 threshold, and provider cost remained below the
$0.15 threshold. Because these were post-run accounting thresholds, the
already completed Worker result is retained; the breach prohibits follow-on
dispatch under R1.

The service reported `success`, `NRestarts=0`, and one completed score record.
Worker cleanup succeeded and the post-run audit found zero related residue.

## Trusted evaluator-only research record

The trusted verifier recorded these four failed tests:

- `test_outputs.py::test_reference_match_resolution_and_holdings_outputs`;
- `test_outputs.py::TestEffectiveHoldings::test_weights_sum_to_one_by_book`;
- `test_outputs.py::TestTurnover::test_summary_max_turnover_matches`;
- `test_outputs.py::TestOverlapLatest::test_summary_max_overlap_matches`.

These identities are retained only for evaluator-side reconstruction of this
research record. They, their traces, expected values, and inferred predicates
must not enter Evolver evidence, a public-only proposal input, candidate
selection, reusable harness components, Worker-visible prompts or tools,
memory, middleware, or routing. A future proposal must be localized from
public task evidence and public Worker artifacts only.

## Interpretation boundary

The measured claim is deliberately narrow: one fresh Quant-H0 execution was
valid and left four official properties of headroom. The result is not a
candidate run, a harness mutation, a Reviewer result, or a comparison against
an evolved harness. It therefore supplies no harness-gain or search-method
claim.

It is also only one stochastic H0 sample. The 47/51 result cannot be promoted
to a stable baseline distribution or benchmark-wide performance statement.
The terminal classification only makes holdings eligible for consideration in
a separately frozen public-only plan; it does not say that a public-grounded
intervention has already been found.

## Artifacts

- Compact result:
  `data/breadth/QF_PUBLIC_ONLY_HOLDINGS_H0_PRESCREEN_RESULT.json`
- Frozen plan:
  `data/breadth/QF_PUBLIC_ONLY_HOLDINGS_H0_PRESCREEN_PLAN.json`
- Source mirror:
  `results/bc-mirror/qf-public-only-holdings-h0-prescreen-20260824-r1`
