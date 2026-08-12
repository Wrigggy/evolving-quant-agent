# QFBench A6 r8 seed rate-limit incident

> Status: measured interrupted seed; canonical accounting incomplete; r8 seed,
> discovery, and candidate IDs frozen; no corpus or discovery result.

## Conclusion

The fresh r8 seed is not admissible. Its fixed Flash/DeepSeek route was live and
the first provider requests reached the expected proxy, but a 12-worker burst
produced 12 HTTP 429 responses across 12 of 13 task ledgers. The r8 proxy
persisted those rows as `request_state=completed` with
`failure_class=provider_http_error`. That representation is intentionally
rejected by the canonical fixed-checkpoint auditor, which requires a completed
request to be an HTTP 200 with no failure class.

The immutable r8 evidence therefore contains 40 raw rows: 28 completed HTTP
200 rows and 12 canonical-incompatible HTTP 429 rows. The 28 accepted rows have
28 unique provider request IDs, 179,660 recorded tokens, and USD
`0.0148273832` recorded cost. Those token and cost values are lower bounds, not
complete totals. There is no seed report, no completed score, no formal R/E/EC
corpus, no proposal, and no candidate.

The machine-readable incident record is
[r8-seed-rate-limit-incident.json](../../output/qfbench-supervisor/a6-7704a05305551d96-r8/r8-seed-rate-limit-incident.json),
5,400 bytes with SHA-256
`16dc84d722ce321cda7e95baad2fba509f4c3d04d941f8454e33d6ef233d3da7`.

## Frozen identities

- Run ID: `qfbench-a6-seed-evidence-flash-20260810-r8`
- Remote release:
  `/home/julius/qea/deploy/releases/a6-7704a05305551d96`
- Source tree:
  `7704a05305551d9647f44ea1548d8d4fa046511b61691a86670247a4268491dd`
- External release manifest:
  `51027c3a709c727818335b6443c6c9542a01e4315aed0b841d9c167785ee6055`
- External ten-field identity record:
  `07a1f5211ae744288dacc1defad072b563376f5efb6e203e252c89e7907e3f84`
- Materialized launch identity:
  `2d89531865d5168ea26a88b3c33730f294e4a28bd464779905e492170a7da90a`
- Same-ID plan:
  `91b8c6249360d7027549211f0bad32b738e460309a5e743a410f7224f052d820`

These identities remain useful infrastructure evidence. They do not rescue the
failed accounting gate or authorize reuse of the r8 seed/corpus under repaired
source bytes.

## Measured incident boundary

The 13 persisted task ledgers contain:

| Raw state | HTTP status | Failure class | Rows |
|---|---:|---|---:|
| `completed` | 200 | `null` | 28 |
| `completed` | 429 | `provider_http_error` | 12 |

The first persisted request began at
`2026-08-10T03:01:52.284514+00:00`; the first 429 began at
`03:01:56.015597+00:00`; the last 429 ended at
`03:03:48.025667+00:00`; and the last persisted row ended at
`03:05:32.008871+00:00`. Twelve of the 13 attempts failed after a 429.
`credit-spread-decomposition` produced one worker execution after 12 HTTP 200
requests, but containment occurred before any official score was persisted.

This is a provider-rate-limit/infrastructure failure. It is not task reward
zero, an Evolver ABSTAIN, a comparison among A6-R/E/EC, or evidence for or
against harness improvement.

## Stop and durability evidence

The bounded monitor was unloaded first, the r8 health timer was disabled and
stopped, and the coordinator was explicitly stopped. Its final state is PID 0,
failed/signal, `NRestarts=1`: `Restart=on-failure` had scheduled one same-ID
restart before containment completed. The aggregate raw ledger above is
preserved as observed; it is not split into speculative per-invocation totals.

All 13 worker, 13 proxy, and 13 scoped-network lifecycle records are exact-ID
clean. The canonical reaper dry/apply/final-dry sequence reports zero pending,
failed, mismatched, or final inventory IDs. The final full 63-ID additive mirror
completed the r8 run at `2026-08-10T03:11:38Z` with exit 0 and zero stderr,
then the mirror was unloaded. Final managed container, network, and lease
counts are zero.

## Source-audited failure and minimal repair

R8 exposed two concrete boundaries:

1. A safe provider 429 was delivered as a terminal model-client error and
   recorded as completed, which poisoned canonical accounting rather than
   making a bounded fresh request at the same logical call boundary.
2. The same final run ID could enter a systemd restart after a paid boundary,
   because the preflight plan identity did not also provide a durable
   execute-once claim.

The accepted R9 patch stays tied to those observations:

- a safe 429 is fully buffered, durably recorded as
  `not_accepted/rate_limited` with null provider identity, usage, and cost, and
  never exposed to the agent;
- the proxy may make at most three independent upstream wire attempts for one
  logical call (initial plus two), each on a fresh connection and with the exact
  original target/body/provider pin;
- the retry wall budget is 60 monotonic seconds after the first safe 429;
  `Retry-After` is honored when present, while absence uses 1- then 2-second
  fallback waits; malformed, negative, or out-of-budget values fail closed;
- only the final HTTP 200 response is returned to the agent; safe 429 rows
  remain visible as a separate retry count and never become zero-cost accepted
  calls;
- NexAU Evolver outer retries are pinned to `retry_attempts=1`, OpenAI SDK
  retries to `max_retries=0`, and the client timeout to at least 360 seconds,
  so a proxy-level three-attempt exhaustion cannot be multiplied outside the
  proxy;
- component and discovery runners share a mode-0600, file-and-directory-fsynced
  `O_EXCL` paid-boundary marker bound to exact plan, identity record, launch
  digest, run kind, and arm. Preflight does not claim it; a same-ID restart
  fails before evaluator/proposer/provider access; and
- the fresh seed uses worker concurrency 1, while R/E/EC discovery is staged
  sequentially. These are new identity-bound scheduler/config values, not an
  in-place r8 change.

Focused source and integration review is `PATCH PASS`; the focused seven-file
suite passes 215 tests, including a real NexAU Agent exhaustion path with
exactly three upstream wire requests and no outer replay. The complete NexAU
environment passes `1189 passed, 1 skipped`. This is offline test evidence only.
No R9 remote release, model request, seed score, corpus, or discovery result
exists at the time of this report.

## Recovery boundary

Freeze all seven r8 run IDs. Do not resume the seed, reinterpret the 429 rows,
or reuse any r8 corpus. Recovery requires a new content-addressed r9 source
release, new ten-field identity, fresh exact IDs, same-ID zero-call preflight,
inactive unit/monitor/mirror audit, a fresh 16-task seed, complete canonical
request/token/cost accounting, fresh byte-matched R/E/EC corpora, and the same
independent per-stage launch gates.

Candidate evaluation, A6-F, feedback, mutation, and the user's proposal for
more tasks/repetitions remain later scientific stages. More tasks may improve
cross-task precision, but they do not repair a malformed request ledger or
substitute for independent run repetitions.
