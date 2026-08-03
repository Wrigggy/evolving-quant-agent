import json
from types import SimpleNamespace

import pytest


def _identity():
    return {
        "model_identity": "model",
        "task_manifest_digest": "1" * 64,
        "runtime_identity_digest": "4" * 64,
        "scheduler_identity_digest": "5" * 64,
        "template_identity_digest": "2" * 64,
        "worker_concurrency": 4,
        "verifier_concurrency": 3,
        "seed_worker_digest": "3" * 64,
        "primary_tasks": [{"task_id": "primary"}],
        "diagnostic_tasks": [{"task_id": "diagnostic"}],
    }


def _write_rep1_boundary(tmp_path, *, score_count=85):
    run_dir = tmp_path / "formal-run"
    attempts = run_dir / "attempts"
    attempts.mkdir(parents=True)
    completed = []
    for index in range(score_count):
        attempt_id = f"attempt-{index:03d}"
        attempt = attempts / attempt_id
        attempt.mkdir()
        checkpoint = (
            "repetition-01-primary"
            if index < 77
            else "repetition-01-diagnostic"
        )
        (attempt / "attempt.json").write_text(
            json.dumps(
                {
                    "attempt_id": attempt_id,
                    "run_id": "formal-run",
                    "benchmark_commit": "0" * 40,
                    "task_id": f"task-{index:03d}",
                    "checkpoint": checkpoint,
                    "split": (
                        "baseline_primary"
                        if index < 77
                        else "baseline_diagnostic"
                    ),
                }
            )
        )
        (attempt / "completed-score.json").write_text(
            json.dumps(
                {
                    "task_id": f"task-{index:03d}",
                    "domain": "risk_credit",
                    "reward": 1.0,
                    "diagnostic_tags": [],
                }
            )
        )
    completed.append(
        {
            "repetition": 1,
            "primary": {"scores": []},
            "diagnostic": {"scores": []},
        }
    )
    (run_dir / "resume.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run_id": "formal-run",
                "benchmark_commit": "0" * 40,
                "total_repetitions": 5,
                "identity": _identity(),
                "phase": "primary",
                "next_repetition": 2,
                "pending_primary": None,
                "completed": completed,
            }
        )
    )
    registry = run_dir / "proxy-request-registry.json"
    registry.write_text(
        json.dumps({"schema_version": 1, "request_identities_sha256": []})
    )
    registry.chmod(0o600)
    return run_dir


class _Backend:
    backend_name = "rootless-docker"

    def __init__(self, *, containers=(), networks=()):
        self.containers = tuple(containers)
        self.networks = frozenset(networks)

    def list(self, labels):
        return tuple(
            SimpleNamespace(native_id=native_id) for native_id in self.containers
        )

    def inspect_internal_network(self, handle):
        return handle.native_id in self.networks

    def remove_internal_network(self, handle):
        raise AssertionError("boundary inspection must never remove a network")


def _add_rep2_attempt(run_dir):
    attempt = run_dir / "attempts" / "rep2-attempt"
    attempt.mkdir()
    (attempt / "attempt.json").write_text(
        json.dumps(
            {
                "attempt_id": "rep2-attempt",
                "run_id": "formal-run",
                "benchmark_commit": "0" * 40,
                "task_id": "rep2-task",
                "checkpoint": "repetition-02-primary",
                "split": "baseline_primary",
            }
        )
    )


def _write_network_lifecycle(run_dir, native_id="network-1"):
    path = run_dir / "lifecycles" / "rep2-attempt"
    path.mkdir(parents=True)
    (path / "proxy-network-lifecycle-v1.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "backend": "rootless-docker",
                "native_id": native_id,
                "name": "network-name",
                "run_id": "formal-run",
                "network_scope": "rep2-attempt",
                "identity_sha256": "a" * 64,
                "created_at": "2026-08-03T00:00:00+00:00",
                "cleaned_at": None,
                "cleaned_up": False,
                "cleanup_method": None,
                "cleanup_result": None,
            }
        )
    )


def test_clean_boundary_hashes_scores_without_reading_artifacts(tmp_path):
    from qea.qfbench_boundary import inspect_boundary

    run_dir = _write_rep1_boundary(tmp_path)
    artifacts = run_dir / "attempts" / "attempt-000" / "artifacts"
    artifacts.mkdir()
    (artifacts / "official-looking-secret.json").write_text("not json")

    inventory = inspect_boundary(run_dir, expected_scores=85, backend=_Backend())

    assert inventory.clean is True
    assert inventory.repetition_one_score_count == 85
    assert inventory.repetition_two_evidence == ()
    assert inventory.active_resource_ids == ()
    assert len(inventory.evidence_sha256) == 64
    assert all("artifacts" not in record[0] for record in inventory.evidence_manifest)


@pytest.mark.parametrize(
    "kind", ["attempt", "registry", "lifecycle", "container", "network"]
)
def test_any_repetition_two_or_active_resource_evidence_blocks_migration(
    tmp_path, kind
):
    from qea.qfbench_boundary import inspect_boundary

    run_dir = _write_rep1_boundary(tmp_path)
    backend = _Backend()
    if kind in {"attempt", "lifecycle"}:
        _add_rep2_attempt(run_dir)
    if kind == "registry":
        (run_dir / "proxy-request-registry.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "request_identities_sha256": ["b" * 64],
                }
            )
        )
    elif kind == "lifecycle":
        lifecycle = run_dir / "lifecycles" / "rep2-attempt"
        lifecycle.mkdir(parents=True)
        (lifecycle / "worker-sandbox-lifecycle-v2.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "attempt_id": "rep2-attempt",
                    "run_id": "formal-run",
                    "native_id": "container-lifecycle",
                    "cleaned_up": True,
                }
            )
        )
    elif kind == "container":
        backend = _Backend(containers=("container-live",))
    elif kind == "network":
        _add_rep2_attempt(run_dir)
        _write_network_lifecycle(run_dir)
        backend = _Backend(networks=("network-1",))

    inventory = inspect_boundary(run_dir, expected_scores=85, backend=backend)

    assert inventory.clean is False
    if kind in {"container", "network"}:
        assert inventory.active_resource_ids
    else:
        assert inventory.repetition_two_evidence


def test_unknown_checkpoint_and_symlinked_metadata_are_rejected(tmp_path):
    from qea.qfbench_boundary import BoundaryError, inspect_boundary

    run_dir = _write_rep1_boundary(tmp_path / "checkpoint")
    attempt = run_dir / "attempts" / "attempt-000" / "attempt.json"
    payload = json.loads(attempt.read_text())
    payload["checkpoint"] = "seed-optimize"
    attempt.write_text(json.dumps(payload))
    with pytest.raises(BoundaryError, match="checkpoint"):
        inspect_boundary(run_dir, expected_scores=85, backend=_Backend())

    run_dir = _write_rep1_boundary(tmp_path / "symlink")
    registry = run_dir / "proxy-request-registry.json"
    target = tmp_path / "registry-target.json"
    target.write_text(registry.read_text())
    registry.unlink()
    registry.symlink_to(target)
    with pytest.raises(BoundaryError, match="symlink"):
        inspect_boundary(run_dir, expected_scores=85, backend=_Backend())


@pytest.mark.parametrize("drift", ["run_id", "benchmark_commit", "score_task"])
def test_attempt_and_score_identity_drift_is_rejected(tmp_path, drift):
    from qea.qfbench_boundary import BoundaryError, inspect_boundary

    run_dir = _write_rep1_boundary(tmp_path)
    attempt_path = run_dir / "attempts" / "attempt-000" / "attempt.json"
    attempt = json.loads(attempt_path.read_text())
    if drift == "run_id":
        attempt["run_id"] = "other-run"
    elif drift == "benchmark_commit":
        attempt["benchmark_commit"] = "f" * 40
    else:
        score_path = attempt_path.parent / "completed-score.json"
        score = json.loads(score_path.read_text())
        score["task_id"] = "other-task"
        score_path.write_text(json.dumps(score))
    attempt_path.write_text(json.dumps(attempt))

    with pytest.raises(BoundaryError, match="identity"):
        inspect_boundary(run_dir, expected_scores=85, backend=_Backend())


def test_freeze_manifest_is_stable_and_does_not_rewrite_evidence(tmp_path):
    from qea.qfbench_boundary import freeze_boundary_manifest, inspect_boundary

    run_dir = _write_rep1_boundary(tmp_path)
    score = run_dir / "attempts" / "attempt-000" / "completed-score.json"
    before = score.read_bytes()
    inventory = inspect_boundary(run_dir, expected_scores=85, backend=_Backend())

    digest = freeze_boundary_manifest(run_dir, inventory)

    assert len(digest) == 64
    assert score.read_bytes() == before
    manifest = json.loads((run_dir / "boundary-manifest.json").read_text())
    assert manifest["evidence_sha256"] == inventory.evidence_sha256
    assert manifest["manifest_sha256"] == digest
