# QFBench Scheduler Epoch Transition

Date: 2026-08-03

Status: locally verified; remote boundary recovery and paid canary pending

Run: `qfbench-rootless-base-85x5-official-deepseek-v4-flash-noreplay-recovery2-20260803`

## Decision

Preserve repetition 1 under its original scheduler and resume repetitions 2–5
under one explicitly different scheduler epoch. This is an operational
throughput change, not a rewrite of the sampling contract:

| Epoch | Repetitions | Worker / verifier concurrency | Capacity |
|---|---:|---:|---|
| 1 | 1 | 4 / 3 | 48 CPU, 98,304 MiB, 8,192 PIDs, 32,768 MiB tmpfs, 24 sandboxes |
| 2 | 2–5 | 12 / 3 | 48 CPU, 98,304 MiB, 8,192 PIDs, 40,960 MiB tmpfs, 24 sandboxes |

Both epochs retain maximum load 56 and minimum Linux `MemAvailable` 16,384
MiB. Each checkpoint epoch binds worker/verifier concurrency plus both the
scheduler and complete runtime identity digests. The benchmark commit, all 85
task/image identities, seed worker, model `deepseek/deepseek-v4-flash`, provider
`deepseek`, fallback prohibition, temperature, official rewards, and evaluator
firewall remain unchanged.

## Boundary and Recovery Contract

The schema-v1 checkpoint may migrate to schema v2 only after repetition 1 has
85 terminal official scores, `next_repetition=2`, `phase=primary`, and a null
pending primary panel. The guard freezes and revalidates the exact coordinator
PID, PGID, UID, start ticks, argv digest, run ID, and source commit. Migration is
blocked by any repetition-2 attempt/request/lifecycle evidence, active run-owned
container or network, changed repetition-1 evidence, or incomplete cleanup.

The epoch-2 launcher owns a dedicated process group. Signals are forwarded to
that group, descendants are reaped, and escalation is bounded. Watch decisions
are based on validated score, proxy-audit, and lifecycle evidence rather than a
quarantine filename. The only supported missing-ledger case is an official
reward-zero timeout with the exact schema-1
`audit_download_or_validation_failed` marker and complete worker/proxy/network
cleanup. It remains a cost lower bound. Every other ambiguity is a hard stop.

## Paid Canary Gate

Before formal epoch-2 resume, run one separately identified
`paid-baseline-batch` canary over the preregistered twelve standard primary
tasks. The path snapshots `qea/worker_gdpval_weak`, performs one evaluator call
with checkpoint `epoch-02-concurrency-canary`, and does not import or construct
the evolver or use feedback/rubric inputs.

Acceptance requires measured worker overlap 12, provider/model route parity,
only completed HTTP-200 requests, no within-attempt replay, complete canonical
cost accounting, offline verifier lifecycles, worker-proxy-only networking,
exact cleanup of every sandbox/network, and zero residual run-owned resources.
Failure blocks epoch 2; it does not silently reduce concurrency.

## Reporting and Local Evidence

Final reporting must separate repetition 1 from repetitions 2–5 for score,
request count, provider latency, timeout count, cost, and wall time, then provide
the requested combined five-repeat aggregate with
`scheduler_epoch_batch_effect_warning=true`. Official rewards are never
rewritten and no LLM judge is introduced.

The implementation consists of commits `fd68f6c`, `92c3e30`, `ff72fa3`,
`1c6d0bc`, `293907c`, and `f99badb`. Local verification completed with:

- focused scheduler/boundary/supervisor/watch/canary suite: 277 passed;
- proxy/replay/reaper/runtime/isolation safety suite: 154 passed;
- complete feature-worktree suite: 942 passed, 1 optional-dependency skip, and
  1 explicit deselection because the untracked historical oracle anchor is not
  materialized in Git worktrees;
- the deselected historical anchor test: 1 passed independently in the main
  workspace without copying or executing its solution artifact.

These are implementation results only. They do not claim that the live
boundary, 12-way canary, or repetitions 2–5 have completed. The exact deployment
commit, remote manifest hashes, measured overlap, run progress, costs, and final
epoch summaries must be appended as live evidence after execution.
