from __future__ import annotations

import io
import json
import sys
import tarfile
from dataclasses import dataclass

import pytest

from qea.backends.rootless_docker import (
    CommandTimedOut,
    CompletedCommand,
    RootlessDockerBackend,
    RootlessDockerError,
    SubprocessCommandRunner,
)
from qea.sandbox_backend import SandboxHandle, SandboxSpec


DOCKER_HOST = "unix:///run/user/1013/docker.sock"
IMAGE_REF = "sha256:" + "a" * 64


@dataclass(frozen=True)
class RecordedCall:
    argv: tuple[str, ...]
    input_bytes: bytes | None
    timeout_seconds: int | None


class RecordingRunner:
    def __init__(self, *replies) -> None:
        self.replies = list(replies)
        self.calls: list[RecordedCall] = []

    def run(self, argv, *, input_bytes=None, timeout_seconds=None):
        self.calls.append(
            RecordedCall(tuple(argv), input_bytes, timeout_seconds)
        )
        if not self.replies:
            raise AssertionError(f"unexpected command: {tuple(argv)!r}")
        reply = self.replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        return reply


def _spec(**changes) -> SandboxSpec:
    values = {
        "role": "worker",
        "run_id": "run-1",
        "attempt_id": "attempt-1",
        "task_id": "historical-var-data-prep",
        "image_ref": IMAGE_REF,
        "cpu_count": 2,
        "memory_mb": 4096,
        "pids_limit": 256,
        "timeout_seconds": 900,
        "network_policy": "worker-proxy-only",
        "environment": {
            "LLM_API_KEY": "qea-proxy-placeholder",
            "QEA_ROLE": "worker",
        },
        "writable_tmpfs_mb": {"/tmp": 256, "/qea": 512},
    }
    values.update(changes)
    return SandboxSpec(**values)


def _handle(spec: SandboxSpec | None = None) -> SandboxHandle:
    actual = spec or _spec()
    return SandboxHandle(
        backend="rootless-docker",
        native_id="container-exact-1",
        immutable_image_ref=actual.image_ref,
        spec_sha256=actual.spec_sha256,
    )


def _labels(spec: SandboxSpec | None = None) -> dict[str, str]:
    actual = spec or _spec()
    return {
        "qea.managed": "true",
        "qea.backend": "rootless-docker",
        "qea.role": actual.role,
        "qea.run-id": actual.run_id,
        "qea.attempt-id": actual.attempt_id,
        "qea.task-id": actual.task_id,
        "qea.spec-sha256": actual.spec_sha256,
    }


def _inspect_reply(
    spec: SandboxSpec | None = None,
    *,
    labels: dict[str, str] | None = None,
    status: str = "running",
) -> CompletedCommand:
    actual = spec or _spec()
    payload = {
        "Id": "container-exact-1",
        "Image": actual.image_ref,
        "Config": {
            "Image": actual.image_ref,
            "Labels": labels if labels is not None else _labels(actual),
        },
        "State": {"Status": status},
        "NetworkSettings": {"Networks": {}},
    }
    return CompletedCommand(0, json.dumps(payload).encode(), b"")


def _tar_payload(name: str, payload: bytes) -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        info = tarfile.TarInfo(name)
        info.size = len(payload)
        info.mtime = 0
        archive.addfile(info, io.BytesIO(payload))
    return output.getvalue()


def _backend(runner: RecordingRunner) -> RootlessDockerBackend:
    return RootlessDockerBackend(
        docker_host=DOCKER_HOST,
        expected_uid=1013,
        runner=runner,
    )


def test_backend_rejects_system_tcp_and_wrong_user_sockets() -> None:
    for docker_host in (
        "unix:///var/run/docker.sock",
        "tcp://127.0.0.1:2375",
        "unix:///run/user/1000/docker.sock",
    ):
        with pytest.raises(RootlessDockerError):
            RootlessDockerBackend(
                docker_host=docker_host,
                expected_uid=1013,
                runner=RecordingRunner(),
            )


def test_create_emits_bounded_read_only_container_argv() -> None:
    runner = RecordingRunner(CompletedCommand(0, b"container-exact-1\n", b""))
    backend = _backend(runner)
    spec = _spec()

    handle = backend.create(spec)

    argv = runner.calls[0].argv
    assert argv[:4] == ("docker", "--host", DOCKER_HOST, "create")
    assert ("--cpus", "2") == _option_pair(argv, "--cpus")
    assert ("--memory", "4096m") == _option_pair(argv, "--memory")
    assert ("--memory-swap", "4096m") == _option_pair(argv, "--memory-swap")
    assert ("--pids-limit", "256") == _option_pair(argv, "--pids-limit")
    assert ("--cap-drop", "ALL") == _option_pair(argv, "--cap-drop")
    assert ("--security-opt", "no-new-privileges") == _option_pair(
        argv, "--security-opt"
    )
    assert ("--network", "qea-run-1-internal") == _option_pair(argv, "--network")
    assert "--read-only" in argv
    assert "--privileged" not in argv
    assert "--pid" not in argv
    assert "--volume" not in argv
    assert ("--env", "LLM_API_KEY=qea-proxy-placeholder") in _option_pairs(
        argv, "--env"
    )
    assert ("--tmpfs", "/qea:rw,nosuid,nodev,noexec,size=512m") in _option_pairs(
        argv, "--tmpfs"
    )
    assert argv[-2:] == (
        IMAGE_REF,
        "/usr/local/bin/qea-sandbox-supervisor",
    )
    for name, value in _labels(spec).items():
        assert ("--label", f"{name}={value}") in _option_pairs(argv, "--label")
    assert handle == _handle(spec)


def test_create_rejects_non_docker_image_identity() -> None:
    backend = _backend(RecordingRunner())
    with pytest.raises(RootlessDockerError, match="Docker image"):
        backend.create(
            _spec(image_ref="e2b-template:qfbench-worker-historical-var-v3")
        )


def test_start_checks_handle_ownership_before_starting() -> None:
    runner = RecordingRunner(
        _inspect_reply(),
        CompletedCommand(0, b"container-exact-1\n", b""),
    )
    backend = _backend(runner)

    backend.start(_handle())

    assert runner.calls[0].argv[-1] == "container-exact-1"
    assert runner.calls[1].argv == (
        "docker",
        "--host",
        DOCKER_HOST,
        "start",
        "container-exact-1",
    )


def test_proxy_start_connects_internal_network_before_starting() -> None:
    spec = _spec(
        role="proxy",
        network_policy="proxy-outbound",
        environment={"QEA_ROLE": "proxy"},
    )
    runner = RecordingRunner(
        _inspect_reply(spec),
        CompletedCommand(0, b"", b""),
        CompletedCommand(0, b"container-exact-1\n", b""),
    )

    _backend(runner).start(_handle(spec))

    assert runner.calls[1].argv[-6:] == (
        "network",
        "connect",
        "--alias",
        "qea-model-proxy",
        "qea-run-1-internal",
        "container-exact-1",
    )
    assert runner.calls[2].argv[-2:] == ("start", "container-exact-1")


def test_proxy_create_uses_fixed_waiting_entrypoint_without_secret_arguments() -> None:
    runner = RecordingRunner(CompletedCommand(0, b"container-exact-1\n", b""))
    spec = _spec(
        role="proxy",
        network_policy="proxy-outbound",
        environment={},
        writable_tmpfs_mb={"/run/qea-secrets": 1, "/tmp": 64},
    )

    _backend(runner).create(spec)

    argv = runner.calls[0].argv
    assert argv[-2:] == (
        IMAGE_REF,
        "/usr/local/bin/qea-model-proxy-entrypoint",
    )
    assert "token" not in " ".join(argv).lower()


def test_put_uses_exec_tar_for_read_only_tmpfs_and_read_uses_deterministic_tar() -> None:
    read_payload = b"artifact-result"
    runner = RecordingRunner(
        _inspect_reply(),
        CompletedCommand(0, b"", b""),
        _inspect_reply(),
        CompletedCommand(0, _tar_payload("result.json", read_payload), b""),
    )
    backend = _backend(runner)

    backend.put_bytes(_handle(), "/qea/input.json", b"input-data")
    returned = backend.read_bytes(_handle(), "/qea/result.json")

    upload = runner.calls[1]
    assert upload.argv[-9:] == (
        "exec",
        "--interactive",
        "container-exact-1",
        "tar",
        "--extract",
        "--file",
        "-",
        "--directory",
        "/qea",
    )
    assert "cp" not in upload.argv
    with tarfile.open(fileobj=io.BytesIO(upload.input_bytes), mode="r:") as archive:
        member = archive.getmembers()[0]
        assert member.name == "input.json"
        assert member.mtime == 0
        assert archive.extractfile(member).read() == b"input-data"
    assert returned == read_payload
    assert runner.calls[3].argv[-3:] == (
        "cp",
        "container-exact-1:/qea/result.json",
        "-",
    )


@pytest.mark.parametrize("path", ["relative", "/", "/qea/../host", "/qea//x"])
def test_transfer_rejects_unsafe_container_paths(path: str) -> None:
    backend = _backend(RecordingRunner())
    with pytest.raises(RootlessDockerError, match="container path"):
        backend.put_bytes(_handle(), path, b"payload")


def test_run_keeps_task_text_as_one_argv_item_and_returns_task_exit() -> None:
    hostile = "$(touch /tmp/host-pwned); echo value"
    runner = RecordingRunner(
        _inspect_reply(),
        CompletedCommand(23, b"task stdout", b"task stderr"),
    )
    backend = _backend(runner)

    result = backend.run(
        _handle(),
        ("python3", "-c", hostile),
        environment={"QEA_MODE": "test"},
        timeout_seconds=30,
    )

    argv = runner.calls[1].argv
    assert argv[-3:] == ("python3", "-c", hostile)
    assert result.exit_code == 23
    assert result.stdout == "task stdout"
    assert result.stderr == "task stderr"
    assert result.timed_out is False


def test_run_rejects_secret_environment_before_inspection() -> None:
    runner = RecordingRunner()
    with pytest.raises(RootlessDockerError, match="environment"):
        _backend(runner).run(
            _handle(),
            ("python3", "worker.py"),
            environment={"OPENAI_API_KEY": "sk-live-value"},
            timeout_seconds=7,
        )
    assert runner.calls == []


def test_run_converts_host_timeout_but_not_daemon_control_failure() -> None:
    timeout_runner = RecordingRunner(
        _inspect_reply(),
        CommandTimedOut(stdout=b"partial", stderr=b"deadline"),
    )
    timed_out = _backend(timeout_runner).run(
        _handle(),
        ("python3", "worker.py"),
        environment={},
        timeout_seconds=7,
    )
    assert timed_out.exit_code == 124
    assert timed_out.stdout == "partial"
    assert timed_out.stderr == "deadline"
    assert timed_out.timed_out is True

    daemon_runner = RecordingRunner(
        _inspect_reply(),
        CompletedCommand(1, b"", b"Error response from daemon: container stopped"),
    )
    with pytest.raises(RootlessDockerError, match="control-plane"):
        _backend(daemon_runner).run(
            _handle(),
            ("python3", "worker.py"),
            environment={},
            timeout_seconds=7,
        )


def test_kill_refuses_unowned_container_and_removes_owned_exact_id() -> None:
    wrong_labels = _labels()
    wrong_labels["qea.managed"] = "false"
    refusing_runner = RecordingRunner(_inspect_reply(labels=wrong_labels))
    with pytest.raises(RootlessDockerError, match="ownership"):
        _backend(refusing_runner).kill("container-exact-1")
    assert len(refusing_runner.calls) == 1

    runner = RecordingRunner(
        _inspect_reply(),
        CompletedCommand(0, b"container-exact-1\n", b""),
    )
    result = _backend(runner).kill("container-exact-1")
    assert result.outcome == "killed"
    assert runner.calls[1].argv[-3:] == ("rm", "--force", "container-exact-1")


def test_kill_returns_absent_only_for_exact_docker_not_found() -> None:
    runner = RecordingRunner(
        CompletedCommand(1, b"", b"Error: No such object: container-exact-1")
    )
    result = _backend(runner).kill("container-exact-1")
    assert result.outcome == "already_absent"
    assert len(runner.calls) == 1


def test_list_requires_managed_filter_and_returns_exact_inspected_states() -> None:
    backend = _backend(RecordingRunner())
    with pytest.raises(RootlessDockerError, match="managed label"):
        backend.list({"qea.run-id": "run-1"})

    runner = RecordingRunner(
        CompletedCommand(0, b"container-exact-1\n", b""),
        _inspect_reply(),
    )
    states = _backend(runner).list(
        {"qea.managed": "true", "qea.run-id": "run-1"}
    )
    assert len(states) == 1
    assert states[0].native_id == "container-exact-1"
    assert ("--filter", "label=qea.managed=true") in _option_pairs(
        runner.calls[0].argv, "--filter"
    )


def test_internal_network_create_and_remove_require_qea_identity() -> None:
    create_runner = RecordingRunner(CompletedCommand(0, b"network-id\n", b""))
    backend = _backend(create_runner)
    assert backend.create_internal_network("run-1") == "qea-run-1-internal"
    create_argv = create_runner.calls[0].argv
    assert "--internal" in create_argv
    assert ("--label", "qea.managed=true") in _option_pairs(create_argv, "--label")
    assert create_argv[-1] == "qea-run-1-internal"

    network_payload = {
        "Name": "qea-run-1-internal",
        "Labels": {
            "qea.managed": "true",
            "qea.backend": "rootless-docker",
            "qea.run-id": "run-1",
            "qea.network-policy": "internal",
        },
    }
    remove_runner = RecordingRunner(
        CompletedCommand(0, json.dumps(network_payload).encode(), b""),
        CompletedCommand(0, b"qea-run-1-internal\n", b""),
    )
    assert _backend(remove_runner).remove_internal_network("run-1") is True
    assert remove_runner.calls[1].argv[-3:] == (
        "network",
        "rm",
        "qea-run-1-internal",
    )

    network_payload["Labels"]["qea.run-id"] = "other-run"
    refusing_runner = RecordingRunner(
        CompletedCommand(0, json.dumps(network_payload).encode(), b"")
    )
    with pytest.raises(RootlessDockerError, match="network ownership"):
        _backend(refusing_runner).remove_internal_network("run-1")
    assert len(refusing_runner.calls) == 1


def test_subprocess_runner_preserves_argument_boundaries_and_reports_timeout() -> None:
    runner = SubprocessCommandRunner()
    result = runner.run(
        (sys.executable, "-c", "import sys; print(sys.argv[1])", "; echo host"),
        timeout_seconds=5,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == b"; echo host"

    with pytest.raises(CommandTimedOut):
        runner.run(
            (sys.executable, "-c", "import time; time.sleep(2)"),
            timeout_seconds=0.01,
        )


def _option_pair(argv: tuple[str, ...], option: str) -> tuple[str, str]:
    index = argv.index(option)
    return argv[index], argv[index + 1]


def _option_pairs(argv: tuple[str, ...], option: str) -> set[tuple[str, str]]:
    return {
        (value, argv[index + 1])
        for index, value in enumerate(argv[:-1])
        if value == option
    }
