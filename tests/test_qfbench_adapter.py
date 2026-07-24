import json
from pathlib import Path
import subprocess
import sys

import pytest


PINNED_COMMIT = "024921eb507fcc0c4ffe3e0a96802724be1ae84a"


def _write_task(root: Path, task_id: str) -> None:
    task_root = root / "tasks" / task_id
    (task_root / "environment" / "data").mkdir(parents=True)
    (task_root / "tests" / "reference_data").mkdir(parents=True)
    (task_root / "solution").mkdir()
    (task_root / "instruction.md").write_text(
        f"Produce /root/output/{task_id}.json from the supplied data.\n"
    )
    (task_root / "task.toml").write_text(
        "version = '1.0'\n"
        "[verifier]\n"
        "timeout_sec = 300.0\n"
        "[agent]\n"
        "timeout_sec = 1800.0\n"
        "[environment]\n"
        "build_timeout_sec = 600.0\n"
        "cpus = 2\n"
        'memory = "4G"\n'
    )
    (task_root / "environment" / "Dockerfile").write_text(
        "FROM finance-bench-sandbox:latest\nCOPY data /root/data\n"
    )
    (task_root / "environment" / "data" / "input.csv").write_text(
        f"x\n{task_id}\n"
    )
    (task_root / "tests" / "test.sh").write_text("pytest -q /tests/test_outputs.py\n")
    (task_root / "tests" / "test_outputs.py").write_text("def test_output(): pass\n")
    (task_root / "tests" / "reference_data" / "expected.json").write_text("{}\n")
    (task_root / "solution" / "solve.sh").write_text("cp /solution/expected.json /root/output/x.json\n")


def _write_manifest(path: Path, *, heldout_lineage: str = "fx_cross_rate") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "schema_version": 1,
        "repository_url": "https://github.com/QF-Bench/QuantitativeFinance-Bench.git",
        "commit": PINNED_COMMIT,
        "inventory": {"tasks": 86, "binary_reward_tasks": 72, "partial_reward_tasks": 14},
        "copy_oracle_tasks": ["barrier-garch-var"],
        "pilot": {
            "optimize": [
                {
                    "task_id": "historical-var-data-prep",
                    "domain": "risk",
                    "lineage": "historical_var",
                    "difficulty": "easy",
                    "reward_kind": "binary",
                },
                {
                    "task_id": "evt-pot-var",
                    "domain": "risk",
                    "lineage": "evt_tail_risk",
                    "difficulty": "medium",
                    "reward_kind": "partial",
                },
            ],
            "held_out": [
                {
                    "task_id": "fx-forward-cross-rate",
                    "domain": "fx",
                    "lineage": heldout_lineage,
                    "difficulty": "easy",
                    "reward_kind": "binary",
                }
            ],
        },
    }, indent=2) + "\n")


@pytest.fixture
def qfbench_fixture(tmp_path):
    root = tmp_path / "qfbench"
    root.mkdir()
    (root / ".qfbench-revision").write_text(PINNED_COMMIT + "\n")
    for task_id in (
        "historical-var-data-prep",
        "evt-pot-var",
        "fx-forward-cross-rate",
        "barrier-garch-var",
    ):
        _write_task(root, task_id)
    manifest = tmp_path / "MANIFEST.json"
    _write_manifest(manifest)
    return root, manifest


def test_loads_pinned_pilot_split_and_separates_task_files(qfbench_fixture):
    from qea.benchmarks.qfbench import load_qfbench_snapshot

    root, manifest = qfbench_fixture
    snapshot = load_qfbench_snapshot(root, manifest_path=manifest)

    assert snapshot.commit == PINNED_COMMIT
    assert snapshot.optimize.task_ids == (
        "historical-var-data-prep",
        "evt-pot-var",
    )
    assert snapshot.held_out.task_ids == ("fx-forward-cross-rate",)

    task = snapshot.task("historical-var-data-prep")
    assert task.domain == "risk"
    assert task.lineage == "historical_var"
    assert task.reward_kind == "binary"
    assert task.copy_oracle is False
    assert task.agent_timeout_seconds == 1800
    assert task.verifier_timeout_seconds == 300
    assert task.build_timeout_seconds == 600
    assert task.cpus == 2
    assert task.memory_mb == 4096
    assert task.instruction_path == root / "tasks" / task.task_id / "instruction.md"
    assert tuple(path.relative_to(task.root).as_posix() for path in task.worker_files) == (
        "environment/data/input.csv",
        "instruction.md",
    )
    assert tuple(path.relative_to(task.root).as_posix() for path in task.verifier_files) == (
        "tests/reference_data/expected.json",
        "tests/test.sh",
        "tests/test_outputs.py",
    )
    assert all("solution" not in path.parts for path in task.worker_files + task.verifier_files)


def test_rejects_snapshot_commit_mismatch(qfbench_fixture):
    from qea.benchmarks.qfbench import QFBenchConfigError, load_qfbench_snapshot

    root, manifest = qfbench_fixture
    (root / ".qfbench-revision").write_text("0" * 40 + "\n")

    with pytest.raises(QFBenchConfigError, match="commit mismatch"):
        load_qfbench_snapshot(root, manifest_path=manifest)


def test_rejects_unknown_task_in_manifest(qfbench_fixture):
    from qea.benchmarks.qfbench import QFBenchConfigError, load_qfbench_snapshot

    root, manifest = qfbench_fixture
    payload = json.loads(manifest.read_text())
    payload["pilot"]["held_out"][0]["task_id"] = "not-in-snapshot"
    manifest.write_text(json.dumps(payload))

    with pytest.raises(QFBenchConfigError, match="not-in-snapshot"):
        load_qfbench_snapshot(root, manifest_path=manifest)


def test_rejects_lineage_overlap_between_optimize_and_heldout(qfbench_fixture):
    from qea.benchmarks.qfbench import QFBenchConfigError, load_qfbench_snapshot

    root, manifest = qfbench_fixture
    _write_manifest(manifest, heldout_lineage="historical_var")

    with pytest.raises(QFBenchConfigError, match="lineage overlap"):
        load_qfbench_snapshot(root, manifest_path=manifest)


def test_rejects_exact_input_hash_overlap_between_splits(qfbench_fixture):
    from qea.benchmarks.qfbench import QFBenchConfigError, load_qfbench_snapshot

    root, manifest = qfbench_fixture
    shared = b"date,value\n2025-01-01,1\n"
    (
        root
        / "tasks/historical-var-data-prep/environment/data/shared.csv"
    ).write_bytes(shared)
    (
        root
        / "tasks/fx-forward-cross-rate/environment/data/copied.csv"
    ).write_bytes(shared)

    with pytest.raises(QFBenchConfigError, match="input data hash overlap"):
        load_qfbench_snapshot(root, manifest_path=manifest)


def test_copy_oracle_task_cannot_enter_a_pilot_split(qfbench_fixture):
    from qea.benchmarks.qfbench import QFBenchConfigError, load_qfbench_snapshot

    root, manifest = qfbench_fixture
    payload = json.loads(manifest.read_text())
    payload["pilot"]["held_out"][0]["task_id"] = "barrier-garch-var"
    manifest.write_text(json.dumps(payload))

    with pytest.raises(QFBenchConfigError, match="copy-oracle"):
        load_qfbench_snapshot(root, manifest_path=manifest)


def test_inoperable_task_cannot_enter_a_pilot_split(qfbench_fixture):
    from qea.benchmarks.qfbench import QFBenchConfigError, load_qfbench_snapshot

    root, manifest = qfbench_fixture
    payload = json.loads(manifest.read_text())
    payload["inoperable_tasks"] = [{
        "task_id": "fx-forward-cross-rate",
        "reason": "official verifier does not emit reward.txt",
    }]
    manifest.write_text(json.dumps(payload))

    with pytest.raises(QFBenchConfigError, match="inoperable"):
        load_qfbench_snapshot(root, manifest_path=manifest)


def _git(path: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(path), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def test_materializes_exact_commit_and_refuses_dirty_cache(tmp_path):
    from qea.benchmarks.qfbench import QFBenchConfigError, materialize_qfbench_snapshot

    source = tmp_path / "source"
    source.mkdir()
    _git(source, "init")
    _git(source, "config", "user.email", "qfbench-test@example.invalid")
    _git(source, "config", "user.name", "QFBench Test")
    (source / "README.md").write_text("pinned snapshot\n")
    _git(source, "add", "README.md")
    _git(source, "commit", "-m", "fixture")
    commit = _git(source, "rev-parse", "HEAD")

    destination = tmp_path / "cache"
    materialize_qfbench_snapshot(str(source), destination, commit)

    assert _git(destination, "rev-parse", "HEAD") == commit
    assert (destination / ".qfbench-revision").read_text().strip() == commit
    assert (destination / ".qfbench-cache").is_file()

    (destination / "README.md").write_text("dirty\n")
    with pytest.raises(QFBenchConfigError, match="dirty"):
        materialize_qfbench_snapshot(str(source), destination, commit)


def test_materializer_resumes_initialized_cache_without_head(tmp_path):
    from qea.benchmarks.qfbench import materialize_qfbench_snapshot

    source = tmp_path / "source"
    source.mkdir()
    _git(source, "init")
    _git(source, "config", "user.email", "qfbench-test@example.invalid")
    _git(source, "config", "user.name", "QFBench Test")
    (source / "README.md").write_text("recoverable\n")
    _git(source, "add", "README.md")
    _git(source, "commit", "-m", "fixture")
    commit = _git(source, "rev-parse", "HEAD")

    destination = tmp_path / "cache"
    destination.mkdir()
    _git(destination, "init")
    _git(destination, "remote", "add", "origin", str(source))
    (destination / ".qfbench-cache").write_text("interrupted fetch\n")

    materialize_qfbench_snapshot(str(source), destination, commit)

    assert _git(destination, "rev-parse", "HEAD") == commit
    assert (destination / "README.md").read_text() == "recoverable\n"


def test_materializer_can_fetch_a_pilot_sparse_snapshot(tmp_path):
    from qea.benchmarks.qfbench import materialize_qfbench_snapshot

    source = tmp_path / "source"
    source.mkdir()
    _git(source, "init")
    _git(source, "config", "user.email", "qfbench-test@example.invalid")
    _git(source, "config", "user.name", "QFBench Test")
    (source / "docker").mkdir()
    (source / "docker" / "sandbox.Dockerfile").write_text("FROM python:3.11-slim\n")
    for task_id in ("task-a", "task-b"):
        task = source / "tasks" / task_id
        task.mkdir(parents=True)
        (task / "instruction.md").write_text(task_id + "\n")
    _git(source, "add", ".")
    _git(source, "commit", "-m", "fixture")
    commit = _git(source, "rev-parse", "HEAD")

    destination = tmp_path / "cache"
    materialize_qfbench_snapshot(
        str(source), destination, commit, task_ids=("task-a",)
    )

    assert (destination / "docker" / "sandbox.Dockerfile").is_file()
    assert (destination / "tasks" / "task-a" / "instruction.md").is_file()
    assert not (destination / "tasks" / "task-b").exists()
    assert json.loads((destination / ".qfbench-sparse-tasks.json").read_text()) == [
        "task-a"
    ]


def test_fetch_script_is_directly_invokable_from_repository_root():
    repository = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [sys.executable, "scripts/fetch_qfbench.py", "--help"],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "dedicated QFBench cache directory" in proc.stdout
    assert "--full" in proc.stdout
