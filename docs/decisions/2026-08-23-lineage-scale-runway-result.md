# Lineage scale runway result

Date: 2026-08-23

Status: retained infrastructure result

## Question

Before a matched multi-benchmark experiment, can the fixed lineage controller
consume both benchmark formats, preserve their different terminal decisions,
reuse an already completed parent observation, charge only new candidate work,
and resume without dispatching duplicate work?

## Cross-benchmark retained-result replay

One zero-model controller plan replayed a retained QFBench quantitative-review
lineage and a retained QuantCodeEval target--repeat--protection lineage. The QF
lineage ended at `HOLD_FOR_REFINE`: Quant-H0 remained the parent and the
Search-v2 candidate remained available for scope refinement. The QuantCodeEval
lineage ended at `PROMOTE`: on T12 the historical parent-to-candidate comparison
was 12/16 to 16/16, the independent repeat was again 12/16 to 16/16, and T19
protection was 18/18 to 18/18 with the property set preserved.

The QF lineage retained its historical accounting of 268 completed requests,
16,153,179 tokens, and $0.575478412. The QuantCodeEval lineage charged only its
three candidate results: 60 completed requests, 1,430,733 tokens, and
$0.0584647056. The reused QuantCodeEval parent was not charged again. A second
controller invocation was identical and added no work or cost. The replay
made zero model requests, Worker sessions, official-verifier executions, or
external child dispatches.

The QuantCodeEval candidate was investigator-seeded after earlier mechanism
localization. Its historical promotion is useful as an integration fixture;
it is not a new autonomous Evolver discovery or a new benchmark result.

## Live parent-comparator reuse canary

The QFBench controller then reused the completed Quant-H0 Brinson observation
and launched only the retained holdings candidate arm. Parent and candidate
both scored 42/42 with reward 1. The candidate invoked its component once, and
the property-wise protection check remained safe. The new candidate arm used
one Worker attempt, eight completed requests, 104,878 tokens, and $0.009652720,
with no rate-limit retry or unreconciled request.

Relative to the earlier independent paired Brinson stage, this canary used half
as many completed requests (8 rather than 16), 37.2% fewer tokens, and 37.4%
less provider cost. Only the request reduction follows mechanically from
omitting one arm; token and cost reductions are observations from this sample.
The terminal state was `PROMOTE` and `FROZEN`. A second controller invocation
left the child report, accounted run set, and cost unchanged and made no new
model or Worker call. The service completed without restart or runtime residue.

## Interpretation and next boundary

These two results close the immediate controller-format, parent-reuse,
candidate-only accounting, property-wise selection, and terminal-resume
runway. They support using this thin controller for a small matched experiment
without rerunning every completed parent arm.

They do not establish a new autonomous search result, benchmark improvement,
sealed gain, or generic-versus-QRS advantage. The cross-benchmark
QuantCodeEval path is a replay over historical official observations, and the
live QFBench canary evaluates an already retained candidate. A scientific
claim still requires a fresh matched generic-versus-QRS search under the same
proposal and evaluation budget, followed by frozen no-feedback evaluation for
any final performance claim.

## Artifacts

- Cross-benchmark compact result:
  `data/breadth/CROSS_BENCHMARK_LINEAGE_REPLAY_RESULT.json`
- Cross-benchmark plan:
  `data/breadth/CROSS_BENCHMARK_LINEAGE_REPLAY_PLAN.json`
- Parent-reuse compact result:
  `data/breadth/QF_PARENT_COMPARATOR_LIVE_CANARY_RESULT.json`
- Parent-reuse plan:
  `data/breadth/QF_PARENT_COMPARATOR_LIVE_CANARY_PLAN.json`
- Live controller result:
  `results/bc-mirror/main0-parent-reuse-canary-20260823-r1/CONTROLLER-RESULT.json`
- Candidate-only child report:
  `results/bc-mirror/main0-parent-reuse-brinson-candidate-20260823-r1/pilot-report.json`
