# QFBench Epoch-2 Canary Panel Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct the twelve-worker paid canary panel so every selected primary task has the declared 2 CPU/4 GiB worker contract and the canary can validly measure twelve-way overlap.

**Architecture:** Keep the existing selection and fail-closed runtime resource gate. Replace only the two heavy task IDs with same-domain, manifest-explicit QEA fallback tasks; strengthen the unit test with the pinned manifest and re-run the unchanged paid canary under a new publish-once ID.

**Tech Stack:** Python 3.12, pytest, pinned QFBench JSON manifest, rootless Docker on `bc-server`.

## Global Constraints

- Preserve worker concurrency 12, verifier concurrency 3, capacity 48 CPU/98,304 MiB/8,192 PIDs/40,960 MiB tmpfs/24 sandboxes, and host memory headroom 16,384 MiB.
- Do not expose official tests, references, solutions, rubrics, credentials, or `.env` to workers.
- Do not install dependencies, merge branches, reuse the failed run ID, or delete its zero-spend evidence.
- Use exact immutable image-set `16df73c4f45c861d88dd11fe286badd043c405bf2ce3010b0dd9fa27abc5f56c` and benchmark commit `024921eb507fcc0c4ffe3e0a96802724be1ae84a`.

---

### Task 1: Correct and verify the fixed canary panel

**Files:**
- Modify: `scripts/smoke_qfbench_full_harness.py:32-46`
- Modify: `tests/test_qfbench_full_harness_scripts.py:90-127`

**Interfaces:**
- Consumes: `PAID_BASELINE_BATCH_TASK_IDS` and `select_paid_baseline_batch_tasks(snapshot, config, executor)`.
- Produces: an exact twelve-task tuple containing `ohlc-realized-vol-estimators` and `geometric-mean-reverting-jd`, with no heavy historical/FX tasks.

- [ ] **Step 1: Write the failing pinned-panel test**

Add literal expected IDs and pinned-manifest assertions:

```python
expected = (
    "ohlc-realized-vol-estimators",
    "momentum-backtest",
    "evt-pot-var",
    "geometric-mean-reverting-jd",
    "option-put-call-parity-forward-audit",
    "sma-crossover-spy",
    "corporate-action-adjustment",
    "earnings-surprise-calculator",
    "fama-french-factor-model-new",
    "credit-migration-matrix",
    "zero-coupon-bootstrapping",
    "copula-sampling-rank-correlation",
)
assert PAID_BASELINE_BATCH_TASK_IDS == expected

manifest = json.loads(
    (Path(__file__).parents[1] / "data/qfbench/MANIFEST_85_BASELINE.json").read_text()
)
primary = {item["task_id"]: item for item in manifest["baseline"]["primary"]}
for task_id in ("ohlc-realized-vol-estimators", "geometric-mean-reverting-jd"):
    assert primary[task_id]["resource_source"] == "qea_fallback"
    assert primary[task_id]["resources"]["cpus"] == 2
    assert primary[task_id]["resources"]["memory_mb"] == 4096
```

Keep the existing mutation from 2 CPU to 4 CPU and require `ValueError` with `2 CPU/4096 MiB`.

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
/Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q \
  tests/test_qfbench_full_harness_scripts.py::test_paid_baseline_batch_requires_exact_epoch_two_standard_panel
```

Expected: FAIL because the production tuple still contains `historical-var-data-prep` and `fx-forward-cross-rate`.

- [ ] **Step 3: Make the minimal constant replacement**

In `PAID_BASELINE_BATCH_TASK_IDS`, replace exactly:

```python
"historical-var-data-prep" -> "ohlc-realized-vol-estimators"
"fx-forward-cross-rate" -> "geometric-mean-reverting-jd"
```

Do not change the resource gate, evaluator path, lifecycle audit, cost audit, or concurrency contract.

- [ ] **Step 4: Run focused and safety tests**

Run:

```bash
/Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q \
  tests/test_qfbench_full_harness_scripts.py tests/test_qfbench_epoch_report.py \
  tests/test_resource_lease.py tests/test_rootless_full_harness.py
git diff --check
```

Expected: all selected tests pass and no whitespace errors occur.

- [ ] **Step 5: Commit only code and test changes**

```bash
git add scripts/smoke_qfbench_full_harness.py tests/test_qfbench_full_harness_scripts.py
git commit -m "fix(canary): use standard QFBench workers"
```

### Task 2: Deploy and rerun the publish-once batch gate

**Files:**
- Remote immutable release: `/home/julius/qea/deploy/releases/$CORRECTED_COMMIT/`, where `CORRECTED_COMMIT` is validated from `git rev-parse HEAD`
- Existing config: `/home/julius/qea/runtime/configs/qfbench-base85-official-deepseek-v4-flash-presend-f62de10-epoch2.json`
- New evidence: `/home/julius/qea/runtime/canaries/qfbench-v4-flash-presend-epoch2-batch-1de511f-r2/`

**Interfaces:**
- Consumes: the corrected exact Git commit, existing image-set, epoch-2 config, public QFBench snapshot, and owner-only token path.
- Produces: `paid-baseline-batch.json` with worker overlap, route, score, cost, lifecycle, firewall, and cleanup evidence.

- [ ] **Step 1: Push and materialize the exact non-merged commit**

Run:

```bash
CORRECTED_COMMIT="$(git rev-parse HEAD)"
printf '%s\n' "$CORRECTED_COMMIT" | grep -E '^[0-9a-f]{40}$'
git push bc:~/qea/git/evolving-quant-agent.git \
  HEAD:refs/heads/qfbench-canary-panel-correction
ssh bc git --git-dir=/home/julius/qea/git/evolving-quant-agent.git \
  worktree add --detach \
  "/home/julius/qea/deploy/releases/$CORRECTED_COMMIT" \
  refs/heads/qfbench-canary-panel-correction
```

Then require `git -C "/home/julius/qea/deploy/releases/$CORRECTED_COMMIT" rev-parse HEAD` to equal `$CORRECTED_COMMIT` and `git status --porcelain` to be empty.

- [ ] **Step 2: Re-run the pre-spend selection under a new run ID**

From the detached release, run `scripts/smoke_qfbench_full_harness.py` with `--mode paid-baseline-batch`, the real `MANIFEST_85_BASELINE.json`, epoch-2 config, corrected image-set, and run ID `qfbench-v4-flash-presend-epoch2-batch-1de511f-r2`.

Expected before model work: all twelve real snapshot tasks pass the 2 CPU/4096 MiB gate.

- [ ] **Step 3: Require live acceptance evidence**

Require `worker_overlap == 12`, `provider == "deepseek"`, `model == "deepseek/deepseek-v4-flash"`, `fallbacks_allowed == false`, complete non-lower-bound cost accounting, networkless verifier lifecycles, worker-proxy-only networking, and `residual_resource_count == 0`. Exact-ID reap only this run if interrupted.

- [ ] **Step 4: Resume the formal-launch plan only after acceptance**

If accepted, continue with run-scoped supervisor/watch/sentinel dry-runs and a new repetition-1 formal run. If rejected, preserve all evidence and do not silently lower concurrency or capacity.
