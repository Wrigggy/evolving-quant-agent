# QFBench 30-Task Five-Iteration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Materialize and validate a pinned 30-task QFBench split, publish its E2B task-role templates, run one five-iteration 140-attempt evolution experiment, and compare it with the five-task pilot.

**Architecture:** Keep the existing local coordinator, content-addressed attempt resume, isolated E2B NexAU workers, and independent no-network official verifiers. Add a separately preregistered manifest plus a raw-file materializer that verifies every downloaded payload against the pinned Git tree blob ID, then reuse the published base and five-task role templates while publishing only missing task-role identities.

**Tech Stack:** Python 3.10+, pytest, Git object IDs, `urllib.request`, E2B SDK 2.30.0, NexAU 0.3.9 pinned to commit `35ee1861546db3cb280a6e17e38a74060d7c96c3`, QFBench commit `024921eb507fcc0c4ffe3e0a96802724be1ae84a`.

## Global Constraints

- The authoritative design is `docs/superpowers/specs/2026-07-25-qfbench-30-task-five-iteration-design.md`.
- Use exactly 20 optimize and 10 held-out tasks from that design; do not substitute tasks based on observed rewards.
- Official tests and reference data may enter only no-network verifier sandboxes; official solutions are not uploaded or executed.
- Held-out rewards, tests, assertions, expected values, and trusted logs never enter proposer feedback.
- Use run ID `qfbench-30x5-20260725`, model `deepseek/deepseek-v4-pro`, five iterations, concurrency 8, and global E2B cap 12.
- Reuse base template `h4d9iarzjjts2z472o8d` and build `b82873ce-db6e-4269-a689-ecb9354bf207`.
- Never broaden sandbox cleanup: dry-run and apply only exact lifecycle IDs under the experiment run directory.
- Preserve all dated prior results and decisions.

---

### Task 1: Preregister the 30-task manifest

**Files:**
- Create: `data/qfbench/MANIFEST_30.json`
- Modify: `tests/test_qfbench_pilot_contract.py`

**Interfaces:**
- Consumes: the manifest schema already loaded by `load_qfbench_snapshot(root, manifest_path=...)`.
- Produces: a manifest whose `pilot.optimize` and `pilot.held_out` arrays exactly match the design spec.

- [ ] **Step 1: Write the failing manifest contract test**

Add this test to `tests/test_qfbench_pilot_contract.py` before creating the manifest:

```python
def test_repository_manifest_30_preregisters_exact_stratified_split():
    path = REPOSITORY / "data/qfbench/MANIFEST_30.json"
    payload = json.loads(path.read_text())
    optimize = payload["pilot"]["optimize"]
    held_out = payload["pilot"]["held_out"]

    assert payload["commit"] == PINNED_COMMIT
    assert [item["task_id"] for item in optimize] == [
        "historical-var-data-prep", "evt-pot-var", "credit-migration-matrix",
        "credit-spread-decomposition", "momentum-backtest",
        "bollinger-backtest-aapl", "brinson-sector-attribution",
        "etf-cross-asset-lead-lag", "cme-hdd-option-pricing",
        "delta-hedging-pnl-simulation", "localvol-barrier",
        "fomc-tone-event-study", "swap-curve-bootstrap-ois",
        "yield-curve-bond-immunization", "zero-coupon-bootstrapping",
        "crypto-funding-rate-basis-carry",
        "prediction-markets-cross-venue-dislocation",
        "13f-amendment-aware-crowding", "corporate-action-adjustment",
        "earnings-surprise-calculator",
    ]
    assert [item["task_id"] for item in held_out] == [
        "dcc-garch-portfolio-var", "fft-compound-poisson",
        "pca-factor-portfolio", "bl-regime-hmm",
        "option-put-call-parity-forward-audit", "interest-rate-cap-floor",
        "fx-forward-cross-rate", "cir-bond-pricing",
        "intraday-volume-fitting-and-execution-scheduling",
        "form4-cross-sectional-sale-pressure",
    ]
    assert len(optimize) == 20
    assert len(held_out) == 10
    assert {item["domain"] for item in optimize} == {
        "risk_credit", "systematic_strategy", "derivatives",
        "rates_fx_macro", "execution_microstructure", "data_engineering",
    }
    assert {item["domain"] for item in held_out} == {
        "risk_credit", "systematic_strategy", "derivatives",
        "rates_fx_macro", "execution_microstructure", "data_engineering",
    }
    assert sum(item["reward_kind"] == "partial" for item in optimize) == 4
    assert {item["lineage"] for item in optimize}.isdisjoint(
        item["lineage"] for item in held_out
    )
    selected = {item["task_id"] for item in optimize + held_out}
    assert selected.isdisjoint(payload["copy_oracle_tasks"])
    assert selected.isdisjoint(
        item["task_id"] for item in payload["inoperable_tasks"]
    )
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
.venv-nexau/bin/python -m pytest -q \
  tests/test_qfbench_pilot_contract.py::test_repository_manifest_30_preregisters_exact_stratified_split
```

Expected: FAIL with `FileNotFoundError` for `data/qfbench/MANIFEST_30.json`.

- [ ] **Step 3: Create the manifest**

Copy the repository URL, commit, inventory, eight `copy_oracle_tasks`, and `inoperable_tasks` fields from `MANIFEST.json`. Add the exact 30 entries, domains, lineages, difficulties, and reward kinds from the approved design spec; preserve their listed order.

- [ ] **Step 4: Run the test and verify GREEN**

Run the Step 2 command. Expected: `1 passed`.

- [ ] **Step 5: Commit the manifest contract**

```bash
git add data/qfbench/MANIFEST_30.json tests/test_qfbench_pilot_contract.py
git commit -m "test(qfbench): preregister 30-task experiment split"
```

### Task 2: Reject exact input-data leakage across splits

**Files:**
- Modify: `qea/benchmarks/qfbench.py`
- Modify: `tests/test_qfbench_adapter.py`

**Interfaces:**
- Consumes: loaded `QFBenchTask` objects and their `environment/data` files.
- Produces: `_reject_cross_split_input_hash_overlap(optimize, held_out) -> None`, called by `load_qfbench_snapshot` before returning.

- [ ] **Step 1: Write a failing duplicate-input test**

Add a second environment data file with identical bytes to one optimize and one held-out fixture task, then assert:

```python
def test_rejects_exact_input_hash_overlap_between_splits(qfbench_fixture):
    from qea.benchmarks.qfbench import QFBenchConfigError, load_qfbench_snapshot

    root, manifest = qfbench_fixture
    shared = b"date,value\n2025-01-01,1\n"
    (root / "tasks/historical-var-data-prep/environment/data/shared.csv").write_bytes(shared)
    (root / "tasks/fx-forward-cross-rate/environment/data/copied.csv").write_bytes(shared)

    with pytest.raises(QFBenchConfigError, match="input data hash overlap"):
        load_qfbench_snapshot(root, manifest_path=manifest)
```

- [ ] **Step 2: Verify RED**

```bash
.venv-nexau/bin/python -m pytest -q \
  tests/test_qfbench_adapter.py::test_rejects_exact_input_hash_overlap_between_splits
```

Expected: FAIL because the loader currently accepts the duplicate bytes.

- [ ] **Step 3: Implement the minimum hash-overlap gate**

Add a helper that hashes files relative to each task's `environment/data` directory with SHA-256, compares optimize hashes with held-out hashes, and raises `QFBenchConfigError` listing only task IDs and relative paths. Call it after both splits are loaded. Do not include file contents or expected values in the error.

- [ ] **Step 4: Verify GREEN and existing firewall tests**

```bash
.venv-nexau/bin/python -m pytest -q tests/test_qfbench_adapter.py
```

Expected: all adapter tests pass.

- [ ] **Step 5: Commit the leakage gate**

```bash
git add qea/benchmarks/qfbench.py tests/test_qfbench_adapter.py
git commit -m "feat(qfbench): reject cross-split input duplication"
```

### Task 3: Add pinned raw-file snapshot materialization

**Files:**
- Modify: `qea/benchmarks/qfbench.py`
- Create: `scripts/materialize_qfbench_raw_snapshot.py`
- Modify: `tests/test_qfbench_adapter.py`

**Interfaces:**
- Produces: `git_blob_oid(payload: bytes) -> str`.
- Produces: `list_qfbench_tree_blobs(source_repo, commit, task_ids) -> tuple[PinnedBlob, ...]` where `PinnedBlob` contains `mode`, `oid`, and `path`.
- Produces: `materialize_qfbench_raw_snapshot(source_repo, destination, repository_url, commit, task_ids, fetch_blob=None) -> Path`.
- The default fetcher accepts a repository-relative path and returns bytes from `raw.githubusercontent.com` at the exact commit. Tests inject a local fetcher and perform no network.

- [ ] **Step 1: Write failing Git-blob and atomic-materialization tests**

Create a local Git fixture containing `docker/` plus two task directories. Assert that `git_blob_oid(b"hello\n")` equals `git hash-object` output, that the requested paths are exact, that executable modes are preserved, and that a wrong payload raises before the destination or revision marker exists.

- [ ] **Step 2: Verify RED**

```bash
.venv-nexau/bin/python -m pytest -q tests/test_qfbench_adapter.py \
  -k 'git_blob or raw_snapshot'
```

Expected: FAIL because the functions do not exist.

- [ ] **Step 3: Implement verified staging and atomic promotion**

Implement the Git blob formula exactly:

```python
def git_blob_oid(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode()
    return hashlib.sha1(header + payload).hexdigest()
```

Use `git ls-tree -r <commit> -- docker tasks/<id>...` to obtain authoritative blob IDs without fetching blobs. Download into `<destination>.partial`, skip only existing files whose blob IDs already match, apply executable mode `0o755` for mode `100755`, and write the two marker files only after every blob verifies. Refuse an existing final destination; atomically rename the verified staging directory into place.

- [ ] **Step 4: Add the CLI**

The script must require `--source-tree`, `--manifest`, and `--destination`; it loads task IDs from both manifest splits and invokes the new materializer. Its final output prints the commit, task count, file count, and destination, without printing file contents.

- [ ] **Step 5: Verify GREEN**

```bash
.venv-nexau/bin/python -m pytest -q tests/test_qfbench_adapter.py
.venv-nexau/bin/python -m py_compile scripts/materialize_qfbench_raw_snapshot.py
```

Expected: both commands exit 0.

- [ ] **Step 6: Commit the materializer**

```bash
git add qea/benchmarks/qfbench.py scripts/materialize_qfbench_raw_snapshot.py \
  tests/test_qfbench_adapter.py
git commit -m "feat(qfbench): verify raw snapshot files against Git blobs"
```

### Task 4: Lock the five-iteration attempt contract

**Files:**
- Modify: `run.py`
- Modify: `tests/test_run_cli.py`

**Interfaces:**
- Produces: `estimate_qfbench_attempts(optimize_count: int, held_out_count: int, iterations: int) -> int`.
- `run_qfbench` uses that helper for its preflight output.

- [ ] **Step 1: Write the failing 140-attempt test**

```python
def test_qfbench_30x5_estimates_140_official_attempts():
    assert run.estimate_qfbench_attempts(20, 10, 5) == 140
```

- [ ] **Step 2: Verify RED**

```bash
.venv-nexau/bin/python -m pytest -q \
  tests/test_run_cli.py::test_qfbench_30x5_estimates_140_official_attempts
```

Expected: FAIL with missing attribute.

- [ ] **Step 3: Implement and use the helper**

```python
def estimate_qfbench_attempts(
    optimize_count: int, held_out_count: int, iterations: int
) -> int:
    if optimize_count < 1 or held_out_count < 1 or iterations not in {3, 5}:
        raise ValueError("invalid QFBench attempt schedule")
    return optimize_count * (iterations + 1) + held_out_count * 2
```

Replace the inline calculation with this helper.

- [ ] **Step 4: Verify GREEN and evolution scheduling**

```bash
.venv-nexau/bin/python -m pytest -q \
  tests/test_run_cli.py tests/test_qfbench_evolution.py
```

Expected: both files pass.

- [ ] **Step 5: Commit the schedule contract**

```bash
git add run.py tests/test_run_cli.py
git commit -m "test(qfbench): lock 30-task five-iteration schedule"
```

### Task 5: Materialize and dry-validate the live 30-task snapshot

**Files:**
- Generate: `/private/tmp/qea-qfbench-30-024921eb`
- Generate: `output/qfbench-e2b-images/20260725_30x5_024921eb/*.image.json`

**Interfaces:**
- Consumes: `MANIFEST_30.json`, the existing pinned tree at `/private/tmp/qea-qfbench-024921eb`, and the published base manifest.
- Produces: one locally verified snapshot and 60 dry-run role manifests.

- [ ] **Step 1: Run the raw materializer**

```bash
.venv-nexau/bin/python scripts/materialize_qfbench_raw_snapshot.py \
  --source-tree /private/tmp/qea-qfbench-024921eb \
  --manifest data/qfbench/MANIFEST_30.json \
  --destination /private/tmp/qea-qfbench-30-024921eb
```

Expected: commit `024921eb...`, 30 tasks, a positive file count, and no hash mismatch.

- [ ] **Step 2: Load the snapshot through the production adapter**

```bash
.venv-nexau/bin/python -c 'from qea.benchmarks.qfbench import load_qfbench_snapshot; s=load_qfbench_snapshot("/private/tmp/qea-qfbench-30-024921eb", manifest_path="data/qfbench/MANIFEST_30.json"); assert len(s.optimize.tasks)==20 and len(s.held_out.tasks)==10; print(s.commit, len(s.tasks))'
```

Expected: the pinned commit and `30`.

- [ ] **Step 3: Seed the new output directory with reusable manifests**

Create `output/qfbench-e2b-images/20260725_30x5_024921eb/`, copy the previous base manifest, and copy both published role manifests for the five shared tasks: `historical-var-data-prep`, `evt-pot-var`, `momentum-backtest`, `fx-forward-cross-rate`, and `option-put-call-parity-forward-audit`.

- [ ] **Step 4: Generate all role manifests without publication**

```bash
.venv-nexau/bin/python scripts/build_qfbench_e2b_templates.py \
  --qfbench-root /private/tmp/qea-qfbench-30-024921eb \
  --manifest data/qfbench/MANIFEST_30.json \
  --base-manifest output/qfbench-e2b-images/20260725_30x5_024921eb/qfbench-base.image.json \
  --output-dir output/qfbench-e2b-images/20260725_30x5_024921eb
```

Expected: 60 prepared manifests and `dry run only`.

- [ ] **Step 5: Audit dry identities and resources**

Assert there are 30 worker and 30 verifier manifests, all use the pinned commit/base IDs, all resources match task TOML, the five shared identities retain published IDs, and the other 50 published IDs remain null.

### Task 6: Publish the 50 missing E2B role templates

**Files:**
- Update generated manifests under `output/qfbench-e2b-images/20260725_30x5_024921eb/`.

**Interfaces:**
- Produces: immutable template/build IDs for all 60 role manifests.

- [ ] **Step 1: Publish sequentially and resumably**

```bash
set -a
source .env
set +a
.venv-nexau/bin/python scripts/build_qfbench_e2b_templates.py \
  --qfbench-root /private/tmp/qea-qfbench-30-024921eb \
  --manifest data/qfbench/MANIFEST_30.json \
  --base-manifest output/qfbench-e2b-images/20260725_30x5_024921eb/qfbench-base.image.json \
  --output-dir output/qfbench-e2b-images/20260725_30x5_024921eb \
  --publish
```

If interrupted, rerun this exact command; already-published manifests must be reused.

- [ ] **Step 2: Audit publication**

Verify exactly 60 non-empty `published_template_id` values, 60 non-empty `published_build_id` values, 60 unique task-role pairs, and exactly 10 reused IDs from the prior output directory.

- [ ] **Step 3: Smoke a new worker template and model egress**

Run `scripts/smoke_qfbench_e2b_worker_template.py` and `scripts/smoke_qfbench_e2b_model_egress.py` against `cme-hdd-option-pricing.worker.image.json`. Require Python 3.11 task runtime, Python 3.12 NexAU runtime, NexAU 0.3.9, the expected worker lock hash, HTTP 200 from the configured provider, and cleanup.

### Task 7: Run and resume the 30-task five-iteration experiment

**Files:**
- Generate: `results/qfbench/qfbench-30x5-20260725/`.

**Interfaces:**
- Produces: seed optimize/held-out summaries, five iteration records, final held-out, 140 completed official scores, and 280 cleaned lifecycle records.

- [ ] **Step 1: Run reaper dry-runs before launch**

Dry-run the exact-ID reaper against existing pilot/oracle directories and require no pending sandbox IDs.

- [ ] **Step 2: Launch the authorized run**

```bash
set -a
source .env
set +a
export LLM_MODEL=deepseek/deepseek-v4-pro
export PYTHONUNBUFFERED=1
.venv-nexau/bin/python run.py \
  --benchmark qfbench --executor e2b \
  --qfbench-root /private/tmp/qea-qfbench-30-024921eb \
  --qfbench-manifest data/qfbench/MANIFEST_30.json \
  --template-manifest-dir output/qfbench-e2b-images/20260725_30x5_024921eb \
  --run-id qfbench-30x5-20260725 --iters 5 \
  --concurrency 8 --global-e2b-cap 12 \
  --results-dir results/qfbench --approve-external-run
```

- [ ] **Step 3: Recover any interruption exactly**

If the process exits before phase complete, run the reaper without `--apply`, review exact pending IDs, apply only to this run directory if needed, then rerun the Step 2 command with `--resume`. Do not change any other argument.

- [ ] **Step 4: Verify completion counts**

Require phase `complete`, five records, 140 attempt directories, 140 `completed-score.json` files, 140 worker cleanups, 140 verifier cleanups, and no pending lifecycle IDs.

### Task 8: Compare, document, and verify

**Files:**
- Create: `docs/decisions/2026-07-25-qfbench-30-task-five-iteration-result.md`
- Create: `docs/reports/2026-07-25-qfbench-30x5-comparison.md`
- Modify: `docs/PROJECT_MEMORY.md`
- Modify: `docs/runbooks/2026-07-23-qfbench-e2b-pilot.md`

**Interfaces:**
- Consumes: current run artifacts and `qfbench-pilot-3-20260724T102755`.
- Produces: a measured comparison that preserves raw task rewards and separates engineering, benchmark, variance, and transfer claims.

- [ ] **Step 1: Generate an auditable comparison table**

Extract shared-task seed scores, all new seed scores, each iteration's per-task/domain scores, keep/rollback decisions, held-out seed/final paired deltas, attempt durations, errors, and cleanup status. Preserve links to both run directories.

- [ ] **Step 2: Write the decision and comparison report**

Record the exact manifest, model, template directory, run ID, attempt count, score trajectories, held-out change, candidate decisions, failures/recovery, and unavailable cost fields. Do not rewrite the 2026-07-24 report.

- [ ] **Step 3: Update canonical memory and runbook**

Replace the pending 30-task experiment entry with measured evidence and link the new decision/report. Add the exact resume command and template directory to the runbook.

- [ ] **Step 4: Run fresh full verification**

```bash
.venv-nexau/bin/python -m pytest -q tests
.venv-nexau/bin/python -m py_compile \
  scripts/materialize_qfbench_raw_snapshot.py \
  scripts/build_qfbench_e2b_base.py \
  scripts/build_qfbench_e2b_templates.py \
  scripts/reap_qfbench_e2b.py \
  scripts/run_qfbench_e2b_oracle.py \
  scripts/smoke_qfbench_e2b_worker_template.py \
  scripts/smoke_qfbench_e2b_model_egress.py
.venv-nexau/bin/python run.py --mock
```

Expected: pytest has zero failures, script compilation exits 0, and mock mechanism signals all pass.

- [ ] **Step 5: Commit measured documentation**

```bash
git add docs/decisions/2026-07-25-qfbench-30-task-five-iteration-result.md \
  docs/reports/2026-07-25-qfbench-30x5-comparison.md \
  docs/PROJECT_MEMORY.md docs/runbooks/2026-07-23-qfbench-e2b-pilot.md
git commit -m "results(qfbench): record 30-task five-iteration experiment"
```
