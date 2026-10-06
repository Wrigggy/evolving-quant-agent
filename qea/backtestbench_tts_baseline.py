"""Test-time-scaling (TTS) baseline for BacktestBench campaigns.

Runs best-of-K parallel Workers from the frozen initial harness on a declared
task set, at matched total compute to the evolution campaign. This provides
the critical comparison baseline required by arxiv:2607.12227: does harness
evolution outperform simply running more parallel Workers at the same cost?

Design:
- K Workers run in parallel on each task, each with identical public inputs
  and the unchanged initial H (no Evolver, no harness mutation)
- Per-task winner = majority vote on the binary reward; ties resolved by
  the attempt with the highest passed-check count, then earlier registration
- The TTS endpoint compares initial H baseline (K=1) vs. TTS (K=N) on the
  same task set and the same initial H, so any TTS gain is attributable only
  to sampling variance, not capability improvement
- A separate evolution campaign comparison is: evolution_frozen_score vs.
  tts_score at matched cost

This module is intentionally parallel in structure to backtestbench_panel.py
but does not use an Evolver and does not modify the worker harness.

Usage:
    from qea.backtestbench_tts_baseline import run_backtestbench_tts_baseline
    result = run_backtestbench_tts_baseline(
        config_path=...,
        public_root=...,
        trusted_root=...,
        run_dir=...,
        worker_dir=...,
        task_ids=...,
        k_samples=4,   # number of parallel Workers per task
        ...
    )
"""

from __future__ import annotations

import json
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from .backtestbench_panel import (
    RESULT_FILE as PANEL_RESULT_FILE,
    STATE_FILE as PANEL_STATE_FILE,
    _public_task,
    _worker_settings,
    BacktestBenchPanelError,
)
from .benchmarks.backtestbench import (
    BacktestBenchTask,
    grade_submission,
    project_public_task,
)
from .evaluation import TaskAttempt
from .executors.execution_record import WorkerExecution, persist_worker_execution
from .executors.sandbox_evolver import _combined_request
from .executors.sandbox_nexau import SandboxNexAUExecutor
from .executors.sandbox_runtime import SandboxInfrastructureError, SandboxResourceContract
from .quantcodeeval_baseline import _atomic_private_json
from .quantcodeeval_behavior_revision import _prepare_revision_runtime
from .rootless_full_harness import _CoordinatorLock, load_rootless_full_harness_config
from .worker_identity import hash_worker_directory


STATE_FILE = "BACKTESTBENCH-TTS-STATE.json"
RESULT_FILE = "BACKTESTBENCH-TTS-RESULT.json"
PROTOCOL = "backtestbench-tts-baseline-v1"


class BacktestBenchTTSError(ValueError):
    """A TTS baseline run cannot be started or safely resumed."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class TTSTaskResult:
    task_id: str
    k_samples: int
    attempts: list[dict]          # per-attempt reward + cost
    majority_reward: int           # 0 or 1 by majority vote (ties go to 0)
    winning_attempt_id: str | None # attempt with highest passed count (or None on all-fail)
    passed: int                    # passed checks of winning attempt
    total: int                     # total checks of winning attempt
    cost_usd: float                # total cost for all K attempts on this task


def _majority_vote(attempts: list[dict]) -> tuple[int, str | None, int, int]:
    """Return (majority_reward, winning_attempt_id, passed, total)."""
    ones = [a for a in attempts if a.get("reward") == 1]
    zeros = [a for a in attempts if a.get("reward") == 0]
    # Majority vote
    if len(ones) > len(zeros):
        pool = ones
        majority = 1
    elif len(zeros) > len(ones):
        pool = zeros
        majority = 0
    else:
        # Tie: conservative — reward 0
        pool = ones  # pick best of ties by quality
        majority = 0

    if not pool:
        return 0, None, 0, 0

    # Break ties by passed count, then earlier registration
    best = max(pool, key=lambda a: (a.get("passed", 0), -a.get("attempt_index", 0)))
    return majority, best.get("attempt_id"), best.get("passed", 0), best.get("total", 1)


def run_backtestbench_tts_baseline(
    *,
    config_path: str | Path,
    public_root: str | Path,
    trusted_root: str | Path,
    run_dir: str | Path,
    worker_dir: str | Path,
    task_ids: Sequence[str],
    worker_image_ref: str,
    proxy_image_ref: str,
    k_samples: int = 4,
    concurrency: int = 4,
    scoring_mode: str = "official",
) -> dict:
    """Run K parallel Workers per task on the unchanged initial harness.

    Returns a result dict with per-task majority-vote rewards and full
    accounting for all K*N Worker calls. Does not run an Evolver or modify H.

    k_samples: number of independent Workers per task (default 4)
    concurrency: total parallel Workers across all tasks (default 4)
    """
    if type(k_samples) is not int or k_samples < 1:
        raise BacktestBenchTTSError("k_samples must be a positive integer")
    if type(concurrency) is not int or concurrency < 1:
        raise BacktestBenchTTSError("concurrency must be a positive integer")

    run_root = Path(run_dir).expanduser().resolve()
    run_root.mkdir(parents=True, exist_ok=True)
    worker = Path(worker_dir).expanduser().resolve()
    pub = Path(public_root).expanduser().resolve()
    trusted = Path(trusted_root).expanduser().resolve()

    harness_id = hash_worker_directory(worker)
    worker_cfg = _worker_settings(worker)

    state_path = run_root / STATE_FILE
    result_path = run_root / RESULT_FILE

    # Resume existing run.
    if result_path.is_file() and not result_path.is_symlink():
        return json.loads(result_path.read_text(encoding="utf-8"))

    # Initialize or reload state.
    if state_path.is_file() and not state_path.is_symlink():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("protocol") != PROTOCOL or state.get("harness_id") != harness_id:
            raise BacktestBenchTTSError(
                "retained TTS state belongs to a different harness or protocol"
            )
    else:
        state = {
            "protocol": PROTOCOL,
            "run_id": run_root.name,
            "harness_id": harness_id,
            "k_samples": k_samples,
            "scoring_mode": scoring_mode,
            "worker_settings": worker_cfg,
            "status": "running",
            "tasks": {
                task_id: {
                    "attempts": {},
                    "result": None,
                }
                for task_id in task_ids
            },
            "started_at": _now(),
        }
        _atomic_private_json(state_path, state)

    config = load_rootless_full_harness_config(config_path)

    # Build work queue: (task_id, attempt_index) pairs not yet completed.
    pending = []
    for task_id in task_ids:
        cell = state["tasks"].setdefault(task_id, {"attempts": {}, "result": None})
        for k in range(k_samples):
            key = f"attempt-{k:04d}"
            if key not in cell["attempts"]:
                pending.append((task_id, k, key))

    # Run pending Workers in parallel.
    if pending:
        _run_tts_workers(
            pending=pending,
            state=state,
            state_path=state_path,
            worker=worker,
            pub=pub,
            trusted=trusted,
            run_root=run_root,
            config=config,
            worker_image_ref=worker_image_ref,
            proxy_image_ref=proxy_image_ref,
            scoring_mode=scoring_mode,
            concurrency=concurrency,
        )

    # Grade each task by majority vote.
    task_results: dict[str, dict] = {}
    for task_id in task_ids:
        cell = state["tasks"][task_id]
        attempts = list(cell["attempts"].values())
        majority, winner_id, passed, total = _majority_vote(attempts)
        cost = sum(float(a.get("cost_usd", 0.0)) for a in attempts)
        task_results[task_id] = {
            "task_id": task_id,
            "k_samples": k_samples,
            "majority_reward": majority,
            "winning_attempt_id": winner_id,
            "passed": passed,
            "total": total,
            "cost_usd": cost,
            "attempts": attempts,
        }

    total_cost = sum(r["cost_usd"] for r in task_results.values())
    binary_successes = sum(r["majority_reward"] for r in task_results.values())

    result = {
        "protocol": PROTOCOL,
        "schema_version": 1,
        "run_id": run_root.name,
        "harness_id": harness_id,
        "k_samples": k_samples,
        "scoring_mode": scoring_mode,
        "worker_settings": worker_cfg,
        "status": "complete",
        "tasks": task_results,
        "summary": {
            "task_count": len(task_ids),
            "binary_successes": binary_successes,
            "binary_accuracy": binary_successes / max(len(task_ids), 1),
            "total_worker_calls": k_samples * len(task_ids),
            "total_cost_usd": total_cost,
        },
        "completed_at": _now(),
    }
    _atomic_private_json(result_path, result)
    state["status"] = "complete"
    _atomic_private_json(state_path, state)
    return result


def _run_tts_workers(
    *,
    pending: list[tuple[str, int, str]],
    state: dict,
    state_path: Path,
    worker: Path,
    pub: Path,
    trusted: Path,
    run_root: Path,
    config: dict,
    worker_image_ref: str,
    proxy_image_ref: str,
    scoring_mode: str,
    concurrency: int,
) -> None:
    """Run all pending (task_id, k, key) Worker cells up to concurrency."""

    from .backtestbench_panel import (
        _PanelRuntime,
        _grade_attempt,
        _run_one_attempt,
    )

    # Import these lazily so module-level import stays clean.
    from .executors.sandbox_evolver import _combined_request
    from .executors.sandbox_nexau import SandboxNexAUExecutor

    resource_contract = SandboxResourceContract(
        **{k: config["worker_resources"][k] for k in config["worker_resources"]}
    )

    runtime = _PanelRuntime(
        proposer=_build_proposer(
            config=config,
            worker=worker,
            run_root=run_root,
            worker_image_ref=worker_image_ref,
            proxy_image_ref=proxy_image_ref,
        ),
        public_root=pub,
        worker_image_ref=worker_image_ref,
        worker_resources=resource_contract,
        lease_timeout_seconds=float(config.get("lease_timeout_seconds", 3600)),
        metadata={"run_id": run_root.name, "mode": "tts_baseline"},
    )

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {}
        queue = list(pending)

        def _submit_next():
            if queue:
                task_id, k, key = queue.pop(0)
                attempt_dir = run_root / "attempts" / task_id / key
                task = _public_task(pub, task_id)
                future = executor.submit(
                    _run_one_attempt,
                    task=task,
                    attempt_dir=attempt_dir,
                    run_dir=run_root,
                    runtime=runtime,
                    worker_dir=worker,
                    trusted_root=trusted,
                    scoring_mode=scoring_mode,
                    attempt_index=k,
                )
                futures[future] = (task_id, k, key)

        for _ in range(min(concurrency, len(queue))):
            _submit_next()

        while futures:
            done, _ = wait(futures, return_when=FIRST_COMPLETED)
            for future in done:
                task_id, k, key = futures.pop(future)
                try:
                    attempt_result = future.result()
                    state["tasks"][task_id]["attempts"][key] = {
                        "attempt_id": attempt_result.get("attempt_id", key),
                        "attempt_index": k,
                        "reward": attempt_result.get("reward"),
                        "passed": attempt_result.get("passed", 0),
                        "total": attempt_result.get("total", 0),
                        "cost_usd": attempt_result.get("cost_usd", 0.0),
                        "status": attempt_result.get("status", "unknown"),
                    }
                except Exception as exc:
                    state["tasks"][task_id]["attempts"][key] = {
                        "attempt_id": key,
                        "attempt_index": k,
                        "reward": None,
                        "passed": 0,
                        "total": 0,
                        "cost_usd": 0.0,
                        "status": "failed",
                        "failure": str(exc),
                    }
                _atomic_private_json(state_path, state)
                _submit_next()


def _build_proposer(
    *,
    config: dict,
    worker: Path,
    run_root: Path,
    worker_image_ref: str,
    proxy_image_ref: str,
) -> object:
    """Build the proxy manager / resource pool needed by _PanelRuntime."""
    _, proposer = _prepare_revision_runtime(
        root=run_root,
        config_path=config["config_path"],
        evolver_config_path=config.get("evolver_config_path", config["config_path"]),
        evolver_image_ref=worker_image_ref,  # not used for TTS
        proxy_image_ref=proxy_image_ref,
    )
    return proposer
