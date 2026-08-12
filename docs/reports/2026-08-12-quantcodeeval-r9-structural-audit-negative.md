# QuantCodeEval r9 structural-audit negative

Date: 2026-08-12

Status: measured engineering negative; not a formal benchmark result

## Outcome

r9 tested whether the Evolver could use r8's partial score and refine the
working static strategy audit. The search mechanism worked: it loaded multiple
scored rounds, identified that r8 had repaired T24 Type-B while leaving one
Type-A failure, changed executable tool code and its bindings, passed component
smokes and admission, and reached the official panel. The proposed component
did not work.

The two-task panel returned `T16=0, T24=0`. T16 passed only 3 of 18 properties,
with the candidate strategy raising errors in most checks. T24 produced no
artifact because its fifth model call exhausted the 32,000-token reasoning
allowance and returned neither content nor a tool call. A fixed-candidate,
T24-only retry reproduced the same five-request empty-response failure. This
stable failure mode is attributable to the r9 worker interaction and model
budget, not to an official T24 property score.

## What the Evolver changed

The Evolver selected a structural-convention-gap hypothesis. Starting from the
r8 mechanism recorded in history, it expanded the static audit to inspect
declared output-column creation, window causality, and calendar indicators. It
changed four harness surfaces:

- `agent.yaml`
- `systemprompt.md`
- `tool_descriptions/audit_strategy_module.tool.yaml`
- `tools/strategy_audit.py`

The primary executable component imported successfully, the agent graph was
valid, and independent admission passed. The resulting audit and prompt were
substantially larger than r8. On T16 the worker spent effort satisfying static
surface checks but still submitted code with runtime behavior that failed most
properties. On T24 the interaction repeatedly consumed the entire reasoning
budget before writing the required file. This falsifies further accumulation
of broad static rules as the next mechanism direction.

## Cost

| Stage | Requests | Tokens | Cost |
| --- | ---: | ---: | ---: |
| r9 Evolver activation | 28 | 2,610,364 | $0.0519559208 |
| T16/T24 panel | 16 | 224,714 | $0.0183478512 |
| Fixed-candidate T24 retry | 5 | 73,805 | $0.0105009184 |
| Total | 49 | 2,908,883 | $0.0808046904 |

All three services exited successfully. No experiment container or network
remained after the runs.

## T24 benchmark-contract finding

Trusted diagnosis of r8's sole remaining T24 failure found an interface
mismatch. The public task contract presents `compute_portfolio_weight` as
returning a DataFrame and `compute_strategy_returns` as accepting one
DataFrame. The end-to-end differential checker follows the reference pipeline,
where the first function also returns a scale value and the second function
accepts that scale as a second argument. r8 followed the public interface and
therefore raised a positional-argument error only in this differential
property.

This should not be solved by revealing the checker call to the Evolver. Treat
it as a benchmark-adapter issue: correct the public interface and rebuild a
new baseline before making a T24 gain claim. Old and corrected-contract T24
scores must remain separate.

## Next direction

Do not launch another autonomous round that adds more static checks. Preserve
r8 as the useful partial mechanism and use the following two branches:

1. Build a compact, investigator-authored behavior-probe canary around the r8
   component. It should require an early saved draft and execute public
   function contracts on public data, without checker access. Label this as a
   manual mechanism-localization experiment rather than autonomous discovery.
2. Expand the engineering panel to self-contained public-data tasks T01, T12,
   T18, and T19. This tests whether r8's small audit generalizes across
   multi-asset momentum, factor momentum, conditional volatility targeting,
   and downside-volatility management without requiring WRDS access.

The complete generated evidence is mirrored under:

- `results/bc-mirror/qce-v2-activation-20260812-r9/`
- `results/bc-mirror/qce-v2-full-candidate-20260812-r5/`
- `results/bc-mirror/qce-v2-full-candidate-20260812-r5-t24-retry1/`
