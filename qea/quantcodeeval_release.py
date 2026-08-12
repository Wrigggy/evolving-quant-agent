"""Content-addressed publisher for a QuantCodeEval engineering release.

The publisher deliberately treats every supplied input as evidence.  It copies
complete regular-file trees into a new release, binds their paths, permission
bits, sizes, and bytes, and never cleans an older partial or negative result.
No network or Docker operation is performed here.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Mapping, Sequence


_SCHEMA_VERSION = 1
_BENCHMARK = "quantcodeeval"
_RELEASE_KIND = "engineering-canary"
_IDENTITY_ALGORITHM = "sha256-canonical-quantcodeeval-release-v1"
_TREE_ALGORITHM = "sha256-canonical-surface-tree-v1"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_SURFACE_ORDER = (
    "source",
    "public",
    "trusted",
    "image",
    "no-model",
    "h0",
    "pgbhs",
)
_REQUIRED_SURFACES = frozenset(_SURFACE_ORDER[:5])
_OPTIONAL_SURFACES = frozenset(_SURFACE_ORDER[5:])
_MANIFEST_NAME = "RELEASE.json"


class QuantCodeEvalReleaseError(ValueError):
    """A release input or published identity is unsafe, incomplete, or drifted."""


@dataclass(frozen=True)
class QuantCodeEvalReleaseResult:
    """Result of publishing or reusing one exact release identity."""

    release_dir: Path
    manifest_path: Path
    identity_sha256: str
    manifest_sha256: str
    file_count: int
    total_bytes: int
    reused_existing: bool


@dataclass(frozen=True)
class _SurfaceInput:
    name: str
    source: Path
    input_kind: str
    root_mode: str | None
    directories: tuple[dict[str, object], ...]
    members: tuple[dict[str, object], ...]
    tree_sha256: str


def _canonical_json_bytes(payload: object, *, compact: bool = False) -> bytes:
    options: dict[str, object] = {
        "ensure_ascii": False,
        "sort_keys": True,
    }
    if compact:
        options["separators"] = (",", ":")
    else:
        options["indent"] = 2
    return (json.dumps(payload, **options) + "\n").encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _mode_string(mode: int) -> str:
    return oct(stat.S_IMODE(mode))


def _safe_relative(value: object) -> str:
    if not isinstance(value, str) or not value or "\x00" in value or "\\" in value:
        raise QuantCodeEvalReleaseError("release member path is unsafe")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or path.as_posix() != value
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise QuantCodeEvalReleaseError(f"release member path is unsafe: {value!r}")
    return value


def _resolved_input(path: str | Path, *, label: str, directory: bool) -> Path:
    unresolved = Path(path).expanduser()
    try:
        metadata = unresolved.lstat()
    except OSError as exc:
        raise QuantCodeEvalReleaseError(f"{label} is unavailable: {unresolved}") from exc
    if stat.S_ISLNK(metadata.st_mode):
        raise QuantCodeEvalReleaseError(f"{label} may not be a symlink")
    expected = stat.S_ISDIR(metadata.st_mode) if directory else stat.S_ISREG(metadata.st_mode)
    if not expected:
        kind = "directory" if directory else "regular file"
        raise QuantCodeEvalReleaseError(f"{label} must be a {kind}")
    return unresolved.resolve()


def _resolved_result(path: str | Path, *, label: str) -> tuple[Path, str]:
    unresolved = Path(path).expanduser()
    try:
        metadata = unresolved.lstat()
    except OSError as exc:
        raise QuantCodeEvalReleaseError(f"{label} is unavailable: {unresolved}") from exc
    if stat.S_ISLNK(metadata.st_mode):
        raise QuantCodeEvalReleaseError(f"{label} may not be a symlink")
    if stat.S_ISDIR(metadata.st_mode):
        return unresolved.resolve(), "directory"
    if stat.S_ISREG(metadata.st_mode):
        return unresolved.resolve(), "file"
    raise QuantCodeEvalReleaseError(f"{label} must be a regular file or directory")


def _read_regular(path: Path, *, label: str) -> tuple[bytes, os.stat_result]:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise QuantCodeEvalReleaseError(f"cannot read regular {label}: {path}") from exc
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise QuantCodeEvalReleaseError(f"{label} is not a regular file: {path}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks), metadata
    finally:
        os.close(descriptor)


def _member(relative: str, path: Path) -> dict[str, object]:
    payload, metadata = _read_regular(path, label="release member")
    return {
        "mode": _mode_string(metadata.st_mode),
        "path": _safe_relative(relative),
        "sha256": _sha256_bytes(payload),
        "size_bytes": len(payload),
    }


def _directory_record(relative: str, path: Path) -> dict[str, object]:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise QuantCodeEvalReleaseError(f"cannot inspect release directory: {path}") from exc
    if stat.S_ISLNK(metadata.st_mode):
        raise QuantCodeEvalReleaseError(f"release symlink is forbidden: {relative}")
    if not stat.S_ISDIR(metadata.st_mode):
        raise QuantCodeEvalReleaseError(f"special release member is forbidden: {relative}")
    return {"mode": _mode_string(metadata.st_mode), "path": _safe_relative(relative)}


def _surface_tree_sha256(
    *,
    name: str,
    input_kind: str,
    root_mode: str | None,
    directories: Sequence[Mapping[str, object]],
    members: Sequence[Mapping[str, object]],
) -> str:
    return _sha256_bytes(
        _canonical_json_bytes(
            {
                "algorithm": _TREE_ALGORITHM,
                "directories": list(directories),
                "input_kind": input_kind,
                "members": list(members),
                "name": name,
                "root_mode": root_mode,
            },
            compact=True,
        )
    )


def _snapshot_directory(name: str, root: Path) -> _SurfaceInput:
    root_metadata = root.lstat()
    directories: list[dict[str, object]] = []
    members: list[dict[str, object]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        try:
            metadata = path.lstat()
        except OSError as exc:
            raise QuantCodeEvalReleaseError(f"cannot inspect {name} member: {relative}") from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise QuantCodeEvalReleaseError(f"release symlink is forbidden: {name}/{relative}")
        if stat.S_ISDIR(metadata.st_mode):
            directories.append(_directory_record(relative, path))
        elif stat.S_ISREG(metadata.st_mode):
            members.append(_member(relative, path))
        else:
            raise QuantCodeEvalReleaseError(
                f"special release member is forbidden: {name}/{relative}"
            )
    if not members:
        raise QuantCodeEvalReleaseError(f"{name} input contains no regular files")
    root_mode = _mode_string(root_metadata.st_mode)
    tree = _surface_tree_sha256(
        name=name,
        input_kind="directory",
        root_mode=root_mode,
        directories=directories,
        members=members,
    )
    return _SurfaceInput(
        name=name,
        source=root,
        input_kind="directory",
        root_mode=root_mode,
        directories=tuple(directories),
        members=tuple(members),
        tree_sha256=tree,
    )


def _snapshot_file(name: str, path: Path) -> _SurfaceInput:
    member = _member("RESULT.json", path)
    tree = _surface_tree_sha256(
        name=name,
        input_kind="file",
        root_mode=None,
        directories=(),
        members=(member,),
    )
    return _SurfaceInput(
        name=name,
        source=path,
        input_kind="file",
        root_mode=None,
        directories=(),
        members=(member,),
        tree_sha256=tree,
    )


def _snapshot_surface(name: str, source: Path, input_kind: str) -> _SurfaceInput:
    if input_kind == "directory":
        return _snapshot_directory(name, source)
    if input_kind == "file":
        return _snapshot_file(name, source)
    raise AssertionError(input_kind)


def _surface_payload(surface: _SurfaceInput) -> dict[str, object]:
    return {
        "directories": list(surface.directories),
        "file_count": len(surface.members),
        "input_kind": surface.input_kind,
        "members": list(surface.members),
        "name": surface.name,
        "root_mode": surface.root_mode,
        "total_bytes": sum(int(item["size_bytes"]) for item in surface.members),
        "tree_sha256": surface.tree_sha256,
    }


def _manifest_without_identity(surfaces: Sequence[_SurfaceInput]) -> dict[str, object]:
    return {
        "benchmark": _BENCHMARK,
        "digest_algorithm": _IDENTITY_ALGORITHM,
        "file_count": sum(len(surface.members) for surface in surfaces),
        "release_kind": _RELEASE_KIND,
        "schema_version": _SCHEMA_VERSION,
        "surfaces": [_surface_payload(surface) for surface in surfaces],
        "total_bytes": sum(
            int(item["size_bytes"])
            for surface in surfaces
            for item in surface.members
        ),
    }


def _release_identity(unsigned: Mapping[str, object]) -> str:
    return _sha256_bytes(_canonical_json_bytes(unsigned, compact=True))


def _manifest(surfaces: Sequence[_SurfaceInput]) -> dict[str, object]:
    unsigned = _manifest_without_identity(surfaces)
    return {**unsigned, "identity_sha256": _release_identity(unsigned)}


def _inputs(
    *,
    source_root: str | Path,
    public_root: str | Path,
    trusted_root: str | Path,
    image_result: str | Path,
    no_model_audit_result: str | Path,
    h0_result: str | Path | None,
    pgbhs_result: str | Path | None,
) -> tuple[_SurfaceInput, ...]:
    raw: dict[str, tuple[Path, str]] = {
        "source": (
            _resolved_input(source_root, label="source_root", directory=True),
            "directory",
        ),
        "public": (
            _resolved_input(public_root, label="public_root", directory=True),
            "directory",
        ),
        "trusted": (
            _resolved_input(trusted_root, label="trusted_root", directory=True),
            "directory",
        ),
    }
    for name, value, label in (
        ("image", image_result, "image_result"),
        ("no-model", no_model_audit_result, "no_model_audit_result"),
    ):
        raw[name] = _resolved_result(value, label=label)
    for name, value in (("h0", h0_result), ("pgbhs", pgbhs_result)):
        if value is not None:
            raw[name] = _resolved_result(value, label=f"{name}_result")
    return tuple(
        _snapshot_surface(name, *raw[name])
        for name in _SURFACE_ORDER
        if name in raw
    )


def build_quantcodeeval_release_manifest(
    *,
    source_root: str | Path,
    public_root: str | Path,
    trusted_root: str | Path,
    image_result: str | Path,
    no_model_audit_result: str | Path,
    h0_result: str | Path | None = None,
    pgbhs_result: str | Path | None = None,
) -> dict[str, object]:
    """Return a canonicalizable manifest after rehashing every input member."""

    surfaces = _inputs(
        source_root=source_root,
        public_root=public_root,
        trusted_root=trusted_root,
        image_result=image_result,
        no_model_audit_result=no_model_audit_result,
        h0_result=h0_result,
        pgbhs_result=pgbhs_result,
    )
    return _manifest(surfaces)


def _copy_member(source: Path, destination: Path, expected: Mapping[str, object]) -> None:
    payload, metadata = _read_regular(source, label="release source")
    observed = {
        "mode": _mode_string(metadata.st_mode),
        "path": expected["path"],
        "sha256": _sha256_bytes(payload),
        "size_bytes": len(payload),
    }
    if observed != dict(expected):
        raise QuantCodeEvalReleaseError(
            f"release source drifted while publishing: {expected['path']}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
    descriptor = os.open(destination, flags, stat.S_IMODE(metadata.st_mode))
    try:
        with os.fdopen(descriptor, "wb") as output:
            descriptor = -1
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        destination.chmod(stat.S_IMODE(metadata.st_mode))
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _copy_surface(surface: _SurfaceInput, staging: Path) -> None:
    destination = staging / surface.name
    destination.mkdir(mode=0o700)
    for directory in surface.directories:
        target = destination / str(directory["path"])
        target.mkdir(parents=True, exist_ok=False)
    for member in surface.members:
        relative = Path(*PurePosixPath(str(member["path"])).parts)
        source = surface.source / relative if surface.input_kind == "directory" else surface.source
        _copy_member(source, destination / relative, member)
    # Apply directory permissions only after all descendants exist.  A source
    # release is allowed to contain deliberately read-only directories.
    for directory in sorted(
        surface.directories,
        key=lambda item: len(PurePosixPath(str(item["path"])).parts),
        reverse=True,
    ):
        (destination / str(directory["path"])).chmod(int(str(directory["mode"]), 8))
    if surface.root_mode is not None:
        destination.chmod(int(surface.root_mode, 8))


def _require_unchanged_inputs(surfaces: Sequence[_SurfaceInput]) -> None:
    """Detect additions/removals and byte or permission drift before publish."""

    for expected in surfaces:
        observed = _snapshot_surface(
            expected.name,
            expected.source,
            expected.input_kind,
        )
        if _surface_payload(observed) != _surface_payload(expected):
            raise QuantCodeEvalReleaseError(
                f"{expected.name} input membership or bytes drifted while publishing"
            )


def _load_manifest(path: Path) -> tuple[dict[str, object], bytes]:
    if path.is_symlink() or not path.is_file():
        raise QuantCodeEvalReleaseError(f"release manifest is unavailable: {path}")
    raw = path.read_bytes()
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise QuantCodeEvalReleaseError(f"release manifest is invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise QuantCodeEvalReleaseError("release manifest must contain an object")
    if raw != _canonical_json_bytes(payload):
        raise QuantCodeEvalReleaseError("release manifest bytes are not canonical JSON")
    return payload, raw


def _validate_mode(value: object, *, label: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"0o[0-7]{3,4}", value) is None:
        raise QuantCodeEvalReleaseError(f"{label} mode is invalid")
    return value


def _validate_surface_payload(raw: object) -> dict[str, object]:
    expected_keys = {
        "directories",
        "file_count",
        "input_kind",
        "members",
        "name",
        "root_mode",
        "total_bytes",
        "tree_sha256",
    }
    if not isinstance(raw, dict) or set(raw) != expected_keys:
        raise QuantCodeEvalReleaseError("release surface fields differ from schema v1")
    name = raw.get("name")
    if name not in _SURFACE_ORDER:
        raise QuantCodeEvalReleaseError("release surface name is invalid")
    input_kind = raw.get("input_kind")
    if input_kind not in {"file", "directory"}:
        raise QuantCodeEvalReleaseError(f"{name} input_kind is invalid")
    root_mode = raw.get("root_mode")
    if input_kind == "directory":
        _validate_mode(root_mode, label=f"{name} root")
    elif root_mode is not None:
        raise QuantCodeEvalReleaseError(f"{name} file surface has a root mode")
    directories = raw.get("directories")
    members = raw.get("members")
    if not isinstance(directories, list) or not isinstance(members, list) or not members:
        raise QuantCodeEvalReleaseError(f"{name} membership is invalid")
    normalized_dirs: list[dict[str, object]] = []
    dir_paths: list[str] = []
    for item in directories:
        if not isinstance(item, dict) or set(item) != {"mode", "path"}:
            raise QuantCodeEvalReleaseError(f"{name} directory record is invalid")
        relative = _safe_relative(item.get("path"))
        mode = _validate_mode(item.get("mode"), label=f"{name}/{relative}")
        normalized_dirs.append({"mode": mode, "path": relative})
        dir_paths.append(relative)
    normalized_members: list[dict[str, object]] = []
    member_paths: list[str] = []
    for item in members:
        if not isinstance(item, dict) or set(item) != {
            "mode", "path", "sha256", "size_bytes"
        }:
            raise QuantCodeEvalReleaseError(f"{name} member record is invalid")
        relative = _safe_relative(item.get("path"))
        mode = _validate_mode(item.get("mode"), label=f"{name}/{relative}")
        size = item.get("size_bytes")
        digest = item.get("sha256")
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise QuantCodeEvalReleaseError(f"{name}/{relative} size is invalid")
        if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
            raise QuantCodeEvalReleaseError(f"{name}/{relative} digest is invalid")
        normalized_members.append(
            {"mode": mode, "path": relative, "sha256": digest, "size_bytes": size}
        )
        member_paths.append(relative)
    if dir_paths != sorted(dir_paths) or len(dir_paths) != len(set(dir_paths)):
        raise QuantCodeEvalReleaseError(f"{name} directories are not canonical")
    if member_paths != sorted(member_paths) or len(member_paths) != len(set(member_paths)):
        raise QuantCodeEvalReleaseError(f"{name} members are not canonical")
    if input_kind == "file" and (directories or member_paths != ["RESULT.json"]):
        raise QuantCodeEvalReleaseError(f"{name} file surface layout is invalid")
    if raw.get("file_count") != len(normalized_members):
        raise QuantCodeEvalReleaseError(f"{name} file_count is inconsistent")
    total_bytes = sum(int(item["size_bytes"]) for item in normalized_members)
    if raw.get("total_bytes") != total_bytes:
        raise QuantCodeEvalReleaseError(f"{name} total_bytes is inconsistent")
    tree = raw.get("tree_sha256")
    expected_tree = _surface_tree_sha256(
        name=str(name),
        input_kind=str(input_kind),
        root_mode=root_mode if isinstance(root_mode, str) else None,
        directories=normalized_dirs,
        members=normalized_members,
    )
    if tree != expected_tree:
        raise QuantCodeEvalReleaseError(f"{name} tree_sha256 is inconsistent")
    return {
        **raw,
        "directories": normalized_dirs,
        "members": normalized_members,
    }


def validate_quantcodeeval_release(release_dir: str | Path) -> dict[str, object]:
    """Rehash and validate an already-published release without input roots."""

    root = _resolved_input(release_dir, label="release_dir", directory=True)
    payload, raw = _load_manifest(root / _MANIFEST_NAME)
    expected_keys = {
        "benchmark",
        "digest_algorithm",
        "file_count",
        "identity_sha256",
        "release_kind",
        "schema_version",
        "surfaces",
        "total_bytes",
    }
    if set(payload) != expected_keys:
        raise QuantCodeEvalReleaseError("release manifest fields differ from schema v1")
    if (
        payload.get("schema_version") != _SCHEMA_VERSION
        or payload.get("benchmark") != _BENCHMARK
        or payload.get("release_kind") != _RELEASE_KIND
        or payload.get("digest_algorithm") != _IDENTITY_ALGORITHM
    ):
        raise QuantCodeEvalReleaseError("release manifest protocol identity is invalid")
    raw_surfaces = payload.get("surfaces")
    if not isinstance(raw_surfaces, list):
        raise QuantCodeEvalReleaseError("release surfaces must be an array")
    surfaces = [_validate_surface_payload(item) for item in raw_surfaces]
    names = [str(item["name"]) for item in surfaces]
    expected_names = [name for name in _SURFACE_ORDER if name in set(names)]
    if names != expected_names or len(names) != len(set(names)):
        raise QuantCodeEvalReleaseError("release surfaces are not canonical")
    if not _REQUIRED_SURFACES.issubset(names) or set(names) - (
        _REQUIRED_SURFACES | _OPTIONAL_SURFACES
    ):
        raise QuantCodeEvalReleaseError("release required surface membership differs")

    expected_top = {_MANIFEST_NAME, *names}
    actual_top: set[str] = set()
    for path in root.iterdir():
        if path.is_symlink():
            raise QuantCodeEvalReleaseError(f"release symlink is forbidden: {path.name}")
        actual_top.add(path.name)
    if actual_top != expected_top:
        raise QuantCodeEvalReleaseError(
            "release top-level membership differs; "
            f"extras={sorted(actual_top - expected_top)}, "
            f"missing={sorted(expected_top - actual_top)}"
        )

    file_count = 0
    total_bytes = 0
    for surface in surfaces:
        name = str(surface["name"])
        surface_root = root / name
        if surface_root.is_symlink() or not surface_root.is_dir():
            raise QuantCodeEvalReleaseError(f"release surface is unavailable: {name}")
        expected_dirs = {str(item["path"]): item for item in surface["directories"]}
        expected_members = {str(item["path"]): item for item in surface["members"]}
        actual_dirs: dict[str, Path] = {}
        actual_members: dict[str, Path] = {}
        for path in sorted(
            surface_root.rglob("*"),
            key=lambda item: item.relative_to(surface_root).as_posix(),
        ):
            relative = path.relative_to(surface_root).as_posix()
            metadata = path.lstat()
            if stat.S_ISLNK(metadata.st_mode):
                raise QuantCodeEvalReleaseError(
                    f"release symlink is forbidden: {name}/{relative}"
                )
            if stat.S_ISDIR(metadata.st_mode):
                actual_dirs[relative] = path
            elif stat.S_ISREG(metadata.st_mode):
                actual_members[relative] = path
            else:
                raise QuantCodeEvalReleaseError(
                    f"special release member is forbidden: {name}/{relative}"
                )
        if set(actual_dirs) != set(expected_dirs) or set(actual_members) != set(
            expected_members
        ):
            raise QuantCodeEvalReleaseError(f"{name} release membership differs")
        if surface["root_mode"] != _mode_string(surface_root.stat().st_mode):
            if surface["input_kind"] == "directory":
                raise QuantCodeEvalReleaseError(f"{name} root mode drifted")
        for relative, item in expected_dirs.items():
            if _mode_string(actual_dirs[relative].stat().st_mode) != item["mode"]:
                raise QuantCodeEvalReleaseError(f"{name}/{relative} mode drifted")
        for relative, item in expected_members.items():
            payload_bytes, metadata = _read_regular(
                actual_members[relative], label=f"published {name} member"
            )
            if (
                _mode_string(metadata.st_mode) != item["mode"]
                or len(payload_bytes) != item["size_bytes"]
                or _sha256_bytes(payload_bytes) != item["sha256"]
            ):
                raise QuantCodeEvalReleaseError(f"{name}/{relative} drifted")
            file_count += 1
            total_bytes += len(payload_bytes)
    if payload.get("file_count") != file_count or payload.get("total_bytes") != total_bytes:
        raise QuantCodeEvalReleaseError("release aggregate counts are inconsistent")
    unsigned = dict(payload)
    identity = unsigned.pop("identity_sha256", None)
    if not isinstance(identity, str) or _SHA256.fullmatch(identity) is None:
        raise QuantCodeEvalReleaseError("release identity_sha256 is invalid")
    if _release_identity(unsigned) != identity:
        raise QuantCodeEvalReleaseError("release identity_sha256 is inconsistent")
    if root.name != identity:
        raise QuantCodeEvalReleaseError("release directory is not content-addressed")
    return {
        "file_count": file_count,
        "identity_sha256": identity,
        "manifest_sha256": _sha256_bytes(raw),
        "release_dir": str(root),
        "surface_names": names,
        "total_bytes": total_bytes,
    }


def _publication_root(path: str | Path) -> Path:
    unresolved = Path(path).expanduser()
    if unresolved.is_symlink():
        raise QuantCodeEvalReleaseError("output_root may not be a symlink")
    if unresolved.exists() and not unresolved.is_dir():
        raise QuantCodeEvalReleaseError("output_root must be a directory")
    unresolved.mkdir(parents=True, exist_ok=True)
    return unresolved.resolve()


def publish_quantcodeeval_release(
    *,
    source_root: str | Path,
    public_root: str | Path,
    trusted_root: str | Path,
    image_result: str | Path,
    no_model_audit_result: str | Path,
    output_root: str | Path,
    h0_result: str | Path | None = None,
    pgbhs_result: str | Path | None = None,
) -> QuantCodeEvalReleaseResult:
    """Atomically publish one exact release, preserving all prior evidence."""

    surfaces = _inputs(
        source_root=source_root,
        public_root=public_root,
        trusted_root=trusted_root,
        image_result=image_result,
        no_model_audit_result=no_model_audit_result,
        h0_result=h0_result,
        pgbhs_result=pgbhs_result,
    )
    manifest = _manifest(surfaces)
    encoded = _canonical_json_bytes(manifest)
    identity = str(manifest["identity_sha256"])
    publication_root = _publication_root(output_root)
    final = publication_root / identity
    staging = publication_root / f"{identity}.partial"
    if final.exists() or final.is_symlink():
        report = validate_quantcodeeval_release(final)
        existing = (final / _MANIFEST_NAME).read_bytes()
        if existing != encoded:
            raise QuantCodeEvalReleaseError(
                "existing release identity differs from the requested release"
            )
        return QuantCodeEvalReleaseResult(
            release_dir=final,
            manifest_path=final / _MANIFEST_NAME,
            identity_sha256=identity,
            manifest_sha256=str(report["manifest_sha256"]),
            file_count=int(report["file_count"]),
            total_bytes=int(report["total_bytes"]),
            reused_existing=True,
        )
    if staging.exists() or staging.is_symlink():
        raise QuantCodeEvalReleaseError(
            f"existing partial release is preserved and blocks publication: {staging}"
        )
    staging.mkdir(mode=0o700)
    for surface in surfaces:
        _copy_surface(surface, staging)
    _require_unchanged_inputs(surfaces)
    manifest_path = staging / _MANIFEST_NAME
    descriptor = os.open(
        manifest_path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0),
        0o600,
    )
    try:
        with os.fdopen(descriptor, "wb") as output:
            descriptor = -1
            output.write(encoded)
            output.flush()
            os.fsync(output.fileno())
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    try:
        os.rename(staging, final)
    except OSError as exc:
        raise QuantCodeEvalReleaseError(
            "atomic release publication failed; partial evidence was preserved"
        ) from exc
    report = validate_quantcodeeval_release(final)
    return QuantCodeEvalReleaseResult(
        release_dir=final,
        manifest_path=final / _MANIFEST_NAME,
        identity_sha256=identity,
        manifest_sha256=str(report["manifest_sha256"]),
        file_count=int(report["file_count"]),
        total_bytes=int(report["total_bytes"]),
        reused_existing=False,
    )


__all__ = [
    "QuantCodeEvalReleaseError",
    "QuantCodeEvalReleaseResult",
    "build_quantcodeeval_release_manifest",
    "publish_quantcodeeval_release",
    "validate_quantcodeeval_release",
]
