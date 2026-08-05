import hashlib

import pytest

from qea.evaluation import TaskAttempt


def _attempt() -> TaskAttempt:
    return TaskAttempt.create(
        run_id="run-001",
        benchmark_commit="0" * 40,
        task_id="fixture-task",
        split="optimize",
        checkpoint="seed",
        worker_digest="a" * 64,
    )


def _existing_e2b_manifest(attempt_id: str) -> str:
    artifact_sha256 = hashlib.sha256(b"42\n").hexdigest()
    return (
        "{\n"
        '  "artifact_dir": "artifacts",\n'
        '  "artifacts": [\n'
        "    {\n"
        '      "path": "answer.txt",\n'
        f'      "sha256": "{artifact_sha256}",\n'
        '      "size_bytes": 3\n'
        "    }\n"
        "  ],\n"
        f'  "attempt_id": "{attempt_id}",\n'
        '  "cleaned_up": true,\n'
        '  "final_text_uri": "final.txt",\n'
        '  "log_uri": "worker-command.json",\n'
        '  "sandbox_id": "sandbox-worker-123",\n'
        '  "summary": {\n'
        '    "files": 1,\n'
        '    "turns": 2\n'
        "  },\n"
        '  "trace_uri": "raw-trace.jsonl"\n'
        "}\n"
    )


def _write_existing_attempt(tmp_path):
    attempt = _attempt()
    attempt_dir = tmp_path / "run" / "attempts" / attempt.attempt_id
    artifact_dir = attempt_dir / "artifacts"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "answer.txt").write_bytes(b"42\n")
    (attempt_dir / "raw-trace.jsonl").write_text('{"role":"assistant"}\n')
    (attempt_dir / "worker-command.json").write_text("{}\n")
    (attempt_dir / "final.txt").write_text("done\n")
    manifest = _existing_e2b_manifest(attempt.attempt_id)
    (attempt_dir / "worker-execution.json").write_text(manifest)
    return attempt, attempt_dir, manifest


def test_neutral_api_round_trips_existing_e2b_manifest_byte_for_byte(tmp_path):
    from qea.executors.execution_record import (
        WorkerExecution,
        load_worker_execution,
        persist_worker_execution,
    )

    attempt, attempt_dir, original_bytes = _write_existing_attempt(tmp_path)

    execution = load_worker_execution(attempt, tmp_path / "run")

    assert isinstance(execution, WorkerExecution)
    assert execution.attempt_id == attempt.attempt_id
    assert execution.artifact_dir == (attempt_dir / "artifacts").resolve()
    assert execution.trace_uri == str((attempt_dir / "raw-trace.jsonl").resolve())
    assert execution.log_uri == str((attempt_dir / "worker-command.json").resolve())
    assert execution.final_text_uri == str((attempt_dir / "final.txt").resolve())
    assert execution.summary == {"files": 1, "turns": 2}
    assert execution.sandbox_id == "sandbox-worker-123"
    assert execution.cleaned_up is True

    persist_worker_execution(execution, attempt_dir)

    assert (attempt_dir / "worker-execution.json").read_text() == original_bytes


def test_neutral_loader_rehashes_every_persisted_artifact(tmp_path):
    from qea.executors.execution_record import (
        WorkerExecutionError,
        load_worker_execution,
    )

    attempt, attempt_dir, _ = _write_existing_attempt(tmp_path)
    (attempt_dir / "artifacts" / "answer.txt").write_bytes(b"tampered\n")

    with pytest.raises(WorkerExecutionError, match="artifact integrity mismatch"):
        load_worker_execution(attempt, tmp_path / "run")


def test_e2b_record_and_timeout_names_are_compatibility_aliases():
    from qea.executors.e2b_nexau import (
        E2BExecutionError,
        E2BWorkerExecution,
        E2BWorkerTimeout,
    )
    from qea.executors.execution_record import (
        WorkerBehaviorTimeout,
        WorkerExecution,
    )

    assert E2BWorkerExecution is WorkerExecution
    assert E2BWorkerTimeout is WorkerBehaviorTimeout
    assert issubclass(E2BWorkerTimeout, E2BExecutionError)


def _write_worker_command(attempt_dir, *, timed_out: bool, exit_code: int) -> None:
    import json

    attempt_dir.mkdir(parents=True, exist_ok=True)
    (attempt_dir / "worker-command.json").write_text(
        json.dumps(
            {
                "exit_code": exit_code,
                "stdout": "",
                "stderr": "",
                "timed_out": timed_out,
            },
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )


def test_completed_worker_command_without_quarantine_is_not_a_timeout(tmp_path):
    """A normally exited worker is absence of timeout evidence, not a pairing fault."""

    from qea.executors.execution_record import load_persisted_worker_timeout

    attempt = _attempt()
    attempt_dir = tmp_path / "run" / "attempts" / attempt.attempt_id
    _write_worker_command(attempt_dir, timed_out=False, exit_code=0)

    assert load_persisted_worker_timeout(attempt, tmp_path / "run") is None


def test_timed_out_worker_command_without_quarantine_is_unpaired(tmp_path):
    """Genuine timeout evidence still requires its quarantine counterpart."""

    from qea.executors.execution_record import (
        WorkerExecutionError,
        load_persisted_worker_timeout,
    )

    attempt = _attempt()
    attempt_dir = tmp_path / "run" / "attempts" / attempt.attempt_id
    _write_worker_command(attempt_dir, timed_out=True, exit_code=124)

    with pytest.raises(WorkerExecutionError, match="must be paired"):
        load_persisted_worker_timeout(attempt, tmp_path / "run")
