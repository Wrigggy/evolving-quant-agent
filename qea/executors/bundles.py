"""Build deterministic worker and verifier archives with disjoint inputs."""

from __future__ import annotations

import hashlib
import io
import tarfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable


DEFAULT_MAX_FILES = 2_000
DEFAULT_MAX_BYTES = 512 * 1024 * 1024
_SKIP_PARTS = frozenset({".git"})


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


def _tree_files(root: Path, *, skip_cache: bool = True) -> tuple[Path, ...]:
    if not root.is_dir():
        raise BundleError(f"bundle root is not a directory: {root}")
    files: list[Path] = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if (
            any(part in _SKIP_PARTS for part in relative.parts)
            or (skip_cache and "__pycache__" in relative.parts)
            or path.name == ".DS_Store"
        ):
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
    for source in _tree_files(artifact_root, skip_cache=False):
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


def build_evolver_input_bundle(
    candidate_dir: str | Path,
    evidence_dir: str | Path,
    evolver_dir: str | Path,
    destination: str | Path,
    *,
    forbidden_values: Iterable[str] = (),
    max_files: int = DEFAULT_MAX_FILES,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> BundleRecord:
    """Archive only the candidate, authorized evidence, and evolver assets."""

    roots = (
        (Path(candidate_dir).resolve(), "candidate"),
        (Path(evidence_dir).resolve(), "evidence"),
        (Path(evolver_dir).resolve(), "evolve_agent"),
    )
    entries: list[tuple[Path, str]] = []
    forbidden = tuple(
        value.encode() for value in forbidden_values if isinstance(value, str) and value
    )
    for root, prefix in roots:
        for source in _tree_files(root):
            relative = source.relative_to(root)
            payload = source.read_bytes()
            if any(secret in payload for secret in forbidden):
                raise BundleError(
                    f"forbidden value found in evolver bundle member: "
                    f"{prefix}/{relative.as_posix()}"
                )
            entries.append((source, f"{prefix}/{relative.as_posix()}"))
    return _build_bundle(
        entries,
        destination,
        max_files=max_files,
        max_bytes=max_bytes,
    )


def extract_candidate_archive(
    payload: bytes,
    destination: str | Path,
    *,
    max_files: int = DEFAULT_MAX_FILES,
    max_bytes: int = 64 * 1024 * 1024,
) -> tuple[Path, ...]:
    """Extract regular candidate files without traversal, links, or secrets."""

    root = Path(destination).resolve()
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise BundleError(f"candidate output directory is not empty: {root}")
    try:
        archive = tarfile.open(fileobj=io.BytesIO(payload), mode="r:*")
    except tarfile.TarError as exc:
        raise BundleError(f"invalid candidate archive: {exc}") from exc
    extracted: list[Path] = []
    total_bytes = 0
    seen: set[str] = set()
    with archive:
        for member in archive.getmembers():
            if member.isdir():
                continue
            try:
                name = _safe_name(member.name)
            except BundleError as exc:
                raise BundleError(
                    f"unsafe candidate member {member.name!r}"
                ) from exc
            if not member.isfile():
                raise BundleError(f"unsafe candidate member {member.name!r}")
            if name in seen:
                raise BundleError(f"duplicate candidate member {name!r}")
            seen.add(name)
            if len(seen) > max_files:
                raise BundleError(
                    f"candidate file limit exceeded: {len(seen)} > {max_files}"
                )
            total_bytes += member.size
            if total_bytes > max_bytes:
                raise BundleError(
                    f"candidate byte limit exceeded: {total_bytes} > {max_bytes}"
                )
            target = (root / Path(*PurePosixPath(name).parts)).resolve()
            try:
                target.relative_to(root)
            except ValueError as exc:
                raise BundleError(
                    f"unsafe candidate member {member.name!r}"
                ) from exc
            target.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                raise BundleError(f"cannot read candidate member {name!r}")
            with target.open("wb") as handle:
                handle.write(source.read())
            extracted.append(target)
    return tuple(
        sorted(extracted, key=lambda path: path.relative_to(root).as_posix())
    )
