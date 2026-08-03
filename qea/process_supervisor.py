"""Own one coordinator process group and publish bounded exit evidence."""

from __future__ import annotations

import hashlib
import json
import os
import re
import signal
import stat
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from .qfbench_boundary import BoundaryError, read_process_snapshot


_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_CONFIG_FIELDS = frozenset(
    {
        "schema_version",
        "run_id",
        "source_commit",
        "argv",
        "cwd",
        "environment",
        "state_dir",
        "run_dir",
        "expected_child_command_sha256",
        "termination_grace_seconds",
    }
)


class SupervisorError(RuntimeError):
    """A coordinator process group cannot be supervised safely."""


def _atomic_bytes(path: Path, payload: bytes, *, mode=0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(path.suffix + ".tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = None
    try:
        descriptor = os.open(temporary, flags, mode)
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb", closefd=True) as output:
            descriptor = None
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        os.chmod(path, mode)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary.exists():
            temporary.unlink()


def _atomic_json(path: Path, payload: Mapping[str, object]) -> None:
    _atomic_bytes(
        path,
        json.dumps(payload, sort_keys=True, indent=2).encode() + b"\n",
    )


@dataclass(frozen=True)
class ChildIdentity:
    pid: int
    process_group_id: int
    uid: int
    start_ticks: int
    command_sha256: str
    run_id: str
    source_commit: str

    def __post_init__(self) -> None:
        for name in ("pid", "process_group_id", "start_ticks"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise SupervisorError(f"child {name} must be positive")
        if type(self.uid) is not int or self.uid < 0:
            raise SupervisorError("child uid must be non-negative")
        if not isinstance(self.command_sha256, str) or not _SHA256.fullmatch(
            self.command_sha256
        ):
            raise SupervisorError("child command digest is invalid")
        if not isinstance(self.run_id, str) or not _RUN_ID.fullmatch(self.run_id):
            raise SupervisorError("child run_id is invalid")
        if not isinstance(self.source_commit, str) or not _COMMIT.fullmatch(
            self.source_commit
        ):
            raise SupervisorError("child source_commit is invalid")

    def to_dict(self) -> dict[str, int | str]:
        return {
            "pid": self.pid,
            "process_group_id": self.process_group_id,
            "uid": self.uid,
            "start_ticks": self.start_ticks,
            "command_sha256": self.command_sha256,
            "run_id": self.run_id,
            "source_commit": self.source_commit,
        }

    @classmethod
    def from_dict(cls, payload: object) -> "ChildIdentity":
        if not isinstance(payload, dict) or set(payload) != {
            "pid",
            "process_group_id",
            "uid",
            "start_ticks",
            "command_sha256",
            "run_id",
            "source_commit",
        }:
            raise SupervisorError("child identity schema is invalid")
        return cls(**payload)


@dataclass(frozen=True)
class SupervisorConfig:
    run_id: str
    source_commit: str
    argv: tuple[str, ...]
    cwd: Path | str
    environment: Mapping[str, str]
    state_dir: Path | str
    run_dir: Path | str
    expected_child_command_sha256: str
    termination_grace_seconds: float = 30.0

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, str) or not _RUN_ID.fullmatch(self.run_id):
            raise SupervisorError("run_id is invalid")
        if not isinstance(self.source_commit, str) or not _COMMIT.fullmatch(
            self.source_commit
        ):
            raise SupervisorError("source_commit is invalid")
        argv = tuple(self.argv)
        if not argv or any(
            not isinstance(value, str) or not value or "\x00" in value
            for value in argv
        ):
            raise SupervisorError("argv must contain exact non-empty strings")
        if not isinstance(self.environment, Mapping) or any(
            not isinstance(key, str)
            or not key
            or not isinstance(value, str)
            or "\x00" in key
            or "\x00" in value
            for key, value in self.environment.items()
        ):
            raise SupervisorError("environment must contain exact strings")
        cwd = Path(self.cwd).resolve()
        run_dir = Path(self.run_dir).resolve()
        state_dir = Path(self.state_dir).resolve()
        if not cwd.is_dir():
            raise SupervisorError("cwd is unavailable")
        if not run_dir.is_dir() or run_dir.name != self.run_id:
            raise SupervisorError("run_dir is unavailable or mismatched")
        if state_dir == run_dir or state_dir.is_relative_to(run_dir):
            raise SupervisorError("state_dir must be separate from run evidence")
        if not isinstance(self.expected_child_command_sha256, str) or not (
            _SHA256.fullmatch(self.expected_child_command_sha256)
        ):
            raise SupervisorError("expected child command digest is invalid")
        if (
            isinstance(self.termination_grace_seconds, bool)
            or not isinstance(self.termination_grace_seconds, (int, float))
            or not 0.05 <= float(self.termination_grace_seconds) <= 300
        ):
            raise SupervisorError("termination grace must be between 0.05 and 300")
        object.__setattr__(self, "argv", argv)
        object.__setattr__(self, "cwd", cwd)
        object.__setattr__(self, "run_dir", run_dir)
        object.__setattr__(self, "state_dir", state_dir)
        object.__setattr__(
            self, "environment", MappingProxyType(dict(self.environment))
        )
        object.__setattr__(
            self,
            "termination_grace_seconds",
            float(self.termination_grace_seconds),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "run_id": self.run_id,
            "source_commit": self.source_commit,
            "argv": list(self.argv),
            "cwd": str(self.cwd),
            "environment": dict(self.environment),
            "state_dir": str(self.state_dir),
            "run_dir": str(self.run_dir),
            "expected_child_command_sha256": self.expected_child_command_sha256,
            "termination_grace_seconds": self.termination_grace_seconds,
        }


def load_supervisor_config(path: str | Path) -> SupervisorConfig:
    """Load one exact owner-only mode-600 supervisor configuration."""

    config_path = Path(path)
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(config_path, flags)
    except OSError as exc:
        raise SupervisorError("supervisor config is unavailable or a symlink") from exc
    with os.fdopen(descriptor, "rb", closefd=True) as source:
        metadata = os.fstat(source.fileno())
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.geteuid()
            or stat.S_IMODE(metadata.st_mode) != 0o600
        ):
            raise SupervisorError("supervisor config must be owner mode 600")
        raw = source.read(4 * 1024 * 1024 + 1)
    if len(raw) > 4 * 1024 * 1024:
        raise SupervisorError("supervisor config exceeds its byte bound")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SupervisorError("supervisor config is not valid JSON") from exc
    if not isinstance(payload, dict) or set(payload) != _CONFIG_FIELDS:
        raise SupervisorError("supervisor config schema is invalid")
    if payload.get("schema_version") != 1:
        raise SupervisorError("supervisor config schema is unsupported")
    try:
        return SupervisorConfig(
            run_id=payload["run_id"],
            source_commit=payload["source_commit"],
            argv=tuple(payload["argv"]),
            cwd=payload["cwd"],
            environment=payload["environment"],
            state_dir=payload["state_dir"],
            run_dir=payload["run_dir"],
            expected_child_command_sha256=payload[
                "expected_child_command_sha256"
            ],
            termination_grace_seconds=payload["termination_grace_seconds"],
        )
    except (KeyError, TypeError) as exc:
        raise SupervisorError("supervisor config field types are invalid") from exc


def _child_start_identity(child: subprocess.Popen) -> tuple[int, int]:
    try:
        snapshot = read_process_snapshot(child.pid)
        return snapshot.identity.uid, snapshot.identity.start_ticks
    except (BoundaryError, ProcessLookupError):
        # Non-Linux test/development hosts lack /proc. Production bc is Linux.
        return os.geteuid(), time.monotonic_ns()


def _group_alive(process_group_id: int) -> bool:
    try:
        os.killpg(process_group_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _terminate_group(
    process_group_id: int,
    *,
    first_signal: int,
    grace_seconds: float,
) -> None:
    if not _group_alive(process_group_id):
        return
    try:
        os.killpg(process_group_id, first_signal)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + grace_seconds
    while _group_alive(process_group_id) and time.monotonic() < deadline:
        time.sleep(0.02)
    if _group_alive(process_group_id):
        try:
            os.killpg(process_group_id, signal.SIGKILL)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + max(grace_seconds, 1.0)
    while _group_alive(process_group_id) and time.monotonic() < deadline:
        time.sleep(0.02)
    if _group_alive(process_group_id):
        raise SupervisorError(
            f"process group {process_group_id} remains alive after SIGKILL"
        )


def _resume_complete(config: SupervisorConfig) -> bool:
    path = config.run_dir / "resume.json"
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return False
    return bool(
        isinstance(payload, dict)
        and payload.get("run_id") == config.run_id
        and payload.get("phase") == "complete"
    )


def run_supervised(config: SupervisorConfig) -> int:
    """Run and completely reap one new-session coordinator process group."""

    if not isinstance(config, SupervisorConfig):
        raise SupervisorError("config must be a SupervisorConfig")
    config.state_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
    os.chmod(config.state_dir, 0o700)
    _atomic_bytes(
        config.state_dir / "supervisor-pid", f"{os.getpid()}\n".encode()
    )
    log_path = config.state_dir / "failure.log"
    requested_signal: list[int] = []

    def request_stop(signum, frame):
        if not requested_signal:
            requested_signal.append(signum)

    previous = {
        signum: signal.signal(signum, request_stop)
        for signum in (signal.SIGTERM, signal.SIGINT)
    }
    child = None
    exit_code = 127
    try:
        with log_path.open("wb") as log_handle:
            os.chmod(log_path, 0o600)
            child = subprocess.Popen(
                config.argv,
                cwd=config.cwd,
                stdin=subprocess.DEVNULL,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                close_fds=True,
                env=dict(config.environment),
            )
            process_group_id = os.getpgid(child.pid)
            if process_group_id != child.pid:
                raise SupervisorError("child is not the process-group leader")
            uid, start_ticks = _child_start_identity(child)
            identity = ChildIdentity(
                pid=child.pid,
                process_group_id=process_group_id,
                uid=uid,
                start_ticks=start_ticks,
                command_sha256=config.expected_child_command_sha256,
                run_id=config.run_id,
                source_commit=config.source_commit,
            )
            _atomic_json(config.state_dir / "child-identity.json", identity.to_dict())
            _atomic_bytes(config.state_dir / "child-pid", f"{child.pid}\n".encode())

            forwarded = False
            while child.poll() is None:
                if requested_signal and not forwarded:
                    forwarded = True
                    try:
                        os.killpg(process_group_id, requested_signal[0])
                    except ProcessLookupError:
                        pass
                    deadline = time.monotonic() + config.termination_grace_seconds
                if forwarded and time.monotonic() >= deadline:
                    try:
                        os.killpg(process_group_id, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                time.sleep(0.02)
            exit_code = child.wait()
            _terminate_group(
                process_group_id,
                first_signal=signal.SIGTERM,
                grace_seconds=config.termination_grace_seconds,
            )
    except BaseException as exc:
        if child is not None:
            try:
                process_group_id = os.getpgid(child.pid)
            except ProcessLookupError:
                process_group_id = child.pid
            _terminate_group(
                process_group_id,
                first_signal=signal.SIGTERM,
                grace_seconds=config.termination_grace_seconds,
            )
            try:
                exit_code = child.wait(timeout=1)
            except subprocess.TimeoutExpired:
                exit_code = 127
        with log_path.open("ab") as log_handle:
            message = f"supervisor failure: {type(exc).__name__}: {exc}\n"
            log_handle.write(message.encode("utf-8", errors="replace")[:4096])
        if isinstance(exc, SupervisorError):
            raise
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)

    _atomic_bytes(config.state_dir / "exit-code", f"{exit_code}\n".encode())
    if exit_code == 0 and _resume_complete(config):
        _atomic_json(
            config.state_dir / "completion.json",
            {"run_id": config.run_id, "status": "complete"},
        )
    elif (config.run_dir / "boundary-migrated.json").is_file():
        _atomic_json(
            config.state_dir / "boundary-stopped.json",
            {"run_id": config.run_id, "status": "boundary_stopped"},
        )
    return exit_code


__all__ = [
    "ChildIdentity",
    "SupervisorConfig",
    "SupervisorError",
    "load_supervisor_config",
    "run_supervised",
]
