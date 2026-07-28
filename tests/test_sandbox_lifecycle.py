from __future__ import annotations

import json
from datetime import datetime, timezone

from qea.sandbox_backend import SandboxHandle, SandboxSpec
from qea.sandbox_lifecycle import (
    create_lifecycle,
    load_lifecycle,
    mark_cleaned,
    mark_finished,
    mark_started,
)


NOW = datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc)
LATER = datetime(2026, 7, 28, 12, 1, tzinfo=timezone.utc)


def _spec() -> SandboxSpec:
    return SandboxSpec(
        role="worker",
        run_id="run-1",
        attempt_id="attempt-1",
        task_id="historical-var-data-prep",
        image_ref="sha256:" + "a" * 64,
        cpu_count=2,
        memory_mb=4096,
        pids_limit=256,
        timeout_seconds=900,
        network_policy="worker-proxy-only",
        environment={"LLM_API_KEY": "qea-proxy-placeholder"},
        writable_tmpfs_mb={"/tmp": 256, "/qea": 512},
    )


def _handle(spec: SandboxSpec) -> SandboxHandle:
    return SandboxHandle(
        backend="rootless-docker",
        native_id="container-exact-1",
        immutable_image_ref=spec.image_ref,
        spec_sha256=spec.spec_sha256,
    )


def test_create_lifecycle_persists_identity_without_environment_values(tmp_path) -> None:
    path = tmp_path / "attempt" / "worker-sandbox-lifecycle-v2.json"
    spec = _spec()

    lifecycle = create_lifecycle(
        path,
        handle=_handle(spec),
        spec=spec,
        attempt_identity_sha256="b" * 64,
        at=NOW,
    )

    payload = json.loads(path.read_text())
    assert lifecycle.native_id == "container-exact-1"
    assert payload == {
        "attempt_id": "attempt-1",
        "attempt_identity_sha256": "b" * 64,
        "backend": "rootless-docker",
        "cleaned_at": None,
        "cleaned_up": False,
        "cleanup_method": None,
        "cleanup_result": None,
        "created_at": "2026-07-28T12:00:00+00:00",
        "failure": None,
        "finished_at": None,
        "immutable_image_ref": "sha256:" + "a" * 64,
        "native_id": "container-exact-1",
        "resource_contract": {
            "cpu_count": 2,
            "memory_mb": 4096,
            "network_policy": "worker-proxy-only",
            "pids_limit": 256,
            "timeout_seconds": 900,
            "writable_tmpfs_mb": {"/qea": 512, "/tmp": 256},
        },
        "role": "worker",
        "run_id": "run-1",
        "schema_version": 2,
        "spec_sha256": spec.spec_sha256,
        "started_at": None,
        "task_id": "historical-var-data-prep",
    }
    assert "qea-proxy-placeholder" not in path.read_text()
    assert not tuple(path.parent.glob("*.tmp"))


def test_lifecycle_transitions_preserve_identity_and_record_terminal_cleanup(tmp_path) -> None:
    path = tmp_path / "worker-sandbox-lifecycle-v2.json"
    spec = _spec()
    create_lifecycle(
        path,
        handle=_handle(spec),
        spec=spec,
        attempt_identity_sha256="b" * 64,
        at=NOW,
    )

    mark_started(path, at=LATER)
    mark_finished(path, at=LATER, failure="worker exited 23\nwith details")
    final = mark_cleaned(
        path,
        cleanup_method="executor-finally",
        cleanup_result="killed",
        at=LATER,
    )

    reloaded = load_lifecycle(path)
    assert final == reloaded
    assert reloaded.started_at == "2026-07-28T12:01:00+00:00"
    assert reloaded.finished_at == "2026-07-28T12:01:00+00:00"
    assert reloaded.failure == "worker exited 23 with details"
    assert reloaded.cleaned_up is True
    assert reloaded.cleanup_method == "executor-finally"
    assert reloaded.cleanup_result == "killed"
    assert reloaded.native_id == "container-exact-1"


def test_finished_lifecycle_redacts_declared_secret_values(tmp_path) -> None:
    path = tmp_path / "worker-sandbox-lifecycle-v2.json"
    spec = _spec()
    create_lifecycle(
        path,
        handle=_handle(spec),
        spec=spec,
        attempt_identity_sha256="b" * 64,
        at=NOW,
    )

    finished = mark_finished(
        path,
        at=LATER,
        failure="provider rejected sk-live-secret",
        forbidden_values=("sk-live-secret",),
    )

    assert finished.failure == "provider rejected [REDACTED]"
    assert "sk-live-secret" not in path.read_text()
