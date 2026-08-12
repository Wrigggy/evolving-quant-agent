import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

from qea.a6_model_boundary import (
    A6ModelBoundaryError,
    assert_a6_model_boundary_unclaimed,
    claim_a6_model_boundary,
)


def _plan(run_dir: Path) -> Path:
    run_dir.mkdir(mode=0o700)
    path = run_dir / "pilot-plan.json"
    path.write_text('{"schema_version":1}\n', encoding="utf-8")
    return path


def _claim(run_dir: Path, plan: Path, **changes):
    kwargs = {
        "plan_path": plan,
        "run_id": "qfbench-a6-fixture-r1",
        "run_kind": "seed",
        "arm_labels": ["seed-evidence"],
        "identity_record_sha256": "1" * 64,
        "materialized_launch_identity_sha256": "2" * 64,
    }
    kwargs.update(changes)
    return claim_a6_model_boundary(run_dir, **kwargs)


def test_a6_model_boundary_is_private_digest_bound_and_durably_synced(
    tmp_path, monkeypatch
):
    import qea.a6_model_boundary as boundary

    run_dir = tmp_path / "run"
    plan = _plan(run_dir)
    real_fsync = boundary.os.fsync
    synced = []

    def fsync(descriptor):
        synced.append(descriptor)
        return real_fsync(descriptor)

    monkeypatch.setattr(boundary.os, "fsync", fsync)
    claimed = _claim(run_dir, plan)

    marker = run_dir / "pilot-model-boundary.json"
    payload = json.loads(marker.read_text())
    assert marker.stat().st_mode & 0o777 == 0o600
    assert payload == {
        "arm_labels": ["seed-evidence"],
        "identity_record_sha256": "1" * 64,
        "materialized_launch_identity_sha256": "2" * 64,
        "plan_sha256": hashlib.sha256(plan.read_bytes()).hexdigest(),
        "run_id": "qfbench-a6-fixture-r1",
        "run_kind": "seed",
        "schema_version": 1,
        "stage": "A6",
        "status": "model_boundary_claimed",
    }
    assert claimed["marker_sha256"] == hashlib.sha256(
        marker.read_bytes()
    ).hexdigest()
    assert len(synced) == 2


def test_a6_model_boundary_existing_or_tampered_marker_never_reopens(tmp_path):
    run_dir = tmp_path / "run"
    plan = _plan(run_dir)
    _claim(run_dir, plan)
    marker = run_dir / "pilot-model-boundary.json"
    original = marker.read_bytes()

    with pytest.raises(A6ModelBoundaryError, match="already claimed"):
        assert_a6_model_boundary_unclaimed(run_dir)
    with pytest.raises(A6ModelBoundaryError, match="already claimed"):
        _claim(run_dir, plan)
    assert marker.read_bytes() == original

    payload = json.loads(original)
    payload["plan_sha256"] = "3" * 64
    marker.write_text(json.dumps(payload), encoding="utf-8")
    os.chmod(marker, 0o600)
    with pytest.raises(A6ModelBoundaryError, match="not canonical"):
        assert_a6_model_boundary_unclaimed(run_dir)
    assert marker.exists()


def test_a6_model_boundary_concurrent_claim_has_exactly_one_winner(tmp_path):
    run_dir = tmp_path / "run"
    plan = _plan(run_dir)
    barrier = Barrier(2)

    def claim():
        barrier.wait()
        try:
            return "claimed", _claim(run_dir, plan)
        except A6ModelBoundaryError as exc:
            return "blocked", str(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(lambda _: claim(), range(2)))

    assert sorted(result[0] for result in results) == ["blocked", "claimed"]
    marker = run_dir / "pilot-model-boundary.json"
    assert marker.is_file()
    assert marker.stat().st_mode & 0o777 == 0o600
    assert json.loads(marker.read_text())["plan_sha256"] == hashlib.sha256(
        plan.read_bytes()
    ).hexdigest()


def test_a6_model_boundary_invalid_identity_does_not_consume_marker(tmp_path):
    run_dir = tmp_path / "run"
    plan = _plan(run_dir)

    with pytest.raises(A6ModelBoundaryError, match="identity_record_sha256"):
        _claim(run_dir, plan, identity_record_sha256="not-a-digest")

    assert not (run_dir / "pilot-model-boundary.json").exists()
    assert_a6_model_boundary_unclaimed(run_dir)
