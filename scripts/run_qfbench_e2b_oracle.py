#!/usr/bin/env python3
"""Run the pinned QFBench oracle in E2B and compare it with the local anchor."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import run as run_cli
from qea.benchmarks.qfbench import default_manifest_path, load_qfbench_snapshot
from qea.e2b_lease import E2BLeasePool
from qea.evaluation import TaskAttempt
from qea.executors.e2b_nexau import (
    E2BNexAUConfig,
    E2BOracleRunner,
    E2BQFBenchVerifier,
)
from qea.loop_benchmark import hash_worker_directory
from qea.oracle_parity import compare_oracle_artifacts


DEFAULT_ANCHOR = Path("results/qfbench_smoke/20260721T144046+0800_024921eb")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qfbench-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=default_manifest_path())
    parser.add_argument("--template-manifest-dir", type=Path, required=True)
    parser.add_argument("--task", default="historical-var-data-prep")
    parser.add_argument("--anchor-dir", type=Path, default=DEFAULT_ANCHOR)
    parser.add_argument("--results-dir", type=Path, default=Path("results/qfbench_oracle"))
    parser.add_argument("--run-id")
    parser.add_argument("--allow-verifier-network", action="store_true")
    parser.add_argument("--approve-paid-e2b", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_cli._load_dotenv()
    snapshot = load_qfbench_snapshot(args.qfbench_root, manifest_path=args.manifest)
    task = snapshot.task(args.task)
    anchor_dir = args.anchor_dir.resolve()
    anchor_status = json.loads((anchor_dir / "run_status.json").read_text())
    if anchor_status["benchmark"]["commit"] != snapshot.commit:
        raise ValueError("local oracle anchor commit does not match QFBench snapshot")
    if anchor_status["benchmark"]["task"] != task.task_id:
        raise ValueError("local oracle anchor task does not match requested task")
    if not args.approve_paid_e2b:
        print("NOT STARTED: pass --approve-paid-e2b to authorize the E2B oracle canary")
        return 2

    worker_templates, verifier_templates = run_cli.load_template_ids(
        args.template_manifest_dir, (task,), benchmark_commit=snapshot.commit
    )
    run_id = args.run_id or datetime.now(timezone.utc).strftime("oracle-%Y%m%dT%H%M%SZ")
    run_dir = args.results_dir.resolve() / run_id
    config = E2BNexAUConfig(
        worker_templates=worker_templates,
        verifier_templates=verifier_templates,
        worker_allow_internet=False,
        verifier_allow_internet=args.allow_verifier_network,
    )
    leases = E2BLeasePool(args.results_dir.resolve() / ".e2b-leases", max_leases=12)
    attempt = TaskAttempt.create(
        run_id=run_id,
        benchmark_commit=snapshot.commit,
        task_id=task.task_id,
        split="oracle",
        checkpoint="e2b-oracle-parity",
        worker_digest=hash_worker_directory(task.root / "solution"),
    )
    execution = E2BOracleRunner(config, lease_pool=leases).execute(
        attempt=attempt, task=task, run_dir=run_dir
    )
    score = E2BQFBenchVerifier(config, lease_pool=leases).verify(
        attempt=attempt, task=task, execution=execution, run_dir=run_dir
    )
    parity = compare_oracle_artifacts(anchor_dir / "oracle_output", execution.artifact_dir)

    expected_reward = float(anchor_status["oracle"]["reward"])
    expected_passed = int(anchor_status["oracle"]["pytest_passed"])
    expected_failed = int(anchor_status["oracle"]["pytest_failed"])
    accepted = (
        score.reward == expected_reward
        and score.tests_passed == expected_passed
        and score.tests_failed == expected_failed
        and parity.matches
        and execution.cleaned_up
    )
    payload = {
        "run_id": run_id,
        "benchmark_commit": snapshot.commit,
        "task_id": task.task_id,
        "expected": {
            "reward": expected_reward,
            "pytest_passed": expected_passed,
            "pytest_failed": expected_failed,
        },
        "e2b_score": asdict(score),
        "artifact_parity": asdict(parity),
        "worker_sandbox_cleaned_up": execution.cleaned_up,
        "accepted": accepted,
    }
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "parity.json").write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")
    print(json.dumps(payload, sort_keys=True, indent=2))
    return 0 if accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
