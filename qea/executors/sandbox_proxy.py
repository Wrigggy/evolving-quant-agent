"""Attempt-scoped model-proxy lifecycle and retry quarantine."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator, Literal, Mapping, Sequence

from ..model_proxy import (
    ModelProxyError,
    _read_token_bytes,
    _validate_provider_slug,
    build_model_proxy_sandbox_plan,
    model_proxy_plan_identity,
)
from ..sandbox_backend import (
    SandboxBackend,
    SandboxCommandResult,
    SandboxNetworkHandle,
    ScopedNetworkBackend,
)
from ..sandbox_lifecycle import (
    create_lifecycle,
    mark_cleaned,
    mark_finished,
    mark_started,
)
from ..sandbox_network_lifecycle import (
    create_network_lifecycle,
    mark_network_cleaned,
)
from .sandbox_nexau import SandboxResourceContract


_PRIVATE_CONFIG_PATH = "/run/qea-secrets/proxy-config.json"
_PRIVATE_TOKEN_PATH = "/run/qea-secrets/model-token"
_PRIVATE_AUDIT_PATH = "/run/qea-secrets/proxy-audit.jsonl"
_PROXY_ALIAS = "qea-model-proxy"
_READY_TIMEOUT_SECONDS = 30
_MAX_AUDIT_BYTES = 16 * 1024 * 1024
_MAX_AUDIT_LATENCY_MS = 7 * 24 * 60 * 60 * 1000
_MAX_REQUEST_IDENTITIES = 10_000
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_PROVIDER_REQUEST_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,511}\Z")
_STATUS_MUST_BE_NULL = "must_be_null"
_STATUS_MAY_BE_NULL = "may_be_null_or_http_status"
_STATUS_MUST_BE_PRESENT = "must_be_http_status"
_STATUS_MUST_BE_NON_ERROR = "must_be_100_through_399"
_STATUS_MUST_BE_ERROR = "must_be_400_through_599"
_AUDIT_STATUS_RULES: Mapping[tuple[str, str | None], str] = {
    ("not_accepted", "policy_rejection"): _STATUS_MUST_BE_NULL,
    ("not_accepted", "pre_accept_transport"): _STATUS_MUST_BE_NULL,
    ("completed", None): _STATUS_MUST_BE_NON_ERROR,
    ("completed", "provider_http_error"): _STATUS_MUST_BE_ERROR,
    ("quarantined", "post_accept_transport"): _STATUS_MAY_BE_NULL,
    ("quarantined", "unsafe_upstream_response"): _STATUS_MUST_BE_PRESENT,
    ("quarantined", "invalid_upstream_response"): _STATUS_MUST_BE_PRESENT,
    ("quarantined", "upstream_response_limit"): _STATUS_MUST_BE_PRESENT,
    ("quarantined", "replay_denied"): _STATUS_MUST_BE_NULL,
}
_REQUEST_STATES = frozenset(state for state, _ in _AUDIT_STATUS_RULES)
_FAILURE_CLASSES = frozenset(failure for _, failure in _AUDIT_STATUS_RULES)
_CROSS_ATTEMPT_DENIAL_FAILURES = frozenset(
    {
        "post_accept_transport",
        "unsafe_upstream_response",
        "invalid_upstream_response",
        "upstream_response_limit",
    }
)
_CALLER_ROLES = frozenset({"worker", "evolver"})
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
_READY_CODE = """
import socket
import sys
import time

port = int(sys.argv[1])
deadline = time.monotonic() + float(sys.argv[2])
last_error = None
connected = False
while time.monotonic() < deadline:
    remaining = deadline - time.monotonic()
    try:
        with socket.create_connection(
            ('127.0.0.1', port), timeout=min(2, max(0.1, remaining))
        ):
            connected = True
        break
    except OSError as exc:
        last_error = exc
        time.sleep(min(0.1, max(0, deadline - time.monotonic())))
if not connected:
    raise last_error or TimeoutError('proxy readiness deadline expired')
""".strip()
_FINALIZE_CODE = """
import http.client
import sys

connection = http.client.HTTPConnection(
    '127.0.0.1', int(sys.argv[1]), timeout=float(sys.argv[2])
)
connection.request(
    'POST', '/__qea_private/finalize', body=b'',
    headers={'Content-Length': '0'},
)
response = connection.getresponse()
payload = response.read()
sys.stdout.buffer.write(payload)
connection.close()
raise SystemExit(0 if response.status == 200 else 3)
""".strip()


class SandboxProxyError(RuntimeError):
    """An attempt proxy cannot be opened, audited, or cleaned safely."""


@dataclass(frozen=True)
class SandboxProxyConfig:
    image_ref: str
    resource_contract: SandboxResourceContract
    token_file: Path
    upstream_base_url: str
    allowed_path_prefix: str
    allowed_model: str
    listen_port: int = 8080
    timeout_seconds: int = 120
    expect_request: bool = True
    required_provider: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.resource_contract, SandboxResourceContract):
            raise SandboxProxyError("resource_contract must be a SandboxResourceContract")
        missing = {"/run/qea-secrets", "/tmp"} - set(
            self.resource_contract.writable_tmpfs_mb
        )
        if missing:
            raise SandboxProxyError(
                f"proxy resource contract is missing private tmpfs mounts: {sorted(missing)}"
            )
        if type(self.listen_port) is not int or not 1 <= self.listen_port <= 65535:
            raise SandboxProxyError("listen_port must be an integer in [1, 65535]")
        if type(self.timeout_seconds) is not int or self.timeout_seconds <= 0:
            raise SandboxProxyError("timeout_seconds must be a positive integer")
        if type(self.expect_request) is not bool:
            raise SandboxProxyError("expect_request must be a boolean")
        if self.required_provider is not None:
            try:
                normalized_provider = _validate_provider_slug(
                    self.required_provider
                )
            except ModelProxyError as exc:
                raise SandboxProxyError(str(exc)) from exc
            object.__setattr__(
                self, "required_provider", normalized_provider
            )
        object.__setattr__(self, "token_file", Path(self.token_file).expanduser())


@dataclass(frozen=True)
class SandboxProxySession:
    base_url: str
    network_scope: str
    network_name: str
    network_id: str
    native_id: str
    lifecycle_uri: Path
    audit_uri: Path
    allowed_model: str
    required_provider: str | None
    immutable_image_ref: str
    spec_sha256: str
    public_plan_sha256: str
    public_config_sha256: str
    attempt_identity_sha256: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_detail(value: BaseException, secret: bytes | bytearray) -> str:
    detail = f"{type(value).__name__}: {value}"
    if secret:
        try:
            detail = detail.replace(secret.decode("ascii"), "[REDACTED]")
        except UnicodeDecodeError:
            detail = type(value).__name__
    return " ".join(detail.split())[:2_000]


def _backend_call(
    phase: str,
    operation: Callable[[], object],
    *,
    secret: bytes | bytearray,
):
    try:
        return operation()
    except SandboxProxyError:
        raise
    except Exception as exc:  # noqa: BLE001 - typed provider boundary.
        raise SandboxProxyError(f"{phase}: {_safe_detail(exc, secret)}") from exc


def _private_file_metadata(path: Path) -> None:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise SandboxProxyError(f"private file is unavailable: {path}") from exc
    if path.is_symlink() or not path.is_file():
        raise SandboxProxyError(f"private file must be regular and non-symlink: {path}")
    if hasattr(os, "getuid") and metadata.st_uid != os.getuid():
        raise SandboxProxyError(f"private file must be owned by the current UID: {path}")
    if metadata.st_mode & 0o077:
        raise SandboxProxyError(
            f"private file must have no group or other permission bits: {path}"
        )


def _atomic_private_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = None
    try:
        descriptor = os.open(temporary, flags, 0o600)
        os.fchmod(descriptor, 0o600)
        written = os.write(descriptor, payload)
        if written != len(payload):
            raise SandboxProxyError("private audit write was incomplete")
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
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


def _is_optional_integer(value: object) -> bool:
    return value is None or (type(value) is int and value >= 0)


def _parse_audit_seal(payload: str) -> Mapping[str, object]:
    if not isinstance(payload, str) or len(payload.encode()) > 4096:
        raise SandboxProxyError("proxy audit seal exceeds its bounded contract")
    try:
        seal = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise SandboxProxyError("proxy audit seal is invalid JSON") from exc
    if not isinstance(seal, dict) or set(seal) != {
        "schema_version",
        "record_count",
        "audit_sha256",
    }:
        raise SandboxProxyError("proxy audit seal has an unsafe schema")
    if seal["schema_version"] != 1:
        raise SandboxProxyError("proxy audit seal version is unsupported")
    count = seal["record_count"]
    digest = seal["audit_sha256"]
    if type(count) is not int or not 0 <= count <= _MAX_REQUEST_IDENTITIES:
        raise SandboxProxyError("proxy audit seal record count is invalid")
    if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
        raise SandboxProxyError("proxy audit seal digest is invalid")
    return seal


def _validate_audit_semantics(record: Mapping[str, object]) -> None:
    state = record["request_state"]
    failure = record["failure_class"]
    status = record["upstream_status_code"]
    usage_fields = (
        "provider_request_id",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "provider_cost_usd",
    )
    status_rule = _AUDIT_STATUS_RULES.get((state, failure))
    status_is_http = type(status) is int and 100 <= status <= 599
    status_is_valid = (
        (status_rule == _STATUS_MUST_BE_NULL and status is None)
        or (
            status_rule == _STATUS_MAY_BE_NULL
            and (status is None or status_is_http)
        )
        or (status_rule == _STATUS_MUST_BE_PRESENT and status_is_http)
        or (
            status_rule == _STATUS_MUST_BE_NON_ERROR
            and status_is_http
            and status < 400
        )
        or (
            status_rule == _STATUS_MUST_BE_ERROR
            and status_is_http
            and status >= 400
        )
    )
    if not status_is_valid or (
        state == "not_accepted"
        and any(record[field] is not None for field in usage_fields)
    ):
        raise SandboxProxyError(
            "proxy audit state/failure semantic pair is invalid"
        )


def _parse_audit_timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not 20 <= len(value) <= 64:
        raise SandboxProxyError("proxy audit timestamp is invalid")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise SandboxProxyError("proxy audit timestamp is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise SandboxProxyError("proxy audit timestamp is invalid")
    normalized = parsed.astimezone(timezone.utc)
    if not 2000 <= normalized.year <= 2100:
        raise SandboxProxyError("proxy audit timestamp is outside its bound")
    return normalized


def _parse_audit(
    payload: bytes,
    *,
    secret: bytes | bytearray,
    allowed_model: str,
) -> tuple[Mapping[str, object], ...]:
    if not isinstance(payload, bytes) or len(payload) > _MAX_AUDIT_BYTES:
        raise SandboxProxyError("proxy audit exceeds its bounded transfer contract")
    if secret and payload.find(secret) >= 0:
        raise SandboxProxyError("proxy audit contains forbidden credential bytes")
    records: list[Mapping[str, object]] = []
    for line_number, line in enumerate(payload.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SandboxProxyError(
                f"proxy audit line {line_number} is invalid JSON"
            ) from exc
        if not isinstance(record, dict) or set(record) != _AUDIT_KEYS:
            raise SandboxProxyError(
                f"proxy audit line {line_number} has an unsafe schema"
            )
        if record["schema_version"] != 1:
            raise SandboxProxyError("proxy audit schema version is unsupported")
        identity = record["request_identity_sha256"]
        if not isinstance(identity, str) or _SHA256.fullmatch(identity) is None:
            raise SandboxProxyError("proxy audit request identity is invalid")
        if record["request_state"] not in _REQUEST_STATES:
            raise SandboxProxyError("proxy audit request state is invalid")
        model = record["model"]
        model_is_policy_rejection = (
            model is None
            and record["request_state"] == "not_accepted"
            and record["failure_class"] == "policy_rejection"
        )
        if model != allowed_model and not model_is_policy_rejection:
            raise SandboxProxyError("proxy audit model is invalid")
        started_at = _parse_audit_timestamp(record["started_at"])
        finished_at = _parse_audit_timestamp(record["finished_at"])
        if finished_at < started_at:
            raise SandboxProxyError("proxy audit timestamp order is invalid")
        latency = record["latency_ms"]
        if (
            isinstance(latency, bool)
            or not isinstance(latency, (int, float))
            or not math.isfinite(latency)
            or latency < 0
            or latency > _MAX_AUDIT_LATENCY_MS
        ):
            raise SandboxProxyError("proxy audit latency is invalid")
        status = record["upstream_status_code"]
        if status is not None and (
            type(status) is not int or not 100 <= status <= 599
        ):
            raise SandboxProxyError("proxy audit upstream status is invalid")
        provider_request_id = record["provider_request_id"]
        if provider_request_id is not None and (
            not isinstance(provider_request_id, str)
            or _PROVIDER_REQUEST_ID.fullmatch(provider_request_id) is None
        ):
            raise SandboxProxyError("proxy audit provider request ID is invalid")
        for field in ("input_tokens", "output_tokens", "total_tokens"):
            if not _is_optional_integer(record[field]):
                raise SandboxProxyError(f"proxy audit {field} is invalid")
        cost = record["provider_cost_usd"]
        if cost is not None and (
            isinstance(cost, bool)
            or not isinstance(cost, (int, float))
            or not math.isfinite(cost)
            or cost < 0
            or cost > 10**9
        ):
            raise SandboxProxyError("proxy audit provider cost is invalid")
        if record["failure_class"] not in _FAILURE_CLASSES:
            raise SandboxProxyError("proxy audit failure class is invalid")
        _validate_audit_semantics(record)
        records.append(record)
    return tuple(records)


def _request_state(records: Sequence[Mapping[str, object]]) -> str:
    states = {record["request_state"] for record in records}
    if "quarantined" in states:
        return "quarantined"
    if "completed" in states:
        return "completed"
    return "not_accepted"


def _requires_cross_attempt_denial(record: Mapping[str, object]) -> bool:
    return (
        record.get("request_state") == "quarantined"
        and record.get("failure_class") in _CROSS_ATTEMPT_DENIAL_FAILURES
    )


def _is_retryable_replay_denial(
    records: Sequence[Mapping[str, object]],
) -> bool:
    return bool(records) and all(
        record.get("request_state") == "quarantined"
        and record.get("failure_class") == "replay_denied"
        and record.get("upstream_status_code") is None
        for record in records
    )


def _attempt_paths(
    run_dir: Path, attempt_id: str
) -> tuple[Path, Path, Path, Path]:
    lifecycle = (
        run_dir
        / "lifecycles"
        / attempt_id
        / "proxy-sandbox-lifecycle-v2.json"
    )
    network_lifecycle = lifecycle.with_name(
        "proxy-network-lifecycle-v1.json"
    )
    audit = run_dir / "attempts" / attempt_id / "proxy-audit.jsonl"
    quarantine = audit.with_suffix(".quarantined.json")
    return lifecycle, network_lifecycle, audit, quarantine


def _request_registry_path(run_dir: Path) -> Path:
    return run_dir / "proxy-request-registry.json"


def _read_request_registry(path: Path) -> set[str]:
    if not path.exists() and not path.is_symlink():
        return set()
    _private_file_metadata(path)
    try:
        payload = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SandboxProxyError("proxy request registry is invalid JSON") from exc
    if not isinstance(payload, dict) or set(payload) != {
        "schema_version",
        "request_identities_sha256",
    }:
        raise SandboxProxyError("proxy request registry has an unsafe schema")
    identities = payload["request_identities_sha256"]
    if (
        payload["schema_version"] != 1
        or not isinstance(identities, list)
        or len(identities) > _MAX_REQUEST_IDENTITIES
    ):
        raise SandboxProxyError("proxy request registry is invalid")
    if any(
        not isinstance(identity, str) or _SHA256.fullmatch(identity) is None
        for identity in identities
    ):
        raise SandboxProxyError("proxy request registry identity is invalid")
    if identities != sorted(set(identities)):
        raise SandboxProxyError("proxy request registry identities are not canonical")
    return set(identities)


def _write_request_registry(path: Path, identities: set[str]) -> None:
    if len(identities) > _MAX_REQUEST_IDENTITIES or any(
        _SHA256.fullmatch(identity) is None for identity in identities
    ):
        raise SandboxProxyError("proxy request registry exceeds its safe contract")
    _atomic_private_write(
        path,
        (
            json.dumps(
                {
                    "schema_version": 1,
                    "request_identities_sha256": sorted(identities),
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode(),
    )


def _collect_denied_request_identities(
    run_dir: Path,
    *,
    secret: bytes | bytearray,
    allowed_model: str,
) -> set[str]:
    recorded_registry = _read_request_registry(_request_registry_path(run_dir))
    persisted_identities: set[str] = set()
    denied_identities: set[str] = set()
    attempts_root = run_dir / "attempts"
    if attempts_root.exists():
        for audit_path in sorted(attempts_root.glob("*/proxy-audit.jsonl")):
            _private_file_metadata(audit_path)
            records = _parse_audit(
                audit_path.read_bytes(),
                secret=secret,
                allowed_model=allowed_model,
            )
            for record in records:
                if record["request_state"] in {"completed", "quarantined"}:
                    persisted_identities.add(
                        str(record["request_identity_sha256"])
                    )
                if _requires_cross_attempt_denial(record):
                    denied_identities.add(
                        str(record["request_identity_sha256"])
                    )
    orphaned = recorded_registry - persisted_identities
    if orphaned:
        raise SandboxProxyError(
            "proxy request registry contains an identity without a persisted audit"
        )
    if len(denied_identities) > _MAX_REQUEST_IDENTITIES:
        raise SandboxProxyError("proxy request registry exceeds its safe contract")
    return denied_identities


def _archive_retryable_replay_denial(path: Path) -> Path:
    archive = path.with_name("proxy-audit.replay-denied-v1.jsonl")
    if archive.exists() or archive.is_symlink():
        raise SandboxProxyError(
            "retryable replay-denial audit was already archived once"
        )
    os.replace(path, archive)
    directory_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    return archive


def _quarantine_marker(path: Path, *, reason: str) -> None:
    _atomic_private_write(
        path,
        (
            json.dumps(
                {
                    "schema_version": 1,
                    "request_state": "quarantined",
                    "reason": reason,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode(),
    )


class SandboxProxyManager:
    """Own one proxy container and one exact scoped network per caller attempt."""

    def __init__(
        self,
        *,
        backend: SandboxBackend,
        config: SandboxProxyConfig,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self.backend = backend
        self.config = config
        self.clock = clock

    @contextmanager
    def open(
        self,
        *,
        run_id: str,
        attempt_id: str,
        task_id: str,
        caller_role: Literal["worker", "evolver"],
        run_dir: str | Path,
    ) -> Iterator[SandboxProxySession]:
        if caller_role not in _CALLER_ROLES:
            raise SandboxProxyError("caller_role must be 'worker' or 'evolver'")
        if not isinstance(self.backend, ScopedNetworkBackend):
            raise SandboxProxyError(
                "sandbox backend must implement the ScopedNetworkBackend contract"
            )
        run_root = Path(run_dir).expanduser().resolve()
        (
            lifecycle_uri,
            network_lifecycle_uri,
            audit_uri,
            quarantine_uri,
        ) = _attempt_paths(run_root, attempt_id)
        try:
            raw_token = _read_token_bytes(self.config.token_file)
        except ModelProxyError as exc:
            raise SandboxProxyError(str(exc)) from exc
        token_buffer = bytearray(raw_token)
        del raw_token
        try:
            if quarantine_uri.exists():
                raise SandboxProxyError(
                    "quarantined request identity requires a new attempt identity"
                )
            if audit_uri.exists() or audit_uri.is_symlink():
                _private_file_metadata(audit_uri)
                records = _parse_audit(
                    audit_uri.read_bytes(),
                    secret=token_buffer,
                    allowed_model=self.config.allowed_model,
                )
                if not records:
                    _quarantine_marker(
                        quarantine_uri, reason="missing_persisted_request_record"
                    )
                    raise SandboxProxyError(
                        "proxy audit has no persisted request record"
                    )
                state = _request_state(records)
                if _is_retryable_replay_denial(records):
                    _archive_retryable_replay_denial(audit_uri)
                elif state in {"completed", "quarantined"}:
                    raise SandboxProxyError(
                        f"{state} request identity must not reopen a proxy session"
                    )
            denied_request_identities = _collect_denied_request_identities(
                run_root,
                secret=token_buffer,
                allowed_model=self.config.allowed_model,
            )
        except BaseException:
            for index in range(len(token_buffer)):
                token_buffer[index] = 0
            raise

        network: SandboxNetworkHandle | None = None
        handle = None
        lifecycle_written = False
        network_lifecycle_written = False
        yielded = False
        primary_error: BaseException | None = None
        audit_policy_error: SandboxProxyError | None = None
        cleanup_errors: list[SandboxProxyError] = []
        session: SandboxProxySession | None = None

        try:
            network = _backend_call(
                "proxy.network.create",
                lambda: self.backend.create_internal_network(
                    run_id=run_id, network_scope=attempt_id
                ),
                secret=token_buffer,
            )
            if not isinstance(network, SandboxNetworkHandle):
                raise SandboxProxyError(
                    "scoped network backend returned an invalid network handle"
                )
            _backend_call(
                "proxy.network.lifecycle",
                lambda: create_network_lifecycle(
                    network_lifecycle_uri,
                    handle=network,
                    at=self.clock(),
                ),
                secret=token_buffer,
            )
            network_lifecycle_written = True
            plan = build_model_proxy_sandbox_plan(
                run_id=run_id,
                attempt_id=attempt_id,
                task_id=task_id,
                image_ref=self.config.image_ref,
                upstream_base_url=self.config.upstream_base_url,
                allowed_path_prefix=self.config.allowed_path_prefix,
                listen_port=self.config.listen_port,
                cpu_count=self.config.resource_contract.cpu_count,
                memory_mb=self.config.resource_contract.memory_mb,
                pids_limit=self.config.resource_contract.pids_limit,
                timeout_seconds=self.config.resource_contract.timeout_seconds,
                network_scope=attempt_id,
                allowed_model=self.config.allowed_model,
                required_provider=self.config.required_provider,
                audit_path=_PRIVATE_AUDIT_PATH,
                denied_request_identities_sha256=tuple(
                    sorted(denied_request_identities)
                ),
                writable_tmpfs_mb=self.config.resource_contract.writable_tmpfs_mb,
            )
            (
                public_plan_sha256,
                public_config_sha256,
                attempt_identity,
            ) = model_proxy_plan_identity(plan)
            public_config_identity = json.dumps(
                plan.config_payload(), sort_keys=True, separators=(",", ":")
            ).encode()
            handle = _backend_call(
                "proxy.create",
                lambda: self.backend.create(plan.spec),
                secret=token_buffer,
            )
            _backend_call(
                "proxy.lifecycle",
                lambda: create_lifecycle(
                    lifecycle_uri,
                    handle=handle,
                    spec=plan.spec,
                    attempt_identity_sha256=attempt_identity,
                    at=self.clock(),
                ),
                secret=token_buffer,
            )
            lifecycle_written = True
            _backend_call(
                "proxy.start",
                lambda: self.backend.start(handle),
                secret=token_buffer,
            )
            _backend_call(
                "proxy.lifecycle",
                lambda: mark_started(lifecycle_uri, at=self.clock()),
                secret=token_buffer,
            )
            config_payload = public_config_identity + b"\n"
            _backend_call(
                "proxy.config.transfer",
                lambda: self.backend.put_bytes(
                    handle, _PRIVATE_CONFIG_PATH, config_payload
                ),
                secret=token_buffer,
            )
            transfer_token = bytes(token_buffer)
            try:
                _backend_call(
                    "proxy.token.transfer",
                    lambda: self.backend.put_bytes(
                        handle, _PRIVATE_TOKEN_PATH, transfer_token
                    ),
                    secret=token_buffer,
                )
            finally:
                del transfer_token
            result = _backend_call(
                "proxy.readiness",
                lambda: self.backend.run(
                    handle,
                    (
                        "/usr/local/bin/python3",
                        "-c",
                        _READY_CODE,
                        str(self.config.listen_port),
                        str(
                            min(
                                _READY_TIMEOUT_SECONDS,
                                self.config.timeout_seconds,
                            )
                        ),
                    ),
                    environment={},
                    timeout_seconds=self.config.timeout_seconds,
                ),
                secret=token_buffer,
            )
            if not isinstance(result, SandboxCommandResult):
                raise SandboxProxyError("proxy readiness returned an invalid result")
            if result.timed_out or result.exit_code != 0:
                detail = result.stderr or result.stdout or f"exit {result.exit_code}"
                if token_buffer:
                    detail = detail.replace(
                        token_buffer.decode("ascii"), "[REDACTED]"
                    )
                raise SandboxProxyError(
                    "proxy readiness failed: "
                    + " ".join(detail.split())[:1000]
                )
            session = SandboxProxySession(
                base_url=(
                    f"http://{_PROXY_ALIAS}:{self.config.listen_port}"
                    f"{plan.allowed_path_prefix}"
                ),
                network_scope=network.network_scope,
                network_name=network.name,
                network_id=network.native_id,
                native_id=handle.native_id,
                lifecycle_uri=lifecycle_uri,
                audit_uri=audit_uri,
                allowed_model=self.config.allowed_model,
                required_provider=self.config.required_provider,
                immutable_image_ref=handle.immutable_image_ref,
                spec_sha256=handle.spec_sha256,
                public_plan_sha256=public_plan_sha256,
                public_config_sha256=public_config_sha256,
                attempt_identity_sha256=attempt_identity,
            )
            yielded = True
            try:
                yield session
            except BaseException as exc:  # caller exception must survive cleanup.
                primary_error = exc
        except BaseException as exc:  # setup/config/backend boundary.
            if primary_error is None:
                primary_error = exc
        finally:
            if yielded and handle is not None:
                try:
                    finalize_result = _backend_call(
                        "proxy.audit.finalize",
                        lambda: self.backend.run(
                            handle,
                            (
                                "/usr/local/bin/python3",
                                "-c",
                                _FINALIZE_CODE,
                                str(self.config.listen_port),
                                str(self.config.timeout_seconds),
                            ),
                            environment={},
                            timeout_seconds=self.config.timeout_seconds,
                        ),
                        secret=token_buffer,
                    )
                    if not isinstance(finalize_result, SandboxCommandResult):
                        raise SandboxProxyError(
                            "proxy audit finalize returned an invalid result"
                        )
                    if finalize_result.timed_out or finalize_result.exit_code != 0:
                        detail = (
                            finalize_result.stderr
                            or finalize_result.stdout
                            or f"exit {finalize_result.exit_code}"
                        )
                        if token_buffer:
                            detail = detail.replace(
                                token_buffer.decode("ascii"), "[REDACTED]"
                            )
                        raise SandboxProxyError(
                            "proxy audit finalize failed: "
                            + " ".join(detail.split())[:1000]
                        )
                    seal = _parse_audit_seal(finalize_result.stdout)
                    audit_payload = _backend_call(
                        "proxy.audit.download",
                        lambda: self.backend.read_bytes(handle, _PRIVATE_AUDIT_PATH),
                        secret=token_buffer,
                    )
                    if not isinstance(audit_payload, bytes):
                        raise SandboxProxyError(
                            "proxy audit download returned non-bytes data"
                        )
                    if hashlib.sha256(audit_payload).hexdigest() != seal[
                        "audit_sha256"
                    ]:
                        raise SandboxProxyError(
                            "proxy audit seal digest does not match downloaded bytes"
                        )
                    records = _parse_audit(
                        audit_payload,
                        secret=token_buffer,
                        allowed_model=self.config.allowed_model,
                    )
                    if len(records) != seal["record_count"]:
                        raise SandboxProxyError(
                            "proxy audit seal record count does not match audit"
                        )
                    if self.config.expect_request and not records:
                        raise SandboxProxyError(
                            "proxy audit has no persisted request record"
                        )
                    _atomic_private_write(audit_uri, audit_payload)
                    registry_identities = _collect_denied_request_identities(
                        run_root,
                        secret=token_buffer,
                        allowed_model=self.config.allowed_model,
                    )
                    _write_request_registry(
                        _request_registry_path(run_root), registry_identities
                    )
                    if any(
                        _requires_cross_attempt_denial(record)
                        for record in records
                    ):
                        audit_policy_error = SandboxProxyError(
                            "proxy audit contains an ambiguous accepted request"
                        )
                except SandboxProxyError as exc:
                    cleanup_errors.append(exc)
                    try:
                        _quarantine_marker(
                            quarantine_uri, reason="audit_download_or_validation_failed"
                        )
                    except SandboxProxyError as marker_exc:
                        cleanup_errors.append(marker_exc)
            if lifecycle_written and lifecycle_uri.is_file():
                try:
                    mark_finished(
                        lifecycle_uri,
                        at=self.clock(),
                        failure=(str(primary_error) if primary_error else None),
                        forbidden_values=(token_buffer.decode("ascii"),),
                    )
                except Exception as exc:  # noqa: BLE001 - lifecycle cleanup boundary.
                    cleanup_errors.append(
                        SandboxProxyError(
                            "proxy.lifecycle.finish: "
                            + _safe_detail(exc, token_buffer)
                        )
                    )
            if handle is not None:
                try:
                    result = self.backend.kill(handle.native_id)
                    if lifecycle_written and lifecycle_uri.is_file():
                        mark_cleaned(
                            lifecycle_uri,
                            cleanup_method="exact-id",
                            cleanup_result=result.outcome,
                            at=self.clock(),
                        )
                except Exception as exc:  # noqa: BLE001 - exact-ID cleanup boundary.
                    cleanup_errors.append(
                        SandboxProxyError(
                            "proxy.cleanup: " + _safe_detail(exc, token_buffer)
                        )
                    )
            if network is not None:
                try:
                    outcome = self.backend.remove_internal_network(network)
                    if outcome not in {"killed", "already_absent"}:
                        raise SandboxProxyError(
                            "proxy network cleanup returned an invalid outcome"
                        )
                    if (
                        network_lifecycle_written
                        and network_lifecycle_uri.is_file()
                    ):
                        mark_network_cleaned(
                            network_lifecycle_uri,
                            cleanup_method="exact-id",
                            cleanup_result=outcome,
                            at=self.clock(),
                        )
                except Exception as exc:  # noqa: BLE001 - exact network cleanup boundary.
                    cleanup_errors.append(
                        SandboxProxyError(
                            "proxy.network.cleanup: "
                            + _safe_detail(exc, token_buffer)
                        )
                    )
            for index in range(len(token_buffer)):
                token_buffer[index] = 0

        if cleanup_errors:
            detail = "; ".join(str(error) for error in cleanup_errors)[:2_000]
            if primary_error is not None:
                raise SandboxProxyError(
                    f"proxy session failed and cleanup was incomplete: {detail}"
                ) from primary_error
            raise SandboxProxyError(f"proxy cleanup was incomplete: {detail}")
        if audit_policy_error is not None:
            if primary_error is not None:
                raise audit_policy_error from primary_error
            raise audit_policy_error
        if primary_error is not None:
            raise primary_error.with_traceback(primary_error.__traceback__)


__all__ = [
    "SandboxProxyConfig",
    "SandboxProxyError",
    "SandboxProxyManager",
    "SandboxProxySession",
]
