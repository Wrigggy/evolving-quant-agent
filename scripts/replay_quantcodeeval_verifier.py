#!/usr/bin/env python3
"""Re-score saved QuantCodeEval worker artifacts without model calls."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.backends.rootless_docker import RootlessDockerBackend
from qea.benchmarks.quantcodeeval import load_quantcodeeval_snapshot
from qea.evaluation import TaskAttempt
from qea.executors.execution_record import load_worker_execution
from qea.executors.sandbox_runtime import SandboxResourceContract
from qea.verifiers.quantcodeeval_sandbox import IsolatedQuantCodeEvalVerifier


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--public-root", type=Path, required=True)
    parser.add_argument("--trusted-root", type=Path, required=True)
    parser.add_argument("--task-panel", type=Path, required=True)
    parser.add_argument("--source-run", type=Path, required=True)
    parser.add_argument("--output-run", type=Path, required=True)
    parser.add_argument("--verifier-image", required=True)
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
    source = args.source_run.resolve()
    tasks = {task.task_id: task for task in snapshot.optimize.tasks}
    rows = []
    for attempt_path in sorted((source / "attempts").glob("*/attempt.json")):
        payload = json.loads(attempt_path.read_text())
        task_id = payload.get("task_id")
        if task_id not in tasks:
            continue
        attempt = TaskAttempt(**payload)
        execution = load_worker_execution(attempt, source)
        if execution is None:
            raise SystemExit(f"{task_id} has no completed worker artifact")
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
            "score": asdict(score),
            "answer_free_evidence": json.loads(answer_path.read_text()),
        })
    missing = sorted(set(tasks) - {row["task_id"] for row in rows})
    if missing:
        raise SystemExit(f"source run has no completed artifacts for {missing}")
    result = {
        "schema_version": 1,
        "protocol": "quantcodeeval-verifier-only-replay",
        "source_run": str(source),
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
