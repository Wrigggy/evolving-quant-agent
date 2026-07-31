from __future__ import annotations

import json
import stat
import subprocess
import sys
from pathlib import Path

import pytest


def _git(repository: Path, *args: str) -> str:
    result = subprocess.run(
        ("git", "-C", str(repository), *args),
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _write_source(tmp_path: Path, *, unknown_path: bool = False) -> tuple[Path, str]:
    source = tmp_path / "source"
    source.mkdir()
    _git(source, "init")
    _git(source, "config", "user.email", "qfbench-test@example.invalid")
    _git(source, "config", "user.name", "QFBench Test")
    docker = source / "docker"
    docker.mkdir()
    (docker / "sandbox.Dockerfile").write_text("FROM python:3.12-slim\n")
    (docker / "requirements-sandbox.txt").write_text("numpy==2.0.0\n")
    task = source / "tasks" / "task-a"
    (task / "environment" / "data").mkdir(parents=True)
    (task / "tests" / "reference_data").mkdir(parents=True)
    (task / "solution").mkdir(parents=True)
    (task / "instruction.md").write_text("Create /root/output/result.json\n")
    (task / "task.toml").write_text(
        "[agent]\ntimeout_sec = 900\n"
        "[verifier]\ntimeout_sec = 300\n"
        "[environment]\ncpus = 2\nmemory = '4G'\nbuild_timeout_sec = 600\n"
    )
    (task / "environment" / "Dockerfile").write_text(
        "FROM finance-bench-sandbox:latest\n"
    )
    (task / "environment" / "data" / "input.csv").write_text("x\n1\n")
    test_script = task / "tests" / "test.sh"
    test_script.write_text("pytest -q /tests/test_outputs.py\n")
    test_script.chmod(0o755)
    (task / "tests" / "test_outputs.py").write_text(
        "def test_output(): pass\n"
    )
    (task / "tests" / "reference_data" / "expected.json").write_text(
        '{"expected": 17}\n'
    )
    solution = task / "solution" / "solve.sh"
    solution.write_text("#!/bin/sh\nexit 0\n")
    solution.chmod(0o755)
    if unknown_path:
        (task / "private-answer.txt").write_text("must not be silently copied\n")
    _git(source, "add", ".")
    _git(source, "commit", "-m", "fixture")
    return source, _git(source, "rev-parse", "HEAD")


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("docker/sandbox.Dockerfile", "public"),
        ("docker/solution/solve.py", "deny"),
        ("docker/.env", "deny"),
        ("tasks/task-a/instruction.md", "public"),
        ("tasks/task-a/task.toml", "public"),
        ("tasks/task-a/environment/Dockerfile", "public"),
        ("tasks/task-a/environment/data/input.csv", "public"),
        ("tasks/task-a/tests/test.sh", "trusted-verifier"),
        ("tasks/task-a/tests/reference_data/expected.json", "trusted-verifier"),
        ("tasks/task-a/solution/solve.sh", "deny"),
        ("tasks/task-a/private-answer.txt", "deny"),
        ("tasks/task-b/instruction.md", "deny"),
        ("../tasks/task-a/instruction.md", "deny"),
        ("/tasks/task-a/instruction.md", "deny"),
    ],
)
def test_classifies_qfbench_paths_by_role(path: str, expected: str) -> None:
    from qea.benchmarks.qfbench import classify_qfbench_path

    assert classify_qfbench_path(path, task_ids=("task-a",)) == expected


def test_materializes_disjoint_public_and_trusted_roots_without_solution(tmp_path) -> None:
    from qea.benchmarks.qfbench import materialize_qfbench_role_snapshot

    source, commit = _write_source(tmp_path)
    public_root = tmp_path / "public"
    trusted_root = tmp_path / "trusted"

    result = materialize_qfbench_role_snapshot(
        source,
        public_root,
        trusted_root,
        repository_url="https://github.com/QF-Bench/QuantitativeFinance-Bench.git",
        commit=commit,
        task_ids=("task-a",),
        fetch_blob=lambda path: (source / path).read_bytes(),
    )

    assert result.public_root == public_root.resolve()
    assert result.trusted_root == trusted_root.resolve()
    assert (public_root / "docker/sandbox.Dockerfile").is_file()
    assert (public_root / "tasks/task-a/instruction.md").is_file()
    assert (public_root / "tasks/task-a/task.toml").is_file()
    assert (public_root / "tasks/task-a/environment/data/input.csv").is_file()
    assert not (public_root / "tasks/task-a/tests").exists()
    assert not (public_root / "tasks/task-a/solution").exists()
    assert (trusted_root / "tasks/task-a/tests/test.sh").is_file()
    assert (trusted_root / "tasks/task-a/tests/reference_data/expected.json").is_file()
    assert not (trusted_root / "tasks/task-a/environment").exists()
    assert not (trusted_root / "tasks/task-a/solution").exists()

    public_manifest = json.loads((public_root / "MANIFEST.json").read_text())
    trusted_manifest = json.loads((trusted_root / "MANIFEST.json").read_text())
    assert public_manifest["role"] == "public"
    assert trusted_manifest["role"] == "trusted-verifier"
    assert public_manifest["commit"] == commit
    assert trusted_manifest["commit"] == commit
    assert all("/tests/" not in item["path"] for item in public_manifest["files"])
    assert all(
        "/tests/" in item["path"] for item in trusted_manifest["files"]
    )
    combined_manifest = json.dumps([public_manifest, trusted_manifest])
    assert "solution" not in combined_manifest
    assert {item["git_blob_oid"] for item in public_manifest["files"]}
    assert {item["sha256"] for item in trusted_manifest["files"]}
    assert not public_root.with_name("public.partial").exists()
    assert not trusted_root.with_name("trusted.partial").exists()
    assert stat.S_IMODE(trusted_root.stat().st_mode) == 0o700
    assert {
        stat.S_IMODE(path.stat().st_mode)
        for path in trusted_root.rglob("*")
        if path.is_dir()
    } == {0o700}
    assert {
        stat.S_IMODE(path.stat().st_mode)
        for path in trusted_root.rglob("*")
        if path.is_file()
    } == {0o600}


def test_materializer_rejects_wrong_blob_without_promoting_either_root(tmp_path) -> None:
    from qea.benchmarks.qfbench import (
        QFBenchConfigError,
        materialize_qfbench_role_snapshot,
    )

    source, commit = _write_source(tmp_path)
    public_root = tmp_path / "public"
    trusted_root = tmp_path / "trusted"

    with pytest.raises(QFBenchConfigError, match="Git blob hash mismatch"):
        materialize_qfbench_role_snapshot(
            source,
            public_root,
            trusted_root,
            repository_url="https://github.com/QF-Bench/QuantitativeFinance-Bench.git",
            commit=commit,
            task_ids=("task-a",),
            fetch_blob=lambda path: (
                b"corrupt\n"
                if path.endswith("instruction.md")
                else (source / path).read_bytes()
            ),
        )

    assert not public_root.exists()
    assert not trusted_root.exists()


def test_materializer_fails_closed_on_unknown_task_root_path(tmp_path) -> None:
    from qea.benchmarks.qfbench import (
        QFBenchConfigError,
        plan_qfbench_role_snapshot,
    )

    source, commit = _write_source(tmp_path, unknown_path=True)

    with pytest.raises(QFBenchConfigError, match="unexpected task path"):
        plan_qfbench_role_snapshot(
            source,
            repository_url="https://github.com/QF-Bench/QuantitativeFinance-Bench.git",
            commit=commit,
            task_ids=("task-a",),
        )


def test_materializer_plans_from_bare_object_store(tmp_path) -> None:
    from qea.benchmarks.qfbench import plan_qfbench_role_snapshot

    source, commit = _write_source(tmp_path)
    bare = tmp_path / "source.git"
    subprocess.run(
        ("git", "clone", "--bare", str(source), str(bare)),
        check=True,
        capture_output=True,
        text=True,
    )

    plan = plan_qfbench_role_snapshot(
        bare,
        repository_url="https://github.com/QF-Bench/QuantitativeFinance-Bench.git",
        commit=commit,
        task_ids=("task-a",),
    )

    assert {blob.path for blob in plan.public_blobs} >= {
        "docker/sandbox.Dockerfile",
        "tasks/task-a/instruction.md",
    }
    assert {blob.path for blob in plan.trusted_verifier_blobs} >= {
        "tasks/task-a/tests/test.sh",
    }
    assert {blob.path for blob in plan.denied_solution_blobs} == {
        "tasks/task-a/solution/solve.sh",
    }


def test_materializer_rejects_git_symlinks_before_fetch(tmp_path) -> None:
    from qea.benchmarks.qfbench import (
        QFBenchConfigError,
        plan_qfbench_role_snapshot,
    )

    source, _ = _write_source(tmp_path)
    symlink = source / "tasks" / "task-a" / "environment" / "linked.csv"
    symlink.symlink_to("data/input.csv")
    _git(source, "add", ".")
    _git(source, "commit", "-m", "add symlink")
    commit = _git(source, "rev-parse", "HEAD")

    with pytest.raises(QFBenchConfigError, match="regular files"):
        plan_qfbench_role_snapshot(
            source,
            repository_url="https://github.com/QF-Bench/QuantitativeFinance-Bench.git",
            commit=commit,
            task_ids=("task-a",),
        )


def test_rootless_materializer_cli_plans_without_downloading(tmp_path) -> None:
    source, commit = _write_source(tmp_path)
    manifest = tmp_path / "panel.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "repository_url": "https://github.com/QF-Bench/QuantitativeFinance-Bench.git",
                "commit": commit,
                "pilot": {
                    "optimize": [{"task_id": "task-a"}],
                    "held_out": [],
                },
            }
        )
    )
    public_root = tmp_path / "public"
    trusted_root = tmp_path / "trusted"
    repository = Path(__file__).resolve().parents[1]

    result = subprocess.run(
        (
            sys.executable,
            "scripts/materialize_qfbench_rootless_snapshot.py",
            "--source-tree",
            str(source),
            "--task-panel-manifest",
            str(manifest),
            "--public-root",
            str(public_root),
            "--trusted-root",
            str(trusted_root),
            "--plan-only",
        ),
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "public files:" in result.stdout
    assert "trusted verifier files:" in result.stdout
    assert "denied solution files: 1" in result.stdout
    assert not public_root.exists()
    assert not trusted_root.exists()


def test_rootless_materializer_cli_accepts_baseline_panels_without_exclusions(
    tmp_path,
) -> None:
    source, commit = _write_source(tmp_path)
    manifest = tmp_path / "baseline-panel.json"
    manifest.write_text(json.dumps({
        "schema_version": 1,
        "repository_url": "https://github.com/QF-Bench/QuantitativeFinance-Bench.git",
        "commit": commit,
        "baseline": {
            "primary": [{"task_id": "task-a"}],
            "diagnostic": [],
            "structural_exclusions": [{"task_id": "task-b", "reason": "broken"}],
        },
    }))
    repository = Path(__file__).resolve().parents[1]

    result = subprocess.run(
        (
            sys.executable,
            "scripts/materialize_qfbench_rootless_snapshot.py",
            "--source-tree", str(source),
            "--task-panel-manifest", str(manifest),
            "--public-root", str(tmp_path / "public"),
            "--trusted-root", str(tmp_path / "trusted"),
            "--plan-only",
        ),
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "tasks: 1" in result.stdout
