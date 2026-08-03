# QFBench Scheduler Epoch Transition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve the completed repetition-1 evidence at concurrency 4, migrate the baseline checkpoint at one proven-clean boundary, and run repetitions 2–5 at concurrency 12 with fail-closed supervision and per-epoch reporting.

**Architecture:** Separate the sampling identity from an ordered scheduler-epoch contract in schema-v2 baseline checkpoints. A trusted bc-local boundary guard freezes the legacy coordinator exactly after repetition 1, validates and hashes all boundary evidence, and publishes the schema-v2 checkpoint only when no repetition-2 evidence or live resource exists. A process-group supervisor, run-aware watch, sentinel, and 12-task canary protect the resumed epoch-2 coordinator.

**Tech Stack:** Python 3.10+, pytest, rootless Docker, Linux `/proc` and inotify, JSON/JSONL checkpoints, systemd user services, macOS `launchd`/`caffeinate`, Git/SSH deployment.

## Global Constraints

- Run ID remains `qfbench-rootless-base-85x5-official-deepseek-v4-flash-noreplay-recovery2-20260803`.
- Repetition 1 remains scheduler epoch 1 with worker concurrency 4 and verifier concurrency 3.
- Repetitions 2–5 use scheduler epoch 2 with worker concurrency 12 and verifier concurrency 3.
- Epoch-2 capacity is 48 CPU, 98,304 MiB memory, 8,192 PIDs, 24 sandboxes, and 40,960 MiB tmpfs; headroom remains 16,384 MiB `MemAvailable` and maximum load 56.
- Keep model `deepseek/deepseek-v4-flash`, provider `deepseek`, fallbacks disabled, the frozen task/image/worker identities, and official rewards unchanged.
- Official tests/reference data remain verifier-only and networkless. Never upload or execute official solutions.
- A supported timeout is a cost lower bound only when reward is 0, the diagnostic tag is `timeout`, the marker is exactly schema 1/state `quarantined`/reason `audit_download_or_validation_failed`, lifecycle cleanup is exact and complete, and no canonical ledger exists.
- Any repetition-2 evidence before migration, identity drift, ambiguous accepted request, replay, evaluator exposure, accounting conflict, residual resource, or headroom violation causes a hard stop.
- Preserve old run evidence and pre-existing dirty files. Do not merge this branch or perform broad cleanup.

---

### Task 1: Add the scheduler-epoch checkpoint contract

**Files:**
- Create: `qea/qfbench_scheduler_epochs.py`
- Modify: `qea/qfbench_baseline.py`
- Modify: `tests/test_qfbench_baseline.py`
- Test: `tests/test_qfbench_scheduler_epochs.py`

**Interfaces:**
- Produces: `SchedulerEpochError`, `SchedulerEpoch`, `validate_scheduler_epochs()`, `epoch_for_repetition()`, `sampling_identity()`, and `migrate_v1_checkpoint()`.
- Consumes: the existing schema-v1 `resume.json`, `BaselineConfig`, and immutable task/worker/model/image identities.

- [ ] **Step 1: Write failing unit tests for epoch validation and clean migration**

```python
def test_epoch_contract_covers_each_repetition_exactly_once():
    epochs = (
        SchedulerEpoch(1, 1, 4, 3, "1" * 64),
        SchedulerEpoch(2, 5, 12, 3, "2" * 64),
    )
    assert epoch_for_repetition(epochs, 1).worker_concurrency == 4
    assert epoch_for_repetition(epochs, 5).worker_concurrency == 12


def test_clean_v1_boundary_migrates_without_mutating_completed_record(tmp_path):
    before = _schema_v1_boundary_state()
    resume = tmp_path / "resume.json"
    resume.write_text(json.dumps(before))
    migrated = migrate_v1_checkpoint(
        resume,
        scheduler_epochs=_epochs(),
        boundary_manifest_sha256="a" * 64,
    )
    assert migrated["schema_version"] == 2
    assert migrated["completed"] == before["completed"]
    assert migrated["sampling_identity"] == sampling_identity(before["identity"])
```

Add parametrized rejections for overlapping epochs, gaps, non-1/5 endpoints, invalid digests, `phase != "primary"`, `next_repetition != 2`, non-null `pending_primary`, and incomplete repetition 1.

- [ ] **Step 2: Run the new tests and verify RED**

Run: `python3 -m pytest -q tests/test_qfbench_scheduler_epochs.py tests/test_qfbench_baseline.py -k 'epoch or migration'`

Expected: collection/import failure because `qea.qfbench_scheduler_epochs` does not exist.

- [ ] **Step 3: Implement the immutable epoch model and atomic migration**

```python
@dataclass(frozen=True)
class SchedulerEpoch:
    first_repetition: int
    last_repetition: int
    worker_concurrency: int
    verifier_concurrency: int
    scheduler_identity_digest: str


def epoch_for_repetition(
    epochs: tuple[SchedulerEpoch, ...], repetition: int
) -> SchedulerEpoch:
    matches = tuple(
        epoch for epoch in epochs
        if epoch.first_repetition <= repetition <= epoch.last_repetition
    )
    if len(matches) != 1:
        raise SchedulerEpochError("repetition has no unique scheduler epoch")
    return matches[0]
```

`migrate_v1_checkpoint()` must require the exact clean boundary, move only scheduler fields out of `identity`, retain every completed score object as a deep-equal JSON value, add `sampling_identity`, `scheduler_epochs`, and `boundary_manifest_sha256`, then use the existing atomic JSON replacement pattern. The boundary manifest preserves the pre-migration checkpoint hash, and no attempt/score/ledger/lifecycle file is rewritten. The function must reject schema-v2 input unless it is semantically identical to the requested migration, making reruns idempotent.

- [ ] **Step 4: Make baseline resume select and validate the declared epoch**

Extend `BaselineConfig` with `scheduler_epochs: tuple[SchedulerEpoch, ...] | None`. Preserve schema-v1 behavior when it is `None`. For schema v2, validate sampling identity once, select `epoch_for_repetition(..., state["next_repetition"])`, and require the active runtime's concurrency and scheduler digest to equal that epoch. Record the active epoch index in `result.json` without changing official score aggregation.

- [ ] **Step 5: Run focused and complete baseline tests**

Run: `python3 -m pytest -q tests/test_qfbench_scheduler_epochs.py tests/test_qfbench_baseline.py`

Expected: PASS, including legacy schema-v1 resume compatibility.

- [ ] **Step 6: Commit the checkpoint contract**

```bash
git add qea/qfbench_scheduler_epochs.py qea/qfbench_baseline.py tests/test_qfbench_scheduler_epochs.py tests/test_qfbench_baseline.py
git commit -m "feat(baseline): add scheduler epoch checkpoints"
```

---

### Task 2: Select the epoch before assembling the rootless runtime

**Files:**
- Modify: `run.py`
- Modify: `qea/rootless_full_harness.py`
- Modify: `tests/test_run_cli.py`
- Modify: `tests/test_rootless_full_harness.py`

**Interfaces:**
- Consumes: `SchedulerEpoch` and `epoch_for_repetition()` from Task 1.
- Produces: `resolve_baseline_scheduler_epoch(run_dir, configured_epochs)` and rootless config schema 3 with an explicit `scheduler_epoch` label.

- [ ] **Step 1: Write failing CLI tests for pre-runtime epoch selection**

```python
def test_schema_v2_resume_builds_runtime_with_epoch_two_limits(tmp_path, monkeypatch):
    _write_schema_v2_resume(tmp_path, next_repetition=2)
    captured = {}

    def build_runtime(**kwargs):
        captured["config"] = kwargs["config"]
        return _runtime()

    monkeypatch.setattr(run_cli, "build_rootless_full_harness_runtime", build_runtime)
    assert run_cli.main(_baseline_argv(tmp_path)) == 0
    assert captured["config"].worker_concurrency == 12
    assert captured["config"].verifier_concurrency == 3
    assert captured["config"].capacity.tmpfs_mb == 40960
```

Also assert schema-v1 repetition 1 remains 4/3, a CLI concurrency override is rejected for schema v2, and a runtime scheduler digest mismatch fails before any evaluator call.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `python3 -m pytest -q tests/test_run_cli.py tests/test_rootless_full_harness.py -k 'scheduler_epoch or schema_v2_resume'`

Expected: FAIL because the rootless runtime is assembled before the resume epoch is resolved.

- [ ] **Step 3: Implement pre-runtime selection and config schema 3**

Add a strict schema-3 config field:

```json
{
  "schema_version": 3,
  "scheduler_epoch": "repetitions-02-through-05",
  "worker_concurrency": 12,
  "verifier_concurrency": 3
}
```

Keep schema 1/2 read compatibility. Include `scheduler_epoch` in the scheduler payload hashed by `build_rootless_full_harness_runtime()`, but not in model or image identity. In `_run_qfbench_rootless_baseline()`, inspect the trusted resume checkpoint before `build_rootless_full_harness_runtime()`, select the expected epoch, reject command-line overrides that differ, then pass the complete epoch tuple to `BaselineConfig`.

- [ ] **Step 4: Prove weighted admission is 12 for standard pairs and 8 for heavy pairs**

Add a deterministic pool test with capacity `(48, 98304, 8192, 40960, 24)`. Acquire twelve standard worker-plus-proxy requests `(4, 8192, 384, 2960, 2)` and reject the thirteenth; independently acquire eight heavy worker-plus-proxy requests `(6, 12288, 384, 2960, 2)` and reject the ninth. Release every lease and assert all five dimensions return to capacity.

- [ ] **Step 5: Run runtime and resource tests**

Run: `python3 -m pytest -q tests/test_run_cli.py tests/test_rootless_full_harness.py tests/test_resource_lease.py`

Expected: PASS.

- [ ] **Step 6: Commit epoch-aware runtime selection**

```bash
git add run.py qea/rootless_full_harness.py tests/test_run_cli.py tests/test_rootless_full_harness.py tests/test_resource_lease.py
git commit -m "feat(rootless): select scheduler epoch before resume"
```

---

### Task 3: Build the fail-closed repetition-boundary guard

**Files:**
- Create: `qea/qfbench_boundary.py`
- Create: `scripts/run_qfbench_boundary_guard.py`
- Create: `tests/test_qfbench_boundary.py`
- Create: `tests/test_qfbench_boundary_guard.py`

**Interfaces:**
- Produces: `BoundaryGuardConfig`, `BoundaryInventory`, `inspect_boundary()`, `freeze_boundary_manifest()`, `ProcessIdentity`, and `run_boundary_guard()`.
- Consumes: Task 1 migration, `RootlessDockerBackend.list()`, exact lifecycle manifests, `proxy-request-registry.json`, and Linux `/proc/<pid>` identity.

- [ ] **Step 1: Write failing boundary inventory tests**

```python
def test_clean_boundary_hashes_85_scores_and_has_no_rep2_evidence(tmp_path):
    run_dir = _write_rep1_boundary(tmp_path, score_count=85)
    inventory = inspect_boundary(run_dir, expected_scores=85)
    assert inventory.clean is True
    assert inventory.repetition_one_score_count == 85
    assert inventory.repetition_two_evidence == ()
    assert len(inventory.evidence_sha256) == 64


@pytest.mark.parametrize("kind", ["attempt", "registry", "lifecycle", "container", "network"])
def test_any_repetition_two_evidence_blocks_migration(tmp_path, kind):
    run_dir = _write_rep1_boundary(tmp_path, score_count=85)
    _add_rep2_evidence(run_dir, kind)
    assert inspect_boundary(run_dir, expected_scores=85).clean is False
```

The scanner may parse `attempt.json`, `completed-score.json`, lifecycle schemas, and the request registry. It may hash but never parse worker artifacts, traces, verifier logs, official tests, or reference data.

- [ ] **Step 2: Write failing PID and guard state-machine tests**

Cover command token, run ID, source commit, UID, `/proc/<pid>/stat` start ticks, process-group ID, stale PID reuse, already-stopped process, duplicate guard invocation, and both branches after `SIGSTOP`: clean migration terminates only the validated process group; discovered repetition-2 evidence preserves it stopped and writes a hard-stop record.

- [ ] **Step 3: Run boundary tests and verify RED**

Run: `python3 -m pytest -q tests/test_qfbench_boundary.py tests/test_qfbench_boundary_guard.py`

Expected: import failure for the new modules.

- [ ] **Step 4: Implement bounded evidence hashing and process identity**

```python
@dataclass(frozen=True)
class ProcessIdentity:
    pid: int
    process_group_id: int
    uid: int
    start_ticks: int
    command_sha256: str


@dataclass(frozen=True)
class BoundaryInventory:
    clean: bool
    repetition_one_score_count: int
    repetition_two_evidence: tuple[str, ...]
    active_resource_ids: tuple[str, ...]
    evidence_sha256: str
```

Use `os.open(..., O_NOFOLLOW)` and owner/mode checks for the mode-600 guard config. Parse `/proc/<pid>/stat` by splitting after the final `)` before reading field 22. Hash a sorted manifest of relative path, size, and SHA-256. Reject unknown checkpoint/panel values and symlinks.

- [ ] **Step 5: Implement Linux inotify observation and atomic migration**

Use `ctypes.CDLL(None)` bindings for `inotify_init1`, `inotify_add_watch`, and `select.poll`; watch the run directory for close-write/move events because `resume.json` is atomically replaced. Re-read and validate the exact checkpoint after each event. At the boundary, call `SIGSTOP`, revalidate `/proc` identity and all evidence, terminate the stopped legacy group with `SIGKILL`, wait until every configured PID is absent, prove zero run-owned containers/networks, freeze the manifest, and then migrate:

```python
os.killpg(identity.process_group_id, signal.SIGKILL)
migrate_v1_checkpoint(
    resume_path,
    scheduler_epochs=config.scheduler_epochs,
    boundary_manifest_sha256=manifest_sha256,
)
```

If any post-stop check fails, atomically write `boundary-hard-stop.json` and leave the exact process group stopped. Never send a signal before all configured identity fields match, and never publish schema v2 before the stopped legacy group and all run-owned resources are absent.

- [ ] **Step 6: Run tests and commit the boundary guard**

Run: `python3 -m pytest -q tests/test_qfbench_boundary.py tests/test_qfbench_boundary_guard.py tests/test_qfbench_baseline.py`

```bash
git add qea/qfbench_boundary.py scripts/run_qfbench_boundary_guard.py tests/test_qfbench_boundary.py tests/test_qfbench_boundary_guard.py
git commit -m "feat(supervisor): guard QFBench repetition boundary"
```

---

### Task 4: Add an orphan-safe process-group supervisor

**Files:**
- Create: `qea/process_supervisor.py`
- Create: `scripts/run_qfbench_process_supervisor.py`
- Create: `scripts/qfbench_exec_gate.py`
- Create: `tests/test_process_supervisor.py`
- Modify: `tests/test_qfbench_rootless_sentinel.py`

**Interfaces:**
- Produces: `SupervisorConfig`, `ChildIdentity`, `run_supervised()`, an owner-controlled pre-exec release gate, atomic `child-identity.json`, `exit-code`, `failure.log`, and `completion.json` artifacts.
- Consumes: an argv array, exact run/source identity, and a bounded supervisor directory.

- [ ] **Step 1: Write failing subprocess tests**

Create a fixture child that spawns one grandchild and records both PIDs. Test successful exit, SIGTERM forwarding, SIGINT forwarding, and a child that ignores SIGTERM until the bounded grace period expires. Also prove the pre-exec gate writes `gate-ready.json` but does not execute the coordinator argv until a mode-600 `gate-release.json` with matching run/source/command identity appears. In every terminal case assert `os.kill(pid, 0)` raises `ProcessLookupError` for child and grandchild after the supervisor returns.

- [ ] **Step 2: Run the supervisor tests and verify RED**

Run: `python3 -m pytest -q tests/test_process_supervisor.py`

Expected: import failure for `qea.process_supervisor`.

- [ ] **Step 3: Implement process-group ownership and atomic evidence**

```python
child = subprocess.Popen(
    config.argv,
    cwd=config.cwd,
    stdin=subprocess.DEVNULL,
    stdout=log_handle,
    stderr=subprocess.STDOUT,
    start_new_session=True,
    close_fds=True,
    env=config.environment,
)
pgid = os.getpgid(child.pid)
```

Install handlers that set a requested signal, forward it with `os.killpg`, wait up to the configured 30-second grace period, then use `SIGKILL` on that same validated PGID. Always `wait()` the child. `qfbench_exec_gate.py` remains in the same PID/process group across `os.execve()`, validates the release file identity, and then replaces itself with the exact coordinator argv. This allows the boundary guard and watch to bind the PID/PGID/start ticks before any repetition-1 recovery work begins. Atomically publish exit evidence. Publish `completion.json` only for exit 0 after the run's `resume.json` is phase `complete`; a clean epoch-boundary stop gets `boundary-stopped.json`, not a false completion marker.

- [ ] **Step 4: Bind sentinel schema 3 to child identity evidence**

Extend the sentinel config with `child_identity_file` and verify PID, PGID, start ticks, command digest, run ID, and source commit. A dead wrapper with a live owned child becomes `supervisor_orphan` and is a hard stop; it is never classified as an ordinary coordinator exit.

- [ ] **Step 5: Run supervisor and sentinel tests**

Run: `python3 -m pytest -q tests/test_process_supervisor.py tests/test_qfbench_rootless_sentinel.py tests/test_repair_supervisor.py`

Expected: PASS.

- [ ] **Step 6: Commit orphan-safe supervision**

```bash
git add qea/process_supervisor.py scripts/run_qfbench_process_supervisor.py scripts/qfbench_exec_gate.py tests/test_process_supervisor.py scripts/run_qfbench_rootless_sentinel.py tests/test_qfbench_rootless_sentinel.py
git commit -m "fix(supervisor): own coordinator process groups"
```

---

### Task 5: Replace quarantine-by-filename monitoring with evidence classification

**Files:**
- Create: `qea/qfbench_run_watch.py`
- Create: `scripts/run_qfbench_rootless_watch.py`
- Create: `tests/test_qfbench_run_watch.py`
- Modify: `qea/qfbench_baseline.py`
- Modify: `tests/test_qfbench_baseline.py`

**Interfaces:**
- Produces: `AttemptWatchResult`, `classify_attempt_evidence()`, `observe_run()`, and atomic `watch-state.json`/`hard-stop.json` records.
- Consumes: the existing baseline cost schema, `completed-score.json`, quarantine/audit files, worker/proxy/network lifecycle files, and supervisor child identity.

- [ ] **Step 1: Write failing classification tests for the observed timeout**

```python
def test_exact_official_timeout_is_unreconciled_cost_lower_bound(tmp_path):
    attempt = _write_timeout_attempt(
        tmp_path,
        task_id="yield-curve-bond-immunization",
        reward=0.0,
        tag="timeout",
        reason="audit_download_or_validation_failed",
        cleaned=True,
    )
    result = classify_attempt_evidence(attempt)
    assert result.status == "timeout_cost_lower_bound"
    assert result.hard_stop is False
```

Add fatal cases for reward nonzero, missing timeout tag, unsupported marker reason, malformed schema, canonical ledger plus marker, unclean lifecycle, `downstream_delivery`, `post_accept_transport`, HTTP-200 quarantine, and within-attempt duplicate request identity.

- [ ] **Step 2: Run watch tests and verify RED**

Run: `python3 -m pytest -q tests/test_qfbench_run_watch.py tests/test_qfbench_baseline.py -k 'timeout or quarantine'`

Expected: import failure for the new watch module.

- [ ] **Step 3: Extract one shared timeout validator and implement run observation**

Move the exact timeout predicate from `_validated_timeout_quarantine()` into a side-effect-free shared function. Keep `audit_baseline_proxy_costs()` behavior unchanged. `observe_run()` scans only bounded, owner-controlled metadata; it writes the count and relative paths of lower-bound attempts but no prompt, response, test, reference, key, or artifact content.

- [ ] **Step 4: Implement watch hard-stop against the supervised PGID**

`run_qfbench_rootless_watch.py` loads a mode-600 exact config, verifies `child-identity.json`, polls file events, and calls `os.killpg(validated_pgid, SIGTERM)` only when `observe_run().hard_stop` is true. The hard-stop record includes category, evidence hash, source commit, run ID, and timestamp. It must never signal only the shell wrapper PID.

- [ ] **Step 5: Run focused suites and commit**

Run: `python3 -m pytest -q tests/test_qfbench_run_watch.py tests/test_qfbench_baseline.py tests/test_model_proxy.py tests/test_sandbox_proxy.py`

```bash
git add qea/qfbench_run_watch.py scripts/run_qfbench_rootless_watch.py tests/test_qfbench_run_watch.py qea/qfbench_baseline.py tests/test_qfbench_baseline.py
git commit -m "fix(watch): classify official timeout evidence"
```

---

### Task 6: Add a 12-task paid baseline concurrency canary

**Files:**
- Modify: `scripts/smoke_qfbench_full_harness.py`
- Modify: `tests/test_qfbench_full_harness_scripts.py`
- Create: `qea/qfbench_epoch_report.py`
- Create: `tests/test_qfbench_epoch_report.py`

**Interfaces:**
- Produces: `paid-baseline-batch` canary mode, `max_worker_overlap()`, `summarize_scheduler_epochs()`, and a canary `run_status.json` containing route, concurrency, latency, accounting, cleanup, and firewall assertions.
- Consumes: the production rootless evaluator, immutable seed worker, twelve explicitly selected standard tasks, canonical proxy audits, and lifecycle timestamps.

- [ ] **Step 1: Write failing canary CLI and overlap tests**

Assert the new mode requires exactly these twelve unique primary tasks: `historical-var-data-prep`, `momentum-backtest`, `evt-pot-var`, `fx-forward-cross-rate`, `option-put-call-parity-forward-audit`, `sma-crossover-spy`, `corporate-action-adjustment`, `earnings-surprise-calculator`, `fama-french-factor-model-new`, `credit-migration-matrix`, `zero-coupon-bootstrapping`, and `copula-sampling-rank-correlation`. Require every selected catalog entry to have a 2-CPU/4,096-MiB worker contract before spending. Also require rootless executor, external-run approval, schema-3 epoch-2 config, worker concurrency 12, verifier concurrency 3, and no feedback/evolver inputs. Build twelve synthetic worker lifecycle intervals with a twelve-way overlap and assert `max_worker_overlap(...) == 12`; a peak of eleven fails the canary.

- [ ] **Step 2: Run the tests and verify RED**

Run: `python3 -m pytest -q tests/test_qfbench_full_harness_scripts.py tests/test_qfbench_epoch_report.py -k 'baseline_batch or overlap'`

Expected: parser rejection because `paid-baseline-batch` is not yet defined.

- [ ] **Step 3: Implement a baseline-only batch path**

The new path snapshots `qea/worker_gdpval_weak`, creates one content-addressed attempt per selected task with checkpoint `epoch-02-concurrency-canary`, and calls `runtime.evaluator.evaluate()` once over all twelve tasks. It must not instantiate or import an evolver. After evaluation, call the canonical cost auditor, exact-ID reaper, provider-route check, no-network verifier checks, and lifecycle overlap summarizer.

```python
summary = runtime.evaluator.evaluate(
    worker_dir=seed_worker,
    tasks=selected_tasks,
    split="baseline_primary",
    checkpoint="epoch-02-concurrency-canary",
    run_dir=run_dir,
)
```

- [ ] **Step 4: Implement epoch-aware reporting**

`summarize_scheduler_epochs()` returns separate repetition-1 and repetition-2-through-5 score, provider latency, request count, timeout count, cost, and wall-time summaries plus the combined five-repeat aggregate. It includes `scheduler_epoch_batch_effect_warning: true`; it never rewrites official rewards or calls an LLM judge.

- [ ] **Step 5: Run canary/report tests and commit**

Run: `python3 -m pytest -q tests/test_qfbench_full_harness_scripts.py tests/test_qfbench_epoch_report.py tests/test_rootless_runtime.py`

```bash
git add scripts/smoke_qfbench_full_harness.py tests/test_qfbench_full_harness_scripts.py qea/qfbench_epoch_report.py tests/test_qfbench_epoch_report.py
git commit -m "feat(canary): exercise twelve rootless workers"
```

---

### Task 7: Verify locally and record the superseding operational decision

**Files:**
- Modify: `docs/PROJECT_MEMORY.md` with one isolated hunk
- Create: `docs/decisions/2026-08-03-qfbench-scheduler-epoch-transition.md`
- Modify: `docs/runbooks/qfbench-rootless-docker-vm.md` only in the epoch-transition section

**Interfaces:**
- Consumes: Tasks 1–6 and the approved design.
- Produces: exact local verification evidence and an auditable deployment/runbook record.

- [ ] **Step 1: Run focused suites**

Run:

```bash
python3 -m pytest -q tests/test_qfbench_scheduler_epochs.py tests/test_qfbench_baseline.py tests/test_run_cli.py tests/test_rootless_full_harness.py tests/test_resource_lease.py tests/test_qfbench_boundary.py tests/test_qfbench_boundary_guard.py tests/test_process_supervisor.py tests/test_qfbench_run_watch.py tests/test_qfbench_rootless_sentinel.py tests/test_repair_supervisor.py tests/test_qfbench_full_harness_scripts.py tests/test_qfbench_epoch_report.py
```

- [ ] **Step 2: Run broader safety and full suites**

Run:

```bash
python3 -m pytest -q tests/test_model_proxy.py tests/test_sandbox_proxy.py tests/test_sandbox_reaper.py tests/test_rootless_runtime.py tests/test_qfbench_isolation.py
python3 -m pytest -q tests
git diff --check
```

Expected: all tests pass or only repository-declared optional-dependency skips occur; no warnings may be reclassified as a pass without inspection.

- [ ] **Step 3: Write the decision and memory update**

Record the two scheduler identities, boundary manifest schema, fixed run/model/provider/image/task identities, exact resource capacity, timeout lower-bound rule, process-group supervisor behavior, canary identity, test counts, and the fact that mixed scheduler epochs may introduce a batch effect. Preserve dated reports and old hard-stop evidence.

- [ ] **Step 4: Stage only owned documentation changes and commit**

```bash
git add docs/decisions/2026-08-03-qfbench-scheduler-epoch-transition.md
git diff --cached --name-only
git commit -m "docs: record QFBench scheduler epoch transition"
```

Use patch staging to add only the new epoch-transition hunks from `docs/PROJECT_MEMORY.md` and `docs/runbooks/qfbench-rootless-docker-vm.md` before the documentation commit; do not stage their unrelated pre-existing hunks. The implementation plan is already committed before execution. Do not merge.

---

### Task 8: Deploy the exact commit, guard the boundary, canary, and resume epoch 2

**Files:**
- Remote owner-only runtime files under `/home/julius/qea/runtime/`
- Remote immutable release under `/home/julius/qea/deploy/releases/$QEA_EPOCH_COMMIT/`, where `QEA_EPOCH_COMMIT` is the tested 40-character Git SHA.
- Remote run evidence under `/home/julius/qea/runs/qfbench-rootless-base-85x5-official-deepseek-v4-flash-noreplay-recovery2-20260803/`
- Local controller state under the existing run-scoped Mac controller directory

**Interfaces:**
- Consumes: the exact tested Git commit from Task 7.
- Produces: exact completion of the three currently missing epoch-1 diagnostic scores, one frozen epoch-1 boundary, one 12-task canary, an epoch-2 supervised resume, new systemd/watch/sentinel generations, and continuous Mac monitoring.

- [ ] **Step 1: Re-read the live boundary before any deployment mutation**

Read `resume.json`, all repetition-tagged attempts, `proxy-request-registry.json`, lifecycle/network manifests, Docker labels, coordinator PID/PGID/start ticks, and supervisor state. The 2026-08-03 planning snapshot was schema 1, repetition-1 diagnostic, `pending_primary=true`, 82 score files, no coordinator process, no run-owned container/network, and zero repetition-2 attempts. Re-derive those values rather than trusting the snapshot. If repetition 2 evidence exists, do not migrate or resample; publish the hard-stop disposition and stop this task. If the run remains at 82/85, require a clean exact-ID reaper dry-run and identify the three unfinished diagnostic attempts before recovery.

- [ ] **Step 2: Deploy the exact tested commit and epoch-2 config**

Set `QEA_EPOCH_COMMIT` to the output of `git rev-parse HEAD`, require it to match `^[0-9a-f]{40}$`, push the feature branch without merging, fetch that exact SHA into the bc bare repository, and materialize `/home/julius/qea/deploy/releases/$QEA_EPOCH_COMMIT`. Write two mode-600 configs: an epoch-1 recovery config that preserves the existing schema-2 runtime contract, capacity `48/98304/8192/32768/24`, headroom `56/16384`, and concurrency `4/3`; and an epoch-2 schema-3 config with capacity `48/98304/8192/40960/24`, the same headroom, and concurrency `12/3`. Preserve model/provider/fallback/image/task/token-file identities in both.

- [ ] **Step 3: Start a gated epoch-1 recovery with the boundary guard already attached**

Launch the exact schema-v1 resume command at concurrency 4/3 through the process supervisor and pre-exec gate. It must reuse all 82 terminal scores and completed request identities; it may execute only the three unfinished diagnostic attempts. Before releasing the gate, bind the guard and watch to the exact child PID, PGID, start ticks, expected post-exec command digest, run ID, source commit, and expected 85 scores. Run one dry observation for each, start them as user systemd services, confirm their inotify watches are active, and only then publish the matching release file. The guard must stop the coordinator at the first schema-v1 checkpoint with completed repetition 1, `next_repetition=2`, `phase=primary`, and no repetition-2 evidence.

- [ ] **Step 4: Audit the frozen boundary**

After the guard stops the recovered epoch-1 coordinator, require: schema-v2 checkpoint, completed repetition 1, `next_repetition=2`, `phase=primary`, null pending primary, exactly 85 terminal scores, exactly three new score files relative to the frozen 82-score snapshot, no changed hash for the prior 82 scores or their completed ledgers, zero repetition-2 evidence, matching frozen hashes, zero run-owned containers/networks, and a clean exact-ID reaper dry-run. Preserve the old false hard-stop record unchanged.

- [ ] **Step 5: Run no-model and paid 12-task canaries**

Run the existing rootless import canary first. Then run `paid-baseline-batch` with twelve preregistered standard tasks and require measured worker overlap 12, provider `deepseek`, model `deepseek/deepseek-v4-flash`, fallbacks false, no 429, no replay, no ambiguous acceptance, complete successful accounting, offline verifier evidence, firewall pass, and zero residual resources. Failure blocks formal resume.

- [ ] **Step 6: Install new supervisor/watch/sentinel generations**

Create run-scoped user systemd units for the process supervisor, watch, and sentinel using owner-only configs and state directories. Run every component once manually before enabling it. Update the Mac controller config to the new incident state and resume command, run one dry poll, then keep it alive under `/usr/bin/caffeinate -i`. Confirm the old red units are disabled but their state is preserved.

- [ ] **Step 7: Resume repetitions 2–5 and monitor continuously**

Launch the exact epoch-2 command through `run_qfbench_process_supervisor.py`. Immediately verify the active scheduler digest, runtime digest, source commit, provider route, PID/PGID identity, first attempt identity, and first proxy record. Monitor checkpoint progress, active workers, host headroom, model latency, cost lower bounds, verifier isolation, replays, accepted-delivery ambiguity, and exact resource cleanup. Autonomous repair remains limited to allowlisted infrastructure categories.

- [ ] **Step 8: Perform final five-repeat audit**

Require phase `complete`, five completed repetitions, 425 terminal scores, no duplicate within-attempt request identity, complete or explicitly lower-bound cost accounting, zero residual containers/networks/leases, and a passing firewall scan. Generate per-epoch and combined summaries with the scheduler batch-effect warning. Stop the run-scoped Mac/controller/sentinel/watch units only after final evidence is durable.
