# QFBench No-Replay Runtime and Baseline Restart Design

> Date: 2026-08-03
> Status: approved by the user's instruction to repair and rerun repetition 02
> Supersedes: the resume action in `2026-08-03-qfbench-successful-usage-omission-and-repetition-02-design.md`

## Finding

The repetition-01 cost canary found 15 duplicated completed request identities
across 13 attempts in
`qfbench-rootless-base-85x5-official-deepseek-20260801`. The duplicates account
for 17 extra provider calls. Thirteen groups began another identical call near
the configured 180-second client timeout; two groups retried after a completed
but unusable/empty response. Every duplicate reached the provider and completed
with HTTP 200. This is not coordinator resume replay, but it is a second
stochastic sample for one model turn and violates the accepted-request
no-replay contract.

The root cause is two retry layers around a shorter client timeout: the worker
YAML supplies a 180-second OpenAI client timeout, the OpenAI SDK may retry, and
NexAU has an outer five-attempt loop. The proxy permits concurrent identical
requests and waits up to 300 seconds for upstream reads. Observed completed
latency reached 304.218 seconds, so a client could retry while the first
provider request was still live.

## Decision

Preserve the old run and all 85 scores without modification, classify it as
invalid for a repeated-performance baseline, and do not resume it. Historical
cost auditing continues to reject duplicated completed identities. The old run
remains useful for verifier, timeout, cleanup, and failure-discovery evidence.

Create a new content-addressed run and execute repetitions 01 and 02 under one
corrected runtime identity. Do not reuse old worker artifacts or scores. Keep
the benchmark commit, 85-task manifest, seed-worker bytes, model/provider pin,
official verifier images, resources, concurrency, and scoring semantics fixed.

## No-Replay Runtime Invariant

The coordinator-uploaded NexAU worker adapter applies this policy before Agent
construction:

- OpenAI SDK `max_retries = 0`;
- NexAU outer `retry_attempts = 1`;
- model-client timeout is at least 360 seconds, above the proxy's 300-second
  read timeout and observed repetition-01 latency.

NexAU 0.3.9 omits falsy `max_retries=0` from client kwargs, which silently
restores the OpenAI SDK default. The adapter must therefore wrap
`to_client_kwargs()` and explicitly insert integer zero. It then verifies the
constructed client's retry setting when the client exposes it. This policy is
runtime infrastructure, not an evolvable candidate field.

A timeout or post-accept transport ambiguity fails closed as infrastructure;
it is not retried under the same attempt identity. A behavioral task timeout
retains its existing official-zero contract.

## Gates and Execution

Local TDD must prove the adapter overrides both retry layers, raises the timeout
floor, passes explicit zero to the client, and rejects a constructed client
whose retry setting drifts. Run the remote-worker, sandbox-worker, proxy, cost,
baseline, supervisor, and full local suites.

Deploy one exact clean commit. Before paid work, run a no-model adapter canary
inside the pinned NexAU runtime and a read-only audit proving the old run has 15
duplicated completed identities and zero residual resources. Then run one paid
worker-to-offline-verifier canary and require unique accepted request identities,
the pinned DeepSeek provider, no worker-visible credential/trusted material, and
zero residual containers/networks.

Only then launch a new 85-task run with five repetitions configured but
`--stop-after-repetition 2`. Acceptance requires 170 official scores, two
complete repetition evaluations, no duplicated completed request identity, no
ambiguous provider request, lower-bound reporting for genuine all-null usage,
the unchanged verifier firewall, and final zero run-owned Docker resources.
