"""Provider-neutral persisted worker execution records and behavioral errors."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from ..evaluation import ArtifactRecord, TaskAttempt


class WorkerExecutionError(RuntimeError):
    """A worker execution record is invalid or cannot be used safely."""


class WorkerBehaviorTimeout(WorkerExecutionError):
    """The worker reached the benchmark's declared behavioral time limit."""

    def __init__(self, message: str, *, log_uri: str | None = None) -> None:
        super().__init__(message)
        self.log_uri = log_uri


@dataclass(frozen=True)
class PersistedWorkerTimeout:
    """Coordinator-authored evidence for one official worker timeout."""

    attempt_id: str
    log_uri: str
    command_sha256: str
    quarantine_sha256: str
    quarantine_reason: str


@dataclass(frozen=True)
class WorkerExecution:
    attempt_id: str
    artifact_dir: Path
    artifacts: tuple[ArtifactRecord, ...]
    trace_uri: str
    log_uri: str
    final_text_uri: str
    summary: dict
    sandbox_id: str
    cleaned_up: bool


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")
    os.replace(temporary, path)


def _read_bounded_json(path: Path, *, label: str) -> tuple[dict, bytes]:
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise WorkerExecutionError(f"persisted timeout {label} is unreadable") from exc
    if not payload or len(payload) > 1024 * 1024:
        raise WorkerExecutionError(f"persisted timeout {label} exceeds its bound")
    try:
        parsed = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkerExecutionError(
            f"persisted timeout {label} is invalid JSON"
        ) from exc
    if not isinstance(parsed, dict):
        raise WorkerExecutionError(f"persisted timeout {label} schema is invalid")
    return parsed, payload


def load_persisted_worker_timeout(
    attempt: TaskAttempt,
    run_dir: str | Path,
) -> PersistedWorkerTimeout | None:
    """Load exact timeout/quarantine evidence without reopening the worker."""

    attempt_dir = Path(run_dir).resolve() / "attempts" / attempt.attempt_id
    command_path = attempt_dir / "worker-command.json"
    quarantine_path = attempt_dir / "proxy-audit.quarantined.json"
    command_exists = command_path.is_file()
    quarantine_exists = quarantine_path.is_file()
    if not command_exists and not quarantine_exists:
        return None
    if command_exists != quarantine_exists:
        raise WorkerExecutionError(
            "persisted timeout command and quarantine evidence must be paired"
        )
    if (attempt_dir / "proxy-audit.jsonl").exists():
        raise WorkerExecutionError(
            "persisted timeout conflicts with a canonical proxy audit"
        )

    command, command_bytes = _read_bounded_json(command_path, label="command")
    if set(command) != {"exit_code", "stdout", "stderr", "timed_out"}:
        raise WorkerExecutionError("persisted timeout command schema is invalid")
    if command["timed_out"] is not True:
        raise WorkerExecutionError("persisted timeout command timed_out must be true")
    if type(command["exit_code"]) is not int or command["exit_code"] != 124:
        raise WorkerExecutionError("persisted timeout command exit code must be 124")
    if not isinstance(command["stdout"], str) or not isinstance(
        command["stderr"], str
    ):
        raise WorkerExecutionError("persisted timeout command output schema is invalid")

    quarantine, quarantine_bytes = _read_bounded_json(
        quarantine_path, label="quarantine"
    )
    if set(quarantine) != {"schema_version", "request_state", "reason"}:
        raise WorkerExecutionError("persisted timeout quarantine schema is invalid")
    if (
        quarantine["schema_version"] != 1
        or quarantine["request_state"] != "quarantined"
    ):
        raise WorkerExecutionError("persisted timeout quarantine state is invalid")
    reason = quarantine["reason"]
    if reason != "audit_download_or_validation_failed":
        raise WorkerExecutionError("persisted timeout quarantine reason is unsupported")

    return PersistedWorkerTimeout(
        attempt_id=attempt.attempt_id,
        log_uri=str(command_path.resolve()),
        command_sha256=hashlib.sha256(command_bytes).hexdigest(),
        quarantine_sha256=hashlib.sha256(quarantine_bytes).hexdigest(),
        quarantine_reason=reason,
    )


def persist_timeout_recovery(
    attempt_dir: Path,
    evidence: PersistedWorkerTimeout,
) -> Path:
    """Persist one source-hash-bound timeout recovery record idempotently."""

    path = attempt_dir / "timeout-recovery.json"
    payload = {
        "schema_version": 1,
        "attempt_id": evidence.attempt_id,
        "outcome": "official_worker_timeout_zero",
        "command_sha256": evidence.command_sha256,
        "quarantine_sha256": evidence.quarantine_sha256,
        "quarantine_reason": evidence.quarantine_reason,
    }
    if path.is_file():
        try:
            existing = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise WorkerExecutionError(
                "persisted timeout recovery record is invalid"
            ) from exc
        if existing != payload:
            raise WorkerExecutionError("persisted timeout recovery record drifted")
        return path
    _write_json(path, payload)
    return path


def persist_worker_execution(execution: WorkerExecution, attempt_dir: Path) -> None:
    """Persist the historical worker-execution JSON schema without byte drift."""

    payload = {
        "attempt_id": execution.attempt_id,
        "artifact_dir": str(execution.artifact_dir.relative_to(attempt_dir)),
        "artifacts": [asdict(record) for record in execution.artifacts],
        "trace_uri": str(Path(execution.trace_uri).relative_to(attempt_dir)),
        "log_uri": str(Path(execution.log_uri).relative_to(attempt_dir)),
        "final_text_uri": str(Path(execution.final_text_uri).relative_to(attempt_dir)),
        "summary": execution.summary,
        "sandbox_id": execution.sandbox_id,
        "cleaned_up": execution.cleaned_up,
    }
    _write_json(attempt_dir / "worker-execution.json", payload)


def load_worker_execution(
    attempt: TaskAttempt,
    run_dir: str | Path,
) -> WorkerExecution | None:
    """Restore a completed worker attempt and verify every artifact hash."""

    attempt_dir = Path(run_dir).resolve() / "attempts" / attempt.attempt_id
    manifest_path = attempt_dir / "worker-execution.json"
    if not manifest_path.is_file():
        return None
    try:
        payload = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkerExecutionError(f"invalid worker execution manifest: {exc}") from exc
    if payload.get("attempt_id") != attempt.attempt_id:
        raise WorkerExecutionError("worker execution manifest attempt mismatch")
    artifact_dir = (attempt_dir / payload["artifact_dir"]).resolve()
    records = tuple(ArtifactRecord(**item) for item in payload.get("artifacts", ()))
    for record in records:
        current = ArtifactRecord.from_file(artifact_dir / record.path, root=artifact_dir)
        if current != record:
            raise WorkerExecutionError(
                f"artifact integrity mismatch on resume: {record.path}"
            )
    return WorkerExecution(
        attempt_id=attempt.attempt_id,
        artifact_dir=artifact_dir,
        artifacts=records,
        trace_uri=str((attempt_dir / payload["trace_uri"]).resolve()),
        log_uri=str((attempt_dir / payload["log_uri"]).resolve()),
        final_text_uri=str((attempt_dir / payload["final_text_uri"]).resolve()),
        summary=dict(payload.get("summary", {})),
        sandbox_id=str(payload.get("sandbox_id", "")),
        cleaned_up=bool(payload.get("cleaned_up", False)),
    )
