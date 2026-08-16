# QuantCodeEval T26 Answer-Rich REFINE Canary — 2026-08-17

## Conclusion

The answer-rich Evolver mechanism produced the strongest T26 property result
measured so far and, importantly, did so with a real multi-component harness
change rather than another prompt-only mutation.

The Evolver inferred a persistent declared-formula-realization failure from
the retained 13/17, 14/17, and 12/17 T26 attempts. It implemented a reusable
static quant-contract auditor, registered it as a Worker tool, and bound FAIL
results to artifact revision. The one valid fresh blind Worker activated that
component and scored 16/17. B5 and B9, the two properties explicitly predicted
by the Evolver, both changed to PASS. All ten Type-B properties passed. A10
end-to-end numeric identity remained the only failure.

This is a positive mechanism-localization result and a positive single-sample
property result. It is not yet a stable improvement, an official binary-reward
gain, or a cross-task transfer result. Two attempted replacement Workers were
invalid before scoring because of model-route failures, so repeat stability
remains unmeasured.

## Setup

- benchmark: QuantCodeEval T26, optimization task;
- model: `deepseek/deepseek-v4-flash-0731` through the required DeepSeek route;
- execution: one rootless-Docker Evolver or Worker at a time on personal
  `bc-server`;
- Worker visibility: public T26 instruction, paper, and data only;
- Evolver visibility: retained post-run item-level diagnostic from the three
  already scored blind Worker attempts;
- verifier: official 17-property T26 checker in the isolated trusted role;
- H0 and prior candidates were reused; no baseline was resampled;
- source commits: `38e0ffb` for answer-rich feedback and `45fb154` for the
  current discovery-decision runner compatibility fix.

The proposal-only Evolver reused the available 85-task rootless runtime as its
container substrate, but its authorized evidence contained only the T26
optimization card and retained T26 diagnostic. No QFBench answer entered the
proposal. Candidate Worker evaluation used the existing T26/T27 QuantCodeEval
roles and the T26 task panel.

## Evolver result

Run: `qce-t26-answer-rich-evolver-20260816-r2`.

The Evolver registered legal `ACT` with search operator `REFINE` and selected
`tools` as the primary component. Its complete mutation touched four roles:

- `tools/quant_contract_audit.py`: deterministic source audit for an
  inverse-covariance-weighted CV score, identity-ridge solve, and consistent
  training gate;
- `tool_descriptions/audit_strategy_source.tool.yaml`: Worker-facing callable
  contract;
- `agent.yaml`: tool registration and reachability;
- `systemprompt.md`: audit, revise, re-audit, smoke, and final-artifact loop.

The candidate passed positive/negative tool smokes and full-harness admission.
The Evolver used 26 completed model requests, 1,365,579 tokens, 581.18 seconds,
and $0.0301527968.

An earlier startup, `qce-t26-answer-rich-evolver-20260816-r1`, made no model
request. Its old proxy image exited because it did not understand the current
retry configuration. Switching to the already available compatible proxy
image resolved the observed failure; the failed directory remains preserved.

## Blind Worker outcomes

| Run | Outcome | Requests | Tokens | Cost |
| --- | --- | ---: | ---: | ---: |
| `qce-t26-answer-rich-candidate-20260817-r1` | invalid: model stream lost after 10 completed requests; no artifact | 10 | 265,153 | $0.0128399432 |
| `qce-t26-answer-rich-candidate-20260817-r2` | valid: 16/17, official reward 0 | 52 | 2,214,819 | $0.0438079376 |
| `qce-t26-answer-rich-candidate-20260817-r3` | invalid: 32,000 reasoning tokens, empty response, no tool call or artifact | 13 | 332,529 | $0.0230003648 |

The valid Worker invoked `audit_strategy_source` 14 times. It audited the real
deliverable, constructed bounded probes to understand check behavior, made at
least four post-creation revisions to `strategy.py`, and finished with all
three local audit checks reporting PASS. The resulting official property
vector was:

- Type A: 6/7; A2, A3, A4, A6, A7, and A9 passed; A10 failed;
- Type B: 10/10; B1 through B10 all passed;
- total: 16/17; official binary reward remained 0.

The A10 mismatch was substantive rather than a malformed-output failure:
candidate Sharpe was about 0.481 versus reference 0.649, and annual return was
about 0.0680 versus 0.0918. The static auditor therefore repaired the declared
formula/source properties it was designed to target but did not solve the
remaining end-to-end numerical reconciliation.

## Interpretation

This round supports three claims:

1. answer-rich post-run evidence can help the Evolver localize a concrete
   component state instead of merely proposing a nicer prompt;
2. the Evolver can autonomously implement, register, smoke, and activate a
   multi-file quant component;
3. the component's predicted B5/B9 effects occurred in one blind Worker, with
   the previously unstable A3 and B3 properties also passing.

It does not support three stronger claims:

1. stable T26 improvement, because neither replacement attempt yielded a valid
   scored Worker;
2. official QuantCodeEval success, because 16/17 still maps to reward 0;
3. transfer, because no second task with a measured matching failure signature
   was evaluated.

The component also has a material efficiency cost. The valid Worker used 52
model requests versus 32–36 in the earlier T26 samples, and spent substantial
time building audit probes. A narrower task-conditioned check selection or a
single compact audit report may retain the B5/B9 benefit with fewer turns.

## Cost and evidence

The Evolver plus all three Worker attempts used 101 completed model requests,
4,178,080 tokens, and $0.1098010424. All containers and run-scoped networks were
cleaned. Complete additive artifacts are mirrored under:

- `results/bc-mirror/qce-t26-answer-rich-evolver-20260816-r1`;
- `results/bc-mirror/qce-t26-answer-rich-evolver-20260816-r2`;
- `results/bc-mirror/qce-t26-answer-rich-candidate-20260817-r1`;
- `results/bc-mirror/qce-t26-answer-rich-candidate-20260817-r2`;
- `results/bc-mirror/qce-t26-answer-rich-candidate-20260817-r3`.

## Next experiment

Do not launch T19 or T27 as positive-transfer tests yet. First obtain one valid
same-configuration T26 repeat, but only after fixing or bounding the two
observed model-route failure modes and reducing the pre-artifact turn budget.
Promotion requires another scored Worker in which B5 and B9 remain PASS and
the total does not materially regress.

If that repeat succeeds, inspect candidate transfer tasks before running them.
Only a task whose blind H0 shows the same semantic state, pipeline phase, and
observable declared-formula-realization failure is eligible as positive
transfer. An unrelated T19 run may still serve as protection evidence, but it
cannot establish transfer for this HJ-objective auditor.
