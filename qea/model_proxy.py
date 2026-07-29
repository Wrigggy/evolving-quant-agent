"""A fixed-upstream model proxy that injects credentials outside workers."""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import stat
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from typing import Callable, Mapping
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
_BUFFER_SIZE = 64 * 1024
_ALLOWED_METHODS = frozenset({"GET", "POST"})


class ModelProxyError(RuntimeError):
    """Proxy configuration, routing, token storage, or exposure is unsafe."""


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
    if base_path and not base_path.startswith("/"):
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


def _read_token(path: Path) -> str:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise ModelProxyError("token file is unavailable") from exc
    if path.is_symlink() or not stat.S_ISREG(metadata.st_mode):
        raise ModelProxyError("token file must be a regular non-symlink file")
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise ModelProxyError("token file must have exact mode 600")
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
        return payload.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ModelProxyError("token file must contain one printable credential") from exc


@dataclass(frozen=True)
class ModelProxyConfig:
    """Validated listener, upstream, token-file, and size/time limits."""

    listen_host: str
    listen_port: int
    upstream_base_url: str
    allowed_path_prefix: str
    token_file: Path | str
    max_request_bytes: int = 8 * 1024 * 1024
    max_response_bytes: int = 64 * 1024 * 1024
    connect_timeout_seconds: float = 10.0
    read_timeout_seconds: float = 300.0

    def __post_init__(self) -> None:
        if self.listen_host not in {"127.0.0.1", "0.0.0.0"}:
            raise ModelProxyError("proxy listener must use an explicit IPv4 bind address")
        if type(self.listen_port) is not int or not 0 <= self.listen_port <= 65535:
            raise ModelProxyError("proxy listener port is invalid")
        _parse_upstream(self.upstream_base_url)
        object.__setattr__(
            self, "allowed_path_prefix", _validate_prefix(self.allowed_path_prefix)
        )
        token_path = Path(self.token_file).expanduser()
        _read_token(token_path)
        object.__setattr__(self, "token_file", token_path)
        for name in ("max_request_bytes", "max_response_bytes"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ModelProxyError(f"{name} must be a positive integer")
        for name in ("connect_timeout_seconds", "read_timeout_seconds"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                raise ModelProxyError(f"{name} must be positive")


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

    def config_payload(self) -> dict[str, object]:
        """Return the public config uploaded before the token appears."""

        return {
            "listen_host": "0.0.0.0",
            "listen_port": self.listen_port,
            "upstream_base_url": self.upstream_base_url,
            "allowed_path_prefix": self.allowed_path_prefix,
            "max_request_bytes": 8 * 1024 * 1024,
            "max_response_bytes": 64 * 1024 * 1024,
            "connect_timeout_seconds": 10.0,
            "read_timeout_seconds": 300.0,
        }

    def public_payload(self) -> dict[str, object]:
        return {
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
                "environment": dict(self.spec.environment),
                "writable_tmpfs_mb": dict(self.spec.writable_tmpfs_mb),
                "spec_sha256": self.spec.spec_sha256,
            },
            "token_path": self.token_path,
            "start_argv": list(self.start_argv),
            "upstream_base_url": self.upstream_base_url,
            "allowed_path_prefix": self.allowed_path_prefix,
            "listen_port": self.listen_port,
        }


def build_model_proxy_sandbox_plan(
    *,
    run_id: str,
    attempt_id: str,
    image_ref: str,
    upstream_base_url: str,
    allowed_path_prefix: str,
    listen_port: int,
    cpu_count: int,
    memory_mb: int,
    pids_limit: int,
    timeout_seconds: int,
) -> ModelProxySandboxPlan:
    """Build a proxy plan that has no API-key argument, env value, or label."""

    _parse_upstream(upstream_base_url)
    prefix = _validate_prefix(allowed_path_prefix)
    if type(listen_port) is not int or not 1 <= listen_port <= 65535:
        raise ModelProxyError("proxy plan listener port is invalid")
    spec = SandboxSpec(
        role="proxy",
        run_id=run_id,
        attempt_id=attempt_id,
        task_id="model-proxy",
        image_ref=image_ref,
        cpu_count=cpu_count,
        memory_mb=memory_mb,
        pids_limit=pids_limit,
        timeout_seconds=timeout_seconds,
        network_policy="proxy-outbound",
        environment={},
        writable_tmpfs_mb={
            "/run/qea-secrets": 1,
            "/tmp": 64,
        },
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
    max_request_bytes: int
    max_response_bytes: int
    connect_timeout_seconds: float
    read_timeout_seconds: float


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


class _ModelProxyServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, policy: _ProxyPolicy) -> None:
        self.policy = policy
        super().__init__(address, _ModelProxyHandler)


class _ModelProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "qea-model-proxy"
    sys_version = ""

    def log_message(self, format, *args):
        return

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

    def _proxy(self) -> None:
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
        headers = _filtered_request_headers(self.headers, policy, len(body))
        connection = self._open_upstream(policy)
        spool = tempfile.SpooledTemporaryFile(
            max_size=min(policy.max_response_bytes, 1024 * 1024), mode="w+b"
        )
        response = None
        total = 0
        try:
            connection.request(self.command, target, body=body, headers=headers)
            if connection.sock is not None:
                connection.sock.settimeout(policy.read_timeout_seconds)
            response = connection.getresponse()
            token_bytes = policy.token.encode("ascii")
            if any(
                token_bytes in name.encode("utf-8", errors="replace")
                or token_bytes in value.encode("utf-8", errors="replace")
                for name, value in response.headers.items()
            ):
                self._reject(502, "credential_echo")
                return
            raw_length = response.getheader("Content-Length")
            if raw_length is not None:
                try:
                    declared = int(raw_length)
                except ValueError:
                    self._reject(502, "invalid_upstream_length")
                    return
                if declared < 0 or declared > policy.max_response_bytes:
                    self._reject(502, "response_limit")
                    return
            overlap = b""
            while True:
                chunk = response.read(_BUFFER_SIZE)
                if not chunk:
                    break
                combined = overlap + chunk
                if token_bytes in combined:
                    self._reject(502, "credential_echo")
                    return
                overlap = (
                    combined[-(len(token_bytes) - 1) :]
                    if len(token_bytes) > 1
                    else b""
                )
                total += len(chunk)
                if total > policy.max_response_bytes:
                    self._reject(502, "response_limit")
                    return
                spool.write(chunk)
            spool.seek(0)
            self.send_response(response.status)
            for name, value in _filtered_response_headers(response.headers):
                self.send_header(name, value)
            self.send_header("Content-Length", str(total))
            self.end_headers()
            while True:
                chunk = spool.read(_BUFFER_SIZE)
                if not chunk:
                    break
                self.wfile.write(chunk)
        except (OSError, TimeoutError, http.client.HTTPException):
            if not self.wfile.closed:
                self._reject(502, "upstream_failure")
        finally:
            spool.close()
            connection.close()

    do_GET = _proxy
    do_POST = _proxy

    def do_CONNECT(self) -> None:
        self._reject(405, "method_not_allowed")

    do_DELETE = do_CONNECT
    do_HEAD = do_CONNECT
    do_OPTIONS = do_CONNECT
    do_PATCH = do_CONNECT
    do_PUT = do_CONNECT
    do_TRACE = do_CONNECT


def create_proxy_server(config: ModelProxyConfig) -> ThreadingHTTPServer:
    """Create but do not start a no-logging fixed-upstream proxy server."""

    policy = _ProxyPolicy(
        upstream=_parse_upstream(config.upstream_base_url),
        prefix=config.allowed_path_prefix,
        token=_read_token(Path(config.token_file)),
        max_request_bytes=config.max_request_bytes,
        max_response_bytes=config.max_response_bytes,
        connect_timeout_seconds=float(config.connect_timeout_seconds),
        read_timeout_seconds=float(config.read_timeout_seconds),
    )
    return _ModelProxyServer((config.listen_host, config.listen_port), policy)
