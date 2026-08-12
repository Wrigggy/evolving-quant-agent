import hashlib
import json
import subprocess
from pathlib import Path

import pytest


PUBLIC_TRACK = (
    "T01", "T12", "T16", "T18", "T19",
    "T24", "T26", "T27", "T28", "T29",
)


def _git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def _source_fixture(tmp_path: Path) -> tuple[Path, str, str]:
    source = tmp_path / "source"
    source.mkdir()
    _git(source, "init")
    _git(source, "config", "user.email", "qce-test@example.invalid")
    _git(source, "config", "user.name", "QuantCodeEval Test")

    task = source / "tasks" / "T16"
    (task / "data").mkdir(parents=True)
    (task / "checkers").mkdir()
    (source / "scripts").mkdir()
    (source / "quantcodeeval" / "diff_fuzz").mkdir(parents=True)
    (source / "pyproject.toml").write_text("[project]\nname = 'qce-fixture'\n")
    (source / "uv.lock").write_text("version = 1\n")
    (task / "sample_instruction.md").write_text("Implement the strategy.\n")
    (task / "paper_text.md").write_text("A public paper.\n")
    data = task / "data" / "ff3.csv"
    data.write_text("date,mktrf\n2020-01-31,0.01\n")
    data_sha = hashlib.sha256(data.read_bytes()).hexdigest()
    checker_manifest = {
        "task_id": "T16",
        "checkers": [
            {"property_id": "A2", "directory": "a2"},
            {"property_id": "B1", "directory": "b1"},
        ],
    }
    (task / "checkers" / "manifest.json").write_text(json.dumps(checker_manifest))
    (task / "checkers" / "run_all.py").write_text(
        "import sys\n"
        "try:\n    pass\n"
        "except Exception as e:\n    row = {\"detail\": str(e),}\n"
    )
    (task / "checkers" / "shared").mkdir()
    (task / "checkers" / "shared" / "module_loader.py").write_text(
        "def load_module(path):\n    return None\n"
    )
    (source / "scripts" / "run_checker_harness.py").write_text("raise SystemExit(0)\n")
    (source / "quantcodeeval" / "__init__.py").write_text("\n")
    (source / "quantcodeeval" / "diff_fuzz" / "__init__.py").write_text("\n")
    (source / "quantcodeeval" / "diff_fuzz" / "harness.py").write_text(
        "from pathlib import Path\n"
        "from types import ModuleType\n"
        "def _import_from_path(path: Path, module_name: str) -> ModuleType:\n"
        "    raise RuntimeError('fixture')\n"
    )

    # These are deliberately present upstream and must enter neither role.
    (task / "golden_ref.py").write_text("SECRET = 17\n")
    (task / "strategy_digest.md").write_text("gold strategy\n")
    (task / "properties").mkdir()
    (task / "properties" / "type_b.json").write_text('{"answer": 17}\n')
    public_track = {
        "schema_version": 1,
        "status": "PASS",
        "track": "fully-public",
        "task_ids": list(PUBLIC_TRACK),
        "tasks": {
            "T16": {
                "input_files": [{
                    "path": "tasks/T16/data/ff3.csv",
                    "bytes": data.stat().st_size,
                    "sha256": data_sha,
                    "manifest_sha256_verified": True,
                }],
            },
        },
    }
    track_path = source / "public_track_manifest.json"
    track_path.write_text(json.dumps(public_track, sort_keys=True) + "\n")
    track_sha = hashlib.sha256(track_path.read_bytes()).hexdigest()
    _git(source, "add", ".")
    _git(source, "commit", "-m", "fixture")
    return source, _git(source, "rev-parse", "HEAD"), track_sha


def _manifest(tmp_path: Path, commit: str, track_sha: str) -> Path:
    source = tmp_path / "source"
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "schema_version": 1,
        "repository_url": "https://example.invalid/quantcodeeval",
        "commit": commit,
        "public_track_manifest_sha256": track_sha,
        "upstream_environment": {
            "python": "3.11.15",
            "pyproject_sha256": hashlib.sha256(
                (source / "pyproject.toml").read_bytes()
            ).hexdigest(),
            "uv_lock_sha256": hashlib.sha256(
                (source / "uv.lock").read_bytes()
            ).hexdigest(),
        },
        "trusted_runtime": {
            "T16": {
                "golden_ref_sha256": hashlib.sha256(
                    (source / "tasks" / "T16" / "golden_ref.py").read_bytes()
                ).hexdigest(),
            },
        },
        "pilot": {
            "optimize": [{
                "task_id": "T16",
                "domain": "volatility",
                "lineage": "volatility-managed",
                "difficulty": "paper_reproduction",
                "reward_kind": "binary_all_properties",
                "agent_timeout_seconds": 60,
                "verifier_timeout_seconds": 60,
                "build_timeout_seconds": 60,
                "cpus": 1,
                "memory_mb": 512,
            }],
            "held_out": [],
        },
    }))
    return manifest


def _file_members(root: Path) -> set[str]:
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_materializer_separates_public_inputs_from_trusted_checkers(tmp_path):
    from qea.benchmarks.quantcodeeval import (
        load_quantcodeeval_snapshot,
        materialize_quantcodeeval_role_snapshot,
    )

    source, commit, track_sha = _source_fixture(tmp_path)
    manifest = _manifest(tmp_path, commit, track_sha)
    public = tmp_path / "public"
    trusted = tmp_path / "trusted"
    result = materialize_quantcodeeval_role_snapshot(
        source, public, trusted, manifest_path=manifest
    )

    assert result.public_root == public
    public_members = _file_members(public)
    trusted_members = _file_members(trusted)
    assert "tasks/T16/instruction.md" in public_members
    assert "tasks/T16/environment/data/paper_text.md" in public_members
    assert "tasks/T16/environment/data/ff3.csv" in public_members
    assert "tasks/T16/tests/checkers/manifest.json" in trusted_members
    assert "tasks/T16/tests/data/ff3.csv" in trusted_members
    assert "tasks/T16/tests/test.sh" in trusted_members
    assert not any("golden_ref" in item for item in public_members)
    assert "tasks/T16/tests/golden_ref.py" in trusted_members
    assert not any("strategy_digest" in item for item in public_members | trusted_members)
    assert not any("properties" in item for item in public_members | trusted_members)
    assert "SECRET = 17" not in "\n".join(
        path.read_text(errors="ignore")
        for path in public.rglob("*")
        if path.is_file()
    )
    assert all(
        path.stat().st_mode & 0o077 == 0
        for path in trusted.rglob("*")
        if path.is_file()
    )

    snapshot = load_quantcodeeval_snapshot(public, manifest_path=manifest)
    assert snapshot.commit == commit
    assert snapshot.optimize.task_ids == ("T16",)
    assert snapshot.held_out.tasks == ()
    assert snapshot.task("T16").reward_kind == "binary_all_properties"


def test_task_panel_can_select_a_pinned_public_task_without_a_new_oracle_hash(
    tmp_path,
):
    from qea.benchmarks.quantcodeeval import (
        load_quantcodeeval_snapshot,
        materialize_quantcodeeval_role_snapshot,
    )

    source, commit, track_sha = _source_fixture(tmp_path)
    manifest = _manifest(tmp_path, commit, track_sha)
    protocol = json.loads(manifest.read_text())
    protocol["trusted_runtime"] = {}
    manifest.write_text(json.dumps(protocol))
    panel = tmp_path / "panel.json"
    panel.write_text(json.dumps({
        "schema_version": 1,
        "name": "expansion-smoke",
        "optimize": [{
            "task_id": "T16",
            "domain": "panel_override",
            "lineage": "public-pinned-task",
            "difficulty": "paper_reproduction",
            "reward_kind": "binary_all_properties",
            "agent_timeout_seconds": 60,
            "verifier_timeout_seconds": 60,
            "build_timeout_seconds": 60,
            "cpus": 1,
            "memory_mb": 512,
        }],
        "held_out": [],
    }))

    public = tmp_path / "public-panel"
    trusted = tmp_path / "trusted-panel"
    materialize_quantcodeeval_role_snapshot(
        source,
        public,
        trusted,
        manifest_path=manifest,
        task_panel_path=panel,
    )
    snapshot = load_quantcodeeval_snapshot(
        public,
        manifest_path=manifest,
        task_panel_path=panel,
    )

    assert snapshot.optimize.task_ids == ("T16",)
    assert snapshot.task("T16").domain == "panel_override"
    assert (trusted / "tasks/T16/tests/golden_ref.py").is_file()


def test_snapshot_loader_rejects_manifested_file_tamper(tmp_path):
    from qea.benchmarks.quantcodeeval import (
        QuantCodeEvalConfigError,
        load_quantcodeeval_snapshot,
        materialize_quantcodeeval_role_snapshot,
    )

    source, commit, track_sha = _source_fixture(tmp_path)
    manifest = _manifest(tmp_path, commit, track_sha)
    public = tmp_path / "public"
    materialize_quantcodeeval_role_snapshot(
        source, public, tmp_path / "trusted", manifest_path=manifest
    )
    (public / "tasks" / "T16" / "instruction.md").write_text("tampered\n")
    with pytest.raises(QuantCodeEvalConfigError, match="role record mismatch"):
        load_quantcodeeval_snapshot(public, manifest_path=manifest)


def test_materializer_rejects_manifest_bound_data_drift(tmp_path):
    from qea.benchmarks.quantcodeeval import (
        QuantCodeEvalConfigError,
        materialize_quantcodeeval_role_snapshot,
    )

    source, commit, track_sha = _source_fixture(tmp_path)
    manifest = _manifest(tmp_path, commit, track_sha)
    # Amend both the source commit and protocol commit, while retaining the old
    # public-track input digest: role materialization must still fail closed.
    (source / "tasks" / "T16" / "data" / "ff3.csv").write_text("tampered\n")
    _git(source, "add", ".")
    _git(source, "commit", "-m", "tamper")
    payload = json.loads(manifest.read_text())
    payload["commit"] = _git(source, "rev-parse", "HEAD")
    manifest.write_text(json.dumps(payload))

    with pytest.raises(QuantCodeEvalConfigError, match="source digest mismatch"):
        materialize_quantcodeeval_role_snapshot(
            source,
            tmp_path / "public-drift",
            tmp_path / "trusted-drift",
            manifest_path=manifest,
        )


def test_materializer_rejects_dirty_consumed_source(tmp_path):
    from qea.benchmarks.quantcodeeval import (
        QuantCodeEvalConfigError,
        materialize_quantcodeeval_role_snapshot,
    )

    source, commit, track_sha = _source_fixture(tmp_path)
    manifest = _manifest(tmp_path, commit, track_sha)
    (source / "tasks" / "T16" / "sample_instruction.md").write_text(
        "Modified outside the pinned commit.\n"
    )

    with pytest.raises(QuantCodeEvalConfigError, match="differs from the pinned commit"):
        materialize_quantcodeeval_role_snapshot(
            source,
            tmp_path / "public-dirty",
            tmp_path / "trusted-dirty",
            manifest_path=manifest,
        )


def _checker_payload(verdicts):
    rows = [
        {"property_id": property_id, "verdict": verdict, "detail": "secret"}
        for property_id, verdict in verdicts
    ]
    return {
        "target": "strategy.py",
        "total": len(rows),
        "pass": sum(row["verdict"] == "PASS" for row in rows),
        "fail": sum(row["verdict"] in {"FAIL", "ERROR"} for row in rows),
        "skip": sum(row["verdict"] == "SKIP" for row in rows),
        "results": rows,
    }


def test_score_is_binary_but_retains_property_progress_counts(tmp_path):
    from qea.verifiers.quantcodeeval import (
        parse_official_quantcodeeval_score,
        quantcodeeval_answer_free_summary,
    )

    result = tmp_path / "result.json"
    reward = tmp_path / "reward.txt"
    result.write_text(json.dumps(_checker_payload((
        ("A2", "PASS"), ("A3", "FAIL"), ("B1", "PASS"),
    ))))
    reward.write_text("0\n")

    score = parse_official_quantcodeeval_score(
        task_id="T16",
        domain="volatility",
        reward_path=reward,
        ctrf_path=result,
        verifier_exit_code=0,
    )

    assert score.reward == 0.0
    assert score.tests_passed == 2
    assert score.tests_failed == 1
    assert score.diagnostic_tags == ("tests_failed",)
    assert "secret" not in repr(score)

    evidence = quantcodeeval_answer_free_summary(result)
    assert evidence == {
        "schema_version": 1,
        "benchmark": "quantcodeeval",
        "official_reward": 0.0,
        "property_families": {
            "type_a": {
                "total": 2,
                "passed": 1,
                "failed": 1,
                "skipped": 0,
                "errors": 0,
            },
            "type_b": {
                "total": 1,
                "passed": 1,
                "failed": 0,
                "skipped": 0,
                "errors": 0,
            },
        },
        "diagnostic_tags": ["properties_incomplete"],
    }
    assert "A2" not in repr(evidence)
    assert "secret" not in repr(evidence)


def test_score_parser_rejects_inconsistent_or_partial_output(tmp_path):
    from qea.evaluation import EvaluationContractError
    from qea.verifiers.quantcodeeval import parse_official_quantcodeeval_score

    result = tmp_path / "result.json"
    reward = tmp_path / "reward.txt"
    payload = _checker_payload((("A2", "PASS"), ("B1", "PASS")))
    payload["pass"] = 1
    result.write_text(json.dumps(payload))
    reward.write_text("1\n")

    with pytest.raises(EvaluationContractError, match="pass count is inconsistent"):
        parse_official_quantcodeeval_score(
            task_id="T16",
            domain="volatility",
            reward_path=reward,
            ctrf_path=result,
            verifier_exit_code=0,
        )


def test_answer_free_summary_uses_official_a11_type_b_exception(tmp_path):
    from qea.verifiers.quantcodeeval import quantcodeeval_answer_free_summary

    result = tmp_path / "result.json"
    result.write_text(json.dumps(_checker_payload((
        ("A2", "PASS"), ("A11", "FAIL"), ("B1", "PASS"),
    ))))

    families = quantcodeeval_answer_free_summary(result)["property_families"]
    assert families["type_a"]["total"] == 1
    assert families["type_b"]["total"] == 2
