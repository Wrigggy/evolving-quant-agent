#!/usr/bin/env python3
"""Re-score saved QFBench Worker artifacts without new model calls."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.benchmarks.qfbench import load_qfbench_baseline_snapshot
from qea.evaluation import TaskAttempt
from qea.executors.execution_record import load_worker_execution
from qea.rootless_full_harness import (
    build_rootless_full_harness_runtime,
    load_rootless_full_harness_config,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qfbench-root", type=Path, required=True)
    parser.add_argument("--qfbench-manifest", type=Path, required=True)
    parser.add_argument("--rootless-config", type=Path, required=True)
    parser.add_argument("--rootless-image-set-manifest", type=Path, required=True)
    parser.add_argument("--source-run", type=Path, required=True, action="append")
    parser.add_argument("--output-run", type=Path, required=True)
    parser.add_argument("--task", action="append", required=True)
    args = parser.parse_args()

    output = args.output_run.expanduser().resolve()
    if output.exists():
        raise SystemExit(f"refusing existing replay output {output}")

    snapshot = load_qfbench_baseline_snapshot(
        args.qfbench_root,
        manifest_path=args.qfbench_manifest,
    )
    full_panel = snapshot.primary.tasks + snapshot.diagnostic.tasks
    tasks = {task.task_id: task for task in full_panel}
    unknown = sorted(set(args.task) - set(tasks))
    if unknown:
        raise SystemExit(f"unknown QFBench tasks: {unknown}")

    selected: dict[str, tuple[TaskAttempt, Path]] = {}
    for source in (path.expanduser().resolve() for path in args.source_run):
        for attempt_path in sorted((source / "attempts").glob("*/attempt.json")):
            payload = json.loads(attempt_path.read_text())
            task_id = payload.get("task_id")
            if task_id in args.task and task_id not in selected:
                selected[task_id] = (TaskAttempt(**payload), source)
    missing = sorted(set(args.task) - set(selected))
    if missing:
        raise SystemExit(f"saved runs have no attempts for: {missing}")

    runtime = build_rootless_full_harness_runtime(
        config=load_rootless_full_harness_config(args.rootless_config),
        image_set_manifest=args.rootless_image_set_manifest,
        benchmark_commit=snapshot.commit,
        tasks=full_panel,
        run_id=output.name,
        results_root=output.parent,
        include_evolver=False,
    )
    rows = []
    try:
        for task_id in args.task:
            attempt, source = selected[task_id]
            execution = load_worker_execution(attempt, source)
            if execution is None:
                raise SystemExit(f"saved attempt has no Worker execution: {task_id}")
            score = runtime.evaluator.verifier.verify(
                attempt=attempt,
                task=tasks[task_id],
                execution=execution,
                run_dir=output,
            )
            rows.append(
                {
                    "task_id": task_id,
                    "source_run": str(source),
                    "score": asdict(score),
                }
            )
    finally:
        runtime.close()

    result = {
        "schema_version": 1,
        "protocol": "qfbench-verifier-only-replay",
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
