# QFBench Successful-Usage Omission and Repetition 02 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reconcile identity-bound successful provider responses whose accounting is unavailable, correct the sentinel provider-brand false positive, and resume the preserved formal run for repetition 02 only.

**Architecture:** Keep canonical proxy records and repetition-01 scores immutable. Extend the baseline cost auditor with one atomic all-null accounting state that remains an explicit lower bound, and narrow sentinel credential detection to actual credential syntax rather than provider names. Deploy one exact source commit, validate the preserved run without model calls, then resume from the existing `calibration_stop` checkpoint with `--stop-after-repetition 2`.

**Tech Stack:** Python 3.10+, pytest, Git, SSH, rootless Docker, systemd user services, JSON checkpoint/audit artifacts.

## Global Constraints

- Preserve QFBench commit `024921eb507fcc0c4ffe3e0a96802724be1ae84a`, model `deepseek/deepseek-v4-pro`, required provider `deepseek`, and `allow_fallbacks=false`.
- Preserve the 85 repetition-01 attempts and scores byte-for-byte; do not rerun any repetition-01 worker or model request.
- Keep official tests/reference data verifier-only, verifier networking disabled, official solutions absent, and worker inputs answer-free.
- Unknown usage/cost remains unknown and is never inferred or converted to zero.
- Resume only repetition 02 and stop with `next_repetition == 3`; do not release repetition 03.
- Use exact-ID cleanup only, do not merge, and do not stage unrelated pre-existing documentation changes.

---

### Task 1: Correct provider-brand sentinel classification

**Files:**
- Modify: `tests/test_qfbench_rootless_sentinel.py`
- Modify: `scripts/run_qfbench_rootless_sentinel.py`

**Interfaces:**
- Consumes: `_classify(raw: bytes) -> tuple[str, str]` and `_redact(raw: bytes) -> str` through the public `observe(...)` path.
- Produces: brand-only `openrouter` text no longer triggers `credential_exposure`; concrete credential markers retain the existing hard stop and redaction behavior.

- [ ] **Step 1: Write the failing observable regression test**

Add `test_provider_brand_does_not_mask_cost_omission` using `_sentinel_config`.
Replace the fixture failure log with:

```text
model transport label: openrouter-compatible
cost audit missing successful usage
```

Call `observe(config, pid_alive=lambda pid: False)` and assert:

```python
assert incident.category == "unsupported_cost_omission"
assert incident.failure_signature == "unsupported cost ledger omission"
assert "openrouter-compatible" in incident.excerpt
```

The production break caught by this test is reintroducing a provider brand into
the credential-marker set or evaluating brand text as credential exposure.

- [ ] **Step 2: Run RED**

Run:

```bash
/Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q tests/test_qfbench_rootless_sentinel.py::test_provider_brand_does_not_mask_cost_omission
```

Expected: FAIL because the current incident category is
`credential_exposure`.

- [ ] **Step 3: Implement the narrow fix**

Remove only `b"openrouter"` from `_REDACT_MARKERS`. Retain `b"api_key"`,
`b"api-key"`, `b"authorization:"`, `b"bearer "`, `b"token="`, `b".env"`,
`b"credentials"`, and `b"secret"`. Do not reorder the remaining security and
failure classifications.

- [ ] **Step 4: Run GREEN and the existing secret regression**

Run:

```bash
/Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q tests/test_qfbench_rootless_sentinel.py
```

Expected: all sentinel tests pass, including
`test_secret_like_binary_log_is_bounded_redacted_and_hard_stop`.

- [ ] **Step 5: Commit Task 1**

```bash
git add scripts/run_qfbench_rootless_sentinel.py tests/test_qfbench_rootless_sentinel.py
git commit -m "fix(supervisor): ignore provider brands in secret scan"
```

### Task 2: Report successful requests with unavailable accounting

**Files:**
- Modify: `tests/test_qfbench_baseline.py`
- Modify: `qea/qfbench_baseline.py`

**Interfaces:**
- Extends: `audit_baseline_proxy_costs(run_dir, expected_attempts)` with `unreconciled_request_count: int` and `unreconciled_requests: list[dict]`.
- Preserves: timeout-only `unreconciled_attempt_count` and `unreconciled_attempts`.
- Changes internal contract: `_validated_completed_cost(...) -> Decimal | None`, where `None` means an exact completed/HTTP-200/all-null accounting omission.

- [ ] **Step 1: Write the failing all-null accounting test**

Add `test_cost_audit_reports_completed_request_without_accounting_as_lower_bound`.
Use `_cost_fixture`, replace all four accounting fields on the first canonical
record with `None`, and assert these hand-derived values:

```python
assert audit["attempt_count"] == 2
assert audit["request_count"] == 3
assert audit["completed_request_count"] == 3
assert audit["input_tokens"] == 50
assert audit["output_tokens"] == 10
assert audit["total_tokens"] == 60
assert audit["provider_cost_usd"] == "0.05"
assert audit["cost_complete"] is False
assert audit["provider_cost_is_lower_bound"] is True
assert audit["unreconciled_attempt_count"] == 0
assert audit["unreconciled_request_count"] == 1
```

Assert the single unresolved item exactly contains the first attempt identity,
`repetition-01-primary`, panel `primary`, repetition `1`, task `risk-task`, the
record request identity, and reason `successful_response_usage_unavailable`.
The production break caught is treating an atomically unavailable successful
response as fatal or silently adding zero accounting.

- [ ] **Step 2: Add partial/mislabelled omission rejection cases**

Keep `null_success_cost` and `null_success_usage` in
`test_cost_audit_fails_closed_on_incomplete_or_drifted_ledger`; each changes
only one field and must remain fatal. Add `successful_failure_class`, setting
all four accounting fields to `None` plus `failure_class="unexpected"`, and
require `BaselineConfigError`.

- [ ] **Step 3: Run RED**

Run:

```bash
/Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q tests/test_qfbench_baseline.py -k "completed_request_without_accounting or fails_closed_on_incomplete"
```

Expected: the new all-null test fails with `cost audit missing successful
usage`; existing partial-omission tests continue to pass.

- [ ] **Step 4: Implement atomic omission validation and aggregation**

In `_validated_completed_cost`, inspect the three token values and cost as one
accounting tuple. If all four are `None` and `failure_class is None`, return
`None`. If only some are `None`, or a completed request has a non-null failure
class, raise `BaselineConfigError`. Keep all existing nonnegative, finite,
arithmetic, schema, status, state, and identity validation for accounted
records.

Make `_add_cost` accept `Decimal | None`: always increment request count and
completed-request count for a completed record, but add tokens and dollars only
when cost is not `None`.

In `audit_baseline_proxy_costs`, validate request-identity uniqueness for every
record. Append an identity-only item when cost is `None`; then pass the record
through all three total/panel/task counters. Set:

```python
payload["cost_complete"] = not (unreconciled_attempts or unreconciled_requests)
payload["provider_cost_is_lower_bound"] = bool(
    unreconciled_attempts or unreconciled_requests
)
payload["unreconciled_request_count"] = len(unreconciled_requests)
payload["unreconciled_requests"] = unreconciled_requests
```

- [ ] **Step 5: Run GREEN and the full baseline test file**

Run:

```bash
/Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q tests/test_qfbench_baseline.py
```

Expected: every baseline test passes; partial omissions and unsupported ledger
states remain rejected.

- [ ] **Step 6: Commit Task 2**

```bash
git add qea/qfbench_baseline.py tests/test_qfbench_baseline.py
git commit -m "fix(cost): preserve successful usage omissions"
```

### Task 3: Verify the local infrastructure patch

**Files:**
- Verify only: `qea/`, `scripts/`, `tests/`

**Interfaces:**
- Consumes: both Task 1 and Task 2 commits.
- Produces: one exact, locally verified source commit suitable for immutable deployment.

- [ ] **Step 1: Run focused integration suites**

```bash
/Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q \
  tests/test_qfbench_baseline.py \
  tests/test_qfbench_rootless_sentinel.py \
  tests/test_repair_supervisor.py \
  tests/test_qfbench_repair_controller.py \
  tests/test_model_proxy.py \
  tests/test_sandbox_proxy.py
```

Expected: zero failures.

- [ ] **Step 2: Run the complete dependency-available test suite**

```bash
/Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q tests
```

Expected: zero failures; explicitly report any environment-gated skips.

- [ ] **Step 3: Audit source scope and whitespace**

```bash
git diff --check HEAD~2..HEAD
git status --short --branch
git log -4 --oneline
```

Expected: only the approved spec, sentinel/test, and cost-auditor/test changes
are committed; pre-existing dirty documentation remains unstaged.

- [ ] **Step 4: Push the feature branch without merging**

```bash
git push origin qfbench-selfhosted-vm-backend
```

Record the full source SHA for deployment.

### Task 4: Deploy and run no-model repetition-01 canaries

**Files:**
- Read remotely: `/home/julius/qea/runs/qfbench-rootless-base-85x5-official-deepseek-20260801`
- Create remotely: `/home/julius/qea/runtime/canaries/qfbench-rep01-accounting-<sha12>/`
- Create remotely: `/home/julius/qea/runtime/canaries/qfbench-sentinel-provider-brand-<sha12>/`

**Interfaces:**
- Consumes: exact Task 3 source SHA and preserved repetition-01 artifacts.
- Produces: owner-only `acceptance.json` artifacts for accounting and sentinel behavior; invokes no model, worker, verifier, or official solution.

- [ ] **Step 1: Deploy the exact commit**

Use the existing exact deploy adapter and bare Git transport. Require remote
`git rev-parse HEAD` to equal the local full SHA and remote `git status
--short` to be empty. Do not change worker/proxy/verifier image identities.

- [ ] **Step 2: Snapshot formal evidence before canaries**

Create an owner-only manifest of repetition-01 `attempt.json`,
`completed-score.json`, worker execution, proxy audit/quarantine, verifier
official-score, `resume.json`, and `result.json` hashes. Require 85 attempts,
85 scores, 79 workers/verifiers, six timeout quarantines, and zero run-owned
Docker containers/networks.

- [ ] **Step 3: Run the real-ledger accounting canary**

With `PYTHONPATH` pinned to the new deployment, call:

```python
audit_baseline_proxy_costs(formal_run_dir, expected_attempts=85)
```

Require `cost_complete=false`, `provider_cost_is_lower_bound=true`, six timeout
attempt exceptions, six successful-response accounting exceptions across
`stable-residual`, `fft-compound-poisson`, `lookback-options`, and
`mc-greek-surface-1`, unique request identities, and no formal-run file hash
changes. Persist the full lower-bound audit plus a bounded acceptance summary.

- [ ] **Step 4: Run the sentinel provider-brand canary**

Create a synthetic owner-only run directory whose failure log contains a
brand-only information line and `cost audit missing successful usage`. Run the
deployed sentinel once and require category `unsupported_cost_omission`.
Separately use a synthetic `OPENROUTER_API_KEY=fixture-value` line, require
category `credential_exposure`, and require the fixture value absent from the
incident excerpt. Delete no formal evidence.

- [ ] **Step 5: Recheck exact cleanup and formal hashes**

Require zero canary/formal managed containers and networks and byte-identical
formal evidence. Stop before repetition 02 on any mismatch.

### Task 5: Audit repetition 01 and run repetition 02

**Files:**
- Preserve remotely: `/home/julius/qea/runs/qfbench-rootless-base-85x5-official-deepseek-20260801`
- Create remotely: one pre-repetition-02 snapshot, launcher directory,
  supervisor state directory, progress log, completion marker, and post-run
  audit directory bound to the exact deployment SHA.

**Interfaces:**
- Consumes: accepted Task 4 canaries, frozen runtime identities, and checkpoint `phase=calibration_stop`, `next_repetition=2`.
- Produces: exactly repetition 02, then `phase=calibration_stop`, `next_repetition=3`, 170 official scores, and a post-repetition-02 acceptance artifact.

- [ ] **Step 1: Run the full repetition-01 acceptance gate**

Require 85/85 scores, the Task 4 cost report, unchanged protected hashes,
worker bundle firewall pass, offline verifier/network evidence, required
provider `deepseek`, fallback disabled, expected benchmark/image/runtime/
scheduler identities, and zero residual resources. Preserve the prior
false-positive incident unchanged and use a new supervisor state directory.

- [ ] **Step 2: Create the exact repetition-02 launcher**

Reuse the immutable official-provider configuration and existing run ID. Pin
the new source deployment, `--resume`, five total repetitions, worker
concurrency 4, verifier concurrency 3, and `--stop-after-repetition 2`.
Before launch, require the checkpoint contains exactly one completed
repetition and `next_repetition == 2`.

- [ ] **Step 3: Start fail-closed supervision and the coordinator**

Update the bc sentinel to the new exact launcher/exit/completion/state paths.
Start one durable coordinator plus a watcher that records attempt, score,
worker, verifier, quarantine, protected-hash, and run-owned Docker counts. The
watcher must run the post-repetition-02 audit only after coordinator exit 0 or
the explicitly accepted continuation-gate exit.

- [ ] **Step 4: Monitor repetition 02 to terminal state**

Progress must move from 85 to 170 attempts/scores without changing any
repetition-01 worker/proxy/score hash. Stop on identity drift, new unsupported
accounting shape, firewall failure, duplicate request identity, unexpected
worker replay, or cleanup residue.

- [ ] **Step 5: Run post-repetition-02 acceptance**

Require 170 attempts and scores; workers plus timeout quarantines equal 170;
workers equal proxy ledgers and independent official verifiers; all request
identities are unique; all known usage/cost is summed; every unknown is listed;
checkpoint is `calibration_stop` with `next_repetition == 3`; result has two
completed repetitions and `complete=false`; firewall findings and residual
containers/networks are zero.

- [ ] **Step 6: Freeze repetition 03 and record the decision**

Do not resume again. Write a new dated decision record with exact source/run/
canary/audit identities and append a concise current-state entry to
`docs/PROJECT_MEMORY.md` without rewriting dated reports. Do not merge.
