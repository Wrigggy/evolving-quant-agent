"""Bounded bridge from NexAU's Python 3.12 process to task Python 3.11."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path, PurePosixPath
from typing import Iterable


class TaskPythonBridgeError(RuntimeError):
    """The task-Python call is unsafe, timed out, or exceeded its output contract."""


def _resolve_cwd(cwd: Path, allowed_root: Path) -> Path:
    root = allowed_root.resolve()
    work = cwd.resolve()
    try:
        work.relative_to(root)
    except ValueError as exc:
        raise TaskPythonBridgeError(
            f"task Python cwd is outside allowed root {root}: {work}"
        ) from exc
    if not work.is_dir():
        raise TaskPythonBridgeError(f"task Python cwd does not exist: {work}")
    return work


def _validate_argv(argv: Iterable[str], cwd: Path) -> tuple[str, ...]:
    normalized = tuple(argv)
    if not normalized or any(not isinstance(item, str) or not item for item in normalized):
        raise TaskPythonBridgeError("task Python argv must contain non-empty strings")
    if any("\x00" in item for item in normalized):
        raise TaskPythonBridgeError("task Python argv contains NUL")
    first = normalized[0]
    if first.startswith("-"):
        if first not in {"-c", "-m"}:
            raise TaskPythonBridgeError(f"unsupported task Python argv mode {first!r}")
        return normalized
    script = PurePosixPath(first)
    if script.is_absolute() or any(part in {"", ".", ".."} for part in script.parts):
        raise TaskPythonBridgeError(f"task Python script path escapes cwd: {first!r}")
    resolved = (cwd / Path(*script.parts)).resolve()
    try:
        resolved.relative_to(cwd)
    except ValueError as exc:
        raise TaskPythonBridgeError(f"task Python script path escapes cwd: {first!r}") from exc
    return normalized


def task_python(
    argv: Iterable[str],
    *,
    cwd: str | Path,
    timeout_seconds: int,
    max_output_bytes: int = 1024 * 1024,
    python_executable: str = "/usr/local/bin/python3",
    allowed_root: str | Path = "/app",
) -> dict:
    """Execute a task-runtime Python argv without a shell or inherited secrets."""

    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int) \
            or timeout_seconds < 1:
        raise TaskPythonBridgeError("task Python timeout must be a positive integer")
    if isinstance(max_output_bytes, bool) or not isinstance(max_output_bytes, int) \
            or max_output_bytes < 1:
        raise TaskPythonBridgeError("task Python output limit must be positive")
    executable = Path(python_executable)
    if not executable.is_absolute():
        raise TaskPythonBridgeError("task Python executable must be absolute")
    work = _resolve_cwd(Path(cwd), Path(allowed_root))
    arguments = _validate_argv(argv, work)
    environment = {
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8"),
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
    }
    try:
        completed = subprocess.run(
            [str(executable), *arguments],
            cwd=work,
            env=environment,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise TaskPythonBridgeError(
            f"task Python process timed out after {timeout_seconds}s"
        ) from exc
    stdout = completed.stdout or b""
    stderr = completed.stderr or b""
    if len(stdout) + len(stderr) > max_output_bytes:
        raise TaskPythonBridgeError(
            "task Python output limit exceeded: "
            f"{len(stdout) + len(stderr)} > {max_output_bytes}"
        )
    return {
        "exit_code": int(completed.returncode),
        "stdout": stdout.decode("utf-8", errors="replace"),
        "stderr": stderr.decode("utf-8", errors="replace"),
    }
