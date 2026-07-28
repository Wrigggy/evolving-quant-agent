from __future__ import annotations

import base64
import json
import shlex
from types import SimpleNamespace

import pytest

from qea.backends.e2b import (
    E2BBackendCapabilityError,
    E2BSandboxBackend,
    E2BSandboxBackendError,
)
from qea.sandbox_backend import SandboxSpec


class FakeFiles:
    def __init__(self) -> None:
        self.writes: list[tuple[str, bytes]] = []
        self.payloads: dict[str, bytes] = {}

    def write(self, path: str, data, **kwargs):
        self.writes.append((path, data))
        self.payloads[path] = data

    def read(self, path: str, format: str = "text", **kwargs):
        assert format == "bytes"
        return self.payloads[path]


class FakeCommands:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.result = SimpleNamespace(exit_code=23, stdout="out", stderr="err")

    def run(self, command: str, **kwargs):
        self.calls.append((command, kwargs))
        return self.result


class FakeSandbox:
    def __init__(self, sandbox_id: str = "e2b-native-exact-1") -> None:
        self.sandbox_id = sandbox_id
        self.files = FakeFiles()
        self.commands = FakeCommands()
        self.kill_calls = 0

    def kill(self):
        self.kill_calls += 1


class FakeFactory:
    def __init__(self) -> None:
        self.sandbox = FakeSandbox()
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.sandbox


def _spec(**changes) -> SandboxSpec:
    values = {
        "role": "verifier",
        "run_id": "run-1",
        "attempt_id": "attempt-1",
        "task_id": "historical-var-data-prep",
        "image_ref": "e2b-template:qfbench-verifier-historical-var-v3",
        "cpu_count": 2,
        "memory_mb": 4096,
        "pids_limit": 256,
        "timeout_seconds": 900,
        "network_policy": "none",
        "environment": {"QEA_ROLE": "verifier"},
        "writable_tmpfs_mb": {},
    }
    values.update(changes)
    return SandboxSpec(**values)


def test_create_preserves_e2b_template_and_native_sandbox_id() -> None:
    factory = FakeFactory()
    backend = E2BSandboxBackend(sandbox_factory=factory)
    spec = _spec()

    handle = backend.create(spec)
    backend.start(handle)

    assert handle.backend == "e2b"
    assert handle.native_id == "e2b-native-exact-1"
    assert handle.immutable_image_ref == spec.image_ref
    assert factory.calls == [
        {
            "template": "qfbench-verifier-historical-var-v3",
            "timeout": 900,
            "metadata": {
                "qea_role": "verifier",
                "qea_run_id": "run-1",
                "qea_attempt_id": "attempt-1",
                "qea_task_id": "historical-var-data-prep",
                "qea_spec_sha256": spec.spec_sha256,
            },
            "envs": {"QEA_ROLE": "verifier"},
            "secure": True,
            "allow_internet_access": False,
        }
    ]


def test_transfer_and_run_use_known_live_sandbox_only() -> None:
    factory = FakeFactory()
    backend = E2BSandboxBackend(sandbox_factory=factory)
    handle = backend.create(_spec())

    backend.put_bytes(handle, "/qea/input.bin", b"input")
    assert backend.read_bytes(handle, "/qea/input.bin") == b"input"
    result = backend.run(
        handle,
        ("python3", "-c", "print('task; not shell')"),
        environment={"QEA_MODE": "test"},
        timeout_seconds=30,
    )

    assert factory.sandbox.files.writes == [("/qea/input.bin", b"input")]
    command, kwargs = factory.sandbox.commands.calls[0]
    command_argv = shlex.split(command)
    assert command_argv[:2] == ["python3", "-c"]
    payload = json.loads(base64.b64decode(command_argv[3]))
    assert payload == {
        "argv": ["python3", "-c", "print('task; not shell')"],
        "environment": {"QEA_MODE": "test"},
    }
    assert kwargs == {"timeout": 30}
    assert result.exit_code == 23
    assert result.stdout == "out"
    assert result.stderr == "err"
    assert result.timed_out is False


def test_kill_is_exact_and_unknown_ids_are_not_guessed_absent() -> None:
    factory = FakeFactory()
    backend = E2BSandboxBackend(sandbox_factory=factory)
    handle = backend.create(_spec())

    result = backend.kill(handle.native_id)

    assert result.native_id == "e2b-native-exact-1"
    assert result.outcome == "killed"
    assert factory.sandbox.kill_calls == 1
    with pytest.raises(E2BBackendCapabilityError, match="unknown E2B sandbox"):
        backend.kill("account-sandbox-not-created-here")


def test_inspect_and_list_raise_typed_capability_errors() -> None:
    backend = E2BSandboxBackend(sandbox_factory=FakeFactory())
    with pytest.raises(E2BBackendCapabilityError, match="inspect"):
        backend.inspect("e2b-native-exact-1")
    with pytest.raises(E2BBackendCapabilityError, match="list"):
        backend.list({"qea.managed": "true"})


def test_create_rejects_docker_image_and_worker_network_without_sdk_policy() -> None:
    backend = E2BSandboxBackend(sandbox_factory=FakeFactory())
    with pytest.raises(E2BSandboxBackendError, match="E2B template"):
        backend.create(_spec(image_ref="sha256:" + "a" * 64))
    with pytest.raises(E2BSandboxBackendError, match="network policy"):
        backend.create(
            _spec(
                role="worker",
                network_policy="worker-proxy-only",
                environment={"LLM_API_KEY": "qea-proxy-placeholder"},
            )
        )
