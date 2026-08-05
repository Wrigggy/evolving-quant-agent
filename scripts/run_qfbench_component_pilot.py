#!/usr/bin/env python3
"""Evaluate a few worker harness arms on an exact QFBench task subset.

The rootless runtime is still assembled against the immutable full 85-task image
and material panel. Only the requested public tasks are executed. This keeps the
official verifier firewall and image identities unchanged while making an A1-A3
mechanism canary affordable and resumable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import asdict, replace
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.benchmarks.qfbench import load_qfbench_baseline_snapshot  # noqa: E402
from qea.candidate_admission import AdmissionPolicy, admit_candidate  # noqa: E402
from qea.loop_benchmark import hash_worker_directory  # noqa: E402
from qea.rootless_full_harness import (  # noqa: E402
    build_rootless_full_harness_runtime,
    load_rootless_full_harness_config,
)


_LABEL = re.compile(r"[a-z0-9][a-z0-9_-]{0,47}\Z")
_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")
    os.replace(temporary, path)


def _arm(value: str) -> tuple[str, Path]:
    label, separator, raw_path = value.partition("=")
    if not separator or _LABEL.fullmatch(label) is None:
        raise argparse.ArgumentTypeError("arm must be LABEL=PATH with a safe label")
    path = Path(raw_path).expanduser().resolve()
    if not path.is_dir():
        raise argparse.ArgumentTypeError(f"worker arm is unavailable: {path}")
    return label, path


def _summary_payload(summary) -> dict[str, object]:
    return {
        "scores": [asdict(score) for score in summary.scores],
        "task_rewards": dict(summary.task_rewards),
        "domain_scores": dict(summary.domain_scores),
        "task_mean": summary.task_mean,
        "overall": summary.overall,
    }


def _activation_payload(run_dir: Path, checkpoint: str, token: str | None) -> dict:
    attempts: list[dict[str, object]] = []
    for attempt_path in sorted(run_dir.glob("attempts/*/attempt.json")):
        attempt = json.loads(attempt_path.read_text())
        if attempt.get("checkpoint") != checkpoint:
            continue
        trace_path = attempt_path.with_name("raw-trace.jsonl")
        trace = trace_path.read_text(errors="replace") if trace_path.is_file() else ""
        marker = (
            token is not None
            and token in trace
            and ("<SkillDetails>" in trace or "Found the skill details" in trace)
        )
        attempts.append({
            "attempt_id": attempt.get("attempt_id"),
            "task_id": attempt.get("task_id"),
            "trace_path": trace_path.relative_to(run_dir).as_posix(),
            "activation_token": token,
            "activated": marker,
            "trace_sha256": _sha256(trace_path) if trace_path.is_file() else None,
        })
    return {
        "checkpoint": checkpoint,
        "attempts": attempts,
        "activation_count": sum(bool(item["activated"]) for item in attempts),
    }


def _cost_payload(run_dir: Path) -> dict[str, object]:
    completed = []
    failures = []
    for path in sorted(run_dir.glob("attempts/*/proxy-audit.jsonl")):
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("request_state") == "completed":
                completed.append(record)
            else:
                failures.append(record)
    costs = [record.get("provider_cost_usd") for record in completed]
    tokens = [record.get("total_tokens") for record in completed]
    return {
        "completed_request_count": len(completed),
        "noncompleted_request_count": len(failures),
        "provider_cost_usd": (
            sum(float(value) for value in costs)
            if completed and all(isinstance(value, (int, float)) for value in costs)
            else None
        ),
        "total_tokens": (
            sum(int(value) for value in tokens)
            if completed and all(isinstance(value, int) for value in tokens)
            else None
        ),
        "missing_cost_count": sum(value is None for value in costs),
        "missing_token_count": sum(value is None for value in tokens),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qfbench-root", type=Path, required=True)
    parser.add_argument("--qfbench-manifest", type=Path, required=True)
    parser.add_argument("--rootless-config", type=Path, required=True)
    parser.add_argument("--rootless-image-set-manifest", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--seed-worker", type=Path, required=True)
    parser.add_argument("--arm", action="append", type=_arm, required=True)
    parser.add_argument("--task-id", action="append", required=True)
    parser.add_argument("--checkpoint-prefix", default="component-pilot")
    parser.add_argument("--activation-token")
    parser.add_argument("--worker-concurrency", type=int)
    parser.add_argument("--verifier-concurrency", type=int)
    parser.add_argument("--approve-external-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if _RUN_ID.fullmatch(args.run_id) is None:
        raise ValueError("run ID is unsafe")
    if not args.approve_external_run and os.environ.get(
        "QEA_PAID_EVAL_AUTO_APPROVE"
    ) != "1":
        raise ValueError("external worker/model execution was not approved")
    arms = tuple(args.arm)
    if len({label for label, _ in arms}) != len(arms):
        raise ValueError("worker arm labels must be unique")
    task_ids = tuple(args.task_id)
    if len(set(task_ids)) != len(task_ids):
        raise ValueError("task IDs must be unique")

    snapshot = load_qfbench_baseline_snapshot(
        args.qfbench_root,
        manifest_path=args.qfbench_manifest,
    )
    full_panel = snapshot.primary.tasks + snapshot.diagnostic.tasks
    tasks_by_id = {task.task_id: task for task in full_panel}
    missing = sorted(set(task_ids) - set(tasks_by_id))
    if missing:
        raise ValueError(f"unknown or excluded QFBench tasks: {missing}")
    selected_tasks = tuple(tasks_by_id[task_id] for task_id in task_ids)

    seed = args.seed_worker.resolve()
    policy = AdmissionPolicy.qfbench_full()
    arm_payloads = []
    for label, worker in arms:
        admission = admit_candidate(seed, worker, policy)
        arm_payloads.append({
            "label": label,
            "worker_dir": str(worker),
            "worker_digest": hash_worker_directory(worker),
            "admission": asdict(admission),
        })

    results_root = args.results_dir.expanduser().resolve()
    run_dir = results_root / args.run_id
    plan = {
        "schema_version": 1,
        "run_id": args.run_id,
        "benchmark_commit": snapshot.commit,
        "task_ids": list(task_ids),
        "checkpoint_prefix": args.checkpoint_prefix,
        "activation_token": args.activation_token,
        "arms": arm_payloads,
        "qfbench_manifest_sha256": _sha256(args.qfbench_manifest.resolve()),
        "rootless_config_sha256": _sha256(args.rootless_config.resolve()),
        "image_set_sha256": _sha256(args.rootless_image_set_manifest.resolve()),
    }
    plan_path = run_dir / "pilot-plan.json"
    if plan_path.is_file() and json.loads(plan_path.read_text()) != plan:
        raise ValueError("existing pilot plan identity differs")
    _atomic_json(plan_path, plan)

    config = load_rootless_full_harness_config(args.rootless_config)
    overrides = {}
    if args.worker_concurrency is not None:
        overrides["worker_concurrency"] = args.worker_concurrency
    if args.verifier_concurrency is not None:
        overrides["verifier_concurrency"] = args.verifier_concurrency
    if overrides:
        config = replace(config, **overrides)

    runtime = build_rootless_full_harness_runtime(
        config=config,
        image_set_manifest=args.rootless_image_set_manifest,
        benchmark_commit=snapshot.commit,
        tasks=full_panel,
        run_id=args.run_id,
        results_root=results_root,
        include_evolver=False,
    )
    summaries: dict[str, object] = {}
    activations: dict[str, object] = {}
    try:
        for label, worker in arms:
            checkpoint = f"{args.checkpoint_prefix}-{label}"
            summary = runtime.evaluator.evaluate(
                worker_dir=worker,
                tasks=selected_tasks,
                split="mechanism-pilot",
                checkpoint=checkpoint,
                run_dir=run_dir,
            )
            summaries[label] = _summary_payload(summary)
            activations[label] = _activation_payload(
                run_dir, checkpoint, args.activation_token
            )
            _atomic_json(run_dir / "pilot-progress.json", {
                "schema_version": 1,
                "run_id": args.run_id,
                "completed_arms": list(summaries),
                "summaries": summaries,
                "activations": activations,
                "status": "running",
            })
    finally:
        runtime.close()

    report = {
        "schema_version": 1,
        "run_id": args.run_id,
        "status": "complete",
        "task_ids": list(task_ids),
        "summaries": summaries,
        "activations": activations,
        "cost": _cost_payload(run_dir),
    }
    _atomic_json(run_dir / "pilot-report.json", report)
    _atomic_json(run_dir / "pilot-progress.json", report)
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
