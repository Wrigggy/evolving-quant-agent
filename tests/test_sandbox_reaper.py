from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from qea.sandbox_backend import (
    KillResult,
    SandboxHandle,
    SandboxSpec,
    SandboxState,
)
from qea.sandbox_lifecycle import create_lifecycle, load_lifecycle
from qea.sandbox_reaper import SandboxReaperError, reap_sandboxes


NOW = datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc)


class FakeBackend:
    backend_name = "rootless-docker"

    def __init__(self, states: dict[str, SandboxState | None]) -> None:
        self.states = states
        self.inspected_ids: list[str] = []
        self.killed_ids: list[str] = []

    def inspect(self, native_id: str) -> SandboxState | None:
        self.inspected_ids.append(native_id)
        return self.states.get(native_id)

    def kill(self, native_id: str) -> KillResult:
        self.killed_ids.append(native_id)
        existed = self.states.get(native_id) is not None
        self.states[native_id] = None
        return KillResult(
            native_id=native_id,
            outcome="killed" if existed else "already_absent",
        )


def _spec(*, attempt_id: str = "attempt-1") -> SandboxSpec:
    return SandboxSpec(
        role="worker",
        run_id="run-1",
        attempt_id=attempt_id,
        task_id="historical-var-data-prep",
        image_ref="sha256:" + "a" * 64,
        cpu_count=2,
        memory_mb=4096,
        pids_limit=256,
        timeout_seconds=900,
        network_policy="worker-proxy-only",
    )


def _write_open_lifecycle(
    root,
    *,
    native_id: str = "container-exact-1",
    attempt_id: str = "attempt-1",
):
    spec = _spec(attempt_id=attempt_id)
    handle = SandboxHandle(
        backend="rootless-docker",
        native_id=native_id,
        immutable_image_ref=spec.image_ref,
        spec_sha256=spec.spec_sha256,
    )
    path = root / attempt_id / "worker-sandbox-lifecycle-v2.json"
    create_lifecycle(
        path,
        handle=handle,
        spec=spec,
        attempt_identity_sha256="b" * 64,
        at=NOW,
    )
    return path, spec


def _matching_state(native_id: str, spec: SandboxSpec) -> SandboxState:
    return SandboxState(
        backend="rootless-docker",
        native_id=native_id,
        status="running",
        labels={
            "qea.managed": "true",
            "qea.backend": "rootless-docker",
            "qea.spec-sha256": spec.spec_sha256,
        },
        immutable_image_ref=spec.image_ref,
    )


def test_reaper_is_dry_run_by_default_and_applies_only_exact_id(tmp_path) -> None:
    lifecycle_path, spec = _write_open_lifecycle(tmp_path)
    backend = FakeBackend(
        {"container-exact-1": _matching_state("container-exact-1", spec)}
    )

    dry = reap_sandboxes(tmp_path, backend=backend)

    assert dry.pending_ids == ("container-exact-1",)
    assert dry.killed_ids == ()
    assert backend.killed_ids == []
    assert load_lifecycle(lifecycle_path).cleaned_up is False

    applied = reap_sandboxes(tmp_path, backend=backend, apply=True, at=NOW)

    assert applied.killed_ids == ("container-exact-1",)
    assert backend.killed_ids == ["container-exact-1"]
    lifecycle = load_lifecycle(lifecycle_path)
    assert lifecycle.cleaned_up is True
    assert lifecycle.cleanup_method == "reaper"
    assert lifecycle.cleanup_result == "killed"


def test_reaper_refuses_label_or_image_identity_mismatch(tmp_path) -> None:
    lifecycle_path, spec = _write_open_lifecycle(tmp_path)
    mismatched = SandboxState(
        backend="rootless-docker",
        native_id="container-exact-1",
        status="running",
        labels={
            "qea.managed": "true",
            "qea.backend": "rootless-docker",
            "qea.spec-sha256": "2" * 64,
        },
        immutable_image_ref=spec.image_ref,
    )
    backend = FakeBackend({"container-exact-1": mismatched})

    report = reap_sandboxes(tmp_path, backend=backend, apply=True, at=NOW)

    assert report.identity_mismatch_ids == ("container-exact-1",)
    assert backend.killed_ids == []
    assert load_lifecycle(lifecycle_path).cleaned_up is False


def test_reaper_marks_an_inspected_absent_id_without_broad_kill(tmp_path) -> None:
    lifecycle_path, _ = _write_open_lifecycle(tmp_path)
    backend = FakeBackend({"container-exact-1": None})

    report = reap_sandboxes(tmp_path, backend=backend, apply=True, at=NOW)

    assert report.absent_ids == ("container-exact-1",)
    assert backend.killed_ids == []
    assert load_lifecycle(lifecycle_path).cleanup_result == "already_absent"


def test_reaper_rejects_duplicate_native_ids_before_inspection(tmp_path) -> None:
    _, first_spec = _write_open_lifecycle(tmp_path, attempt_id="attempt-1")
    _write_open_lifecycle(tmp_path, attempt_id="attempt-2")
    backend = FakeBackend(
        {"container-exact-1": _matching_state("container-exact-1", first_spec)}
    )

    with pytest.raises(SandboxReaperError, match="duplicate native ID"):
        reap_sandboxes(tmp_path, backend=backend, apply=True, at=NOW)

    assert backend.inspected_ids == []
    assert backend.killed_ids == []


def test_reaper_rejects_malformed_or_wrong_backend_manifest(tmp_path) -> None:
    malformed = tmp_path / "bad-sandbox-lifecycle-v2.json"
    malformed.write_text(json.dumps({"schema_version": 1}))

    with pytest.raises(SandboxReaperError, match="unsupported lifecycle"):
        reap_sandboxes(tmp_path, backend=FakeBackend({}))

    malformed.unlink()
    lifecycle_path, _ = _write_open_lifecycle(tmp_path)
    payload = json.loads(lifecycle_path.read_text())
    payload["backend"] = "e2b"
    lifecycle_path.write_text(json.dumps(payload))

    with pytest.raises(SandboxReaperError, match="backend mismatch"):
        reap_sandboxes(tmp_path, backend=FakeBackend({}))
