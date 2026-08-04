# QFBench Worker Launch Ramp Design

## Context

The corrected twelve-worker rootless canary passed its host and resource gates,
then all twelve first model requests received explicit HTTP 503 responses from
the required DeepSeek provider. The records had no generation ID, token counts,
or provider cost. All worker and proxy resources were exact-ID reaped. A prior
one-worker provider canary completed eleven requests successfully. A later
one-worker canary completed two requests before receiving the same 503 while
DeepSeek reported degraded V4 Flash API performance. This rules out rootless
capacity and cleanup as the cause, but does not prove that startup burst was
the sole provider failure.

## Decision

Keep epoch-2 worker concurrency at twelve and verifier concurrency at three,
but add a scheduler-owned `worker_launch_interval_seconds` setting. The fresh
formal run will use a two-second interval. The evaluator applies the interval
immediately before each genuinely new worker execution. It does not delay
completed scores, persisted worker executions awaiting verification, or
persisted timeout recovery.

The interval is part of the rootless scheduler identity. Config schemas 1-3
remain readable with an implicit zero interval; schema 4 requires the explicit
field. The paid epoch-2 canary requires schema-4 semantics, interval two,
concurrency 12/3, and a measured maximum overlap of twelve workers.
Provider recovery and a fresh successful single-worker canary are independent
prerequisites; the ramp is not evidence that the provider is healthy.

## Safety Boundaries

- An HTTP response proves the request was sent. The proxy and worker do not
  replay a 503 within an attempt.
- A failed canary directory is immutable evidence. A new canary uses a new run
  ID and new attempt identities.
- Provider fallback remains disabled.
- The verifier remains networkless and receives official tests only through
  trusted verifier storage.
- The ramp changes launch timing only; it does not change task order, rewards,
  official scoring, model identity, or worker contents.

## Acceptance

Unit tests must prove minimum launch spacing, zero-delay compatibility, resume
bypass, schema validation, scheduler-identity drift, and canary enforcement.
The paid canary must then show successful official scores, complete provider
accounting, no within-attempt replay, twelve-way worker overlap, and zero
residual resources before epoch 2 is eligible to run.
