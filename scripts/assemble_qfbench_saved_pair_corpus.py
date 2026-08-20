#!/usr/bin/env python3
"""Add one saved QFBench trajectory to an existing component-search corpus."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


def _json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required: {path}")
    return payload


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _saved_attempt(
    source_run: Path,
    task_id: str,
    *,
    attempt_id: str | None = None,
) -> Path:
    if attempt_id is not None:
        attempt = source_run / "attempts" / attempt_id
        attempt_payload = _json(attempt / "attempt.json")
        if attempt_payload.get("task_id") != task_id:
            raise ValueError(
                f"saved attempt {attempt_id} does not belong to {task_id}"
            )
        if not (attempt / "worker-execution.json").is_file():
            raise ValueError(f"saved attempt {attempt_id} has no Worker trajectory")
        return attempt
    for attempt_path in sorted((source_run / "attempts").glob("*/attempt.json")):
        if _json(attempt_path).get("task_id") != task_id:
            continue
        if (attempt_path.parent / "worker-execution.json").is_file():
            return attempt_path.parent
    raise ValueError(f"saved run has no complete Worker trajectory for {task_id}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-corpus", type=Path, required=True)
    parser.add_argument("--source-run", type=Path, required=True)
    parser.add_argument(
        "--attempt-id",
        help="Select a previously reviewed attempt instead of the first saved trajectory.",
    )
    parser.add_argument("--public-root", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--add-task", required=True)
    parser.add_argument("--existing-task", required=True)
    parser.add_argument("--add-evaluation", type=Path, required=True)
    parser.add_argument("--existing-evaluation", type=Path, required=True)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--state-tag", action="append", default=[])
    args = parser.parse_args(argv)

    destination = args.destination.expanduser().resolve()
    if destination.exists():
        raise ValueError(f"destination already exists: {destination}")
    shutil.copytree(args.base_corpus.expanduser().resolve(), destination)

    add_evaluation = _json(args.add_evaluation)
    existing_evaluation = _json(args.existing_evaluation)
    if add_evaluation.get("task_id") != args.add_task:
        raise ValueError("added evaluation task does not match")
    if existing_evaluation.get("task_id") != args.existing_task:
        raise ValueError("existing evaluation task does not match")

    catalog_path = destination / "tasks/CATALOG.json"
    catalog = _json(catalog_path)
    tasks = catalog.get("tasks")
    if not isinstance(tasks, list):
        raise ValueError("base corpus task catalog is invalid")
    existing_card = next(
        (
            row
            for row in tasks
            if isinstance(row, dict) and row.get("task_id") == args.existing_task
        ),
        None,
    )
    if existing_card is None:
        raise ValueError(f"base corpus has no task {args.existing_task}")
    existing_card["role"] = "protection"
    existing_card["answer_free_outcome"] = existing_evaluation
    existing_task_root = (
        destination / "benchmarks/qfbench/tasks" / args.existing_task
    )
    _write_json(existing_task_root / "public_evaluation.json", existing_evaluation)
    _write_json(
        destination / "tasks/cards" / f"qfbench--{args.existing_task}.json",
        existing_card,
    )

    attempt = _saved_attempt(
        args.source_run.expanduser().resolve(),
        args.add_task,
        attempt_id=args.attempt_id,
    )
    execution = _json(attempt / "worker-execution.json")
    artifact_dir = attempt / str(execution.get("artifact_dir", "artifacts"))
    trace = attempt / str(execution.get("trace_uri", "raw-trace.jsonl"))
    final = attempt / str(execution.get("final_text_uri", "final.txt"))
    public_instruction = (
        args.public_root.expanduser().resolve()
        / "tasks"
        / args.add_task
        / "instruction.md"
    )
    task_root = destination / "benchmarks/qfbench/tasks" / args.add_task
    task_root.mkdir(parents=True)
    shutil.copy2(public_instruction, task_root / "instruction.md")
    shutil.copy2(trace, task_root / "worker_trace.jsonl")
    shutil.copy2(final, task_root / "worker_final.txt")
    shutil.copytree(artifact_dir, task_root / "artifacts")
    _write_json(task_root / "public_evaluation.json", add_evaluation)
    _write_json(task_root / "process_summary.json", execution.get("summary", {}))
    artifact_rows = [
        {"path": path.relative_to(artifact_dir).as_posix(), "size_bytes": path.stat().st_size}
        for path in sorted(artifact_dir.rglob("*"))
        if path.is_file()
    ]
    _write_json(
        task_root / "artifact_manifest.json",
        {"schema_version": 1, "artifacts": artifact_rows},
    )

    task_key = f"qfbench:{args.add_task}"
    card = {
        "schema_version": 1,
        "task_key": task_key,
        "benchmark": "qfbench",
        "task_id": args.add_task,
        "role": "target",
        "domain": args.domain,
        "state_tags": list(dict.fromkeys(args.state_tag)),
        "execution_status": "complete",
        "evidence_completeness": "full_structured_trace",
        "answer_free_outcome": add_evaluation,
        "runtime_summary": execution.get("summary", {}),
        "artifact_paths": [row["path"] for row in artifact_rows],
        "evidence_paths": {
            "instruction": f"benchmarks/qfbench/tasks/{args.add_task}/instruction.md",
            "evaluation": f"benchmarks/qfbench/tasks/{args.add_task}/public_evaluation.json",
            "process": f"benchmarks/qfbench/tasks/{args.add_task}/process_summary.json",
            "trace": f"benchmarks/qfbench/tasks/{args.add_task}/worker_trace.jsonl",
            "final": f"benchmarks/qfbench/tasks/{args.add_task}/worker_final.txt",
            "artifacts": f"benchmarks/qfbench/tasks/{args.add_task}/artifacts",
        },
    }
    tasks.append(card)
    catalog["task_count"] = len(tasks)
    _write_json(catalog_path, catalog)
    _write_json(
        destination / "tasks/cards" / f"qfbench--{args.add_task}.json", card
    )

    relevant_path = destination / "tasks/RELEVANT_COMPONENTS.json"
    relevant = _json(relevant_path)
    relevant_rows = relevant.get("tasks")
    if not isinstance(relevant_rows, list):
        raise ValueError("base corpus relevant-component index is invalid")
    relevant_rows.append({"task_key": task_key, "components": []})
    _write_json(relevant_path, relevant)
    _write_json(
        destination / "ASSEMBLY-RECORD.json",
        {
            "schema_version": 1,
            "protocol": "saved_qfbench_pair_corpus",
            "base_corpus": str(args.base_corpus),
            "source_run": str(args.source_run),
            "attempt_id": attempt.name,
            "added_task": args.add_task,
            "existing_task": args.existing_task,
            "worker_model_requests": 0,
        },
    )
    print(json.dumps({"destination": str(destination), "task_key": task_key}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
