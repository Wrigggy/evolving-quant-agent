# Decision: Restart the Repeated Baseline with DeepSeek V4 Flash

> Date: 2026-08-03
> Status: accepted; supersedes the planned V4 Pro two-repetition restart

## Evidence

The stopped no-replay V4 Pro run
`qfbench-rootless-base-85x5-official-deepseek-noreplay-20260803` exited with code
1 during repetition 01. It produced 12 attempt directories and seven official
scores. All 128 provider records are unique within their attempts and completed
HTTP 200, but one unscored attempt has no worker execution after five accepted
requests. Four other unscored attempts retain complete worker artifacts suitable
only for verifier-recovery engineering checks. The external supervisor recorded
the exit, while the active remote watchdog did not publish an incident and the
Mac repair controller remained bound to the earlier run.

The proxy wrote `completed` audit records before sending the spooled response to
the worker. The evidence therefore proves provider completion but not downstream
delivery. It does not authorize another stochastic sample under the same scoring
attempt.

Separately, the five-repetition protocol permits identical content hashes across
different attempts. The current run-wide duplicate check would incorrectly stop
valid repetitions even though the earlier invalid V4 Pro replay groups occurred
within a single attempt.

OpenRouter's official model page specifies the requested slug as
[`deepseek/deepseek-v4-flash`](https://openrouter.ai/deepseek/deepseek-v4-flash/api).

## Ruling

Preserve both V4 Pro runs without rewriting scores or ledgers. They remain
engineering evidence and are excluded from V4 Flash performance estimates.

Define replay by `(attempt_id, request_identity_sha256)`, require proxy completion
to include downstream flush, and connect the exact external supervisor paths to
the incident sentinel. Rebind the Mac controller and hold one continuous
run-scoped `caffeinate` assertion while monitoring.

After local tests and bounded canaries, start a new content-addressed run at
repetition 01 using model `deepseek/deepseek-v4-flash`, required provider
`deepseek`, and `allow_fallbacks=false`. Run all five preregistered independent
repetitions (425 official scoring attempts). Preserve the benchmark commit,
85-task manifest, seed worker, images, resources, concurrency, temperature,
official verifier inputs, and scoring contract. No V4 Pro artifact or score may
enter the new aggregate.
