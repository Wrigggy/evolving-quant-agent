# QFBench A6 R11 ME7 Engineering Terminal ABSTAIN

> Status: measured engineering-only terminal ABSTAIN pass from one A6-E
> continuation. This is not an ACT result, a candidate-benefit result, a formal
> A6 result, or a statistical comparison. The ME7 run ID and mechanism bytes are
> frozen and must not be resumed or rewritten.

## Outcome first

ME7 completed the bounded multi-epoch control path that its predecessors had
failed to complete. It produced three real artifact-bound probes, two non-ready
`CONTINUE` checkpoints, a final ready `ABSTAIN` checkpoint, a checkpoint-bound
`ABSTAIN` decision, and a terminal `after_agent complete=true` record whose
decision exactly matches the outer proposal. Candidate writes remained locked;
the candidate tree was byte-identical; validation and admission were not
applicable.

This is a positive end-to-end **terminal ABSTAIN mechanism pass**. It proves
that ME7 can preserve bounded exploration, reach the final branch, record an
honest no-intervention decision, and fail closed against candidate mutation.
It does not prove that the evidence can support ACT, that the ACT/mutation path
works live, that any candidate improves QFBench, or that the mechanism has a
formal/statistical advantage.

The canonical machine record is
[r11-me7-engineering-terminal-abstain-20260811.json](../../output/qfbench-supervisor/a6-d5d954b0c404e6f4-r11-me7-continuation/r11-me7-engineering-terminal-abstain-20260811.json),
9,196 bytes, SHA-256
`1bd5fde052d05281a3109d7b6b287a108c1aebbac88b951935deeb783f0d4839`.

## Measured execution and accounting

The sealed proxy ledger has 23 wire-attempt rows representing 21 logical
requests. Twenty-one rows completed HTTP 200 on the exact route
`deepseek/deepseek-v4-flash-0731`. Two retry-index-0 attempts returned HTTP 429
as `not_accepted`, with null provider IDs, token usage, and cost. Each failed
logical prompt was issued again as a distinct wire request and completed once
at retry index 1. This is the intended request-level retry behavior; it did not
resume an in-flight model session or count either rejected attempt as a model
completion.

| Metric | Measured value |
| --- | ---: |
| Wire attempts / logical requests | 23 / 21 |
| Completed HTTP 200 / nonaccepted HTTP 429 | 21 / 2 |
| Input tokens | 439,112 |
| Output tokens | 45,030 |
| Total tokens | 484,142 |
| Provider cost | USD `0.0338504544` |
| First request start | `2026-08-11T03:32:25.012307Z` |
| Last response finish | `2026-08-11T03:38:51.078270Z` |
| Ledger interval | 386.065963 seconds |
| Runner wall time | 389.136 seconds |

The ledger SHA-256 is
`6dbe57d01fce92d73c3e87d434472850d41337dcd804d8404ac5cce4f6b1419e`.
The run stayed inside the unchanged 48-provider-call and 1,800-second global
bounds.

## Structured progress and terminal binding

ME7 persisted 68 access records and three generic schema-1 probes:

| Probe | Bound result SHA-256 |
| --- | --- |
| `trace-phase-profile-zcb-vs-earnings` | `1f02ba6f453d70862980f45c4f062fa7b65f5e321b8a76365c7da7bd89048e4b` |
| `second-pair-13f-vs-localvol` | `fe2e3836e7fe767a0c65f53d671b7d3715b58433e3206d6cfb1cd3a92775a917` |
| `validation-asymmetry-target-process-summaries` | `b1caab92b7e9e0f06f468a7d9d098c75e2031b342cac67be2e8ef9863ff62508` |

The checkpoint chain was:

1. `380c52802631f795dc57b73c88c40836f8ea056183f0506e4daf369caa0275f9`
   — `CONTINUE`, non-ready;
2. `aedddc1602d8f60b2dbe134b4b90e8152802f4ee85dc6ebc570377465eb21336`
   — `CONTINUE`, non-ready;
3. `4f1374ed4e18ce90cb20d56d61c04e662e589ebf44a4f10668034f14d27db07b`
   — `ABSTAIN`, ready for decision.

The final decision state is `ABSTAIN`, `unlocked=false`, with hypothesis SHA
`98d52874e83876d7dc0c5349831f737b0c1c537256528ab3bc99252003b66a33`
and state-file SHA
`c7a393626c93b0cbb6e498a65f217b5eaf493a827f457cd4638dc2b4d66776e4`.
Audit event 146 is the last event and is exactly `after_agent` with
`complete=true`, `decision=ABSTAIN`, `candidate_changed=false`, and
`candidate_validation_seen=false`. The outer decision has SHA
`911eb78ffd79070f4a2bc7e1d6c18a6e5f02b92324d005f6d6795dd1d9e58f68`
and matches that terminal state.

The candidate remained
`4ad9cd8d8450dabc845e7bbc6467127d2405f2db156da2d89f152f06887ac46c`.
There is no write, diff, validation, admission, or candidate evaluation. The
summary reports one tool error, but zero checkpoint validation errors and null
`current_exact_error`; it did not prevent the valid terminal ABSTAIN.

## Why the model reported contracts and artifacts as absent

The ABSTAIN record says the `contracts/**` glob was empty and no usable exact
path named `contracts/` or `tasks/*/artifacts/`. That statement accurately
describes the model's compacted navigation state, but it does **not** describe
the authorized evidence source.

Read-only inspection of the mirrored evidence proves that the run contained
all 178 authorized files, including:

- `contracts/index.json` and all 16 instruction/clauses pairs: 33 contract
  files in total;
- all 16 `tasks/<id>/artifact_manifest.json` files and 55 manifested artifact
  files;
- all task `public_evaluation.json`, `worker_trace.jsonl`, process summaries,
  and worker finals; and
- `debugger/task_index.json`, which already binds task roles and exact paths.

The exact navigation failure has two parts. First, `list_workspace` applies
`pathlib.Path.glob()` to its literal pattern and then retains regular files.
For `contracts/**`, Python yields the `contracts` directory itself rather than
recursive member files; the subsequent file-only filter therefore returns an
empty list. The recursive file pattern would be `contracts/**/*`, or callers
could read the exact paths already listed in `contracts/index.json`.

Second, the initial `map_evidence` did recursively enumerate the evidence tree,
but its durable access row names only the broad navigation pattern `**/*`.
ME7 compaction intentionally retained exact accessed evidence paths for
readiness and dropped mapped-but-unread member pointers. Consequently, the
contract/artifact map was no longer visible when the model revisited the
question in the final epoch. It inferred a source gap from a failed glob plus
its exact-access list.

Therefore the measured diagnosis is **navigation/compaction loss**, not an
evidence staging or authorization failure. The ABSTAIN remains an honest and
valid decision for the exact evidence actually read and probed, but the prose
claim that the source corpus itself was absent is false.

## Identity and containment

ME7 did not modify the immutable R10 release. Relevant execution identities
are:

- external runner:
  `438f6bfe3de437d1551b3d5c98d407b2ba7aeab83ef852141eb021f50f86454b`;
- overlay tree:
  `4e7a5096042b7ff1e65565aff4b119b3eed34d96d884e6aaa59eacd56b3f4feb`;
- agent overlay contract:
  `3a523f445266bb9c08d6af22d2d6827017893b92df343407dcba67513e189cdb`;
- immutable source tree:
  `d5d954b0c404e6f4521d91cd72a99c832aa237d33e219eaaa06a2350703a4335`;
- live plan / preflight:
  `345c1780ad48a7301a5c94255538f3763bbf4450b0001d662dc2e8f128ba9f0a` /
  `452b056146b3e05f98891a702c6ce79b5aef900f55e220c12c39e09880bcf4ea`;
- terminal summary / raw trace:
  `e67f3cb1310bc8e94438e50bda80b46420c4e5f740761a14c09c940a8d9c1db3` /
  `e0d32df4337217113fbc7b7ebfa741cdc393767987f6970b93aedfa5243f5e0e`.

The result and all three lifecycle records say the Evolver container, proxy
container, and run-scoped proxy network were cleaned. The primary service is
inactive/dead with `NRestarts=0`. The last additive mirror completed at
`2026-08-11T03:42:39Z`. At record time, local monitor/mirror labels had not been
independently verified unloaded, so this report makes no unloaded claim.

## ME8 proposal: preserve evidence, repair navigation

Proposed separately, not measured in ME7: ME8 should preserve the exact ME7
mechanism and the exact 178-file authorized evidence tree. Before every model
boundary and compaction, middleware should recompute a bounded
**VERIFIED NAVIGATION** capsule from the immutable `debugger/task_index.json`,
`contracts/index.json`, task artifact manifests, public evaluations, and trace
pointers. Each entry contains only exact relative path, existence, byte length,
SHA-256, task role, bounded scalar/count outcome summary, contract pointers,
and manifested artifact pointers, with explicit truncation metadata.

The capsule must say `navigation_only=true` and `readiness_effect=false`.
Producing or displaying it must never append an access-log row, make a member
path usable, satisfy a checkpoint, or count as evidence read. The model must
still call an exact access tool before citing a path and must execute the
same-task clause + manifested artifact + trace schema-2 discriminator before
ACT. ACT also requires accessed public evaluation plus task evidence for at
least two declared target members. If `matched_success_tasks` is nonempty,
every claimed match must be an accessed role=`protection`, reward-1 task with
public evaluation and task evidence; sentinels are forbidden. If no defensible
match exists, `insufficient_contrast` remains legal.

This is an evidence-navigation repair, not a fabricated success contrast and
not a relaxation of the ACT gate. No gold, official tests, evaluator verdicts,
private criteria, reference values, or hidden outcomes may enter the capsule.
ME8 must receive independent source, package, and zero-model live gates before
standing authorization permits any launch.
