# Decision: Restart the 85-Task Baseline After Same-Turn Model Replay

> Date: 2026-08-03
> Status: accepted; supersedes repetition-02 resume for the affected run

## Evidence

The no-model accounting canary for
`qfbench-rootless-base-85x5-official-deepseek-20260801` stopped on a duplicate
request identity before approving repetition 02. A complete prompt-free scan of
the repetition-01 proxy ledgers found:

- 1,069 audit records and 1,052 distinct request identities;
- 15 duplicated completed identities in 13 worker attempts;
- 17 extra DeepSeek provider calls, all HTTP 200;
- 13 retry groups beginning near the worker client's 180-second timeout and
  two groups following completed empty/unusable responses;
- maximum recorded completed latency of 304.218 seconds;
- no cross-attempt duplicate and no coordinator/resume replay;
- 85 preserved official scores, six behavioral-timeout zeros, and zero
  run-owned Docker containers or networks.

NexAU 0.3.9 contributes an outer five-attempt loop. Its LLM config also defaults
the OpenAI SDK to retries, and its `to_client_kwargs()` drops explicit zero as
falsy. The proxy can wait 300 seconds for an upstream read. The shorter
180-second client timeout therefore allowed a second identical stochastic call
while the first provider request remained live.

## Ruling

The run is immutable engineering evidence but is invalid as repetition 01 of a
repeated base-worker performance baseline. Its scores, ledgers, timeout records,
and prior incident remain unchanged. Repetition 02 must not resume from it, and
completed duplicate identities remain a fatal cost-audit finding rather than a
supported accounting exception.

The worker runtime now pins one model transmission per turn: OpenAI SDK
`max_retries=0`, NexAU `retry_attempts=1`, and a model-client timeout floor of
360 seconds. The coordinator adapter explicitly restores zero after NexAU's
falsy-value omission and verifies the constructed client. Provider ambiguity
fails closed; it does not obtain another sample.

The rootless runtime identity also binds the SHA-256 and byte length of the
exact coordinator-uploaded worker runner, worker runtime bridge, and evolver
runner. The adapter repair therefore changes the formal runtime digest even
when images, task materials, model route, and seed-worker bytes remain fixed.

After local, no-model, and paid worker/verifier canaries pass, launch
`qfbench-rootless-base-85x5-official-deepseek-noreplay-20260803` from
repetition 01 and stop after repetition 02. The new run reuses the benchmark,
task manifest, seed worker, model/provider, verifier images, resources, and
scoring contract, but records a new source/runtime identity. None of the old
run's worker artifacts or scores may be imported.
