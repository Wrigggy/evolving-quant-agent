"""Compatibility adapter for the narrow E2B SDK surface used by QEA."""

from __future__ import annotations

import base64
import json
import shlex
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Mapping, Sequence

from ..executors.e2b_protocol import E2BSandbox, E2BSandboxFactory, SDKSandboxFactory
from ..sandbox_backend import (
    KillResult,
    SandboxCommandResult,
    SandboxHandle,
    SandboxSpec,
    SandboxSpecError,
    SandboxState,
    validate_sandbox_environment,
)


_TEMPLATE_PREFIX = "e2b-template:"
_REMOTE_EXEC_CODE = (
    "import base64,json,os,subprocess,sys;"
    "payload=json.loads(base64.b64decode(sys.argv[1]));"
    "environment=os.environ.copy();"
    "environment.update(payload['environment']);"
    "result=subprocess.run(payload['argv'],env=environment,capture_output=True);"
    "sys.stdout.buffer.write(result.stdout);"
    "sys.stderr.buffer.write(result.stderr);"
    "raise SystemExit(result.returncode)"
)


class E2BSandboxBackendError(RuntimeError):
    """An E2B compatibility operation violates the neutral contract."""


class E2BBackendCapabilityError(E2BSandboxBackendError):
    """The installed narrow E2B SDK cannot prove an account-wide operation."""


@dataclass(frozen=True)
class _LiveSandbox:
    handle: SandboxHandle
    sandbox: E2BSandbox


def _safe_path(value: str) -> str:
    if not isinstance(value, str):
        raise E2BSandboxBackendError(f"unsafe E2B path: {value!r}")
    path = PurePosixPath(value)
    if (
        not path.is_absolute()
        or value == "/"
        or path.as_posix() != value
        or any(part in {"", ".", ".."} for part in path.parts[1:])
    ):
        raise E2BSandboxBackendError(f"unsafe E2B path: {value!r}")
    return value


class E2BSandboxBackend:
    """Expose known in-process E2B sandboxes without guessing account state."""

    backend_name = "e2b"
    supports_list = False

    def __init__(
        self,
        *,
        sandbox_factory: E2BSandboxFactory | None = None,
    ) -> None:
        self.sandbox_factory = sandbox_factory or SDKSandboxFactory()
        self._live: dict[str, _LiveSandbox] = {}

    def create(self, spec: SandboxSpec) -> SandboxHandle:
        if not spec.image_ref.startswith(_TEMPLATE_PREFIX):
            raise E2BSandboxBackendError(
                f"E2B backend requires an E2B template identity: {spec.image_ref!r}"
            )
        if spec.network_policy != "none":
            raise E2BSandboxBackendError(
                "E2B compatibility adapter requires an explicit SDK network policy "
                "for internet-enabled sandboxes"
            )
        template_id = spec.image_ref.removeprefix(_TEMPLATE_PREFIX)
        try:
            sandbox = self.sandbox_factory.create(
                template=template_id,
                timeout=spec.timeout_seconds,
                metadata={
                    "qea_role": spec.role,
                    "qea_run_id": spec.run_id,
                    "qea_attempt_id": spec.attempt_id,
                    "qea_task_id": spec.task_id,
                    "qea_spec_sha256": spec.spec_sha256,
                },
                envs=dict(spec.environment),
                secure=True,
                allow_internet_access=False,
            )
        except Exception as exc:  # noqa: BLE001 - normalize SDK boundary.
            raise E2BSandboxBackendError(
                f"E2B sandbox creation failed: {type(exc).__name__}: {exc}"
            ) from exc
        native_id = str(getattr(sandbox, "sandbox_id", ""))
        if not native_id or any(character.isspace() for character in native_id):
            try:
                sandbox.kill()
            finally:
                raise E2BSandboxBackendError("E2B returned no valid native sandbox ID")
        if native_id in self._live:
            try:
                sandbox.kill()
            finally:
                raise E2BSandboxBackendError(
                    f"duplicate live E2B sandbox ID: {native_id!r}"
                )
        handle = SandboxHandle(
            backend=self.backend_name,
            native_id=native_id,
            immutable_image_ref=spec.image_ref,
            spec_sha256=spec.spec_sha256,
        )
        self._live[native_id] = _LiveSandbox(handle=handle, sandbox=sandbox)
        return handle

    def _known(self, handle: SandboxHandle) -> E2BSandbox:
        live = self._live.get(handle.native_id)
        if live is None or live.handle != handle:
            raise E2BSandboxBackendError(
                f"unknown or mismatched E2B sandbox handle: {handle.native_id!r}"
            )
        return live.sandbox

    def start(self, handle: SandboxHandle) -> None:
        self._known(handle)

    def put_bytes(
        self,
        handle: SandboxHandle,
        path: str,
        payload: bytes,
    ) -> None:
        safe_path = _safe_path(path)
        if not isinstance(payload, bytes):
            raise E2BSandboxBackendError("E2B upload payload must be bytes")
        sandbox = self._known(handle)
        sandbox.files.write(safe_path, payload)

    def read_bytes(self, handle: SandboxHandle, path: str) -> bytes:
        safe_path = _safe_path(path)
        sandbox = self._known(handle)
        payload = sandbox.files.read(safe_path, format="bytes")
        if isinstance(payload, bytes):
            return payload
        if isinstance(payload, bytearray):
            return bytes(payload)
        raise E2BSandboxBackendError(
            f"E2B byte read returned {type(payload).__name__}"
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
            raise E2BSandboxBackendError(
                "E2B command must be a non-empty argv sequence"
            )
        if type(timeout_seconds) is not int or timeout_seconds <= 0:
            raise E2BSandboxBackendError("E2B command timeout must be positive")
        try:
            safe_environment = validate_sandbox_environment(environment)
        except SandboxSpecError as exc:
            raise E2BSandboxBackendError(
                f"unsafe E2B command environment: {exc}"
            ) from exc
        sandbox = self._known(handle)
        payload = base64.b64encode(
            json.dumps(
                {
                    "argv": list(argv),
                    "environment": dict(safe_environment),
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).decode("ascii")
        command = f"python3 -c {shlex.quote(_REMOTE_EXEC_CODE)} {payload}"
        try:
            result = sandbox.commands.run(command, timeout=timeout_seconds)
        except TimeoutError as exc:
            return SandboxCommandResult(
                exit_code=124,
                stdout="",
                stderr=str(exc),
                timed_out=True,
            )
        return SandboxCommandResult(
            exit_code=int(getattr(result, "exit_code", -1)),
            stdout=str(getattr(result, "stdout", "") or ""),
            stderr=str(getattr(result, "stderr", "") or ""),
            timed_out=False,
        )

    def inspect(self, native_id: str) -> SandboxState | None:
        raise E2BBackendCapabilityError(
            "E2B inspect is unavailable through the installed narrow SDK"
        )

    def list(self, labels: Mapping[str, str]) -> Sequence[SandboxState]:
        raise E2BBackendCapabilityError(
            "E2B list is unavailable through the installed narrow SDK"
        )

    def kill(self, native_id: str) -> KillResult:
        live = self._live.get(native_id)
        if live is None:
            raise E2BBackendCapabilityError(
                f"unknown E2B sandbox cannot be guessed absent: {native_id!r}"
            )
        try:
            live.sandbox.kill()
        except Exception as exc:  # noqa: BLE001 - normalize SDK boundary.
            raise E2BSandboxBackendError(
                f"E2B exact kill failed: {type(exc).__name__}: {exc}"
            ) from exc
        del self._live[native_id]
        return KillResult(native_id=native_id, outcome="killed")
