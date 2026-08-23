# QuantCodeEval Live Lineage Canary Result

Date: 2026-08-23  
Status: target and independent repeat complete; protection pending

## Decision

Retain this run as a positive live-execution and lineage-resume canary with a
narrow mechanism result. The shared controller successfully dispatched two
candidate-only QuantCodeEval children, reused the completed Quant-H0 parent,
imported each completed result and its cost once, and advanced from target to
repeat and then to protection. Both fresh candidate Workers actually used
`check_quant_relations`, ended with all six declared relations realized, and
improved the retained T26 parent at the property-count level.

Do not promote or freeze the candidate. The target improved 12/17 to 16/17 but
the independent repeat reached only 14/17, both rewards remained zero, and no
matched T27 protection comparison exists. The controller therefore remains in
`PROTECTION`, stopped after `repeat`, with no terminal decision.

## Setup

- Benchmark/task: public QuantCodeEval T26.
- Parent: retained Quant-H0 from `qce-t26-ap3-20260820-r3-h0`, 12/17,
  reward 0.
- Candidate: retained investigator-seeded QDR-1 relation-audit harness,
  `qdr1-relation-audit-v1`.
- Evaluation: candidate-only live child with the official verifier; the parent
  observation was reused and was not resampled or recharged.
- Worker visibility remained answer-blind. This run evaluated a retained
  candidate; it did not ask a new Evolver to discover one.

## Measured result

| Stage | Official comparison | Component outcome | New requests | New tokens | New cost |
|---|---:|---|---:|---:|---:|
| Target | 12/17 to 16/17, reward 0 to 0 | activated; final 6/6 relations, zero errors/warnings and information-time residual | 55 | 5,352,374 | $0.119301288 |
| Repeat | 12/17 to 14/17, reward 0 to 0 | activated; final 6/6 relations, zero errors/warnings and information-time residual | 54 | 4,304,835 | $0.093733948 |
| Total | two candidate Workers | both realized the declared relation audit | 109 | 9,657,209 | $0.213035236 |

The target failed A10. The repeat failed A10, B5, and B9. Both live children
used one Worker attempt and had zero rate-limit retry or unreconciled request.
The clean six-relation audit therefore remained a mechanism-local observation,
not a complete correctness certificate: the independent repeat still failed
two official HJ-metric properties that the candidate's declared audit regarded
as realized.

## Resume and setup evidence

The first target import rejected the retained parent because its live stage did
not supply an explicit parent run ID. The child service restarted against the
already completed result and incurred no new Worker attempt or cost. After the
stage supplied `qce-t26-ap3-20260820-r3-h0`, controller resume imported the
target and its cost exactly once, advanced to `REPEAT`, and did not rerun the
target child. The independent repeat was then dispatched normally and imported
once. The controller now accounts for both run IDs and exactly the measured
109 requests, 9,657,209 tokens, and $0.213035236.

Two earlier launch attempts are retained as setup failures rather than
benchmark outcomes. One used a runtime config with the wrong model; one loaded
the wrong public task panel and produced a public-role identity mismatch. Each
failed before a model or Worker call and cost zero. After completion all related
services and runtime resources were cleaned up, with no remaining process,
container, or network.

## Interpretation and boundary

This closes the live QuantCodeEval child-dispatch, completed-child reuse,
cross-restart transition/accounting, independent repeat, and actual component-
realization portions of the scale runway. It also supplies repeated evidence
that the retained relation harness changes fresh T26 work: the candidate beat
the same retained 12/17 parent in both samples.

It does not close candidate quality or stable evolution. The run produced no
binary reward gain, did not reproduce 16/17, did not execute matched T27
protection, did not promote a new parent, and did not autonomously discover a
new candidate. It is neither sealed nor benchmark-wide. The immediate state is
therefore `PROTECTION` pending a matched T27 Quant-H0 comparator, not a terminal
success.

## Evidence

- Compact result:
  `data/quantcodeeval/QCE_LINEAGE_LIVE_CANARY_RESULT.json`
- Controller:
  `results/bc-mirror/qce-lineage-live-canary-20260823-r1/CONTROLLER-RESULT.json`
- Target:
  `results/bc-mirror/qce-lineage-qdr1-target-20260823-r1/FULL-CANDIDATE-RESULT.json`
- Repeat:
  `results/bc-mirror/qce-lineage-qdr1-repeat-20260823-r1/FULL-CANDIDATE-RESULT.json`
