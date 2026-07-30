"""Shared provider-neutral mechanics for trusted sandbox coordinators."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Callable, Mapping, Sequence
from urllib.parse import urlparse

from ..sandbox_backend import (
    SandboxBackend,
    SandboxCommandResult,
    SandboxSpec,
)
from ..sandbox_lifecycle import mark_cleaned, mark_finished


PLACEHOLDER_API_KEY = "qea-proxy-placeholder"
SYSTEM_CA_BUNDLE = "/etc/ssl/certs/ca-certificates.crt"


class SandboxExecutionError(RuntimeError):
    """A neutral sandbox attempt cannot produce its expected result."""


class SandboxInfrastructureError(SandboxExecutionError):
    """A coordinator, backend, transfer, isolation, or cleanup operation failed."""

    def __init__(self, phase: str, detail: str) -> None:
        self.phase = phase
        self.detail = " ".join(str(detail).split())[:2_000]
        super().__init__(f"{phase}: {self.detail}")


@dataclass(frozen=True)
class SandboxResourceContract:
    """Bounded resources and writable tmpfs mounts for one sandbox role."""

    cpu_count: int
    memory_mb: int
    pids_limit: int
    timeout_seconds: int
    writable_tmpfs_mb: Mapping[str, int]

    def __post_init__(self) -> None:
        for name in ("cpu_count", "memory_mb", "pids_limit", "timeout_seconds"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise SandboxInfrastructureError(
                    "resource.contract", f"{name} must be a positive integer"
                )
        if not isinstance(self.writable_tmpfs_mb, Mapping):
            raise SandboxInfrastructureError(
                "resource.contract", "writable_tmpfs_mb must be a mapping"
            )
        copied: dict[str, int] = {}
        for path, size_mb in self.writable_tmpfs_mb.items():
            if (
                not isinstance(path, str)
                or not path.startswith("/")
                or path == "/"
                or type(size_mb) is not int
                or size_mb <= 0
            ):
                raise SandboxInfrastructureError(
                    "resource.contract", f"invalid tmpfs entry {path!r}"
                )
            copied[path] = size_mb
        object.__setattr__(
            self,
            "writable_tmpfs_mb",
            MappingProxyType(dict(sorted(copied.items()))),
        )


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


def atomic_json(path: Path, payload: Mapping[str, object]) -> None:
    """Durably replace one JSON document without exposing a partial write."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    encoded = json.dumps(payload, sort_keys=True, indent=2).encode() + b"\n"
    try:
        with temporary.open("wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def require_tmpfs(
    resources: SandboxResourceContract,
    required: frozenset[str],
    *,
    role: str,
) -> None:
    """Reject a role contract missing any required bounded writable mount."""

    missing = sorted(required - set(resources.writable_tmpfs_mb))
    if missing:
        raise SandboxInfrastructureError(
            f"{role}.config", f"resource contract is missing tmpfs mounts: {missing}"
        )


def backend_call(phase: str, operation: Callable[[], object]):
    """Normalize a backend-specific exception at the trusted boundary."""

    try:
        return operation()
    except SandboxInfrastructureError:
        raise
    except Exception as exc:  # noqa: BLE001 - typed provider boundary.
        raise SandboxInfrastructureError(
            phase, f"{type(exc).__name__}: {exc}"
        ) from exc


def run_required(
    backend: SandboxBackend,
    handle,
    argv: Sequence[str],
    *,
    environment: Mapping[str, str],
    timeout_seconds: int,
    phase: str,
) -> SandboxCommandResult:
    """Run one structured command and require a successful bounded result."""

    result = backend_call(
        phase,
        lambda: backend.run(
            handle,
            tuple(argv),
            environment=environment,
            timeout_seconds=timeout_seconds,
        ),
    )
    if not isinstance(result, SandboxCommandResult):
        raise SandboxInfrastructureError(phase, "backend returned an invalid result")
    if result.timed_out:
        raise SandboxInfrastructureError(phase, "coordinator operation timed out")
    if result.exit_code != 0:
        detail = result.stderr or result.stdout or f"exit {result.exit_code}"
        raise SandboxInfrastructureError(
            phase, f"command exited {result.exit_code}: {detail}"
        )
    return result


def public_model_environment(
    *,
    proxy_base_url: str,
    model_name: str,
    placeholder_api_key: str = PLACEHOLDER_API_KEY,
) -> dict[str, str]:
    """Build the only public model environment allowed in worker/evolver specs."""

    if placeholder_api_key != PLACEHOLDER_API_KEY:
        raise SandboxInfrastructureError(
            "sandbox.proxy", "only the fixed public proxy placeholder is accepted"
        )
    parsed = urlparse(proxy_base_url)
    if (
        parsed.scheme != "http"
        or not parsed.hostname
        or parsed.hostname != "qea-model-proxy"
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or not parsed.path.startswith("/v1")
    ):
        raise SandboxInfrastructureError(
            "sandbox.proxy",
            "proxy URL must be the internal qea-model-proxy /v1 endpoint",
        )
    if not isinstance(model_name, str) or not model_name.strip():
        raise SandboxInfrastructureError("sandbox.proxy", "model name must be public")
    return {
        "LLM_API_KEY": placeholder_api_key,
        "LLM_BASE_URL": proxy_base_url,
        "LLM_MODEL": model_name,
        "SSL_CERT_FILE": SYSTEM_CA_BUNDLE,
    }


def validate_public_model_env(
    supplied: Mapping[str, str] | None,
    expected: Mapping[str, str],
    *,
    role: str,
) -> None:
    """Permit an omitted environment or the exact public placeholder mapping."""

    values = dict(supplied or {})
    if values and values != dict(expected):
        raise SandboxInfrastructureError(
            f"{role}.public proxy environment",
            "provider credentials and environment overrides are forbidden",
        )


def write_command_log(path: Path, result: SandboxCommandResult) -> None:
    """Persist only the bounded command result, never its environment or argv."""

    atomic_json(
        path,
        {
            "exit_code": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "timed_out": result.timed_out,
        },
    )


def finish_and_cleanup(
    *,
    backend: SandboxBackend,
    handle,
    lifecycle_path: Path | None,
    clock: Callable[[], datetime],
    role: str,
    primary_error: BaseException | None,
    finished: bool,
) -> None:
    """Finish lifecycle evidence and kill exactly the recorded native ID."""

    finish_error: SandboxInfrastructureError | None = None
    if lifecycle_path is not None and lifecycle_path.is_file() and not finished:
        try:
            mark_finished(
                lifecycle_path,
                at=clock(),
                failure=str(primary_error) if primary_error else "attempt interrupted",
            )
        except Exception as exc:  # noqa: BLE001 - lifecycle boundary.
            finish_error = SandboxInfrastructureError(
                f"{role}.lifecycle", f"{type(exc).__name__}: {exc}"
            )

    cleanup_error: SandboxInfrastructureError | None = None
    if handle is not None:
        try:
            result = backend.kill(handle.native_id)
            if lifecycle_path is not None and lifecycle_path.is_file():
                mark_cleaned(
                    lifecycle_path,
                    cleanup_method="exact-id",
                    cleanup_result=result.outcome,
                    at=clock(),
                )
        except Exception as exc:  # noqa: BLE001 - normalize backend cleanup.
            cleanup_error = SandboxInfrastructureError(
                f"{role}.cleanup", f"{type(exc).__name__}: {exc}"
            )
    if cleanup_error is not None:
        if primary_error is not None:
            raise cleanup_error from primary_error
        raise cleanup_error
    if finish_error is not None:
        if primary_error is not None:
            raise finish_error from primary_error
        raise finish_error


__all__ = [
    "PLACEHOLDER_API_KEY",
    "SYSTEM_CA_BUNDLE",
    "SandboxExecutionError",
    "SandboxInfrastructureError",
    "SandboxResourceContract",
    "atomic_json",
    "backend_call",
    "finish_and_cleanup",
    "public_model_environment",
    "require_tmpfs",
    "run_required",
    "utc_now",
    "validate_public_model_env",
    "write_command_log",
]
