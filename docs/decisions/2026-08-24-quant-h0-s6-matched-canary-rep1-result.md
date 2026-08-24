# Quant-H0-S6 matched construct canary rep1 result

> Date: 2026-08-24  
> Experiment: `qf-quant-h0-s6-matched-canary-20260824-r1-rep1-legacy-first`  
> Status: retained valid repetition; `S6_PROTOCOL_NOT_REALIZED`; rep2 as-is `NO-GO`

## 1. Process and Results

### Goal

The result rejects the current six-stage protocol as a realized starting
substrate. The canary asked whether a thin observable state interface
(S6-Core) or a detailed human-authored workflow (S6-Full) changes fresh
Quant-H0 execution validity, official development-task outcomes, trace
observability, headroom, and cost.

### Method and process

The frozen plan compared legacy Quant-H0, S6-Core, and S6-Full on three
purposively selected public development tasks: stable rates construction,
long holdings reconciliation, and an FX ceiling/overhead control. All arms used
the same DeepSeek V4 Flash route, public inputs, shell tool and descriptor,
rootless runtime, official verifier, task order, and one-at-a-time Worker and
verifier concurrency. S6-Core added only a thin S1--S6 state interface;
S6-Full added detailed human-authored stage advice. No Evolver, Candidate
Reviewer, candidate mutation, history, or sealed task ran.

The clean deployment resolved the plan's future source reference to commit
`2de15fd32a6293a3171c41970a580aa5e8c29d70`. The transient systemd unit ran
from 13:04:53 to 13:54:22 SGT, exited zero, and produced nine valid fresh
Worker/verifier cells. Trusted attempt-side parsers evaluated the S1--S6
markers only for Core and Full; missing markers on legacy are correctly
recorded as not applicable.

### Data and results

The headline result is a protocol failure with a directionally positive but
single-repetition Core score. Every Worker and verifier observation was valid,
yet only two of six Core/Full cells realized the complete marker protocol.

| Task | Legacy | S6-Core | S6-Full | Core--Legacy | Full--Core |
|---|---:|---:|---:|---:|---:|
| `swap-curve-bootstrap-ois` | 19/19 | 19/19 | 19/19 | 0 | 0 |
| `13f-amendment-aware-crowding` | 47/51 | 49/51 | 48/51 | +2 | -1 |
| `fx-forward-cross-rate` | 36/37 | 37/37 | 36/37 | +1 | -1 |
| Total | 102/107 | 105/107 | 103/107 | +3 | -2 |

Legacy left five failed properties in this repetition. Core closed three of
five (60%), while Full closed one of five (20%). These are descriptive
development values, not a population macro or stable capability estimate.

| Arm | Valid cells | Complete protocol | Turns / tools / errors | Requests | Tokens | Cost |
|---|---:|---:|---:|---:|---:|---:|
| Legacy | 3/3 | N/A | 60 / 66 / 6 | 60 | 2,583,626 | $0.111511560 |
| S6-Core | 3/3 | 1/3 | 47 / 60 / 10 | 47 | 2,029,778 | $0.095227936 |
| S6-Full | 3/3 | 1/3 | 50 / 59 / 9 | 50 | 1,667,201 | $0.092089636 |

Run-level accounting reconciled 157/157 completed requests, 6,280,605 total
tokens, and $0.298829132 with zero retry, nonaccepted request, or unreconciled
attempt. All limits were satisfied. Exact-ID cleanup completed for all 36
lifecycle records; no process, container, network, volume, or run-specific
namespace remained. The zero-byte coordinator lock path remained without an
owner and is an inert lock artifact. Rep2 was not created or launched.

### Case study

The FX Core cell demonstrates the intended interface. Its trusted
`research-state-trace.json` records S1 through S6 in order with one ENTER and
one COMPLETE for each stage, no missing stage, no issue, and no malformed
marker. The fresh Worker scored 37/37 versus legacy's 36/37 while using eight
requests and $0.024534424. This shows that the protocol can be realized and
coexist with a correct artifact in one cell; it does not show that markers
caused the score.

The holdings Core cell demonstrates the blocker. It scored 49/51 versus
legacy's 47/51, but only S2 and S5 were fully accounted. S1, S3, and S4 had
incomplete entry/completion pairs, and S6 had COMPLETE without ENTER. Full
also failed on holdings, and Full FX emitted the unsupported
`[QSTATE S4 REVISIT]` form. The same run therefore shows that official
improvement and stage observability are separate outcomes.

Canonical evidence is retained at
`results/bc-mirror/qf-quant-h0-s6-matched-canary-20260824-r1-rep1-legacy-first/`.
The compact summary is
`data/breadth/QF_QUANT_H0_S6_MATCHED_CANARY_REP1_RESULT.json`.

## 2. Analysis

Core is not yet an acceptable QRS substrate because observability is part of
its construct, not an optional diagnostic. Four of six applicable cells lacked
an accountable S1--S6 protocol, exceeding the frozen threshold of more than
one valid violation and selecting `S6_PROTOCOL_NOT_REALIZED`. The result does
not invalidate the nine official observations; it invalidates the claim that
the current skill reliably produces the intended trace interface.

The +3 Core property delta is useful but narrow. It occurred in one fresh
development repetition over a score-informed, purposive panel. Core also used
13 fewer requests, 553,848 fewer tokens, and $0.016283624 less than legacy, so
the thin interface did not impose measured aggregate overhead in rep1. Neither
direction can be called stable until an independently frozen repetition exists
after the construct itself is realized.

Full provides no evidence that detailed human-authored stage advice is a
stronger baseline. It tied Core on swaps, lost one property on holdings, and
lost one on FX. Its total was two properties below Core even though its cost
was slightly lower. The frozen `FULL_HUMAN_WORKFLOW_ADVANTAGE` condition is not
met, and Full's detailed methods must not be moved into Core on the basis of
this run.

The result also warns about Evolver headroom. Core closed 60% of the fresh
legacy headroom in this panel. If a repaired Core repeats that direction, the
right response is to disclose the human-scaffold gain and freeze harder,
outcome-blind public development tasks. Weakening Core to manufacture search
headroom would confound the paper's method story.

## 3. Problems and Open Questions

- **Protocol realization is the blocking defect.** The registered skill was
  reachable, but marker pairs were often omitted or malformed. The repair must
  address skill loading and the small marker grammar without adding concrete
  task methods or answer-derived predicates.
- **Rep1 cannot estimate stability.** The fresh legacy FX cell scored 36/37
  despite an earlier public-only 37/37 observation, directly showing Worker
  sampling variation. Core's +3 therefore remains one-repetition evidence.
- **A repaired Worker changes the treatment identity.** The pre-frozen rep2
  cannot be relabeled as the matched repeat of a repaired Core/Full package.
  A new matched canary must freeze both repetitions before execution.
- **The panel is deliberately selected.** These three tasks calibrate stable
  rates work, long reconciliation, and a ceiling control; they are not an
  outcome-blind QFBench breadth sample.
- **Candidate provenance remains separate.** This no-candidate canary did not
  exercise the mandatory pre-Worker Candidate Information-Set Reviewer and
  does not close the main-experiment answer boundary.

## 4. Next Plan

1. Repair only S6 skill loading and marker realization, preserving the shell
   descriptor, model/runtime settings, public-only boundary, and open concrete
   stage methods.
2. Freeze a new matched Legacy/Core/Full protocol canary. Do not use rep1
   scores to replace tasks, add task-specific checks, or select methods.
3. Require protocol realization and matched validity before accepting Core as
   the QRS starting substrate; treat marker coverage as observability, never as
   quantitative correctness.
4. If a realized Core still closes substantial headroom, freeze a separate
   outcome-blind Legacy-versus-Core breadth/headroom map and keep Full confined
   to the disclosed construct calibration.
5. Keep the main QRS experiment at `NO-GO` until both the substrate protocol
   and the universal exact-candidate pre-Worker Review path have their own
   fresh retained evidence.

