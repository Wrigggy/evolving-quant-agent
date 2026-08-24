# Public-only credit-migration Quant-H0 prescreen result

Date: 2026-08-24  
Status: valid fresh public-mass-headroom observation; eligibility only

## Decision

Retain `qf-public-only-credit-migration-h0-prescreen-20260824-r1` as one valid
fresh stochastic Quant-H0 observation on `credit-migration-matrix`. The Worker
completed and the official verifier reported 106/107 with reward 0 and exit
code 0.

The predeclared answer-free audit of the fresh public artifacts is evaluable.
The seven AAA-through-CCC count columns in `cohort_sizes.csv` sum to 22,935,
and `cohort_default_rates.csv` reports the same annual issuer totals and the
same 22,935 grand total. Fresh `summary.json` instead reports
`total_transitions=22956`, an exact difference of +21. Under the frozen rule,
the terminal decision is
`ELIGIBLE_FOR_SEPARATE_PUBLIC_ONLY_CREDIT_MIGRATION_PROPOSAL_PLAN`.

This is eligibility only. R1 launched no Evolver, Reviewer, proposal,
candidate Worker, repeat, or protection task. A proposal-and-review stage must
be designed and frozen separately, and no candidate Worker is authorized
unless an admitted nonempty candidate first passes mandatory arm-blind review.

## Frozen scope and information boundary

Deployment source version `d203bd4` authorized one unchanged Quant-H0 Worker
and one official verifier execution on the public QFBench task. The Worker
received only the public task, public task data, and unchanged Quant-H0
harness. This was adaptive development target screening, not sealed
evaluation.

The public audit used only the three fresh Worker artifacts
`cohort_sizes.csv`, `cohort_default_rates.csv`, and `summary.json`. It did not
use an official property identity, verifier output, expected value, reference
answer, optimize diagnostic, or a historical numeric constant. The official
failed-property identity is deliberately absent from this record and must not
enter future Evolver evidence.

A separately authorized Evolver may receive the verbatim public target and
protection contracts and the fresh answer-free Worker trace, final text, and
public output artifacts. It must not receive the official score, reward,
passed or failed counts, failed-property identity, verifier output, checker
behavior, expected values, optimize-only diagnostics, or historical values
used as candidate rules. In particular, 22,935, 22,956, and 21 are measured
artifact values, not reusable candidate constants.

## Measured execution

The single live attempt completed in 16 turns with 20 tool calls and 3 tool
errors. It ran for 290.393 seconds and created eight public artifacts:

- `average_transition_matrix.csv`;
- `cohort_default_rates.csv`;
- `cohort_sizes.csv`;
- `cumulative_default_probs.csv`;
- `generator_matrix.csv`;
- `markov_test.csv`;
- `summary.json`;
- `transition_matrix_deviation.csv`.

The completed trace, final text, and artifacts were nonempty, and the runner
marked the attempt valid for selection. The official verifier reported 106
passed of 107 tests, reward 0, and exit code 0. This establishes aggregate
headroom in one fresh observation without revealing or localizing the trusted
failed property.

All 16 logical provider requests completed successfully on
`deepseek/deepseek-v4-flash-0731`. They used 569,821 input tokens, 31,567
output tokens, and 601,388 total tokens at a provider cost of $0.030813592.
There were zero rate-limited retries, zero requests with a retry index above
zero, zero other nonaccepted requests, and zero unreconciled attempts or
requests. The three Worker tool errors are retained as execution activity; they
were not provider retries and did not invalidate the completed result.

The run remained within every frozen post-run bound: 16 of 40 completed
requests, 601,388 of 3,000,000 tokens, $0.030813592 of $0.15, one Worker, one
official verifier, and roughly five minutes against the 5,400-second wall.

## Fresh public count-mass audit

For each year, the sum of the seven `cohort_sizes.csv` rating columns exactly
matched `cohort_default_rates.csv::total_issuers`:

| Year | AAA-through-CCC cohort sum | Total issuers |
|---|---:|---:|
| 2018 | 3,133 | 3,133 |
| 2019 | 3,510 | 3,510 |
| 2020 | 3,457 | 3,457 |
| 2021 | 3,210 | 3,210 |
| 2022 | 3,299 | 3,299 |
| 2023 | 3,206 | 3,206 |
| 2024 | 3,120 | 3,120 |
| Total | 22,935 | 22,935 |

Fresh `summary.json::total_transitions` was 22,956. The deterministic public
audit therefore finds an exact count-mass mismatch of +21 between the summary
and both reconciled cohort-count surfaces. The mismatch localizes a public
artifact relation that a later proposal may investigate. It does not prove
that this relation caused the one-property official headroom or reveal which
official property failed.

## Runtime and cleanup

The main and health systemd units both ended `inactive/dead` with
`Result=success`, exit code 0, and `NRestarts=0`; no replacement was used. The
Worker, proxy, and verifier sandboxes and the exact proxy network all recorded
`cleaned_up=true` via exact-ID cleanup. The post-run audit found no matching
live container or network residue.

The local mirror intentionally retains the report, evaluation, attempt,
lifecycle, trace, final, public artifact, and accounting files, together with
an empty coordinator-lock file. These are reconstructive evidence, not active
runtime residue.

## Source-level preflight

The focused frozen-plan suite passed 6 tests. A read-only cross-check against
the retained local report, execution record, aggregate score, and three public
audit artifacts passed. The compact result parsed as valid JSON, all 14
credit-migration paper-value macros were both defined and used, and
`git diff --check` passed. A local PDF compile was attempted but the environment
does not provide `latexmk`; this tooling absence does not change the source-
level checks or retained experiment result.

## Interpretation boundary

The measured result combines two observations from the same fresh H0 run: one
official property of aggregate headroom and one exact public count-mass
mismatch. Their co-occurrence satisfies the frozen prescreen branch, but it is
not a causal diagnosis. It does not establish that a mass-reconciliation
component will fix the official result.

No harness mutation, proposal, Reviewer, or candidate Worker ran, so there is
no candidate result, benchmark gain, harness improvement, or search-method
effect. One stochastic H0 is also not a stable baseline, repeat, transfer, or
protection result. The terminal decision permits only the design of a
separately frozen public-only proposal and mandatory review stage; it does not
change main-experiment readiness.

## Artifacts

- Compact result:
  `data/breadth/QF_PUBLIC_ONLY_CREDIT_MIGRATION_H0_PRESCREEN_RESULT.json`
- Frozen plan:
  `data/breadth/QF_PUBLIC_ONLY_CREDIT_MIGRATION_H0_PRESCREEN_PLAN.json`
- Source mirror:
  `results/bc-mirror/qf-public-only-credit-migration-h0-prescreen-20260824-r1`
