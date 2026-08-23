# Public-only FX Quant-H0 prescreen R2 result

Date: 2026-08-24  
Status: valid setup recovery; `CLOSE_FX_NO_HEADROOM`

## Decision

Retain `qf-public-only-fx-h0-prescreen-20260824-r2` as the sole valid fresh
Quant-H0 observation in the R1/R2 setup path. R2 was frozen separately after
R1 stopped at `model_empty_response`; it is a setup recovery, not an
experimental repeat of a valid baseline.

The R2 Worker completed, created `artifacts/results.json`, and passed all 37
official tests with reward 1. The public-only audit found no four-decimal
mismatch in the fresh `forward_cross_rates_3M` values. The predeclared terminal
decision is therefore `CLOSE_FX_NO_HEADROOM`. No Evolver, Reviewer, proposal,
candidate Worker, repeat, or protection task was launched.

## Frozen scope

The R2 plan authorized one normal-budget Quant-H0 Worker and one official
verifier execution on the public QFBench task `fx-forward-cross-rate`. The
Worker received only the public task, public task data, and unchanged Quant-H0
harness. R1 execution evidence and retained selection evidence were not
Worker-visible.

The recovery remained adaptive development rather than sealed evaluation. Its
only post-run selection signal was the frozen public audit of the new Worker's
own artifact. A full official score required closure without a proposal.

## Measured result

The preflight completed with zero model requests. The single live Worker
attempt completed in 5 turns with 7 tool calls, 0 tool errors, and 1 file. It
created `artifacts/results.json` with a size of 6,534 bytes.

The official verifier reported 37 passed and 0 failed tests, reward 1, and exit
code 0. This is a valid fresh observation, unlike R1's empty-submission score.

The five completed provider requests used 125,242 input tokens, 34,439 output
tokens, and 159,681 total tokens at a provider cost of $0.024900196. There were
zero rate-limited retries and zero unreconciled attempts or requests.

The public audit checked all 15 bid, ask, and mid values under
`forward_cross_rates_3M`. Every numeric value equaled the same value rounded to
four decimal places; mismatch count was 0. This audit used only the public
instruction and the fresh R2 Worker artifact.

The service reported `success`, `NRestarts=0`, and one completed score record.
Worker cleanup succeeded and the post-run audit found zero related residue.

## R1/R2 accounting and interpretation

Together, R1 and R2 consumed 8 completed requests, 201,502 total tokens, and
$0.047060872. This is setup-path accounting, not two baseline samples: R1 is
an invalid empty-response run, while R2 is the only valid Worker observation.

R2 demonstrates recovery to one successful Quant-H0 execution and closes this
specific FX branch without search. It does not show stable H0 performance: one
stochastic full-score observation is not a repeat or a baseline distribution.
It also cannot establish harness improvement because no mutable harness,
Evolver proposal, Reviewer verdict, or candidate Worker was involved.

The full score and absence of the predeclared public mismatch remove the
headroom required for the proposed FX intervention. The valid conclusion is
target closure, not successful evolution and not a benchmark-wide result.

## Artifacts

- Compact result:
  `data/breadth/QF_PUBLIC_ONLY_FX_H0_PRESCREEN_R2_RESULT.json`
- Frozen R2 plan:
  `data/breadth/QF_PUBLIC_ONLY_FX_H0_PRESCREEN_R2_PLAN.json`
- Source mirror:
  `results/bc-mirror/qf-public-only-fx-h0-prescreen-20260824-r2`
- R1 compact result:
  `data/breadth/QF_PUBLIC_ONLY_FX_H0_PRESCREEN_R1_RESULT.json`
