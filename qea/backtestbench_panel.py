"""Run one declared BacktestBench panel with the complete shared Worker H.

Each task gets one native NexAU Worker and one scoped credential proxy. The
coordinator judges its downloaded answer only after both have cleaned up; no
trusted answer or judge is placed in a Worker bundle. Checkpoints retain failed
attempts and missing scores. Reopening this run never redraws a Worker.
"""

from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Sequence

import yaml

from .benchmarks.backtestbench import (
    BACKTESTBENCH_PUBLIC_SUBMISSION_PATHS,
    OFFICIAL_CATEGORIES,
    SCORING_MODES,
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
from .quantcodeeval_worker_observation import (
    _attempt_evidence,
    _failure_payload,
    _proxy_cost_evidence,
    _relative,
    _resource_metadata,
    _worker_execution_payload,
)
from .rootless_full_harness import _CoordinatorLock, load_rootless_full_harness_config
from .worker_identity import hash_worker_directory


STATE_FILE = "BACKTESTBENCH-PANEL-STATE.json"
RESULT_FILE = "BACKTESTBENCH-PANEL-RESULT.json"
PROTOCOL = "backtestbench-full-harness-panel-v1"
# Provider/sandbox failures get a bounded number of fresh attempts. Each retry
# is a new attempt identity, so no request that was already sent is replayed.
PROVIDER_RETRY_LIMIT = 2
_PROVIDER_FAILURES = frozenset({"SandboxProxyError", "SandboxInfrastructureError"})


class BacktestBenchPanelError(ValueError):
    """A panel cannot be run or safely resumed under its declared conditions."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _worker_settings(worker_dir: Path) -> dict[str, object]:
    """Record the actual H configuration without changing its inference budget."""
    agent = yaml.safe_load((worker_dir / "agent.yaml").read_text(encoding="utf-8"))
    if not isinstance(agent, dict) or not isinstance(agent.get("llm_config"), dict):
        raise BacktestBenchPanelError("Worker agent.yaml lacks llm_config")
    llm = agent["llm_config"]
    return {
        "max_iterations": agent.get("max_iterations"),
        "max_context_tokens": agent.get("max_context_tokens"),
        **{key: llm.get(key) for key in (
            "model", "max_tokens", "temperature", "stream", "api_type", "timeout",
        )},
    }


def _public_task(public_root: Path, task_id: str) -> BacktestBenchTask:
    data = public_root / "tasks" / task_id / "environment" / "data" / "public_task.json"
    record = json.loads(data.read_text(encoding="utf-8"))
    task = project_public_task(
        record, source_split=record["source_split"], source_row=record["source_row"],
    )
    if task.task_id != task_id:
        raise BacktestBenchPanelError("projected public task differs from requested task")
    return task


@dataclass(frozen=True)
class _PanelRuntime:
    proposer: object
    public_root: Path
    worker_image_ref: str
    worker_resources: SandboxResourceContract
    lease_timeout_seconds: float
    metadata: dict[str, object]
    input_limits: Mapping[str, int] | None = None

    def execute(self, *, attempt, task, worker_dir, run_dir) -> WorkerExecution:
        # Only the existing runtime's backend/proxy/pool are used. No Evolver
        # call or proposer mutation is part of this fixed-H measurement.
        proxy_manager = self.proposer.proxy_manager
        request = _combined_request(
            self.worker_resources, proxy_manager.config.resource_contract,
        )
        with self.proposer.resource_pool.acquire(
            f"backtestbench-worker:{attempt.attempt_id}", request,
            timeout_seconds=self.lease_timeout_seconds,
        ):
            with proxy_manager.open(
                run_id=attempt.run_id, attempt_id=attempt.attempt_id,
                task_id=task.task_id, caller_role="worker", run_dir=run_dir,
            ) as session:
                if (
                    session.network_scope != attempt.attempt_id
                    or session.allowed_model != proxy_manager.config.allowed_model
                    or session.required_provider != proxy_manager.config.required_provider
                    or session.fallback_providers != proxy_manager.config.fallback_providers
                    or session.immutable_image_ref != proxy_manager.config.image_ref
                ):
                    raise SandboxInfrastructureError(
                        "worker.proxy", "proxy session differs from the declared Worker route",
                    )
                executor = SandboxNexAUExecutor(
                    backend=self.proposer.backend,
                    lifecycle_root=Path(run_dir) / "lifecycles",
                    worker_image_ref=self.worker_image_ref,
                    public_task_root=self.public_root,
                    resource_contract=self.worker_resources,
                    worker_network_name=session.network_name,
                    network_scope=session.network_scope,
                    proxy_base_url=session.base_url,
                    model_name=session.allowed_model,
                    # Preserve code and all answer artifacts. A missing/bad
                    # answer from a completed Worker is judged as an answer,
                    # not turned into a transport failure by output membership.
                    expected_output_paths=None,
                    max_output_files=2_000,
                    max_output_bytes=512 * 1024 * 1024,
                    **({"input_limits": self.input_limits} if self.input_limits is not None else {}),
                )
                execution = executor.execute(
                    attempt=attempt, task=task, worker_dir=worker_dir,
                    run_dir=run_dir, model_env={},
                )
                persist_worker_execution(
                    execution, Path(run_dir) / "attempts" / attempt.attempt_id,
                )
            # Proxy audit finalization and cleanup finish before returning.
        return execution


def _prepare_panel_runtime(
    *, root: Path, config_path: str | Path, public_root: Path,
    worker_image_ref: str, proxy_image_ref: str,
    worker_timeout_seconds: int | None,
) -> _PanelRuntime:
    config = load_rootless_full_harness_config(config_path)
    proposer, metadata = _prepare_revision_runtime(
        root=root, config_path=config_path,
        evolver_image_ref=worker_image_ref, proxy_image_ref=proxy_image_ref,
    )
    tmpfs = dict(config.worker_limits.writable_tmpfs_mb)
    # The native executor keeps the archive in /qea and copies public data
    # into /app/data and /app. The stock ZIP is 249 MB and expands to 645 MB.
    tmpfs["/qea"] = max(tmpfs.get("/qea", 0), 1_024)
    tmpfs["/app"] = max(tmpfs.get("/app", 0), 3_072)
    resources = SandboxResourceContract(
        cpu_count=2, memory_mb=8_192, pids_limit=config.worker_limits.pids_limit,
        timeout_seconds=(
            config.worker_limits.timeout_seconds
            if worker_timeout_seconds is None else worker_timeout_seconds
        ),
        writable_tmpfs_mb=tmpfs,
    )
    return _PanelRuntime(
        proposer, public_root, worker_image_ref, resources,
        float(config.lease_timeout_seconds),
        {
            "model": metadata["model"],
            "required_provider": metadata["required_provider"],
            "fallback_providers": metadata["fallback_providers"],
            "worker_image_ref": worker_image_ref,
            "proxy_image_ref": proxy_image_ref,
            "worker_resources": _resource_metadata(resources),
            "proxy_resources": _resource_metadata(config.proxy_resources),
        },
    )


def _submission(execution: WorkerExecution) -> Path:
    for relative in BACKTESTBENCH_PUBLIC_SUBMISSION_PATHS:
        path = execution.artifact_dir / relative
        if path.is_file() and not path.is_symlink():
            return path
    # Official BacktestBench scores the final model message. Retaining this
    # fallback also records Workers that supplied their answer only there.
    return Path(execution.final_text_uri)


def _run_task(
    *, runtime, root: Path, trusted_root: Path, worker_dir: Path,
    task: BacktestBenchTask, attempt: TaskAttempt, scoring_mode: str,
) -> dict[str, object]:
    attempt_dir = root / "attempts" / attempt.attempt_id
    execution = None
    failure = None
    score = None
    submission_uri = None
    status = "worker_failed"
    try:
        execution = runtime.execute(
            attempt=attempt, task=task, worker_dir=worker_dir, run_dir=root,
        )
        if not isinstance(execution, WorkerExecution) or execution.attempt_id != attempt.attempt_id:
            raise BacktestBenchPanelError("Worker returned an invalid execution record")
        persist_worker_execution(execution, attempt_dir)
        if not execution.cleaned_up:
            raise BacktestBenchPanelError("Worker cleanup did not finish; score remains missing")
        submission = _submission(execution)
        submission_uri = _relative(submission, root)
        status = "scoring_failed"
        grade = grade_submission(
            trusted_root / "tasks" / task.task_id / "answer.json",
            submission, scoring_mode=scoring_mode,
        )
        score = grade.public_record()
        status = "scored" if score["scored"] else "unscored_category"
    except Exception as exc:  # noqa: BLE001 - every failed task is retained.
        failure = _failure_payload(exc)
    return {
        "task_id": task.task_id, "attempt_id": attempt.attempt_id,
        "status": status, "finished_at": _now(), "failure": failure,
        "reward": None if score is None else score["reward"],
        "official_evaluation": score, "submission_uri": submission_uri,
        "worker_execution": (
            _worker_execution_payload(execution, run_root=root)
            if isinstance(execution, WorkerExecution) else None
        ),
        "worker_evidence": _attempt_evidence(attempt_dir, run_root=root),
        "proxy_cost": _proxy_cost_evidence(attempt_dir, run_root=root),
    }


def _summary(tasks: dict[str, dict], *, scoring_mode: str) -> dict[str, object]:
    results = [cell["result"] for cell in tasks.values() if cell["result"] is not None]
    scored = [result for result in results if result["reward"] is not None]
    excluded = [result for result in results if result["status"] == "unscored_category"]
    complete_scores = len(scored) + len(excluded) == len(tasks)
    costs = [result["proxy_cost"] for result in results]
    complete_costs = len(costs) == len(tasks) and all(cost["cost_complete"] for cost in costs)
    categories = {}
    for category in OFFICIAL_CATEGORIES:
        selected = [
            cell for cell in tasks.values()
            if cell["public_task"]["strategy_type"] == category
            or (
                category == "ticker_selection"
                and scoring_mode == "stock_selection_alias"
                and cell["public_task"]["strategy_type"] == "stock_selection"
            )
        ]
        if selected:
            available = [cell["result"]["reward"] for cell in selected
                         if cell["result"] is not None and cell["result"]["reward"] is not None]
            categories[category] = {
                "selected_count": len(selected), "scored_count": len(available),
                "accuracy": sum(available) / len(available) if len(available) == len(selected) else None,
            }
    return {
        "selected_count": len(tasks), "returned_count": len(results),
        "scored_count": len(scored), "unscored_category_count": len(excluded),
        "failed_count": sum(result["failure"] is not None for result in results),
        "scores_complete": complete_scores,
        "accuracy": (
            sum(result["reward"] for result in scored) / len(scored)
            if complete_scores and scored else None
        ),
        "categories": categories,
        "cost_complete": complete_costs,
        "provider_cost_usd": (
            sum(cost["provider_cost_usd"] for cost in costs) if complete_costs else None
        ),
        "known_provider_cost_usd": sum(
            cost["provider_cost_usd"] for cost in costs if cost["provider_cost_usd"] is not None
        ),
        "request_count": (
            sum(cost["request_count"] for cost in costs) if complete_costs else None
        ),
    }


def run_backtestbench_panel(
    *, config_path: str | Path, public_root: str | Path, trusted_root: str | Path,
    run_dir: str | Path, worker_dir: str | Path, task_ids: Sequence[str],
    benchmark_commit: str, worker_image_ref: str, proxy_image_ref: str,
    split: str = "development", checkpoint: str = "initial",
    harness_id: str | None = None, concurrency: int = 4,
    scoring_mode: str = "official", worker_timeout_seconds: int | None = None,
) -> dict[str, object]:
    """Run exactly one Worker per declared task; retained terminal runs are read-only."""
    if type(concurrency) is not int or concurrency < 1:
        raise BacktestBenchPanelError("concurrency must be a positive integer")
    if not task_ids or len(set(task_ids)) != len(task_ids):
        raise BacktestBenchPanelError("declare a nonempty panel of unique task IDs")
    if scoring_mode not in SCORING_MODES:
        raise BacktestBenchPanelError("unknown scoring mode")
    if worker_timeout_seconds is not None and (
        type(worker_timeout_seconds) is not int or worker_timeout_seconds < 1
    ):
        raise BacktestBenchPanelError("worker timeout must be positive")
    root = Path(run_dir).expanduser().resolve()
    public = Path(public_root).expanduser().resolve()
    trusted = Path(trusted_root).expanduser().resolve()
    worker = Path(worker_dir).expanduser().resolve()
    if public == trusted or public in trusted.parents or trusted in public.parents:
        raise BacktestBenchPanelError("public and trusted task roots must be disjoint")
    if trusted == worker or trusted in worker.parents or worker in trusted.parents:
        raise BacktestBenchPanelError("trusted inputs must remain outside the Worker H")
    root.mkdir(parents=True, exist_ok=True)
    lock = _CoordinatorLock(root / "coordinator.lock").acquire()
    try:
        declaration = {
            "config_path": str(Path(config_path).expanduser().resolve()),
            "public_root": str(public), "trusted_root": str(trusted),
            "benchmark_commit": benchmark_commit, "task_ids": list(task_ids),
            "split": split, "checkpoint": checkpoint,
            "full_harness": {"harness_id": harness_id or worker.name, "worker_dir": str(worker)},
            "worker_image_ref": worker_image_ref, "proxy_image_ref": proxy_image_ref,
            "concurrency": concurrency, "scoring_mode": scoring_mode,
            "worker_timeout_seconds": worker_timeout_seconds,
            "submission_precedence": [*BACKTESTBENCH_PUBLIC_SUBMISSION_PATHS, "final_message"],
        }
        state_path = root / STATE_FILE
        if state_path.exists():
            state = json.loads(state_path.read_text(encoding="utf-8"))
            if state.get("declaration") != declaration:
                raise BacktestBenchPanelError("existing run has a different panel declaration")
            if state["status"] not in {"complete", "complete_with_failures", "preparation_failed"}:
                raise BacktestBenchPanelError(
                    "incomplete run retained; root recovery is required, no Worker is redrawn",
                )
            return state
        if any((root / "attempts").glob("*/*")):
            raise BacktestBenchPanelError("attempt evidence already exists without a panel checkpoint")
        tasks = tuple(_public_task(public, task_id) for task_id in task_ids)
        worker_digest = hash_worker_directory(worker)
        attempts = {
            task.task_id: TaskAttempt.create(
                run_id=root.name, benchmark_commit=benchmark_commit, task_id=task.task_id,
                split=split, checkpoint=checkpoint, worker_digest=worker_digest,
            ) for task in tasks
        }
        state = {
            "protocol": PROTOCOL, "run_id": root.name, "status": "preparing",
            "started_at": _now(), "updated_at": _now(), "declaration": declaration,
            "worker_settings": _worker_settings(worker), "runtime": None,
            "failure": None,
            "tasks": {
                task.task_id: {
                    "public_task": task.public_record(), "attempt": asdict(attempts[task.task_id]),
                    "status": "pending", "result": None,
                } for task in tasks
            },
        }
        state["summary"] = _summary(state["tasks"], scoring_mode=scoring_mode)
        _atomic_private_json(state_path, state)
        try:
            runtime = _prepare_panel_runtime(
                root=root, config_path=config_path, public_root=public,
                worker_image_ref=worker_image_ref, proxy_image_ref=proxy_image_ref,
                worker_timeout_seconds=worker_timeout_seconds,
            )
        except Exception as exc:  # noqa: BLE001 - preserve qualification failure.
            state.update(status="preparation_failed", failure=_failure_payload(exc), updated_at=_now())
            _atomic_private_json(state_path, state)
            _atomic_private_json(root / RESULT_FILE, state)
            return state
        state.update(status="running", runtime=dict(runtime.metadata))
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            pending = iter(tasks)
            active = {}
            while True:
                while len(active) < concurrency:
                    task = next(pending, None)
                    if task is None:
                        break
                    attempt = attempts[task.task_id]
                    _atomic_private_json(root / "attempts" / attempt.attempt_id / "attempt.json", asdict(attempt))
                    state["tasks"][task.task_id]["status"] = "running"
                    state["updated_at"] = _now()
                    _atomic_private_json(state_path, state)
                    future = executor.submit(
                        _run_task, runtime=runtime, root=root, trusted_root=trusted,
                        worker_dir=worker, task=task, attempt=attempt, scoring_mode=scoring_mode,
                    )
                    active[future] = task.task_id
                if not active:
                    break
                done, _ = wait(active, return_when=FIRST_COMPLETED)
                for future in done:
                    task_id = active.pop(future)
                    result = future.result()
                    cell = state["tasks"][task_id]
                    retries = cell.setdefault("provider_retries", [])
                    if (result["status"] == "worker_failed"
                            and (result["failure"] or {}).get("exception_type") in _PROVIDER_FAILURES
                            and len(retries) < PROVIDER_RETRY_LIMIT):
                        retries.append(result)
                        task = next(t for t in tasks if t.task_id == task_id)
                        attempt = TaskAttempt.create(
                            run_id=root.name, benchmark_commit=benchmark_commit, task_id=task_id,
                            split=split, checkpoint=f"{checkpoint}-retry{len(retries)}",
                            worker_digest=worker_digest,
                        )
                        cell["attempt"] = asdict(attempt)
                        _atomic_private_json(root / "attempts" / attempt.attempt_id / "attempt.json", asdict(attempt))
                        _atomic_private_json(state_path, state)
                        future = executor.submit(
                            _run_task, runtime=runtime, root=root, trusted_root=trusted,
                            worker_dir=worker, task=task, attempt=attempt, scoring_mode=scoring_mode,
                        )
                        active[future] = task_id
                        continue
                    cell.update(status=result["status"], result=result)
                    state["summary"] = _summary(state["tasks"], scoring_mode=scoring_mode)
                    state["updated_at"] = _now()
                    _atomic_private_json(state_path, state)
        state.update(
            status="complete_with_failures" if state["summary"]["failed_count"] else "complete",
            finished_at=_now(), updated_at=_now(),
        )
        _atomic_private_json(state_path, state)
        _atomic_private_json(root / RESULT_FILE, state)
        return state
    finally:
        lock.close()
