"""Atomic lifecycle evidence for provider-neutral QEA sandboxes."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Iterable, Mapping

from .sandbox_backend import SandboxHandle, SandboxSpec


_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_CLEANUP_RESULTS = frozenset(
    {"killed", "already_absent", "identity_mismatch", "failed"}
)


class SandboxLifecycleError(ValueError):
    """Lifecycle evidence is malformed or violates an identity transition."""


@dataclass(frozen=True)
class SandboxLifecycle:
    schema_version: int
    backend: str
    role: str
    run_id: str
    attempt_id: str
    task_id: str
    native_id: str
    immutable_image_ref: str
    spec_sha256: str
    attempt_identity_sha256: str
    resource_contract: Mapping[str, object]
    created_at: str
    started_at: str | None
    finished_at: str | None
    cleaned_at: str | None
    cleaned_up: bool
    cleanup_method: str | None
    cleanup_result: str | None
    failure: str | None

    def __post_init__(self) -> None:
        resources = dict(self.resource_contract)
        tmpfs = resources.get("writable_tmpfs_mb", {})
        resources["writable_tmpfs_mb"] = MappingProxyType(dict(tmpfs))
        object.__setattr__(self, "resource_contract", MappingProxyType(resources))

    def to_payload(self) -> dict[str, object]:
        """Return a JSON-safe representation without sandbox environment values."""

        resources = dict(self.resource_contract)
        resources["writable_tmpfs_mb"] = dict(
            self.resource_contract["writable_tmpfs_mb"]  # type: ignore[arg-type]
        )
        return {
            "schema_version": self.schema_version,
            "backend": self.backend,
            "role": self.role,
            "run_id": self.run_id,
            "attempt_id": self.attempt_id,
            "task_id": self.task_id,
            "native_id": self.native_id,
            "immutable_image_ref": self.immutable_image_ref,
            "spec_sha256": self.spec_sha256,
            "attempt_identity_sha256": self.attempt_identity_sha256,
            "resource_contract": resources,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "cleaned_at": self.cleaned_at,
            "cleaned_up": self.cleaned_up,
            "cleanup_method": self.cleanup_method,
            "cleanup_result": self.cleanup_result,
            "failure": self.failure,
        }


def _timestamp(at: datetime | None) -> str:
    value = at or datetime.now(timezone.utc)
    if value.tzinfo is None or value.utcoffset() is None:
        raise SandboxLifecycleError("lifecycle timestamps must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat()


def _require_sha256(label: str, value: object) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise SandboxLifecycleError(f"invalid {label}: {value!r}")
    return value


def _sanitize_failure(
    value: str | None,
    forbidden_values: Iterable[str] = (),
) -> str | None:
    if value is None:
        return None
    cleaned = str(value)
    secrets = sorted(
        {secret for secret in forbidden_values if isinstance(secret, str) and secret},
        key=len,
        reverse=True,
    )
    for secret in secrets:
        cleaned = cleaned.replace(secret, "[REDACTED]")
    cleaned = " ".join(cleaned.split())
    return cleaned[:2_000]


def _atomic_write(path: Path, lifecycle: SandboxLifecycle) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    encoded = json.dumps(
        lifecycle.to_payload(), sort_keys=True, indent=2
    ).encode("utf-8") + b"\n"
    try:
        with temporary.open("wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


def _resource_contract(spec: SandboxSpec) -> Mapping[str, object]:
    return {
        "cpu_count": spec.cpu_count,
        "memory_mb": spec.memory_mb,
        "network_policy": spec.network_policy,
        "pids_limit": spec.pids_limit,
        "timeout_seconds": spec.timeout_seconds,
        "writable_tmpfs_mb": dict(spec.writable_tmpfs_mb),
    }


def create_lifecycle(
    path: str | Path,
    *,
    handle: SandboxHandle,
    spec: SandboxSpec,
    attempt_identity_sha256: str,
    at: datetime | None = None,
) -> SandboxLifecycle:
    """Persist the native ID immediately after sandbox creation."""

    if not handle.backend or not handle.native_id:
        raise SandboxLifecycleError("sandbox handle has no backend-native identity")
    if handle.immutable_image_ref != spec.image_ref:
        raise SandboxLifecycleError("handle image identity differs from sandbox spec")
    if handle.spec_sha256 != spec.spec_sha256:
        raise SandboxLifecycleError("handle spec digest differs from sandbox spec")
    _require_sha256("attempt identity digest", attempt_identity_sha256)
    lifecycle = SandboxLifecycle(
        schema_version=2,
        backend=handle.backend,
        role=spec.role,
        run_id=spec.run_id,
        attempt_id=spec.attempt_id,
        task_id=spec.task_id,
        native_id=handle.native_id,
        immutable_image_ref=handle.immutable_image_ref,
        spec_sha256=handle.spec_sha256,
        attempt_identity_sha256=attempt_identity_sha256,
        resource_contract=_resource_contract(spec),
        created_at=_timestamp(at),
        started_at=None,
        finished_at=None,
        cleaned_at=None,
        cleaned_up=False,
        cleanup_method=None,
        cleanup_result=None,
        failure=None,
    )
    _atomic_write(Path(path), lifecycle)
    return lifecycle


def load_lifecycle(path: str | Path) -> SandboxLifecycle:
    """Load and validate one lifecycle v2 document."""

    lifecycle_path = Path(path)
    try:
        payload = json.loads(lifecycle_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise SandboxLifecycleError(
            f"invalid lifecycle document {lifecycle_path}: {exc}"
        ) from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 2:
        raise SandboxLifecycleError(
            f"unsupported lifecycle document {lifecycle_path}"
        )
    required = {
        "schema_version",
        "backend",
        "role",
        "run_id",
        "attempt_id",
        "task_id",
        "native_id",
        "immutable_image_ref",
        "spec_sha256",
        "attempt_identity_sha256",
        "resource_contract",
        "created_at",
        "started_at",
        "finished_at",
        "cleaned_at",
        "cleaned_up",
        "cleanup_method",
        "cleanup_result",
        "failure",
    }
    missing = sorted(required - payload.keys())
    if missing:
        raise SandboxLifecycleError(
            f"lifecycle document {lifecycle_path} is missing {missing}"
        )
    for label in ("backend", "role", "run_id", "attempt_id", "task_id", "native_id"):
        if not isinstance(payload[label], str) or not payload[label]:
            raise SandboxLifecycleError(
                f"lifecycle document {lifecycle_path} has invalid {label}"
            )
    _require_sha256("spec digest", payload["spec_sha256"])
    _require_sha256("attempt identity digest", payload["attempt_identity_sha256"])
    if not isinstance(payload["resource_contract"], dict):
        raise SandboxLifecycleError(
            f"lifecycle document {lifecycle_path} has invalid resource contract"
        )
    if not isinstance(payload["cleaned_up"], bool):
        raise SandboxLifecycleError(
            f"lifecycle document {lifecycle_path} has invalid cleanup flag"
        )
    return SandboxLifecycle(**{key: payload[key] for key in required})


def _update(path: str | Path, **changes: object) -> SandboxLifecycle:
    lifecycle_path = Path(path)
    current = load_lifecycle(lifecycle_path)
    updated = replace(current, **changes)
    _atomic_write(lifecycle_path, updated)
    return updated


def mark_started(
    path: str | Path, *, at: datetime | None = None
) -> SandboxLifecycle:
    """Record that the inert sandbox supervisor started."""

    return _update(path, started_at=_timestamp(at))


def mark_finished(
    path: str | Path,
    *,
    at: datetime | None = None,
    failure: str | None = None,
    forbidden_values: Iterable[str] = (),
) -> SandboxLifecycle:
    """Record task-command completion and bounded sanitized failure text."""

    return _update(
        path,
        finished_at=_timestamp(at),
        failure=_sanitize_failure(failure, forbidden_values),
    )


def mark_cleaned(
    path: str | Path,
    *,
    cleanup_method: str,
    cleanup_result: str,
    at: datetime | None = None,
) -> SandboxLifecycle:
    """Record a terminal exact-ID cleanup outcome."""

    if not cleanup_method or any(character.isspace() for character in cleanup_method):
        raise SandboxLifecycleError("cleanup_method must be a non-empty token")
    if cleanup_result not in _CLEANUP_RESULTS:
        raise SandboxLifecycleError(
            f"unsupported cleanup_result: {cleanup_result!r}"
        )
    return _update(
        path,
        cleaned_at=_timestamp(at),
        cleaned_up=True,
        cleanup_method=cleanup_method,
        cleanup_result=cleanup_result,
    )
