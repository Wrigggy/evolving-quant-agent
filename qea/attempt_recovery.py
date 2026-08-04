"""Fail-closed worker-attempt replacement for ambiguous provider transport."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Mapping

from .evaluation import TaskAttempt


REPLACEMENT_MANIFEST = "worker-attempt-replacement.json"
MAX_WORKER_ATTEMPT_REPLACEMENTS = 3
_MAX_METADATA_BYTES = 16 * 1024 * 1024
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_AUDIT_FIELDS = frozenset(
    {
        "schema_version",
        "request_identity_sha256",
        "model",
        "started_at",
        "finished_at",
        "latency_ms",
        "request_state",
        "upstream_status_code",
        "provider_request_id",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "provider_cost_usd",
        "failure_class",
    }
)
_MANIFEST_FIELDS = frozenset(
    {
        "schema_version",
        "reason",
        "logical_attempt_id",
        "logical_checkpoint",
        "replacement_ordinal",
        "superseded_attempt_id",
        "replacement_attempt_id",
        "replacement_checkpoint",
        "source_audit_sha256",
    }
)


class AttemptRecoveryError(RuntimeError):
    """Persisted attempt-replacement evidence is unsafe or inconsistent."""


def _read_regular_bytes(path: Path) -> bytes:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise AttemptRecoveryError(f"attempt recovery metadata is unavailable: {path}") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise AttemptRecoveryError(
            f"attempt recovery metadata must be a regular file: {path}"
        )
    if metadata.st_size <= 0 or metadata.st_size > _MAX_METADATA_BYTES:
        raise AttemptRecoveryError(f"attempt recovery metadata exceeds its bound: {path}")
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise AttemptRecoveryError(f"attempt recovery metadata is unreadable: {path}") from exc
    if len(payload) > _MAX_METADATA_BYTES:
        raise AttemptRecoveryError(f"attempt recovery metadata exceeds its bound: {path}")
    return payload


def _read_json(path: Path) -> dict:
    raw = _read_regular_bytes(path)
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AttemptRecoveryError(f"attempt recovery metadata is invalid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise AttemptRecoveryError(f"attempt recovery metadata is not an object: {path}")
    return payload


def _atomic_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(path.suffix + ".tmp")
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_CLOEXEC", 0),
        0o600,
    )
    with os.fdopen(descriptor, "w", closefd=True) as output:
        os.fchmod(output.fileno(), 0o600)
        json.dump(payload, output, sort_keys=True, indent=2)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)
    os.chmod(path, 0o600)


def _recoverable_audit(attempt_dir: Path) -> tuple[str, str] | None:
    audit_path = attempt_dir / "proxy-audit.jsonl"
    if not audit_path.exists():
        return None
    raw = _read_regular_bytes(audit_path)
    records = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AttemptRecoveryError("attempt recovery proxy audit is malformed") from exc
        if (
            not isinstance(record, dict)
            or set(record) != _AUDIT_FIELDS
            or record.get("schema_version") != 1
        ):
            raise AttemptRecoveryError("attempt recovery proxy audit schema is invalid")
        identity = record.get("request_identity_sha256")
        if not isinstance(identity, str) or not _SHA256.fullmatch(identity):
            raise AttemptRecoveryError("attempt recovery request identity is invalid")
        records.append(record)
    if not records:
        raise AttemptRecoveryError("attempt recovery proxy audit is empty")
    identities = [record["request_identity_sha256"] for record in records]
    if len(identities) != len(set(identities)):
        raise AttemptRecoveryError("attempt recovery proxy audit repeats a request identity")
    quarantined = [
        index
        for index, record in enumerate(records)
        if record.get("request_state") == "quarantined"
    ]
    if not quarantined:
        return None
    if quarantined != [len(records) - 1]:
        raise AttemptRecoveryError(
            "attempt recovery requires exactly one terminal quarantined request"
        )
    final = records[-1]
    if final.get("failure_class") != "post_accept_transport":
        raise AttemptRecoveryError(
            "attempt recovery does not support this quarantined failure class"
        )
    if any(
        record.get("request_state") not in {"completed", "not_accepted"}
        for record in records[:-1]
    ):
        raise AttemptRecoveryError("attempt recovery proxy audit has invalid prior state")
    return "post_accept_transport", hashlib.sha256(raw).hexdigest()


def _replacement_attempt(
    logical_attempt: TaskAttempt,
    *,
    ordinal: int,
) -> TaskAttempt:
    checkpoint = (
        f"{logical_attempt.checkpoint}+infra-replacement-{ordinal:02d}"
    )
    return TaskAttempt.create(
        run_id=logical_attempt.run_id,
        benchmark_commit=logical_attempt.benchmark_commit,
        task_id=logical_attempt.task_id,
        split=logical_attempt.split,
        checkpoint=checkpoint,
        worker_digest=logical_attempt.worker_digest,
    )


def _expected_manifest(
    *,
    logical_attempt: TaskAttempt,
    superseded_attempt: TaskAttempt,
    replacement_attempt: TaskAttempt,
    ordinal: int,
    reason: str,
    source_audit_sha256: str,
) -> dict:
    return {
        "schema_version": 1,
        "reason": reason,
        "logical_attempt_id": logical_attempt.attempt_id,
        "logical_checkpoint": logical_attempt.checkpoint,
        "replacement_ordinal": ordinal,
        "superseded_attempt_id": superseded_attempt.attempt_id,
        "replacement_attempt_id": replacement_attempt.attempt_id,
        "replacement_checkpoint": replacement_attempt.checkpoint,
        "source_audit_sha256": source_audit_sha256,
    }


def read_replacement_manifest(path: str | Path) -> dict:
    """Read a replacement manifest with its closed, public metadata schema."""

    source = Path(path)
    payload = _read_json(source)
    if set(payload) != _MANIFEST_FIELDS or payload.get("schema_version") != 1:
        raise AttemptRecoveryError(f"attempt replacement manifest schema is invalid: {source}")
    for field in (
        "logical_attempt_id",
        "replacement_attempt_id",
        "superseded_attempt_id",
        "source_audit_sha256",
    ):
        value = payload.get(field)
        if not isinstance(value, str) or not _SHA256.fullmatch(value):
            raise AttemptRecoveryError(
                f"attempt replacement manifest digest is invalid: {field}"
            )
    if (
        payload.get("reason") != "post_accept_transport"
        or type(payload.get("replacement_ordinal")) is not int
        or not 1 <= payload["replacement_ordinal"] <= MAX_WORKER_ATTEMPT_REPLACEMENTS
        or not isinstance(payload.get("logical_checkpoint"), str)
        or not payload["logical_checkpoint"]
        or not isinstance(payload.get("replacement_checkpoint"), str)
        or not payload["replacement_checkpoint"]
    ):
        raise AttemptRecoveryError("attempt replacement manifest semantics are invalid")
    return payload


def resolve_worker_attempt(
    logical_attempt: TaskAttempt,
    run_dir: str | Path,
    *,
    maximum_replacements: int = MAX_WORKER_ATTEMPT_REPLACEMENTS,
) -> TaskAttempt:
    """Return the terminal worker identity without reopening a quarantined one."""

    if (
        type(maximum_replacements) is not int
        or not 1 <= maximum_replacements <= MAX_WORKER_ATTEMPT_REPLACEMENTS
    ):
        raise AttemptRecoveryError("worker attempt replacement bound is invalid")
    root = Path(run_dir).resolve()
    current = logical_attempt
    for ordinal in range(1, maximum_replacements + 1):
        current_dir = root / "attempts" / current.attempt_id
        if (
            current_dir.joinpath("completed-score.json").is_file()
            or current_dir.joinpath("worker-execution.json").is_file()
        ):
            return current
        manifest_path = current_dir / REPLACEMENT_MANIFEST
        recoverable = _recoverable_audit(current_dir)
        if manifest_path.exists():
            if recoverable is None:
                raise AttemptRecoveryError(
                    "attempt replacement manifest has no recoverable source audit"
                )
            reason, source_audit_sha256 = recoverable
            replacement = _replacement_attempt(logical_attempt, ordinal=ordinal)
            expected = _expected_manifest(
                logical_attempt=logical_attempt,
                superseded_attempt=current,
                replacement_attempt=replacement,
                ordinal=ordinal,
                reason=reason,
                source_audit_sha256=source_audit_sha256,
            )
            if read_replacement_manifest(manifest_path) != expected:
                raise AttemptRecoveryError("attempt replacement manifest drifted")
            current = replacement
            continue
        if recoverable is None:
            return current
        reason, source_audit_sha256 = recoverable
        replacement = _replacement_attempt(logical_attempt, ordinal=ordinal)
        _atomic_json(
            manifest_path,
            _expected_manifest(
                logical_attempt=logical_attempt,
                superseded_attempt=current,
                replacement_attempt=replacement,
                ordinal=ordinal,
                reason=reason,
                source_audit_sha256=source_audit_sha256,
            ),
        )
        current = replacement

    current_dir = root / "attempts" / current.attempt_id
    if current_dir.joinpath(REPLACEMENT_MANIFEST).exists() or _recoverable_audit(
        current_dir
    ) is not None:
        raise AttemptRecoveryError("worker attempt replacement limit reached")
    return current


def replacement_attempt_from_manifest(
    logical_attempt: TaskAttempt,
    manifest: Mapping[str, object],
) -> TaskAttempt:
    """Rebuild and validate the deterministic successor named by a manifest."""

    ordinal = manifest.get("replacement_ordinal")
    if type(ordinal) is not int:
        raise AttemptRecoveryError("attempt replacement ordinal is invalid")
    replacement = _replacement_attempt(logical_attempt, ordinal=ordinal)
    if (
        manifest.get("logical_attempt_id") != logical_attempt.attempt_id
        or manifest.get("replacement_attempt_id") != replacement.attempt_id
        or manifest.get("replacement_checkpoint") != replacement.checkpoint
    ):
        raise AttemptRecoveryError("attempt replacement identity is invalid")
    return replacement


__all__ = [
    "AttemptRecoveryError",
    "MAX_WORKER_ATTEMPT_REPLACEMENTS",
    "REPLACEMENT_MANIFEST",
    "read_replacement_manifest",
    "replacement_attempt_from_manifest",
    "resolve_worker_attempt",
]
