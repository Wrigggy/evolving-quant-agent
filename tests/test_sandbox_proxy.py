from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import pytest

from qea.executors.sandbox_nexau import SandboxResourceContract
from qea.sandbox_backend import (
    KillResult,
    SandboxCommandResult,
    SandboxHandle,
    SandboxNetworkHandle,
    SandboxState,
)


REAL_TOKEN = b"sk-attempt-private-token"
NOW = datetime(2026, 7, 31, 12, 0, tzinfo=timezone.utc)
AUDIT_KEYS = {
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


def _audit_record(request_state: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "request_identity_sha256": "a" * 64,
        "model": "openai/gpt-5",
        "started_at": "2026-07-31T12:00:00+00:00",
        "finished_at": "2026-07-31T12:00:01+00:00",
        "latency_ms": 1000,
        "request_state": request_state,
        "upstream_status_code": 200 if request_state == "completed" else None,
        "provider_request_id": (
            "provider-request-1" if request_state == "completed" else None
        ),
        "input_tokens": 10 if request_state == "completed" else None,
        "output_tokens": 5 if request_state == "completed" else None,
        "total_tokens": 15 if request_state == "completed" else None,
        "provider_cost_usd": 0.002 if request_state == "completed" else None,
        "failure_class": (
            None
            if request_state == "completed"
            else (
                "pre_accept_transport"
                if request_state == "not_accepted"
                else "post_accept_transport"
            )
        ),
    }


def _audit_bytes(request_state: str) -> bytes:
    return (json.dumps(_audit_record(request_state), sort_keys=True) + "\n").encode()


def _audit_seal(payload: bytes) -> dict[str, object]:
    return {
        "schema_version": 1,
        "record_count": len([line for line in payload.splitlines() if line.strip()]),
        "audit_sha256": hashlib.sha256(payload).hexdigest(),
    }


def _seal_result(payload: bytes) -> SandboxCommandResult:
    return SandboxCommandResult(
        0,
        json.dumps(_audit_seal(payload), sort_keys=True),
        "",
        False,
    )


def _token_file(tmp_path: Path, *, mode: int = 0o600) -> Path:
    path = tmp_path / "model-token"
    path.write_bytes(REAL_TOKEN + b"\n")
    path.chmod(mode)
    return path


def _resources() -> SandboxResourceContract:
    return SandboxResourceContract(
        cpu_count=1,
        memory_mb=512,
        pids_limit=64,
        timeout_seconds=300,
        writable_tmpfs_mb={"/run/qea-secrets": 1, "/tmp": 64},
    )


class RecordingBackend:
    backend_name = "fake-scoped-backend"

    def __init__(
        self,
        lifecycle_root: Path,
        *,
        audit_payload: bytes = _audit_bytes("not_accepted"),
        failure: str | None = None,
        finalize_result: SandboxCommandResult | None = None,
    ) -> None:
        self.lifecycle_root = lifecycle_root
        self.audit_payload = audit_payload
        self.failure = failure
        self.finalize_result = finalize_result
        self.events: list[object] = []
        self.specs = []
        self.uploads: list[tuple[str, str, bytes]] = []
        self.network_handles: list[SandboxNetworkHandle] = []
        self.sandbox_handles: list[SandboxHandle] = []
        self.states: dict[str, SandboxState] = {}

    def _fail(self, phase: str) -> None:
        if self.failure == phase:
            raise RuntimeError(f"synthetic {phase} failure {REAL_TOKEN.decode()}")

    def create_internal_network(
        self, *, run_id: str, network_scope: str
    ) -> SandboxNetworkHandle:
        self._fail("network-create")
        index = len(self.network_handles) + 1
        identity = hashlib.sha256(f"{run_id}:{network_scope}".encode()).hexdigest()
        handle = SandboxNetworkHandle(
            backend=self.backend_name,
            native_id=f"network-native-{index}",
            name=f"qea-{run_id}-{network_scope}-{identity[:12]}-internal",
            run_id=run_id,
            network_scope=network_scope,
            identity_sha256=identity,
        )
        self.network_handles.append(handle)
        self.events.append(("network-create", handle))
        return handle

    def remove_internal_network(self, handle: SandboxNetworkHandle):
        self.events.append(("network-remove", handle))
        self._fail("network-remove")
        self.states.pop(handle.native_id, None)
        return "killed"

    def create(self, spec):
        self._fail("create")
        self.specs.append(spec)
        handle = SandboxHandle(
            backend=self.backend_name,
            native_id=f"proxy-native-{len(self.sandbox_handles) + 1}",
            immutable_image_ref=spec.image_ref,
            spec_sha256=spec.spec_sha256,
        )
        self.sandbox_handles.append(handle)
        self.states[handle.native_id] = SandboxState(
            backend=self.backend_name,
            native_id=handle.native_id,
            status="created",
            labels={
                "qea.managed": "true",
                "qea.spec-sha256": spec.spec_sha256,
                "qea.network-scope": spec.network_scope or "",
            },
            immutable_image_ref=spec.image_ref,
        )
        self.events.append(("create", handle, spec))
        return handle

    def start(self, handle: SandboxHandle) -> None:
        lifecycle_exists = bool(
            tuple(self.lifecycle_root.rglob("proxy-sandbox-lifecycle-v2.json"))
        )
        self.events.append(("start", handle.native_id, lifecycle_exists))
        self._fail("start")

    def put_bytes(self, handle: SandboxHandle, path: str, payload: bytes) -> None:
        self.events.append(("upload", handle.native_id, path, payload))
        if self.failure == "config-transfer" and path.endswith("proxy-config.json"):
            self._fail("config-transfer")
        if self.failure == "token-transfer" and path.endswith("model-token"):
            self._fail("token-transfer")
        self.uploads.append((handle.native_id, path, payload))

    def read_bytes(self, handle: SandboxHandle, path: str) -> bytes:
        self.events.append(("read", handle.native_id, path))
        self._fail("audit-download")
        return self.audit_payload

    def run(
        self,
        handle: SandboxHandle,
        argv,
        *,
        environment,
        timeout_seconds: int,
    ) -> SandboxCommandResult:
        self.events.append(
            (
                "run",
                handle.native_id,
                tuple(argv),
                dict(environment),
                timeout_seconds,
            )
        )
        if any("/__qea_private/finalize" in str(value) for value in argv):
            self._fail("finalize")
            return self.finalize_result or _seal_result(self.audit_payload)
        self._fail("readiness")
        return SandboxCommandResult(0, "ready", "", False)

    def inspect(self, native_id: str):
        return self.states.get(native_id)

    def list(self, labels):
        return tuple(self.states.values())

    def kill(self, native_id: str) -> KillResult:
        self.events.append(("kill", native_id))
        self._fail("kill")
        self.states.pop(native_id, None)
        return KillResult(native_id=native_id, outcome="killed")


def _manager(
    tmp_path: Path,
    backend: RecordingBackend,
    *,
    mode: int = 0o600,
    expect_request: bool | None = None,
):
    from qea.executors.sandbox_proxy import SandboxProxyConfig, SandboxProxyManager

    config_values = {
        "image_ref": "sha256:" + "c" * 64,
        "resource_contract": _resources(),
        "token_file": _token_file(tmp_path, mode=mode),
        "upstream_base_url": "https://openrouter.ai/api/v1",
        "allowed_path_prefix": "/v1",
        "allowed_model": "openai/gpt-5",
        "listen_port": 8080,
        "timeout_seconds": 10,
    }
    if expect_request is not None:
        config_values["expect_request"] = expect_request
    return SandboxProxyManager(
        backend=backend,
        config=SandboxProxyConfig(**config_values),
        clock=lambda: NOW,
    )


def _open(manager, run_dir: Path, attempt_id: str = "attempt-001"):
    return manager.open(
        run_id="run-001",
        attempt_id=attempt_id,
        task_id="historical-var-data-prep",
        caller_role="worker",
        run_dir=run_dir,
    )


def test_session_uses_one_scoped_network_and_private_token_transfer(tmp_path):
    run_dir = tmp_path / "run"
    backend = RecordingBackend(run_dir, audit_payload=_audit_bytes("completed"))
    manager = _manager(tmp_path, backend)

    with _open(manager, run_dir) as session:
        assert session.base_url == "http://qea-model-proxy:8080/v1"
        assert session.network_scope == "attempt-001"
        assert session.network_name == backend.network_handles[0].name
        assert session.network_id == "network-native-1"
        assert session.native_id == "proxy-native-1"
        assert session.allowed_model == "openai/gpt-5"
        assert session.lifecycle_uri.is_file()
        assert REAL_TOKEN.decode() not in json.dumps(asdict(session), default=str)

    assert len(backend.network_handles) == 1
    assert len(backend.sandbox_handles) == 1
    [spec] = backend.specs
    assert spec.role == "proxy"
    assert spec.network_scope == "attempt-001"
    assert dict(spec.environment) == {}
    assert REAL_TOKEN.decode() not in spec.canonical_json()
    assert backend.uploads[-1] == (
        "proxy-native-1",
        "/run/qea-secrets/model-token",
        REAL_TOKEN,
    )
    token_occurrences = [
        event
        for event in backend.events
        if isinstance(event, tuple) and REAL_TOKEN in repr(event).encode()
    ]
    assert token_occurrences == [
        ("upload", "proxy-native-1", "/run/qea-secrets/model-token", REAL_TOKEN)
    ]
    assert REAL_TOKEN.decode() not in session.lifecycle_uri.read_text()
    assert REAL_TOKEN.decode() not in session.audit_uri.read_text()
    assert session.audit_uri.stat().st_mode & 0o777 == 0o600
    assert set(json.loads(session.audit_uri.read_text())) == AUDIT_KEYS
    assert backend.events[-3][0:2] == ("read", "proxy-native-1")
    assert backend.events[-2] == ("kill", "proxy-native-1")
    assert backend.events[-1] == ("network-remove", backend.network_handles[0])
    lifecycle = json.loads(session.lifecycle_uri.read_text())
    assert lifecycle["cleaned_up"] is True
    assert lifecycle["native_id"] == "proxy-native-1"


def test_two_attempts_in_one_run_never_share_proxy_or_network_ids(tmp_path):
    run_dir = tmp_path / "run"
    backend = RecordingBackend(run_dir)
    manager = _manager(tmp_path, backend)

    with _open(manager, run_dir, "attempt-a") as first:
        pass
    with _open(manager, run_dir, "attempt-b") as second:
        pass

    assert first.network_scope == "attempt-a"
    assert second.network_scope == "attempt-b"
    assert first.network_id != second.network_id
    assert first.network_name != second.network_name
    assert first.native_id != second.native_id


@pytest.mark.parametrize("failure", ["start", "config-transfer", "token-transfer"])
def test_start_and_transfer_failures_cleanup_exact_recorded_ids(tmp_path, failure):
    run_dir = tmp_path / "run"
    backend = RecordingBackend(run_dir, failure=failure)
    manager = _manager(tmp_path, backend)

    with pytest.raises(Exception, match="synthetic") as raised:
        with _open(manager, run_dir):
            pytest.fail("session must not be yielded")

    assert REAL_TOKEN.decode() not in str(raised.value)
    assert ("kill", "proxy-native-1") in backend.events
    assert backend.events[-1] == ("network-remove", backend.network_handles[0])
    lifecycle_path = next(run_dir.rglob("proxy-sandbox-lifecycle-v2.json"))
    lifecycle = json.loads(lifecycle_path.read_text())
    assert lifecycle["cleaned_up"] is True
    assert REAL_TOKEN.decode() not in lifecycle_path.read_text()


def test_readiness_failure_retains_token_redaction_through_lifecycle_cleanup(tmp_path):
    run_dir = tmp_path / "run"
    backend = RecordingBackend(run_dir, failure="readiness")
    manager = _manager(tmp_path, backend)

    with pytest.raises(Exception) as raised:
        with _open(manager, run_dir):
            pytest.fail("session must not be yielded")

    assert REAL_TOKEN.decode() not in str(raised.value)
    lifecycle_path = next(run_dir.rglob("proxy-sandbox-lifecycle-v2.json"))
    assert REAL_TOKEN.decode() not in lifecycle_path.read_text()
    assert ("kill", "proxy-native-1") in backend.events
    assert backend.events[-1] == ("network-remove", backend.network_handles[0])


def test_caller_exception_is_preserved_after_audit_download_and_cleanup(tmp_path):
    class CallerFailure(RuntimeError):
        pass

    run_dir = tmp_path / "run"
    backend = RecordingBackend(run_dir, audit_payload=_audit_bytes("not_accepted"))
    manager = _manager(tmp_path, backend)
    failure = CallerFailure("caller failed")

    with pytest.raises(CallerFailure) as raised:
        with _open(manager, run_dir):
            raise failure

    assert raised.value is failure
    assert backend.events[-3][0] == "read"
    assert backend.events[-2] == ("kill", "proxy-native-1")
    assert backend.events[-1][0] == "network-remove"


class BackendWithoutScopedNetwork:
    backend_name = "missing-scoped-network"

    def __init__(self) -> None:
        self.events = []

    def create(self, spec):
        self.events.append(("create", spec))


def test_backend_without_scoped_network_contract_fails_closed(tmp_path):
    from qea.executors.sandbox_proxy import (
        SandboxProxyConfig,
        SandboxProxyError,
        SandboxProxyManager,
    )

    backend = BackendWithoutScopedNetwork()
    manager = SandboxProxyManager(
        backend=backend,
        config=SandboxProxyConfig(
            image_ref="sha256:" + "c" * 64,
            resource_contract=_resources(),
            token_file=_token_file(tmp_path),
            upstream_base_url="https://openrouter.ai/api/v1",
            allowed_path_prefix="/v1",
            allowed_model="openai/gpt-5",
        ),
    )

    with pytest.raises(SandboxProxyError, match="ScopedNetworkBackend"):
        with _open(manager, tmp_path / "run"):
            pytest.fail("session must not be yielded")
    assert backend.events == []


@pytest.mark.parametrize("mode", [0o604, 0o640, 0o666])
def test_manager_rejects_non_private_token_before_creating_network(tmp_path, mode):
    run_dir = tmp_path / "run"
    backend = RecordingBackend(run_dir)
    manager = _manager(tmp_path, backend, mode=mode)

    with pytest.raises(Exception, match="group or other"):
        with _open(manager, run_dir):
            pytest.fail("session must not be yielded")
    assert backend.events == []


@pytest.mark.parametrize("request_state", ["completed", "quarantined"])
def test_resume_never_reopens_completed_or_quarantined_request_identity(
    tmp_path, request_state
):
    run_dir = tmp_path / "run"
    first_backend = RecordingBackend(
        run_dir, audit_payload=_audit_bytes(request_state)
    )
    manager = _manager(tmp_path, first_backend)
    with _open(manager, run_dir):
        pass

    second_backend = RecordingBackend(run_dir)
    manager = _manager(tmp_path, second_backend)
    with pytest.raises(Exception, match=request_state):
        with _open(manager, run_dir):
            pytest.fail("resume must not create a second proxy")
    assert second_backend.events == []


def test_resume_may_retry_request_proven_not_accepted(tmp_path):
    run_dir = tmp_path / "run"
    first_backend = RecordingBackend(
        run_dir, audit_payload=_audit_bytes("not_accepted")
    )
    manager = _manager(tmp_path, first_backend)
    with _open(manager, run_dir):
        pass

    second_backend = RecordingBackend(run_dir)
    manager = _manager(tmp_path, second_backend)
    with _open(manager, run_dir) as retried:
        assert retried.native_id == "proxy-native-1"
    assert second_backend.events[0][0] == "network-create"


def test_empty_downloaded_audit_quarantines_attempt_and_never_reopens(tmp_path):
    run_dir = tmp_path / "run"
    first_backend = RecordingBackend(run_dir, audit_payload=b"")
    manager = _manager(tmp_path, first_backend)

    with pytest.raises(Exception, match="persisted request record"):
        with _open(manager, run_dir):
            pass

    quarantine = (
        run_dir
        / "attempts"
        / "attempt-001"
        / "proxy-audit.quarantined.json"
    )
    assert quarantine.is_file()
    assert quarantine.stat().st_mode & 0o777 == 0o600
    assert json.loads(quarantine.read_text())["request_state"] == "quarantined"
    assert not (
        run_dir / "attempts" / "attempt-001" / "proxy-audit.jsonl"
    ).exists()

    second_backend = RecordingBackend(run_dir)
    manager = _manager(tmp_path, second_backend)
    with pytest.raises(Exception, match="quarantined"):
        with _open(manager, run_dir):
            pytest.fail("an audit-loss attempt must not reopen")
    assert second_backend.events == []


def test_finalize_failure_quarantines_nonempty_not_accepted_audit_prefix(tmp_path):
    run_dir = tmp_path / "run"
    earlier_not_accepted = _audit_bytes("not_accepted")
    backend = RecordingBackend(
        run_dir,
        audit_payload=earlier_not_accepted,
        finalize_result=SandboxCommandResult(
            3,
            json.dumps({"error": {"code": "audit_append_failed"}}),
            "",
            False,
        ),
    )
    manager = _manager(tmp_path, backend)

    with pytest.raises(Exception, match="finalize"):
        with _open(manager, run_dir):
            pass

    quarantine = (
        run_dir
        / "attempts"
        / "attempt-001"
        / "proxy-audit.quarantined.json"
    )
    assert quarantine.is_file()
    assert not (
        run_dir / "attempts" / "attempt-001" / "proxy-audit.jsonl"
    ).exists()
    assert backend.events[-2] == ("kill", "proxy-native-1")
    assert backend.events[-1][0] == "network-remove"


@pytest.mark.parametrize(
    "seal_change",
    [
        {"record_count": 2},
        {"audit_sha256": "b" * 64},
    ],
)
def test_manager_quarantines_seal_count_or_hash_mismatch(tmp_path, seal_change):
    run_dir = tmp_path / "run"
    payload = _audit_bytes("completed")
    seal = _audit_seal(payload)
    seal.update(seal_change)
    backend = RecordingBackend(
        run_dir,
        audit_payload=payload,
        finalize_result=SandboxCommandResult(
            0, json.dumps(seal, sort_keys=True), "", False
        ),
    )
    manager = _manager(tmp_path, backend)

    with pytest.raises(Exception, match="seal"):
        with _open(manager, run_dir):
            pass

    assert not (
        run_dir / "attempts" / "attempt-001" / "proxy-audit.jsonl"
    ).exists()
    assert (
        run_dir
        / "attempts"
        / "attempt-001"
        / "proxy-audit.quarantined.json"
    ).is_file()


def test_sealed_zero_record_session_requires_explicit_no_request_policy(tmp_path):
    required_run = tmp_path / "required-run"
    required_backend = RecordingBackend(required_run, audit_payload=b"")
    required_manager = _manager(tmp_path, required_backend)
    with pytest.raises(Exception, match="persisted request record"):
        with _open(required_manager, required_run):
            pass

    optional_run = tmp_path / "optional-run"
    optional_backend = RecordingBackend(optional_run, audit_payload=b"")
    optional_manager = _manager(
        tmp_path, optional_backend, expect_request=False
    )
    with _open(optional_manager, optional_run) as session:
        pass

    assert session.audit_uri.is_file()
    assert session.audit_uri.read_bytes() == b""
    assert not session.audit_uri.with_suffix(".quarantined.json").exists()


def test_completed_hash_enters_private_run_registry_and_next_attempt_config(tmp_path):
    request_identity = "a" * 64
    run_dir = tmp_path / "run"
    first_backend = RecordingBackend(
        run_dir, audit_payload=_audit_bytes("completed")
    )
    manager = _manager(tmp_path, first_backend)
    with _open(manager, run_dir, "attempt-a"):
        pass

    registry = run_dir / "proxy-request-registry.json"
    assert registry.is_file()
    assert registry.stat().st_mode & 0o777 == 0o600
    assert json.loads(registry.read_text()) == {
        "request_identities_sha256": [request_identity],
        "schema_version": 1,
    }

    second_backend = RecordingBackend(run_dir)
    manager = _manager(tmp_path, second_backend)
    with _open(manager, run_dir, "attempt-b") as session:
        config_upload = next(
            payload
            for _, path, payload in second_backend.uploads
            if path == "/run/qea-secrets/proxy-config.json"
        )
        private_config = json.loads(config_upload)
        assert private_config["denied_request_identities_sha256"] == [
            request_identity
        ]
        public_surface = json.dumps(
            {
                "session": asdict(session),
                "spec": second_backend.specs[0].canonical_json(),
                "lifecycle": session.lifecycle_uri.read_text(),
            },
            default=str,
            sort_keys=True,
        )
        assert request_identity not in public_surface


def test_downloaded_audit_rejects_authorization_smuggled_in_safe_field(tmp_path):
    run_dir = tmp_path / "run"
    record = _audit_record("completed")
    record["provider_request_id"] = "Bearer private authorization"
    payload = (json.dumps(record, sort_keys=True) + "\n").encode()
    backend = RecordingBackend(run_dir, audit_payload=payload)
    manager = _manager(tmp_path, backend)

    with pytest.raises(Exception, match="provider request ID"):
        with _open(manager, run_dir):
            pass

    audit = run_dir / "attempts" / "attempt-001" / "proxy-audit.jsonl"
    assert not audit.exists()
    assert "authorization" not in "".join(
        path.read_text()
        for path in run_dir.rglob("*.json")
        if path.is_file()
    ).lower()
    assert backend.events[-2] == ("kill", "proxy-native-1")
    assert backend.events[-1][0] == "network-remove"


@pytest.mark.parametrize(
    "field",
    [
        "model",
        "started_at",
        "finished_at",
        "provider_request_id",
        "failure_class",
    ],
)
def test_downloaded_audit_rejects_token_smuggled_in_any_string_field(
    tmp_path, field
):
    run_dir = tmp_path / "run"
    record = _audit_record("completed")
    record[field] = REAL_TOKEN.decode()
    payload = (json.dumps(record, sort_keys=True) + "\n").encode()
    backend = RecordingBackend(run_dir, audit_payload=payload)
    manager = _manager(tmp_path, backend)

    with pytest.raises(Exception):
        with _open(manager, run_dir):
            pass

    assert REAL_TOKEN.decode() not in "".join(
        path.read_text()
        for path in run_dir.rglob("*")
        if path.is_file()
    )


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"model": "anthropic/other-model"}, "model"),
        ({"model": None}, "model"),
        ({"started_at": "not-a-timestamp"}, "timestamp"),
        ({"started_at": "9999-01-01T00:00:00+00:00"}, "timestamp"),
        (
            {
                "started_at": "2026-07-31T12:00:02+00:00",
                "finished_at": "2026-07-31T12:00:01+00:00",
            },
            "timestamp",
        ),
        ({"failure_class": "arbitrary free form"}, "failure class"),
        ({"provider_request_id": "x" * 513}, "provider request ID"),
    ],
)
def test_downloaded_audit_requires_exact_bounded_safe_fields(
    tmp_path, changes, message
):
    run_dir = tmp_path / "run"
    record = _audit_record("completed")
    record.update(changes)
    backend = RecordingBackend(
        run_dir,
        audit_payload=(json.dumps(record, sort_keys=True) + "\n").encode(),
    )
    manager = _manager(tmp_path, backend)

    with pytest.raises(Exception, match=message):
        with _open(manager, run_dir):
            pass


@pytest.mark.parametrize(
    "changes",
    [
        {
            "request_state": "not_accepted",
            "failure_class": "post_accept_transport",
            "upstream_status_code": None,
        },
        {
            "request_state": "completed",
            "failure_class": "provider_http_error",
            "upstream_status_code": 200,
        },
        {
            "request_state": "completed",
            "failure_class": None,
            "upstream_status_code": 500,
        },
        {
            "request_state": "quarantined",
            "failure_class": "policy_rejection",
            "upstream_status_code": None,
        },
    ],
)
def test_downloaded_audit_rejects_contradictory_state_failure_semantics(
    tmp_path, changes
):
    run_dir = tmp_path / "run"
    record = _audit_record("completed")
    record.update(changes)
    if record["request_state"] == "not_accepted":
        record["model"] = "openai/gpt-5"
    backend = RecordingBackend(
        run_dir,
        audit_payload=(json.dumps(record, sort_keys=True) + "\n").encode(),
    )
    manager = _manager(tmp_path, backend)

    with pytest.raises(Exception, match="semantic"):
        with _open(manager, run_dir):
            pass
