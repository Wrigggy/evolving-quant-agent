"""Content-addressed, answer-free history for QuantCodeEval harness evolution.

The v1 QuantCodeEval canary retained complete run artifacts, but the next
Evolver only received a compact outcome summary.  This module makes the safe
part of every attempted mutation directly inspectable: exact harness source,
the unified diff, declared mechanism, component-local tests, answer-free
evaluation, and selection/rollback state.  Trusted checker material is never
accepted by this store.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from .evolve_runtime import dir_unified_diff
from .mutation_metrics import measure_mutation
from .worker_identity import hash_worker_directory


_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_FORBIDDEN_KEY_PARTS = (
    "checker",
    "expected",
    "golden",
    "property_id",
    "reference_solution",
    "raw_verdict",
)
_FORBIDDEN_PATH_PARTS = frozenset(
    {
        ".env",
        "checkers",
        "expected",
        "golden",
        "golden_ref.py",
        "tests",
    }
)
_REQUIRED_ENTRY_KEYS = frozenset(
    {
        "schema_version",
        "entry_id",
        "run_id",
        "iteration",
        "parent_digest",
        "candidate_digest",
        "decision",
        "mechanism",
        "primary_components",
        "declared_roles",
        "mutation_metrics",
        "diff_sha256",
        "component_tests",
        "activation",
        "evaluation",
        "selection",
        "rollback_reason",
    }
)


class QuantCodeEvalHistoryError(ValueError):
    """History input, storage, or evidence projection is unsafe or inconsistent."""


@dataclass(frozen=True)
class QuantHistoryAppendResult:
    entry_id: str
    entry_path: Path
    parent_digest: str
    candidate_digest: str
    diff_sha256: str
    reused_existing: bool


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _reject_oracle_keys(value: object, *, label: str) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).casefold()
            if any(part in normalized for part in _FORBIDDEN_KEY_PARTS):
                raise QuantCodeEvalHistoryError(
                    f"{label} contains forbidden oracle-like key {key!r}"
                )
            _reject_oracle_keys(child, label=label)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _reject_oracle_keys(child, label=label)


def _validate_json_value(value: object, *, label: str) -> object:
    try:
        encoded = _canonical_json(value)
        normalized = json.loads(encoded)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise QuantCodeEvalHistoryError(f"{label} must be canonical JSON") from exc
    _reject_oracle_keys(normalized, label=label)
    return normalized


def _validate_worker_tree(root: Path) -> None:
    if root.is_symlink() or not root.is_dir():
        raise QuantCodeEvalHistoryError(f"worker snapshot is not a regular directory: {root}")
    files = 0
    total = 0
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(root)
        if any(part.casefold() in _FORBIDDEN_PATH_PARTS for part in relative.parts):
            raise QuantCodeEvalHistoryError(
                f"worker snapshot contains forbidden path: {relative.as_posix()}"
            )
        if path.is_symlink():
            raise QuantCodeEvalHistoryError(
                f"worker snapshot contains a symlink: {relative.as_posix()}"
            )
        mode = path.lstat().st_mode
        if path.is_dir():
            continue
        if not stat.S_ISREG(mode):
            raise QuantCodeEvalHistoryError(
                f"worker snapshot contains a special member: {relative.as_posix()}"
            )
        payload = path.read_bytes()
        try:
            payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise QuantCodeEvalHistoryError(
                f"worker snapshot contains non-UTF8 source: {relative.as_posix()}"
            ) from exc
        files += 1
        total += len(payload)
        if files > 2_000 or total > 64 * 1024 * 1024:
            raise QuantCodeEvalHistoryError("worker snapshot exceeds history limits")


def _ensure_store(root: Path) -> None:
    if root.is_symlink():
        raise QuantCodeEvalHistoryError("history root must not be a symlink")
    root.mkdir(parents=True, exist_ok=True)
    for relative in ("entries", "diffs", "objects", "tests"):
        path = root / relative
        if path.is_symlink():
            raise QuantCodeEvalHistoryError(f"history path must not be a symlink: {path}")
        path.mkdir(exist_ok=True)


def _atomic_replace(path: Path, payload: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".partial"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _publish_immutable(path: Path, payload: bytes) -> bool:
    """Publish one immutable file; return whether an identical file was reused."""

    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file() or path.read_bytes() != payload:
            raise QuantCodeEvalHistoryError(f"immutable history object differs: {path}")
        return True
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".partial"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.is_symlink() or not path.is_file() or path.read_bytes() != payload:
                raise QuantCodeEvalHistoryError(
                    f"concurrent immutable history object differs: {path}"
                )
            return True
        return False
    finally:
        temporary.unlink(missing_ok=True)


def _publish_snapshot(source: Path, objects_root: Path, digest: str) -> bool:
    destination = objects_root / digest
    if destination.exists() or destination.is_symlink():
        if destination.is_symlink() or not destination.is_dir():
            raise QuantCodeEvalHistoryError("history snapshot object is not a directory")
        _validate_worker_tree(destination)
        if hash_worker_directory(destination) != digest:
            raise QuantCodeEvalHistoryError("history snapshot object was modified")
        return True
    staging = Path(tempfile.mkdtemp(dir=objects_root, prefix=f".{digest}.partial-"))
    snapshot = staging / "snapshot"
    try:
        shutil.copytree(source, snapshot, copy_function=shutil.copy2)
        _validate_worker_tree(snapshot)
        if hash_worker_directory(snapshot) != digest:
            raise QuantCodeEvalHistoryError("worker changed while snapshotting history")
        try:
            os.replace(snapshot, destination)
        except OSError as exc:
            if not destination.is_dir() or hash_worker_directory(destination) != digest:
                raise QuantCodeEvalHistoryError(
                    "concurrent history snapshot publication differs"
                ) from exc
            return True
        return False
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def _load_index(root: Path) -> dict[str, object]:
    path = root / "INDEX.json"
    if not path.exists():
        return {"schema_version": 1, "entries": []}
    if path.is_symlink() or not path.is_file():
        raise QuantCodeEvalHistoryError("history index is not a regular file")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise QuantCodeEvalHistoryError("history index is invalid") from exc
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "entries"}:
        raise QuantCodeEvalHistoryError("history index schema differs")
    if payload["schema_version"] != 1 or not isinstance(payload["entries"], list):
        raise QuantCodeEvalHistoryError("history index fields are invalid")
    if any(not isinstance(value, str) or _SHA256.fullmatch(value) is None for value in payload["entries"]):
        raise QuantCodeEvalHistoryError("history index contains an invalid entry ID")
    if len(payload["entries"]) != len(set(payload["entries"])):
        raise QuantCodeEvalHistoryError("history index contains duplicate entries")
    return payload


def append_quantcodeeval_history(
    *,
    history_root: str | Path,
    run_id: str,
    iteration: int,
    parent_worker_dir: str | Path,
    candidate_worker_dir: str | Path,
    decision: Mapping[str, object],
    mechanism: str,
    primary_components: Iterable[str],
    declared_roles: Iterable[str],
    component_tests: Iterable[Mapping[str, object]] = (),
    activation: Mapping[str, object] | None = None,
    evaluation: Mapping[str, object] | None = None,
    selection: str = "pending",
    rollback_reason: str | None = None,
    allow_rejected_attribution_mismatch: bool = False,
) -> QuantHistoryAppendResult:
    """Append one immutable mutation experience and content-addressed snapshots."""

    if _SAFE_ID.fullmatch(str(run_id)) is None:
        raise QuantCodeEvalHistoryError("run_id must be path-safe")
    if type(iteration) is not int or iteration < 1:
        raise QuantCodeEvalHistoryError("iteration must be a positive integer")
    if not isinstance(mechanism, str) or not mechanism.strip():
        raise QuantCodeEvalHistoryError("mechanism must be non-empty text")
    if selection not in {"pending", "accepted", "rejected", "archived", "abstained"}:
        raise QuantCodeEvalHistoryError("selection is unsupported")
    if selection == "rejected" and not rollback_reason:
        raise QuantCodeEvalHistoryError("rejected history requires rollback_reason")

    parent = Path(parent_worker_dir).expanduser().resolve()
    candidate = Path(candidate_worker_dir).expanduser().resolve()
    _validate_worker_tree(parent)
    _validate_worker_tree(candidate)
    parent_digest = hash_worker_directory(parent)
    candidate_digest = hash_worker_directory(candidate)
    declared = tuple(sorted({str(value) for value in declared_roles}))
    primary = tuple(sorted({str(value) for value in primary_components}))
    if not declared or not primary or not set(primary) <= set(declared):
        raise QuantCodeEvalHistoryError(
            "primary components must be a non-empty subset of declared roles"
        )
    metrics = measure_mutation(
        before_root=parent,
        after_root=candidate,
        declared_roles=declared,
    )
    if metrics["changed_file_count"] == 0:
        raise QuantCodeEvalHistoryError("history ACT requires a non-empty mutation")
    attribution_mismatch_allowed = (
        allow_rejected_attribution_mismatch and selection == "rejected"
    )
    if (
        metrics["declared_roles_match_actual"] is not True
        and not attribution_mismatch_allowed
    ):
        raise QuantCodeEvalHistoryError("declared roles differ from the exact mutation")
    diff = dir_unified_diff(parent, candidate).encode("utf-8")
    if not diff:
        raise QuantCodeEvalHistoryError("history mutation has no exact UTF-8 diff")
    diff_sha256 = _sha256(diff)

    normalized_tests = [
        _validate_json_value(dict(value), label="component test")
        for value in component_tests
    ]
    normalized_decision = _validate_json_value(dict(decision), label="decision")
    normalized_activation = _validate_json_value(
        dict(activation or {}), label="activation"
    )
    normalized_evaluation = _validate_json_value(
        dict(evaluation or {}), label="evaluation"
    )
    core = {
        "schema_version": 1,
        "run_id": str(run_id),
        "iteration": iteration,
        "parent_digest": parent_digest,
        "candidate_digest": candidate_digest,
        "decision": normalized_decision,
        "mechanism": mechanism.strip(),
        "primary_components": list(primary),
        "declared_roles": list(declared),
        "mutation_metrics": metrics,
        "diff_sha256": diff_sha256,
        "component_tests": normalized_tests,
        "activation": normalized_activation,
        "evaluation": normalized_evaluation,
        "selection": selection,
        "rollback_reason": rollback_reason,
    }
    entry_id = _sha256(_canonical_json(core))
    entry = {**core, "entry_id": entry_id}
    entry_payload = _canonical_json(entry)

    root = Path(history_root).expanduser().resolve()
    _ensure_store(root)
    reused_parent = _publish_snapshot(parent, root / "objects", parent_digest)
    reused_candidate = _publish_snapshot(candidate, root / "objects", candidate_digest)
    reused_diff = _publish_immutable(root / "diffs" / f"{diff_sha256}.patch", diff)
    tests_payload = _canonical_json(
        {"schema_version": 1, "candidate_digest": candidate_digest, "tests": normalized_tests}
    )
    _publish_immutable(root / "tests" / f"{candidate_digest}.json", tests_payload)
    reused_entry = _publish_immutable(root / "entries" / f"{entry_id}.json", entry_payload)

    index = _load_index(root)
    entries = list(index["entries"])
    if entry_id not in entries:
        entries.append(entry_id)
        _atomic_replace(root / "INDEX.json", _canonical_json({"schema_version": 1, "entries": entries}))
    validate_quantcodeeval_history(root)
    return QuantHistoryAppendResult(
        entry_id=entry_id,
        entry_path=root / "entries" / f"{entry_id}.json",
        parent_digest=parent_digest,
        candidate_digest=candidate_digest,
        diff_sha256=diff_sha256,
        reused_existing=(
            reused_parent and reused_candidate and reused_diff and reused_entry
        ),
    )


def validate_quantcodeeval_history(history_root: str | Path) -> dict[str, object]:
    """Rehash every history entry, diff, and referenced candidate snapshot."""

    root = Path(history_root).expanduser().resolve()
    _ensure_store(root)
    index = _load_index(root)
    referenced_objects: set[str] = set()
    referenced_diffs: set[str] = set()
    for entry_id in index["entries"]:
        path = root / "entries" / f"{entry_id}.json"
        if path.is_symlink() or not path.is_file():
            raise QuantCodeEvalHistoryError(f"history entry is missing: {entry_id}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise QuantCodeEvalHistoryError(f"history entry is invalid: {entry_id}") from exc
        if not isinstance(payload, dict) or set(payload) != _REQUIRED_ENTRY_KEYS:
            raise QuantCodeEvalHistoryError(f"history entry schema differs: {entry_id}")
        core = {key: value for key, value in payload.items() if key != "entry_id"}
        if payload["entry_id"] != entry_id or _sha256(_canonical_json(core)) != entry_id:
            raise QuantCodeEvalHistoryError(f"history entry identity differs: {entry_id}")
        _reject_oracle_keys(payload, label=f"history entry {entry_id}")
        for name in ("parent_digest", "candidate_digest"):
            digest = payload[name]
            if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
                raise QuantCodeEvalHistoryError(f"history {name} is invalid")
            snapshot = root / "objects" / digest
            _validate_worker_tree(snapshot)
            if hash_worker_directory(snapshot) != digest:
                raise QuantCodeEvalHistoryError(f"history snapshot differs: {digest}")
            referenced_objects.add(digest)
        diff_digest = payload["diff_sha256"]
        if not isinstance(diff_digest, str) or _SHA256.fullmatch(diff_digest) is None:
            raise QuantCodeEvalHistoryError("history diff identity is invalid")
        diff_path = root / "diffs" / f"{diff_digest}.patch"
        if diff_path.is_symlink() or not diff_path.is_file() or _sha256(diff_path.read_bytes()) != diff_digest:
            raise QuantCodeEvalHistoryError(f"history diff differs: {diff_digest}")
        referenced_diffs.add(diff_digest)
        tests_path = root / "tests" / f"{payload['candidate_digest']}.json"
        if tests_path.is_symlink() or not tests_path.is_file():
            raise QuantCodeEvalHistoryError("history component-test record is missing")
        try:
            tests_payload = json.loads(tests_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise QuantCodeEvalHistoryError(
                "history component-test record is invalid"
            ) from exc
        expected_tests = {
            "schema_version": 1,
            "candidate_digest": payload["candidate_digest"],
            "tests": payload["component_tests"],
        }
        if tests_payload != expected_tests:
            raise QuantCodeEvalHistoryError(
                "history component-test record differs from its entry"
            )
    entry_files = {path.stem for path in (root / "entries").glob("*.json")}
    diff_files = {path.stem for path in (root / "diffs").glob("*.patch")}
    object_dirs = {path.name for path in (root / "objects").iterdir() if path.is_dir()}
    if entry_files != set(index["entries"]):
        raise QuantCodeEvalHistoryError("history contains unindexed entry files")
    if diff_files != referenced_diffs:
        raise QuantCodeEvalHistoryError("history contains unreferenced diff files")
    if object_dirs != referenced_objects:
        raise QuantCodeEvalHistoryError("history contains unreferenced snapshots")
    return {
        "schema_version": 1,
        "entry_count": len(index["entries"]),
        "entry_ids": list(index["entries"]),
        "object_count": len(referenced_objects),
        "diff_count": len(referenced_diffs),
    }


def materialize_quantcodeeval_history_evidence(
    *, history_root: str | Path, destination: str | Path
) -> dict[str, object]:
    """Copy the validated safe history into a read-only Evolver evidence surface."""

    source = Path(history_root).expanduser().resolve()
    summary = validate_quantcodeeval_history(source)
    target = Path(destination).expanduser().resolve()
    if target.exists() or target.is_symlink():
        raise QuantCodeEvalHistoryError("history evidence destination already exists")
    staging = target.with_name(target.name + ".partial")
    if staging.exists() or staging.is_symlink():
        raise QuantCodeEvalHistoryError("history evidence staging path already exists")
    try:
        shutil.copytree(source, staging, copy_function=shutil.copy2)
        validate_quantcodeeval_history(staging)
        # The trusted store calls these records ``tests``.  Evolver evidence
        # deliberately forbids every path named ``tests`` because that name is
        # reserved for possible private evaluator material.  Project the same
        # hash-bound records under an unambiguous public name only after the
        # copied store has passed full validation.
        os.replace(staging / "tests", staging / "component_checks")
        validate_quantcodeeval_history(source)
        for path in staging.rglob("*"):
            if path.is_file():
                os.chmod(path, stat.S_IMODE(path.stat().st_mode) & ~0o222)
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging, target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return {**summary, "root": target.as_posix()}


__all__ = [
    "QuantCodeEvalHistoryError",
    "QuantHistoryAppendResult",
    "append_quantcodeeval_history",
    "materialize_quantcodeeval_history_evidence",
    "validate_quantcodeeval_history",
]
