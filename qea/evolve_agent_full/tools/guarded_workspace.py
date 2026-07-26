"""Capability-limited workspace tools for the full-harness evolver.

The evolver may read its immutable evidence corpus and may read/write only the
candidate worker tree.  It never receives a general-purpose shell or Python
execution primitive.
"""

from __future__ import annotations

import importlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any


_ROOT_ENV = {
    "candidate": "QEA_CANDIDATE_ROOT",
    "evidence": "QEA_EVIDENCE_ROOT",
}
_MAX_LISTED_PATHS = 2_000
_MAX_READ_BYTES = 256_000
_MAX_WRITE_BYTES = 512_000
_MAX_SEARCH_FILES = 2_000
_MAX_SEARCH_LINE_BYTES = 8_000
_MAX_PROCESS_OUTPUT_BYTES = 128_000


class GuardedWorkspaceError(ValueError):
    """Raised when an evolver operation violates the workspace contract."""


def _root(source: str) -> Path:
    env_name = _ROOT_ENV.get(source)
    if env_name is None:
        raise GuardedWorkspaceError(f"unknown workspace source: {source!r}")
    raw = os.environ.get(env_name)
    if not raw:
        raise GuardedWorkspaceError(f"required environment variable {env_name} is unset")
    root = Path(raw)
    if not root.is_dir():
        raise GuardedWorkspaceError(f"workspace root does not exist: {source}")
    return root.resolve(strict=True)


def _relative(value: str, *, label: str = "path") -> PurePosixPath:
    if not isinstance(value, str) or not value or "\x00" in value or "\\" in value:
        raise GuardedWorkspaceError(f"unsafe relative {label}: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise GuardedWorkspaceError(f"unsafe relative {label}: {value!r}")
    return path


def _reject_symlinks(root: Path, relative: PurePosixPath) -> None:
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise GuardedWorkspaceError(f"symlink paths are forbidden: {relative}")
        if not current.exists():
            break


def _resolve(source: str, value: str, *, must_exist: bool) -> tuple[Path, str]:
    relative = _relative(value)
    root = _root(source)
    _reject_symlinks(root, relative)
    target = root.joinpath(*relative.parts)
    if must_exist and not target.exists():
        raise GuardedWorkspaceError(f"path does not exist: {relative}")
    resolved = target.resolve(strict=must_exist)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise GuardedWorkspaceError(f"path escapes {source} workspace: {relative}") from exc
    return resolved, relative.as_posix()


def _audit(
    *, operation: str, source: str, relative_path: str, bytes_returned: int = 0
) -> None:
    raw = os.environ.get("QEA_ACCESS_LOG")
    if not raw:
        raise GuardedWorkspaceError("required environment variable QEA_ACCESS_LOG is unset")
    log_path = Path(raw)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "operation": operation,
        "source": source,
        "relative_path": relative_path,
        "bytes_returned": bytes_returned,
    }
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def _read_text(path: Path) -> str:
    if not path.is_file():
        raise GuardedWorkspaceError(f"not a regular file: {path.name}")
    size = path.stat().st_size
    if size > _MAX_READ_BYTES:
        raise GuardedWorkspaceError(
            f"file exceeds {_MAX_READ_BYTES}-byte read limit: {path.name}"
        )
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise GuardedWorkspaceError(f"file is not UTF-8 text: {path.name}") from exc


def list_workspace(source: str, pattern: str = "**/*") -> dict[str, Any]:
    """List regular UTF-8 candidate or evidence files matching a safe glob."""

    relative_pattern = _relative(pattern, label="pattern")
    root = _root(source)
    paths: list[str] = []
    for path in root.glob(relative_pattern.as_posix()):
        relative = path.relative_to(root)
        if path.is_symlink() or not path.is_file():
            continue
        _reject_symlinks(root, PurePosixPath(relative.as_posix()))
        paths.append(relative.as_posix())
        if len(paths) > _MAX_LISTED_PATHS:
            raise GuardedWorkspaceError("workspace listing exceeds path limit")
    paths.sort()
    _audit(
        operation="list",
        source=source,
        relative_path=relative_pattern.as_posix(),
        bytes_returned=sum(len(path.encode("utf-8")) for path in paths),
    )
    return {"paths": paths}


def read_workspace(
    source: str,
    file_path: str,
    start_line: int = 1,
    max_lines: int = 400,
) -> dict[str, Any]:
    """Read a bounded line range from a candidate or evidence text file."""

    if start_line < 1 or not 1 <= max_lines <= 2_000:
        raise GuardedWorkspaceError("start_line must be >= 1 and max_lines must be 1..2000")
    path, relative = _resolve(source, file_path, must_exist=True)
    text = _read_text(path)
    lines = text.splitlines(keepends=True)
    content = "".join(lines[start_line - 1 : start_line - 1 + max_lines])
    _audit(
        operation="read",
        source=source,
        relative_path=relative,
        bytes_returned=len(content.encode("utf-8")),
    )
    return {
        "path": relative,
        "content": content,
        "start_line": start_line,
        "lines_returned": len(content.splitlines()),
        "total_lines": len(lines),
    }


def search_evidence(pattern: str, max_hits: int = 100) -> dict[str, Any]:
    """Search immutable evidence text without exposing another filesystem root."""

    if not isinstance(pattern, str) or not pattern or len(pattern) > 256:
        raise GuardedWorkspaceError("search pattern must contain 1..256 characters")
    if not 1 <= max_hits <= 500:
        raise GuardedWorkspaceError("max_hits must be between 1 and 500")
    try:
        expression = re.compile(pattern, flags=re.IGNORECASE)
    except re.error as exc:
        raise GuardedWorkspaceError(f"invalid search regex: {exc}") from exc

    root = _root("evidence")
    hits: list[dict[str, Any]] = []
    files_seen = 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        _reject_symlinks(root, PurePosixPath(relative))
        files_seen += 1
        if files_seen > _MAX_SEARCH_FILES:
            raise GuardedWorkspaceError("evidence search exceeds file limit")
        try:
            text = _read_text(path)
        except GuardedWorkspaceError:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            if expression.search(line):
                encoded = line.encode("utf-8")[:_MAX_SEARCH_LINE_BYTES]
                hits.append(
                    {
                        "path": relative,
                        "line": line_number,
                        "text": encoded.decode("utf-8", errors="ignore"),
                    }
                )
                if len(hits) >= max_hits:
                    break
        if len(hits) >= max_hits:
            break
    returned = len(json.dumps(hits, ensure_ascii=False).encode("utf-8"))
    _audit(
        operation="search",
        source="evidence",
        relative_path=pattern,
        bytes_returned=returned,
    )
    return {"hits": hits, "truncated": len(hits) >= max_hits}


def write_candidate(file_path: str, content: str) -> dict[str, Any]:
    """Atomically write one UTF-8 file inside the candidate tree."""

    if not isinstance(content, str):
        raise GuardedWorkspaceError("content must be text")
    encoded = content.encode("utf-8")
    if len(encoded) > _MAX_WRITE_BYTES:
        raise GuardedWorkspaceError(f"content exceeds {_MAX_WRITE_BYTES}-byte write limit")
    path, relative = _resolve("candidate", file_path, must_exist=False)
    root = _root("candidate")
    parent_relative = PurePosixPath(relative).parent
    if parent_relative.as_posix() != ".":
        _reject_symlinks(root, parent_relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    _reject_symlinks(root, PurePosixPath(relative))
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temp_path = Path(handle.name)
    try:
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()
    _audit(
        operation="write",
        source="candidate",
        relative_path=relative,
        bytes_returned=0,
    )
    return {"path": relative, "bytes_written": len(encoded)}


def replace_candidate(
    file_path: str,
    old_string: str,
    new_string: str,
    expected_replacements: int = 1,
) -> dict[str, Any]:
    """Replace an exact, expected number of occurrences in a candidate file."""

    if not old_string:
        raise GuardedWorkspaceError("old_string must not be empty")
    if expected_replacements < 1:
        raise GuardedWorkspaceError("expected_replacements must be positive")
    path, relative = _resolve("candidate", file_path, must_exist=True)
    text = _read_text(path)
    actual = text.count(old_string)
    if actual != expected_replacements:
        raise GuardedWorkspaceError(
            f"expected {expected_replacements} replacements, found {actual}"
        )
    write_candidate(relative, text.replace(old_string, new_string))
    _audit(
        operation="replace",
        source="candidate",
        relative_path=relative,
        bytes_returned=0,
    )
    return {"path": relative, "replacements": actual}


def smoke_candidate_tool(
    module: str,
    function: str,
    args_json: str = "{}",
    timeout_seconds: int = 20,
) -> dict[str, Any]:
    """Import and invoke a candidate local tool through a bounded Python argv."""

    if not re.fullmatch(r"tools(?:\.[A-Za-z_][A-Za-z0-9_]*)+", module):
        raise GuardedWorkspaceError("module must be a dotted path below tools")
    if not function.isidentifier() or function.startswith("_"):
        raise GuardedWorkspaceError("function must be a public Python identifier")
    if not 1 <= timeout_seconds <= 120:
        raise GuardedWorkspaceError("timeout_seconds must be between 1 and 120")
    try:
        arguments = json.loads(args_json)
    except json.JSONDecodeError as exc:
        raise GuardedWorkspaceError(f"args_json is invalid JSON: {exc}") from exc
    if not isinstance(arguments, dict):
        raise GuardedWorkspaceError("args_json must decode to an object")

    root = _root("candidate")
    importlib.invalidate_caches()
    runner = (
        "import importlib,json,sys;"
        "m=importlib.import_module(sys.argv[1]);"
        "f=getattr(m,sys.argv[2]);"
        "a=json.loads(sys.argv[3]);"
        "print(json.dumps(f(**a),sort_keys=True,default=str))"
    )
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(root),
        "PYTHONDONTWRITEBYTECODE": "1",
        "LANG": "C.UTF-8",
    }
    try:
        completed = subprocess.run(
            [sys.executable, "-c", runner, module, function, json.dumps(arguments)],
            cwd=root,
            env=env,
            capture_output=True,
            text=False,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise GuardedWorkspaceError(
            f"candidate tool timed out after {timeout_seconds} seconds"
        ) from exc
    stdout = completed.stdout[:_MAX_PROCESS_OUTPUT_BYTES]
    stderr = completed.stderr[:_MAX_PROCESS_OUTPUT_BYTES]
    _audit(
        operation="smoke",
        source="candidate",
        relative_path=f"{module}:{function}",
        bytes_returned=len(stdout) + len(stderr),
    )
    return {
        "exit_code": completed.returncode,
        "stdout": stdout.decode("utf-8", errors="replace"),
        "stderr": stderr.decode("utf-8", errors="replace"),
        "output_truncated": (
            len(completed.stdout) > _MAX_PROCESS_OUTPUT_BYTES
            or len(completed.stderr) > _MAX_PROCESS_OUTPUT_BYTES
        ),
    }

