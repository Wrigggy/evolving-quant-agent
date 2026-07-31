# QFBench All-Task Repeated Base-Worker Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and run a resumable, rootless-Docker-only QFBench baseline that evaluates one frozen base worker on 85 runnable tasks for five independent repetitions and reports uncertainty without invoking an evolver.

**Architecture:** Add a dedicated baseline manifest/loader and baseline state machine around the existing two-stage `QFBenchSandboxEvaluator`. Reuse the accepted rootless runtime, proxy, worker/verifier routers, exact-ID lifecycle handling, and role-separated materializer; add batch image-panel orchestration and baseline-specific statistics/cost artifacts. Run the immutable five-repetition identity through a one-repetition calibration stop, audit it, then resume repetitions two through five.

**Tech Stack:** Python 3.10+ standard library, pytest, existing QEA rootless Docker backend, NexAU worker runtime, official QFBench verifiers, JSON/JSONL artifacts, Git/SSH.

## Global Constraints

- Benchmark commit is exactly `024921eb507fcc0c4ffe3e0a96802724be1ae84a`.
- Run 77 primary tasks and eight diagnostic copy-oracle tasks; do not call the model for inoperable `sec-8k-event-alpha`.
- Use `qea/worker_gdpval_weak` unchanged and bind its directory digest into the run identity.
- Run exactly five independent repetitions; the maximum is 425 workers plus 425 independent no-network verifiers and zero evolver lifecycles.
- Use worker concurrency 4 and verifier concurrency 3 with the existing weighted capacity and headroom gate.
- Never upload or run official solutions; tests/reference data remain trusted-verifier-only; no credential enters a worker/evolver input.
- Eleven resource-unspecified tasks use the manifested QEA fallback 2 CPU/4 GiB/build 600 seconds/worker 2,400 seconds/verifier 300 seconds.
- Stop after repetition one unless 85/85 scores, cost completeness, firewall, cleanup, and projected-total-cost-at-most-USD-60 gates pass.
- Preserve existing dirty report/memory/runbook files; stage only files named by each task; do not merge.

---

### Task 1: Baseline Panel Contract and Loader

**Files:**
- Create: `tests/test_qfbench_baseline_manifest.py`
- Create: `data/qfbench/MANIFEST_85_BASELINE.json`
- Modify: `qea/benchmarks/qfbench.py`
- Modify: `scripts/materialize_qfbench_rootless_snapshot.py`

**Interfaces:**
- Produces: `QFBenchBaselineSnapshot(commit, primary, diagnostic, structural_exclusions, resource_fallback_task_ids)`.
- Produces: `load_qfbench_baseline_snapshot(root, manifest_path) -> QFBenchBaselineSnapshot`.
- Produces: materializer `_panel_contract()` support for `baseline.primary` plus `baseline.diagnostic` without accepting structural exclusions.

- [ ] **Step 1: Write the failing manifest/loader tests**

Add literal assertions that the repository manifest has 77 primary tasks, eight diagnostic tasks, one structural exclusion, six primary domains with counts `23/16/17/11/5/5`, exactly the eight registered copy-oracle diagnostic IDs, and exactly 11 resource fallbacks. Add a temporary-snapshot test that proves primary copy-oracles are rejected, registered diagnostic copy-oracles load, an inoperable task cannot enter either runnable panel, and missing upstream resources load only when all five fallback fields are present.

```python
def test_repository_baseline_manifest_freezes_complete_universe():
    payload = json.loads(MANIFEST.read_text())
    assert len(payload["baseline"]["primary"]) == 77
    assert len(payload["baseline"]["diagnostic"]) == 8
    assert payload["baseline"]["structural_exclusions"] == [{
        "task_id": "sec-8k-event-alpha",
        "reason": "official verifier raises before writing reward.txt at the pinned commit",
    }]
    assert Counter(x["domain"] for x in payload["baseline"]["primary"]) == {
        "derivatives": 23, "risk_credit": 16,
        "systematic_strategy": 17, "rates_fx_macro": 11,
        "execution_microstructure": 5, "data_engineering": 5,
    }
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `/Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q tests/test_qfbench_baseline_manifest.py`

Expected: FAIL because the manifest and baseline loader do not exist.

- [ ] **Step 3: Add the immutable manifest and minimal loader**

Build `MANIFEST_85_BASELINE.json` from the audited six-domain inventory. Each task record contains `task_id`, `domain`, unique `lineage`, `difficulty`, `reward_kind`, `resource_source`, and, only for the 11 fallback tasks, this exact object:

```json
"resources": {
  "agent_timeout_seconds": 2400,
  "verifier_timeout_seconds": 300,
  "build_timeout_seconds": 600,
  "cpus": 2,
  "memory_mb": 4096
}
```

In `qfbench.py`, keep the pilot loader's default copy-oracle rejection and add a baseline-only call path that permits copy-oracles only in the diagnostic panel. Change `_task_resource_contract(task_root, task_id, *, fallback=None)` so a complete upstream contract wins, a complete explicit fallback is accepted only when the upstream contract is absent, and partial/mismatched fallback data fails closed.

- [ ] **Step 4: Extend role materialization to the baseline schema**

Make `_panel_contract()` select either the existing `pilot.optimize + pilot.held_out` entries or `baseline.primary + baseline.diagnostic`, reject a manifest containing both shapes, and never include `baseline.structural_exclusions` in `task_ids`.

- [ ] **Step 5: Run focused manifest/materializer tests and verify GREEN**

Run:

```bash
/Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q \
  tests/test_qfbench_baseline_manifest.py \
  tests/test_qfbench_rootless_materializer.py
```

Expected: PASS.

- [ ] **Step 6: Commit the panel contract**

```bash
git add data/qfbench/MANIFEST_85_BASELINE.json qea/benchmarks/qfbench.py \
  scripts/materialize_qfbench_rootless_snapshot.py \
  tests/test_qfbench_baseline_manifest.py tests/test_qfbench_rootless_materializer.py
git commit -m "feat(qfbench): register all-task baseline panel"
```

### Task 2: Pure Baseline State Machine and Statistics

**Files:**
- Create: `qea/qfbench_baseline.py`
- Create: `tests/test_qfbench_baseline.py`

**Interfaces:**
- Consumes: `BenchmarkEvaluator.evaluate(worker_dir, tasks, split, checkpoint, run_dir)`.
- Produces: `BaselineConfig`, `BaselineRepetition`, `BaselineResult`.
- Produces: `run_qfbench_baseline(config, primary_tasks, diagnostic_tasks, benchmark_commit, evaluator, stop_after_repetition=None) -> BaselineResult`.
- Produces: `aggregate_repetitions(primary_repetitions, diagnostic_repetitions, resource_fallback_task_ids) -> dict`.

- [ ] **Step 1: Write RED tests for no-evolver scheduling and resume**

Use a recording evaluator returning literal `EvaluationSummary` values. Assert five repetitions make ten evaluator calls in this order:

```python
assert calls == [
    ("baseline_primary", "repetition-01-primary"),
    ("baseline_diagnostic", "repetition-01-diagnostic"),
    # ... through repetition 05
]
```

Assert `stop_after_repetition=1` writes a non-complete checkpoint, and resuming with total repetitions five starts at repetition two. Assert changes to worker digest, benchmark commit, task manifest digest, model identity, runtime identity, scheduler identity, or repetition count reject resume.

- [ ] **Step 2: Run and verify RED**

Run: `/Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q tests/test_qfbench_baseline.py -k 'schedule or resume'`

Expected: FAIL with `ModuleNotFoundError: qea.qfbench_baseline`.

- [ ] **Step 3: Implement the minimal resumable state machine**

Persist schema-versioned `resume.json` before the first evaluator call. Snapshot the base worker once under `workers/seed`; store its digest. After each primary and diagnostic summary, atomically write the checkpoint. Use split names `baseline_primary` and `baseline_diagnostic`, with repetition-specific checkpoints, so `TaskAttempt` content identities differ across repetitions while exact resume identities remain stable.

- [ ] **Step 4: Write RED tests for statistical aggregation**

Use hand-derived repetition macros `(0.4, 0.5, 0.6, 0.7, 0.8)` and assert mean `0.6`, sample SD `sqrt(0.025)`, standard error `sqrt(0.005)`, and Student-t interval `0.6 +/- 2.7764451051977987 * sqrt(0.005)`. Assert diagnostic tasks never affect the primary headline, and the resource-declared sensitivity excludes exactly the passed fallback IDs.

- [ ] **Step 5: Implement deterministic aggregation and verify GREEN**

Use `statistics.mean` and `statistics.stdev`. Support only the preregistered five repetitions for a complete result; partial calibration output reports observed summaries without a confidence interval. Emit per-repetition, per-domain, per-task, diagnostic, and resource-declared sections with explicit denominators.

Run: `/Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q tests/test_qfbench_baseline.py`

Expected: PASS.

- [ ] **Step 6: Commit the baseline engine**

```bash
git add qea/qfbench_baseline.py tests/test_qfbench_baseline.py
git commit -m "feat(qfbench): add repeated base-worker baseline"
```

### Task 3: Baseline Cost Audit

**Files:**
- Modify: `qea/qfbench_baseline.py`
- Modify: `tests/test_qfbench_baseline.py`

**Interfaces:**
- Produces: `audit_baseline_proxy_costs(run_dir, *, expected_attempts) -> dict`.

- [ ] **Step 1: Write RED tests for complete and incomplete proxy audits**

Create literal JSONL records matching the production proxy audit schema. Assert the audit maps files back through `attempt.json`, totals request counts/tokens/provider costs exactly, groups by repetition/panel/task, and fails when a successful HTTP-200 request has null usage/cost, an attempt lacks an audit, a checkpoint is outside the baseline roster, or the number of scored attempts differs from `expected_attempts`.

- [ ] **Step 2: Run and verify RED**

Run: `/Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q tests/test_qfbench_baseline.py -k cost`

Expected: FAIL because `audit_baseline_proxy_costs` is absent.

- [ ] **Step 3: Implement strict read-only reconciliation**

Read only `attempts/*/attempt.json`, `completed-score.json`, and `proxy-audit.jsonl`; never read model prompts/responses. Use `Decimal(str(cost))` for the exact total. Treat missing audit files, malformed schemas, non-completed successful records, null successful usage/cost, unrecognized tasks/checkpoints, or count drift as an audit failure rather than zero.

- [ ] **Step 4: Run and verify GREEN, then commit**

Run: `/Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q tests/test_qfbench_baseline.py`

```bash
git add qea/qfbench_baseline.py tests/test_qfbench_baseline.py
git commit -m "feat(qfbench): reconcile baseline provider cost"
```

### Task 4: Rootless Baseline CLI

**Files:**
- Modify: `run.py`
- Modify: `tests/test_run_cli.py`

**Interfaces:**
- Consumes: `load_qfbench_baseline_snapshot`, `build_rootless_full_harness_runtime`, and `run_qfbench_baseline`.
- Produces: `--qfbench-baseline`, `--repetitions 5`, and `--stop-after-repetition 1` on the existing QFBench rootless command.

- [ ] **Step 1: Write RED CLI tests**

Assert baseline mode rejects E2B, feedback/evolver-only flags, any repetition count other than five, a stop boundary outside `1..5`, missing rootless config/image set/root/manifest/run ID, and execution without either `--approve-external-run` or `QEA_PAID_EVAL_AUTO_APPROVE=1`. Assert dry-run planning reports 85 tasks, 425 scoring attempts, 850 maximum worker/verifier lifecycles, and zero evolvers without reading `.env`.

- [ ] **Step 2: Run and verify RED**

Run: `/Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q tests/test_run_cli.py -k baseline`

Expected: FAIL because the baseline CLI flags/path are absent.

- [ ] **Step 3: Implement minimal rootless dispatch**

Add `_run_qfbench_rootless_baseline(args)`. Assemble the runtime with all 85 tasks, but pass only `runtime.evaluator` to the baseline engine; never access `runtime.proposer`. Bind panel digest, model-route identity, worker digest, image/runtime/scheduler identities, and both concurrency values into the checkpoint identity. Always close the runtime in `finally`.

- [ ] **Step 4: Verify CLI tests and commit**

Run:

```bash
/Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q \
  tests/test_run_cli.py tests/test_qfbench_baseline.py
```

```bash
git add run.py tests/test_run_cli.py
git commit -m "feat(qfbench): expose rootless baseline CLI"
```

### Task 5: Batch Rootless Image-Panel Builder

**Files:**
- Create: `scripts/build_qfbench_rootless_panel.py`
- Create: `tests/test_qfbench_rootless_panel_build.py`
- Modify: `scripts/assemble_qfbench_rootless_image_set.py`

**Interfaces:**
- Consumes: the baseline snapshot and existing `prepare_rootless_image_plan`, `execute_rootless_image_build`, and `RootlessImageSet.from_manifest_paths`.
- Produces: a deterministic plan of 170 task-role builds plus explicit neutral manifests, resumable by measured plan/result identity.
- Produces: `--panel-manifest`, `--public-root`, `--trusted-root`, `--manifest-root`, repeatable `--neutral-manifest`, `--docker-host`, `--base-image-ref`, `--nexau-runtime-image-ref`, `--plan-only|--build`, and `--output-image-set`.

- [ ] **Step 1: Write RED plan-mode tests**

Use two literal fake tasks and assert sorted worker/verifier build records, exact task resources including fallback resources, no E2B imports, no Docker connection in plan-only mode, and rejection of an incomplete prior manifest or a manifest whose source/resource/daemon identity differs.

- [ ] **Step 2: Run and verify RED**

Run: `/Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q tests/test_qfbench_rootless_panel_build.py`

Expected: FAIL because the batch script does not exist.

- [ ] **Step 3: Implement deterministic plan/build/resume**

Plan all task-role identities first and persist `panel-build-plan.json`. In build mode, reuse only a result-addressed manifest whose recomputed plan identity matches; otherwise execute the existing single-image build function. After every completed role, atomically update `panel-build-state.json`. Assemble the image set only after exactly one worker and one verifier manifest exist for every task plus base/proxy/evolver neutral manifests.

- [ ] **Step 4: Run and verify GREEN, then commit**

Run:

```bash
/Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q \
  tests/test_qfbench_rootless_panel_build.py tests/test_rootless_images.py \
  tests/test_rootless_image_set.py
```

```bash
git add scripts/build_qfbench_rootless_panel.py \
  scripts/assemble_qfbench_rootless_image_set.py \
  tests/test_qfbench_rootless_panel_build.py
git commit -m "feat(rootless): build complete QFBench image panels"
```

### Task 6: Local and Linux Verification Gate

**Files:**
- Modify only if a new regression is discovered, always after adding its failing test.

- [ ] **Step 1: Run focused macOS tests**

```bash
/Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest -q \
  tests/test_qfbench_baseline_manifest.py tests/test_qfbench_baseline.py \
  tests/test_qfbench_rootless_materializer.py \
  tests/test_qfbench_rootless_panel_build.py tests/test_run_cli.py \
  tests/test_rootless_full_harness.py tests/test_rootless_runtime.py \
  tests/test_rootless_images.py tests/test_rootless_image_set.py
```

Expected: PASS. The pre-existing macOS socket-restricted `test_model_proxy.py`
failures and missing gitignored oracle artifact are not part of this focused
gate.

- [ ] **Step 2: Push the implementation branch without merging**

Push a new remote branch whose tip includes the baseline commits. Record the
exact commit SHA.

- [ ] **Step 3: Update bc and run the complete Linux regression set**

Use `/home/julius/qea/runtime/venvs/rootless/bin/python -m pytest -q tests` in
`/home/julius/qea/worktrees/qfbench-rootless-full-harness-core`. Expected:
all collected Linux tests pass; record count and wall time.

### Task 7: Materialize and Build the 85-Task Rootless Panel

**Files/Artifacts on bc:**
- Create: `/home/julius/qea/runtime/qfbench-source/024921eb`
- Create: `/home/julius/qea/runtime/qfbench-public/024921eb-base85`
- Create: `/home/julius/qea/runtime/trusted-verifier/024921eb-base85`
- Create: `/home/julius/qea/runtime/rootless-images/024921eb-base85/`
- Create: `/home/julius/qea/runtime/image-sets/024921eb-base85.json`

- [ ] **Step 1: Verify source and host capacity**

Verify the source HEAD, 86 task directories, rootless daemon identity,
available CPU/memory/disk/inodes, zero active run-owned containers/networks,
and the owner/mode of the model token without printing it.

- [ ] **Step 2: Materialize role-separated inputs**

Run `scripts/materialize_qfbench_rootless_snapshot.py --apply` with the baseline
manifest. Require exactly 85 public tasks, 85 trusted task roots, zero solution
members in either output, and byte identities matching the pinned Git tree.

- [ ] **Step 3: Plan all images before building**

Run the batch builder with `--plan-only`. Require 170 unique task-role plan
identities, exact 77/8 roster coverage, resource parity, and neutral image
identity compatibility.

- [ ] **Step 4: Build with bounded concurrency and resume**

Run task-role builds with at most two concurrent Docker builds. Preserve every
dependency lock and failure log. Fix a reproducible build defect only through
a failing local test and new commit; never skip a task or enable verifier
network at scoring time.

- [ ] **Step 5: Assemble and preflight the image set**

Require one base, proxy, evolver, 85 worker, and 85 verifier entries; all image
IDs present in the same rootless daemon; all verifier test-script hashes and
public/trusted material hashes exact; no task-role resource drift.

### Task 8: One-Repetition Calibration

**Run ID:** `qfbench-rootless-base-85x5-20260731`

- [ ] **Step 1: Freeze owner-only run config**

Record code SHA, source/panel/image/runtime/scheduler/model-route/worker digests,
five total repetitions, stop-after boundary one, worker concurrency 4,
verifier concurrency 3, and the exact command. Set mode 600; do not copy `.env`.

- [ ] **Step 2: Start the approved paid calibration**

Run baseline mode with `QEA_PAID_EVAL_AUTO_APPROVE=1`, total repetitions five,
and `--stop-after-repetition 1`. Supervise through durable tmux/log files and
report progress without printing credentials or model content.

- [ ] **Step 3: Apply the calibration gates**

Require 85 completed official scores, no infrastructure-as-zero event, complete
proxy usage/cost, zero forbidden exposure, zero residual run-owned resources,
and projected five-repetition model cost no greater than USD 60. Persist the
calibration cost/firewall/lifecycle audit with SHA-256 hashes.

### Task 9: Resume Repetitions Two Through Five and Report

- [ ] **Step 1: Resume the exact immutable run**

Run the same command with `--resume` and no stop-after boundary. Before resume,
preview the exact-ID reaper; reap only unfinished IDs recorded by this run.

- [ ] **Step 2: Verify the complete experiment**

Require 425 unique attempt identities and scores, five primary and five
diagnostic summaries, no evolver lifecycle, complete canonical cost, zero
firewall findings, and zero residual run-owned containers/networks.

- [ ] **Step 3: Generate statistics and the research-quality gate**

Regenerate `result.json` from raw score files. Emit the primary five-repetition
domain-macro mean/SD/SE/95% t interval, domain/task distributions, diagnostic
appendix, 66-task resource-declared sensitivity, failures/timeouts, token/cost,
and wall-time distributions.

Use the quant-research checklist output:

```text
Gate: READY | READY_WITH_WARNINGS | NOT_READY
Scope: QFBench 85-task, five-repetition frozen base-worker baseline
Run ID(s): qfbench-rootless-base-85x5-20260731
```

Mark trading-data/time-split/execution-cost fields `NEEDS_EVIDENCE` where they
do not apply to this heterogeneous benchmark; do not reinterpret benchmark
reward as alpha.

- [ ] **Step 4: Record a superseding decision without rewriting history**

Add a dated decision/report, update `docs/PROJECT_MEMORY.md`, and preserve all
older QFBench reports. Commit only the new implementation/result documents and
explicit memory changes; do not merge.
