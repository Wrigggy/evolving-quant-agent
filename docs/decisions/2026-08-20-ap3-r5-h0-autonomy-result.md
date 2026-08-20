# AP-3 r5 Quant-H0 autonomy result

Date: 2026-08-20

## Question

Can the bounded outer loop start from Quant-H0, discover a harness component,
run a Worker experiment, index the resulting observation, and decide whether to
submit a final candidate without experimenter promotion?

This was a cold-history campaign. Earlier T26 candidates, the QDR-1 Fresh
15/17 result, and answer-rich historical repairs were not exposed to the
Evolver. The only search evidence came from the fresh H0 attempt and the
experiment produced inside r5.

## Trajectory

The answer-blind Quant-H0 Worker completed 29 model requests and scored 13/17,
reward zero. Evolver round one then used 22 requests and selected a
`quantitative_representation` hypothesis: the Worker might not be reconciling
the frequency and provenance of shared estimator inputs across monthly and
daily panels.

The Evolver created a new `convention-reconciliation` skill, changed the system
prompt and agent graph, passed component smoke and candidate admission, and
submitted ACT. It also predeclared a competing explanation involving CV output
schema/signature conventions and a decision-changing observation.

The Evolver chose a six-iteration repair probe over the run-local H0 artifact.
The Worker loaded the new skill on assistant turn one, proving actual component
activation. The probe completed five requests, but the artifact remained
unchanged and the official score remained 13/17, reward zero.

Round two read both the persisted prediction and the probe observation. It
correctly concluded that skill activation was not sufficient to cause a repair.
Because the probe made no edit, it also correctly kept the beta-frequency,
CV-output, and signature hypotheses as untested rather than claiming that one
had been falsified by the unchanged score. With no discriminating evidence and
no second probe permitted in this bounded round, it returned calibrated
ABSTAIN. No final Worker was launched.

The complete campaign used 69 model requests and cost $0.228217836: 29 requests
and $0.097305552 for H0, 22 and $0.09128706 for round one, 5 and $0.004599284
for the Worker probe, and 13 and $0.03502594 for round two. There were no
rate-limit retries or coordinator restarts.

## Conclusion

r5 validates the full bounded autonomy mechanism from Quant-H0 through a
calibrated stop:

`fresh H0 -> autonomous hypothesis/component -> admitted ACT -> Worker
activation -> official observation -> indexed comparison -> updated ABSTAIN`.

This is stronger than the earlier AP-3 r3 result because the selected component
actually activated, the Worker delivered and was officially evaluated, and
round two received the persisted prediction as well as the observation. It is
not a helpful-candidate or benchmark-performance result: the probe produced no
artifact or score change, round two submitted no candidate, and no final Worker
ran.

The immediate search gap is now narrower. A passive reconciliation skill can be
loaded without changing work. Before broad multi-task scheduling, the next
coordination experiment should require each selected probe to expose an
observable action target---an edit, a concrete validator finding, or a
well-supported skip---and should aggregate two task trajectories only to test
whether the same Research-State failure recurs. It should not evaluate every
candidate on every task.

Evidence is mirrored at
`results/bc-mirror/qce-t26-ap3-20260820-r5/`; the compact record is
`data/quantcodeeval/AP3_R5_H0_AUTONOMY_RESULT.json`.
