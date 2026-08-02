# QFBench Autonomous Repair Supervisor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair the current verifier artifact-integrity defect, deploy a bounded Mac-controlled autonomous repair supervisor, and safely resume the interrupted formal QFBench repetition without duplicate worker/model calls.

**Architecture:** Pure Python policy code owns incident identity, state transitions, classification, evidence hashes, and repair budget. A deterministic bc sentinel emits sanitized incidents; a Mac `launchd` controller owns SSH, local `codex exec`, exact-commit deployment, canary, and resume commands. Existing QFBench manifests remain authoritative, and any isolation, identity, history, cost, or cleanup drift stops before automated repair or resume.

**Tech Stack:** Python 3.10+ standard library, pytest, JSON/SHA-256, `fcntl`, `subprocess`, macOS `launchd`, SSH, rootless Docker, Git.

## Global Constraints

- Keep QFBench at `024921eb507fcc0c4ffe3e0a96802724be1ae84a`, model `deepseek/deepseek-v4-pro`, required provider `deepseek`, and fallbacks disabled.
- Keep worker concurrency 4, verifier concurrency 3, offline independent verifiers, and exact-ID resource cleanup.
- Never send `.env`, credentials, official tests/reference data, solutions, raw verifier verdicts, or held-out outcomes to Codex, workers, or evolvers.
- Reuse completed scores and integrity-checked worker executions; never resample a durable worker solely because verification failed.
- Permit at most three code-changing repair cycles for one formal run; fail closed on the boundaries in the approved spec.
- Keep all source changes on `qfbench-selfhosted-vm-backend`; do not merge and do not stage pre-existing dirty files.
- Deploy only an exact tested commit into a clean detached worktree on bc; never edit remote source directly.

---

### Task 1: Make verifier artifact inclusion match the worker manifest

**Files:**
- Modify: `qea/executors/bundles.py`
- Modify: `tests/test_qfbench_isolation.py`

**Interfaces:**
- Produces: `_tree_files(root: Path, *, skip_cache: bool = True) -> tuple[Path, ...]`.
- Preserves: worker/evolver/oracle source bundles skip `__pycache__`; verifier artifact enumeration includes every regular manifest-visible artifact, including `__pycache__/*.pyc`.

- [ ] **Step 1: Write the failing artifact regression test**

Add `test_verifier_bundle_preserves_declared_python_cache_artifact`. Create
`artifacts/function-under-new-api.py` and
`artifacts/__pycache__/function-under-new-api.cpython-311.pyc`, build the
verifier bundle, and assert both exact `artifacts/...` members are present.
Also retain the existing checks that tests are verifier-only and secret-like
paths fail closed.

- [ ] **Step 2: Run the focused test and confirm RED**

Run:

```bash
.venv-nexau/bin/python -m pytest -q \
  tests/test_qfbench_isolation.py::test_verifier_bundle_preserves_declared_python_cache_artifact
```

Expected: FAIL because `_tree_files()` globally excludes `__pycache__`.

- [ ] **Step 3: Implement the narrow inclusion policy**

Change `_tree_files` to skip `.git` unconditionally and skip `__pycache__` only
when `skip_cache=True`. Call `_tree_files(artifact_root, skip_cache=False)` only
from `build_verifier_bundle`. Preserve symlink, traversal, secret-file, size,
count, and deterministic-order checks.

- [ ] **Step 4: Run focused and bundle suites**

Run:

```bash
.venv-nexau/bin/python -m pytest -q tests/test_qfbench_isolation.py
.venv-nexau/bin/python -m pytest -q \
  tests/test_execution_record.py tests/test_sandbox_nexau.py \
  tests/test_rootless_runtime.py
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add qea/executors/bundles.py tests/test_qfbench_isolation.py
git commit -m "fix(verifier): preserve manifested cache artifacts"
```

### Task 2: Implement the fail-closed incident policy and state store

**Files:**
- Create: `qea/repair_supervisor.py`
- Create: `tests/test_repair_supervisor.py`
- Modify: `qea/__init__.py`

**Interfaces:**
- Produces: `IncidentState(str, Enum)` with the states from the approved spec.
- Produces: immutable `Incident`, `ExpectedIdentity`, and `Classification` dataclasses.
- Produces: `incident_id(run_id, source_commit, exit_evidence_sha256, failure_signature) -> str`.
- Produces: `classify_incident(incident: Incident) -> Classification`.
- Produces: `IncidentStore(root: Path).create/load/transition/record_repair` using atomic JSON writes.

- [ ] **Step 1: Write failing policy tests**

Cover deterministic incident ids; allowed transitions; idempotent repeated
transitions; rejection of skipped/backward transitions; one active incident;
repair counts 1, 2, and 3; and terminal `repair_budget_exhausted`. Parameterize
`hard_stop` classification for firewall/network, secret/exposure, official
data, identity/config/provider/image/checkpoint drift, historical hash drift,
ambiguous request acceptance, unsupported cost omission, and cleanup failure.
Assert a normalized artifact-integrity verifier failure is `repairable`.

- [ ] **Step 2: Run tests and confirm RED**

Run:

```bash
.venv-nexau/bin/python -m pytest -q tests/test_repair_supervisor.py
```

Expected: import failure because `qea.repair_supervisor` does not exist.

- [ ] **Step 3: Implement immutable schemas and transitions**

Use schema version 1, exact-key JSON validation, 64-character lowercase
SHA-256 fields, 40-character source SHAs, bounded strings, and allowlisted
failure categories. Persist via temporary sibling plus `Path.replace()`. Reject
existing byte drift. Never store raw logs; store only bounded redacted excerpts
and evidence hashes. `record_repair()` must atomically increment the counter and
refuse a fourth code-changing attempt.

- [ ] **Step 4: Run the policy tests and confirm GREEN**

Run the Task 2 command. Expected: PASS.

- [ ] **Step 5: Commit Task 2**

```bash
git add qea/repair_supervisor.py qea/__init__.py tests/test_repair_supervisor.py
git commit -m "feat(supervisor): add fail-closed incident state"
```

### Task 3: Add the deterministic bc sentinel

**Files:**
- Create: `scripts/run_qfbench_rootless_sentinel.py`
- Create: `tests/test_qfbench_rootless_sentinel.py`
- Create: `deploy/systemd/qea-qfbench-sentinel.service`

**Interfaces:**
- Consumes: an owner-only schema-v1 JSON config containing `run_id`, `run_dir`, `source_commit`, `expected_identity`, `coordinator_pid_file`, `exit_code_file`, `failure_log`, and `state_dir`.
- Produces: one atomic sanitized incident under `<state_dir>/incidents/<incident_id>/incident.json`.
- CLI: `python scripts/run_qfbench_rootless_sentinel.py --config PATH [--once] [--interval-seconds 30]`.

- [ ] **Step 1: Write failing sentinel tests**

Use `tmp_path` fixtures for a running coordinator, completed run, stopped
coordinator with exit 87 and the known artifact-integrity signature, duplicate
polls, oversized/binary logs, symlinked evidence, and permissions. Assert that
only the stopped incomplete run creates one incident, its excerpt is redacted
and bounded, files are `0600`, directories are `0700`, and repeated polls do
not create a second incident.

- [ ] **Step 2: Run tests and confirm RED**

Run:

```bash
.venv-nexau/bin/python -m pytest -q tests/test_qfbench_rootless_sentinel.py
```

Expected: script module is absent.

- [ ] **Step 3: Implement observation without repair authority**

Validate the config and all paths before reading. Treat live PID plus matching
command identity as running. Treat a valid completion marker as resolved.
Otherwise hash the exit record and bounded failure log, normalize known
signatures without copying secrets, create the incident through `IncidentStore`,
and stop there. The script must not import Git, SSH, Codex, model, verifier, or
Docker mutation code.

The tracked systemd unit runs the script from bc's clean deploy worktree, uses
`Restart=on-failure`, `UMask=0077`, and an explicit owner-only config path. It
must not contain a credential or official-data path.

- [ ] **Step 4: Run sentinel and policy tests**

Run:

```bash
.venv-nexau/bin/python -m pytest -q \
  tests/test_repair_supervisor.py tests/test_qfbench_rootless_sentinel.py
```

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

```bash
git add scripts/run_qfbench_rootless_sentinel.py \
  tests/test_qfbench_rootless_sentinel.py \
  deploy/systemd/qea-qfbench-sentinel.service
git commit -m "feat(supervisor): add rootless run sentinel"
```

### Task 4: Add the Mac controller and bounded Codex adapter

**Files:**
- Create: `scripts/run_qfbench_repair_controller.py`
- Create: `tests/test_qfbench_repair_controller.py`
- Create: `deploy/launchd/com.qea.qfbench-repair-supervisor.plist`

**Interfaces:**
- Consumes: owner-only controller JSON with `ssh_host`, `remote_state_dir`, `worktree`, `branch`, `max_repairs=3`, allowlisted test/deploy/canary/resume argv arrays, and expected identities.
- CLI: `python scripts/run_qfbench_repair_controller.py --config PATH [--once] [--dry-run]`.
- Produces: local append-only controller records and remote state transitions; exit 0 for no work/resolved, 10 for transient SSH, 20 for hard stop, and 30 for repair-budget exhaustion.
- Produces: `build_codex_prompt(incident, config) -> str` and argv-based subprocess calls with no shell.

- [ ] **Step 1: Write failing controller tests**

Inject a fake command runner and clock. Cover `fcntl` lock exclusion, no
incident, duplicate incident, transient SSH failure/backoff metadata,
`hard_stop` without Codex, repairable incident, Codex nonzero exit, test
failure, dirty or wrong branch, commit mismatch, deploy failure, canary failure,
successful resume, and third-cycle exhaustion. Assert argv arrays are passed
without `shell=True`, prompts contain only sanitized incident fields, and no
forbidden key/value/path can enter the prompt.

- [ ] **Step 2: Run tests and confirm RED**

Run:

```bash
.venv-nexau/bin/python -m pytest -q tests/test_qfbench_repair_controller.py
```

Expected: script module is absent.

- [ ] **Step 3: Implement the bounded controller pipeline**

Use `fcntl.flock(LOCK_EX | LOCK_NB)` on one local lock file. Fetch incident JSON
with BatchMode SSH, validate it locally, classify it, and transition it before
each external step. Build the fixed Codex prompt from identity and failure
metadata only. Invoke:

```text
codex exec --full-auto --cd <feature-worktree> <sanitized-fixed-prompt>
```

After Codex succeeds, require the allowlisted focused/full tests, a tracked-clean
owned-file set, the configured feature branch, and a new commit. Push the exact
commit, deploy it to a clean detached bc worktree, compare local/remote SHA,
then run the allowlisted canary and resume argv. Never interpolate a remote
value into a shell command; use fixed remote helper argv plus validated ids.

The launchd plist uses `StartInterval=60`, `KeepAlive=false`, absolute program
paths, the owner-only config, and bounded stdout/stderr files. It contains no
secret environment variables. Exit 10 is retried by the next launchd interval;
terminal policy exits are recorded but do not mutate the incident.

- [ ] **Step 4: Run controller, sentinel, and policy tests**

Run:

```bash
.venv-nexau/bin/python -m pytest -q \
  tests/test_repair_supervisor.py \
  tests/test_qfbench_rootless_sentinel.py \
  tests/test_qfbench_repair_controller.py
```

Expected: PASS.

- [ ] **Step 5: Commit Task 4**

```bash
git add scripts/run_qfbench_repair_controller.py \
  tests/test_qfbench_repair_controller.py \
  deploy/launchd/com.qea.qfbench-repair-supervisor.plist
git commit -m "feat(supervisor): add Mac repair controller"
```

### Task 5: Verify the implementation and deploy the exact commit

**Files:**
- Modify only if tests expose a defect: files owned by Tasks 1-4.
- Create at runtime on bc: `/home/julius/qea/runtime/supervisor/config.json`.
- Create at runtime on Mac: `runtime/qfbench-supervisor/controller.json` and state files (gitignored).

**Interfaces:**
- Consumes: committed Task 1-4 implementation.
- Produces: full local verification evidence, exact deployed SHA, owner-only runtime configs, dry-run controller evidence, and active sentinel/controller service status.

- [ ] **Step 1: Run focused and full local verification**

Run:

```bash
.venv-nexau/bin/python -m pytest -q \
  tests/test_qfbench_isolation.py \
  tests/test_repair_supervisor.py \
  tests/test_qfbench_rootless_sentinel.py \
  tests/test_qfbench_repair_controller.py
.venv-nexau/bin/python -m pytest -q tests
git diff --check
```

Expected: all tests pass except documented dependency skips; no whitespace
errors and no unrelated staged files.

- [ ] **Step 2: Push and deploy exact source identity**

Push `qfbench-selfhosted-vm-backend`. On bc, fetch the feature branch into its
deploy-only ref, create or update a detached clean worktree at the exact local
HEAD, and verify `git rev-parse HEAD` matches locally. Stop if either tree has
tracked drift.

- [ ] **Step 3: Materialize owner-only configs and test the services once**

Create configs without credentials, set directories `0700` and files `0600`,
run sentinel `--once`, then run controller `--once --dry-run`. Validate one
deduplicated current incident and no unexpected mutation. Install the user
systemd unit only if `systemctl --user is-system-running` is supported;
otherwise use the documented durable process fallback. Bootstrap the launchd
plist from the tracked worktree only after the current incident is safely
resolved or suppressed during the manual recovery.

- [ ] **Step 4: Commit any test-driven corrections and redeploy**

If Step 1-3 expose a defect, add a failing regression test, implement the
minimal fix, rerun the affected plus full suites, make one scoped commit, push,
and revalidate the exact deployed SHA. Do not consume more than the three-cycle
repair budget.

### Task 6: Canary the persisted artifacts and resume repetition one

**Remote artifacts:**
- Preserve: `/home/julius/qea/runs/qfbench-rootless-base-85x5-official-deepseek-20260801`.
- Create: a separately identified verifier-only canary directory under `/home/julius/qea/runs/`.
- Create: supervisor incident, deployment, canary, resume, firewall, cost, and cleanup manifests under owner-only state/run paths.

**Interfaces:**
- Consumes: exact deployed commit and the four durable no-score worker checkpoints.
- Produces: networkless verifier-only canary, byte-preservation audit, resumed 85-score repetition one, and active future monitoring.

- [ ] **Step 1: Freeze pre-recovery evidence**

Record SHA-256 for all 63 existing scores, 62 worker manifests/artifact trees,
62 canonical proxy audits, five timeout records, formal config, image set, and
runtime identities. Dry-run the exact-ID reaper and require zero ambiguous or
foreign resources.

- [ ] **Step 2: Run the `polars-api-migration` verifier-only canary**

Copy only that attempt's persisted worker artifacts into a new canary identity.
Build the verifier bundle with the repaired contract and assert both the `.py`
and manifested `.pyc` are present. Run the official verifier in an independent
`--network none` container. Require no proxy/worker/model lifecycle, expected
artifact-integrity acceptance, and zero residual canary resources.

- [ ] **Step 3: Resume the formal run at repetition one**

Run the existing full-harness resume command with the immutable formal config,
worker concurrency 4, verifier concurrency 3, official DeepSeek route, and the
same run ID. The four reusable worker executions must enter verifier-only
continuation; completed scores and persisted timeout outcomes must be skipped.

- [ ] **Step 4: Audit before releasing later repetitions**

Require 85/85 official scores, unchanged hashes for every pre-recovery terminal
artifact, no duplicate worker/model request for the four reusable executions,
all canonical provider ledgers or the approved timeout lower-bound exceptions,
zero firewall findings, and zero run-owned containers/networks. Any failure
enters `hard_stop`; repetitions two through five remain blocked.

- [ ] **Step 5: Enable ongoing monitoring and report exact status**

Mark the current incident resolved, enable the bc sentinel and Mac launchd
controller, and run one no-op poll from each. Report source SHA, run/canary ids,
repair count, score counts, worker/model replay count, cost lower bound, service
status, and residual-resource counts. Do not merge.
