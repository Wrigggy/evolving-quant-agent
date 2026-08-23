# Public-only FX Quant-H0 prescreen R1 result

Date: 2026-08-24  
Status: invalid setup; `STOP_NO_RESULT`

## Decision

Retain `qf-public-only-fx-h0-prescreen-20260824-r1` as a fully accounted
invalid setup outcome, not as a Quant-H0 baseline or target-selection result.
The preflight made zero model requests. The single live Worker attempt ended as
`model_empty_response` before producing any agent turn, tool action, file, or
artifact. Its raw trace and final response are both empty.

The trusted official verifier subsequently scored the empty submission at
0/16 with reward 0. That score is a measured verifier response, but it does not
measure Worker capability and must not be used as a baseline or to select an FX
optimization target. The terminal decision is `STOP_NO_RESULT`. Any recovery
must be launched only under a separately frozen R2 plan.

## Frozen scope

The frozen R1 plan authorized one normal-budget Quant-H0 Worker and one
official verifier execution on the public QFBench task
`fx-forward-cross-rate`. It launched no Evolver, Candidate Information-Set
Reviewer, candidate Worker, repeat, protection task, or sealed evaluation.

Its intended result was one fresh adaptive-development H0 observation followed
by a public-only audit of the Worker's `results.json`. Because no artifact was
created, that public rounding audit is `N/A`.

## Measured execution

The preflight completed with zero model requests. The live run made one Worker
attempt with the following terminal summary:

- outcome `model_empty_response`;
- 0 turns, 0 tool calls, and 0 tool errors;
- 0 files and an empty artifact list;
- empty `raw-trace.jsonl` and empty `final.txt`.

All three provider requests were recorded as completed. Together they used
9,516 input tokens, 32,305 output tokens, and 41,821 total tokens at a provider
cost of $0.022160676. There were zero rate-limited retries and zero
unreconciled attempts or requests. The third request alone recorded 32,000
output tokens, but the Worker runtime still summarized its result as
`model_empty_response`. This record preserves those two observed accounting
surfaces without inferring an unmeasured root cause.

The official verifier executed successfully against the empty submission and
reported 0 passed and 16 failed tests, reward 0, and exit code 0. There was no
`artifacts/results.json`, so the predeclared public rounding audit could not be
performed.

The service reported `success`, `NRestarts=0`, and one completed score record.
The Worker cleanup flag was true and the post-run audit found zero related
residue.

## Interpretation boundary

R1 shows that completed provider requests and a successful service exit are
not sufficient conditions for a valid Worker observation. A prescreen result
must also contain a materialized Worker trajectory or required artifact before
its official score can enter baseline or target-selection logic.

This result does not establish Quant-H0 capability, a QFBench baseline, an FX
failure class, a public-rounding mismatch, candidate quality, harness gain, or
main-experiment readiness. It also does not establish why the completed third
request failed to materialize as content or tool calls. The only retained
failure label is the observed `model_empty_response`.

R1 is terminal under its frozen plan. A repaired attempt, if run, is a distinct
R2 experiment with a separately frozen setup; it is not an implicit retry or
continuation of this result.

## Artifacts

- Compact result:
  `data/breadth/QF_PUBLIC_ONLY_FX_H0_PRESCREEN_R1_RESULT.json`
- Frozen plan:
  `data/breadth/QF_PUBLIC_ONLY_FX_H0_PRESCREEN_PLAN.json`
- Source mirror:
  `results/bc-mirror/qf-public-only-fx-h0-prescreen-20260824-r1`
