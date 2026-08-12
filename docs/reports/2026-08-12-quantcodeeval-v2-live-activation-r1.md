# QuantCodeEval v2 live activation r1

> Date: 2026-08-12
>
> Run: `qce-v2-activation-20260812-r1`
>
> Result: REJECTED at component-attribution gate; no candidate benchmark run

## Outcome

The first real v2 Evolver activation demonstrated a non-prompt executable
mutation and then failed closed at the exact file-role attribution gate. This
is a useful negative mechanism result, not a QuantCodeEval score result.

The run reused H0 evaluation
`d42b12416c46e46311cc5076409f7fdf83a55c4fcb25c5990aa7bd4f42878f06`
and worker digest
`4ad9cd8d8450dabc845e7bbc6467127d2405f2db156da2d89f152f06887ac46c`.
It did not resample H0 and never created worker or verifier containers. T16 and
T24 therefore remain the measured H0 vector `[1, 0]`; no candidate reward is
claimed.

## What the Evolver searched and changed

The Evolver read the answer-free T16/T24 summaries, public instructions and
paper text, and strategy AST facts. It compared a percent-versus-decimal scale
hypothesis with a temporal-lag endpoint hypothesis. Its selected intervention
was a deterministic pre-submission strategy validator, not another prompt-only
mutation.

The exact candidate digest is
`5d73211371ffdaf116f845846d980d14e4370d412ced3fba910bdb27607488f3`.
Relative to H0 it changed four files and four actual roles:

- added `tools/strategy_validate.py` (379 lines);
- added `tool_descriptions/validate_strategy_module.tool.yaml`;
- registered the tool in `agent.yaml`;
- activated the validation workflow in `systemprompt.md`.

The mutation added 435 and removed 1 line. It was not prompt-only and touched
executable code. The Evolver created clean, defective, and 100-times-scale
self-test fixtures, exercised them, removed those temporary files, then
recorded three passed digest-bound component smokes: tool import, full agent
graph load, and tool call. Independent full-harness admission separately
passed `file_manifest`, `protected_config`, `python_compile`,
`declared_imports`, `subprocess_timeouts`, `local_bindings`, `local_skills`,
`local_middlewares`, and `component_reachability`.

## Why it was rejected

The decision declared roles
`agent_config, systemprompt, tool_descriptions, tools, validator`, while the
exact mutation roles were
`agent_config, systemprompt, tool_descriptions, tools`. The validator behavior
lived in `tools/strategy_validate.py`; no file below `validator/` changed.
Thus `declared_roles_match_actual=false`. This exposed an ambiguity in the v2
contract: the Evolver used `validator` as a conceptual capability name, while
the coordinator correctly interpreted component roles as exact file loci.

The code and its independent admission were not the direct rejection cause.
The candidate was rejected before activation selection and before T16/T24
candidate evaluation. It must not be relabeled as PASS merely by dropping the
extra role after the fact.

## Model and runtime evidence

The run used exact model `deepseek/deepseek-v4-flash-0731`, provider
`deepseek`, no fallback, Evolver image
`sha256:adb2a68688488fe94e0fffbe1ffecf8c5416a4c3d2325cee6379e854521b29d2`,
and proxy image
`sha256:950280b19b6215c9a48ae81d5d9fdc6b69fa2192706ff4920efbb0981e33beae`.
All 34 proxy requests completed successfully. Exact audited usage was
1,524,350 input tokens, 87,253 output tokens, 1,611,603 total tokens, and
`$0.0377605312` provider cost.

All managed containers and the private network were cleaned by exact ID.
Post-run inspection found zero residual `qea-evolver`, `qea-proxy`, and
`qea-*` network resources.

Selected artifact hashes:

- `LIVE-PREFLIGHT.json`:
  `6a321e61f4d9bd510bb51a6db9f371e4e542f9196c94d5643781f4e2d40dec2f`;
- `summary.json`:
  `c567956fc79b479a3a377f8ecea6a9dff107b09c36584531ee1873c2d1422d24`;
- `result.json`:
  `214f66a50a5579a74818fc556a988f2d29bedd74230d5db0a7683029951a3acf`;
- `final.txt`:
  `6684388a38b4a233b714dc87eb2fd06a8f882dc735095a5837996dd3e5c12665`;
- `proxy-audit.jsonl`:
  `c7a00cdd9c29b42bf5e181ff89bc5bdb54d002e2b84a6c9b8f2ba3b950ebfd85`.

The full additive mirror is retained at
`results/bc-mirror/qce-v2-activation-20260812-r1/`.

## Superseding engineering action

The v2 contract now says explicitly that `components` and
`primary_components` are exact changed file roles, not conceptual capability
labels. Rejected attribution and stale-smoke attempts are retained as immutable
search history instead of escaping as an infrastructure exception. A new live
run may import r1 as exact parent/candidate/diff/decision/test/rollback
experience, forcing the next Evolver to read the failed attempt before ACT.

The full-candidate gate now permits failed draft smokes in chronological
history but requires every final primary component's latest passed smoke to be
bound to the submitted candidate digest. This preserves room for
edit-test-repair within an Evolver round without weakening final admission.

## Follow-up mechanism diagnostics r2 and r3

Run r2 imported r1 into trusted history and passed zero-model preflight, then
failed before any model request because the Evolver firewall reserves every
path named `tests` for possible private evaluator material. The history store's
answer-free component-test records had used that directory name. Their Evolver
projection is now named `component_checks/`; the trusted store and hashes are
unchanged. r2 is a zero-request infrastructure negative.

Run r3 then demonstrated the requested inter-round learning behavior with a
real model. Its access log proves the Evolver read r1's exact 10,290-byte entry,
9,327 bytes of the exact diff, the full 15,225-byte validator source, and the
prior candidate's agent configuration and system prompt. It also ran a
registered competing-expectation probe and correctly identified r1 as a
declarative role mismatch rather than an evaluated mechanism failure.

r3 regenerated an improved validator-tool candidate, corrected the exact roles
to `tools, tool_descriptions, agent_config, systemprompt`, and passed a
digest-bound tool import smoke. It was still rejected before benchmark scoring
because the `decide_candidate` JSON schema required hypothesis field
`failure_prediction`, while the Python implementation required `prediction`.
After repeated valid-looking calls were rejected on alternating sides of that
mismatch, the Evolver fell back to the legacy unlock protocol; the coordinator
correctly refused that schema-1 decision for quant v2.

r3 made 29 successful model requests, used 1,428,999 input and 77,131 output
tokens (1,506,130 total), and cost `$0.036206044`. Its proxy audit SHA-256 is
`f581fefa8f34718dbffb1302500a8b80c788460eca452556869ba1f96e46b5dd`.
No worker or verifier ran and all managed resources were cleaned.

The schema and implementation now both use `prediction`. Quant v2 explicitly
forbids the legacy unlock path, so a future candidate must persist the exact
schema-4 `quant_property_v2` decision or remain write-locked. r2 and r3 are
retained additively under `results/bc-mirror/`; neither is a benchmark result.

## Live activation r4: PASS

After those two repairs, r4 completed the entire activation mechanism. It read
r1's immutable history, persisted a schema-4 `quant_property_v2` ACT, declared
the exact roles `agent_config, systemprompt, tool_descriptions, tools`, revised
its draft and local fixtures several times, deleted all temporary fixtures, and
reran final tool-import and complete-agent-graph smokes on candidate digest
`9a72fc74626774a24bda67d55bd25c39f06d35e1f3a20416dedd61ef5c092089`.
Independent admission passed all nine checks. Activation status is `PASS` and
the immutable history entry is
`287323ea195f13f5983f351bf65f099c123fd8814240465b9f6106ff01df64b6`.

r4 still makes no benchmark claim: candidate T16/T24 was not run, H0 was not
resampled, and the candidate is archived pending the full panel. The exact
proxy audit recorded 48 completed unique requests, 2,980,699 input tokens,
56,863 output tokens, 3,037,562 total tokens, and `$0.0345887416` cost. The
result identity is
`c9ff158996c34faf74547b409d1500cfb3d1825d4a4b8df07a297cafe71d1fac`.
All managed resources were cleaned.

The activation search-state originally counted one NexAU proposal as one model
request even though that proposal contained 48 proxy-audited provider turns.
The live evaluator now reconciles the outer state against the finalized proxy
audit so request/cost stopping limits use provider-turn accounting. The exact
r4 artifact is retained under
`results/bc-mirror/qce-v2-activation-20260812-r4/`.

## First full-candidate panel: worker-contract rejection

The archived r4 candidate was next launched as
`qce-v2-full-candidate-20260812-r1` against T16 and T24. Full-candidate
preflight passed: the candidate source, exact declared roles, final-digest
component tests, independent admission, runtime identity, task panel, and H0
reuse all matched. The candidate digest remained
`9a72fc74626774a24bda67d55bd25c39f06d35e1f3a20416dedd61ef5c092089`.

The run produced no valid QuantCodeEval candidate score. Both tasks stopped at
the worker artifact contract before a verifier ran:

- T16 completed seven provider requests and then reported
  `output file limit exceeded: 4 > 3`. Partial extraction retained
  `trade_log.json` plus Python 3.11 and 3.12 bytecode cache files. The fourth
  output was not extracted after the fail-closed file-count rejection, so its
  membership is not inferred.
- T24 completed eight provider requests but delivered no `strategy.py`; its
  artifact contract recorded an empty output membership.

The two tasks used 168,293 input and 58,392 output tokens, 226,685 total, with
exact audited cost `$0.0218750168`. All 15 proxy requests completed. All six
worker/proxy/network lifecycle records report `cleaned_up=true`. Because no
verifier completed, these outcomes are component-level delivery failures, not
official rewards of zero and not evidence for or against the validator's
quantitative hypothesis.

The original coordinator exited on the T16 archive exception before writing a
top-level result. The immutable mirror retains that absence as historical
behavior. A new recovery path read only preflight, worker artifact-contract,
proxy-audit, and lifecycle records and wrote an explicitly marked
`RecoveredInterruptedPanel` result. It did not inspect checker output. The
preflight SHA-256 is
`59fe46540461178aad8b0f83f3dbaeabe59f6b33c68611879e6a5184fac3a5e3`;
the recovered fail-closed result SHA-256 is
`72e63a654623ed8cee3d239d4af13139bea2f773056c8702e56ac280075b1c3b`.
The additive evidence is under
`results/bc-mirror/qce-v2-full-candidate-20260812-r1/`.

Future full-candidate runs persist the same answer-free failure result during
the failing invocation and reuse it on resume, preventing accidental paid
resampling. The next activation may import this exact r4 candidate, diff,
decision, component tests, passed activation, task-local artifact failures,
cost, and cleanup state as immutable search history. It must treat r4 as
rejected and H0 as the incumbent; H0 is not resampled.
