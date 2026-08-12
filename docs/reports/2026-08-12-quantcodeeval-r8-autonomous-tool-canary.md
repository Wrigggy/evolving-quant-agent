# QuantCodeEval r8 autonomous tool canary

Date: 2026-08-12

Status: measured engineering canary; not a formal benchmark-gain result

## Outcome

The autonomous Evolver completed one search round, chose a unit-scale
hypothesis for T24, and produced an admitted full-harness candidate. The
candidate changed four surfaces rather than only the prompt:

- `agent.yaml`
- `systemprompt.md`
- `tool_descriptions/audit_strategy_module.tool.yaml`
- `tools/strategy_audit.py`

The executable audit tool was imported, called successfully in a component
smoke, and later invoked by the real T24 worker before submission. The two-task
official panel completed with reward vector `T16=1, T24=0` and task mean `0.5`,
the same binary vector as H0.

This is nevertheless a localized partial improvement. H0 failed one Type-A
and one Type-B T24 property. The r8 candidate passed every Type-B property and
retained one Type-A failure. Because QuantCodeEval uses an all-properties gate,
T24 reward remained zero. The result supports the usefulness and activation of
the new component, but does not establish a benchmark gain.

## Search and history behavior

Run: `qce-v2-activation-20260812-r8`

Model/provider: `deepseek/deepseek-v4-flash-0731` via DeepSeek, no fallback

Search budget used: one autonomous round

The Evolver received answer-free history from the earlier r1, r4, r5, and r6
attempts. Its recorded reads included prior entries, candidate diffs, component
files, and scored task summaries. It therefore had access to both ineffective
and partially successful prior edits instead of restarting from an empty
context.

It selected the `h1_unit_scale` hypothesis and treated the new executable audit
tool as the primary component. The candidate passed its tool import, tool call,
agent graph, and independent full-harness admission checks. Activation used 28
completed model requests, 2,288,841 tokens, and $0.0524817216.

## Full candidate evaluation

Run: `qce-v2-full-candidate-20260812-r4`

Tasks: T16 and T24

H0 resampled: no

| Task | H0 reward | Candidate reward | Candidate properties |
| --- | ---: | ---: | --- |
| T16 | 1 | 1 | 18 passed, 0 failed |
| T24 | 0 | 0 | 16 passed, 1 failed |

The full candidate evaluation used 28 completed model requests, 586,718 tokens,
and $0.0433812288. Search plus evaluation therefore used 56 requests,
2,875,559 tokens, and $0.0958629504. Both systemd services exited successfully,
and no experiment containers or networks remained afterward.

## Interpretation and next experiment

The main mechanism question moved forward: an Evolver can use cumulative
history, choose an executable component, modify multiple harness surfaces, run
component tests, pass admission, and cause the real worker to call the new
component. The remaining bottleneck is now semantic coverage, not component
activation or prompt-only exposure.

The next search round should import this scored r8 result and make the residual
T24 Type-A failure visible as answer-free feedback. The mutation surface should
remain open. A productive direction is to improve or replace the task-aware
audit/probe so it tests temporal construction and interface semantics that the
generic unit-scale audit missed. The Evolver should choose that change from the
new evidence; it should not be instructed with a hidden answer. Keep T16 in the
small panel as the protected passing task, and do not expand to the full
QuantCodeEval suite until T24 crosses the all-properties gate.

## Evidence

The complete remote runs were copied additively to:

- `results/bc-mirror/qce-v2-activation-20260812-r8/`
- `results/bc-mirror/qce-v2-full-candidate-20260812-r4/`

The raw mirrors are generated evidence and remain outside normal Git tracking.
This report records the reconstructable setup, mutation surfaces, task scores,
request/token/cost accounting, and cleanup outcome in Git.
