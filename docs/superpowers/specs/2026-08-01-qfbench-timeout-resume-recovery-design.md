# QFBench Timeout and Resume Recovery Design

> Date: 2026-08-01<br>
> Status: approved approach; pending written-spec review<br>
> Scope: repeated QFBench base-worker baseline on self-hosted rootless Docker

## Goal and Evidence Boundary

Recover the interrupted official-provider run without discarding valid work or
giving a timed-out task an extra model sample. Preserve the official score,
provider pin, evaluator firewall, artifact identities, and exact-ID cleanup.
Continue exact accounting for every canonical proxy ledger, while reporting a
quarantined timeout request as unknown rather than zero.

The interrupted run is
`qfbench-rootless-base-85x5-official-deepseek-20260801`. It currently contains
16 completed official scores, four complete worker executions awaiting only
verification, and one timed-out attempt (`american-option-fd-new`) whose proxy
audit was quarantined after finalize exceeded its 120-second controller
deadline. The worker and proxy lifecycles are cleaned, and the persisted worker
command proves `timed_out=true` with exit code 124.

## Chosen Policy

Use continuation policy B:

- retain all content-addressed completed scores;
- reuse verified worker-execution manifests and run only the missing verifier;
- materialize official reward zero for a persisted, coordinator-authored worker
  timeout without resampling the model;
- execute only tasks that have neither a completed score nor a reusable worker
  execution;
- continue the same repetition and run ID;
- keep all reconcilable token and cost totals exact;
- list every quarantined timeout ledger separately and label the aggregate cost
  as a lower bound.

No timeout retry ordinal is introduced. A behavioral timeout is an official
task outcome, not infrastructure permission to give the worker another sample.

## Timeout Evidence and Score Recovery

`QFBenchSandboxEvaluator` remains the owner of official timeout-to-zero
conversion. It may recover a persisted timeout only when all of the following
fail-closed checks pass:

1. `attempt.json` exactly matches the content-addressed run, benchmark, task,
   split, checkpoint, and worker digest expected by the current evaluation.
2. No `completed-score.json` or `worker-execution.json` exists.
3. `worker-command.json` is an exact bounded command record with
   `timed_out=true` and integer exit code 124.
4. A private `proxy-audit.quarantined.json` exists with the exact supported
   schema, state `quarantined`, and reason
   `audit_download_or_validation_failed`.
5. No canonical `proxy-audit.jsonl` is simultaneously presented as complete.

On success, the evaluator atomically writes the same official timeout score it
would have written during the original call: reward `0.0`, diagnostic tag
`timeout`, and the worker-command log URI. It also writes a non-score recovery
record containing the hashes of the input evidence and the recovery policy
version. Any mismatch remains an infrastructure error and performs no model
call or verifier call.

Future timeouts should not need migration. The proxy manager will distinguish
three classes of teardown result:

- **primary behavioral error:** preserve and re-raise the original
  `WorkerBehaviorTimeout` after resource cleanup;
- **audit/accounting error:** persist a quarantine marker and attach bounded
  audit-failure metadata without replacing the behavioral timeout;
- **resource cleanup error:** if exact proxy/container/network cleanup is not
  proven, raise a cleanup infrastructure error and retain the original error as
  its cause.

This prevents an audit-finalize timeout from masking the official worker
timeout while keeping real resource leaks fatal.

## Resume Data Flow

Per-attempt files, not the panel-level `completed` list in `resume.json`, are
the durable task checkpoint. For each stable attempt identity, evaluation uses
this order:

1. Load and identity-check `completed-score.json`; do no worker or verifier
   work.
2. Otherwise load and hash-check `worker-execution.json`; run only the isolated
   verifier.
3. Otherwise recover a proven persisted timeout as reward zero.
4. Otherwise start a fresh worker and proxy for that never-completed task.

The panel-level checkpoint advances only after every primary score is present,
then after every diagnostic score is present. Existing stage concurrency stays
at four workers and three verifiers. Infrastructure failures remain fail-closed;
only `WorkerBehaviorTimeout` is an official zero.

For the current run, this means 16 score reuses, four verifier-only executions,
one recovered timeout zero, and 64 new worker executions to finish repetition
one.

## Cost Reporting

The canonical cost audit continues validating every available request record:
schema, model, terminal state, HTTP status, usage arithmetic, cost value, and
request-identity uniqueness. Audited records continue contributing exact input,
output, total-token, and provider-cost sums.

A missing ledger is tolerated only for an attempt that has both a validated
timeout score and the exact supported quarantine marker. The report adds:

- `cost_complete: false`;
- `provider_cost_is_lower_bound: true`;
- `unreconciled_attempt_count`;
- an identity-only list of unreconciled run/checkpoint/task/attempt records and
  quarantine reasons.

The unknown request contributes no fabricated request count, token count, or
dollar value. Missing ledgers for successful scores, verifier failures, normal
worker failures, or arbitrary quarantine states remain fatal.

## Isolation and Integrity

This change does not expose tests, test reference data, solutions, raw verifier
output, credentials, or held-out identities to workers. Verifiers remain
independent and offline. The model route remains
`provider.only=["deepseek"]` with fallback disabled. Recovered timeout evidence
is coordinator-authored metadata and contains no official answer material.

The interrupted artifacts are preserved byte-for-byte except for new,
explicitly named recovery records and the recovered timeout score. Recovery
records must carry source hashes so the addition is auditable rather than a
silent historical rewrite.

## Tests and Deployment Gates

Implementation starts with failing tests for:

- caller timeout preserved when proxy audit finalization fails but exact cleanup
  succeeds;
- cleanup failure remains fatal and chains the timeout as its cause;
- persisted timeout recovery creates one zero score without worker/verifier
  calls;
- malformed, conflicting, or non-timeout recovery evidence fails before a
  model call;
- mixed resume skips completed scores, verifies reusable executions, recovers
  one timeout, and runs only genuinely pending workers;
- cost audit remains exact for normal ledgers and reports one timeout ledger as
  an explicit lower-bound exception;
- non-timeout missing or quarantined ledgers remain rejected.

After the focused and full local suites pass, deploy the exact commit and build
a new immutable proxy image only if proxy runtime bytes changed. Run a bounded
rootless recovery canary that forces a worker timeout plus proxy-finalize
failure, verifies zero score, exact cleanup, no model retry, lower-bound cost
reporting, and resume idempotency. Only then resume the current repetition.

Repetition one remains a calibration gate: repetitions two through five are not
released until all 85 scores, firewall audit, exact-ID cleanup, and the revised
cost report pass.
