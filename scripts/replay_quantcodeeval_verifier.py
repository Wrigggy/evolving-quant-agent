#!/usr/bin/env python3
"""Re-score saved QuantCodeEval worker artifacts without model calls."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import asdict
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.backends.rootless_docker import RootlessDockerBackend
from qea.benchmarks.quantcodeeval import load_quantcodeeval_snapshot
from qea.evaluation import ArtifactRecord, TaskAttempt
from qea.executors.execution_record import WorkerExecution, load_worker_execution
from qea.executors.sandbox_runtime import SandboxResourceContract
from qea.verifiers.quantcodeeval_sandbox import IsolatedQuantCodeEvalVerifier


def _replay_execution(
    attempt: TaskAttempt,
    source_run: Path,
    replay_root: Path | None = None,
) -> tuple[WorkerExecution, bool]:
    execution = load_worker_execution(attempt, source_run)
    if execution is not None:
        return execution, False
    attempt_dir = source_run / "attempts" / attempt.attempt_id
    contract_path = attempt_dir / "worker-artifact-contract.json"
    if not contract_path.is_file():
        raise RuntimeError(f"{attempt.task_id} has no completed worker artifact")
    contract = json.loads(contract_path.read_text())
    source_artifact_dir = attempt_dir / "artifacts"
    strategy = source_artifact_dir / "strategy.py"
    if contract.get("outcome") != "official_worker_artifact_contract_zero" or not strategy.is_file():
        raise RuntimeError(f"{attempt.task_id} has no replayable strategy.py")
    artifact_dir = (
        replay_root / "fixtures" / attempt.attempt_id / "artifacts"
        if replay_root is not None
        else source_artifact_dir
    )
    if replay_root is not None:
        artifact_dir.mkdir(parents=True)
        shutil.copyfile(strategy, artifact_dir / "strategy.py")
        strategy = artifact_dir / "strategy.py"
    return WorkerExecution(
        attempt_id=attempt.attempt_id,
        artifact_dir=artifact_dir,
        artifacts=(ArtifactRecord.from_file(strategy, root=artifact_dir),),
        trace_uri=str(attempt_dir / "raw-trace.jsonl"),
        log_uri=str(attempt_dir / "worker-command.json"),
        final_text_uri=str(attempt_dir / "final.txt"),
        summary={"contract_adjusted_replay": True},
        sandbox_id="saved-worker-artifact",
        cleaned_up=True,
    ), True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--public-root", type=Path, required=True)
    parser.add_argument("--trusted-root", type=Path, required=True)
    parser.add_argument("--task-panel", type=Path, required=True)
    parser.add_argument("--source-run", type=Path, required=True, action="append")
    parser.add_argument("--output-run", type=Path, required=True)
    parser.add_argument("--verifier-image", required=True)
    parser.add_argument(
        "--task",
        action="append",
        help="Replay only the named task(s) from the bound panel.",
    )
    args = parser.parse_args()

    output = args.output_run.resolve()
    if output.exists():
        raise SystemExit(f"refusing existing replay output {output}")
    output.mkdir(parents=True)
    config = json.loads(args.config.read_text())
    snapshot = load_quantcodeeval_snapshot(
        args.public_root,
        task_panel_path=args.task_panel,
    )
    backend = RootlessDockerBackend(
        docker_host=str(config["docker_host"]),
        expected_uid=int(config["expected_uid"]),
    )
    backend.preflight(
        expected_server_version="29.4.1",
        expected_security_options=(
            "name=seccomp,profile=builtin",
            "name=rootless",
            "name=cgroupns",
        ),
        image_ids=(args.verifier_image,),
    )
    verifier = IsolatedQuantCodeEvalVerifier(
        backend=backend,
        lifecycle_root=output / "lifecycles",
        verifier_image_ref=args.verifier_image,
        public_task_root=args.public_root,
        trusted_task_root=args.trusted_root,
        resource_contract=SandboxResourceContract(
            cpu_count=2,
            memory_mb=4096,
            pids_limit=256,
            timeout_seconds=3600,
            writable_tmpfs_mb={
                "/tmp": 256,
                "/qea": 512,
                "/app": 1024,
                "/tests": 128,
                "/logs": 64,
                "/opt/qea/uv-cache": 256,
                "/opt/qea/uv-tools": 64,
            },
        ),
    )
    sources = tuple(path.resolve() for path in args.source_run)
    tasks = {task.task_id: task for task in snapshot.optimize.tasks}
    if args.task:
        requested = set(args.task)
        unknown = sorted(requested - set(tasks))
        if unknown:
            raise SystemExit(f"task panel has no optimize tasks {unknown}")
        tasks = {
            task_id: task
            for task_id, task in tasks.items()
            if task_id in requested
        }
    rows = []
    seen = set()
    for source in sources:
        for attempt_path in sorted((source / "attempts").glob("*/attempt.json")):
            payload = json.loads(attempt_path.read_text())
            task_id = payload.get("task_id")
            if task_id not in tasks or task_id in seen:
                continue
            attempt = TaskAttempt(**payload)
            try:
                execution, contract_adjusted = _replay_execution(
                    attempt,
                    source,
                    output,
                )
            except RuntimeError:
                continue
            score = verifier.verify(
                attempt=attempt,
                task=tasks[task_id],
                execution=execution,
                run_dir=output,
            )
            answer_path = output / "attempts" / attempt.attempt_id / "verifier" / "answer-free-evidence.json"
            rows.append({
                "task_id": task_id,
                "attempt_id": attempt.attempt_id,
                "source_run": str(source),
                "contract_adjusted": contract_adjusted,
                "score": asdict(score),
                "answer_free_evidence": json.loads(answer_path.read_text()),
            })
            seen.add(task_id)
    missing = sorted(set(tasks) - {row["task_id"] for row in rows})
    if missing:
        raise SystemExit(f"source run has no completed artifacts for {missing}")
    result = {
        "schema_version": 1,
        "protocol": "quantcodeeval-verifier-only-replay",
        "source_runs": [str(source) for source in sources],
        "zero_model_requests": True,
        "results": rows,
    }
    (output / "REPLAY-RESULT.json").write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n"
    )
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
