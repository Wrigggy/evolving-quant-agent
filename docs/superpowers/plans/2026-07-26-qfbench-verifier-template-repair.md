# QFBench Verifier Template Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish three corrected QFBench verifier templates and prove in live no-network E2B sandboxes that their official `if uvx` pytest environments are cached and executable.

**Architecture:** Keep the contaminated 2026-07-25 manifests immutable. Generate verifier-only manifests in a new repair directory using the fixed warm-command parser, add a verifier-only canary CLI that supplies empty artifacts to the trusted verifier, then publish and canary the three identities sequentially. A real pytest run with missing-output failures is successful cache evidence; the canary never calls a model or an oracle solution.

**Tech Stack:** Python 3.10+, pytest, E2B SDK, `.venv-nexau`, QFBench official shell/pytest verifiers, JSON lifecycle manifests.

## Global Constraints

- QFBench commit is exactly `024921eb507fcc0c4ffe3e0a96802724be1ae84a`.
- Repair only `delta-hedging-pnl-simulation`, `swap-curve-bootstrap-ois`, and `form4-cross-sectional-sale-pressure`.
- Reuse base template `h4d9iarzjjts2z472o8d` and base build `b82873ce-db6e-4269-a689-ecb9354bf207`.
- Do not overwrite `output/qfbench-e2b-images/20260725_30x5_024921eb/`.
- Do not run workers, call model providers, repair historical scores, upload or run official solutions, or modify the evolve agent.
- Live verifiers use `envs={}` and `allow_internet_access=False`.
- Preserve unrelated workspace changes and commit exact task files only.

---

### Task 1: Lock the `if uvx` Parser Repair

**Files:**
- Modify: `qea/qfbench_images.py:185-203`
- Test: `tests/test_qfbench_images.py:226-265`

**Interfaces:**
- Consumes: official `tests/test.sh` text through `_verifier_uvx_tokens(test_script: str)`.
- Produces: a non-null warm/lock command or `ImageConfigError` for unrecognized `uvx` syntax.

- [ ] **Step 1: Confirm the existing regression tests cover both behaviors**

```python
def test_uvx_warm_command_accepts_official_if_uvx_wrapper():
    assert verifier_uvx_warm_command(official_if_uvx_script) == expected_warm_command


def test_uvx_warm_command_fails_closed_on_unknown_wrapper():
    with pytest.raises(ImageConfigError, match="cannot locate official uvx command"):
        verifier_uvx_warm_command(
            "command uvx -p 3.11 -w pytest==8.4.1 pytest /tests/test_outputs.py\n"
        )
```

- [ ] **Step 2: Run focused and full image tests**

```bash
.venv-nexau/bin/python -m pytest -q \
  tests/test_qfbench_images.py::test_uvx_warm_command_accepts_official_if_uvx_wrapper \
  tests/test_qfbench_images.py::test_uvx_warm_command_fails_closed_on_unknown_wrapper
.venv-nexau/bin/python -m pytest -q tests/test_qfbench_images.py
```

Expected: `2 passed`, then the complete image test file passes.

- [ ] **Step 3: Commit only the parser repair**

```bash
git add qea/qfbench_images.py tests/test_qfbench_images.py
git commit -m "fix(qfbench): warm shell-prefixed uvx verifiers"
```

### Task 2: Add Verifier-Only Canary Evidence Validation

**Files:**
- Create: `scripts/smoke_qfbench_e2b_verifier_template.py`
- Create: `tests/test_qfbench_verifier_canary.py`

**Interfaces:**
- Consumes: `OfficialTaskScore` and a persisted `attempts/<id>/verifier/` directory.
- Produces: `_assess_evidence(score, verifier_dir) -> dict` with acceptance, test count, dependency-lock/hash evidence, cleanup status, and failure reasons.

- [ ] **Step 1: Write failing evidence tests**

```python
import json

from qea.evaluation import OfficialTaskScore


def _evidence(tmp_path, *, stdout="2 failed", cleaned=True):
    verifier = tmp_path / "verifier"
    verifier.mkdir()
    (verifier / "verifier-requirements.lock").write_text("pytest==8.4.1\n")
    (verifier / "verifier-harness.json").write_text(json.dumps({
        "official_sha256": "a" * 64,
        "executed_sha256": "b" * 64,
        "dependency_lock_sha256": "c" * 64,
        "offline_transformed": True,
    }))
    (verifier / "verifier-command.trusted.json").write_text(json.dumps({
        "stdout": stdout, "stderr": "", "exit_code": 1,
    }))
    (verifier / "verifier-sandbox-lifecycle.json").write_text(json.dumps({
        "schema_version": 1, "sandbox_id": "sandbox-1", "cleaned_up": cleaned,
    }))
    return verifier


def test_assess_evidence_accepts_real_offline_pytest_failure(tmp_path):
    from scripts.smoke_qfbench_e2b_verifier_template import _assess_evidence

    score = OfficialTaskScore(
        task_id="delta-hedging-pnl-simulation",
        domain="derivatives",
        reward=0.0,
        diagnostic_tags=("tests_failed",),
        tests_passed=0,
        tests_failed=2,
    )
    result = _assess_evidence(score, _evidence(tmp_path))
    assert result["accepted"] is True
    assert result["tests_executed"] == 2


def test_assess_evidence_rejects_zero_tests_and_dependency_failure(tmp_path):
    from scripts.smoke_qfbench_e2b_verifier_template import _assess_evidence

    score = OfficialTaskScore(
        task_id="swap-curve-bootstrap-ois",
        domain="rates_fx_macro",
        reward=0.0,
        tests_passed=0,
        tests_failed=0,
    )
    verifier = _evidence(
        tmp_path,
        stdout=("No solution found when resolving tool dependencies. "
                "Packages were unavailable because the network was disabled."),
    )
    result = _assess_evidence(score, verifier)
    assert result["accepted"] is False
    assert "no official tests executed" in result["failure_reasons"]
    assert "offline dependency resolution failed" in result["failure_reasons"]
```

- [ ] **Step 2: Run the tests and verify RED**

```bash
.venv-nexau/bin/python -m pytest -q tests/test_qfbench_verifier_canary.py
```

Expected: collection fails because the canary module does not exist.

- [ ] **Step 3: Implement `_assess_evidence` minimally**

The script imports `OfficialTaskScore`, defines the two known dependency-failure markers, reads the command/harness/lifecycle JSON plus lock, and returns:

```python
{
    "task_id": score.task_id,
    "score": asdict(score),
    "tests_executed": tests_executed,
    "dependency_lock_sha256": hashlib.sha256(lock.encode()).hexdigest(),
    "sandbox_id": lifecycle.get("sandbox_id"),
    "cleaned_up": lifecycle.get("cleaned_up") is True,
    "failure_reasons": failures,
    "accepted": not failures,
}
```

Failures are added for zero tests, both dependency markers, an empty lock, missing official/executed/lock hashes, a non-offline harness, or an unclean lifecycle.

- [ ] **Step 4: Run the tests and verify GREEN**

```bash
.venv-nexau/bin/python -m pytest -q tests/test_qfbench_verifier_canary.py
```

Expected: `2 passed`.

### Task 3: Add the Paid Gate, Manifest Loader, and Canary Orchestration

**Files:**
- Modify: `scripts/smoke_qfbench_e2b_verifier_template.py`
- Modify: `tests/test_qfbench_verifier_canary.py`

**Interfaces:**
- Produces: `build_parser()`, `_load_verifier_templates(directory, tasks, commit)`, and `main(argv=None) -> int`.
- Persists: `results/qfbench_verifier_canary/<run-id>/canary-summary.json`.

- [ ] **Step 1: Write failing authorization and manifest tests**

```python
def test_main_refuses_to_start_without_paid_gate(tmp_path, capsys):
    from scripts import smoke_qfbench_e2b_verifier_template as canary

    result = canary.main([
        "--qfbench-root", str(tmp_path / "missing"),
        "--template-manifest-dir", str(tmp_path / "manifests"),
    ])
    assert result == 2
    assert "NOT STARTED" in capsys.readouterr().out


def test_load_verifier_templates_requires_published_matching_manifests(tmp_path):
    from scripts.smoke_qfbench_e2b_verifier_template import _load_verifier_templates

    task = SimpleNamespace(task_id="delta-hedging-pnl-simulation")
    (tmp_path / f"{task.task_id}.verifier.image.json").write_text(json.dumps({
        "task_id": task.task_id,
        "role": "verifier",
        "benchmark_commit": "0" * 40,
        "published_template_id": "template-1",
        "published_build_id": "build-1",
        "verifier_uvx_warm_command": "uvx -p 3.11 -w pytest pytest --version",
    }))
    assert _load_verifier_templates(tmp_path, (task,), "0" * 40) == {
        task.task_id: "template-1"
    }
```

- [ ] **Step 2: Run the tests and verify RED**

```bash
.venv-nexau/bin/python -m pytest -q tests/test_qfbench_verifier_canary.py
```

Expected: failures because the CLI and loader do not exist.

- [ ] **Step 3: Implement the parser and strict manifest loader**

```python
DEFAULT_TASKS = (
    "delta-hedging-pnl-simulation",
    "swap-curve-bootstrap-ois",
    "form4-cross-sectional-sale-pressure",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qfbench-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=default_manifest_path())
    parser.add_argument("--template-manifest-dir", type=Path, required=True)
    parser.add_argument("--task", action="append", dest="tasks")
    parser.add_argument(
        "--results-dir", type=Path, default=Path("results/qfbench_verifier_canary")
    )
    parser.add_argument("--run-id")
    parser.add_argument("--approve-paid-e2b", action="store_true")
    return parser


def _load_verifier_templates(directory: Path, tasks: tuple, commit: str) -> dict[str, str]:
    templates = {}
    for task in tasks:
        path = directory / f"{task.task_id}.verifier.image.json"
        payload = json.loads(path.read_text())
        expected = (task.task_id, "verifier", commit)
        actual = (payload.get("task_id"), payload.get("role"), payload.get("benchmark_commit"))
        if actual != expected:
            raise ValueError(f"verifier manifest identity mismatch: {path}")
        if not payload.get("verifier_uvx_warm_command"):
            raise ValueError(f"verifier manifest has no uvx warm command: {path}")
        template_id = payload.get("published_template_id")
        build_id = payload.get("published_build_id")
        if not template_id or not build_id:
            raise ValueError(f"verifier manifest is not published: {path}")
        templates[task.task_id] = str(template_id)
    return templates
```

- [ ] **Step 4: Add a failing orchestration test**

Monkeypatch the snapshot loader, manifest loader, lease pool, verifier, and reaper. Have the fake verifier persist valid evidence and record every empty artifact directory. Assert:

```python
assert observed_config.worker_templates == {}
assert observed_config.worker_allow_internet is False
assert observed_config.verifier_allow_internet is False
assert all(path.is_dir() and not tuple(path.iterdir()) for path in artifact_dirs)
assert summary["model_calls"] == 0
assert summary["worker_sandboxes"] == 0
assert summary["verifier_sandboxes_expected"] == 3
```

- [ ] **Step 5: Run the orchestration test and verify RED**

```bash
.venv-nexau/bin/python -m pytest -q tests/test_qfbench_verifier_canary.py
```

Expected: failure because `main()` does not execute the verifier canaries.

- [ ] **Step 6: Implement `main()`**

After an early `--approve-paid-e2b` check, load the pinned snapshot and the three published verifier IDs. Build:

```python
config = E2BNexAUConfig(
    worker_templates={},
    verifier_templates=templates,
    worker_allow_internet=False,
    verifier_allow_internet=False,
)
leases = E2BLeasePool(args.results_dir.resolve() / ".e2b-leases", max_leases=12)
verifier = E2BQFBenchVerifier(config, lease_pool=leases)
```

For each task, create a deterministic `TaskAttempt`, an empty artifact directory, and call:

```python
score = verifier.verify(
    attempt=attempt,
    task=task,
    execution=SimpleNamespace(artifact_dir=artifact_dir),
    run_dir=run_dir,
)
```

Catch per-task exceptions into an answer-free failed result so all three cleanup paths are audited. Run `reap_e2b_sandboxes(run_dir, kill_sandbox=lambda sandbox_id: False, apply=False)` and write:

```python
payload = {
    "schema_version": 1,
    "run_id": run_id,
    "benchmark_commit": snapshot.commit,
    "model_calls": 0,
    "worker_sandboxes": 0,
    "verifier_sandboxes_expected": len(tasks),
    "results": results,
    "final_pending_ids": list(reaper.pending_ids),
    "accepted": all(item["accepted"] for item in results) and not reaper.pending_ids,
}
```

Return `0` only when the payload is accepted, otherwise `1`.

- [ ] **Step 7: Verify GREEN and run related regressions**

```bash
.venv-nexau/bin/python -m pytest -q tests/test_qfbench_verifier_canary.py
.venv-nexau/bin/python -m pytest -q \
  tests/test_qfbench_images.py \
  tests/test_qfbench_isolation.py \
  tests/test_e2b_nexau_executor.py \
  tests/test_e2b_reaper.py \
  tests/test_qfbench_verifier_canary.py
```

Expected: all selected tests pass.

- [ ] **Step 8: Commit the canary CLI and tests**

```bash
git add scripts/smoke_qfbench_e2b_verifier_template.py tests/test_qfbench_verifier_canary.py
git commit -m "test(qfbench): add offline verifier template canary"
```

### Task 4: Generate and Audit Corrected Manifests Locally

**Files:**
- Generate: `output/qfbench-e2b-images/20260726_verifier_repair_024921eb/*.verifier.image.json`
- Preserve: `output/qfbench-e2b-images/20260725_30x5_024921eb/*.image.json`

**Interfaces:**
- Consumes: fixed parser, pinned snapshot, and old shared-base manifest.
- Produces: exactly three unpublished verifier identities.

- [ ] **Step 1: Run verifier-only dry generation**

```bash
.venv-nexau/bin/python scripts/build_qfbench_e2b_templates.py \
  --qfbench-root /private/tmp/qea-qfbench-30-024921eb \
  --manifest data/qfbench/MANIFEST_30.json \
  --base-manifest output/qfbench-e2b-images/20260725_30x5_024921eb/qfbench-base.image.json \
  --output-dir output/qfbench-e2b-images/20260726_verifier_repair_024921eb \
  --role verifier \
  --task delta-hedging-pnl-simulation \
  --task swap-curve-bootstrap-ois \
  --task form4-cross-sectional-sale-pressure
```

Expected: three prepared manifests and `dry run only`.

- [ ] **Step 2: Run machine-readable preflight assertions**

Assert:

```text
manifest count = 3
worker manifest count = 0
all commit values match 024921eb507fcc0c4ffe3e0a96802724be1ae84a
all roles equal verifier
all warm commands are non-null
all dependency-lock commands invoke uvx
all publication IDs are absent before publication
all base template/build IDs match the approved shared base
all new identity hashes differ from the contaminated identities
no generated path or manifest text contains solution/
```

- [ ] **Step 3: Re-run image tests after generation**

```bash
.venv-nexau/bin/python -m pytest -q tests/test_qfbench_images.py
```

Expected: all tests pass.

### Task 5: Publish Three Paid Verifier Templates

**Files:**
- Update: `output/qfbench-e2b-images/20260726_verifier_repair_024921eb/*.verifier.image.json`

**Interfaces:**
- Consumes: three preflight-approved identities.
- Produces: three immutable E2B verifier template/build pairs.

- [ ] **Step 1: Publish with only E2B authentication forwarded**

Run the Task 4 generation command with `--publish` in a clean child environment containing `E2B_API_KEY` but no `LLM_*`, OpenRouter, Anthropic, or OpenAI model credentials.

Expected: exactly three output records beginning with `published qea-qfbench-` and containing `-verifier-`. If interrupted, rerun the identical command; completed identities are reused.

- [ ] **Step 2: Audit publication fields**

Assert that all three manifests contain non-empty and unique `published_template_id` and `published_build_id`, retain their dry-run identity hashes, and contain 2026-07-26 publication timestamps.

- [ ] **Step 3: Persist an old/new publication comparison**

Write `results/qfbench_verifier_canary/verifier-cache-20260726/template-comparison.json`. Build each record by reading the old and new manifests and copying these exact keys: `task_id`, old/new `identity_sha256`, old/new `published_template_id`, old/new `published_build_id`, new `verifier_uvx_warm_command`, new `verifier_dependency_lock_command`, and new `published_at`. Do not hand-enter cloud IDs.

### Task 6: Run Three Live No-Network Canaries and Reap Exact IDs

**Files:**
- Generate: `results/qfbench_verifier_canary/verifier-cache-20260726/`

**Interfaces:**
- Consumes: three corrected published manifests.
- Produces: three verifier lifecycles plus `canary-summary.json`.

- [ ] **Step 1: Run the authorized canaries sequentially**

```bash
.venv-nexau/bin/python scripts/smoke_qfbench_e2b_verifier_template.py \
  --qfbench-root /private/tmp/qea-qfbench-30-024921eb \
  --manifest data/qfbench/MANIFEST_30.json \
  --template-manifest-dir output/qfbench-e2b-images/20260726_verifier_repair_024921eb \
  --results-dir results/qfbench_verifier_canary \
  --run-id verifier-cache-20260726 \
  --approve-paid-e2b
```

Run with only `E2B_API_KEY` forwarded. Expected: exit 0, `model_calls=0`, `worker_sandboxes=0`, three accepted results, and no pending IDs.

- [ ] **Step 2: Preview exact-ID cleanup**

```bash
.venv-nexau/bin/python scripts/reap_qfbench_e2b.py \
  --results-dir results/qfbench_verifier_canary/verifier-cache-20260726
```

Expected: `pending_ids=[]`. If exact IDs are listed, rerun with `--apply`, then preview again. Never perform account-wide cleanup.

- [ ] **Step 3: Independently audit live evidence**

For each task assert:

```text
tests_passed + tests_failed > 0
dependency lock is non-empty
dependency lock hash matches verifier-harness.json
offline_transformed = true
cleaned_up = true
no dependency-resolution failure markers
```

Do not interpret the intentional missing-output reward zero as a model score.

### Task 7: Record the Repair and Run Final Verification

**Files:**
- Create: `docs/decisions/2026-07-26-qfbench-verifier-template-repair.md`
- Modify: `docs/PROJECT_MEMORY.md`

**Interfaces:**
- Consumes: published manifests and `canary-summary.json`.
- Produces: a canonical decision and project-memory pointer while preserving the 2026-07-25 report.

- [ ] **Step 1: Write the decision record**

Record authorization, old/new IDs, exact warm/lock commands, three canary test counts, cleanup, zero model/worker/solution use, costs as measured or `not measured`, and the unrepaired 14-score boundary.

- [ ] **Step 2: Update project memory**

Add a 2026-07-26 entry pointing to the decision. State that future verifier templates are repaired but the 2026-07-25 scores remain provisional until a separately authorized superseding rescore.

- [ ] **Step 3: Run complete local verification**

```bash
.venv-nexau/bin/python -m pytest -q tests
.venv-nexau/bin/python -m compileall -q qea scripts tests
git diff --check
```

Expected: pytest, compileall, and diff check all exit 0.

- [ ] **Step 4: Verify final artifact scope**

Confirm:

```text
3 corrected verifier manifests
3 unique new template IDs
3 unique new build IDs
3 verifier canary lifecycles
0 worker/oracle lifecycles
all lifecycles cleaned
0 pending IDs
0 model-call artifacts
old manifests unchanged
14 historical scores unchanged
```

- [ ] **Step 5: Commit documentation only**

```bash
git add docs/decisions/2026-07-26-qfbench-verifier-template-repair.md docs/PROJECT_MEMORY.md
git commit -m "docs(qfbench): record verifier template repair"
```
