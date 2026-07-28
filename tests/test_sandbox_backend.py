from __future__ import annotations

from types import MappingProxyType

import pytest

from qea.sandbox_backend import SandboxSpec, SandboxSpecError, SandboxState


def _make_spec(**changes) -> SandboxSpec:
    values = {
        "role": "worker",
        "run_id": "canary-20260728",
        "attempt_id": "attempt-001",
        "task_id": "historical-var-data-prep",
        "image_ref": "sha256:" + "a" * 64,
        "cpu_count": 2,
        "memory_mb": 4096,
        "pids_limit": 256,
        "timeout_seconds": 900,
        "network_policy": "worker-proxy-only",
        "environment": {"QEA_ROLE": "worker"},
        "writable_tmpfs_mb": {"/tmp": 256, "/qea": 512},
    }
    values.update(changes)
    return SandboxSpec(**values)


def test_spec_digest_is_order_independent_and_changes_with_contract() -> None:
    left = _make_spec(
        environment={"QEA_Z": "last", "QEA_A": "first"},
        writable_tmpfs_mb={"/tmp": 256, "/qea": 512},
    )
    right = _make_spec(
        environment={"QEA_A": "first", "QEA_Z": "last"},
        writable_tmpfs_mb={"/qea": 512, "/tmp": 256},
    )

    assert left.spec_sha256 == right.spec_sha256
    assert left.spec_sha256 != _make_spec(cpu_count=4).spec_sha256
    assert left.spec_sha256 != _make_spec(
        environment={"QEA_A": "changed", "QEA_Z": "last"}
    ).spec_sha256
    assert len(left.spec_sha256) == 64
    assert set(left.spec_sha256) <= set("0123456789abcdef")


def test_spec_copies_input_mappings_and_exposes_immutable_values() -> None:
    environment = {"QEA_ROLE": "worker"}
    tmpfs = {"/tmp": 256}

    spec = _make_spec(environment=environment, writable_tmpfs_mb=tmpfs)
    environment["QEA_ROLE"] = "verifier"
    tmpfs["/tmp"] = 1

    assert isinstance(spec.environment, MappingProxyType)
    assert isinstance(spec.writable_tmpfs_mb, MappingProxyType)
    assert spec.environment == {"QEA_ROLE": "worker"}
    assert spec.writable_tmpfs_mb == {"/tmp": 256}
    with pytest.raises(TypeError):
        spec.environment["QEA_ROLE"] = "changed"  # type: ignore[index]


def test_state_copies_labels_so_inspection_evidence_cannot_change() -> None:
    labels = {"qea.managed": "true"}
    state = SandboxState(
        backend="rootless-docker",
        native_id="container-abc",
        status="running",
        labels=labels,
        immutable_image_ref="sha256:" + "a" * 64,
    )

    labels["qea.managed"] = "false"

    assert isinstance(state.labels, MappingProxyType)
    assert state.labels == {"qea.managed": "true"}


@pytest.mark.parametrize(
    "change",
    [
        {"role": "oracle"},
        {"run_id": "../escape"},
        {"attempt_id": "bad value"},
        {"task_id": "task/name"},
        {"image_ref": "python:3.12"},
        {"image_ref": "sha256:" + "A" * 64},
        {"cpu_count": 0},
        {"cpu_count": True},
        {"memory_mb": 0},
        {"pids_limit": 0},
        {"timeout_seconds": 0},
        {"network_policy": "host"},
        {"writable_tmpfs_mb": {"relative": 32}},
        {"writable_tmpfs_mb": {"/tmp/../host": 32}},
        {"writable_tmpfs_mb": {"/tmp": 0}},
        {"environment": {"MODEL_API_KEY": "secret"}},
        {"environment": {"NAME=BAD": "value"}},
        {"environment": {"NAME": "bad\x00value"}},
    ],
)
def test_spec_rejects_unsafe_values(change) -> None:
    with pytest.raises(SandboxSpecError):
        _make_spec(**change)


@pytest.mark.parametrize(
    "image_ref",
    [
        "sha256:" + "b" * 64,
        "docker.io/qea/worker@sha256:" + "c" * 64,
        "registry.example:5000/team/image@sha256:" + "d" * 64,
        "e2b-template:qfbench-worker-historical-var-data-prep-v3",
    ],
)
def test_spec_accepts_provider_native_immutable_image_references(image_ref: str) -> None:
    assert _make_spec(image_ref=image_ref).image_ref == image_ref


@pytest.mark.parametrize("key", ["LLM_API_KEY", "OPENAI_API_KEY"])
def test_spec_allows_only_public_proxy_sentinel_for_worker_key(key: str) -> None:
    spec = _make_spec(environment={key: "qea-proxy-placeholder"})
    assert spec.environment[key] == "qea-proxy-placeholder"

    with pytest.raises(SandboxSpecError):
        _make_spec(environment={key: "sk-live-value"})
