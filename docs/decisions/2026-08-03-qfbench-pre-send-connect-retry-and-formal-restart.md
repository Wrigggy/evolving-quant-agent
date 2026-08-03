# QFBench Pre-Send Connect Retry and Formal Restart

Date: 2026-08-03

Status: accepted; affected V4 Flash run frozen, fresh run required

Affected run: `qfbench-rootless-base-85x5-official-deepseek-v4-flash-noreplay-recovery2-20260803`

## Evidence

The affected run stopped in repetition 01 with 85 attempts and 82 official
scores. Its checkpoint contains 77 primary and eight diagnostic attempts, no
repetition-02 evidence, and no live run-owned container or network. Two missing
scores retain complete worker executions and may be used only for isolated
verifier-recovery engineering checks.

The third missing score, `structured-note-risk`, cannot be resumed under the
existing attempt identity. Four model requests completed HTTP 200. A fifth
request failed while establishing the upstream connection, before any HTTP
request bytes were transmitted, and was recorded as
`not_accepted/pre_accept_transport`. The worker then exited before persisting a
worker-execution manifest. Replaying the whole worker would repeat the four
accepted stochastic calls; assigning zero or synthesizing verifier output would
misclassify infrastructure failure as an official result.

## Decision

Preserve the affected run byte-for-byte as engineering evidence and exclude its
82 scores from the five-repetition aggregate. Do not mutate its checkpoint,
backfill the missing score, or migrate it to scheduler epoch 2. The scheduler
epoch protocol remains valid for a fresh run: repetition 01 uses worker/verifier
concurrency `4/3`, and repetitions 02–05 may use `12/3` only after the declared
clean boundary and paid twelve-worker canary.

The credential proxy now performs at most three upstream connection attempts.
Only `connection.connect()` failures are retryable; the waits are bounded at
0.25 and 0.50 seconds. Once HTTP request transmission may have started, the
existing quarantine path remains mandatory and no retry occurs. Generic OpenAI
SDK or NexAU retries remain disabled because they cannot prove non-acceptance.
The attempt cap is validated, included in the public proxy config, and bound by
the public plan/config identity and immutable proxy image.

The paid lifecycle audit now reads worker/verifier evidence from
`lifecycles/<run-id>/<attempt-id>/` and proxy/network evidence from
`lifecycles/<attempt-id>/`, while retaining legacy single-root compatibility.

## Gates and Local Evidence

Commit `8ab2be1` implements the retry and lifecycle audit repair. Local tests
prove that a failed pre-send connection followed by success produces one
upstream request and one completed audit record; an after-send disconnect opens
one connection and remains quarantined. The complete repository suite passes
`951 passed, 1 skipped, 1 deselected`. The deselected historical oracle anchor
is absent from Git worktrees and was already verified in the main workspace;
no solution artifact was copied or executed here.

Before a fresh formal launch, deploy one exact commit, rebuild the proxy image,
and bind the resulting immutable image and config identities. Then require the
no-model isolation gate, a provider-route canary, supervisor/recovery canary,
the twelve-worker paid baseline canary, complete canonical cost accounting,
offline verifier evidence, exact cleanup, and zero residual resources. Any
after-send ambiguity remains a hard stop. No prior worker artifact or score may
enter the fresh run.
