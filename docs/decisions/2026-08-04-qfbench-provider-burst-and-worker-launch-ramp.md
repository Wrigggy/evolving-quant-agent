# QFBench Provider Burst and Worker Launch Ramp

Date: 2026-08-04
Status: accepted; supersedes the epoch-2 zero-ramp scheduling detail in the
2026-08-03 scheduler-epoch decision. All other model, provider, task, scoring,
isolation, and no-replay decisions remain unchanged.

## Evidence

The corrected twelve-task rootless canary
`qfbench-v4-flash-presend-epoch2-batch-1de511f-r2` passed its host and static
resource gates. Each of its twelve first requests then received an explicit
HTTP 503 from `deepseek/deepseek-v4-flash`. All twelve audit records were
terminal `provider_http_error` records with no provider request ID, token
counts, or provider cost. The worker and proxy lifecycle records were complete
and exact-ID cleaned. No OOM, lease, disk, PID, verifier, or residual-resource
failure was observed.

The earlier single-worker canary completed eleven official-provider requests,
80,896 tokens, and one official score without fallback or replay. Together,
the evidence identifies the simultaneous twelve-request startup burst as the
failed condition; it does not justify replaying a sent request.

## Decision

Fresh formal rootless configs use schema 4 and an explicit
`worker_launch_interval_seconds: 2`. Epoch 1 remains concurrency 4/3 and epoch
2 remains concurrency 12/3. The common evaluator gates only genuinely new
worker executions, using a monotonic minimum interval. Resume reuse, verifier
work, completed scores, and persisted timeout recovery do not consume ramp
slots.

The ramp is included in the scheduler identity. Config schemas 1-3 remain
readable with implicit interval zero and retain their legacy scheduler digest.
The paid epoch-2 canary must enforce interval two, achieve measured worker
overlap twelve, complete provider accounting, observe zero within-attempt
replay, and leave no managed resource before repetitions 2-5 may run.

## Resource Boundary

The corrected panel still reserves at most 48 CPU, 96 GiB, and 24 simultaneous
worker/proxy sandboxes. The launch ramp does not raise those limits. Host
headroom remains a separate fail-closed gate with at least 16 GiB available
memory; verifiers enter only after the corresponding worker/proxy lease is
released.
