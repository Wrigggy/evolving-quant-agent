# QFBench Timeout and Resume Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve official timeout-zero semantics, resume the interrupted 85-task baseline without duplicate model calls, and report all reconcilable provider cost while explicitly listing the one unknown quarantined timeout request.

**Architecture:** Persisted per-attempt records remain the task-level source of truth. A focused timeout-evidence loader validates coordinator-written command and quarantine records, the proxy manager separates audit errors from actual resource-cleanup failures, and the baseline cost auditor allows only timeout-bound unreconciled ledgers while keeping every other ambiguity fatal.

**Tech Stack:** Python 3.10+, dataclasses, pathlib, JSON/SHA-256, `ThreadPoolExecutor`, pytest, rootless Docker, SSH deployment to `bc`.

## Global Constraints

- Keep QFBench pinned to commit `024921eb507fcc0c4ffe3e0a96802724be1ae84a`.
- Keep model `deepseek/deepseek-v4-pro` pinned to provider `deepseek` with fallback disabled.
- Preserve official reward and timeout semantics; a 2400-second worker timeout is reward `0.0` and receives no retry sample.
- Preserve independent no-network verification and never expose tests, references, solutions, credentials, or raw verifier output to workers.
- Keep exact-ID proxy/container/network cleanup fatal when cleanup is not proven.
- Do not merge. Stage and commit only files owned by this implementation.
- Preserve the interrupted run; additions must be atomic, explicitly named, and source-hash bound.

---

### Task 1: Validate and recover persisted worker timeouts

**Files:**
- Modify: `qea/executors/execution_record.py`
- Modify: `qea/loop_benchmark.py`
- Test: `tests/test_qfbench_evolution.py`

**Interfaces:**
- Produces: `PersistedWorkerTimeout` with `log_uri`, `command_sha256`, `quarantine_sha256`, and `quarantine_reason`.
- Produces: `load_persisted_worker_timeout(attempt: TaskAttempt, run_dir: str | Path) -> PersistedWorkerTimeout | None`.
- Produces: `persist_timeout_recovery(attempt_dir: Path, evidence: PersistedWorkerTimeout) -> Path`.
- Consumes: stable `TaskAttempt`, `worker-command.json`, and `proxy-audit.quarantined.json`.

- [ ] **Step 1: Write failing timeout-evidence tests**

Add tests that create an exact attempt directory with:

```python
(attempt_dir / "worker-command.json").write_text(json.dumps({
    "exit_code": 124,
    "stdout": "",
    "stderr": "",
    "timed_out": True,
}))
(attempt_dir / "proxy-audit.quarantined.json").write_text(json.dumps({
    "schema_version": 1,
    "request_state": "quarantined",
    "reason": "audit_download_or_validation_failed",
}))
```

Assert that evaluation writes one reward-zero score with `("timeout",)`,
writes `timeout-recovery.json` with both source hashes, and calls neither the
worker executor nor verifier. Add parameterized failures for missing paired
evidence, `timed_out=false`, exit code other than 124, extra JSON keys,
conflicting `proxy-audit.jsonl`, and unsupported quarantine reason.

- [ ] **Step 2: Run the focused tests and confirm RED**

Run:

```bash
.venv-nexau/bin/python -m pytest -q \
  tests/test_qfbench_evolution.py -k 'persisted_timeout or timeout_recovery'
```

Expected: failures because the persisted-timeout loader and recovery record do
not exist.

- [ ] **Step 3: Implement exact timeout evidence loading**

In `execution_record.py`, require exact JSON schemas, bounded strings, exit
code 124, `timed_out is True`, the exact quarantine schema/reason, and absence
of a canonical audit. Compute SHA-256 over the original evidence bytes. Return
`None` only when neither evidence file exists; a half-present or malformed pair
raises `WorkerExecutionError` before any external action.

Persist this exact recovery schema atomically and idempotently:

```python
{
    "schema_version": 1,
    "attempt_id": attempt.attempt_id,
    "outcome": "official_worker_timeout_zero",
    "command_sha256": evidence.command_sha256,
    "quarantine_sha256": evidence.quarantine_sha256,
    "quarantine_reason": evidence.quarantine_reason,
}
```

In `_run_worker_stage`, preserve the precedence:

```text
completed score -> worker execution -> persisted timeout -> new worker
```

Write the recovery record before the score; rerunning after a crash must accept
an identical record and reject byte drift.

- [ ] **Step 4: Run focused tests and confirm GREEN**

Run the Task 1 command again. Expected: all selected tests pass.

- [ ] **Step 5: Commit Task 1**

```bash
git add qea/executors/execution_record.py qea/loop_benchmark.py \
  tests/test_qfbench_evolution.py
git commit -m "fix(qfbench): recover persisted worker timeouts"
```

### Task 2: Preserve behavioral timeout across proxy audit failure

**Files:**
- Modify: `qea/executors/execution_record.py`
- Modify: `qea/executors/sandbox_proxy.py`
- Test: `tests/test_sandbox_proxy.py`

**Interfaces:**
- Extends: `WorkerBehaviorTimeout.proxy_audit_failures: tuple[str, ...]`.
- Preserves: original timeout object and traceback when audit finalization fails but resource cleanup succeeds.
- Keeps fatal: proxy kill or internal-network cleanup failures.

- [ ] **Step 1: Write failing cleanup-precedence tests**

Use `RecordingBackend` with a timed-out finalize result and a caller-raised
`WorkerBehaviorTimeout`. Assert:

```python
with pytest.raises(WorkerBehaviorTimeout) as raised:
    with _open(manager, run_dir):
        raise timeout
assert raised.value is timeout
assert raised.value.proxy_audit_failures
assert quarantine_marker.is_file()
assert backend.events[-2] == ("kill", "proxy-native-1")
assert backend.events[-1][0] == "network-remove"
```

Add a second test where exact proxy kill fails. It must raise
`SandboxProxyError` containing `proxy.cleanup` with the original timeout as
`__cause__`.

- [ ] **Step 2: Run the focused tests and confirm RED**

Run:

```bash
.venv-nexau/bin/python -m pytest -q tests/test_sandbox_proxy.py \
  -k 'timeout and (finalize or cleanup)'
```

Expected: finalize failure currently replaces the timeout with
`SandboxProxyError`.

- [ ] **Step 3: Split audit errors from resource cleanup errors**

Keep separate `audit_errors` and `cleanup_errors` collections. Audit finalize,
seal, download, and validation failures write the quarantine marker and enter
`audit_errors`; lifecycle finish, exact proxy kill, and exact network removal
enter `cleanup_errors`.

At context exit:

```text
resource cleanup error -> fatal SandboxProxyError from primary error
audit error + WorkerBehaviorTimeout -> attach bounded messages, re-raise timeout
audit error + other/no primary error -> fatal SandboxProxyError
no teardown error + primary error -> re-raise primary error
```

Retain current fail-closed handling for an ambiguous downloaded audit unless
the only primary error is the official worker timeout.

- [ ] **Step 4: Run focused proxy and timeout-score tests**

Run:

```bash
.venv-nexau/bin/python -m pytest -q \
  tests/test_sandbox_proxy.py \
  tests/test_qfbench_evolution.py::test_e2b_evaluator_records_worker_command_timeout_as_zero_reward
```

Expected: pass.

- [ ] **Step 5: Commit Task 2**

```bash
git add qea/executors/execution_record.py qea/executors/sandbox_proxy.py \
  tests/test_sandbox_proxy.py
git commit -m "fix(proxy): preserve official worker timeout"
```

### Task 3: Report timeout-bound unknown provider cost

**Files:**
- Modify: `qea/qfbench_baseline.py`
- Test: `tests/test_qfbench_baseline.py`

**Interfaces:**
- Extends: `audit_baseline_proxy_costs(run_dir, expected_attempts)` result with `cost_complete`, `provider_cost_is_lower_bound`, `unreconciled_attempt_count`, and `unreconciled_attempts`.
- Consumes: validated timeout score plus exact quarantine marker when the canonical ledger is absent.

- [ ] **Step 1: Write failing lower-bound cost tests**

Add one scored timeout attempt with no `proxy-audit.jsonl` and the exact
quarantine marker. Assert normal ledgers remain summed exactly and output
contains:

```python
assert audit["cost_complete"] is False
assert audit["provider_cost_is_lower_bound"] is True
assert audit["unreconciled_attempt_count"] == 1
assert audit["unreconciled_attempts"] == [{
    "attempt_id": timeout_attempt_id,
    "checkpoint": "repetition-01-primary",
    "panel": "primary",
    "repetition": 1,
    "task_id": "slow-task",
    "reason": "audit_download_or_validation_failed",
}]
```

Add failures for reward one, missing timeout tag, malformed marker, both marker
and canonical ledger, and a missing ledger without a marker. Confirm the normal
fixture reports `cost_complete=true` and an empty exception list.

- [ ] **Step 2: Run focused cost tests and confirm RED**

Run:

```bash
.venv-nexau/bin/python -m pytest -q tests/test_qfbench_baseline.py \
  -k 'cost_audit'
```

Expected: the existing auditor rejects the timeout ledger and lacks the new
fields.

- [ ] **Step 3: Implement the narrow cost exception**

Parse score and checkpoint identity before reading the ledger. Accept an absent
ledger only when reward is exactly `0.0`, diagnostic tags contain `timeout`,
and the quarantine marker has the exact supported schema. Append identity-only
metadata, do not increment request/token/cost counts, and set the lower-bound
flags. All other existing validation remains unchanged.

- [ ] **Step 4: Run cost tests and confirm GREEN**

Run the Task 3 command again. Expected: pass.

- [ ] **Step 5: Commit Task 3**

```bash
git add qea/qfbench_baseline.py tests/test_qfbench_baseline.py
git commit -m "feat(cost): report quarantined timeout lower bound"
```

### Task 4: Prove mixed-state resume without duplicate model calls

**Files:**
- Modify: `tests/test_qfbench_evolution.py`
- Modify: `tests/test_qfbench_baseline.py`

**Interfaces:**
- Consumes: completed-score loading, worker-execution loading, persisted-timeout recovery, and fresh worker execution from Tasks 1-3.
- Produces: regression evidence for the exact 16/4/1/pending recovery pattern at fixture scale.

- [ ] **Step 1: Add a four-state resume integration test**

Create four tasks in one panel:

```text
task-scored     -> completed-score.json
task-worker     -> worker-execution.json with valid artifact hashes
task-timeout    -> worker-command.json + quarantine marker
task-pending    -> no terminal files
```

Assert executor calls equal `['task-pending']`, verifier calls equal
`['task-worker', 'task-pending']`, all four scores retain input order, timeout
is zero, and a second evaluation makes no worker or verifier calls.

- [ ] **Step 2: Run the integration test and confirm GREEN**

Run:

```bash
.venv-nexau/bin/python -m pytest -q tests/test_qfbench_evolution.py \
  -k 'mixed_state_resume'
```

Expected: pass using the completed implementation.

- [ ] **Step 3: Run all focused recovery suites**

Run:

```bash
.venv-nexau/bin/python -m pytest -q \
  tests/test_qfbench_evolution.py \
  tests/test_sandbox_proxy.py \
  tests/test_qfbench_baseline.py
```

Expected: pass.

- [ ] **Step 4: Commit Task 4**

```bash
git add tests/test_qfbench_evolution.py tests/test_qfbench_baseline.py
git commit -m "test(qfbench): cover mixed timeout resume"
```

### Task 5: Full verification and immutable deployment

**Files:**
- Verify: all modified Python and documentation files
- Create remotely: a new bc deployment ref and recovery-canary artifacts

**Interfaces:**
- Consumes: committed implementation from Tasks 1-4.
- Produces: exact commit SHA, passing test evidence, deployed source identity, and a canary acceptance record.

- [ ] **Step 1: Run static checks and focused compile**

Run:

```bash
git diff --check HEAD~4..HEAD
.venv-nexau/bin/python -m compileall -q qea tests
```

Expected: zero exit.

- [ ] **Step 2: Run the full local suite**

Run:

```bash
.venv-nexau/bin/python -m pytest -q tests \
  --deselect tests/test_qfbench_pilot_contract.py::test_saved_local_oracle_anchor_is_pinned_and_passed
```

Expected: all selected tests pass. The deselection remains limited to the
historical generated anchor absent from this linked worktree.

- [ ] **Step 3: Verify branch scope and push without merging**

Run:

```bash
git status --short
git log --oneline --decorate -8
git push origin qfbench-selfhosted-vm-backend
```

Confirm only implementation-owned paths are committed and protected dirty files
remain unstaged.

- [ ] **Step 4: Deploy the exact feature commit to bc**

Push the exact SHA to a new bc-only deployment ref, switch the detached
`/home/julius/qea/worktrees/qfbench-base85-baseline` deployment to that ref,
and verify `git rev-parse HEAD`, `git status --short`, and the existing
immutable official-provider configuration and image identities.

- [ ] **Step 5: Run a deterministic rootless recovery canary**

Exercise a short fixture attempt that persists `timed_out=true`, forces proxy
audit finalization failure, proves timeout-zero conversion, reuses a completed
worker execution for verifier-only recovery, emits lower-bound cost metadata,
and finishes with zero run-scoped containers and networks. Persist a private
acceptance JSON with source SHA, test command, expected evidence hashes, and
cleanup counts.

### Task 6: Resume and audit formal repetition one

**Files:**
- Preserve remotely: `/home/julius/qea/runs/qfbench-rootless-base-85x5-official-deepseek-20260801`
- Create remotely: a new resume launcher, PID file, log, exit file, and post-run audits

**Interfaces:**
- Consumes: canary-accepted deployed commit and the stopped run's durable attempt files.
- Produces: 85 repetition-one official scores, revised canonical cost report, firewall audit, and zero-resource cleanup audit.

- [ ] **Step 1: Preflight the stopped run without mutation**

Verify the exact counts `16` scores, `4` reusable worker executions without
scores, `1` proven timeout, no live resources, unchanged runtime identity, and
official provider pin. Hash the stopped run's existing evidence inventory.

- [ ] **Step 2: Launch resume under a new durable supervisor record**

Use the same run ID and immutable configuration, but new `.resume-01.pid`,
`.resume-01.log`, and `.resume-01.exit` files so the original exit-code-1
record remains unchanged. Keep worker concurrency 4, verifier concurrency 3,
and `--stop-after-repetition 1`.

- [ ] **Step 3: Verify the recovery boundary immediately**

Confirm the recovered timeout score and recovery record appear, the 16 score
hashes remain unchanged, the four reusable workers do not open new proxies, and
only genuinely pending tasks generate fresh worker/proxy lifecycles.

- [ ] **Step 4: Monitor repetition one to completion**

Track completed scores, request states, token/cost lower bound, failures,
worker/verifier concurrency, and exact run resources. Stop on provider-route
drift, verifier firewall failure, non-timeout missing ledger, or cleanup leak.

- [ ] **Step 5: Run post-repetition acceptance audits**

Require 85 official scores, all available proxy records schema-valid, exactly
one allowed timeout cost exception, no duplicate request identities, accepted
firewall scan, and zero run-scoped containers/networks. Persist the result and
keep repetitions two through five gated pending review of repetition one.
