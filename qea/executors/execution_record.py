"""Provider-neutral persisted worker execution records and behavioral errors."""

from __future__ import annotations

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
