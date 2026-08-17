"""A fixed-upstream model proxy that injects credentials outside workers."""

from __future__ import annotations

import hashlib
import http.client
import ipaddress
import json
import os
import re
import stat
import tempfile
import threading
import time
from email.utils import parsedate_to_datetime
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from typing import Callable, Mapping, Sequence
from urllib.parse import SplitResult, unquote, urlsplit

from .sandbox_backend import SandboxSpec


_HOP_BY_HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "proxy-connection",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
    }
)
_TOKEN_PATH = "/run/qea-secrets/model-token"
_MAX_TOKEN_BYTES = 16 * 1024
_MAX_AUDIT_BYTES = 16 * 1024 * 1024
_BUFFER_SIZE = 64 * 1024
_FINALIZE_PATH = "/__qea_private/finalize"
_ALLOWED_METHODS = frozenset({"GET", "POST"})
_AUDIT_STATES = frozenset({"not_accepted", "completed", "quarantined"})
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_PROVIDER_SLUG = re.compile(
    r"[a-z0-9][a-z0-9._-]*(?:/[a-z0-9][a-z0-9._-]*)?\Z"
)
_AUDIT_KEYS = frozenset(
    {
        "schema_version",
        "request_identity_sha256",
        "model",
        "started_at",
        "finished_at",
        "latency_ms",
        "request_state",
        "upstream_status_code",
        "provider_request_id",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "provider_cost_usd",
        "failure_class",
    }
)
_AUDIT_V2_KEYS = _AUDIT_KEYS | frozenset(
    {"logical_request_identity_sha256", "retry_index"}
)
_PROVIDER_REQUEST_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,511}\Z")
_MAX_DENIED_REQUEST_IDENTITIES = 10_000
_MAX_PRE_ACCEPT_CONNECT_ATTEMPTS = 5
_PRE_ACCEPT_CONNECT_BACKOFF_SECONDS = 0.25
_MAX_RATE_LIMIT_ATTEMPTS = 3
_EMPTY_RESPONSE_RECOVERY_MAX_TOKENS = 8192
_RATE_LIMIT_RETRY_BUDGET_SECONDS = 60.0
_RATE_LIMIT_BACKOFF_SECONDS = 1.0


class ModelProxyError(RuntimeError):
    """Proxy configuration, routing, token storage, or exposure is unsafe."""


class _AuditAppendFailed(ModelProxyError):
    pass


class _AuditStreamIncomplete(ModelProxyError):
    pass


class _RateLimitRetryDeadlineExpired(TimeoutError):
    pass


@dataclass(frozen=True)
class _Upstream:
    scheme: str
    hostname: str
    port: int
    authority: str
    base_path: str


def _parse_upstream(value: str) -> _Upstream:
    if not isinstance(value, str):
        raise ModelProxyError("upstream base URL must be a string")
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ModelProxyError("upstream base URL must be one fixed HTTP(S) origin and path")
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as exc:
        raise ModelProxyError("upstream base URL has an invalid port") from exc
    base_path = parsed.path.rstrip("/")
    if not base_path.startswith("/"):
        raise ModelProxyError("upstream base URL requires an absolute path")
    if _unsafe_path(base_path or "/"):
        raise ModelProxyError("upstream base URL contains an unsafe path")
    default_port = 443 if parsed.scheme == "https" else 80
    authority = parsed.hostname if port == default_port else f"{parsed.hostname}:{port}"
    return _Upstream(
        scheme=parsed.scheme,
        hostname=parsed.hostname,
        port=port,
        authority=authority,
        base_path=base_path,
    )


def _validate_prefix(value: str) -> str:
    if not isinstance(value, str) or not value.startswith("/") or value == "/":
        raise ModelProxyError("allowed path prefix must be an absolute non-root path")
    normalized = value.rstrip("/")
    if _unsafe_path(normalized):
        raise ModelProxyError("allowed path prefix is unsafe")
    return normalized


def _unsafe_path(value: str) -> bool:
    lowered = value.lower()
    if "%2f" in lowered or "%5c" in lowered or "\\" in value:
        return True
    try:
        decoded = unquote(value, errors="strict")
    except (UnicodeDecodeError, ValueError):
        return True
    path = PurePosixPath(decoded)
    return any(part in {"", ".", ".."} for part in path.parts[1:])


def _read_token_bytes(path: Path) -> bytes:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise ModelProxyError("token file is unavailable") from exc
    if path.is_symlink() or not stat.S_ISREG(metadata.st_mode):
        raise ModelProxyError("token file must be a regular non-symlink file")
    if stat.S_IMODE(metadata.st_mode) & 0o077:
        raise ModelProxyError("token file must have no group or other permission bits")
    if hasattr(os, "getuid") and metadata.st_uid != os.getuid():
        raise ModelProxyError("token file must be owned by the proxy user")
    if metadata.st_size > _MAX_TOKEN_BYTES:
        raise ModelProxyError("token file is too large")
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise ModelProxyError("token file is unreadable") from exc
    if len(payload) > _MAX_TOKEN_BYTES:
        raise ModelProxyError("token file is too large")
    payload = payload.rstrip(b"\r\n")
    if not payload or any(value < 0x21 or value > 0x7E for value in payload):
        raise ModelProxyError("token file must contain one printable credential")
    try:
        payload.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ModelProxyError("token file must contain one printable credential") from exc
    return payload


def _read_token(path: Path) -> str:
    return _read_token_bytes(path).decode("ascii")


def _validate_model(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 256
        or any(ord(character) < 0x21 or ord(character) > 0x7E for character in value)
    ):
        raise ModelProxyError("allowed model must be one bounded printable identity")
    return value


def _validate_provider_slug(value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) > 128
        or _PROVIDER_SLUG.fullmatch(value) is None
    ):
        raise ModelProxyError("required provider must be one bounded safe slug")
    return value


def _validate_denied_request_identities(
    values: Sequence[str],
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise ModelProxyError("denied request identities must be a bounded sequence")
    if len(values) > _MAX_DENIED_REQUEST_IDENTITIES:
        raise ModelProxyError("denied request identity set exceeds its bound")
    normalized: set[str] = set()
    for value in values:
        if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
            raise ModelProxyError("denied request identity must be lowercase SHA-256")
        normalized.add(value)
    return tuple(sorted(normalized))


def _validate_audit_path(value: Path | str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ModelProxyError("audit file must use an absolute private path")
    parent = path.parent
    if parent.is_symlink() or not parent.is_dir():
        raise ModelProxyError("audit file parent must be an existing non-symlink directory")
    if path.exists() or path.is_symlink():
        try:
            metadata = path.lstat()
        except OSError as exc:
            raise ModelProxyError("audit file is unavailable") from exc
        if path.is_symlink() or not stat.S_ISREG(metadata.st_mode):
            raise ModelProxyError("audit file must be a regular non-symlink file")
        if hasattr(os, "getuid") and metadata.st_uid != os.getuid():
            raise ModelProxyError("audit file must be owned by the proxy user")
        if stat.S_IMODE(metadata.st_mode) & 0o077:
            raise ModelProxyError("audit file must have no group or other permission bits")
    return path


def _open_private_audit(path: Path) -> int:
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as exc:
        raise ModelProxyError("audit file cannot be opened safely") from exc
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ModelProxyError("audit file must be regular")
        if hasattr(os, "getuid") and metadata.st_uid != os.getuid():
            raise ModelProxyError("audit file must be owned by the proxy user")
        if stat.S_IMODE(metadata.st_mode) & 0o077:
            raise ModelProxyError("audit file must have no group or other permission bits")
        os.fchmod(descriptor, 0o600)
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _ensure_private_audit(path: Path) -> None:
    descriptor = _open_private_audit(path)
    os.close(descriptor)


def _append_audit(
    path: Path,
    record: Mapping[str, object],
    *,
    lock: threading.Lock,
) -> None:
    schema_version = record.get("schema_version")
    expected_keys = _AUDIT_KEYS if schema_version == 1 else _AUDIT_V2_KEYS
    if set(record) != expected_keys or schema_version not in {1, 2}:
        raise ModelProxyError("audit record has an unsafe schema")
    if record.get("request_state") not in _AUDIT_STATES:
        raise ModelProxyError("audit record has an unsafe request state")
    encoded = (
        json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    with lock:
        descriptor = _open_private_audit(path)
        try:
            written = os.write(descriptor, encoded)
            if written != len(encoded):
                raise ModelProxyError("audit record write was incomplete")
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _sealed_audit_bytes(path: Path) -> bytes:
    descriptor = _open_private_audit(path)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ModelProxyError("audit file cannot be sealed safely") from exc
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ModelProxyError("audit file must be regular")
        if hasattr(os, "getuid") and metadata.st_uid != os.getuid():
            raise ModelProxyError("audit file must be owned by the proxy user")
        if stat.S_IMODE(metadata.st_mode) & 0o077:
            raise ModelProxyError(
                "audit file must have no group or other permission bits"
            )
        payload = bytearray()
        while True:
            chunk = os.read(descriptor, _BUFFER_SIZE)
            if not chunk:
                break
            payload.extend(chunk)
            if len(payload) > _MAX_AUDIT_BYTES:
                raise ModelProxyError("audit file exceeds its seal bound")
        return bytes(payload)
    finally:
        os.close(descriptor)


@dataclass(frozen=True)
class ModelProxyConfig:
    """Validated listener, upstream, token-file, and size/time limits."""

    listen_host: str
    listen_port: int
    upstream_base_url: str
    allowed_path_prefix: str
    allowed_model: str
    token_file: Path | str
    audit_file: Path | str
    denied_request_identities_sha256: tuple[str, ...] = ()
    max_request_bytes: int = 8 * 1024 * 1024
    max_response_bytes: int = 64 * 1024 * 1024
    connect_timeout_seconds: float = 10.0
    read_timeout_seconds: float = 300.0
    pre_accept_connect_attempts: int = 3
    rate_limit_max_attempts: int = _MAX_RATE_LIMIT_ATTEMPTS
    rate_limit_retry_budget_seconds: float = _RATE_LIMIT_RETRY_BUDGET_SECONDS
    rate_limit_backoff_seconds: float = _RATE_LIMIT_BACKOFF_SECONDS
    required_provider: str | None = None
    fallback_providers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.listen_host not in {"127.0.0.1", "0.0.0.0"}:
            raise ModelProxyError("proxy listener must use an explicit IPv4 bind address")
        if type(self.listen_port) is not int or not 0 <= self.listen_port <= 65535:
            raise ModelProxyError("proxy listener port is invalid")
        _parse_upstream(self.upstream_base_url)
        object.__setattr__(
            self, "allowed_path_prefix", _validate_prefix(self.allowed_path_prefix)
        )
        object.__setattr__(self, "allowed_model", _validate_model(self.allowed_model))
        if self.required_provider is not None:
            object.__setattr__(
                self,
                "required_provider",
                _validate_provider_slug(self.required_provider),
            )
        if not isinstance(self.fallback_providers, tuple):
            raise ModelProxyError("fallback_providers must be a tuple")
        normalized_fallbacks = tuple(
            _validate_provider_slug(provider)
            for provider in self.fallback_providers
        )
        if normalized_fallbacks and self.required_provider is None:
            raise ModelProxyError(
                "fallback providers require a primary required provider"
            )
        if len(set(normalized_fallbacks)) != len(normalized_fallbacks):
            raise ModelProxyError("fallback providers must be unique")
        if self.required_provider in normalized_fallbacks:
            raise ModelProxyError(
                "fallback providers must not repeat the primary provider"
            )
        object.__setattr__(self, "fallback_providers", normalized_fallbacks)
        token_path = Path(self.token_file).expanduser()
        _read_token(token_path)
        object.__setattr__(self, "token_file", token_path)
        object.__setattr__(self, "audit_file", _validate_audit_path(self.audit_file))
        object.__setattr__(
            self,
            "denied_request_identities_sha256",
            _validate_denied_request_identities(
                self.denied_request_identities_sha256
            ),
        )
        for name in ("max_request_bytes", "max_response_bytes"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ModelProxyError(f"{name} must be a positive integer")
        for name in ("connect_timeout_seconds", "read_timeout_seconds"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                raise ModelProxyError(f"{name} must be positive")
        if (
            type(self.pre_accept_connect_attempts) is not int
            or not 1
            <= self.pre_accept_connect_attempts
            <= _MAX_PRE_ACCEPT_CONNECT_ATTEMPTS
        ):
            raise ModelProxyError(
                "pre_accept_connect_attempts must be an integer in [1, 5]"
            )
        if self.rate_limit_max_attempts != _MAX_RATE_LIMIT_ATTEMPTS:
            raise ModelProxyError("rate_limit_max_attempts must equal 3")
        if self.rate_limit_retry_budget_seconds != _RATE_LIMIT_RETRY_BUDGET_SECONDS:
            raise ModelProxyError("rate_limit_retry_budget_seconds must equal 60.0")
        if self.rate_limit_backoff_seconds != _RATE_LIMIT_BACKOFF_SECONDS:
            raise ModelProxyError("rate_limit_backoff_seconds must equal 1.0")


@dataclass(frozen=True)
class SecretScanReport:
    scanned_surfaces: int
    scanned_files: int
    scanned_bytes: int
    exposed_surfaces: tuple[str, ...] = ()


def scan_secret_exposure(
    secret: bytes,
    surfaces: Mapping[str, bytes | str | Path],
    *,
    max_file_bytes: int = 512 * 1024 * 1024,
    max_total_bytes: int = 2 * 1024 * 1024 * 1024,
) -> SecretScanReport:
    """Fail closed if one exact secret occurs in any declared surface."""

    if not isinstance(secret, bytes) or not secret or len(secret) > _MAX_TOKEN_BYTES:
        raise ModelProxyError("secret scanner requires bounded non-empty bytes")
    if not isinstance(surfaces, Mapping) or not surfaces:
        raise ModelProxyError("secret scanner requires named surfaces")
    if type(max_file_bytes) is not int or max_file_bytes <= 0:
        raise ModelProxyError("max_file_bytes must be positive")
    if type(max_total_bytes) is not int or max_total_bytes <= 0:
        raise ModelProxyError("max_total_bytes must be positive")
    scanned_bytes = 0
    scanned_files = 0
    exposed: list[str] = []

    def inspect_payload(name: str, payload: bytes, *, is_file: bool) -> None:
        nonlocal scanned_bytes, scanned_files
        if is_file:
            scanned_files += 1
        if len(payload) > max_file_bytes:
            raise ModelProxyError(f"secret scan surface exceeds file limit: {name}")
        scanned_bytes += len(payload)
        if scanned_bytes > max_total_bytes:
            raise ModelProxyError("secret scan exceeds total byte limit")
        if secret in payload:
            exposed.append(name)

    for raw_name, surface in sorted(surfaces.items()):
        if not isinstance(raw_name, str) or not raw_name or any(
            character in raw_name for character in ("\x00", "\n", "\r")
        ):
            raise ModelProxyError("secret scan surface name is unsafe")
        if isinstance(surface, bytes):
            inspect_payload(raw_name, surface, is_file=False)
        elif isinstance(surface, str):
            inspect_payload(raw_name, surface.encode(), is_file=False)
        elif isinstance(surface, Path):
            root = surface.resolve()
            if surface.is_symlink():
                raise ModelProxyError(f"secret scan surface is a symlink: {raw_name}")
            if root.is_file():
                inspect_payload(raw_name, root.read_bytes(), is_file=True)
            elif root.is_dir():
                for path in sorted(root.rglob("*")):
                    if path.is_symlink():
                        relative = path.relative_to(root).as_posix()
                        raise ModelProxyError(
                            f"secret scan encountered symlink: {raw_name}/{relative}"
                        )
                    if path.is_file():
                        relative = path.relative_to(root).as_posix()
                        inspect_payload(
                            f"{raw_name}/{relative}", path.read_bytes(), is_file=True
                        )
                    elif not path.is_dir():
                        raise ModelProxyError(
                            f"secret scan encountered non-regular entry: {raw_name}"
                        )
            else:
                raise ModelProxyError(f"secret scan surface is missing: {raw_name}")
        else:
            raise ModelProxyError(f"unsupported secret scan surface: {raw_name}")
    if exposed:
        raise ModelProxyError(
            "secret exposure detected at " + ", ".join(sorted(exposed))
        )
    return SecretScanReport(
        scanned_surfaces=len(surfaces),
        scanned_files=scanned_files,
        scanned_bytes=scanned_bytes,
    )


@dataclass(frozen=True)
class ModelProxySandboxPlan:
    """Public-only proxy sandbox identity and token-file launch arguments."""

    spec: SandboxSpec
    token_path: str
    start_argv: tuple[str, ...]
    upstream_base_url: str
    allowed_path_prefix: str
    listen_port: int
    allowed_model: str | None = None
    audit_path: str | None = None
    network_scope: str | None = None
    denied_request_identities_sha256: tuple[str, ...] = ()
    required_provider: str | None = None
    fallback_providers: tuple[str, ...] = ()
    pre_accept_connect_attempts: int = 3
    rate_limit_max_attempts: int = _MAX_RATE_LIMIT_ATTEMPTS
    rate_limit_retry_budget_seconds: float = _RATE_LIMIT_RETRY_BUDGET_SECONDS
    rate_limit_backoff_seconds: float = _RATE_LIMIT_BACKOFF_SECONDS

    def config_payload(self) -> dict[str, object]:
        """Return the public config uploaded before the token appears."""

        payload: dict[str, object] = {
            "listen_host": "0.0.0.0",
            "listen_port": self.listen_port,
            "upstream_base_url": self.upstream_base_url,
            "allowed_path_prefix": self.allowed_path_prefix,
            "max_request_bytes": 8 * 1024 * 1024,
            "max_response_bytes": 64 * 1024 * 1024,
            "connect_timeout_seconds": 10.0,
            "read_timeout_seconds": 300.0,
            "pre_accept_connect_attempts": self.pre_accept_connect_attempts,
            "rate_limit_max_attempts": self.rate_limit_max_attempts,
            "rate_limit_retry_budget_seconds": self.rate_limit_retry_budget_seconds,
            "rate_limit_backoff_seconds": self.rate_limit_backoff_seconds,
        }
        if self.allowed_model is not None:
            payload["allowed_model"] = self.allowed_model
            if self.required_provider is not None:
                payload["required_provider"] = self.required_provider
                if self.fallback_providers:
                    payload["fallback_providers"] = list(
                        self.fallback_providers
                    )
            payload["audit_file"] = self.audit_path
            payload["denied_request_identities_sha256"] = list(
                self.denied_request_identities_sha256
            )
        return payload

    def public_payload(self) -> dict[str, object]:
        payload = {
            "schema_version": 1,
            "spec": {
                "role": self.spec.role,
                "run_id": self.spec.run_id,
                "attempt_id": self.spec.attempt_id,
                "task_id": self.spec.task_id,
                "image_ref": self.spec.image_ref,
                "cpu_count": self.spec.cpu_count,
                "memory_mb": self.spec.memory_mb,
                "pids_limit": self.spec.pids_limit,
                "timeout_seconds": self.spec.timeout_seconds,
                "network_policy": self.spec.network_policy,
                "network_scope": self.spec.network_scope,
                "environment": dict(self.spec.environment),
                "writable_tmpfs_mb": dict(self.spec.writable_tmpfs_mb),
                "spec_sha256": self.spec.spec_sha256,
            },
            "token_path": self.token_path,
            "start_argv": list(self.start_argv),
            "upstream_base_url": self.upstream_base_url,
            "allowed_path_prefix": self.allowed_path_prefix,
            "listen_port": self.listen_port,
            "allowed_model": self.allowed_model,
            "audit_path": self.audit_path,
            "denied_request_identities_sha256": list(
                self.denied_request_identities_sha256
            ),
            "pre_accept_connect_attempts": self.pre_accept_connect_attempts,
            "rate_limit_max_attempts": self.rate_limit_max_attempts,
            "rate_limit_retry_budget_seconds": self.rate_limit_retry_budget_seconds,
            "rate_limit_backoff_seconds": self.rate_limit_backoff_seconds,
        }
        if self.required_provider is not None:
            payload["required_provider"] = self.required_provider
            if self.fallback_providers:
                payload["fallback_providers"] = list(self.fallback_providers)
        return payload


def model_proxy_attempt_identity(
    *, public_plan_sha256: str, public_config_sha256: str
) -> str:
    """Bind the executed public proxy plan and uploaded public config."""

    if (
        not isinstance(public_plan_sha256, str)
        or _SHA256.fullmatch(public_plan_sha256) is None
        or not isinstance(public_config_sha256, str)
        or _SHA256.fullmatch(public_config_sha256) is None
    ):
        raise ModelProxyError("proxy public identity digest is invalid")
    return hashlib.sha256(
        json.dumps(
            {
                "public_config_sha256": public_config_sha256,
                "public_plan_sha256": public_plan_sha256,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def model_proxy_plan_identity(
    plan: ModelProxySandboxPlan,
) -> tuple[str, str, str]:
    """Return public plan, public config, and combined executed digests."""

    if not isinstance(plan, ModelProxySandboxPlan):
        raise ModelProxyError("proxy plan identity requires a sandbox plan")
    public_plan_sha256 = hashlib.sha256(
        json.dumps(
            plan.public_payload(), sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    public_config_sha256 = hashlib.sha256(
        json.dumps(
            plan.config_payload(), sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    return (
        public_plan_sha256,
        public_config_sha256,
        model_proxy_attempt_identity(
            public_plan_sha256=public_plan_sha256,
            public_config_sha256=public_config_sha256,
        ),
    )


def build_model_proxy_sandbox_plan(
    *,
    run_id: str,
    attempt_id: str,
    task_id: str = "model-proxy",
    image_ref: str,
    upstream_base_url: str,
    allowed_path_prefix: str,
    listen_port: int,
    cpu_count: int,
    memory_mb: int,
    pids_limit: int,
    timeout_seconds: int,
    network_scope: str | None = None,
    allowed_model: str | None = None,
    required_provider: str | None = None,
    fallback_providers: Sequence[str] = (),
    audit_path: str | None = None,
    denied_request_identities_sha256: Sequence[str] = (),
    writable_tmpfs_mb: Mapping[str, int] | None = None,
    pre_accept_connect_attempts: int = 3,
    rate_limit_max_attempts: int = _MAX_RATE_LIMIT_ATTEMPTS,
    rate_limit_retry_budget_seconds: float = _RATE_LIMIT_RETRY_BUDGET_SECONDS,
    rate_limit_backoff_seconds: float = _RATE_LIMIT_BACKOFF_SECONDS,
) -> ModelProxySandboxPlan:
    """Build a proxy plan that has no API-key argument, env value, or label."""

    _parse_upstream(upstream_base_url)
    prefix = _validate_prefix(allowed_path_prefix)
    if type(listen_port) is not int or not 1 <= listen_port <= 65535:
        raise ModelProxyError("proxy plan listener port is invalid")
    supplied_policy = (network_scope, allowed_model, audit_path)
    if any(value is not None for value in supplied_policy) and any(
        value is None for value in supplied_policy
    ):
        raise ModelProxyError(
            "network_scope, allowed_model, and audit_path must be supplied together"
        )
    if allowed_model is not None:
        allowed_model = _validate_model(allowed_model)
        if required_provider is not None:
            required_provider = _validate_provider_slug(required_provider)
        normalized_fallbacks = tuple(
            _validate_provider_slug(provider)
            for provider in fallback_providers
        )
        if normalized_fallbacks and required_provider is None:
            raise ModelProxyError(
                "fallback providers require a primary required provider"
            )
        if len(set(normalized_fallbacks)) != len(normalized_fallbacks):
            raise ModelProxyError("fallback providers must be unique")
        if required_provider in normalized_fallbacks:
            raise ModelProxyError(
                "fallback providers must not repeat the primary provider"
            )
        if not isinstance(audit_path, str) or not audit_path.startswith("/"):
            raise ModelProxyError("proxy plan audit path must be absolute")
    elif required_provider is not None:
        raise ModelProxyError(
            "required provider requires the complete scoped proxy policy"
        )
    else:
        normalized_fallbacks = ()
    denied_identities = _validate_denied_request_identities(
        denied_request_identities_sha256
    )
    if (
        type(pre_accept_connect_attempts) is not int
        or not 1
        <= pre_accept_connect_attempts
        <= _MAX_PRE_ACCEPT_CONNECT_ATTEMPTS
    ):
        raise ModelProxyError(
            "pre_accept_connect_attempts must be an integer in [1, 5]"
        )
    if denied_identities and allowed_model is None:
        raise ModelProxyError(
            "denied request identities require the complete scoped proxy policy"
        )
    if rate_limit_max_attempts != _MAX_RATE_LIMIT_ATTEMPTS:
        raise ModelProxyError("rate_limit_max_attempts must equal 3")
    if rate_limit_retry_budget_seconds != _RATE_LIMIT_RETRY_BUDGET_SECONDS:
        raise ModelProxyError("rate_limit_retry_budget_seconds must equal 60.0")
    if rate_limit_backoff_seconds != _RATE_LIMIT_BACKOFF_SECONDS:
        raise ModelProxyError("rate_limit_backoff_seconds must equal 1.0")
    spec = SandboxSpec(
        role="proxy",
        run_id=run_id,
        attempt_id=attempt_id,
        task_id=task_id,
        image_ref=image_ref,
        cpu_count=cpu_count,
        memory_mb=memory_mb,
        pids_limit=pids_limit,
        timeout_seconds=timeout_seconds,
        network_policy="proxy-outbound",
        environment={},
        writable_tmpfs_mb=(
            {
                "/run/qea-secrets": 1,
                "/tmp": 64,
            }
            if writable_tmpfs_mb is None
            else writable_tmpfs_mb
        ),
        network_scope=network_scope,
    )
    argv = (
        "/usr/local/bin/python3",
        "/usr/local/lib/qea/run_qea_model_proxy.py",
        "--listen-host",
        "0.0.0.0",
        "--listen-port",
        str(listen_port),
        "--upstream-base-url",
        upstream_base_url,
        "--allowed-path-prefix",
        prefix,
        "--token-file",
        _TOKEN_PATH,
    )
    return ModelProxySandboxPlan(
        spec=spec,
        token_path=_TOKEN_PATH,
        start_argv=argv,
        upstream_base_url=upstream_base_url,
        allowed_path_prefix=prefix,
        listen_port=listen_port,
        allowed_model=allowed_model,
        audit_path=audit_path,
        network_scope=network_scope,
        denied_request_identities_sha256=denied_identities,
        required_provider=required_provider,
        fallback_providers=normalized_fallbacks,
        pre_accept_connect_attempts=pre_accept_connect_attempts,
        rate_limit_max_attempts=rate_limit_max_attempts,
        rate_limit_retry_budget_seconds=rate_limit_retry_budget_seconds,
        rate_limit_backoff_seconds=rate_limit_backoff_seconds,
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def start_model_proxy_sandbox(
    *,
    backend,
    plan: ModelProxySandboxPlan,
    token: bytes,
    lifecycle_path: str | Path,
    clock: Callable[[], datetime] = _now,
):
    """Start the fixed waiting entrypoint, then upload public config and token."""

    from .sandbox_lifecycle import create_lifecycle, mark_cleaned, mark_started

    if (
        not isinstance(token, bytes)
        or not token
        or len(token) > _MAX_TOKEN_BYTES
        or any(value < 0x21 or value > 0x7E for value in token)
    ):
        raise ModelProxyError("proxy token must be bounded printable bytes")
    lifecycle = Path(lifecycle_path).expanduser().resolve()
    public = json.dumps(
        plan.public_payload(), sort_keys=True, separators=(",", ":")
    ).encode()
    attempt_identity = hashlib.sha256(public).hexdigest()
    handle = None
    lifecycle_written = False
    try:
        handle = backend.create(plan.spec)
        create_lifecycle(
            lifecycle,
            handle=handle,
            spec=plan.spec,
            attempt_identity_sha256=attempt_identity,
            at=clock(),
        )
        lifecycle_written = True
        backend.start(handle)
        mark_started(lifecycle, at=clock())
        config_payload = (
            json.dumps(
                plan.config_payload(), sort_keys=True, separators=(",", ":")
            ).encode()
            + b"\n"
        )
        backend.put_bytes(
            handle, "/run/qea-secrets/proxy-config.json", config_payload
        )
        backend.put_bytes(handle, plan.token_path, token)
        return handle
    except Exception as exc:  # noqa: BLE001 - secret-aware backend boundary.
        cleanup_error = None
        if handle is not None:
            try:
                result = backend.kill(handle.native_id)
                if lifecycle_written:
                    mark_cleaned(
                        lifecycle,
                        cleanup_method="exact-id",
                        cleanup_result=result.outcome,
                        at=clock(),
                    )
            except Exception as cleanup_exc:  # noqa: BLE001
                cleanup_error = cleanup_exc
        detail = str(exc)
        try:
            detail = detail.replace(token.decode("ascii"), "[REDACTED]")
        except UnicodeDecodeError:
            detail = "proxy sandbox startup failed"
        if cleanup_error is not None:
            raise ModelProxyError("proxy sandbox startup and exact-ID cleanup failed") from exc
        raise ModelProxyError(
            "proxy sandbox startup failed: " + " ".join(detail.split())[:1_000]
        ) from exc


@dataclass(frozen=True)
class _ProxyPolicy:
    upstream: _Upstream
    prefix: str
    token: str
    allowed_model: str
    required_provider: str | None
    fallback_providers: tuple[str, ...]
    audit_file: Path
    denied_request_identities_sha256: frozenset[str]
    max_request_bytes: int
    max_response_bytes: int
    connect_timeout_seconds: float
    read_timeout_seconds: float
    pre_accept_connect_attempts: int = 3
    rate_limit_max_attempts: int = _MAX_RATE_LIMIT_ATTEMPTS
    rate_limit_retry_budget_seconds: float = _RATE_LIMIT_RETRY_BUDGET_SECONDS
    rate_limit_backoff_seconds: float = _RATE_LIMIT_BACKOFF_SECONDS


@dataclass(frozen=True)
class _BufferedUpstreamResponse:
    status: int
    headers: tuple[tuple[str, str], ...]
    body: bytes
    provider_request_id: str | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    provider_cost_usd: int | float | None
    retry_after_values: tuple[str, ...]


def _connection_tokens(headers) -> set[str]:
    tokens: set[str] = set()
    for value in headers.get_all("Connection", []):
        tokens.update(part.strip().lower() for part in value.split(",") if part.strip())
    return tokens


def _filtered_request_headers(headers, policy: _ProxyPolicy, body_size: int) -> dict[str, str]:
    blocked = set(_HOP_BY_HOP) | _connection_tokens(headers) | {
        "authorization",
        "host",
        "content-length",
    }
    output: dict[str, str] = {}
    for name, value in headers.items():
        if name.lower() not in blocked:
            output[name] = value
    output["Host"] = policy.upstream.authority
    output["Authorization"] = f"Bearer {policy.token}"
    output["Content-Length"] = str(body_size)
    return output


def _filtered_response_headers(headers) -> tuple[tuple[str, str], ...]:
    blocked = set(_HOP_BY_HOP) | _connection_tokens(headers) | {"content-length"}
    return tuple(
        (name, value)
        for name, value in headers.items()
        if name.lower() not in blocked
    )


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def model_proxy_wire_request_identity(
    logical_request_identity_sha256: str, retry_index: int
) -> str:
    """Derive one wire-attempt identity from a stable logical call identity."""

    if (
        not isinstance(logical_request_identity_sha256, str)
        or _SHA256.fullmatch(logical_request_identity_sha256) is None
        or type(retry_index) is not int
        or not 0 <= retry_index < _MAX_RATE_LIMIT_ATTEMPTS
    ):
        raise ModelProxyError("proxy wire request identity input is invalid")
    return hashlib.sha256(
        json.dumps(
            {
                "logical_request_identity_sha256": logical_request_identity_sha256,
                "retry_index": retry_index,
                "schema_version": 2,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def _retry_after_seconds(value: str, *, now: datetime) -> float:
    """Parse one present Retry-After strictly; absence is handled by the caller."""

    if not isinstance(value, str) or not value or value != value.strip():
        raise ModelProxyError("Retry-After is malformed")
    if value.isascii() and value.isdigit():
        delay = float(int(value))
    else:
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ModelProxyError("Retry-After is malformed") from exc
        if parsed.tzinfo is None:
            raise ModelProxyError("Retry-After date lacks a timezone")
        delay = (parsed.astimezone(timezone.utc) - now).total_seconds()
    if delay < 0:
        raise ModelProxyError("Retry-After is negative")
    return delay


def _bounded_nonnegative_integer(value: object) -> int | None:
    if type(value) is int and 0 <= value <= 10**12:
        return value
    return None


def _bounded_nonnegative_cost(value: object) -> int | float | None:
    if (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and 0 <= value <= 10**9
    ):
        return value
    return None


def _decoded_usage(
    decoded: object,
) -> tuple[int | None, int | None, int | None, int | float | None]:
    if not isinstance(decoded, dict) or not isinstance(decoded.get("usage"), dict):
        return None, None, None, None
    usage = decoded["usage"]
    input_tokens = _bounded_nonnegative_integer(
        usage.get("prompt_tokens", usage.get("input_tokens"))
    )
    output_tokens = _bounded_nonnegative_integer(
        usage.get("completion_tokens", usage.get("output_tokens"))
    )
    total_tokens = _bounded_nonnegative_integer(usage.get("total_tokens"))
    cost = _bounded_nonnegative_cost(
        usage.get("cost", usage.get("provider_cost_usd"))
    )
    return input_tokens, output_tokens, total_tokens, cost


def _response_usage(
    payload: bytes,
) -> tuple[int | None, int | None, int | None, int | float | None]:
    try:
        decoded = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        decoded = None
    if decoded is not None:
        return _decoded_usage(decoded)

    # OpenRouter puts usage in the final JSON SSE event for streaming calls.
    # Parse only top-level ``data:`` JSON objects and retain no response text.
    latest = (None, None, None, None)
    for line in payload.splitlines():
        if not line.startswith(b"data:"):
            continue
        event = line[len(b"data:") :].lstrip(b" ")
        if not event or event == b"[DONE]":
            continue
        try:
            decoded_event = json.loads(event)
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
            continue
        candidate = _decoded_usage(decoded_event)
        if any(value is not None for value in candidate):
            latest = candidate
    return latest


def _is_empty_model_response(payload: bytes) -> bool:
    """Whether a completed chat response has neither content nor tool calls."""

    try:
        decoded = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        decoded = None
    if decoded is None:
        saw_choice = False
        for line in payload.splitlines():
            if not line.startswith(b"data:"):
                continue
            event = line[len(b"data:") :].lstrip(b" ")
            if not event or event == b"[DONE]":
                continue
            try:
                decoded_event = json.loads(event)
            except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
                return False
            if not isinstance(decoded_event, dict):
                return False
            choices = decoded_event.get("choices")
            if not isinstance(choices, list):
                return False
            for choice in choices:
                if not isinstance(choice, dict):
                    return False
                message = choice.get("delta", choice.get("message"))
                if not isinstance(message, dict):
                    return False
                saw_choice = True
                content = message.get("content")
                if isinstance(content, str) and content.strip():
                    return False
                tool_calls = message.get("tool_calls")
                if isinstance(tool_calls, list) and tool_calls:
                    return False
        return saw_choice
    if not isinstance(decoded, dict):
        return False
    choices = decoded.get("choices")
    if not isinstance(choices, list) or not choices:
        return False
    for choice in choices:
        if not isinstance(choice, dict):
            return False
        message = choice.get("message")
        if not isinstance(message, dict):
            return False
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return False
        tool_calls = message.get("tool_calls")
        if isinstance(tool_calls, list) and tool_calls:
            return False
    return True


def _empty_response_recovery_payload(payload: dict) -> dict:
    """Use a bounded reasoning budget for one otherwise lost continuation."""

    recovered = dict(payload)
    token_key = (
        "max_completion_tokens"
        if "max_completion_tokens" in recovered
        else "max_tokens"
    )
    current = recovered.get(token_key)
    if type(current) is int and current > 0:
        recovered[token_key] = min(current, _EMPTY_RESPONSE_RECOVERY_MAX_TOKENS)
    else:
        recovered[token_key] = _EMPTY_RESPONSE_RECOVERY_MAX_TOKENS
    reasoning = recovered.get("reasoning")
    recovered_reasoning = dict(reasoning) if isinstance(reasoning, dict) else {}
    recovered_reasoning.pop("max_tokens", None)
    recovered_reasoning["effort"] = "low"
    recovered["reasoning"] = recovered_reasoning
    return recovered


def _provider_request_id(headers, *, forbidden: str) -> str | None:
    for name in (
        "X-Generation-Id",
        "X-Request-Id",
        "X-OpenAI-Request-Id",
        "X-OpenRouter-Request-Id",
    ):
        value = headers.get(name)
        if (
            isinstance(value, str)
            and _PROVIDER_REQUEST_ID.fullmatch(value) is not None
            and forbidden not in value
        ):
            return value
    return None


class _DuplicateJSONKey(ValueError):
    pass


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    output: dict[str, object] = {}
    for key, value in pairs:
        if key in output:
            raise _DuplicateJSONKey(key)
        output[key] = value
    return output


class _ModelProxyServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, policy: _ProxyPolicy) -> None:
        self.policy = policy
        self.audit_lock = threading.Lock()
        self.handler_condition = threading.Condition()
        self.active_normal_handlers = 0
        self.normal_handler_count = 0
        self.audit_append_failures = 0
        self.audit_record_count = 0
        self.terminal_handler_count = 0
        self.finalizing = False
        self.finalize_failure: ModelProxyError | None = None
        self.audit_seal: dict[str, object] | None = None
        self.finalize_started = threading.Event()
        super().__init__(address, _ModelProxyHandler)

    def begin_normal_handler(self) -> bool:
        with self.handler_condition:
            if self.finalizing or self.audit_seal is not None:
                return False
            self.active_normal_handlers += 1
            self.normal_handler_count += 1
            return True

    def finish_normal_handler(self, *, terminal_audit_written: bool) -> None:
        with self.handler_condition:
            self.active_normal_handlers -= 1
            if self.active_normal_handlers < 0:
                raise ModelProxyError("proxy handler accounting underflow")
            if terminal_audit_written:
                self.terminal_handler_count += 1
            self.handler_condition.notify_all()

    def append_audit(self, record: Mapping[str, object]) -> None:
        try:
            _append_audit(
                self.policy.audit_file,
                record,
                lock=self.audit_lock,
            )
        except BaseException:
            with self.handler_condition:
                self.audit_append_failures += 1
                self.handler_condition.notify_all()
            raise
        with self.handler_condition:
            self.audit_record_count += 1

    def finalize_audit(self) -> dict[str, object]:
        with self.handler_condition:
            if self.audit_seal is not None:
                return dict(self.audit_seal)
            if self.finalize_failure is not None:
                raise self.finalize_failure
            if self.finalizing:
                while self.audit_seal is None and self.finalize_failure is None:
                    self.handler_condition.wait()
                if self.finalize_failure is not None:
                    raise self.finalize_failure
                return dict(self.audit_seal or {})
            self.finalizing = True
            self.finalize_started.set()
            while self.active_normal_handlers:
                self.handler_condition.wait()
            if self.audit_append_failures:
                failure = _AuditAppendFailed("one or more audit appends failed")
                self.finalize_failure = failure
                self.handler_condition.notify_all()
                raise failure
            if self.terminal_handler_count != self.normal_handler_count:
                failure = _AuditStreamIncomplete(
                    "one or more normal handlers lack a terminal audit record"
                )
                self.finalize_failure = failure
                self.handler_condition.notify_all()
                raise failure
            record_count = self.audit_record_count
        try:
            with self.audit_lock:
                payload = _sealed_audit_bytes(self.policy.audit_file)
            seal: dict[str, object] = {
                "schema_version": 1,
                "record_count": record_count,
                "audit_sha256": hashlib.sha256(payload).hexdigest(),
            }
        except ModelProxyError as exc:
            with self.handler_condition:
                self.finalize_failure = exc
                self.handler_condition.notify_all()
            raise
        with self.handler_condition:
            self.audit_seal = seal
            self.handler_condition.notify_all()
        return dict(seal)


class _ModelProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "qea-model-proxy"
    sys_version = ""

    def log_message(self, format, *args):
        return

    def _retry_monotonic(self) -> float:
        return time.monotonic()

    def _reject(self, status: int, code: str) -> None:
        payload = json.dumps(
            {"error": {"code": code, "type": "proxy_policy_error"}},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(payload)
        self.close_connection = True

    def _finalize(self) -> None:
        try:
            client_is_loopback = ipaddress.ip_address(
                self.client_address[0]
            ).is_loopback
        except ValueError:
            client_is_loopback = False
        if not client_is_loopback:
            self._reject(403, "finalize_loopback_only")
            return
        if self.command != "POST":
            self._reject(405, "method_not_allowed")
            return
        if self.headers.get("Transfer-Encoding") or self.headers.get(
            "Content-Length", "0"
        ) != "0":
            self._reject(400, "finalize_body_forbidden")
            return
        try:
            seal = self.server.finalize_audit()
        except _AuditAppendFailed:
            self._reject(409, "audit_append_failed")
            return
        except _AuditStreamIncomplete:
            self._reject(409, "audit_stream_incomplete")
            return
        except ModelProxyError:
            self._reject(409, "audit_finalize_failed")
            return
        payload = json.dumps(
            seal, sort_keys=True, separators=(",", ":")
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(payload)
        self.close_connection = True

    def _route(self, raw_target: str, policy: _ProxyPolicy) -> str | None:
        parsed: SplitResult = urlsplit(raw_target)
        if parsed.scheme or parsed.netloc or parsed.fragment:
            self._reject(400, "absolute_target_forbidden")
            return None
        if _unsafe_path(parsed.path):
            self._reject(400, "unsafe_path")
            return None
        if not (
            parsed.path == policy.prefix
            or parsed.path.startswith(policy.prefix + "/")
        ):
            self._reject(404, "path_not_allowed")
            return None
        suffix = parsed.path[len(policy.prefix) :]
        target = policy.upstream.base_path + suffix
        if not target:
            target = "/"
        if parsed.query:
            target += "?" + parsed.query
        return target

    def _read_body(self, policy: _ProxyPolicy) -> bytes | None:
        if self.headers.get("Transfer-Encoding"):
            self._reject(400, "transfer_encoding_forbidden")
            return None
        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
        except ValueError:
            self._reject(400, "invalid_content_length")
            return None
        if length < 0:
            self._reject(400, "invalid_content_length")
            return None
        if length > policy.max_request_bytes:
            self._reject(413, "request_limit")
            return None
        body = self.rfile.read(length)
        if len(body) != length:
            self._reject(400, "incomplete_request")
            return None
        return body

    def _open_upstream(self, policy: _ProxyPolicy):
        connection_class = (
            http.client.HTTPSConnection
            if policy.upstream.scheme == "https"
            else http.client.HTTPConnection
        )
        return connection_class(
            policy.upstream.hostname,
            policy.upstream.port,
            timeout=policy.connect_timeout_seconds,
        )

    def _connect_upstream(self, policy: _ProxyPolicy):
        """Retry only failures proven to precede all HTTP request bytes."""

        for attempt_number in range(1, policy.pre_accept_connect_attempts + 1):
            connection = None
            try:
                connection = self._open_upstream(policy)
                connection.connect()
                return connection
            except (OSError, TimeoutError, http.client.HTTPException):
                if connection is not None:
                    try:
                        connection.close()
                    except (OSError, http.client.HTTPException):
                        pass
                if attempt_number >= policy.pre_accept_connect_attempts:
                    raise
                time.sleep(
                    _PRE_ACCEPT_CONNECT_BACKOFF_SECONDS * attempt_number
                )
        raise AssertionError("bounded pre-accept connect loop did not terminate")

    def _request_identity(self, target: str, body: bytes) -> str:
        digest = hashlib.sha256()
        digest.update(self.command.encode("ascii"))
        digest.update(b"\x00")
        digest.update(target.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(body)
        return digest.hexdigest()

    def _audit(
        self,
        *,
        request_identity_sha256: str,
        retry_index: int = 0,
        model: str | None,
        started_at: str,
        started_monotonic: float,
        request_state: str,
        upstream_status_code: int | None = None,
        provider_request_id: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_tokens: int | None = None,
        provider_cost_usd: int | float | None = None,
        failure_class: str | None = None,
        terminal_for_handler: bool = True,
        audit_schema_version: int | None = None,
    ) -> None:
        policy: _ProxyPolicy = self.server.policy
        elapsed = max(0.0, time.monotonic() - started_monotonic)
        if audit_schema_version is None:
            audit_schema_version = 2
        if audit_schema_version not in {1, 2}:
            raise ModelProxyError("proxy audit schema version is invalid")
        record = {
                "schema_version": audit_schema_version,
                "request_identity_sha256": (
                    model_proxy_wire_request_identity(
                        request_identity_sha256, retry_index
                    )
                    if audit_schema_version == 2
                    else request_identity_sha256
                ),
                "model": model,
                "started_at": started_at,
                "finished_at": _utc_timestamp(),
                "latency_ms": round(elapsed * 1000, 3),
                "request_state": request_state,
                "upstream_status_code": upstream_status_code,
                "provider_request_id": provider_request_id,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "provider_cost_usd": provider_cost_usd,
                "failure_class": failure_class,
            }
        if audit_schema_version == 2:
            record.update(
                {
                    "logical_request_identity_sha256": request_identity_sha256,
                    "retry_index": retry_index,
                }
            )
        self.server.append_audit(record)
        if terminal_for_handler:
            self._terminal_audit_written = True

    def _read_upstream_attempt(
        self,
        *,
        policy: _ProxyPolicy,
        target: str,
        outbound_body: bytes,
        headers: Mapping[str, str],
        logical_request_identity_sha256: str,
        retry_index: int,
        started_at: str,
        started_monotonic: float,
        retry_deadline: float | None = None,
    ) -> _BufferedUpstreamResponse | None:
        """Read one independent upstream wire response before exposing any bytes."""

        connection = None
        request_transmission_started = False
        response_status: int | None = None
        provider_request_id: str | None = None
        audit_written = False
        spool = tempfile.SpooledTemporaryFile(
            max_size=min(policy.max_response_bytes, 1024 * 1024), mode="w+b"
        )
        try:
            attempt_policy = policy
            if retry_deadline is not None:
                remaining = retry_deadline - self._retry_monotonic()
                if remaining <= 0:
                    self._terminal_audit_written = True
                    self._reject(429, "rate_limit_retry_exhausted")
                    return None
                attempt_policy = replace(
                    policy,
                    connect_timeout_seconds=min(
                        policy.connect_timeout_seconds, remaining
                    ),
                )
            connection = self._connect_upstream(attempt_policy)
            request_transmission_started = True
            connection.request(
                self.command,
                target,
                body=outbound_body,
                headers=headers,
            )
            if connection.sock is not None:
                read_timeout = attempt_policy.read_timeout_seconds
                connection.sock.settimeout(read_timeout)
            response = connection.getresponse()
            response_status = response.status
            provider_request_id = _provider_request_id(
                response.headers, forbidden=policy.token
            )
            token_bytes = policy.token.encode("ascii")
            if any(
                token_bytes in name.encode("utf-8", errors="replace")
                or token_bytes in value.encode("utf-8", errors="replace")
                for name, value in response.headers.items()
            ):
                self._audit(
                    request_identity_sha256=logical_request_identity_sha256,
                    retry_index=retry_index,
                    model=policy.allowed_model,
                    started_at=started_at,
                    started_monotonic=started_monotonic,
                    request_state="quarantined",
                    upstream_status_code=response.status,
                    provider_request_id=provider_request_id,
                    failure_class="unsafe_upstream_response",
                )
                audit_written = True
                self._reject(502, "credential_echo")
                return None
            declared = None
            raw_length = response.getheader("Content-Length")
            if raw_length is not None:
                try:
                    declared = int(raw_length)
                except ValueError:
                    self._audit(
                        request_identity_sha256=logical_request_identity_sha256,
                        retry_index=retry_index,
                        model=policy.allowed_model,
                        started_at=started_at,
                        started_monotonic=started_monotonic,
                        request_state="quarantined",
                        upstream_status_code=response.status,
                        provider_request_id=provider_request_id,
                        failure_class="invalid_upstream_response",
                    )
                    audit_written = True
                    self._reject(502, "invalid_upstream_length")
                    return None
                if declared < 0 or declared > policy.max_response_bytes:
                    self._audit(
                        request_identity_sha256=logical_request_identity_sha256,
                        retry_index=retry_index,
                        model=policy.allowed_model,
                        started_at=started_at,
                        started_monotonic=started_monotonic,
                        request_state="quarantined",
                        upstream_status_code=response.status,
                        provider_request_id=provider_request_id,
                        failure_class="upstream_response_limit",
                    )
                    audit_written = True
                    self._reject(502, "response_limit")
                    return None
            total = 0
            overlap = b""
            while True:
                chunk = response.read(_BUFFER_SIZE)
                if not chunk:
                    break
                combined = overlap + chunk
                if token_bytes in combined:
                    self._audit(
                        request_identity_sha256=logical_request_identity_sha256,
                        retry_index=retry_index,
                        model=policy.allowed_model,
                        started_at=started_at,
                        started_monotonic=started_monotonic,
                        request_state="quarantined",
                        upstream_status_code=response.status,
                        provider_request_id=provider_request_id,
                        failure_class="unsafe_upstream_response",
                    )
                    audit_written = True
                    self._reject(502, "credential_echo")
                    return None
                overlap = (
                    combined[-(len(token_bytes) - 1) :]
                    if len(token_bytes) > 1
                    else b""
                )
                total += len(chunk)
                if total > policy.max_response_bytes:
                    self._audit(
                        request_identity_sha256=logical_request_identity_sha256,
                        retry_index=retry_index,
                        model=policy.allowed_model,
                        started_at=started_at,
                        started_monotonic=started_monotonic,
                        request_state="quarantined",
                        upstream_status_code=response.status,
                        provider_request_id=provider_request_id,
                        failure_class="upstream_response_limit",
                    )
                    audit_written = True
                    self._reject(502, "response_limit")
                    return None
                spool.write(chunk)
            if declared is not None and total != declared:
                self._audit(
                    request_identity_sha256=logical_request_identity_sha256,
                    retry_index=retry_index,
                    model=policy.allowed_model,
                    started_at=started_at,
                    started_monotonic=started_monotonic,
                    request_state="quarantined",
                    upstream_status_code=response.status,
                    provider_request_id=provider_request_id,
                    failure_class="post_accept_transport",
                )
                audit_written = True
                self._reject(502, "incomplete_upstream_response")
                return None
            spool.seek(0)
            response_payload = spool.read()
            usage = _response_usage(response_payload)
            return _BufferedUpstreamResponse(
                status=response.status,
                headers=_filtered_response_headers(response.headers),
                body=response_payload,
                provider_request_id=provider_request_id,
                input_tokens=usage[0],
                output_tokens=usage[1],
                total_tokens=usage[2],
                provider_cost_usd=usage[3],
                retry_after_values=tuple(response.headers.get_all("Retry-After", [])),
            )
        except (OSError, TimeoutError, http.client.HTTPException) as exc:
            deadline_expired = isinstance(
                exc, _RateLimitRetryDeadlineExpired
            ) or (
                retry_deadline is not None
                and self._retry_monotonic() >= retry_deadline
            )
            if not audit_written:
                self._audit(
                    request_identity_sha256=logical_request_identity_sha256,
                    retry_index=retry_index,
                    model=policy.allowed_model,
                    started_at=started_at,
                    started_monotonic=started_monotonic,
                    request_state=(
                        "quarantined"
                        if request_transmission_started
                        else "not_accepted"
                    ),
                    upstream_status_code=response_status,
                    provider_request_id=provider_request_id,
                    failure_class=(
                        "post_accept_transport"
                        if request_transmission_started
                        else "pre_accept_transport"
                    ),
                )
            if not self.wfile.closed:
                try:
                    self._reject(
                        502,
                        (
                            "rate_limit_retry_deadline_expired"
                            if deadline_expired
                            else "upstream_failure"
                        ),
                    )
                except OSError:
                    pass
            return None
        finally:
            spool.close()
            if connection is not None:
                connection.close()

    def _rate_limit_delay(
        self,
        *,
        response: _BufferedUpstreamResponse,
        retry_index: int,
        policy: _ProxyPolicy,
    ) -> float:
        if len(response.retry_after_values) > 1:
            raise ModelProxyError("multiple Retry-After headers are ambiguous")
        if response.retry_after_values:
            return _retry_after_seconds(
                response.retry_after_values[0], now=datetime.now(timezone.utc)
            )
        return policy.rate_limit_backoff_seconds * (2**retry_index)

    def _deliver_buffered_response(
        self,
        *,
        response: _BufferedUpstreamResponse,
        logical_request_identity_sha256: str,
        retry_index: int,
        policy: _ProxyPolicy,
        started_at: str,
        started_monotonic: float,
        rate_limit_retry_group: bool,
    ) -> None:
        delivery_started = False
        audit_written = False
        try:
            delivery_started = True
            self.send_response(response.status)
            for name, value in response.headers:
                self.send_header(name, value)
            self.send_header("Content-Length", str(len(response.body)))
            self.end_headers()
            self.wfile.write(response.body)
            self.wfile.flush()
            self._audit(
                request_identity_sha256=logical_request_identity_sha256,
                retry_index=retry_index,
                model=policy.allowed_model,
                started_at=started_at,
                started_monotonic=started_monotonic,
                request_state="completed",
                upstream_status_code=response.status,
                provider_request_id=response.provider_request_id,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                total_tokens=response.total_tokens,
                provider_cost_usd=response.provider_cost_usd,
                failure_class=(
                    "provider_http_error" if response.status >= 400 else None
                ),
                audit_schema_version=2,
            )
            audit_written = True
        except OSError:
            if not audit_written:
                self._audit(
                    request_identity_sha256=logical_request_identity_sha256,
                    retry_index=retry_index,
                    model=policy.allowed_model,
                    started_at=started_at,
                    started_monotonic=started_monotonic,
                    request_state="quarantined",
                    upstream_status_code=response.status,
                    provider_request_id=response.provider_request_id,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    total_tokens=response.total_tokens,
                    provider_cost_usd=response.provider_cost_usd,
                    failure_class=(
                        "downstream_delivery"
                        if delivery_started
                        else "post_accept_transport"
                    ),
                    audit_schema_version=2,
                )

    def _proxy_counted(self) -> None:
        policy: _ProxyPolicy = self.server.policy
        if self.command not in _ALLOWED_METHODS:
            self._reject(405, "method_not_allowed")
            return
        if self.headers.get("Upgrade"):
            self._reject(400, "upgrade_forbidden")
            return
        target = self._route(self.path, policy)
        if target is None:
            return
        body = self._read_body(policy)
        if body is None:
            return
        request_identity = self._request_identity(target, body)
        started_at = _utc_timestamp()
        started_monotonic = time.monotonic()
        try:
            request_payload = json.loads(body, object_pairs_hook=_unique_json_object)
        except _DuplicateJSONKey:
            self._audit(
                request_identity_sha256=request_identity,
                model=None,
                started_at=started_at,
                started_monotonic=started_monotonic,
                request_state="not_accepted",
                failure_class="policy_rejection",
            )
            self._reject(400, "duplicate_json_key")
            return
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
            self._audit(
                request_identity_sha256=request_identity,
                model=None,
                started_at=started_at,
                started_monotonic=started_monotonic,
                request_state="not_accepted",
                failure_class="policy_rejection",
            )
            self._reject(400, "invalid_json")
            return
        if not isinstance(request_payload, dict):
            self._audit(
                request_identity_sha256=request_identity,
                model=None,
                started_at=started_at,
                started_monotonic=started_monotonic,
                request_state="not_accepted",
                failure_class="policy_rejection",
            )
            self._reject(400, "invalid_json")
            return
        requested_model = request_payload.get("model")
        if requested_model is None:
            self._audit(
                request_identity_sha256=request_identity,
                model=None,
                started_at=started_at,
                started_monotonic=started_monotonic,
                request_state="not_accepted",
                failure_class="policy_rejection",
            )
            self._reject(400, "model_required")
            return
        if requested_model != policy.allowed_model:
            self._audit(
                request_identity_sha256=request_identity,
                model=None,
                started_at=started_at,
                started_monotonic=started_monotonic,
                request_state="not_accepted",
                failure_class="policy_rejection",
            )
            self._reject(400, "model_not_allowed")
            return
        outbound_body = body
        if policy.required_provider is not None:
            if "provider" in request_payload:
                self._audit(
                    request_identity_sha256=request_identity,
                    model=None,
                    started_at=started_at,
                    started_monotonic=started_monotonic,
                    request_state="not_accepted",
                    failure_class="policy_rejection",
                )
                self._reject(400, "provider_forbidden")
                return
            providers = [
                policy.required_provider,
                *policy.fallback_providers,
            ]
            if policy.fallback_providers:
                request_payload["provider"] = {
                    "order": providers,
                    "only": providers,
                    "allow_fallbacks": True,
                    "require_parameters": True,
                }
            else:
                request_payload["provider"] = {
                    "only": providers,
                    "allow_fallbacks": False,
                }
            outbound_body = json.dumps(
                request_payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            request_identity = self._request_identity(target, outbound_body)
            if len(outbound_body) > policy.max_request_bytes:
                self._audit(
                    request_identity_sha256=request_identity,
                    model=None,
                    started_at=started_at,
                    started_monotonic=started_monotonic,
                    request_state="not_accepted",
                    failure_class="policy_rejection",
                )
                self._reject(413, "request_limit")
                return
        if request_identity in policy.denied_request_identities_sha256:
            self._audit(
                request_identity_sha256=request_identity,
                model=policy.allowed_model,
                started_at=started_at,
                started_monotonic=started_monotonic,
                request_state="quarantined",
                failure_class="replay_denied",
            )
            self._reject(409, "request_replay_forbidden")
            return
        retry_deadline: float | None = None
        empty_response_seen = False
        for retry_index in range(policy.rate_limit_max_attempts):
            attempt_body = outbound_body
            if retry_index > 0 and policy.fallback_providers:
                remaining = list(policy.fallback_providers[retry_index - 1 :])
                if remaining:
                    attempt_payload = (
                        _empty_response_recovery_payload(request_payload)
                        if empty_response_seen
                        else dict(request_payload)
                    )
                    attempt_payload["provider"] = {
                        "order": remaining,
                        "only": remaining,
                        "allow_fallbacks": len(remaining) > 1,
                        "require_parameters": True,
                    }
                    attempt_body = json.dumps(
                        attempt_payload,
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=False,
                    ).encode("utf-8")
            headers = _filtered_request_headers(
                self.headers, policy, len(attempt_body)
            )
            response = self._read_upstream_attempt(
                policy=policy,
                target=target,
                outbound_body=attempt_body,
                headers=headers,
                logical_request_identity_sha256=request_identity,
                retry_index=retry_index,
                started_at=started_at,
                started_monotonic=started_monotonic,
                retry_deadline=retry_deadline,
            )
            if response is None:
                return
            empty_response = (
                response.status == 200
                and _is_empty_model_response(response.body)
            )
            if empty_response:
                can_retry_empty = (
                    not empty_response_seen
                    and bool(policy.fallback_providers)
                    and retry_index + 1 < policy.rate_limit_max_attempts
                    and retry_index < len(policy.fallback_providers)
                )
                self._audit(
                    request_identity_sha256=request_identity,
                    retry_index=retry_index,
                    model=policy.allowed_model,
                    started_at=started_at,
                    started_monotonic=started_monotonic,
                    request_state="completed",
                    upstream_status_code=200,
                    provider_request_id=response.provider_request_id,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    total_tokens=response.total_tokens,
                    provider_cost_usd=response.provider_cost_usd,
                    failure_class="empty_model_response",
                    terminal_for_handler=not can_retry_empty,
                    audit_schema_version=2,
                )
                if can_retry_empty:
                    empty_response_seen = True
                    continue
                self._reject(502, "empty_model_response_after_fallback")
                return
            if response.status != 429:
                self._deliver_buffered_response(
                    response=response,
                    logical_request_identity_sha256=request_identity,
                    retry_index=retry_index,
                    policy=policy,
                    started_at=started_at,
                    started_monotonic=started_monotonic,
                    rate_limit_retry_group=retry_index > 0,
                )
                return
            if any(
                value is not None
                for value in (
                    response.provider_request_id,
                    response.input_tokens,
                    response.output_tokens,
                    response.total_tokens,
                    response.provider_cost_usd,
                )
            ):
                self._audit(
                    request_identity_sha256=request_identity,
                    retry_index=retry_index,
                    model=policy.allowed_model,
                    started_at=started_at,
                    started_monotonic=started_monotonic,
                    request_state="quarantined",
                    upstream_status_code=429,
                    provider_request_id=response.provider_request_id,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    total_tokens=response.total_tokens,
                    provider_cost_usd=response.provider_cost_usd,
                    failure_class="invalid_upstream_response",
                    audit_schema_version=2,
                )
                self._reject(502, "ambiguous_rate_limit_response")
                return
            if retry_deadline is None:
                retry_deadline = (
                    self._retry_monotonic()
                    + policy.rate_limit_retry_budget_seconds
                )
            last_attempt = retry_index + 1 >= policy.rate_limit_max_attempts
            try:
                delay = self._rate_limit_delay(
                    response=response,
                    retry_index=retry_index,
                    policy=policy,
                )
            except ModelProxyError:
                last_attempt = True
                delay = 0.0
            remaining_before = retry_deadline - self._retry_monotonic()
            if delay > remaining_before:
                last_attempt = True
            self._audit(
                request_identity_sha256=request_identity,
                retry_index=retry_index,
                model=policy.allowed_model,
                started_at=started_at,
                started_monotonic=started_monotonic,
                request_state="not_accepted",
                upstream_status_code=429,
                failure_class="rate_limited",
                terminal_for_handler=last_attempt,
                audit_schema_version=2,
            )
            if last_attempt:
                self._reject(429, "rate_limit_retry_exhausted")
                return
            if remaining_before <= 0:
                self._terminal_audit_written = True
                self._reject(429, "rate_limit_retry_exhausted")
                return
            time.sleep(delay)
            if retry_deadline - self._retry_monotonic() <= 0:
                self._terminal_audit_written = True
                self._reject(429, "rate_limit_retry_exhausted")
                return
        raise AssertionError("bounded rate-limit retry loop did not terminate")
    def _proxy(self) -> None:
        if self.path == _FINALIZE_PATH:
            self._finalize()
            return
        if not self.server.begin_normal_handler():
            self._reject(409, "proxy_finalized")
            return
        self._terminal_audit_written = False
        try:
            self._proxy_counted()
        finally:
            self.server.finish_normal_handler(
                terminal_audit_written=self._terminal_audit_written
            )

    do_GET = _proxy
    do_POST = _proxy

    def do_CONNECT(self) -> None:
        if not self.server.begin_normal_handler():
            self._reject(409, "proxy_finalized")
            return
        self._terminal_audit_written = False
        try:
            self._reject(405, "method_not_allowed")
        finally:
            self.server.finish_normal_handler(
                terminal_audit_written=self._terminal_audit_written
            )

    do_DELETE = do_CONNECT
    do_HEAD = do_CONNECT
    do_OPTIONS = do_CONNECT
    do_PATCH = do_CONNECT
    do_PUT = do_CONNECT
    do_TRACE = do_CONNECT


def create_proxy_server(config: ModelProxyConfig) -> ThreadingHTTPServer:
    """Create but do not start a no-logging fixed-upstream proxy server."""

    audit_file = Path(config.audit_file)
    _ensure_private_audit(audit_file)
    policy = _ProxyPolicy(
        upstream=_parse_upstream(config.upstream_base_url),
        prefix=config.allowed_path_prefix,
        token=_read_token(Path(config.token_file)),
        allowed_model=config.allowed_model,
        required_provider=config.required_provider,
        fallback_providers=config.fallback_providers,
        audit_file=audit_file,
        denied_request_identities_sha256=frozenset(
            config.denied_request_identities_sha256
        ),
        max_request_bytes=config.max_request_bytes,
        max_response_bytes=config.max_response_bytes,
        connect_timeout_seconds=float(config.connect_timeout_seconds),
        read_timeout_seconds=float(config.read_timeout_seconds),
        pre_accept_connect_attempts=config.pre_accept_connect_attempts,
        rate_limit_max_attempts=config.rate_limit_max_attempts,
        rate_limit_retry_budget_seconds=config.rate_limit_retry_budget_seconds,
        rate_limit_backoff_seconds=config.rate_limit_backoff_seconds,
    )
    return _ModelProxyServer((config.listen_host, config.listen_port), policy)
