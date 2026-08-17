# QuantCodeEval T26 Repeat and Worker-Delivery Recovery — 2026-08-17

## Conclusion

The answer-rich `REFINE` candidate now has a valid independent T26 repeat. Both
valid blind Workers scored 16/17, passed all ten Type-B properties, and passed
the Evolver-predicted B5/B9 HJ-objective properties. The only remaining failure
was A10 end-to-end numeric identity. This supports repeated property-level
benefit and component activation on T26. It does not support an official binary
reward gain or cross-task transfer.

The repeat also improved the remaining numeric discrepancy. A10's worst
relative difference fell from about 25.9% in the first valid candidate sample
to 8.65% in the repeat. The repeat candidate's Sharpe was 0.5932 versus the
reference 0.6493, annual return was 0.08385 versus 0.09178, and maximum drawdown
was -0.4084 versus -0.4250. This is directional numeric progress, not an A10
pass.

The two observed model-delivery failures were repaired at the coordinator
level. A worker can now receive one complete replacement within the same
QuantCodeEval evaluation when either its model stream is lost or the model
returns an empty turn and no `strategy.py` exists. The current Proxy audit
record shape is accepted. Focused tests and read-only replay of the retained r1
and r3 failure records recognized both cases. The live repeat did not trigger
this branch, so live replacement success remains unmeasured.

## Setup

- benchmark: QuantCodeEval T26, declared optimization task;
- candidate source: Evolver run
  `qce-t26-answer-rich-evolver-20260816-r2`;
- model: `deepseek/deepseek-v4-flash-0731`, required DeepSeek provider, no
  fallback;
- execution: one Worker and one verifier at a time on the personal `bc-server`;
- Worker visibility: public T26 instruction, paper, and data only;
- verifier: isolated official 17-property checker;
- candidate: the previously admitted four-role change in tools,
  tool descriptions, agent configuration, and system prompt;
- H0 and Evolver were reused; neither was resampled;
- live run code: commit `707f6c0`; current recovery compatibility fix: commit
  `d3f246f`.

The preflight reran component admission and a positive source-auditor smoke.
It made no model request. The live run was
`qce-t26-answer-rich-candidate-20260817-r4`.

## Worker-delivery repair

Previously, recovery was checked only when an evaluator was resumed. The
candidate wrapper persisted an evaluation failure before that resume, so a
recoverable failure could not be replaced in the same invocation. In addition,
the recovery classifier knew the network-stream signature but not the observed
32,000-reasoning-token empty turn, and it expected the older Proxy audit record
shape.

The repair is deliberately narrow:

1. after a Worker exception or missing-artifact outcome, the evaluator checks
   the retained command and Proxy audit immediately;
2. network stream loss may start one replacement Worker;
3. an empty model response may start one replacement only when the artifact
   contract confirms that no submission file exists;
4. ordinary missing output, timeout, and worker code errors keep their previous
   semantics;
5. QuantCodeEval allows at most one whole-Worker replacement;
6. both the older and current Proxy audit record shapes are accepted.

Focused local tests passed for network and empty-response inline replacement.
The same focused set passed on bc. A broader bc regression produced 148 passes
and one unrelated pre-existing Python 3.12 `pathlib` monkeypatch failure in the
run-watch tests. Read-only classification of the exact retained r1 and r3
attempt records recognized both as recoverable model-delivery failures.

## Live repeat result

The r4 Worker completed normally on its first attempt. No replacement manifest
was created. It used 38 completed model requests and 1,662,929 total tokens,
including 1,563,317 input and 99,612 output tokens. Worker runtime was 1,131.21
seconds.

The trace contained 116 events and 76 tool events. The source-audit tool name
appeared in 12 trace records, the answer-free trace classifier found four
implementation revisions, and the Worker repeatedly changed `strategy.py`
after its initial creation. This confirms real activation of the executable
component and its revise/re-audit workflow.

The official property vector was:

| Property | Result | Main observation |
| --- | --- | --- |
| A2 | PASS | training moments scoped before 2005 |
| A3 | PASS | training functions excluded future data |
| A4 | PASS | deterministic finite coefficient vector |
| A6 | PASS | training moments invariant to OOS permutation |
| A7 | PASS | monthly alignment held |
| A9 | PASS | fixed coefficient vector applied across OOS |
| A10 | FAIL | worst relative metric difference 8.65% |
| B1 | PASS | 50-anomaly universe |
| B2 | PASS | 2004-12 training cutoff |
| B3 | PASS | identity-L2 coefficient solve |
| B4 | PASS | three CV folds |
| B5 | PASS | inverse-covariance HJ CV metric |
| B6 | PASS | fixed out-of-sample SDF coefficients |
| B7 | PASS | market-volatility matching |
| B8 | PASS | log-spaced kappa grid |
| B9 | PASS | HJ objective with an interior optimum |
| B10 | PASS | gamma-to-kappa scaling |

The final official result was Type A 6/7, Type B 10/10, total 16/17, binary
reward 0. All Worker, Proxy, strategy-RPC, and verifier containers were cleaned,
and the user service exited successfully.

## Repetition and claim boundary

| Valid sample | Requests | Tokens | Cost | T26 result | A10 worst relative error |
| --- | ---: | ---: | ---: | ---: | ---: |
| r2 | 52 | 2,214,819 | $0.0438079376 | 16/17 | about 25.9% |
| r4 | 38 | 1,662,929 | $0.1825148080 | 16/17 | 8.65% |

Both valid samples passed B5 and B9, so the property gain the Evolver predicted
is now repeated. The candidate remains below official success because A10
still fails. The two invalid samples, r1 and r3, remain infrastructure/model-
delivery evidence and are not scored as candidate regressions.

The r4 cost was materially higher than the pre-run estimate of roughly
$0.04–$0.08 despite fewer requests and tokens than r2. The finalized provider
audit reports $0.182514808 and is the recorded value. Across the Evolver, r1,
r2, r3, and r4, the retained lineage used 139 completed requests, 5,841,009
tokens, and $0.2923158504.

## Next experiment

The T26 repeat gate is satisfied. The next experiment should not assume that
an arbitrary finance task is transfer. First run a shell-only H0 on a candidate
task and compare its failure signature with T26 on semantic state, pipeline
phase, and observable. Only a matching declared-formula-realization failure is
eligible for unchanged-component transfer.

If no candidate task matches, stay on T26 and let the Evolver refine a second
component for A10: a compact numeric-reconciliation tool that traces the
monthly mean, daily covariance scaling, kappa-to-gamma mapping, coefficient
fit, volatility rescaling, and final metrics in one structured pass. That is a
different component hypothesis from the current static formula-realization
auditor and should be evaluated separately.

Complete r4 evidence is mirrored under
`results/bc-mirror/qce-t26-answer-rich-candidate-20260817-r4`. The tracked
summary is
`results/quantcodeeval-answer-rich-refine-repeat-20260817/RESULT.json`.
