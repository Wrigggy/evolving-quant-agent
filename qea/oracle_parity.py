"""Compare local and E2B oracle artifacts without relying on JSON formatting."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


class OracleParityError(ValueError):
    """The E2B oracle output is missing or differs from the pinned local anchor."""


@dataclass(frozen=True)
class OracleParityResult:
    matches: bool
    files: tuple[str, ...]
    canonical_sha256: dict[str, str]


def _files(root: Path) -> dict[str, Path]:
    if not root.is_dir():
        raise OracleParityError(f"oracle artifact directory does not exist: {root}")
    found: dict[str, Path] = {}
    for path in root.rglob("*"):
        if path.is_symlink():
            raise OracleParityError(f"oracle artifact symlink is forbidden: {path}")
        if path.is_file():
            found[path.relative_to(root).as_posix()] = path
    return found


def _canonical_bytes(path: Path) -> bytes:
    if path.suffix.lower() == ".json":
        try:
            payload = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise OracleParityError(f"invalid JSON oracle artifact {path}: {exc}") from exc
        return json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    return path.read_bytes()


def compare_oracle_artifacts(
    expected_dir: str | Path,
    actual_dir: str | Path,
) -> OracleParityResult:
    expected = _files(Path(expected_dir).resolve())
    actual = _files(Path(actual_dir).resolve())
    missing = sorted(set(expected) - set(actual))
    if missing:
        raise OracleParityError(f"missing E2B oracle artifacts: {missing}")

    digests: dict[str, str] = {}
    for relative in sorted(expected):
        expected_payload = _canonical_bytes(expected[relative])
        actual_payload = _canonical_bytes(actual[relative])
        if expected_payload != actual_payload:
            raise OracleParityError(f"oracle artifact content mismatch: {relative}")
        digests[relative] = hashlib.sha256(expected_payload).hexdigest()
    return OracleParityResult(
        matches=True,
        files=tuple(sorted(expected)),
        canonical_sha256=digests,
    )
