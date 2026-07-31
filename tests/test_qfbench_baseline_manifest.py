from collections import Counter
import json
from pathlib import Path

import pytest


REPOSITORY = Path(__file__).resolve().parents[1]
MANIFEST = REPOSITORY / "data/qfbench/MANIFEST_85_BASELINE.json"
PINNED_COMMIT = "024921eb507fcc0c4ffe3e0a96802724be1ae84a"
COPY_ORACLES = {
    "barrier-garch-var",
    "cta-basel-capital",
    "kelly-var-sizing",
    "regime-cta-vol-target",
    "regime-riskparity-cvar",
    "sec-10k-report-long",
    "sentiment-factor-alpha",
    "structured-note-risk",
}
FALLBACK_TASKS = {
    "barone-adesi-whaley",
    "bs-greeks-pde",
    "compound-option-geske",
    "copula-sampling-rank-correlation",
    "digital-barrier-options",
    "dupire-local-vol",
    "first-passage-time",
    "geometric-mean-reverting-jd",
    "lookback-options",
    "ohlc-realized-vol-estimators",
    "smith-tail-index",
}
FALLBACK_RESOURCES = {
    "agent_timeout_seconds": 2400,
    "verifier_timeout_seconds": 300,
    "build_timeout_seconds": 600,
    "cpus": 2,
    "memory_mb": 4096,
}


def test_repository_baseline_manifest_freezes_complete_universe() -> None:
    payload = json.loads(MANIFEST.read_text())
    baseline = payload["baseline"]
    primary = baseline["primary"]
    diagnostic = baseline["diagnostic"]

    assert payload["schema_version"] == 1
    assert payload["commit"] == PINNED_COMMIT
    assert len(primary) == 77
    assert len(diagnostic) == 8
    assert baseline["structural_exclusions"] == [{
        "task_id": "sec-8k-event-alpha",
        "reason": "official verifier raises before writing reward.txt at the pinned commit",
    }]
    assert Counter(item["domain"] for item in primary) == {
        "derivatives": 23,
        "risk_credit": 16,
        "systematic_strategy": 17,
        "rates_fx_macro": 11,
        "execution_microstructure": 5,
        "data_engineering": 5,
    }
    assert {item["task_id"] for item in diagnostic} == COPY_ORACLES
    assert {
        item["task_id"] for item in primary if item["resource_source"] == "qea_fallback"
    } == FALLBACK_TASKS
    assert all(
        item.get("resources") == FALLBACK_RESOURCES
        for item in primary
        if item["task_id"] in FALLBACK_TASKS
    )
    all_ids = [
        *(item["task_id"] for item in primary),
        *(item["task_id"] for item in diagnostic),
        *(item["task_id"] for item in baseline["structural_exclusions"]),
    ]
    assert len(all_ids) == len(set(all_ids)) == 86


def _write_task(root: Path, task_id: str, *, resources: bool = True) -> None:
    task = root / "tasks" / task_id
    (task / "environment/data").mkdir(parents=True)
    (task / "tests/reference_data").mkdir(parents=True)
    (task / "instruction.md").write_text("Write /root/output/result.json\n")
    resource_text = (
        "[verifier]\ntimeout_sec = 300\n"
        "[agent]\ntimeout_sec = 1800\n"
        "[environment]\nbuild_timeout_sec = 600\ncpus = 2\nmemory = '4G'\n"
        if resources
        else "[task]\nname = 'legacy-task'\n"
    )
    (task / "task.toml").write_text(resource_text)
    (task / "environment/Dockerfile").write_text("FROM python:3.12-slim\n")
    (task / "environment/data/input.csv").write_text(f"id\n{task_id}\n")
    (task / "tests/test.sh").write_text("pytest -q /tests/test_outputs.py\n")
    (task / "tests/test_outputs.py").write_text("def test_output(): pass\n")
    (task / "tests/reference_data/expected.json").write_text("{}\n")


def _entry(task_id: str, *, fallback: bool = False) -> dict:
    entry = {
        "task_id": task_id,
        "domain": "risk_credit",
        "lineage": task_id.replace("-", "_"),
        "difficulty": "medium",
        "reward_kind": "binary",
        "resource_source": "qea_fallback" if fallback else "upstream",
    }
    if fallback:
        entry["resources"] = dict(FALLBACK_RESOURCES)
    return entry


@pytest.fixture
def baseline_fixture(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "snapshot"
    root.mkdir()
    (root / ".qfbench-revision").write_text(PINNED_COMMIT + "\n")
    _write_task(root, "primary-task")
    _write_task(root, "barrier-garch-var")
    _write_task(root, "legacy-task", resources=False)
    _write_task(root, "sec-8k-event-alpha")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "schema_version": 1,
        "repository_url": "https://github.com/QF-Bench/QuantitativeFinance-Bench.git",
        "commit": PINNED_COMMIT,
        "copy_oracle_tasks": ["barrier-garch-var"],
        "inoperable_tasks": [{
            "task_id": "sec-8k-event-alpha",
            "reason": "official verifier is broken",
        }],
        "baseline": {
            "primary": [_entry("primary-task"), _entry("legacy-task", fallback=True)],
            "diagnostic": [_entry("barrier-garch-var")],
            "structural_exclusions": [{
                "task_id": "sec-8k-event-alpha",
                "reason": "official verifier is broken",
            }],
        },
    }))
    return root, manifest


def test_baseline_loader_allows_registered_diagnostic_copy_oracle_and_fallback(
    baseline_fixture: tuple[Path, Path],
) -> None:
    from qea.benchmarks.qfbench import load_qfbench_baseline_snapshot

    root, manifest = baseline_fixture
    snapshot = load_qfbench_baseline_snapshot(root, manifest_path=manifest)

    assert snapshot.primary.task_ids == ("primary-task", "legacy-task")
    assert snapshot.diagnostic.task_ids == ("barrier-garch-var",)
    assert snapshot.diagnostic.tasks[0].copy_oracle is True
    assert snapshot.task("legacy-task").cpus == 2
    assert snapshot.task("legacy-task").memory_mb == 4096
    assert snapshot.resource_fallback_task_ids == frozenset({"legacy-task"})
    assert snapshot.structural_exclusions == frozenset({"sec-8k-event-alpha"})


def test_baseline_loader_rejects_copy_oracle_in_primary(
    baseline_fixture: tuple[Path, Path],
) -> None:
    from qea.benchmarks.qfbench import QFBenchConfigError, load_qfbench_baseline_snapshot

    root, manifest = baseline_fixture
    payload = json.loads(manifest.read_text())
    payload["baseline"]["primary"][0] = _entry("barrier-garch-var")
    payload["baseline"]["diagnostic"] = [_entry("primary-task")]
    manifest.write_text(json.dumps(payload))

    with pytest.raises(QFBenchConfigError, match="copy-oracle.*primary"):
        load_qfbench_baseline_snapshot(root, manifest_path=manifest)


def test_baseline_loader_rejects_runnable_inoperable_task(
    baseline_fixture: tuple[Path, Path],
) -> None:
    from qea.benchmarks.qfbench import QFBenchConfigError, load_qfbench_baseline_snapshot

    root, manifest = baseline_fixture
    payload = json.loads(manifest.read_text())
    payload["baseline"]["diagnostic"][0] = _entry("sec-8k-event-alpha")
    manifest.write_text(json.dumps(payload))

    with pytest.raises(QFBenchConfigError, match="inoperable"):
        load_qfbench_baseline_snapshot(root, manifest_path=manifest)


def test_baseline_loader_requires_complete_fallback_resources(
    baseline_fixture: tuple[Path, Path],
) -> None:
    from qea.benchmarks.qfbench import QFBenchConfigError, load_qfbench_baseline_snapshot

    root, manifest = baseline_fixture
    payload = json.loads(manifest.read_text())
    del payload["baseline"]["primary"][1]["resources"]["memory_mb"]
    manifest.write_text(json.dumps(payload))

    with pytest.raises(QFBenchConfigError, match="fallback resource"):
        load_qfbench_baseline_snapshot(root, manifest_path=manifest)
