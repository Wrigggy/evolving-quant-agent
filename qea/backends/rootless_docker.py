"""Rootless Docker implementation of the provider-neutral sandbox contract."""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import subprocess
import tarfile
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Mapping, Protocol, Sequence

from ..sandbox_backend import (
    KillOutcome,
    KillResult,
    SandboxCommandResult,
    SandboxHandle,
    SandboxNetworkHandle,
    SandboxSpec,
    SandboxSpecError,
    SandboxState,
    validate_sandbox_environment,
)


_DOCKER_IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}\Z")
_DOCKER_DIGEST_REF = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9._:/-]*@sha256:[0-9a-f]{64}\Z"
)
_NATIVE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
_NETWORK_SCOPE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
_NETWORK_IDENTITY = re.compile(r"[0-9a-f]{64}\Z")
_DOCKER_CONTAINER_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,254}\Z")
_DOCKER_NETWORK_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,254}\Z")
_ALLOWED_FILTER_LABELS = frozenset(
    {
        "qea.managed",
        "qea.backend",
        "qea.role",
        "qea.run-id",
        "qea.attempt-id",
        "qea.task-id",
        "qea.spec-sha256",
    }
)
_MAX_ERROR_BYTES = 16 * 1024
_DEFAULT_MAX_COMMAND_OUTPUT_BYTES = 2 * 1024 * 1024
_DEFAULT_MAX_TRANSFER_BYTES = 512 * 1024 * 1024
_SANDBOX_SUPERVISOR = "/usr/local/bin/qea-sandbox-supervisor"
_MODEL_PROXY_ENTRYPOINT = "/usr/local/bin/qea-model-proxy-entrypoint"


class RootlessDockerError(RuntimeError):
    """A Docker control-plane operation or ownership check failed."""


@dataclass(frozen=True)
class CompletedCommand:
    returncode: int
    stdout: bytes
    stderr: bytes


@dataclass(frozen=True)
class RootlessDockerPreflight:
    """Measured daemon and immutable-image identity for one coordinator."""

    docker_host: str
    actual_uid: int
    server_version: str
    security_options: tuple[str, ...]
    image_ids: tuple[str, ...]
    identity_sha256: str

    @classmethod
    def measured(
        cls,
        *,
        docker_host: str,
        actual_uid: int,
        server_version: str,
        security_options: tuple[str, ...],
        image_ids: tuple[str, ...],
    ) -> "RootlessDockerPreflight":
        payload = {
            "schema_version": 1,
            "docker_host": docker_host,
            "actual_uid": actual_uid,
            "server_version": server_version,
            "security_options": list(security_options),
            "image_ids": list(image_ids),
        }
        identity = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return cls(
            docker_host=docker_host,
            actual_uid=actual_uid,
            server_version=server_version,
            security_options=security_options,
            image_ids=image_ids,
            identity_sha256=identity,
        )


class CommandTimedOut(TimeoutError):
    """A shell-free host command exceeded its deadline."""

    def __init__(self, *, stdout: bytes = b"", stderr: bytes = b"") -> None:
        super().__init__("command timed out")
        self.stdout = stdout
        self.stderr = stderr


class CommandRunner(Protocol):
    def run(
        self,
        argv: Sequence[str],
        *,
        input_bytes: bytes | None = None,
        timeout_seconds: int | float | None = None,
    ) -> CompletedCommand:
        raise NotImplementedError


class SubprocessCommandRunner:
    """Execute exact argv sequences without a host shell."""

    def run(
        self,
        argv: Sequence[str],
        *,
        input_bytes: bytes | None = None,
        timeout_seconds: int | float | None = None,
    ) -> CompletedCommand:
        try:
            result = subprocess.run(
                tuple(argv),
                shell=False,
                input=input_bytes,
                capture_output=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise CommandTimedOut(
                stdout=_as_bytes(exc.stdout),
                stderr=_as_bytes(exc.stderr),
            ) from exc
        return CompletedCommand(
            returncode=result.returncode,
            stdout=_as_bytes(result.stdout),
            stderr=_as_bytes(result.stderr),
        )


def _as_bytes(value: object) -> bytes:
    if value is None:
        return b""
    if isinstance(value, bytes):
        return value
    return str(value).encode("utf-8", errors="replace")


def _bounded_text(payload: bytes, limit: int) -> str:
    clipped = payload[:limit]
    text = clipped.decode("utf-8", errors="replace")
    if len(payload) > limit:
        text += "\n[TRUNCATED]"
    return text


def _is_not_found(stderr: bytes) -> bool:
    lowered = stderr.decode("utf-8", errors="replace").lower()
    return (
        "no such object:" in lowered
        or "no such container:" in lowered
        or "no such network:" in lowered
        or (
            "error response from daemon: network " in lowered
            and " not found" in lowered
        )
    )


def _is_control_plane_error(stderr: bytes) -> bool:
    lowered = stderr.decode("utf-8", errors="replace").lstrip().lower()
    return lowered.startswith("error response from daemon:") or lowered.startswith(
        "docker: error"
    )


def _safe_container_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if (
        not isinstance(value, str)
        or not path.is_absolute()
        or value == "/"
        or path.as_posix() != value
        or any(part in {"", ".", ".."} for part in path.parts[1:])
    ):
        raise RootlessDockerError(f"unsafe container path: {value!r}")
    return path


def _safe_native_id(value: str) -> str:
    if not isinstance(value, str) or _NATIVE_ID.fullmatch(value) is None:
        raise RootlessDockerError(f"invalid Docker native ID: {value!r}")
    return value


def _safe_run_id(value: str) -> str:
    if not isinstance(value, str) or _RUN_ID.fullmatch(value) is None:
        raise RootlessDockerError(f"invalid run ID: {value!r}")
    return value


def _safe_network_scope(value: str) -> str:
    if not isinstance(value, str) or _NETWORK_SCOPE.fullmatch(value) is None:
        raise RootlessDockerError(f"invalid network scope: {value!r}")
    return value


def _safe_network_name(value: str) -> str:
    if not isinstance(value, str) or _DOCKER_NETWORK_NAME.fullmatch(value) is None:
        raise RootlessDockerError(f"invalid Docker network name: {value!r}")
    return value


def _container_name(spec: SandboxSpec) -> str:
    logical_identity = hashlib.sha256(
        (
            "qea-rootless-container-v1\x00"
            f"{spec.role}\x00{spec.run_id}\x00{spec.attempt_id}"
        ).encode("utf-8")
    ).hexdigest()
    name = f"qea-{spec.role}-{logical_identity}"
    if _DOCKER_CONTAINER_NAME.fullmatch(name) is None:
        raise RootlessDockerError(f"invalid Docker container name: {name!r}")
    return name


def _network_identity_sha256(run_id: str, network_scope: str | None) -> str:
    scope_value = "" if network_scope is None else network_scope
    return hashlib.sha256(f"{run_id}\x00{scope_value}".encode("utf-8")).hexdigest()


def _tar_single_file(name: str, payload: bytes) -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w", format=tarfile.PAX_FORMAT) as archive:
        info = tarfile.TarInfo(name=name)
        info.size = len(payload)
        info.mtime = 0
        info.uid = 0
        info.gid = 0
        info.uname = ""
        info.gname = ""
        info.mode = 0o600
        archive.addfile(info, io.BytesIO(payload))
    return output.getvalue()


def _read_single_file_tar(
    payload: bytes,
    *,
    expected_name: str,
    max_bytes: int,
) -> bytes:
    if len(payload) > max_bytes + 1024 * 1024:
        raise RootlessDockerError("Docker transfer archive exceeds byte limit")
    try:
        archive = tarfile.open(fileobj=io.BytesIO(payload), mode="r:*")
    except tarfile.TarError as exc:
        raise RootlessDockerError(f"invalid Docker transfer archive: {exc}") from exc
    with archive:
        members = [member for member in archive.getmembers() if not member.isdir()]
        if len(members) != 1:
            raise RootlessDockerError("Docker transfer archive must contain one file")
        member = members[0]
        member_path = PurePosixPath(member.name)
        if (
            not member.isfile()
            or member_path.name != expected_name
            or any(part in {"", ".", ".."} for part in member_path.parts)
            or member.size > max_bytes
        ):
            raise RootlessDockerError("unsafe Docker transfer archive member")
        extracted = archive.extractfile(member)
        if extracted is None:
            raise RootlessDockerError("Docker transfer archive member is unreadable")
        result = extracted.read(max_bytes + 1)
        if len(result) > max_bytes:
            raise RootlessDockerError("Docker transfer payload exceeds byte limit")
        return result


class RootlessDockerBackend:
    """Create and control QEA-owned containers through one rootless socket."""

    backend_name = "rootless-docker"

    def __init__(
        self,
        *,
        docker_host: str,
        expected_uid: int | None = None,
        runner: CommandRunner | None = None,
        max_command_output_bytes: int = _DEFAULT_MAX_COMMAND_OUTPUT_BYTES,
        max_transfer_bytes: int = _DEFAULT_MAX_TRANSFER_BYTES,
    ) -> None:
        uid = os.getuid() if expected_uid is None else expected_uid
        expected_host = f"unix:///run/user/{uid}/docker.sock"
        if docker_host != expected_host:
            if docker_host == "unix:///var/run/docker.sock":
                detail = "system Docker socket is forbidden"
            else:
                detail = f"expected rootless Docker socket {expected_host!r}"
            raise RootlessDockerError(f"unsafe Docker endpoint {docker_host!r}: {detail}")
        if type(max_command_output_bytes) is not int or max_command_output_bytes <= 0:
            raise RootlessDockerError("max_command_output_bytes must be positive")
        if type(max_transfer_bytes) is not int or max_transfer_bytes <= 0:
            raise RootlessDockerError("max_transfer_bytes must be positive")
        self.docker_host = docker_host
        self.expected_uid = uid
        self.runner = runner or SubprocessCommandRunner()
        self.max_command_output_bytes = max_command_output_bytes
        self.max_transfer_bytes = max_transfer_bytes

    def preflight(
        self,
        *,
        expected_server_version: str,
        expected_security_options: Sequence[str],
        image_ids: Sequence[str],
    ) -> RootlessDockerPreflight:
        """Measure and require the exact rootless daemon and selected images."""

        actual_uid = os.getuid()
        if actual_uid != self.expected_uid:
            raise RootlessDockerError(
                "rootless Docker UID identity differs from the coordinator"
            )
        if (
            not isinstance(expected_server_version, str)
            or not expected_server_version
            or len(expected_server_version) > 128
            or any(
                ord(character) < 0x21 or ord(character) > 0x7E
                for character in expected_server_version
            )
        ):
            raise RootlessDockerError("expected Docker server identity is invalid")
        if isinstance(expected_security_options, (str, bytes)):
            raise RootlessDockerError("expected Docker security identity is invalid")
        raw_expected_security = tuple(expected_security_options)
        if (
            not raw_expected_security
            or any(
                not isinstance(value, str) or not value
                for value in raw_expected_security
            )
        ):
            raise RootlessDockerError("expected Docker rootless identity is invalid")
        expected_security = tuple(sorted(raw_expected_security))
        if "name=rootless" not in expected_security:
            raise RootlessDockerError("expected Docker rootless identity is invalid")
        if isinstance(image_ids, (str, bytes)):
            raise RootlessDockerError("selected image identity set is invalid")
        raw_image_ids = tuple(image_ids)
        if not raw_image_ids or any(
            not isinstance(value, str) or _DOCKER_IMAGE_ID.fullmatch(value) is None
            for value in raw_image_ids
        ):
            raise RootlessDockerError("selected image identity set is invalid")
        selected_images = tuple(sorted(set(raw_image_ids)))

        version = self._checked(
            ("version", "--format", "{{.Server.Version}}"),
            timeout_seconds=30,
            operation="server version preflight",
        ).stdout.decode("utf-8", errors="replace").strip()
        if version != expected_server_version:
            raise RootlessDockerError(
                "active Docker server version identity differs from image builds"
            )
        security_raw = self._checked(
            ("info", "--format", "{{json .SecurityOptions}}"),
            timeout_seconds=30,
            operation="security preflight",
        ).stdout
        if len(security_raw) > 64 * 1024:
            raise RootlessDockerError("active Docker security identity is oversized")
        try:
            decoded_security = json.loads(security_raw)
        except json.JSONDecodeError as exc:
            raise RootlessDockerError(
                "active Docker security identity is malformed"
            ) from exc
        if not isinstance(decoded_security, list) or any(
            not isinstance(value, str) or not value for value in decoded_security
        ):
            raise RootlessDockerError("active Docker security identity is malformed")
        measured_security = tuple(sorted(decoded_security))
        if (
            "name=rootless" not in measured_security
            or measured_security != expected_security
        ):
            raise RootlessDockerError(
                "active Docker rootless security identity differs from image builds"
            )
        for image_id in selected_images:
            observed = self._checked(
                ("image", "inspect", "--format", "{{.Id}}", image_id),
                timeout_seconds=30,
                operation="selected image preflight",
            ).stdout.decode("utf-8", errors="replace").strip()
            if observed != image_id:
                raise RootlessDockerError(
                    f"selected Docker image identity differs for {image_id}"
                )
        return RootlessDockerPreflight.measured(
            docker_host=self.docker_host,
            actual_uid=actual_uid,
            server_version=version,
            security_options=measured_security,
            image_ids=selected_images,
        )

    def _argv(self, *arguments: str) -> tuple[str, ...]:
        return ("docker", "--host", self.docker_host, *arguments)

    def _checked(
        self,
        arguments: Sequence[str],
        *,
        input_bytes: bytes | None = None,
        timeout_seconds: int | float | None = None,
        operation: str,
    ) -> CompletedCommand:
        try:
            result = self.runner.run(
                self._argv(*arguments),
                input_bytes=input_bytes,
                timeout_seconds=timeout_seconds,
            )
        except CommandTimedOut:
            raise
        if result.returncode != 0:
            error = _bounded_text(result.stderr, _MAX_ERROR_BYTES)
            raise RootlessDockerError(f"Docker {operation} failed: {error}")
        return result

    def create(self, spec: SandboxSpec) -> SandboxHandle:
        if not (
            _DOCKER_IMAGE_ID.fullmatch(spec.image_ref)
            or _DOCKER_DIGEST_REF.fullmatch(spec.image_ref)
        ):
            raise RootlessDockerError(
                f"rootless backend requires an immutable Docker image: {spec.image_ref!r}"
            )
        labels = {
            "qea.managed": "true",
            "qea.backend": self.backend_name,
            "qea.role": spec.role,
            "qea.run-id": spec.run_id,
            "qea.attempt-id": spec.attempt_id,
            "qea.task-id": spec.task_id,
            "qea.spec-sha256": spec.spec_sha256,
            "qea.network-scope-mode": (
                "legacy" if spec.network_scope is None else "scoped"
            ),
        }
        if spec.network_scope is not None:
            labels["qea.network-scope"] = spec.network_scope
        if spec.network_policy == "none":
            network = "none"
        elif spec.network_policy == "worker-proxy-only":
            network = self._internal_network_name(
                spec.run_id,
                spec.network_scope,
            )
        else:
            network = "bridge"
        arguments: list[str] = [
            "create",
            "--name",
            _container_name(spec),
        ]
        for name, value in sorted(labels.items()):
            arguments.extend(("--label", f"{name}={value}"))
        arguments.extend(
            (
                "--cpus",
                str(spec.cpu_count),
                "--memory",
                f"{spec.memory_mb}m",
                "--memory-swap",
                f"{spec.memory_mb}m",
                "--pids-limit",
                str(spec.pids_limit),
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--network",
                network,
            )
        )
        for path, size_mb in spec.writable_tmpfs_mb.items():
            executable = "exec" if path in spec.executable_tmpfs_paths else "noexec"
            arguments.extend(
                (
                    "--tmpfs",
                    f"{path}:rw,nosuid,nodev,{executable},size={size_mb}m",
                )
            )
        for name, value in spec.environment.items():
            arguments.extend(("--env", f"{name}={value}"))
        entrypoint = (
            _MODEL_PROXY_ENTRYPOINT if spec.role == "proxy" else _SANDBOX_SUPERVISOR
        )
        arguments.extend((spec.image_ref, entrypoint))
        result = self._checked(
            arguments,
            timeout_seconds=60,
            operation="container create",
        )
        native_id = _safe_native_id(
            result.stdout.decode("utf-8", errors="replace").strip()
        )
        return SandboxHandle(
            backend=self.backend_name,
            native_id=native_id,
            immutable_image_ref=spec.image_ref,
            spec_sha256=spec.spec_sha256,
        )

    def start(self, handle: SandboxHandle) -> None:
        state = self._require_handle_ownership(handle)
        if state.labels.get("qea.role") == "proxy":
            run_id = state.labels.get("qea.run-id", "")
            network_scope = state.labels.get("qea.network-scope")
            scope_mode = state.labels.get("qea.network-scope-mode")
            if scope_mode == "scoped" and network_scope is None:
                raise RootlessDockerError(
                    "scoped proxy is missing its network scope label"
                )
            if scope_mode == "legacy" and network_scope is not None:
                raise RootlessDockerError(
                    "legacy proxy has an unexpected network scope label"
                )
            if scope_mode not in {None, "legacy", "scoped"}:
                raise RootlessDockerError(
                    f"proxy has an invalid network scope mode: {scope_mode!r}"
                )
            network_name = self._internal_network_name(run_id, network_scope)
            result = self.runner.run(
                self._argv(
                    "network",
                    "connect",
                    "--alias",
                    "qea-model-proxy",
                    network_name,
                    handle.native_id,
                ),
                timeout_seconds=30,
            )
            already_connected = b"already exists in network" in result.stderr.lower()
            if result.returncode != 0 and not already_connected:
                raise RootlessDockerError(
                    "Docker network connect failed: "
                    + _bounded_text(result.stderr, _MAX_ERROR_BYTES)
                )
        self._checked(
            ("start", handle.native_id),
            timeout_seconds=30,
            operation="container start",
        )

    def put_bytes(
        self,
        handle: SandboxHandle,
        path: str,
        payload: bytes,
    ) -> None:
        container_path = _safe_container_path(path)
        if not isinstance(payload, bytes):
            raise RootlessDockerError("sandbox upload payload must be bytes")
        if len(payload) > self.max_transfer_bytes:
            raise RootlessDockerError("sandbox upload exceeds byte limit")
        self._require_handle_ownership(handle)
        archive = _tar_single_file(container_path.name, payload)
        self._checked(
            (
                "exec",
                "--interactive",
                handle.native_id,
                "tar",
                "--extract",
                "--file",
                "-",
                "--directory",
                container_path.parent.as_posix(),
            ),
            input_bytes=archive,
            timeout_seconds=120,
            operation="container upload",
        )

    def read_bytes(self, handle: SandboxHandle, path: str) -> bytes:
        container_path = _safe_container_path(path)
        self._require_handle_ownership(handle)
        result = self._checked(
            (
                "exec",
                handle.native_id,
                "tar",
                "--create",
                "--file",
                "-",
                "--directory",
                container_path.parent.as_posix(),
                "--",
                container_path.name,
            ),
            timeout_seconds=120,
            operation="container download",
        )
        return _read_single_file_tar(
            result.stdout,
            expected_name=container_path.name,
            max_bytes=self.max_transfer_bytes,
        )

    def run(
        self,
        handle: SandboxHandle,
        argv: Sequence[str],
        *,
        environment: Mapping[str, str],
        timeout_seconds: int,
    ) -> SandboxCommandResult:
        if (
            isinstance(argv, (str, bytes))
            or not argv
            or any(
                not isinstance(value, str) or not value or "\x00" in value
                for value in argv
            )
        ):
            raise RootlessDockerError("sandbox command must be a non-empty argv sequence")
        if type(timeout_seconds) is not int or timeout_seconds <= 0:
            raise RootlessDockerError("sandbox command timeout must be positive")
        try:
            safe_environment = validate_sandbox_environment(environment)
        except SandboxSpecError as exc:
            raise RootlessDockerError(f"unsafe sandbox command environment: {exc}") from exc
        self._require_handle_ownership(handle)
        arguments: list[str] = ["exec"]
        for name, value in safe_environment.items():
            arguments.extend(("--env", f"{name}={value}"))
        arguments.append(handle.native_id)
        arguments.extend(argv)
        try:
            result = self.runner.run(
                self._argv(*arguments),
                timeout_seconds=timeout_seconds,
            )
        except CommandTimedOut as exc:
            return SandboxCommandResult(
                exit_code=124,
                stdout=_bounded_text(exc.stdout, self.max_command_output_bytes),
                stderr=_bounded_text(exc.stderr, self.max_command_output_bytes),
                timed_out=True,
            )
        if result.returncode != 0 and _is_control_plane_error(result.stderr):
            raise RootlessDockerError(
                "Docker exec control-plane failure: "
                + _bounded_text(result.stderr, _MAX_ERROR_BYTES)
            )
        return SandboxCommandResult(
            exit_code=result.returncode,
            stdout=_bounded_text(result.stdout, self.max_command_output_bytes),
            stderr=_bounded_text(result.stderr, self.max_command_output_bytes),
            timed_out=False,
        )

    def inspect(self, native_id: str) -> SandboxState | None:
        safe_id = _safe_native_id(native_id)
        result = self.runner.run(
            self._argv(
                "container",
                "inspect",
                "--format",
                "{{json .}}",
                safe_id,
            ),
            timeout_seconds=30,
        )
        if result.returncode != 0:
            if _is_not_found(result.stderr):
                return None
            raise RootlessDockerError(
                "Docker container inspect failed: "
                + _bounded_text(result.stderr, _MAX_ERROR_BYTES)
            )
        try:
            payload = json.loads(result.stdout)
            config = payload["Config"]
            state = payload["State"]
            labels = config.get("Labels") or {}
            image_ref = config["Image"]
            inspected_id = payload["Id"]
            status = state["Status"]
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise RootlessDockerError("malformed Docker container inspect output") from exc
        if inspected_id != safe_id:
            raise RootlessDockerError("Docker inspect returned a different native ID")
        if not isinstance(labels, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in labels.items()
        ):
            raise RootlessDockerError("Docker inspect returned malformed labels")
        return SandboxState(
            backend=self.backend_name,
            native_id=safe_id,
            status=str(status),
            labels=labels,
            immutable_image_ref=str(image_ref),
        )

    def list(self, labels: Mapping[str, str]) -> Sequence[SandboxState]:
        if labels.get("qea.managed") != "true":
            raise RootlessDockerError(
                "container list requires managed label qea.managed=true"
            )
        for name, value in labels.items():
            if name not in _ALLOWED_FILTER_LABELS or not isinstance(value, str) or not value:
                raise RootlessDockerError(f"unsafe Docker label filter: {name!r}")
            if any(character in value for character in ("\x00", "\n", "\r", "=")):
                raise RootlessDockerError(f"unsafe Docker label value for {name!r}")
        arguments: list[str] = [
            "container",
            "ls",
            "--all",
            "--quiet",
            "--no-trunc",
        ]
        for name, value in sorted(labels.items()):
            arguments.extend(("--filter", f"label={name}={value}"))
        result = self._checked(
            arguments,
            timeout_seconds=30,
            operation="container list",
        )
        states: list[SandboxState] = []
        for raw_id in result.stdout.decode("utf-8", errors="replace").splitlines():
            native_id = _safe_native_id(raw_id.strip())
            state = self.inspect(native_id)
            if state is not None and all(
                state.labels.get(name) == value for name, value in labels.items()
            ):
                states.append(state)
        return tuple(states)

    def kill(self, native_id: str) -> KillResult:
        safe_id = _safe_native_id(native_id)
        state = self.inspect(safe_id)
        if state is None:
            return KillResult(native_id=safe_id, outcome="already_absent")
        if (
            state.labels.get("qea.managed") != "true"
            or state.labels.get("qea.backend") != self.backend_name
        ):
            raise RootlessDockerError(
                f"container ownership check failed for {safe_id!r}"
            )
        result = self.runner.run(
            self._argv("container", "rm", "--force", safe_id),
            timeout_seconds=30,
        )
        if result.returncode != 0:
            if _is_not_found(result.stderr):
                return KillResult(native_id=safe_id, outcome="already_absent")
            raise RootlessDockerError(
                "Docker container kill failed: "
                + _bounded_text(result.stderr, _MAX_ERROR_BYTES)
            )
        return KillResult(native_id=safe_id, outcome="killed")

    def _require_handle_ownership(self, handle: SandboxHandle) -> SandboxState:
        if handle.backend != self.backend_name:
            raise RootlessDockerError("sandbox handle names a different backend")
        state = self.inspect(handle.native_id)
        if state is None:
            raise RootlessDockerError(f"sandbox is absent: {handle.native_id!r}")
        if (
            state.labels.get("qea.managed") != "true"
            or state.labels.get("qea.backend") != self.backend_name
            or state.labels.get("qea.spec-sha256") != handle.spec_sha256
            or state.immutable_image_ref != handle.immutable_image_ref
        ):
            raise RootlessDockerError(
                f"sandbox handle ownership check failed for {handle.native_id!r}"
            )
        return state

    def _internal_network_name(
        self,
        run_id: str,
        network_scope: str | None = None,
    ) -> str:
        safe_run_id = _safe_run_id(run_id)
        if network_scope is None:
            return _safe_network_name(f"qea-{safe_run_id}-internal")
        safe_scope = _safe_network_scope(network_scope)
        identity = _network_identity_sha256(run_id, network_scope)
        suffix = f"-{identity[:12]}-internal"
        readable = f"qea-{safe_run_id}-{safe_scope}"
        bounded = readable[: 255 - len(suffix)]
        return _safe_network_name(f"{bounded}{suffix}")

    def _internal_network_labels(
        self,
        *,
        run_id: str,
        network_scope: str | None,
        identity_sha256: str,
    ) -> dict[str, str]:
        labels = {
            "qea.managed": "true",
            "qea.backend": self.backend_name,
            "qea.run-id": run_id,
            "qea.network-policy": "internal",
            "qea.network-identity-sha256": identity_sha256,
        }
        if network_scope is not None:
            labels["qea.network-scope"] = network_scope
        return labels

    def _inspect_internal_network(
        self,
        reference: str,
    ) -> tuple[str, str, Mapping[str, str]] | None:
        safe_reference = _safe_network_name(reference)
        result = self.runner.run(
            self._argv(
                "network",
                "inspect",
                "--format",
                "{{json .}}",
                safe_reference,
            ),
            timeout_seconds=30,
        )
        if result.returncode != 0:
            if _is_not_found(result.stderr):
                return None
            raise RootlessDockerError(
                "Docker network inspect failed: "
                + _bounded_text(result.stderr, _MAX_ERROR_BYTES)
            )
        try:
            payload = json.loads(result.stdout)
            native_id = _safe_native_id(payload["Id"])
            name = _safe_network_name(payload["Name"])
            labels = payload.get("Labels") or {}
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise RootlessDockerError(
                "malformed Docker network inspect output"
            ) from exc
        if not isinstance(labels, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in labels.items()
        ):
            raise RootlessDockerError("Docker network inspect returned malformed labels")
        return native_id, name, labels

    def _require_internal_network_identity(
        self,
        inspected: tuple[str, str, Mapping[str, str]],
        *,
        native_id: str,
        name: str,
        labels: Mapping[str, str],
    ) -> None:
        inspected_id, inspected_name, inspected_labels = inspected
        if (
            inspected_id != native_id
            or inspected_name != name
            or any(
                inspected_labels.get(key) != value
                for key, value in labels.items()
            )
        ):
            raise RootlessDockerError(
                f"network ownership check failed for {native_id!r}"
            )

    def create_internal_network(
        self,
        run_id: str,
        *,
        network_scope: str | None = None,
    ) -> SandboxNetworkHandle | str:
        """Create a scoped network, retaining the legacy positional run API."""

        safe_run_id = _safe_run_id(run_id)
        safe_scope = (
            None
            if network_scope is None
            else _safe_network_scope(network_scope)
        )
        identity = _network_identity_sha256(run_id, network_scope)
        name = self._internal_network_name(run_id, network_scope)
        labels = self._internal_network_labels(
            run_id=safe_run_id,
            network_scope=safe_scope,
            identity_sha256=identity,
        )
        arguments: list[str] = ["network", "create", "--internal"]
        for key, value in sorted(labels.items()):
            arguments.extend(("--label", f"{key}={value}"))
        arguments.append(name)
        result = self._checked(
            arguments,
            timeout_seconds=30,
            operation="internal network create",
        )
        native_id = _safe_native_id(
            result.stdout.decode("utf-8", errors="replace").strip()
        )
        inspected = self._inspect_internal_network(native_id)
        if inspected is None:
            raise RootlessDockerError(
                f"created Docker network is absent: {native_id!r}"
            )
        self._require_internal_network_identity(
            inspected,
            native_id=native_id,
            name=name,
            labels=labels,
        )
        if safe_scope is None:
            return name
        return SandboxNetworkHandle(
            backend=self.backend_name,
            native_id=native_id,
            name=name,
            run_id=safe_run_id,
            network_scope=safe_scope,
            identity_sha256=identity,
        )

    def _remove_internal_network_by_id(self, native_id: str) -> KillOutcome:
        safe_id = _safe_native_id(native_id)
        result = self.runner.run(
            self._argv("network", "rm", safe_id),
            timeout_seconds=30,
        )
        if result.returncode != 0:
            if _is_not_found(result.stderr):
                return "already_absent"
            raise RootlessDockerError(
                "Docker internal network removal failed: "
                + _bounded_text(result.stderr, _MAX_ERROR_BYTES)
            )
        return "killed"

    def _remove_legacy_internal_network(self, run_id: str) -> bool:
        safe_run_id = _safe_run_id(run_id)
        name = self._internal_network_name(run_id)
        identity = _network_identity_sha256(run_id, None)
        inspected = self._inspect_internal_network(name)
        if inspected is None:
            return False
        native_id, _, inspected_labels = inspected
        required_labels = self._internal_network_labels(
            run_id=safe_run_id,
            network_scope=None,
            identity_sha256=identity,
        )
        if "qea.network-identity-sha256" not in inspected_labels:
            required_labels.pop("qea.network-identity-sha256")
        if "qea.network-scope" in inspected_labels:
            raise RootlessDockerError(
                f"network ownership check failed for {native_id!r}"
            )
        self._require_internal_network_identity(
            inspected,
            native_id=native_id,
            name=name,
            labels=required_labels,
        )
        return self._remove_internal_network_by_id(native_id) == "killed"

    def inspect_internal_network(
        self,
        handle: SandboxNetworkHandle,
    ) -> bool:
        """Return presence only after validating the complete network handle."""

        if not isinstance(handle, SandboxNetworkHandle):
            raise RootlessDockerError("invalid sandbox network handle")
        if handle.backend != self.backend_name:
            raise RootlessDockerError("network handle names a different backend")
        native_id = _safe_native_id(handle.native_id)
        safe_run_id = _safe_run_id(handle.run_id)
        safe_scope = _safe_network_scope(handle.network_scope)
        if _NETWORK_IDENTITY.fullmatch(handle.identity_sha256) is None:
            raise RootlessDockerError("network handle has an invalid identity digest")
        expected_identity = _network_identity_sha256(
            handle.run_id,
            handle.network_scope,
        )
        expected_name = self._internal_network_name(
            handle.run_id,
            handle.network_scope,
        )
        if (
            handle.identity_sha256 != expected_identity
            or handle.name != expected_name
        ):
            raise RootlessDockerError("network handle identity check failed")
        inspected = self._inspect_internal_network(native_id)
        if inspected is None:
            return False
        self._require_internal_network_identity(
            inspected,
            native_id=native_id,
            name=expected_name,
            labels=self._internal_network_labels(
                run_id=safe_run_id,
                network_scope=safe_scope,
                identity_sha256=expected_identity,
            ),
        )
        return True

    def remove_internal_network(
        self,
        handle: SandboxNetworkHandle | str,
    ) -> KillOutcome | bool:
        """Remove only the exact recorded network, with legacy run compatibility."""

        if isinstance(handle, str):
            return self._remove_legacy_internal_network(handle)
        if not self.inspect_internal_network(handle):
            return "already_absent"
        return self._remove_internal_network_by_id(
            _safe_native_id(handle.native_id)
        )
