#!/usr/bin/env python3
"""Run no-model, no-network canaries for published QFBench verifier templates."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.benchmarks.qfbench import default_manifest_path, load_qfbench_snapshot
from qea.e2b_lease import E2BLeasePool
from qea.e2b_reaper import reap_e2b_sandboxes
from qea.evaluation import OfficialTaskScore, TaskAttempt
from qea.executors.e2b_nexau import E2BNexAUConfig, E2BQFBenchVerifier


DEFAULT_TASKS = (
    "delta-hedging-pnl-simulation",
    "swap-curve-bootstrap-ois",
    "form4-cross-sectional-sale-pressure",
)


_DEPENDENCY_FAILURE_MARKERS = (
    "No solution found when resolving tool dependencies",
    "Packages were unavailable because the network was disabled",
)


def _read_json(path: Path) -> dict:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return payload


def _assess_evidence(score: OfficialTaskScore, verifier_dir: Path) -> dict:
    """Accept only real offline test execution with complete cleanup evidence."""

    command = _read_json(verifier_dir / "verifier-command.trusted.json")
    harness = _read_json(verifier_dir / "verifier-harness.json")
    lifecycle = _read_json(verifier_dir / "verifier-sandbox-lifecycle.json")
    dependency_lock = (verifier_dir / "verifier-requirements.lock").read_text()
    tests_executed = int(score.tests_passed or 0) + int(score.tests_failed or 0)
    output = f"{command.get('stdout', '')}\n{command.get('stderr', '')}"

    failures: list[str] = []
    if tests_executed == 0:
        failures.append("no official tests executed")
    if all(marker in output for marker in _DEPENDENCY_FAILURE_MARKERS):
        failures.append("offline dependency resolution failed")
    if not dependency_lock.strip():
        failures.append("verifier dependency lock is empty")
    for key in ("official_sha256", "executed_sha256", "dependency_lock_sha256"):
        if not harness.get(key):
            failures.append(f"missing {key}")
    if harness.get("offline_transformed") is not True:
        failures.append("verifier was not transformed for offline execution")
    if lifecycle.get("cleaned_up") is not True:
        failures.append("verifier sandbox was not cleaned up")

    return {
        "task_id": score.task_id,
        "score": asdict(score),
        "tests_executed": tests_executed,
        "dependency_lock_sha256": hashlib.sha256(dependency_lock.encode()).hexdigest(),
        "sandbox_id": lifecycle.get("sandbox_id"),
        "cleaned_up": lifecycle.get("cleaned_up") is True,
        "failure_reasons": failures,
        "accepted": not failures,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qfbench-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=default_manifest_path())
    parser.add_argument("--template-manifest-dir", type=Path, required=True)
    parser.add_argument("--task", action="append", dest="tasks")
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("results/qfbench_verifier_canary"),
    )
    parser.add_argument("--run-id")
    parser.add_argument("--approve-paid-e2b", action="store_true")
    return parser


def _load_verifier_templates(
    directory: Path,
    tasks: tuple,
    commit: str,
) -> dict[str, str]:
    templates: dict[str, str] = {}
    for task in tasks:
        path = directory / f"{task.task_id}.verifier.image.json"
        payload = _read_json(path)
        expected = (task.task_id, "verifier", commit)
        actual = (
            payload.get("task_id"),
            payload.get("role"),
            payload.get("benchmark_commit"),
        )
        if actual != expected:
            raise ValueError(f"verifier manifest identity mismatch: {path}")
        if not payload.get("verifier_uvx_warm_command"):
            raise ValueError(f"verifier manifest has no uvx warm command: {path}")
        template_id = payload.get("published_template_id")
        build_id = payload.get("published_build_id")
        if not template_id or not build_id:
            raise ValueError(f"verifier manifest is not published: {path}")
        templates[task.task_id] = str(template_id)
    return templates


def _failed_result(task_id: str, exc: Exception) -> dict:
    return {
        "task_id": task_id,
        "score": None,
        "tests_executed": 0,
        "dependency_lock_sha256": None,
        "sandbox_id": None,
        "cleaned_up": False,
        "failure_reasons": ["verifier canary execution failed"],
        "error_type": type(exc).__name__,
        "accepted": False,
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.approve_paid_e2b:
        print(
            "NOT STARTED: pass --approve-paid-e2b to authorize the paid E2B "
            "verifier canary"
        )
        return 2

    selected_ids = tuple(args.tasks or DEFAULT_TASKS)
    if len(selected_ids) != len(set(selected_ids)):
        raise ValueError("verifier canary task IDs must be unique")
    unsupported = sorted(set(selected_ids) - set(DEFAULT_TASKS))
    if unsupported:
        raise ValueError(f"unsupported verifier repair canary tasks: {unsupported}")

    snapshot = load_qfbench_snapshot(
        args.qfbench_root,
        manifest_path=args.manifest,
    )
    tasks = tuple(snapshot.task(task_id) for task_id in selected_ids)
    templates = _load_verifier_templates(
        args.template_manifest_dir,
        tasks,
        snapshot.commit,
    )
    run_id = args.run_id or datetime.now(timezone.utc).strftime(
        "verifier-cache-%Y%m%dT%H%M%SZ"
    )
    results_root = args.results_dir.resolve()
    run_dir = results_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    config = E2BNexAUConfig(
        worker_templates={},
        verifier_templates=templates,
        worker_allow_internet=False,
        verifier_allow_internet=False,
    )
    leases = E2BLeasePool(results_root / ".e2b-leases", max_leases=12)
    verifier = E2BQFBenchVerifier(config, lease_pool=leases)
    worker_digest = hashlib.sha256(
        b"qfbench-verifier-canary-empty-artifacts-v1"
    ).hexdigest()

    results: list[dict] = []
    for task in tasks:
        attempt = TaskAttempt.create(
            run_id=run_id,
            benchmark_commit=snapshot.commit,
            task_id=task.task_id,
            split="verifier_canary",
            checkpoint="empty-artifacts-offline-cache",
            worker_digest=worker_digest,
        )
        attempt_dir = run_dir / "attempts" / attempt.attempt_id
        artifact_dir = attempt_dir / "empty-artifacts"
        artifact_dir.mkdir(parents=True)
        try:
            score = verifier.verify(
                attempt=attempt,
                task=task,
                execution=SimpleNamespace(artifact_dir=artifact_dir),
                run_dir=run_dir,
            )
            results.append(
                _assess_evidence(score, attempt_dir / "verifier")
            )
        except Exception as exc:  # noqa: BLE001 - preserve per-task cleanup audit.
            results.append(_failed_result(task.task_id, exc))

    reaper = reap_e2b_sandboxes(
        run_dir,
        kill_sandbox=lambda sandbox_id: False,
        apply=False,
    )
    payload = {
        "schema_version": 1,
        "run_id": run_id,
        "benchmark_commit": snapshot.commit,
        "model_calls": 0,
        "worker_sandboxes": 0,
        "verifier_sandboxes_expected": len(tasks),
        "results": results,
        "final_pending_ids": list(reaper.pending_ids),
        "accepted": (
            all(item["accepted"] for item in results)
            and not reaper.pending_ids
        ),
    }
    summary_path = run_dir / "canary-summary.json"
    summary_path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")
    print(json.dumps(payload, sort_keys=True, indent=2))
    return 0 if payload["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
