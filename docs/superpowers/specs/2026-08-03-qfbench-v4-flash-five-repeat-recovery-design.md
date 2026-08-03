# QFBench V4 Flash Five-Repeat Recovery Design

> Date: 2026-08-03
> Status: approved by the user's instruction to complete the recovery and resume with DeepSeek V4 Flash
> Supersedes: the V4 Pro restart action in `2026-08-03-qfbench-no-replay-runtime-and-baseline-restart-design.md`

## Experiment Boundary

OpenRouter's official model page identifies DeepSeek V4 Flash as
`deepseek/deepseek-v4-flash`. The formal route remains pinned to provider
`deepseek` with fallbacks disabled. Changing the model creates a new experiment
arm: the stopped V4 Pro run and its seven scores remain immutable engineering
evidence and are never imported into V4 Flash results.

The new run starts at repetition 01 and schedules five independent repetitions
of all 85 runnable QFBench tasks: 425 official scoring attempts. Every
repetition creates a fresh task attempt, worker sandbox, NexAU agent, trajectory,
artifact set, and independent no-network verifier sandbox. Model temperature and
all non-model benchmark/runtime inputs remain frozen.

## Request Identity and Delivery

`request_identity_sha256` remains a hash of the exact provider-bound request.
The no-replay key is `(attempt_id, request_identity_sha256)`: a duplicate within
one attempt is fatal, while the same request content across different
preregistered repetitions is expected and is reported separately. Adding a
nonce to model input is forbidden because it would change the experimental
distribution and defeat content auditing.

A proxy record is `completed` only after the entire upstream response has been
read, screened, written to the worker connection, and flushed. A provider-
accepted response whose downstream delivery fails is quarantined with its
accounting retained and cannot be resampled. This closes the window in which an
HTTP-200 provider call was logged as complete before the worker received it.

## Failure Detection and Autonomous Recovery

The remote sentinel receives separate exact `run_dir` and `supervisor_dir`
roots. It may read only configured regular files beneath those roots, so the
external launcher PID, exit code, log, and completion marker are observable
without broadening filesystem access. A dead coordinator with no valid
completion marker always freezes an incident; a nonzero exit cannot remain a
progress-only event.

The Mac controller is rebound to the new run identity before launch. It runs as
a long-lived, lock-protected poll loop under `caffeinate`, tolerates temporary
SSH loss, and invokes Codex only for allowlisted infrastructure categories.
Identity drift, evaluator/firewall exposure, accepted-request ambiguity, cost
omission, or cleanup failure remain hard stops. Repairs may not change the
model/provider route, benchmark, worker behavior, verifier contract, or formal
configuration.

## Gates and Launch

Local TDD and full regression tests precede deployment of one clean commit. The
remote gate then requires: an in-image no-model adapter test, attempt-scoped
replay audit, forced coordinator-exit incident canary, controller dry run,
official-provider V4 Flash worker canary, independent offline verifier, firewall
scan, authoritative cost record, and zero residual run-owned resources.

After those gates pass, launch
`qfbench-rootless-base-85x5-official-deepseek-v4-flash-noreplay-20260803`
from repetition 01. The run may continue through all five repetitions under the
same frozen identity. Report raw task/repetition/domain scores, mean and sample
uncertainty, token/cost totals or explicit lower bounds, replay findings, and
resource cleanup; never translate missing accounting into zero.
