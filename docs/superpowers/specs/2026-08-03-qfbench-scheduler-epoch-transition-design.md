# QFBench Repetition-Boundary Scheduler Epoch Transition Design

> Date: 2026-08-03<br>
> Status: approved for implementation<br>
> Run: `qfbench-rootless-base-85x5-official-deepseek-v4-flash-noreplay-recovery2-20260803`<br>
> Scope: preserve repetition 1 at concurrency 4; run repetitions 2–5 at concurrency 12

## Context and Evidence

The formal DeepSeek V4 Flash baseline contains five independent repetitions of
85 QFBench tasks. Repetition 1 was frozen with worker concurrency 4 and verifier
concurrency 3. Its 77-task primary panel required about 2.5 wall-clock hours.
Completed worker lifecycles accumulated 9.05 worker-hours, used an average of
3.64 of four worker slots, and spent 74% of worker time waiting for 1,063 model
requests. Median worker duration was 235 seconds, p90 was 894 seconds, and the
longest worker took 1,812 seconds. Verifiers averaged 3.88 seconds and are not
the bottleneck.

The 64-core, 125-GiB host was 97–100% idle during four-way execution, with
about 99 GiB `MemAvailable`. The task catalog contains 77 standard workers at
2 CPU/4 GiB and eight heavy workers at 4 CPU/8 GiB. Each live worker also owns
one 2 CPU/4 GiB model proxy. A worker-concurrency cap of 12 therefore offers a
large safe speedup while the weighted lease pool continues to reduce actual
admission for heavy tasks.

During repetition 1, the live watch incorrectly treated an approved official
timeout marker as ambiguous upstream acceptance. It signalled the outer bash
launcher, while the Python coordinator continued as orphan PID `3714787`.
The affected task, `yield-curve-bond-immunization`, has reward 0, a `timeout`
diagnostic tag, the exact `audit_download_or_validation_failed` marker, and
exact-ID worker/proxy cleanup. No sample was replayed, but the old watch and
sentinel generation can no longer supervise the orphan reliably.

## Goals

- Freeze repetition 1 without changing or importing any sample, score, ledger,
  timeout, worker artifact, or verifier artifact.
- Record one explicit scheduler epoch boundary between repetitions 1 and 2.
- Run repetitions 2–5 with worker concurrency 12 and verifier concurrency 3.
- Keep the benchmark, seed worker, model, provider, fallbacks, temperature,
  task panels, images, worker behavior, verifier contract, and reward unchanged.
- Preserve attempt-scoped no-replay, evaluator isolation, exact-ID cleanup,
  authoritative cost accounting, and fail-closed recovery.
- Rebind the remote watch/sentinel and Mac repair controller to the new epoch.

## Non-Goals

- Do not claim that scheduler concurrency is scientifically invisible. Report
  the two epochs and test for an epoch-associated latency or score shift.
- Do not rewrite repetition 1 into the new scheduler identity.
- Do not expose official tests/reference data to workers, the boundary guard,
  the watch, the repair controller, or Codex.
- Do not upload or execute official solutions.
- Do not merge the feature branch or clean unrelated resources or dirty files.

## Scheduler Epoch Model

The checkpoint advances from schema v1 to schema v2 only at a proven clean
repetition boundary. Schema v2 separates the immutable sampling identity from
the per-repetition scheduler identity:

```json
{
  "schema_version": 2,
  "sampling_identity": "<unchanged model/task/seed/image contract>",
  "scheduler_epochs": [
    {
      "first_repetition": 1,
      "last_repetition": 1,
      "worker_concurrency": 4,
      "verifier_concurrency": 3,
      "scheduler_identity_digest": "<epoch-1 digest>"
    },
    {
      "first_repetition": 2,
      "last_repetition": 5,
      "worker_concurrency": 12,
      "verifier_concurrency": 3,
      "scheduler_identity_digest": "<epoch-2 digest>"
    }
  ]
}
```

Migration is publish-once and is permitted only when all of these conditions
hold simultaneously:

- repetition 1 is present in `completed`;
- `next_repetition == 2`, `phase == "primary"`, and `pending_primary == null`;
- all 85 repetition-1 attempts have terminal official scores;
- no repetition-2 attempt directory, worker execution, proxy ledger, lifecycle,
  provider request registry entry, container, or network exists;
- the repetition-1 score, attempt, proxy, lifecycle, and checkpoint hashes match
  a frozen pre-migration manifest;
- the seed worker, benchmark commit, task manifest, image set, route, model,
  provider, and fallback policy still match epoch 1.

If any condition fails, migration publishes no checkpoint and enters hard stop.
The migration never deletes or renames evidence.

## Repetition-Boundary Guard

The currently running coordinator predates the epoch feature and has no dynamic
stop control. A bc-local, owner-only boundary guard observes `resume.json` using
Linux file events rather than slow remote polling. When the schema-v1 checkpoint
first shows completed repetition 1 and `next_repetition == 2`, it sends
`SIGSTOP` to the exact validated Python coordinator PID. It then verifies the
complete migration preconditions above.

If zero repetition-2 evidence exists, the guard terminates that exact stopped
coordinator, proves zero run-owned containers/networks, and records the boundary
manifest. If any repetition-2 attempt or accepted request exists, the guard
does not delete or resample it; it records a hard stop for manual disposition.
The guard refuses PIDs whose command line, run ID, source commit, or start time
does not match its owner-only configuration.

## Epoch-2 Resource Contract

Epoch 2 uses:

| Setting | Value |
|---|---:|
| Worker concurrency cap | 12 |
| Verifier concurrency cap | 3 |
| Weighted CPU capacity | 48 |
| Weighted memory capacity | 98,304 MiB |
| Weighted PID capacity | 8,192 |
| Weighted sandbox capacity | 24 |
| Weighted tmpfs capacity | 40,960 MiB |
| Minimum `MemAvailable` | 16,384 MiB |
| Maximum one-minute load | 56 |

A standard worker plus proxy requests 4 CPU, 8,192 MiB, two sandboxes, and
2,960 MiB tmpfs, allowing 12 concurrent standard attempts. A heavy worker plus
proxy requests 6 CPU and 12,288 MiB, so the weighted pool automatically admits
at most eight all-heavy attempts. The eight diagnostic tasks can therefore run
as one heavy batch. Host-health checks remain admission gates and may reduce
concurrency further without changing attempt identity.

Verifier concurrency remains 3 because measured verifier duration is negligible
and a larger verifier pool would only compete with workers during completion
bursts.

## Concurrency Canary

Before formal resume, run one separately identified 12-task paid canary with
the epoch-2 config. It must prove:

- 12 standard worker/proxy pairs are admitted concurrently when host health
  permits;
- the route remains `deepseek/deepseek-v4-flash`, provider `deepseek`, with
  fallbacks disabled;
- no HTTP 429, provider fallback, ambiguous accepted request, within-attempt
  replay, or partially missing accounting occurs;
- official tests/reference data enter only independent networkless verifier
  sandboxes;
- every worker, proxy, verifier, network, and lifecycle uses exact-ID cleanup;
- `MemAvailable`, load, disk, inode, PID, and tmpfs headroom remain within policy;
- zero canary resources remain afterward.

Failure of the 12-way canary blocks epoch 2. It does not silently fall back to
another concurrency. A lower concurrency requires a new explicit scheduler
epoch decision.

## Timeout and Ambiguity Classification

The new watch accepts a missing canonical proxy ledger only when all of these
are true:

- the completed official score has reward 0 and a `timeout` diagnostic tag;
- the marker exactly equals schema 1, state `quarantined`, reason
  `audit_download_or_validation_failed`;
- worker/proxy lifecycle evidence identifies the official timeout;
- exact-ID cleanup is complete;
- no canonical proxy audit exists for the same attempt.

Such an attempt remains an explicit unreconciled cost lower bound. All other
quarantine markers, `downstream_delivery`, `post_accept_transport`, conflicting
ledgers, provider ambiguity, or incomplete cleanup remain hard stops.

## Orphan-Safe Supervisor and Monitoring

The epoch-2 launcher must not repeat the bash-orphan failure. Its external
supervisor records wrapper and child identities, forwards termination to the
exact child process group, waits for the child, and atomically publishes the
exit code and completion marker. Tests must demonstrate that watch termination
cannot leave `run.py`, workers, proxies, verifiers, containers, or networks
running without owned lifecycle evidence.

Create a new watch state directory, sentinel configuration, systemd user unit
generation, and Mac controller configuration. The old hard-stop record remains
immutable historical evidence. Manual watch and sentinel one-shots must pass
before their timers are enabled. The Mac controller may invoke Codex only for
allowlisted infrastructure failures and remains unable to weaken the epoch,
provider, verifier, accounting, or cleanup contracts.

## Reporting and Analysis

The final report includes:

- repetition 1 labeled scheduler epoch 1 (`worker_concurrency=4`);
- repetitions 2–5 labeled scheduler epoch 2 (`worker_concurrency=12`);
- combined five-repetition metrics requested by the user;
- per-epoch score, provider latency, request count, timeout, cost, and runtime
  summaries;
- a clear warning that concurrency was changed after repetition 1 for
  operational throughput and may introduce an epoch-associated batch effect.

No result may describe all five repetitions as having one scheduler identity.

## Tests and Acceptance Gates

Implementation uses test-driven development and must cover:

1. schema-v1 to schema-v2 migration at exactly one clean boundary;
2. rejection during a panel, with pending primary data, or after any
   repetition-2 evidence exists;
3. immutable repetition-1 evidence before and after migration;
4. scheduler-epoch selection for repetitions 2–5 and resume refusal outside
   the declared epoch;
5. weighted admission of 12 standard attempts and reduction for heavy tasks;
6. exact timeout lower-bound acceptance and ambiguous quarantine rejection;
7. process-group signal forwarding and absence of orphan coordinators;
8. boundary-guard PID/command/start-time validation and idempotency;
9. focused supervisor, baseline, rootless runtime, evaluator, cost, and replay
   suites, followed by the full local test suite;
10. remote no-model, 12-way provider, offline verifier, firewall, exact-cleanup,
    watch, sentinel, boundary, and resume canaries.

Any identity mismatch, repetition-2 pre-boundary request, evaluator exposure,
ambiguous acceptance, replay, cleanup failure, unsupported accounting gap, or
resource-headroom breach causes hard stop without formal resume.
