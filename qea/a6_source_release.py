"""Deterministic source-tree identity for an A6 remote release.

The release manifest lives outside the release root so the manifest can bind
every executable/source member without creating a self-referential digest.
Only the narrow code, configuration, frozen QFBench data, and dated protocol
documentation surfaces needed by A6 are admissible.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path, PurePosixPath
from typing import Mapping, Sequence


class A6SourceReleaseError(ValueError):
    """The proposed A6 source release is incomplete, unsafe, or drifted."""


_SCHEMA_VERSION = 1
_STAGE = "A6"
_TREE_DIGEST_ALGORITHM = "sha256-canonical-member-index-v1"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_ROOT_FILES = frozenset({"pyproject.toml", "run.py"})
_PREFIX_SUFFIXES = {
    "qea": frozenset({".json", ".md", ".py", ".yaml"}),
    "scripts": frozenset({".py"}),
    "configs": frozenset({".json", ".md", ".yaml"}),
    "data/qfbench": frozenset({".json", ".md"}),
    "docs/decisions": frozenset({".md"}),
    "docs/reports": frozenset({".md"}),
}
_EXACT_DOCS = frozenset({"docs/PROJECT_MEMORY.md"})
_REQUIRED_MEMBERS = frozenset(
    {
        "pyproject.toml",
        "run.py",
        "qea/__init__.py",
        "qea/a6_source_release.py",
        "qea/qfbench_a6.py",
        "scripts/audit_qfbench_a6_discovery.py",
        "scripts/build_qfbench_a6_evidence.py",
        "scripts/materialize_a6_prelaunch_identity.py",
        "scripts/run_qfbench_component_pilot.py",
        "scripts/run_qfbench_discovery_pilot.py",
        "data/qfbench/MANIFEST_A6_EXPANDED_CANARY.json",
        "docs/PROJECT_MEMORY.md",
        (
            "docs/decisions/2026-08-09-qfbench-a6-expanded-panel-"
            "feedback-and-mutation-protocol.md"
        ),
    }
)
_FORBIDDEN_PARTS = frozenset(
    {
        ".git",
        ".hg",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".svn",
        ".tox",
        ".venv",
        "__pycache__",
        "artifacts",
        "cache",
        "caches",
        "credential",
        "credentials",
        "inspection",
        "node_modules",
        "output",
        "outputs",
        "result",
        "results",
        "run-artifacts",
        "runs",
        "runtime",
        "secret",
        "secrets",
        "tests",
        "tmp",
        "venv",
    }
)
_FORBIDDEN_FILE_NAMES = frozenset(
    {
        ".env",
        ".env.local",
        ".env.production",
        ".env.test",
        ".netrc",
        ".npmrc",
        ".pypirc",
        ".python-version",
        ".ssh",
        "id_dsa",
        "id_ed25519",
        "id_rsa",
    }
)
_FORBIDDEN_SUFFIXES = frozenset({".key", ".p12", ".pem", ".pyc", ".pyo"})


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


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


def _safe_relative_path(value: object) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise A6SourceReleaseError("release member path must be a non-empty string")
    if "\\" in value:
        raise A6SourceReleaseError(f"release member path is not POSIX: {value!r}")
    pure = PurePosixPath(value)
    if pure.is_absolute() or pure.as_posix() != value:
        raise A6SourceReleaseError(f"release member path is not canonical: {value!r}")
    if any(part in {"", ".", ".."} for part in pure.parts):
        raise A6SourceReleaseError(f"release member path is unsafe: {value!r}")
    return value


def _path_policy(relative: str, *, directory: bool = False) -> None:
    pure = PurePosixPath(relative)
    lowered = tuple(part.casefold() for part in pure.parts)
    name = lowered[-1]
    if name == ".ds_store" or name.startswith("._"):
        raise A6SourceReleaseError(
            f"AppleDouble or Finder metadata is forbidden: {relative}"
        )
    if any(part in _FORBIDDEN_PARTS for part in lowered):
        raise A6SourceReleaseError(
            f"cache, result, runtime, or secret path is forbidden: {relative}"
        )
    if name in _FORBIDDEN_FILE_NAMES or PurePosixPath(name).suffix in _FORBIDDEN_SUFFIXES:
        raise A6SourceReleaseError(f"credential or generated file is forbidden: {relative}")
    if any(marker in name for marker in ("credential", "password", "private_key", "secret")):
        raise A6SourceReleaseError(f"secret-like filename is forbidden: {relative}")

    if directory:
        return

    if relative in _ROOT_FILES or relative in _EXACT_DOCS:
        return
    for prefix, suffixes in _PREFIX_SUFFIXES.items():
        if relative.startswith(prefix + "/") and PurePosixPath(relative).suffix in suffixes:
            return
    raise A6SourceReleaseError(f"release member is outside the A6 allowlist: {relative}")


def _resolved_directory(root: str | Path) -> Path:
    raw = Path(root).expanduser()
    if raw.is_symlink() or not raw.is_dir():
        raise A6SourceReleaseError(f"release root must be a regular directory: {raw}")
    return raw.resolve()


def _resolved_external_manifest(root: Path, manifest_path: str | Path) -> Path:
    raw = Path(manifest_path).expanduser()
    if raw.is_symlink():
        raise A6SourceReleaseError("release manifest may not be a symlink")
    resolved = raw.resolve()
    if resolved == root or root in resolved.parents:
        raise A6SourceReleaseError("release manifest must live outside the release root")
    return resolved


def _release_files(root: Path) -> list[tuple[str, Path]]:
    files: list[tuple[str, Path]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        _safe_relative_path(relative)
        if path.is_symlink():
            raise A6SourceReleaseError(f"release symlink is forbidden: {relative}")
        if path.is_dir():
            _path_policy(relative, directory=True)
            continue
        _path_policy(relative)
        if not path.is_file():
            raise A6SourceReleaseError(f"special release member is forbidden: {relative}")
        resolved = path.resolve()
        if root not in resolved.parents:
            raise A6SourceReleaseError(f"release member escapes its root: {relative}")
        files.append((relative, path))
    members = {relative for relative, _ in files}
    missing = sorted(_REQUIRED_MEMBERS - members)
    if missing:
        raise A6SourceReleaseError(
            "A6 source release is missing required members: " + ", ".join(missing)
        )
    return files


def _member_record(relative: str, path: Path) -> dict[str, object]:
    payload = path.read_bytes()
    return {
        "path": relative,
        "size_bytes": len(payload),
        "sha256": _sha256_bytes(payload),
    }


def _tree_digest(members: Sequence[Mapping[str, object]]) -> str:
    payload = {
        "algorithm": _TREE_DIGEST_ALGORITHM,
        "members": list(members),
        "schema_version": _SCHEMA_VERSION,
        "stage": _STAGE,
    }
    return _sha256_bytes(_canonical_json_bytes(payload, compact=True))


def build_a6_source_release_manifest(
    root: str | Path,
    manifest_path: str | Path,
    *,
    overwrite: bool = False,
) -> dict[str, object]:
    """Build a canonical manifest for a pre-staged, allowlisted A6 tree."""

    release_root = _resolved_directory(root)
    destination = _resolved_external_manifest(release_root, manifest_path)
    if destination.exists() and not overwrite:
        raise A6SourceReleaseError(f"release manifest already exists: {destination}")
    members = [
        _member_record(relative, path)
        for relative, path in _release_files(release_root)
    ]
    payload = {
        "digest_algorithm": _TREE_DIGEST_ALGORITHM,
        "member_count": len(members),
        "members": members,
        "schema_version": _SCHEMA_VERSION,
        "stage": _STAGE,
        "tree_sha256": _tree_digest(members),
    }
    encoded = _canonical_json_bytes(payload)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=destination.parent,
            prefix=destination.name + ".tmp-",
            delete=False,
        ) as temporary:
            temporary.write(encoded)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_name = temporary.name
        os.replace(temporary_name, destination)
        temporary_name = None
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)
    return {
        "manifest_sha256": _sha256_bytes(encoded),
        "tree_sha256": payload["tree_sha256"],
        "member_count": len(members),
    }


def _manifest_object(path: Path) -> tuple[dict[str, object], bytes]:
    if path.is_symlink() or not path.is_file():
        raise A6SourceReleaseError(f"release manifest is unavailable: {path}")
    raw = path.read_bytes()
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise A6SourceReleaseError(f"release manifest is invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise A6SourceReleaseError("release manifest must contain an object")
    if raw != _canonical_json_bytes(payload):
        raise A6SourceReleaseError("release manifest bytes are not canonical JSON")
    return payload, raw


def validate_a6_source_release(
    root: str | Path,
    manifest_path: str | Path,
) -> dict[str, object]:
    """Verify the exact regular-file membership and bytes of an A6 release."""

    release_root = _resolved_directory(root)
    manifest = _resolved_external_manifest(release_root, manifest_path)
    payload, raw = _manifest_object(manifest)
    expected_keys = {
        "digest_algorithm",
        "member_count",
        "members",
        "schema_version",
        "stage",
        "tree_sha256",
    }
    if set(payload) != expected_keys:
        raise A6SourceReleaseError("release manifest fields differ from schema v1")
    if payload.get("schema_version") != _SCHEMA_VERSION or payload.get("stage") != _STAGE:
        raise A6SourceReleaseError("release manifest schema or stage is invalid")
    if payload.get("digest_algorithm") != _TREE_DIGEST_ALGORITHM:
        raise A6SourceReleaseError("release manifest digest algorithm is invalid")
    members = payload.get("members")
    if not isinstance(members, list):
        raise A6SourceReleaseError("release manifest members must be an array")
    if payload.get("member_count") != len(members):
        raise A6SourceReleaseError("release manifest member_count is inconsistent")

    paths: list[str] = []
    normalized: list[dict[str, object]] = []
    for item in members:
        if not isinstance(item, dict) or set(item) != {"path", "sha256", "size_bytes"}:
            raise A6SourceReleaseError("release manifest member fields are invalid")
        relative = _safe_relative_path(item.get("path"))
        _path_policy(relative)
        size = item.get("size_bytes")
        digest = item.get("sha256")
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise A6SourceReleaseError(f"release member size is invalid: {relative}")
        if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
            raise A6SourceReleaseError(f"release member digest is invalid: {relative}")
        paths.append(relative)
        normalized.append({"path": relative, "size_bytes": size, "sha256": digest})
    if paths != sorted(paths):
        raise A6SourceReleaseError("release manifest members are not canonically sorted")
    if len(paths) != len(set(paths)):
        raise A6SourceReleaseError("release manifest contains duplicate members")

    actual_files = _release_files(release_root)
    actual_paths = [relative for relative, _ in actual_files]
    if paths != actual_paths:
        extras = sorted(set(actual_paths) - set(paths))
        missing = sorted(set(paths) - set(actual_paths))
        raise A6SourceReleaseError(
            f"release file membership differs; extras={extras}, missing={missing}"
        )
    for item, (_, path) in zip(normalized, actual_files):
        stat = path.stat()
        if stat.st_size != item["size_bytes"]:
            raise A6SourceReleaseError(f"release member size drifted: {item['path']}")
        if _sha256_bytes(path.read_bytes()) != item["sha256"]:
            raise A6SourceReleaseError(f"release member digest drifted: {item['path']}")

    tree_sha256 = payload.get("tree_sha256")
    if not isinstance(tree_sha256, str) or _SHA256.fullmatch(tree_sha256) is None:
        raise A6SourceReleaseError("release tree_sha256 is invalid")
    if _tree_digest(normalized) != tree_sha256:
        raise A6SourceReleaseError("release tree_sha256 is inconsistent")
    return {
        "manifest_sha256": _sha256_bytes(raw),
        "tree_sha256": tree_sha256,
        "member_count": len(normalized),
    }


__all__ = [
    "A6SourceReleaseError",
    "build_a6_source_release_manifest",
    "validate_a6_source_release",
]
