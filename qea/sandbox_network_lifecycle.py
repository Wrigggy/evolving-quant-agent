"""Atomic exact-ID lifecycle evidence for scoped sandbox networks."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

from .sandbox_backend import SandboxNetworkHandle


_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_CLEANUP_RESULTS = frozenset({"killed", "already_absent"})
_FIELDS = frozenset(
    {
        "schema_version",
        "backend",
        "native_id",
        "name",
        "run_id",
        "network_scope",
        "identity_sha256",
        "created_at",
        "cleaned_at",
        "cleaned_up",
        "cleanup_method",
        "cleanup_result",
    }
)


class SandboxNetworkLifecycleError(ValueError):
    """Network lifecycle evidence is malformed or ambiguous."""


@dataclass(frozen=True)
class SandboxNetworkLifecycle:
    schema_version: int
    backend: str
    native_id: str
    name: str
    run_id: str
    network_scope: str
    identity_sha256: str
    created_at: str
    cleaned_at: str | None
    cleaned_up: bool
    cleanup_method: str | None
    cleanup_result: str | None

    def to_payload(self) -> dict[str, object]:
        return {
            field: getattr(self, field) for field in sorted(_FIELDS)
        }

    def to_handle(self) -> SandboxNetworkHandle:
        return SandboxNetworkHandle(
            backend=self.backend,
            native_id=self.native_id,
            name=self.name,
            run_id=self.run_id,
            network_scope=self.network_scope,
            identity_sha256=self.identity_sha256,
        )


def _timestamp(at: datetime | None) -> str:
    value = at or datetime.now(timezone.utc)
    if value.tzinfo is None or value.utcoffset() is None:
        raise SandboxNetworkLifecycleError(
            "network lifecycle timestamps must be timezone-aware"
        )
    return value.astimezone(timezone.utc).isoformat()


def _validate_text(label: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 256
        or any(ord(character) < 0x21 or ord(character) > 0x7E for character in value)
    ):
        raise SandboxNetworkLifecycleError(f"invalid {label}")
    return value


def _atomic_write(path: Path, lifecycle: SandboxNetworkLifecycle) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(path.suffix + ".tmp")
    payload = (
        json.dumps(lifecycle.to_payload(), sort_keys=True, indent=2) + "\n"
    ).encode()
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = None
    try:
        descriptor = os.open(temporary, flags, 0o600)
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb", closefd=True) as output:
            descriptor = None
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary.exists():
            temporary.unlink()


def _validate(lifecycle: SandboxNetworkLifecycle) -> None:
    if lifecycle.schema_version != 1:
        raise SandboxNetworkLifecycleError(
            "unsupported network lifecycle schema"
        )
    for label in (
        "backend",
        "native_id",
        "name",
        "run_id",
        "network_scope",
    ):
        _validate_text(label, getattr(lifecycle, label))
    if _SHA256.fullmatch(lifecycle.identity_sha256) is None:
        raise SandboxNetworkLifecycleError("invalid network identity digest")
    if not isinstance(lifecycle.created_at, str) or not lifecycle.created_at:
        raise SandboxNetworkLifecycleError("invalid network creation timestamp")
    if type(lifecycle.cleaned_up) is not bool:
        raise SandboxNetworkLifecycleError("invalid network cleanup flag")
    terminal = (
        lifecycle.cleaned_at is not None
        and lifecycle.cleanup_method is not None
        and lifecycle.cleanup_result in _CLEANUP_RESULTS
    )
    if lifecycle.cleaned_up != terminal:
        raise SandboxNetworkLifecycleError(
            "network cleanup fields are not a valid terminal transition"
        )


def create_network_lifecycle(
    path: str | Path,
    *,
    handle: SandboxNetworkHandle,
    at: datetime | None = None,
) -> SandboxNetworkLifecycle:
    """Persist one scoped network handle immediately after creation."""

    lifecycle = SandboxNetworkLifecycle(
        schema_version=1,
        backend=handle.backend,
        native_id=handle.native_id,
        name=handle.name,
        run_id=handle.run_id,
        network_scope=handle.network_scope,
        identity_sha256=handle.identity_sha256,
        created_at=_timestamp(at),
        cleaned_at=None,
        cleaned_up=False,
        cleanup_method=None,
        cleanup_result=None,
    )
    _validate(lifecycle)
    _atomic_write(Path(path), lifecycle)
    return lifecycle


def load_network_lifecycle(path: str | Path) -> SandboxNetworkLifecycle:
    """Load and strictly validate one network lifecycle document."""

    lifecycle_path = Path(path)
    try:
        payload = json.loads(lifecycle_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise SandboxNetworkLifecycleError(
            f"invalid network lifecycle document {lifecycle_path}: {exc}"
        ) from exc
    if not isinstance(payload, dict) or set(payload) != _FIELDS:
        raise SandboxNetworkLifecycleError(
            f"unsupported network lifecycle document {lifecycle_path}"
        )
    lifecycle = SandboxNetworkLifecycle(**payload)
    _validate(lifecycle)
    return lifecycle


def mark_network_cleaned(
    path: str | Path,
    *,
    cleanup_method: str,
    cleanup_result: str,
    at: datetime | None = None,
) -> SandboxNetworkLifecycle:
    """Persist one successful exact-ID or already-absent cleanup result."""

    if (
        not isinstance(cleanup_method, str)
        or not cleanup_method
        or any(character.isspace() for character in cleanup_method)
    ):
        raise SandboxNetworkLifecycleError(
            "cleanup_method must be a non-empty token"
        )
    if cleanup_result not in _CLEANUP_RESULTS:
        raise SandboxNetworkLifecycleError(
            f"unsupported cleanup_result: {cleanup_result!r}"
        )
    lifecycle_path = Path(path)
    current = load_network_lifecycle(lifecycle_path)
    if current.cleaned_up:
        if (
            current.cleanup_method == cleanup_method
            and current.cleanup_result == cleanup_result
        ):
            return current
        raise SandboxNetworkLifecycleError(
            "network lifecycle is already terminal"
        )
    updated = replace(
        current,
        cleaned_at=_timestamp(at),
        cleaned_up=True,
        cleanup_method=cleanup_method,
        cleanup_result=cleanup_result,
    )
    _validate(updated)
    _atomic_write(lifecycle_path, updated)
    return updated


__all__ = [
    "SandboxNetworkLifecycle",
    "SandboxNetworkLifecycleError",
    "create_network_lifecycle",
    "load_network_lifecycle",
    "mark_network_cleaned",
]
