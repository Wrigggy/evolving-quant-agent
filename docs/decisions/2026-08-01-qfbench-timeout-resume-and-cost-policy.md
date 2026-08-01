# QFBench Timeout Resume and Cost Policy

> Date: 2026-08-01<br>
> Status: approved for implementation<br>
> Scope: official-provider repeated base-worker baseline<br>
> Supersedes: only the complete-cost stopping gate in the
> [official-provider route decision](2026-08-01-qfbench-official-provider-route.md)

## Decision

A worker that reaches its official task timeout receives official reward zero
and does not receive a second model sample. One task timeout must not abort the
remaining panel when exact proxy/container/network cleanup succeeds.

Resume keeps content-addressed completed scores, reuses integrity-checked worker
executions for verifier-only continuation, recovers a coordinator-proven
persisted timeout as zero, and runs only tasks with no durable terminal or
reusable state. The interrupted run
`qfbench-rootless-base-85x5-official-deepseek-20260801` will continue under this
policy after tests and a recovery canary pass.

## Cost Exception

Canonical proxy ledgers remain authoritative and all available costs and tokens
must still be validated and summed. A quarantined proxy ledger associated with
a proven official worker timeout may remain unreconciled. It must be reported
as an explicit unknown item, and the aggregate provider cost must be labelled a
lower bound. Unknown cost is never converted to zero.

No other missing or ambiguous ledger is accepted. Provider routing, evaluator
isolation, official rewards, resource contracts, and exact-ID cleanup gates are
unchanged.

## Acceptance

Implementation requires deterministic timeout, cleanup-precedence, mixed-state
resume, and lower-bound cost-audit tests; a forced-timeout rootless canary; and
zero residual run resources. Repetitions two through five remain gated on the
completed and audited repetition one.
