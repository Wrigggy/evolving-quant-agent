from collections import Counter
import json
from pathlib import Path

import pytest


REPOSITORY = Path(__file__).resolve().parents[1]
EVOLUTION_MANIFEST = (
    REPOSITORY / "data/qfbench/MANIFEST_30_15_40_EVOLUTION.json"
)
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


def test_repository_evolution_manifest_freezes_exact_four_way_protocol() -> None:
    payload = json.loads(EVOLUTION_MANIFEST.read_text())
    protocol = payload["evolution"]
    panels = {
        name: tuple(item["task_id"] for item in protocol[name])
        for name in ("train", "validation", "test", "diagnostic")
    }

    assert payload["schema_version"] == 2
    assert payload["commit"] == PINNED_COMMIT
    assert {name: len(task_ids) for name, task_ids in panels.items()} == {
        "train": 30,
        "validation": 15,
        "test": 32,
        "diagnostic": 8,
    }
    assert sum(map(len, panels.values())) == 85
    assert len(set().union(*map(set, panels.values()))) == 85
    assert set(panels["diagnostic"]) == COPY_ORACLES
    assert not COPY_ORACLES & (
        set(panels["train"])
        | set(panels["validation"])
        | set(panels["test"])
    )
    assert protocol["structural_exclusions"] == [{
        "task_id": "sec-8k-event-alpha",
        "reason": (
            "official verifier raises before writing reward.txt at the pinned commit"
        ),
    }]
    assert Counter(item["domain"] for item in protocol["train"]) == {
        "data_engineering": 3,
        "derivatives": 8,
        "execution_microstructure": 3,
        "rates_fx_macro": 4,
        "risk_credit": 6,
        "systematic_strategy": 6,
    }
    assert Counter(item["domain"] for item in protocol["validation"]) == {
        "data_engineering": 1,
        "derivatives": 4,
        "execution_microstructure": 1,
        "rates_fx_macro": 3,
        "risk_credit": 3,
        "systematic_strategy": 3,
    }


def test_evolution_snapshot_loader_is_part_of_benchmark_public_api() -> None:
    from qea import benchmarks

    assert benchmarks.QFBenchEvolutionSnapshot.__name__ == (
        "QFBenchEvolutionSnapshot"
    )
    assert callable(benchmarks.load_qfbench_evolution_snapshot)


def _write_task(root: Path, task_id: str) -> None:
    task = root / "tasks" / task_id
    (task / "environment/data").mkdir(parents=True)
    (task / "tests/reference_data").mkdir(parents=True)
    (task / "instruction.md").write_text("Write /root/output/result.json\n")
    (task / "task.toml").write_text(
        "[verifier]\ntimeout_sec = 300\n"
        "[agent]\ntimeout_sec = 1800\n"
        "[environment]\nbuild_timeout_sec = 600\ncpus = 2\nmemory = '4G'\n"
    )
    (task / "environment/Dockerfile").write_text("FROM python:3.12-slim\n")
    (task / "environment/data/input.csv").write_text(f"id\n{task_id}\n")
    (task / "tests/test.sh").write_text("pytest -q /tests/test_outputs.py\n")
    (task / "tests/test_outputs.py").write_text("def test_output(): pass\n")
    (task / "tests/reference_data/expected.json").write_text("{}\n")


def _entry(task_id: str, domain: str, *, copy_oracle: bool = False) -> dict:
    entry = {
        "task_id": task_id,
        "domain": domain,
        "lineage": task_id.replace("-", "_"),
        "difficulty": "medium",
        "reward_kind": "binary",
        "resource_source": "upstream",
    }
    if copy_oracle:
        assert task_id == "diagnostic-task"
    return entry


@pytest.fixture
def evolution_fixture(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "snapshot"
    root.mkdir()
    (root / ".qfbench-revision").write_text(PINNED_COMMIT + "\n")
    for task_id in (
        "train-task",
        "validation-task",
        "test-task",
        "diagnostic-task",
        "sec-8k-event-alpha",
    ):
        _write_task(root, task_id)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "schema_version": 2,
        "repository_url": "https://github.com/QF-Bench/QuantitativeFinance-Bench.git",
        "commit": PINNED_COMMIT,
        "copy_oracle_tasks": ["diagnostic-task"],
        "inoperable_tasks": [{
            "task_id": "sec-8k-event-alpha",
            "reason": "official verifier is broken",
        }],
        "evolution": {
            "train": [_entry("train-task", "risk_credit")],
            "validation": [_entry("validation-task", "rates_fx_macro")],
            "test": [_entry("test-task", "derivatives")],
            "diagnostic": [
                _entry("diagnostic-task", "systematic_strategy", copy_oracle=True)
            ],
            "structural_exclusions": [{
                "task_id": "sec-8k-event-alpha",
                "reason": "official verifier is broken",
            }],
        },
    }, indent=2) + "\n")
    return root, manifest


def test_evolution_loader_exposes_four_disjoint_splits(
    evolution_fixture: tuple[Path, Path],
) -> None:
    from qea.benchmarks.qfbench import load_qfbench_evolution_snapshot

    root, manifest = evolution_fixture
    snapshot = load_qfbench_evolution_snapshot(root, manifest_path=manifest)

    assert snapshot.train.task_ids == ("train-task",)
    assert snapshot.validation.task_ids == ("validation-task",)
    assert snapshot.test.task_ids == ("test-task",)
    assert snapshot.diagnostic.task_ids == ("diagnostic-task",)
    assert tuple(task.task_id for task in snapshot.tasks) == (
        "train-task",
        "validation-task",
        "test-task",
        "diagnostic-task",
    )
    assert snapshot.task("diagnostic-task").copy_oracle is True
    assert snapshot.structural_exclusions == frozenset({"sec-8k-event-alpha"})


def test_evolution_loader_rejects_copy_oracle_outside_diagnostic(
    evolution_fixture: tuple[Path, Path],
) -> None:
    from qea.benchmarks.qfbench import (
        QFBenchConfigError,
        load_qfbench_evolution_snapshot,
    )

    root, manifest = evolution_fixture
    payload = json.loads(manifest.read_text())
    payload["evolution"]["train"][0]["task_id"] = "diagnostic-task"
    payload["evolution"]["diagnostic"][0]["task_id"] = "train-task"
    manifest.write_text(json.dumps(payload))

    with pytest.raises(QFBenchConfigError, match="copy-oracle.*train"):
        load_qfbench_evolution_snapshot(root, manifest_path=manifest)


def test_evolution_loader_rejects_cross_panel_lineage_overlap(
    evolution_fixture: tuple[Path, Path],
) -> None:
    from qea.benchmarks.qfbench import (
        QFBenchConfigError,
        load_qfbench_evolution_snapshot,
    )

    root, manifest = evolution_fixture
    payload = json.loads(manifest.read_text())
    payload["evolution"]["validation"][0]["lineage"] = "train_task"
    manifest.write_text(json.dumps(payload))

    with pytest.raises(QFBenchConfigError, match="lineage overlap"):
        load_qfbench_evolution_snapshot(root, manifest_path=manifest)


def test_evolution_loader_allows_shared_data_file_across_distinct_tasks(
    evolution_fixture: tuple[Path, Path],
) -> None:
    from qea.benchmarks.qfbench import load_qfbench_evolution_snapshot

    root, manifest = evolution_fixture
    train = root / "tasks/train-task"
    validation = root / "tasks/validation-task"
    validation.joinpath("environment/data/input.csv").write_bytes(
        train.joinpath("environment/data/input.csv").read_bytes()
    )
    train.joinpath("instruction.md").write_text("Produce the train risk report.\n")
    validation.joinpath("instruction.md").write_text(
        "Price the validation rates instrument.\n"
    )

    snapshot = load_qfbench_evolution_snapshot(root, manifest_path=manifest)

    assert snapshot.train.task_ids == ("train-task",)
    assert snapshot.validation.task_ids == ("validation-task",)


def test_evolution_loader_rejects_exact_public_task_bundle_overlap(
    evolution_fixture: tuple[Path, Path],
) -> None:
    from qea.benchmarks.qfbench import (
        QFBenchConfigError,
        load_qfbench_evolution_snapshot,
    )

    root, manifest = evolution_fixture
    train = root / "tasks/train-task"
    validation = root / "tasks/validation-task"
    validation.joinpath("environment/data/input.csv").write_bytes(
        train.joinpath("environment/data/input.csv").read_bytes()
    )

    with pytest.raises(QFBenchConfigError, match="public task bundle overlap"):
        load_qfbench_evolution_snapshot(root, manifest_path=manifest)
