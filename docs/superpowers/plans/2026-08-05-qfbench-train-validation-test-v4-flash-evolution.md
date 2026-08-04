# QFBench Train/Validation/Test V4 Flash Evolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and launch a ten-iteration, full-harness QFBench evolution that uses 30 feedback-visible train tasks, 15 per-iteration blind validation tasks, and 40 seed/final-only test tasks.

**Architecture:** Add a versioned four-way QFBench experiment manifest and a protocol object beside the legacy optimize/held-out pilot. Extend the benchmark loop with a schema-v3 train/validation/test state machine while preserving schema-v2 legacy resume behavior. Bind baseline-derived validation tolerance, provider identity, scheduler tier, and all split digests into immutable run identity; keep validation/test material outside the evolver evidence boundary.

**Tech Stack:** Python 3.10+, standard-library dataclasses/JSON/threading, pytest, rootless Docker, OpenRouter official DeepSeek provider, systemd user services, macOS LaunchAgent and `caffeinate`.

## Global Constraints

- Use QFBench commit `024921eb507fcc0c4ffe3e0a96802724be1ae84a` and exclude inoperable `sec-8k-event-alpha`.
- Train 30 tasks; validation 15 tasks at seed and all ten iterations; test 32 plus diagnostic 8 tasks at seed/final only; exactly 575 official scoring attempts.
- Use `deepseek/deepseek-v4-flash-0731`, required provider `DeepSeek`, and no fallback.
- Official tests and reference data remain verifier-only and offline; official solutions are never uploaded or run.
- Validation/test identities, scores, artifacts, and verifier evidence never reach proposer inputs. Only the resulting keep/rollback event may be observed.
- Select the highest accepted scheduler tier from `20/3`, `16/3`, `12/3`; freeze it for the run and use a new scheduler epoch for any later downshift.
- Do not merge. Preserve pre-existing dirty documentation and generated files. Mirror exact-run evidence additively with no `--delete`.

---

### Task 1: Add the preregistered four-way task manifest

**Files:**
- Create: `data/qfbench/MANIFEST_30_15_40_EVOLUTION.json`
- Modify: `qea/benchmarks/qfbench.py`
- Test: `tests/test_qfbench_train_validation_test_contract.py`

**Interfaces:**
- Consumes: existing `QFBenchTask`, `_load_split()`, pinned baseline manifest metadata.
- Produces: `QFBenchEvolutionSnapshot` and `load_qfbench_evolution_snapshot(root, *, manifest_path)` with `.train`, `.validation`, `.test`, `.diagnostic`, and `.tasks`.

- [ ] **Step 1: Write the failing manifest/loader tests**

```python
def test_evolution_manifest_has_exact_disjoint_panels(qfbench_checkout):
    snapshot = load_qfbench_evolution_snapshot(
        qfbench_checkout,
        manifest_path="data/qfbench/MANIFEST_30_15_40_EVOLUTION.json",
    )
    assert tuple(map(len, (
        snapshot.train.tasks,
        snapshot.validation.tasks,
        snapshot.test.tasks,
        snapshot.diagnostic.tasks,
    )) == (30, 15, 32, 8)
    panels = [set(split.task_ids) for split in (
        snapshot.train, snapshot.validation, snapshot.test, snapshot.diagnostic
    )]
    assert not any(left & right for i, left in enumerate(panels) for right in panels[i + 1:])
    assert set(snapshot.diagnostic.task_ids) == set(snapshot.copy_oracle_tasks)
    assert "sec-8k-event-alpha" in snapshot.inoperable_tasks
```

- [ ] **Step 2: Run the contract test and verify RED**

Run: `python3 -m pytest -q tests/test_qfbench_train_validation_test_contract.py`

Expected: collection/import failure because the loader and manifest do not exist.

- [ ] **Step 3: Implement the manifest and strict loader**

Use schema version 2 with keys `train`, `validation`, `test`, and `diagnostic`. Reuse the complete task entries from `MANIFEST_85_BASELINE.json`, validate exact commit, unique IDs and lineages across all four panels, reject cross-panel public-input hash overlap, require diagnostic equality with `copy_oracle_tasks`, and reject copy-oracle membership in the other three panels.

```python
@dataclass(frozen=True)
class QFBenchEvolutionSnapshot:
    root: Path
    repository_url: str
    commit: str
    train: QFBenchSplit
    validation: QFBenchSplit
    test: QFBenchSplit
    diagnostic: QFBenchSplit
    copy_oracle_tasks: frozenset[str]
    inoperable_tasks: frozenset[str]

    @property
    def tasks(self) -> tuple[QFBenchTask, ...]:
        return (
            self.train.tasks + self.validation.tasks
            + self.test.tasks + self.diagnostic.tasks
        )
```

- [ ] **Step 4: Run focused and legacy adapter tests**

Run: `python3 -m pytest -q tests/test_qfbench_train_validation_test_contract.py tests/test_qfbench_adapter.py tests/test_qfbench_baseline_manifest.py`

Expected: PASS, including unchanged legacy schema-v1 loaders.

- [ ] **Step 5: Commit the manifest contract**

```bash
git add data/qfbench/MANIFEST_30_15_40_EVOLUTION.json qea/benchmarks/qfbench.py tests/test_qfbench_train_validation_test_contract.py
git commit -m "feat(qfbench): preregister train validation test panels"
```

### Task 2: Expand rich train feedback to all 30 train tasks

**Files:**
- Create: `data/qfbench/FEEDBACK_TRAIN_30.json`
- Create: `data/qfbench/VERIFIER_CRITERIA_TRAIN_30.json`
- Modify: `tests/test_qfbench_feedback_contract.py`

**Interfaces:**
- Consumes: `load_feedback_manifest()`, `load_verifier_mapping()`, public instructions/rubrics for the ten newly selected train tasks.
- Produces: complete answer-free public feedback and verifier-to-public-criterion maps for exactly the train panel.

- [ ] **Step 1: Add a failing exact-coverage and forbidden-panel test**

```python
def test_train30_feedback_covers_only_train_panel(qfbench_evolution_snapshot):
    forbidden = set(
        qfbench_evolution_snapshot.validation.task_ids
        + qfbench_evolution_snapshot.test.task_ids
        + qfbench_evolution_snapshot.diagnostic.task_ids
    )
    feedback = load_feedback_manifest(
        "data/qfbench/FEEDBACK_TRAIN_30.json",
        expected_task_ids=set(qfbench_evolution_snapshot.train.task_ids),
        forbidden_task_ids=forbidden,
    )
    mapping = load_verifier_mapping(
        "data/qfbench/VERIFIER_CRITERIA_TRAIN_30.json",
        public_criteria={
            task_id: {criterion.criterion_id for criterion in rubric.criteria}
            for task_id, rubric in feedback.items()
        },
    )
    assert set(feedback) == set(qfbench_evolution_snapshot.train.task_ids)
    assert set(mapping) == set(feedback)
```

- [ ] **Step 2: Run the test and verify RED**

Run: `python3 -m pytest -q tests/test_qfbench_feedback_contract.py -k train30`

Expected: FAIL because both versioned manifests are absent.

- [ ] **Step 3: Materialize answer-free criteria and mappings**

Copy the existing twenty train entries byte-for-byte from `FEEDBACK_30.json` and `VERIFIER_CRITERIA_30.json`. Derive the ten new public criteria from their public instructions/rubrics only. Map verifier check IDs to public criterion IDs without copying test assertions, reference values, raw verdicts, or solution text into the public manifest.

- [ ] **Step 4: Run feedback firewall tests**

Run: `python3 -m pytest -q tests/test_qfbench_feedback_contract.py tests/test_evolution_feedback.py tests/test_evolution_evidence.py`

Expected: PASS with exact train-only coverage.

- [ ] **Step 5: Commit the train feedback contract**

```bash
git add data/qfbench/FEEDBACK_TRAIN_30.json data/qfbench/VERIFIER_CRITERIA_TRAIN_30.json tests/test_qfbench_feedback_contract.py
git commit -m "feat(qfbench): extend rich feedback to train panel"
```

### Task 3: Calibrate and bind the blind validation tolerance

**Files:**
- Create: `qea/qfbench_validation.py`
- Create: `scripts/calibrate_qfbench_validation.py`
- Test: `tests/test_qfbench_validation.py`

**Interfaces:**
- Consumes: exact completed baseline `result.json`/attempt tree and the fixed validation task IDs.
- Produces: `ValidationCalibration`, `calibrate_validation_tolerance(...)`, and an immutable JSON artifact with source run ID, five domain-macro values, formula version `max-absolute-deviation-floor-v1`, floor `0.02`, tolerance, and SHA-256 digest.

- [ ] **Step 1: Write failing unit and reconciliation tests**

```python
def test_calibration_uses_max_absolute_deviation_with_floor():
    calibration = calibrate_validation_tolerance(
        run_id="base-85x5",
        repetition_scores=(0.40, 0.42, 0.38, 0.41, 0.39),
        validation_task_ids=("v1", "v2"),
    )
    assert calibration.mean_score == pytest.approx(0.40)
    assert calibration.tolerance == pytest.approx(0.02)
    assert len(calibration.digest) == 64

def test_calibration_rejects_missing_or_nonfive_repetitions(tmp_path):
    with pytest.raises(ValidationCalibrationError, match="exactly five"):
        calibration_from_baseline_run(tmp_path, validation_tasks=("v1",))
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `python3 -m pytest -q tests/test_qfbench_validation.py`

Expected: import failure for `qea.qfbench_validation`.

- [ ] **Step 3: Implement fail-closed calibration**

Reconcile each selected task against one completed score per repetition and aggregate domain macros with the repository’s existing `aggregate_domain_macro()`. Reject duplicate/missing attempts, non-complete baseline state, task/domain mismatch, provider replay findings, and a source run ID other than the CLI-declared exact ID. Serialize with sorted keys and hash the canonical JSON excluding the digest field.

- [ ] **Step 4: Run calibration and baseline audit tests**

Run: `python3 -m pytest -q tests/test_qfbench_validation.py tests/test_qfbench_baseline.py`

Expected: PASS.

- [ ] **Step 5: Commit calibration support**

```bash
git add qea/qfbench_validation.py scripts/calibrate_qfbench_validation.py tests/test_qfbench_validation.py
git commit -m "feat(qfbench): calibrate blind validation tolerance"
```

### Task 4: Implement the schema-v3 train/validation/test evolution state machine

**Files:**
- Modify: `qea/loop_benchmark.py`
- Modify: `qea/evolution_evidence.py`
- Modify: `tests/test_qfbench_evolution.py`
- Modify: `tests/test_evolution_evidence.py`

**Interfaces:**
- Consumes: `ValidationCalibration`, four task tuples, existing evaluator/proposer/admission interfaces.
- Produces: `run_benchmark_evolution(..., validation_tasks=..., test_tasks=..., diagnostic_tasks=...)`, validation-aware `BenchmarkIterationRecord`, and result fields `validation_seed`, `validation_final`, `test_seed`, `test_final`, `diagnostic_seed`, `diagnostic_final`.

- [ ] **Step 1: Add failing schedule and keep/rollback tests**

```python
def test_tvt_schedule_scores_validation_each_iteration_and_test_seed_final(tmp_path):
    result = run_benchmark_evolution(
        _config(tmp_path, n_iters=10, validation_noise_tolerance=0.02),
        optimize_tasks=train,
        validation_tasks=validation,
        test_tasks=test,
        diagnostic_tasks=diagnostic,
        benchmark_commit="a" * 40,
        evaluator=evaluator,
        proposer=proposer,
    )
    assert evaluator.checkpoints("validation") == [
        "seed-validation", *[f"iteration-{i}-validation" for i in range(1, 11)]
    ]
    assert evaluator.checkpoints("test") == ["seed-test", "final-test"]
    assert evaluator.checkpoints("diagnostic") == [
        "seed-diagnostic", "final-diagnostic"
    ]
    assert len(evaluator.scored_tasks) == 575

def test_train_gain_rolls_back_when_blind_validation_exceeds_tolerance(tmp_path):
    result = run_case(train=(0.4, 0.6), validation=(0.5, 0.47), tolerance=0.02)
    assert result.records[0].kept is False
    assert result.records[0].reason == "confirm_failed"
    assert result.records[0].validation_overall is None
```

- [ ] **Step 2: Add failing non-leakage/resume tests**

Assert proposer context/history/evidence contains none of the 55 forbidden task IDs or validation/test score values. Assert schema-v3 resume rejects changes to calibration digest, tolerance, any split digest, scheduler identity, model identity, or feedback identity. Assert schema-v2 legacy runs retain optimize/held-out semantics.

- [ ] **Step 3: Run focused tests and verify RED**

Run: `python3 -m pytest -q tests/test_qfbench_evolution.py tests/test_evolution_evidence.py -k 'validation or test_schedule or schema_v3 or forbidden_panel'`

Expected: failures for unsupported `n_iters=10`, new arguments, schedule, and result fields.

- [ ] **Step 4: Implement schema-v3 scheduling and blind selection**

Allow iteration counts `{1, 3, 5, 10}`. Validate all four panels as non-empty, internally unique, and pairwise ID/lineage disjoint. Score seed train, seed validation, seed test, seed diagnostic; score candidate train then candidate validation at every admitted iteration, including no-op/repeated edits; score final test and diagnostic only after iteration ten.

```python
train_kept, train_reason, train_deltas = _accept_candidate(
    incumbent_train, candidate_train, config
)
confirm_kept = (
    candidate_validation.overall
    >= incumbent_validation.overall - config.validation_noise_tolerance
)
kept = train_kept and confirm_kept
reason = train_reason if not train_kept else (
    "train_gate_passed" if confirm_kept else "confirm_failed"
)
```

Persist full validation summaries only in trusted coordinator state/result. Store `validation_overall=None` and the generic reason in proposer-visible history. Extend evidence construction to accept `forbidden_task_ids` containing validation, test, and diagnostic IDs, rejecting any match in attempt metadata, history text, evidence members, or public feedback.

- [ ] **Step 5: Run new and legacy evolution suites**

Run: `python3 -m pytest -q tests/test_qfbench_evolution.py tests/test_qfbench_feedback_ab.py tests/test_evolution_evidence.py tests/test_levelb_resume.py`

Expected: PASS for schema-v3 and unchanged legacy behavior.

- [ ] **Step 6: Commit the state machine**

```bash
git add qea/loop_benchmark.py qea/evolution_evidence.py tests/test_qfbench_evolution.py tests/test_evolution_evidence.py
git commit -m "feat(qfbench): add blind validation evolution gate"
```

### Task 5: Wire the protocol into the rootless CLI and result output

**Files:**
- Modify: `run.py`
- Modify: `tests/test_run_cli.py`
- Create: `tests/test_qfbench_tvt_cli.py`

**Interfaces:**
- Consumes: four-way snapshot loader, calibration JSON, rootless runtime factory.
- Produces: CLI flags `--validation-calibration` and schema-v2 manifest auto-detection; exact 575-attempt plan and protocol-aware printed result.

- [ ] **Step 1: Write failing CLI plan tests**

```python
def test_tvt_attempt_accounting_and_ten_iterations():
    assert estimate_qfbench_tvt_attempts(30, 15, 40, 10) == 575
    args = build_parser().parse_args([
        "--benchmark", "qfbench", "--executor", "rootless-docker",
        "--iters", "10", "--qfbench-manifest",
        "data/qfbench/MANIFEST_30_15_40_EVOLUTION.json",
        "--validation-calibration", "calibration.json",
    ])
    assert resolve_iterations(args) == 10
```

- [ ] **Step 2: Run CLI tests and verify RED**

Run: `python3 -m pytest -q tests/test_run_cli.py tests/test_qfbench_tvt_cli.py`

Expected: parser rejects `--validation-calibration` and iteration ten.

- [ ] **Step 3: Implement protocol-aware preparation and launch**

Detect manifest schema before loading. For schema 2 require calibration JSON, verify its exact source run ID/digest/task panel, pass all four task tuples to the loop, forbid all non-train IDs in `AdmissionPolicy.qfbench_full()`, and print train/validation/test counts, scheduler identity, tolerance/provenance, model/provider, 575 attempts, and 1,150 maximum worker/verifier lifecycles.

- [ ] **Step 4: Run CLI, boundary, and full-harness tests**

Run: `python3 -m pytest -q tests/test_run_cli.py tests/test_qfbench_tvt_cli.py tests/test_qfbench_boundary.py tests/test_rootless_full_harness.py`

Expected: PASS.

- [ ] **Step 5: Commit CLI integration**

```bash
git add run.py tests/test_run_cli.py tests/test_qfbench_tvt_cli.py
git commit -m "feat(qfbench): launch train-validation-test evolution"
```

### Task 6: Replace healthy lease expiry with bounded queueing

**Files:**
- Modify: `qea/rootless_full_harness.py`
- Modify: `qea/rootless_runtime.py`
- Modify: `tests/test_rootless_full_harness.py`
- Modify: `tests/test_rootless_runtime.py`

**Interfaces:**
- Consumes: `HostResourceLeasePool.acquire(request, key, timeout_seconds)`.
- Produces: rootless config schema 5 field `lease_timeout_seconds`; value bound into scheduler/runtime identity and used consistently by worker, verifier, and evolver routers.

- [ ] **Step 1: Add failing schema/identity/queue tests**

```python
def test_schema5_binds_lease_timeout_to_scheduler_identity(tmp_path):
    short = load_config(write_config(tmp_path, schema_version=5, lease_timeout_seconds=120))
    queued = load_config(write_config(tmp_path, schema_version=5, lease_timeout_seconds=6000))
    assert scheduler_identity(short) != scheduler_identity(queued)

def test_waiting_worker_acquires_after_prior_lease_releases(resource_pool):
    first = resource_pool.acquire(large_request, key="first", timeout_seconds=1)
    future = executor.submit(resource_pool.acquire, large_request, key="second", timeout_seconds=2)
    first.release()
    assert future.result(timeout=2).key == "second"
```

- [ ] **Step 2: Run lease tests and verify RED**

Run: `python3 -m pytest -q tests/test_rootless_full_harness.py tests/test_rootless_runtime.py -k lease_timeout`

Expected: schema 5 and routed timeout assertions fail.

- [ ] **Step 3: Implement schema 5 and routed queue timeout**

Require an integer `lease_timeout_seconds` from 120 through 7,200. Formal config uses 6,000 seconds so a queued thread can wait behind a valid long task without being treated as an infrastructure failure. Preserve host-health checks during each lease attempt; an unhealthy host still fails closed immediately through the existing headroom policy.

- [ ] **Step 4: Run rootless resource and safety tests**

Run: `python3 -m pytest -q tests/test_resource_lease.py tests/test_rootless_runtime.py tests/test_rootless_full_harness.py`

Expected: PASS, including cancellation and lease release on worker/verifier failures.

- [ ] **Step 5: Commit queued lease support**

```bash
git add qea/rootless_full_harness.py qea/rootless_runtime.py tests/test_rootless_full_harness.py tests/test_rootless_runtime.py
git commit -m "fix(rootless): queue healthy resource lease contention"
```

### Task 7: Add concurrency-tier acceptance and evolution completion audit

**Files:**
- Create: `scripts/accept_qfbench_evolution_tier.py`
- Create: `scripts/audit_qfbench_tvt_evolution.py`
- Create: `tests/test_qfbench_evolution_operations.py`

**Interfaces:**
- Consumes: rootless canary result, Docker lifecycle logs, host samples, schema-v3 result/resume, calibration artifact.
- Produces: signed-by-digest `tier-acceptance.json` and `evolution-audit.json`; exit zero only when all preregistered gates reconcile.

- [ ] **Step 1: Write failing acceptance/audit tests**

```python
def test_tier_acceptance_selects_highest_observed_safe_tier(tmp_path):
    accepted = accept_tiers([
        panel(20, overlap=18, clean=True),
        panel(16, overlap=16, clean=True, available_memory_mb=18000),
        panel(12, overlap=12, clean=True),
    ])
    assert accepted.worker_concurrency == 16
    assert accepted.verifier_concurrency == 3

def test_complete_audit_reconciles_575_and_separates_diagnostic(tmp_path):
    audit = audit_run(complete_run_fixture(tmp_path))
    assert audit["attempts"]["total"] == 575
    assert audit["primary_test"]["task_count"] == 32
    assert audit["diagnostic_test"]["task_count"] == 8
    assert audit["firewall"]["passed"] is True
```

- [ ] **Step 2: Run operational tests and verify RED**

Run: `python3 -m pytest -q tests/test_qfbench_evolution_operations.py`

Expected: imports fail for both new scripts.

- [ ] **Step 3: Implement fail-closed tier and final audits**

Tier acceptance requires exact formal model/provider/fallback, observed overlap equal to configured workers, no lease/provider/replay/coordinator failure, verifier offline, memory at least 16,384 MiB, safe sampled load, and zero residual resources. Try inputs in 20/3, 16/3, 12/3 order and select the first passing panel.

Final audit reconciles checkpoint counts `(30, 15, 40) + 10*(30, 15) + 40`, unique logical attempt IDs, completed official scores, provider identity, no replay, verifier firewall, calibration digest, scheduler epoch, keep/rollback sequence, exact mirror count, and separate 32/8 test aggregates.

- [ ] **Step 4: Run operational and existing watchdog tests**

Run: `python3 -m pytest -q tests/test_qfbench_evolution_operations.py tests/test_qfbench_run_watch.py tests/test_qfbench_rootless_sentinel.py tests/test_qfbench_repair_controller.py`

Expected: PASS.

- [ ] **Step 5: Commit operational gates**

```bash
git add scripts/accept_qfbench_evolution_tier.py scripts/audit_qfbench_tvt_evolution.py tests/test_qfbench_evolution_operations.py
git commit -m "feat(qfbench): audit evolution scheduler and test outcome"
```

### Task 8: Verify, deploy the exact commit, and select a scheduler tier

**Files:**
- Create locally during execution: `/tmp/qfbench-tvt-deploy-manifest.json`
- Create remotely under the exact release: `/home/julius/qea/deploy/releases/<sha>/runtime/config/evolution-<tier>.json`
- Create remotely per canary: `/home/julius/qea/results/<canary-run-id>/tier-acceptance.json`

**Interfaces:**
- Consumes: committed source, rootless images, trusted/public task roots, token file, completed baseline.
- Produces: exact deployed release SHA, validation calibration artifact, and one accepted frozen tier.

- [ ] **Step 1: Run complete local verification**

```bash
python3 -m pytest -q tests/test_qfbench_train_validation_test_contract.py tests/test_qfbench_feedback_contract.py tests/test_qfbench_validation.py tests/test_qfbench_evolution.py tests/test_evolution_evidence.py tests/test_qfbench_tvt_cli.py tests/test_rootless_runtime.py tests/test_rootless_full_harness.py tests/test_qfbench_evolution_operations.py
python3 -m pytest -q tests
git diff --check
```

Expected: all tests pass; only the five pre-existing dirty docs remain outside implementation commits.

- [ ] **Step 2: Commit verification-owned changes and push without merging**

```bash
git status --short
git push origin qfbench-selfhosted-vm-backend
```

Record exact local and remote `git rev-parse HEAD`; require equality before launch.

- [ ] **Step 3: Wait for and audit the current baseline completion**

Require run `qfbench-rootless-base-85x5-official-deepseek-v4-flash-0731-all12x3-20260804` to show 425/425, repetitions 1-5 complete, official DeepSeek/no-fallback/no-replay audit, clean exact-ID dry reaper, zero residual resources, and an additive Mac mirror with all 425 score artifacts.

- [ ] **Step 4: Generate the calibration artifact from the audited baseline**

```bash
python3 scripts/calibrate_qfbench_validation.py \
  --run-dir /home/julius/qea/results/qfbench-rootless-base-85x5-official-deepseek-v4-flash-0731-all12x3-20260804 \
  --manifest data/qfbench/MANIFEST_30_15_40_EVOLUTION.json \
  --output /home/julius/qea/runtime/config/validation-calibration-v1.json
```

Require the declared source run, five values, scalar tolerance, and digest in the launch manifest.

- [ ] **Step 5: Run the descending paid tier ladder**

For each tier, use a unique exact run ID, the formal V4 Flash route, representative standard and heavy tasks, verifier network disabled, and schema-5 lease timeout 6,000. Run `20/3`; if it fails any acceptance condition, exact-ID reap and run `16/3`; if that fails, run `12/3`. Stop at the first passing tier and persist the accepted artifact.

- [ ] **Step 6: Verify exact cleanup and deployment evidence**

Run the exact-ID reaper in dry-run then execute mode only for completed canaries. Require no containers/networks labeled with any canary run ID and copy all non-secret canary/calibration artifacts additively to the Mac.

### Task 9: Launch and monitor the ten-iteration formal evolution

**Files:**
- Create remotely: `/home/julius/.config/systemd/user/qea-qfbench-tvt-evolution.service`
- Create remotely: `/home/julius/.config/systemd/user/qea-qfbench-tvt-evolution-sentinel.service`
- Create remotely: `/home/julius/.config/systemd/user/qea-qfbench-tvt-evolution-sentinel.timer`
- Create locally: `~/Library/LaunchAgents/com.qea.qfbench-tvt-evolution-repair.plist`
- Create locally and remotely: exact-run non-secret monitoring/mirror configuration.

**Interfaces:**
- Consumes: accepted scheduler tier, exact release, calibration, schema-v2 manifest, rich feedback manifests, watchdog tooling.
- Produces: completed run `qfbench-rootless-evolution-30x15x40-v4-flash-0731-10iter-20260805`, local exact-ID mirror, and final audit/report inputs.

- [ ] **Step 1: Publish immutable formal configuration**

Set worker/verifier concurrency to the accepted tier, scheduler epoch `iter01-10-<tier>w3v`, lease timeout 6,000, worker launch interval 2, official model/provider/no-fallback route, fixed four-way manifest, calibration digest, rich feedback files, ten iterations, and a new immutable run ID.

- [ ] **Step 2: Install all monitoring layers before coordinator start**

Install/enable `Restart=on-failure` coordinator supervision, formal sentinel/watch timer, bounded repair policy, continuous Mac `caffeinate -i` controller, and additive exact-ID result mirror. Validate unit syntax and dry-run the controller against the exact run without reading prompts, verifier-only data, or secrets.

- [ ] **Step 3: Start the formal service and validate the first live attempt**

Run `systemctl --user start qea-qfbench-tvt-evolution.service`. Confirm exact release SHA, command line, run ID, manifest/calibration hashes, scheduler tier/epoch, proxy model/provider/fallback record, worker/proxy separation, verifier `NetworkMode=none`, and an advancing local mirror.

- [ ] **Step 4: Monitor and repair within bounded authority**

Poll coordinator state, score/checkpoint counts, current role counts, host load/memory/disk/inodes, provider identity, replay/quarantine/firewall findings, systemd restart count, sentinel state, Mac controller health, and mirror progress. Autonomously repair allowlisted infrastructure failures. Downshift only at an exact completed iteration boundary, publish a new scheduler epoch, and preserve prior evidence; benchmark-integrity failures freeze the run.

- [ ] **Step 5: Audit and report completion**

At completion require 575 reconciled official scores, 10 records, validation at 11 checkpoints, test and diagnostic at two checkpoints, clean verifier firewall, no replay/fallback, exact local mirror, zero residual resources, and a final audit. Report train/validation trajectories, retained iterations, 32-task primary seed/final delta by domain/task, eight diagnostic deltas separately, baseline variability context, provider usage/cost, failures, timeouts, and scheduler epochs.

