# QFBench A6 R11 ME6 Engineering Negative

> Status: measured engineering-only negative result from one A6-E continuation.
> This is not a formal A6 result, a statistical comparison, or evidence of
> candidate benefit. The run ID is frozen and must not be resumed.

## Outcome first

ME6 produced two real artifact-bound probes and two durably validated,
non-ready `CONTINUE` checkpoints. The first checkpoint advanced exploration
from epoch 0 to epoch 1. The second, recorded at provider call 12, bound a new
epoch-1 probe and was eligible to advance only when execution reached the next
model boundary.

Execution stopped before that boundary. Call 13 executed two evidence tools;
call 14 returned a long text-only synthesis with no executable tool call while
the middleware was still in `explore`. ME6 enforced structured responses in
checkpoint repair and decision phases, but not in ordinary exploration. NexAU
therefore treated the no-call response as a natural finish. The middleware's
`after_agent` record correctly says `phase=invalid`, `complete=false`, and
`decision=null`, but the immutable pilot runner did not bind its process result
to that record: it wrote `status=complete` and returned zero.

The systemd `success` / exit-0 result is therefore a **false-success
control-flow outcome**, not mechanism success. There is no ACT, ABSTAIN,
downstream decision, candidate change, validation, admission, or candidate
evaluation. ME6 remains an engineering negative.

The canonical machine record is
[r11-me6-engineering-negative-20260811.json](../../output/qfbench-supervisor/a6-d5d954b0c404e6f4-r11-me6-continuation/r11-me6-engineering-negative-20260811.json),
8,553 bytes, SHA-256
`da08afdd395b747511a8a12551f72a649fe51c5c447eccb470d6fdb2c5f2aba0`.

## Measured execution and accounting

The sealed proxy ledger contains 14 rows. All 14 are completed HTTP-200
responses from the exact route `deepseek/deepseek-v4-flash-0731`; provider,
wire-request, and logical-request identities are each unique 14/14. Every
`retry_index` is zero and every `failure_class` is null.

| Metric | Measured value |
| --- | ---: |
| Provider calls / HTTP 200 | 14 / 14 |
| Input tokens | 325,632 |
| Output tokens | 27,206 |
| Total tokens | 352,838 |
| Provider cost | USD `0.0217533344` |
| First request start | `2026-08-11T02:55:45.796920Z` |
| Last response finish | `2026-08-11T03:00:11.173825Z` |
| Ledger interval | 265.376905 seconds |
| Runner wall time | 268.231 seconds |

The ledger is SHA-256
`9b10337fd3cb5a8915b95a434514a2a6034718e6a424c68d3263c4ae0502cf0`.
The run stayed inside the unchanged 48-provider-call and 1,800-second bounds;
it did not exhaust either bound.

## Structured progress

The run persisted 44 access records and two schema-1 probes:

| Probe | Bound result SHA-256 |
| --- | --- |
| `repair-epoch0-schema-vs-inventory` | `8834f8839e5c28c5da4ff65847475eac8608cb1de074a23f8d3892b11fe29eee` |
| `epoch1-artifact-vs-contract-coverage` | `d75068d293591d75a522dc53e0d60d976e3a493df0113b079aebf9c80b4a42c7` |

The corresponding checkpoint hashes were
`c942e8ee7e84afb3de3938fb96ad0b9155188f02b954fd0018e8cf7daf12187f`
and
`83624f3cad91caa9c7ab0674718a477345d3a51bfc639e3e82be7298f98ff29b`.
Both decisions were `CONTINUE`; both had `ready_for_decision=false`; neither
changed the candidate tree
`4ad9cd8d8450dabc845e7bbc6467127d2405f2db156da2d89f152f06887ac46c`.

The summary reports one tool error and the final response failed the JSON
prediction parser. Those observations did not cause the terminal stop:
validation-error count was zero, `current_exact_error` was null, and the exact
stop path is the explore-phase no-call behavior described below.

## Exact control-flow diagnosis

The terminal audit establishes the sequence:

1. Provider call 12 appended checkpoint 2 during epoch-1 exploration.
2. Provider call 13 remained in `explore` and executed `trace_slice` plus
   `read_workspace`.
3. `wrap_model_call` consumed provider call 14 and raised the epoch call count
   to six.
4. Call 14 returned HTTP 200 with 8,318 output tokens, but no executable call.
5. The ME6 middleware armed a pending response contract only when phase was
   `checkpoint_repair` or `decision`; explore `after_model` recorded usage and
   returned `no_changes`.
6. Pinned NexAU stops normally when a parsed response has no calls unless an
   after-model hook returns `force_continue=true`.
7. The next `before_model` boundary was never reached, so the bound checkpoint
   could not advance epoch 1 to epoch 2.
8. `after_agent` recorded `complete=false`; the immutable runner nevertheless
   emitted a successful outer report and process exit.

The causal artifacts are the terminal summary SHA
`cb59b33ec2734b837ccf615311dfd9b5d808fa61d5a196bd7cc0bfdb9d68d40f`,
raw trace SHA
`327cf8cbea5b126a574578fb1d600a808c329c14d4d8b1f3373f347a62ebe74a`,
and final text SHA
`4cb7a7fd4d0d9ef696ff64ed78af2c9941bcd82557a4e6612748b5707367c114`.

## Identity and containment

The immutable R10 release remained unchanged. Relevant execution identities
are:

- external ME6 runner:
  `656731f9627c7610f75fa4984b93f520ea9eaea19dbf054707513eb8e8afba10`;
- overlay tree:
  `9f728789650a92e6545e0d351413a713409063fa2c9906f267aab7315c3888c7`;
- agent overlay contract:
  `3a523f445266bb9c08d6af22d2d6827017893b92df343407dcba67513e189cdb`;
- immutable source tree:
  `d5d954b0c404e6f4521d91cd72a99c832aa237d33e219eaaa06a2350703a4335`;
- live plan / preflight:
  `c117e261051c2a036f0b6cbc3147ab4b1cfa6a2425b19bb323d53e033b9753fb` /
  `c562ec37f9b19d976eefc40b6d1ac08d9337eaccc53729ce60e768096b9cfec0`;
- model-boundary marker:
  `4f5fb68f0875a3044a80a665db30a16da87bd7b30bf6fe16e3364fd724316ecd`.

The result and all three lifecycle records say the Evolver container, proxy
container, and run-scoped proxy network were cleaned. The service is inactive
and dead with `NRestarts=0`. The final additive mirror completed at
`2026-08-11T03:01:19Z`.

## Engineering implication and ME7 proposal

Measured: ME6's real probe and checkpoint persistence worked for two epochs.
Measured: its final-epoch ACT/ABSTAIN-only repair surface was never reached,
because an earlier ordinary-exploration text response could still terminate
the agent. Therefore ME6 does not validate the end-to-end engineering
mechanism.

Proposed separately, not measured in ME6: ME7 gives ordinary exploration and
incomplete mutation exact post-model response contracts. Text/no-call,
unauthorized tool, sub-agent, and batch-agent responses are scrubbed and
force-continued without refunding the consumed call. Exploration is narrowed
away from legacy unlock and downstream decision/write tools; final-epoch
exploration additionally removes `checkpoint_continue`. A completed outer
pilot report is rejected before write unless the terminal audit's last event is
`after_agent complete=true` and its ACT/ABSTAIN decision exactly matches the
outer proposal. The 48-call and 1,800-second bounds remain unchanged, and no
decision is synthesized. ME7 is a fresh mechanism and must not be treated as an
ME6 result.
