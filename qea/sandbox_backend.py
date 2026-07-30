"""Provider-neutral sandbox contracts with deterministic immutable identity."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from types import MappingProxyType
from typing import Literal, Mapping, Protocol, Sequence, runtime_checkable


SandboxRole = Literal["worker", "verifier", "evolver", "proxy", "canary"]
NetworkPolicy = Literal["none", "worker-proxy-only", "proxy-outbound"]
KillOutcome = Literal["killed", "already_absent"]

_ALLOWED_ROLES = frozenset({"worker", "verifier", "evolver", "proxy", "canary"})
_ALLOWED_NETWORK_POLICIES = frozenset(
    {"none", "worker-proxy-only", "proxy-outbound"}
)
_ROLE_NETWORK_POLICIES = {
    "worker": "worker-proxy-only",
    "evolver": "worker-proxy-only",
    "verifier": "none",
    "proxy": "proxy-outbound",
}
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
_RAW_IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}\Z")
_DIGEST_IMAGE_REF = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9._:/-]*@sha256:[0-9a-f]{64}\Z"
)
_E2B_TEMPLATE_REF = re.compile(r"e2b-template:[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
_ENVIRONMENT_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_PUBLIC_PROXY_SENTINEL = "qea-proxy-placeholder"
_PUBLIC_PROXY_KEY_NAMES = frozenset({"LLM_API_KEY", "OPENAI_API_KEY"})


class SandboxSpecError(ValueError):
    """A sandbox request violates the backend-neutral safety contract."""


def _require_identifier(label: str, value: object) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise SandboxSpecError(f"unsafe {label}: {value!r}")
    return value


def _require_positive_integer(label: str, value: object) -> int:
    if type(value) is not int or value <= 0:
        raise SandboxSpecError(f"{label} must be a positive integer")
    return value


def _is_secret_environment_name(name: str) -> bool:
    upper = name.upper()
    return (
        upper.endswith(("_API_KEY", "_TOKEN", "_SECRET", "_PASSWORD"))
        or "CREDENTIAL" in upper
        or upper in {"API_KEY", "TOKEN", "SECRET", "PASSWORD"}
    )


def _freeze_environment(values: Mapping[str, str]) -> Mapping[str, str]:
    if not isinstance(values, Mapping):
        raise SandboxSpecError("environment must be a mapping")
    normalized: dict[str, str] = {}
    for name, value in values.items():
        if not isinstance(name, str) or _ENVIRONMENT_NAME.fullmatch(name) is None:
            raise SandboxSpecError(f"unsafe environment name: {name!r}")
        if not isinstance(value, str) or "\x00" in value:
            raise SandboxSpecError(f"unsafe environment value for {name!r}")
        if _is_secret_environment_name(name) and not (
            name in _PUBLIC_PROXY_KEY_NAMES and value == _PUBLIC_PROXY_SENTINEL
        ):
            raise SandboxSpecError(
                f"secret environment value is forbidden for {name!r}"
            )
        normalized[name] = value
    return MappingProxyType(dict(sorted(normalized.items())))


def validate_sandbox_environment(values: Mapping[str, str]) -> Mapping[str, str]:
    """Return an immutable public-only environment mapping for sandbox commands."""

    return _freeze_environment(values)


def _freeze_tmpfs(values: Mapping[str, int]) -> Mapping[str, int]:
    if not isinstance(values, Mapping):
        raise SandboxSpecError("writable_tmpfs_mb must be a mapping")
    normalized: dict[str, int] = {}
    for raw_path, size_mb in values.items():
        if not isinstance(raw_path, str):
            raise SandboxSpecError(f"unsafe tmpfs path: {raw_path!r}")
        path = PurePosixPath(raw_path)
        if (
            not path.is_absolute()
            or raw_path == "/"
            or path.as_posix() != raw_path
            or any(part in {"", ".", ".."} for part in path.parts[1:])
        ):
            raise SandboxSpecError(f"unsafe tmpfs path: {raw_path!r}")
        normalized[raw_path] = _require_positive_integer(
            f"tmpfs size for {raw_path}", size_mb
        )
    return MappingProxyType(dict(sorted(normalized.items())))


def _freeze_executable_tmpfs(
    values: object,
    *,
    writable_tmpfs_mb: Mapping[str, int],
) -> frozenset[str]:
    if isinstance(values, (str, bytes)):
        raise SandboxSpecError("executable_tmpfs_paths must be a collection")
    try:
        normalized = frozenset(values)  # type: ignore[arg-type]
    except TypeError as exc:
        raise SandboxSpecError(
            "executable_tmpfs_paths must be a collection"
        ) from exc
    if any(not isinstance(path, str) for path in normalized):
        raise SandboxSpecError("executable tmpfs paths must be strings")
    outside = sorted(normalized - set(writable_tmpfs_mb))
    if outside:
        raise SandboxSpecError(
            f"executable tmpfs paths are not bounded writable mounts: {outside}"
        )
    return normalized


def _require_image_ref(value: object) -> str:
    if not isinstance(value, str) or not (
        _RAW_IMAGE_ID.fullmatch(value)
        or _DIGEST_IMAGE_REF.fullmatch(value)
        or _E2B_TEMPLATE_REF.fullmatch(value)
    ):
        raise SandboxSpecError(f"image_ref is not immutable: {value!r}")
    return value


@dataclass(frozen=True)
class SandboxSpec:
    """Validated resource, isolation, and identity request for one sandbox."""

    role: SandboxRole
    run_id: str
    attempt_id: str
    task_id: str
    image_ref: str
    cpu_count: int
    memory_mb: int
    pids_limit: int
    timeout_seconds: int
    network_policy: NetworkPolicy
    environment: Mapping[str, str] = field(default_factory=dict)
    writable_tmpfs_mb: Mapping[str, int] = field(default_factory=dict)
    executable_tmpfs_paths: frozenset[str] = field(default_factory=frozenset)
    network_scope: str | None = None

    def __post_init__(self) -> None:
        if self.role not in _ALLOWED_ROLES:
            raise SandboxSpecError(f"unsupported sandbox role: {self.role!r}")
        if self.network_policy not in _ALLOWED_NETWORK_POLICIES:
            raise SandboxSpecError(
                f"unsupported network policy: {self.network_policy!r}"
            )
        required_policy = _ROLE_NETWORK_POLICIES.get(self.role)
        if required_policy is not None and self.network_policy != required_policy:
            raise SandboxSpecError(
                f"sandbox role {self.role!r} requires network policy "
                f"{required_policy!r}"
            )
        _require_identifier("run_id", self.run_id)
        _require_identifier("attempt_id", self.attempt_id)
        _require_identifier("task_id", self.task_id)
        if self.network_scope is not None:
            _require_identifier("network_scope", self.network_scope)
        _require_image_ref(self.image_ref)
        _require_positive_integer("cpu_count", self.cpu_count)
        _require_positive_integer("memory_mb", self.memory_mb)
        _require_positive_integer("pids_limit", self.pids_limit)
        _require_positive_integer("timeout_seconds", self.timeout_seconds)
        object.__setattr__(self, "environment", _freeze_environment(self.environment))
        writable_tmpfs_mb = _freeze_tmpfs(self.writable_tmpfs_mb)
        object.__setattr__(self, "writable_tmpfs_mb", writable_tmpfs_mb)
        object.__setattr__(
            self,
            "executable_tmpfs_paths",
            _freeze_executable_tmpfs(
                self.executable_tmpfs_paths,
                writable_tmpfs_mb=writable_tmpfs_mb,
            ),
        )

    def canonical_json(self) -> str:
        """Return the stable JSON payload whose hash is the sandbox identity."""

        payload = {
            "attempt_id": self.attempt_id,
            "cpu_count": self.cpu_count,
            "environment": dict(self.environment),
            "executable_tmpfs_paths": sorted(self.executable_tmpfs_paths),
            "image_ref": self.image_ref,
            "memory_mb": self.memory_mb,
            "network_policy": self.network_policy,
            "network_scope": self.network_scope,
            "pids_limit": self.pids_limit,
            "role": self.role,
            "run_id": self.run_id,
            "task_id": self.task_id,
            "timeout_seconds": self.timeout_seconds,
            "writable_tmpfs_mb": dict(self.writable_tmpfs_mb),
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    @property
    def spec_sha256(self) -> str:
        """Return a content digest for the complete validated contract."""

        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SandboxHandle:
    backend: str
    native_id: str
    immutable_image_ref: str
    spec_sha256: str


@dataclass(frozen=True)
class SandboxNetworkHandle:
    backend: str
    native_id: str
    name: str
    run_id: str
    network_scope: str
    identity_sha256: str


@dataclass(frozen=True)
class SandboxCommandResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool


@dataclass(frozen=True)
class SandboxState:
    backend: str
    native_id: str
    status: str
    labels: Mapping[str, str]
    immutable_image_ref: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "labels",
            MappingProxyType(dict(sorted(self.labels.items()))),
        )


@dataclass(frozen=True)
class KillResult:
    native_id: str
    outcome: KillOutcome


class SandboxBackend(Protocol):
    """Minimal operations shared by remote and self-hosted sandboxes."""

    backend_name: str

    def create(self, spec: SandboxSpec) -> SandboxHandle:
        raise NotImplementedError

    def start(self, handle: SandboxHandle) -> None:
        raise NotImplementedError

    def put_bytes(self, handle: SandboxHandle, path: str, payload: bytes) -> None:
        raise NotImplementedError

    def read_bytes(self, handle: SandboxHandle, path: str) -> bytes:
        raise NotImplementedError

    def run(
        self,
        handle: SandboxHandle,
        argv: Sequence[str],
        *,
        environment: Mapping[str, str],
        timeout_seconds: int,
    ) -> SandboxCommandResult:
        raise NotImplementedError

    def inspect(self, native_id: str) -> SandboxState | None:
        raise NotImplementedError

    def list(self, labels: Mapping[str, str]) -> Sequence[SandboxState]:
        raise NotImplementedError

    def kill(self, native_id: str) -> KillResult:
        raise NotImplementedError


@runtime_checkable
class ScopedNetworkBackend(Protocol):
    """Optional exact-ID lifecycle contract for attempt-scoped networks."""

    def create_internal_network(
        self,
        *,
        run_id: str,
        network_scope: str,
    ) -> SandboxNetworkHandle:
        raise NotImplementedError

    def remove_internal_network(
        self,
        handle: SandboxNetworkHandle,
    ) -> KillOutcome:
        raise NotImplementedError
