"""Resumable repeated QFBench evaluation of one immutable base worker."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Mapping, Protocol

from .evaluation import EvaluationSummary, OfficialTaskScore, aggregate_domain_macro
from .evolve_runtime import snapshot_dir
from .worker_identity import WorkerIdentityError, hash_worker_directory


_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_T_CRITICAL_95 = {
    2: 12.706204736432095,
    3: 4.302652729696142,
    4: 3.182446305284263,
    5: 2.7764451051977987,
}


class BaselineConfigError(ValueError):
    """A baseline run is unsafe or incompatible with its checkpoint."""


class BaselineEvaluator(Protocol):
    def evaluate(
        self, *, worker_dir, tasks, split, checkpoint, run_dir
    ) -> EvaluationSummary: ...


@dataclass(frozen=True)
class BaselineConfig:
    """Immutable identity and storage configuration for a five-repeat baseline."""

    run_id: str
    repetitions: int
    results_dir: Path | str
    seed_worker_dir: Path | str
    model_identity: str
    task_manifest_digest: str
    runtime_identity_digest: str
    scheduler_identity_digest: str
    template_identity_digest: str
    worker_concurrency: int = 4
    verifier_concurrency: int = 3
    resume: bool = True

    def __post_init__(self) -> None:
        if not _RUN_ID_RE.fullmatch(self.run_id):
            raise BaselineConfigError("run_id must be a path-safe identifier")
        if self.repetitions != 5:
            raise BaselineConfigError("QFBench repeated baseline requires five repetitions")
        if not self.model_identity.strip():
            raise BaselineConfigError("model_identity must be non-empty")
        for name in (
            "task_manifest_digest",
            "runtime_identity_digest",
            "scheduler_identity_digest",
            "template_identity_digest",
        ):
            if not _SHA256_RE.fullmatch(getattr(self, name)):
                raise BaselineConfigError(f"{name} must be 64 lowercase hex characters")
        for name in ("worker_concurrency", "verifier_concurrency"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise BaselineConfigError(f"{name} must be positive")


@dataclass(frozen=True)
class BaselineRepetition:
    repetition: int
    primary: EvaluationSummary
    diagnostic: EvaluationSummary


@dataclass(frozen=True)
class BaselineResult:
    run_id: str
    run_dir: Path
    complete: bool
    repetitions: tuple[BaselineRepetition, ...]
    aggregate: dict
    seed_worker_dir: Path


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")
    os.replace(temporary, path)


def _summary_dict(summary: EvaluationSummary) -> dict:
    return {
        "scores": [asdict(score) for score in summary.scores],
        "task_rewards": summary.task_rewards,
        "domain_scores": summary.domain_scores,
        "task_mean": summary.task_mean,
        "overall": summary.overall,
    }


def _summary_from_dict(payload: Mapping) -> EvaluationSummary:
    scores = tuple(
        OfficialTaskScore(
            **{**item, "diagnostic_tags": tuple(item.get("diagnostic_tags", ()))}
        )
        for item in payload["scores"]
    )
    return EvaluationSummary(
        scores=scores,
        task_rewards={
            str(key): float(value) for key, value in payload["task_rewards"].items()
        },
        domain_scores={
            str(key): float(value) for key, value in payload["domain_scores"].items()
        },
        task_mean=float(payload["task_mean"]),
        overall=float(payload["overall"]),
    )


def _task_contract(tasks: tuple) -> list[dict]:
    return [
        {
            "task_id": task.task_id,
            "domain": task.domain,
            "reward_kind": task.reward_kind,
            "resource_source": task.resource_source,
        }
        for task in tasks
    ]


def _identity(
    config: BaselineConfig,
    *,
    worker_digest: str,
    primary_tasks: tuple,
    diagnostic_tasks: tuple,
) -> dict:
    return {
        "model_identity": config.model_identity,
        "task_manifest_digest": config.task_manifest_digest,
        "runtime_identity_digest": config.runtime_identity_digest,
        "scheduler_identity_digest": config.scheduler_identity_digest,
        "template_identity_digest": config.template_identity_digest,
        "worker_concurrency": config.worker_concurrency,
        "verifier_concurrency": config.verifier_concurrency,
        "seed_worker_digest": worker_digest,
        "primary_tasks": _task_contract(primary_tasks),
        "diagnostic_tasks": _task_contract(diagnostic_tasks),
    }


def _validate_tasks(primary_tasks: tuple, diagnostic_tasks: tuple) -> None:
    if not primary_tasks or not diagnostic_tasks:
        raise BaselineConfigError("primary and diagnostic task panels must be non-empty")
    primary_ids = [task.task_id for task in primary_tasks]
    diagnostic_ids = [task.task_id for task in diagnostic_tasks]
    if len(primary_ids) != len(set(primary_ids)):
        raise BaselineConfigError("primary task IDs must be unique")
    if len(diagnostic_ids) != len(set(diagnostic_ids)):
        raise BaselineConfigError("diagnostic task IDs must be unique")
    overlap = set(primary_ids) & set(diagnostic_ids)
    if overlap:
        raise BaselineConfigError(f"task panels overlap: {sorted(overlap)}")


def _series(values: Iterable[float], *, complete: bool) -> dict:
    ordered = tuple(float(value) for value in values)
    if not ordered:
        raise BaselineConfigError("cannot aggregate an empty repetition series")
    mean = statistics.fmean(ordered)
    if len(ordered) == 1:
        sample_sd = None
        standard_error = None
    else:
        sample_sd = statistics.stdev(ordered)
        standard_error = sample_sd / math.sqrt(len(ordered))
    interval = None
    if complete and standard_error is not None:
        critical = _T_CRITICAL_95.get(len(ordered))
        if critical is not None:
            half_width = critical * standard_error
            interval = [mean - half_width, mean + half_width]
    return {
        "n": len(ordered),
        "mean": mean,
        "sample_sd": sample_sd,
        "standard_error": standard_error,
        "confidence_interval_95": interval,
        "values": list(ordered),
    }


def _panel(
    summaries: tuple[EvaluationSummary, ...],
    tasks: tuple,
    *,
    complete: bool,
) -> dict:
    expected = {task.task_id for task in tasks}
    reward_kinds = {task.task_id: task.reward_kind for task in tasks}
    for summary in summaries:
        if set(summary.task_rewards) != expected:
            raise BaselineConfigError("evaluation summary task panel mismatch")

    domains = sorted({task.domain for task in tasks})
    domain_series = {
        domain: _series(
            (summary.domain_scores[domain] for summary in summaries),
            complete=complete,
        )
        for domain in domains
    }
    task_series = {}
    for task_id in sorted(expected):
        values = tuple(summary.task_rewards[task_id] for summary in summaries)
        stats = _series(values, complete=complete)
        if reward_kinds[task_id] == "binary":
            stats["success_count"] = sum(value == 1.0 for value in values)
        task_series[task_id] = stats
    return {
        "task_count": len(tasks),
        "repeat_domain_macro": _series(
            (summary.overall for summary in summaries), complete=complete
        ),
        "repeat_task_mean": _series(
            (summary.task_mean for summary in summaries), complete=complete
        ),
        "domains": domain_series,
        "tasks": task_series,
    }


def aggregate_repetitions(
    primary_repetitions: Iterable[EvaluationSummary],
    diagnostic_repetitions: Iterable[EvaluationSummary],
    *,
    resource_fallback_task_ids: frozenset[str],
    primary_tasks: Iterable,
    diagnostic_tasks: Iterable,
    expected_repetitions: int,
) -> dict:
    """Aggregate independent repeat-level estimates and keep diagnostics separate."""

    primary = tuple(primary_repetitions)
    diagnostic = tuple(diagnostic_repetitions)
    primary_task_tuple = tuple(primary_tasks)
    diagnostic_task_tuple = tuple(diagnostic_tasks)
    if not primary or len(primary) != len(diagnostic):
        raise BaselineConfigError("primary and diagnostic repetitions must be paired")
    if len(primary) > expected_repetitions:
        raise BaselineConfigError("more repetitions recorded than preregistered")
    complete = len(primary) == expected_repetitions

    declared_tasks = tuple(
        task
        for task in primary_task_tuple
        if task.task_id not in resource_fallback_task_ids
    )
    if not declared_tasks:
        raise BaselineConfigError("resource-declared sensitivity panel is empty")
    declared_ids = {task.task_id for task in declared_tasks}
    declared_summaries = tuple(
        aggregate_domain_macro(
            score for score in summary.scores if score.task_id in declared_ids
        )
        for summary in primary
    )

    return {
        "expected_repetitions": expected_repetitions,
        "completed_repetitions": len(primary),
        "complete": complete,
        "primary": _panel(primary, primary_task_tuple, complete=complete),
        "diagnostic": _panel(
            diagnostic, diagnostic_task_tuple, complete=complete
        ),
        "resource_declared_sensitivity": _panel(
            declared_summaries, declared_tasks, complete=complete
        ),
    }


def _records_from_state(state: Mapping) -> tuple[BaselineRepetition, ...]:
    return tuple(
        BaselineRepetition(
            repetition=int(record["repetition"]),
            primary=_summary_from_dict(record["primary"]),
            diagnostic=_summary_from_dict(record["diagnostic"]),
        )
        for record in state["completed"]
    )


def _result(
    config: BaselineConfig,
    *,
    run_dir: Path,
    seed_worker_dir: Path,
    state: dict,
    primary_tasks: tuple,
    diagnostic_tasks: tuple,
) -> BaselineResult:
    repetitions = _records_from_state(state)
    aggregate = aggregate_repetitions(
        (record.primary for record in repetitions),
        (record.diagnostic for record in repetitions),
        resource_fallback_task_ids=frozenset(
            task.task_id
            for task in primary_tasks
            if task.resource_source == "qea_fallback"
        ),
        primary_tasks=primary_tasks,
        diagnostic_tasks=diagnostic_tasks,
        expected_repetitions=config.repetitions,
    )
    result = BaselineResult(
        run_id=config.run_id,
        run_dir=run_dir,
        complete=aggregate["complete"],
        repetitions=repetitions,
        aggregate=aggregate,
        seed_worker_dir=seed_worker_dir,
    )
    _atomic_json(
        run_dir / "result.json",
        {
            "run_id": result.run_id,
            "complete": result.complete,
            "seed_worker_dir": seed_worker_dir.relative_to(run_dir).as_posix(),
            "repetitions": [
                {
                    "repetition": record.repetition,
                    "primary": _summary_dict(record.primary),
                    "diagnostic": _summary_dict(record.diagnostic),
                }
                for record in repetitions
            ],
            "aggregate": aggregate,
        },
    )
    return result


def run_qfbench_baseline(
    config: BaselineConfig,
    *,
    primary_tasks: Iterable,
    diagnostic_tasks: Iterable,
    benchmark_commit: str,
    evaluator: BaselineEvaluator,
    stop_after_repetition: int | None = None,
) -> BaselineResult:
    """Evaluate an immutable seed worker, checkpointing after every panel."""

    if not _COMMIT_RE.fullmatch(benchmark_commit):
        raise BaselineConfigError("benchmark_commit must be a full lowercase SHA")
    if stop_after_repetition is not None and not (
        1 <= stop_after_repetition < config.repetitions
    ):
        raise BaselineConfigError("stop_after_repetition must be between 1 and 4")
    primary = tuple(primary_tasks)
    diagnostic = tuple(diagnostic_tasks)
    _validate_tasks(primary, diagnostic)
    source_worker = Path(config.seed_worker_dir).resolve()
    try:
        worker_digest = hash_worker_directory(source_worker)
    except WorkerIdentityError as exc:
        raise BaselineConfigError(str(exc)) from exc

    run_dir = Path(config.results_dir).resolve() / config.run_id
    resume_path = run_dir / "resume.json"
    seed_worker = run_dir / "workers" / "seed"
    identity = _identity(
        config,
        worker_digest=worker_digest,
        primary_tasks=primary,
        diagnostic_tasks=diagnostic,
    )

    if run_dir.exists():
        if not config.resume:
            raise BaselineConfigError(f"run directory already exists: {run_dir}")
        if not resume_path.is_file():
            raise BaselineConfigError("existing run has no resume checkpoint")
        try:
            state = json.loads(resume_path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise BaselineConfigError(f"invalid resume checkpoint: {exc}") from exc
        expected_checkpoint = {
            "schema_version": 1,
            "run_id": config.run_id,
            "benchmark_commit": benchmark_commit,
            "total_repetitions": config.repetitions,
        }
        actual_checkpoint = {
            key: state.get(key) for key in expected_checkpoint
        }
        if actual_checkpoint != expected_checkpoint:
            raise BaselineConfigError(
                "resume checkpoint mismatch: "
                f"expected {expected_checkpoint}, found {actual_checkpoint}"
            )
        if state.get("identity") != identity:
            raise BaselineConfigError("resume immutable identity mismatch")
        if not seed_worker.is_dir():
            raise BaselineConfigError("resume seed worker snapshot is missing")
        if state.get("phase") == "calibration_stop":
            state["phase"] = "primary"
            _atomic_json(resume_path, state)
    else:
        run_dir.mkdir(parents=True)
        snapshot_dir(source_worker, seed_worker)
        state = {
            "schema_version": 1,
            "run_id": config.run_id,
            "benchmark_commit": benchmark_commit,
            "total_repetitions": config.repetitions,
            "identity": identity,
            "phase": "primary",
            "next_repetition": 1,
            "pending_primary": None,
            "completed": [],
        }
        _atomic_json(resume_path, state)

    while state["next_repetition"] <= config.repetitions:
        repetition = int(state["next_repetition"])
        if state["phase"] == "primary":
            primary_summary = evaluator.evaluate(
                worker_dir=seed_worker,
                tasks=primary,
                split="baseline_primary",
                checkpoint=f"repetition-{repetition:02d}-primary",
                run_dir=run_dir,
            )
            state["pending_primary"] = _summary_dict(primary_summary)
            state["phase"] = "diagnostic"
            _atomic_json(resume_path, state)
        if state["phase"] == "diagnostic":
            diagnostic_summary = evaluator.evaluate(
                worker_dir=seed_worker,
                tasks=diagnostic,
                split="baseline_diagnostic",
                checkpoint=f"repetition-{repetition:02d}-diagnostic",
                run_dir=run_dir,
            )
            state["completed"].append(
                {
                    "repetition": repetition,
                    "primary": state["pending_primary"],
                    "diagnostic": _summary_dict(diagnostic_summary),
                }
            )
            state["pending_primary"] = None
            state["next_repetition"] = repetition + 1
            if repetition == config.repetitions:
                state["phase"] = "complete"
            elif (
                stop_after_repetition is not None
                and repetition >= stop_after_repetition
            ):
                state["phase"] = "calibration_stop"
            else:
                state["phase"] = "primary"
            _atomic_json(resume_path, state)
        if state["phase"] in {"calibration_stop", "complete"}:
            break

    return _result(
        config,
        run_dir=run_dir,
        seed_worker_dir=seed_worker,
        state=state,
        primary_tasks=primary,
        diagnostic_tasks=diagnostic,
    )
