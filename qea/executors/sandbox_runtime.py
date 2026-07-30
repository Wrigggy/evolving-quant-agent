"""Shared provider-neutral mechanics for trusted sandbox coordinators."""

from __future__ import annotations

import base64
import binascii
import json
import os
import stat
import tempfile
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
_BOUNDED_READ_CODE = r'''
# QEA_BOUNDED_READ_V1
import base64
import os
import stat
import sys

path = sys.argv[1]
limit = int(sys.argv[2])
flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
try:
    descriptor = os.open(path, flags)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > limit:
            raise SystemExit(73)
        chunks = []
        remaining = limit + 1
        while remaining:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
    finally:
        os.close(descriptor)
except (OSError, ValueError):
    raise SystemExit(74)
payload = b"".join(chunks)
if len(payload) > limit:
    raise SystemExit(73)
sys.stdout.write(base64.b64encode(payload).decode("ascii"))
'''.strip()


class SandboxExecutionError(RuntimeError):
    """A neutral sandbox attempt cannot produce its expected result."""


class SandboxInfrastructureError(SandboxExecutionError):
    """A coordinator, backend, transfer, isolation, or cleanup operation failed."""

    def __init__(self, phase: str, detail: str) -> None:
        self.phase = phase
        self.detail = " ".join(str(detail).split())[:2_000]
        self.secondary_failures: tuple[SandboxInfrastructureError, ...] = ()
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


def lexical_absolute(path: str | Path) -> Path:
    """Return an absolute lexical path without resolving symlinks."""

    return Path(os.path.abspath(os.fspath(Path(path).expanduser())))


def trusted_directory(
    path: str | Path,
    *,
    create: bool,
    phase: str,
    contained_by: str | Path | None = None,
) -> Path:
    """Validate every path component as a real directory, optionally creating it."""

    target = lexical_absolute(path)
    if contained_by is not None:
        root = lexical_absolute(contained_by)
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise SandboxInfrastructureError(
                phase, f"directory escapes its trusted root: {target}"
            ) from exc
    current = Path(target.anchor)
    for part in target.parts[1:]:
        current /= part
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            if not create:
                raise SandboxInfrastructureError(
                    phase, f"trusted directory is unavailable: {current}"
                )
            try:
                os.mkdir(current, 0o700)
                metadata = current.lstat()
            except OSError as exc:
                raise SandboxInfrastructureError(
                    phase, f"cannot create trusted directory {current}: {exc}"
                ) from exc
        except OSError as exc:
            raise SandboxInfrastructureError(
                phase, f"cannot inspect trusted directory {current}: {exc}"
            ) from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise SandboxInfrastructureError(
                phase, f"symlink is forbidden in trusted directory: {current}"
            )
        if not stat.S_ISDIR(metadata.st_mode):
            raise SandboxInfrastructureError(
                phase, f"trusted directory component is not a directory: {current}"
            )
    return target


def trusted_regular_path(
    path: str | Path,
    *,
    phase: str,
    contained_by: str | Path | None = None,
    allow_missing: bool = False,
) -> Path:
    """Validate one leaf as a contained regular non-symlink file."""

    target = lexical_absolute(path)
    if contained_by is not None:
        root = lexical_absolute(contained_by)
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise SandboxInfrastructureError(
                phase, f"file escapes its trusted root: {target}"
            ) from exc
    trusted_directory(target.parent, create=False, phase=phase)
    try:
        metadata = target.lstat()
    except FileNotFoundError:
        if allow_missing:
            return target
        raise SandboxInfrastructureError(
            phase, f"trusted file is unavailable: {target}"
        )
    except OSError as exc:
        raise SandboxInfrastructureError(
            phase, f"cannot inspect trusted file {target}: {exc}"
        ) from exc
    if stat.S_ISLNK(metadata.st_mode):
        raise SandboxInfrastructureError(
            phase, f"symlink is forbidden for trusted file: {target}"
        )
    if not stat.S_ISREG(metadata.st_mode):
        raise SandboxInfrastructureError(
            phase, f"trusted file is not regular: {target}"
        )
    return target


def atomic_bytes(path: Path, payload: bytes, *, phase: str) -> None:
    """Atomically replace one regular file without following stale symlinks."""

    target = lexical_absolute(path)
    trusted_directory(target.parent, create=True, phase=phase)
    trusted_regular_path(
        target, phase=phase, contained_by=target.parent, allow_missing=True
    )
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def atomic_json(path: Path, payload: Mapping[str, object]) -> None:
    """Durably replace one JSON document without exposing a partial write."""

    encoded = json.dumps(payload, sort_keys=True, indent=2).encode() + b"\n"
    atomic_bytes(path, encoded, phase="sandbox.atomic-write")


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


def read_bounded(
    backend: SandboxBackend,
    handle,
    path: str,
    *,
    max_bytes: int,
    timeout_seconds: int,
    phase: str,
) -> bytes:
    """Read a regular sandbox file through a bounded no-follow command."""

    if (
        not isinstance(path, str)
        or not path.startswith("/")
        or type(max_bytes) is not int
        or max_bytes <= 0
        or type(timeout_seconds) is not int
        or timeout_seconds <= 0
    ):
        raise SandboxInfrastructureError(
            phase, "invalid bounded read contract"
        )
    result = backend_call(
        phase,
        lambda: backend.run(
            handle,
            (
                "/usr/local/bin/python3",
                "-c",
                _BOUNDED_READ_CODE,
                path,
                str(max_bytes),
            ),
            environment={},
            timeout_seconds=timeout_seconds,
        ),
    )
    if not isinstance(result, SandboxCommandResult):
        raise SandboxInfrastructureError(
            phase, "backend returned an invalid bounded read result"
        )
    if result.timed_out:
        raise SandboxInfrastructureError(phase, "bounded read timed out")
    if result.exit_code != 0:
        raise SandboxInfrastructureError(
            phase, f"bounded read rejected remote file (exit {result.exit_code})"
        )
    maximum_encoded = 4 * ((max_bytes + 2) // 3)
    if len(result.stdout) > maximum_encoded:
        raise SandboxInfrastructureError(
            phase, "bounded read returned an oversized envelope"
        )
    try:
        payload = base64.b64decode(result.stdout.encode("ascii"), validate=True)
    except (UnicodeEncodeError, binascii.Error) as exc:
        raise SandboxInfrastructureError(
            phase, "bounded read returned invalid base64"
        ) from exc
    if len(payload) > max_bytes:
        raise SandboxInfrastructureError(
            phase, "bounded read exceeded its local contract"
        )
    return payload


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


def _redact_values(value: str, forbidden_values: Sequence[str]) -> str:
    cleaned = value
    for secret in sorted(
        {item for item in forbidden_values if isinstance(item, str) and item},
        key=len,
        reverse=True,
    ):
        cleaned = cleaned.replace(secret, "[REDACTED]")
    return cleaned


def write_command_log(
    path: Path,
    result: SandboxCommandResult,
    *,
    forbidden_values: Sequence[str] = (),
) -> None:
    """Persist only the bounded command result, never its environment or argv."""

    atomic_json(
        path,
        {
            "exit_code": result.exit_code,
            "stdout": _redact_values(result.stdout, forbidden_values),
            "stderr": _redact_values(result.stderr, forbidden_values),
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
    forbidden_values: Sequence[str] = (),
) -> None:
    """Finish lifecycle evidence and kill exactly the recorded native ID."""

    finish_error: SandboxInfrastructureError | None = None
    if lifecycle_path is not None and lifecycle_path.is_file() and not finished:
        try:
            mark_finished(
                lifecycle_path,
                at=clock(),
                failure=str(primary_error) if primary_error else "attempt interrupted",
                forbidden_values=forbidden_values,
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
        if finish_error is not None:
            cleanup_error.secondary_failures = (finish_error,)
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
    "atomic_bytes",
    "atomic_json",
    "backend_call",
    "finish_and_cleanup",
    "lexical_absolute",
    "public_model_environment",
    "read_bounded",
    "require_tmpfs",
    "run_required",
    "trusted_directory",
    "trusted_regular_path",
    "utc_now",
    "validate_public_model_env",
    "write_command_log",
]
