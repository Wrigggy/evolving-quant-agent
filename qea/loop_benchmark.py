"""Benchmark-neutral Level-B evolution with optimize/held-out isolation and resume."""

from __future__ import annotations

import hashlib
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable, Mapping, Protocol

from .evaluation import (
    EvaluationSummary,
    OfficialTaskScore,
    TaskAttempt,
    aggregate_domain_macro,
)
from .evolve_runtime import diff_signature, dir_unified_diff, run_evolve_agent, snapshot_dir


_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class EvolutionConfigError(ValueError):
    """The pilot configuration is unsafe or incompatible with its checkpoint."""


class BenchmarkEvaluator(Protocol):
    def evaluate(self, *, worker_dir, tasks, split, checkpoint, run_dir) -> EvaluationSummary: ...


Proposer = Callable[[Path, dict, int, Path], dict]


@dataclass(frozen=True)
class BenchmarkEvolutionConfig:
    run_id: str
    n_iters: int
    results_dir: Path | str
    seed_worker_dir: Path | str
    noise_floor: float = 0.02
    max_domain_regression: float = 0.0
    concurrency: int = 3
    resume: bool = True

    def __post_init__(self) -> None:
        if self.n_iters not in {3, 5}:
            raise EvolutionConfigError("QFBench pilot n_iters must be 3 or 5")
        if not _RUN_ID_RE.fullmatch(self.run_id):
            raise EvolutionConfigError("run_id must be a path-safe identifier")
        if self.noise_floor < 0 or self.max_domain_regression < 0:
            raise EvolutionConfigError("noise and domain regression limits must be non-negative")
        if self.concurrency < 1:
            raise EvolutionConfigError("concurrency must be positive")


@dataclass(frozen=True)
class BenchmarkIterationRecord:
    iteration: int
    edit_signature: str
    candidate_worker_digest: str
    incumbent_before: float
    candidate_overall: float
    incumbent_after: float
    kept: bool
    reason: str
    domain_deltas: dict[str, float]


@dataclass(frozen=True)
class BenchmarkEvolutionResult:
    run_id: str
    run_dir: Path
    records: tuple[BenchmarkIterationRecord, ...]
    optimize_trajectory: tuple[float, ...]
    optimize_final: EvaluationSummary
    held_out_seed: EvaluationSummary
    held_out_final: EvaluationSummary
    final_worker_dir: Path

    @property
    def n_kept(self) -> int:
        return sum(record.kept for record in self.records)


def hash_worker_directory(root: str | Path) -> str:
    directory = Path(root).resolve()
    if not directory.is_dir():
        raise EvolutionConfigError(f"worker directory does not exist: {directory}")
    digest = hashlib.sha256()
    files = sorted(
        (path for path in directory.rglob("*")
         if path.is_file() and ".git" not in path.parts and "__pycache__" not in path.parts),
        key=lambda path: path.relative_to(directory).as_posix(),
    )
    for path in files:
        relative = path.relative_to(directory).as_posix().encode()
        payload = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


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


def _summary_from_dict(payload: dict) -> EvaluationSummary:
    scores = tuple(OfficialTaskScore(
        **{**item, "diagnostic_tags": tuple(item.get("diagnostic_tags", ())) }
    ) for item in payload["scores"])
    return EvaluationSummary(
        scores=scores,
        task_rewards={str(key): float(value) for key, value in payload["task_rewards"].items()},
        domain_scores={str(key): float(value) for key, value in payload["domain_scores"].items()},
        task_mean=float(payload["task_mean"]),
        overall=float(payload["overall"]),
    )


def _answer_free_diagnosis(summary: EvaluationSummary) -> dict:
    feedback = [{
        "task_id": score.task_id,
        "official_reward": score.reward,
        "diagnostic_tags": list(score.diagnostic_tags),
    } for score in summary.scores]
    tags = sorted({tag for score in summary.scores for tag in score.diagnostic_tags})
    root_cause = tags[0] if tags else "process_headroom"
    return {
        "root_cause_tag": root_cause,
        "deficiency_category": "official_verifier_feedback",
        "suggested_target_slot": "prompt",
        "overview": (
            f"Optimize domain macro is {summary.overall:.6f}; "
            f"{sum(bool(score.diagnostic_tags) for score in summary.scores)} tasks have coarse failure tags."
        ),
        "optimize_feedback": feedback,
    }


def nexau_process_proposer(candidate_dir: Path, diagnosis: dict, iteration: int, run_dir: Path) -> dict:
    return run_evolve_agent(candidate_dir, diagnosis, run_dir / f"iteration-{iteration:02d}")


class QFBenchE2BEvaluator:
    """Evaluate task attempts concurrently and resume from per-task official scores."""

    def __init__(
        self,
        *,
        benchmark_commit: str,
        run_id: str,
        executor,
        verifier,
        model_env: Mapping[str, str],
        max_workers: int = 3,
    ) -> None:
        if not re.fullmatch(r"[0-9a-f]{40}", benchmark_commit):
            raise EvolutionConfigError("benchmark_commit must be a full SHA")
        if max_workers < 1:
            raise EvolutionConfigError("max_workers must be positive")
        self.benchmark_commit = benchmark_commit
        self.run_id = run_id
        self.executor = executor
        self.verifier = verifier
        self.model_env = dict(model_env)
        self.max_workers = max_workers

    @staticmethod
    def _completed_score_path(run_dir: Path, attempt: TaskAttempt) -> Path:
        return run_dir / "attempts" / attempt.attempt_id / "completed-score.json"

    def _load_score(self, run_dir: Path, attempt: TaskAttempt, task) -> OfficialTaskScore | None:
        path = self._completed_score_path(run_dir, attempt)
        if not path.is_file():
            return None
        payload = json.loads(path.read_text())
        score = OfficialTaskScore(
            **{**payload, "diagnostic_tags": tuple(payload.get("diagnostic_tags", ())) }
        )
        if score.task_id != task.task_id or score.domain != task.domain:
            raise EvolutionConfigError(f"completed score identity mismatch for {task.task_id}")
        return score

    def _score_task(
        self,
        *,
        task,
        worker_dir: Path,
        worker_digest: str,
        split: str,
        checkpoint: str,
        run_dir: Path,
    ) -> OfficialTaskScore:
        attempt = TaskAttempt.create(
            run_id=self.run_id,
            benchmark_commit=self.benchmark_commit,
            task_id=task.task_id,
            split=split,
            checkpoint=checkpoint,
            worker_digest=worker_digest,
        )
        completed = self._load_score(run_dir, attempt, task)
        if completed is not None:
            return completed

        from .executors.e2b_nexau import E2BWorkerTimeout, load_worker_execution

        execution = load_worker_execution(attempt, run_dir)
        if execution is None:
            try:
                execution = self.executor.execute(
                    attempt=attempt,
                    task=task,
                    worker_dir=worker_dir,
                    run_dir=run_dir,
                    model_env=self.model_env,
                )
            except E2BWorkerTimeout as exc:
                score = OfficialTaskScore(
                    task_id=task.task_id,
                    domain=task.domain,
                    reward=0.0,
                    diagnostic_tags=("timeout",),
                    log_uri=exc.log_uri,
                )
                _atomic_json(self._completed_score_path(run_dir, attempt), asdict(score))
                return score
        score = self.verifier.verify(
            attempt=attempt,
            task=task,
            execution=execution,
            run_dir=run_dir,
        )
        _atomic_json(self._completed_score_path(run_dir, attempt), asdict(score))
        return score

    def evaluate(
        self,
        *,
        worker_dir,
        tasks,
        split,
        checkpoint,
        run_dir,
    ) -> EvaluationSummary:
        task_list = tuple(tasks)
        if not task_list:
            raise EvolutionConfigError("cannot evaluate an empty task set")
        worker_path = Path(worker_dir).resolve()
        run_path = Path(run_dir).resolve()
        worker_digest = hash_worker_directory(worker_path)
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(task_list))) as pool:
            futures = [pool.submit(
                self._score_task,
                task=task,
                worker_dir=worker_path,
                worker_digest=worker_digest,
                split=split,
                checkpoint=checkpoint,
                run_dir=run_path,
            ) for task in task_list]
            scores = tuple(future.result() for future in futures)
        summary = aggregate_domain_macro(
            scores, expected_domains={task.domain for task in task_list}
        )
        safe_checkpoint = re.sub(r"[^A-Za-z0-9_.-]+", "-", checkpoint)
        _atomic_json(run_path / "evaluations" / f"{safe_checkpoint}-{worker_digest[:12]}.json", {
            "benchmark_commit": self.benchmark_commit,
            "run_id": self.run_id,
            "split": split,
            "checkpoint": checkpoint,
            "worker_digest": worker_digest,
            "summary": _summary_dict(summary),
        })
        return summary


def _validate_task_sets(optimize_tasks: tuple, held_out_tasks: tuple) -> None:
    if not optimize_tasks or not held_out_tasks:
        raise EvolutionConfigError("optimize and held-out task sets must both be non-empty")
    optimize_ids = {task.task_id for task in optimize_tasks}
    held_ids = {task.task_id for task in held_out_tasks}
    if len(optimize_ids) != len(optimize_tasks) or len(held_ids) != len(held_out_tasks):
        raise EvolutionConfigError("task IDs must be unique within each split")
    if optimize_ids & held_ids:
        raise EvolutionConfigError("optimize and held-out task IDs overlap")
    optimize_lineages = {task.lineage for task in optimize_tasks}
    held_lineages = {task.lineage for task in held_out_tasks}
    if optimize_lineages & held_lineages:
        raise EvolutionConfigError("optimize and held-out lineages overlap")


def _accept_candidate(
    incumbent: EvaluationSummary,
    candidate: EvaluationSummary,
    config: BenchmarkEvolutionConfig,
) -> tuple[bool, str, dict[str, float]]:
    if set(incumbent.domain_scores) != set(candidate.domain_scores):
        raise EvolutionConfigError("candidate evaluation changed optimize domains")
    deltas = {
        domain: candidate.domain_scores[domain] - incumbent.domain_scores[domain]
        for domain in sorted(incumbent.domain_scores)
    }
    regressed = [
        domain for domain, delta in deltas.items()
        if delta < -config.max_domain_regression
    ]
    if regressed:
        return False, f"domain regression: {', '.join(regressed)}", deltas
    gain = candidate.overall - incumbent.overall
    if gain <= config.noise_floor:
        return False, f"gain {gain:.6f} did not exceed noise floor {config.noise_floor:.6f}", deltas
    return True, f"gain {gain:.6f} with no domain regression", deltas


def _result_from_state(run_dir: Path, state: dict) -> BenchmarkEvolutionResult:
    records = tuple(BenchmarkIterationRecord(**record) for record in state["records"])
    seed_optimize = _summary_from_dict(state["seed_optimize"])
    trajectory = [seed_optimize.overall]
    trajectory.extend(record.candidate_overall for record in records if record.kept)
    return BenchmarkEvolutionResult(
        run_id=state["run_id"],
        run_dir=run_dir,
        records=records,
        optimize_trajectory=tuple(trajectory),
        optimize_final=_summary_from_dict(state["incumbent_summary"]),
        held_out_seed=_summary_from_dict(state["held_out_seed"]),
        held_out_final=_summary_from_dict(state["held_out_final"]),
        final_worker_dir=(run_dir / state["incumbent_worker"]).resolve(),
    )


def run_benchmark_evolution(
    config: BenchmarkEvolutionConfig,
    *,
    optimize_tasks: Iterable,
    held_out_tasks: Iterable,
    benchmark_commit: str,
    evaluator: BenchmarkEvaluator,
    proposer: Proposer = nexau_process_proposer,
) -> BenchmarkEvolutionResult:
    optimize = tuple(optimize_tasks)
    held_out = tuple(held_out_tasks)
    _validate_task_sets(optimize, held_out)
    if not re.fullmatch(r"[0-9a-f]{40}", benchmark_commit):
        raise EvolutionConfigError("benchmark_commit must be a full SHA")

    run_dir = Path(config.results_dir).resolve() / config.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    resume_path = run_dir / "resume.json"
    if resume_path.exists():
        if not config.resume:
            raise EvolutionConfigError(f"run {config.run_id} already has a checkpoint")
        state = json.loads(resume_path.read_text())
        expected = (config.run_id, config.n_iters, benchmark_commit)
        actual = (state.get("run_id"), state.get("n_iters"), state.get("benchmark_commit"))
        if actual != expected:
            raise EvolutionConfigError(f"resume checkpoint mismatch: expected {expected}, found {actual}")
        if state.get("phase") == "complete":
            return _result_from_state(run_dir, state)
    else:
        seed_source = Path(config.seed_worker_dir).resolve()
        if not seed_source.is_dir():
            raise EvolutionConfigError(f"seed worker directory does not exist: {seed_source}")
        seed_target = run_dir / "workers" / "seed"
        snapshot_dir(seed_source, seed_target)
        state = {
            "schema_version": 1,
            "run_id": config.run_id,
            "n_iters": config.n_iters,
            "benchmark_commit": benchmark_commit,
            "phase": "seed",
            "next_iteration": 1,
            "incumbent_worker": seed_target.relative_to(run_dir).as_posix(),
            "records": [],
            "rejected_edit_signatures": [],
            "pending_candidate": None,
        }
        _atomic_json(resume_path, state)

    if state["phase"] == "seed":
        incumbent_worker = (run_dir / state["incumbent_worker"]).resolve()
        seed_optimize = evaluator.evaluate(
            worker_dir=incumbent_worker,
            tasks=optimize,
            split="optimize",
            checkpoint="seed-optimize",
            run_dir=run_dir,
        )
        seed_held_out = evaluator.evaluate(
            worker_dir=incumbent_worker,
            tasks=held_out,
            split="held_out",
            checkpoint="seed-held-out",
            run_dir=run_dir,
        )
        state.update({
            "seed_optimize": _summary_dict(seed_optimize),
            "incumbent_summary": _summary_dict(seed_optimize),
            "held_out_seed": _summary_dict(seed_held_out),
            "phase": "propose",
        })
        _atomic_json(resume_path, state)

    while int(state["next_iteration"]) <= config.n_iters:
        iteration = int(state["next_iteration"])
        incumbent_worker = (run_dir / state["incumbent_worker"]).resolve()
        incumbent_summary = _summary_from_dict(state["incumbent_summary"])
        pending = state.get("pending_candidate")
        if pending is None:
            candidate = run_dir / "workers" / f"iteration-{iteration:02d}-candidate"
            snapshot_dir(incumbent_worker, candidate)
            diagnosis = _answer_free_diagnosis(incumbent_summary)
            proposal = proposer(candidate, diagnosis, iteration, run_dir) or {}
            edit = dir_unified_diff(incumbent_worker, candidate)
            signature = diff_signature(edit)
            edit_path = run_dir / f"iteration-{iteration:02d}" / "edit.diff"
            edit_path.parent.mkdir(parents=True, exist_ok=True)
            edit_path.write_text(edit)
            pending = {
                "iteration": iteration,
                "candidate_worker": candidate.relative_to(run_dir).as_posix(),
                "candidate_worker_digest": hash_worker_directory(candidate),
                "edit_signature": signature,
                "edit_path": edit_path.relative_to(run_dir).as_posix(),
                "proposal_trace": dict(proposal.get("trace", {})),
            }
            state["pending_candidate"] = pending
            state["phase"] = "evaluate_candidate"
            _atomic_json(resume_path, state)
        elif int(pending.get("iteration", -1)) != iteration:
            raise EvolutionConfigError("pending candidate iteration does not match checkpoint")

        candidate = (run_dir / pending["candidate_worker"]).resolve()
        signature = pending["edit_signature"]
        if not (run_dir / pending["edit_path"]).read_text():
            kept, reason, deltas = False, "candidate made no change", {
                domain: 0.0 for domain in incumbent_summary.domain_scores
            }
            candidate_summary = incumbent_summary
        elif signature in set(state["rejected_edit_signatures"]):
            kept, reason, deltas = False, "candidate repeats a rejected edit", {
                domain: 0.0 for domain in incumbent_summary.domain_scores
            }
            candidate_summary = incumbent_summary
        else:
            candidate_summary = evaluator.evaluate(
                worker_dir=candidate,
                tasks=optimize,
                split="optimize",
                checkpoint=f"iteration-{iteration}-candidate",
                run_dir=run_dir,
            )
            kept, reason, deltas = _accept_candidate(incumbent_summary, candidate_summary, config)

        if kept:
            state["incumbent_worker"] = pending["candidate_worker"]
            state["incumbent_summary"] = _summary_dict(candidate_summary)
            incumbent_after = candidate_summary.overall
        else:
            state["rejected_edit_signatures"].append(signature)
            incumbent_after = incumbent_summary.overall
        record = BenchmarkIterationRecord(
            iteration=iteration,
            edit_signature=signature,
            candidate_worker_digest=pending["candidate_worker_digest"],
            incumbent_before=incumbent_summary.overall,
            candidate_overall=candidate_summary.overall,
            incumbent_after=incumbent_after,
            kept=kept,
            reason=reason,
            domain_deltas=deltas,
        )
        state["records"].append(asdict(record))
        state["pending_candidate"] = None
        state["next_iteration"] = iteration + 1
        state["phase"] = "propose" if iteration < config.n_iters else "final_held_out"
        _atomic_json(resume_path, state)

    if state["phase"] != "complete":
        final_worker = (run_dir / state["incumbent_worker"]).resolve()
        final_held_out = evaluator.evaluate(
            worker_dir=final_worker,
            tasks=held_out,
            split="held_out",
            checkpoint="final-held-out",
            run_dir=run_dir,
        )
        state["held_out_final"] = _summary_dict(final_held_out)
        state["phase"] = "complete"
        _atomic_json(resume_path, state)

    result = _result_from_state(run_dir, state)
    _atomic_json(run_dir / "result.json", {
        "run_id": result.run_id,
        "records": [asdict(record) for record in result.records],
        "optimize_trajectory": result.optimize_trajectory,
        "optimize_final": _summary_dict(result.optimize_final),
        "held_out_seed": _summary_dict(result.held_out_seed),
        "held_out_final": _summary_dict(result.held_out_final),
        "final_worker_dir": str(result.final_worker_dir),
    })
    return result
