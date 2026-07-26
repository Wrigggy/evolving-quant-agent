"""Build deterministic worker and verifier archives with disjoint inputs."""

from __future__ import annotations

import hashlib
import tarfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable


DEFAULT_MAX_FILES = 2_000
DEFAULT_MAX_BYTES = 512 * 1024 * 1024
_SKIP_PARTS = frozenset({".git", "__pycache__"})


class BundleError(ValueError):
    """A bundle contains an unsafe path, secret-like file, or exceeds a limit."""


@dataclass(frozen=True)
class BundleRecord:
    path: Path
    sha256: str
    size_bytes: int
    payload_bytes: int
    members: tuple[str, ...]


def _is_secret_like(path: PurePosixPath) -> bool:
    name = path.name.lower()
    return (
        name == ".env"
        or name.startswith(".env.")
        or name.startswith("credentials")
        or name.startswith("secrets")
        or name in {"id_rsa", "id_ed25519"}
        or name.endswith((".pem", ".key"))
    )


def _safe_name(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise BundleError(f"unsafe archive path {value!r}")
    if _is_secret_like(path):
        raise BundleError(f"secret-like file is forbidden in bundle: {value}")
    return path.as_posix()


def _tree_files(root: Path) -> tuple[Path, ...]:
    if not root.is_dir():
        raise BundleError(f"bundle root is not a directory: {root}")
    files: list[Path] = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if any(part in _SKIP_PARTS for part in relative.parts) or path.name == ".DS_Store":
            continue
        if path.is_symlink():
            raise BundleError(f"symlinks are forbidden in bundles: {path}")
        if path.is_file():
            files.append(path.resolve())
    return tuple(sorted(files, key=lambda path: path.relative_to(root.resolve()).as_posix()))


def _relative_to(path: Path, root: Path, label: str) -> Path:
    resolved = path.resolve()
    try:
        return resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise BundleError(f"{label} file is outside its declared root: {path}") from exc


def _build_bundle(
    entries: Iterable[tuple[Path, str]],
    destination: str | Path,
    *,
    max_files: int,
    max_bytes: int,
) -> BundleRecord:
    normalized: list[tuple[Path, str]] = []
    seen: set[str] = set()
    payload_bytes = 0
    for source, archive_name in entries:
        if source.is_symlink() or not source.is_file():
            raise BundleError(f"bundle source is not a regular file: {source}")
        safe_name = _safe_name(archive_name)
        if safe_name in seen:
            raise BundleError(f"duplicate archive member {safe_name}")
        seen.add(safe_name)
        payload_bytes += source.stat().st_size
        normalized.append((source, safe_name))

    normalized.sort(key=lambda item: item[1])
    if len(normalized) > max_files:
        raise BundleError(f"bundle file limit exceeded: {len(normalized)} > {max_files}")
    if payload_bytes > max_bytes:
        raise BundleError(f"bundle byte limit exceeded: {payload_bytes} > {max_bytes}")

    target = Path(destination).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(target, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for source, archive_name in normalized:
            info = tarfile.TarInfo(name=archive_name)
            info.size = source.stat().st_size
            info.mtime = 0
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mode = 0o755 if source.suffix == ".sh" else 0o644
            with source.open("rb") as handle:
                archive.addfile(info, handle)
    payload = target.read_bytes()
    return BundleRecord(
        path=target,
        sha256=hashlib.sha256(payload).hexdigest(),
        size_bytes=len(payload),
        payload_bytes=payload_bytes,
        members=tuple(name for _, name in normalized),
    )


def build_worker_bundle(
    task,
    worker_dir: str | Path,
    destination: str | Path,
    *,
    max_files: int = DEFAULT_MAX_FILES,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> BundleRecord:
    """Archive only public task files and the candidate NexAU worker snapshot."""

    task_root = Path(task.root).resolve()
    worker_root = Path(worker_dir).resolve()
    entries: list[tuple[Path, str]] = []
    for source in task.worker_files:
        relative = _relative_to(Path(source), task_root, "worker task")
        if relative.parts[0] in {"tests", "solution"}:
            raise BundleError(f"worker file crosses evaluator firewall: {relative}")
        entries.append((Path(source).resolve(), f"task/{relative.as_posix()}"))
    for source in _tree_files(worker_root):
        relative = source.relative_to(worker_root)
        entries.append((source, f"worker/{relative.as_posix()}"))
    return _build_bundle(entries, destination, max_files=max_files, max_bytes=max_bytes)


def build_verifier_bundle(
    task,
    artifacts_dir: str | Path,
    destination: str | Path,
    *,
    max_files: int = DEFAULT_MAX_FILES,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> BundleRecord:
    """Archive hidden official tests with immutable worker-produced artifacts."""

    task_root = Path(task.root).resolve()
    artifact_root = Path(artifacts_dir).resolve()
    entries: list[tuple[Path, str]] = []
    for source in task.verifier_files:
        relative = _relative_to(Path(source), task_root, "verifier")
        if not relative.parts or relative.parts[0] != "tests":
            raise BundleError(f"verifier file must live below tests/: {relative}")
        entries.append((Path(source).resolve(), relative.as_posix()))
    for source in _tree_files(artifact_root):
        relative = source.relative_to(artifact_root)
        entries.append((source, f"artifacts/{relative.as_posix()}"))
    return _build_bundle(entries, destination, max_files=max_files, max_bytes=max_bytes)


def build_oracle_bundle(
    task,
    destination: str | Path,
    *,
    max_files: int = DEFAULT_MAX_FILES,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> BundleRecord:
    """Archive the trusted oracle separately; it is never a worker input."""

    task_root = Path(task.root).resolve()
    solution_root = task_root / "solution"
    solution_files = _tree_files(solution_root)
    if not solution_files:
        raise BundleError(f"task {task.task_id!r} has no oracle solution files")
    entries: list[tuple[Path, str]] = []
    for source in task.worker_files:
        relative = _relative_to(Path(source), task_root, "oracle task")
        if relative.parts[0] in {"tests", "solution"}:
            raise BundleError(f"oracle public file crosses firewall: {relative}")
        entries.append((Path(source).resolve(), f"task/{relative.as_posix()}"))
    for source in solution_files:
        relative = source.relative_to(solution_root)
        entries.append((source, f"solution/{relative.as_posix()}"))
    return _build_bundle(entries, destination, max_files=max_files, max_bytes=max_bytes)
