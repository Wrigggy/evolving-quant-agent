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

from .candidate_admission import (
    AdmissionPolicy,
    CandidateAdmissionError,
    admit_candidate,
)
from .evaluation import (
    EvaluationSummary,
    OfficialTaskScore,
    TaskAttempt,
    aggregate_domain_macro,
)
from .evolution_evidence import EvidenceRecord, build_evolution_evidence
from .evolution_feedback import (
    FeedbackMode,
    feedback_contract_digest as compute_feedback_contract_digest,
    load_feedback_manifest,
    load_verifier_mapping,
)
from .evolve_runtime import diff_signature, dir_unified_diff, run_evolve_agent, snapshot_dir
from .worker_identity import (
    WorkerIdentityError,
    hash_worker_directory as _hash_worker_directory,
)


_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class EvolutionConfigError(ValueError):
    """The pilot configuration is unsafe or incompatible with its checkpoint."""


class BenchmarkEvaluator(Protocol):
    def evaluate(self, *, worker_dir, tasks, split, checkpoint, run_dir) -> EvaluationSummary: ...


LegacyProposer = Callable[[Path, dict, int, Path], dict]


@dataclass(frozen=True)
class EvolutionProposalContext:
    candidate_dir: Path
    evidence: EvidenceRecord
    diagnosis: dict
    iteration: int
    run_dir: Path
    history: tuple[dict, ...]


FullHarnessProposer = Callable[[EvolutionProposalContext], object]


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
    feedback_mode: FeedbackMode | str = FeedbackMode.CONTROL
    feedback_contract_digest: str = ""
    public_rubric_path: Path | str | None = None
    verifier_mapping_path: Path | str | None = None
    admission_policy_digest: str = ""
    task_manifest_digest: str = ""
    model_identity: str = "unspecified"
    template_identity_digest: str = "unspecified"

    def __post_init__(self) -> None:
        if self.n_iters not in {3, 5}:
            raise EvolutionConfigError("QFBench pilot n_iters must be 3 or 5")
        if not _RUN_ID_RE.fullmatch(self.run_id):
            raise EvolutionConfigError("run_id must be a path-safe identifier")
        if self.noise_floor < 0 or self.max_domain_regression < 0:
            raise EvolutionConfigError("noise and domain regression limits must be non-negative")
        if self.concurrency < 1:
            raise EvolutionConfigError("concurrency must be positive")
        try:
            FeedbackMode(self.feedback_mode)
        except ValueError as exc:
            raise EvolutionConfigError(
                f"unknown feedback mode {self.feedback_mode!r}"
            ) from exc
        if (self.public_rubric_path is None) != (self.verifier_mapping_path is None):
            raise EvolutionConfigError(
                "public rubric and verifier mapping must be configured together"
            )

    @property
    def full_harness(self) -> bool:
        return self.public_rubric_path is not None


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
    admitted: bool = True
    admission_failure: str | None = None
    evidence_digest: str | None = None
    official_evaluated: bool = True


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
    try:
        return _hash_worker_directory(root)
    except WorkerIdentityError as exc:
        raise EvolutionConfigError(str(exc)) from exc


def _sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).resolve().read_bytes()).hexdigest()


def _task_manifest_digest(
    benchmark_commit: str,
    optimize: tuple,
    held_out: tuple,
) -> str:
    payload = {
        "benchmark_commit": benchmark_commit,
        "optimize": [
            {
                "task_id": task.task_id,
                "domain": task.domain,
                "lineage": task.lineage,
            }
            for task in optimize
        ],
        "held_out": [
            {
                "task_id": task.task_id,
                "domain": task.domain,
                "lineage": task.lineage,
            }
            for task in held_out
        ],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _relative_artifact(path: Path, run_dir: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(run_dir).as_posix()
    except ValueError:
        return str(resolved)


def _json_safe(value, run_dir: Path):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Path):
        return _relative_artifact(value, run_dir)
    if isinstance(value, Mapping):
        return {
            str(key): _json_safe(item, run_dir)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item, run_dir) for item in value]
    return str(value)


def _proposal_metadata(proposal: object, run_dir: Path) -> dict:
    if proposal is None:
        return {}
    if isinstance(proposal, dict):
        return _json_safe(proposal, run_dir)
    payload: dict = {}
    for name in (
        "iteration",
        "candidate_digest",
        "input_bundle_sha256",
        "sandbox_id",
        "cleaned_up",
    ):
        if hasattr(proposal, name):
            payload[name] = getattr(proposal, name)
    for name in (
        "trace_uri",
        "final_uri",
        "prediction_uri",
        "access_summary_uri",
        "summary_uri",
        "command_log_uri",
        "lifecycle_uri",
        "dependency_lock_uri",
    ):
        value = getattr(proposal, name, None)
        if value is not None:
            payload[name] = _relative_artifact(Path(value), run_dir)
    return payload


def _failed_admission(
    *,
    policy_digest: str,
    edit_signature: str,
    failure: str,
) -> dict:
    return {
        "admitted": False,
        "candidate_digest": hashlib.sha256(
            f"unadmitted:{edit_signature}".encode()
        ).hexdigest(),
        "policy_digest": policy_digest,
        "files": [],
        "checks": [],
        "failure": failure,
    }


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
        _atomic_json(
            run_dir / "attempts" / attempt.attempt_id / "attempt.json",
            asdict(attempt),
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


def _backfill_legacy_fixed_schedule(
    *,
    run_dir: Path,
    state: dict,
    evaluator: BenchmarkEvaluator,
    optimize_tasks: tuple,
) -> None:
    """Score admitted legacy no-op records that skipped the fixed schedule."""

    skipped_reasons = {
        "candidate made no change",
        "candidate repeats a rejected edit",
    }
    history_by_iteration = {
        int(item["iteration"]): item for item in state.get("history", [])
    }
    backfilled = {
        int(item["iteration"]) for item in state.get("schedule_backfills", [])
    }
    for record in state.get("records", []):
        iteration = int(record["iteration"])
        legacy_skipped = (
            "official_evaluated" not in record
            and bool(record.get("admitted", True))
            and record.get("reason") in skipped_reasons
        )
        if not legacy_skipped or iteration in backfilled:
            continue
        candidate = run_dir / "workers" / f"iteration-{iteration:02d}-candidate"
        if not candidate.is_dir():
            raise EvolutionConfigError(
                f"fixed-schedule backfill candidate is missing: {candidate}"
            )
        checkpoint = f"iteration-{iteration}-candidate"
        summary = evaluator.evaluate(
            worker_dir=candidate,
            tasks=optimize_tasks,
            split="optimize",
            checkpoint=checkpoint,
            run_dir=run_dir,
        )
        record["official_evaluated"] = True
        history = history_by_iteration.get(iteration)
        if history is not None:
            history["official_evaluated"] = True
        state.setdefault("schedule_backfills", []).append({
            "iteration": iteration,
            "checkpoint": checkpoint,
            "candidate_worker": candidate.relative_to(run_dir).as_posix(),
            "summary": _summary_dict(summary),
        })
        _atomic_json(run_dir / "resume.json", state)


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
    proposer: LegacyProposer | FullHarnessProposer = nexau_process_proposer,
) -> BenchmarkEvolutionResult:
    optimize = tuple(optimize_tasks)
    held_out = tuple(held_out_tasks)
    _validate_task_sets(optimize, held_out)
    if not re.fullmatch(r"[0-9a-f]{40}", benchmark_commit):
        raise EvolutionConfigError("benchmark_commit must be a full SHA")

    seed_source = Path(config.seed_worker_dir).resolve()
    if not seed_source.is_dir():
        raise EvolutionConfigError(
            f"seed worker directory does not exist: {seed_source}"
        )
    feedback_mode = FeedbackMode(config.feedback_mode)
    held_out_ids = {task.task_id for task in held_out}
    policy = AdmissionPolicy.qfbench_full(
        forbidden_content=sorted(held_out_ids)
    )
    feedback_manifest = {}
    verifier_mapping = {}
    if config.full_harness:
        assert config.public_rubric_path is not None
        assert config.verifier_mapping_path is not None
        feedback_manifest = load_feedback_manifest(
            config.public_rubric_path,
            expected_task_ids={task.task_id for task in optimize},
            forbidden_task_ids=held_out_ids,
        )
        public_criteria = {
            task_id: {item.criterion_id for item in rubric.criteria}
            for task_id, rubric in feedback_manifest.items()
        }
        verifier_mapping = load_verifier_mapping(
            config.verifier_mapping_path,
            public_criteria=public_criteria,
        )
        computed_feedback_digest = compute_feedback_contract_digest(
            feedback_mode, config.public_rubric_path
        )
        if (
            config.feedback_contract_digest
            and config.feedback_contract_digest != computed_feedback_digest
        ):
            raise EvolutionConfigError(
                "configured feedback contract digest does not match mode/rubric"
            )
        if (
            config.admission_policy_digest
            and config.admission_policy_digest != policy.digest()
        ):
            raise EvolutionConfigError(
                "configured admission policy digest does not match active policy"
            )
        rubric_digest = _sha256_file(config.public_rubric_path)
        verifier_mapping_digest = _sha256_file(config.verifier_mapping_path)
        active_feedback_digest = computed_feedback_digest
        active_admission_digest = policy.digest()
    else:
        rubric_digest = "legacy-answer-free"
        verifier_mapping_digest = "legacy-answer-free"
        active_feedback_digest = (
            config.feedback_contract_digest or "legacy-answer-free-v1"
        )
        active_admission_digest = (
            config.admission_policy_digest or "legacy-process-only"
        )

    identity = {
        "arm": feedback_mode.value,
        "benchmark_commit": benchmark_commit,
        "task_manifest_digest": (
            config.task_manifest_digest
            or _task_manifest_digest(benchmark_commit, optimize, held_out)
        ),
        "feedback_contract_digest": active_feedback_digest,
        "public_rubric_digest": rubric_digest,
        "verifier_mapping_digest": verifier_mapping_digest,
        "admission_policy_digest": active_admission_digest,
        "model_identity": config.model_identity,
        "seed_digest": hash_worker_directory(seed_source),
        "template_identity_digest": config.template_identity_digest,
    }

    run_dir = Path(config.results_dir).resolve() / config.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    resume_path = run_dir / "resume.json"
    if resume_path.exists():
        if not config.resume:
            raise EvolutionConfigError(f"run {config.run_id} already has a checkpoint")
        state = json.loads(resume_path.read_text())
        if state.get("schema_version") != 2:
            raise EvolutionConfigError(
                f"resume checkpoint schema mismatch: expected 2, "
                f"found {state.get('schema_version')}"
            )
        expected = (config.run_id, config.n_iters, benchmark_commit)
        actual = (state.get("run_id"), state.get("n_iters"), state.get("benchmark_commit"))
        if actual != expected:
            raise EvolutionConfigError(f"resume checkpoint mismatch: expected {expected}, found {actual}")
        if state.get("identity") != identity:
            changed = sorted(
                key
                for key in set(identity) | set(state.get("identity", {}))
                if identity.get(key) != state.get("identity", {}).get(key)
            )
            raise EvolutionConfigError(
                f"resume immutable identity mismatch: {changed}"
            )
        if state.get("phase") == "complete":
            if config.full_harness:
                _backfill_legacy_fixed_schedule(
                    run_dir=run_dir,
                    state=state,
                    evaluator=evaluator,
                    optimize_tasks=optimize,
                )
            return _result_from_state(run_dir, state)
    else:
        seed_target = run_dir / "workers" / "seed"
        snapshot_dir(seed_source, seed_target)
        state = {
            "schema_version": 2,
            "run_id": config.run_id,
            "arm": feedback_mode.value,
            "n_iters": config.n_iters,
            "benchmark_commit": benchmark_commit,
            "identity": identity,
            "phase": "seed",
            "next_iteration": 1,
            "incumbent_worker": seed_target.relative_to(run_dir).as_posix(),
            "records": [],
            "history": [],
            "rejected_edit_signatures": [],
            "candidate_admissions": [],
            "proposals": [],
            "costs": [],
            "lifecycles": [],
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
            evidence: EvidenceRecord | None = None
            if config.full_harness:
                evidence = build_evolution_evidence(
                    mode=feedback_mode,
                    optimize_tasks=optimize,
                    held_out_task_ids=held_out_ids,
                    run_dir=run_dir,
                    destination=(
                        run_dir
                        / "evidence"
                        / f"iteration-{iteration:02d}-{feedback_mode.value}"
                    ),
                    feedback_manifest=feedback_manifest,
                    verifier_mapping=verifier_mapping,
                    history=tuple(state["history"]),
                )
                proposal_context = EvolutionProposalContext(
                    candidate_dir=candidate,
                    evidence=evidence,
                    diagnosis=diagnosis,
                    iteration=iteration,
                    run_dir=run_dir,
                    history=tuple(state["history"]),
                )
                proposal_raw = proposer(proposal_context)
                proposed_candidate = getattr(
                    proposal_raw, "candidate_dir", candidate
                )
                if isinstance(proposal_raw, dict) and proposal_raw.get("candidate_dir"):
                    proposed_candidate = Path(proposal_raw["candidate_dir"])
                proposed_path = Path(proposed_candidate).resolve()
                if proposed_path != candidate.resolve():
                    try:
                        proposed_path.relative_to(run_dir)
                    except ValueError as exc:
                        raise EvolutionConfigError(
                            "proposer candidate output is outside the run directory"
                        ) from exc
                    snapshot_dir(proposed_path, candidate)
            else:
                proposal_raw = proposer(candidate, diagnosis, iteration, run_dir)
            proposal = _proposal_metadata(proposal_raw, run_dir)
            if config.full_harness:
                try:
                    admission_record = admit_candidate(
                        run_dir / "workers" / "seed",
                        candidate,
                        policy,
                    )
                    admission = asdict(admission_record)
                    edit = dir_unified_diff(incumbent_worker, candidate)
                    signature = diff_signature(edit)
                except CandidateAdmissionError as exc:
                    failure = f"{type(exc).__name__}: {exc}"
                    edit = ""
                    signature = hashlib.sha256(
                        f"admission-rejected:{failure}".encode()
                    ).hexdigest()
                    admission = _failed_admission(
                        policy_digest=active_admission_digest,
                        edit_signature=signature,
                        failure=failure,
                    )
            else:
                edit = dir_unified_diff(incumbent_worker, candidate)
                signature = diff_signature(edit)
                admission = {
                    "admitted": True,
                    "candidate_digest": hash_worker_directory(candidate),
                    "policy_digest": active_admission_digest,
                    "files": [],
                    "checks": ["legacy_process_only"],
                    "failure": None,
                }
            edit_path = run_dir / f"iteration-{iteration:02d}" / "edit.diff"
            edit_path.parent.mkdir(parents=True, exist_ok=True)
            edit_path.write_text(edit)
            admission_path = edit_path.parent / "admission.json"
            _atomic_json(admission_path, admission)
            proposal.update({
                "iteration": iteration,
                "evidence_digest": evidence.sha256 if evidence else None,
                "evidence_members": list(evidence.members) if evidence else [],
                "admission_path": admission_path.relative_to(run_dir).as_posix(),
            })
            proposal_path = edit_path.parent / "proposal.json"
            _atomic_json(proposal_path, proposal)
            pending = {
                "iteration": iteration,
                "candidate_worker": candidate.relative_to(run_dir).as_posix(),
                "candidate_worker_digest": admission["candidate_digest"],
                "edit_signature": signature,
                "edit_path": edit_path.relative_to(run_dir).as_posix(),
                "proposal_trace": dict(proposal.get("trace", {})),
                "proposal_path": proposal_path.relative_to(run_dir).as_posix(),
                "evidence_digest": evidence.sha256 if evidence else None,
                "admission": admission,
            }
            state["proposals"].append(proposal)
            state["candidate_admissions"].append(admission)
            if proposal.get("lifecycle_uri"):
                state["lifecycles"].append(proposal["lifecycle_uri"])
            if proposal.get("summary_uri"):
                summary_file = run_dir / str(proposal["summary_uri"])
                if summary_file.is_file():
                    try:
                        usage = json.loads(summary_file.read_text()).get(
                            "model_usage"
                        )
                    except (OSError, json.JSONDecodeError):
                        usage = None
                    state["costs"].append({
                        "iteration": iteration,
                        "model_usage": usage,
                        "reason": None if usage else "usage unavailable",
                    })
            state["pending_candidate"] = pending
            state["phase"] = "evaluate_candidate"
            _atomic_json(resume_path, state)
        elif int(pending.get("iteration", -1)) != iteration:
            raise EvolutionConfigError("pending candidate iteration does not match checkpoint")

        candidate = (run_dir / pending["candidate_worker"]).resolve()
        signature = pending["edit_signature"]
        admission = dict(pending.get("admission", {}))
        admitted = bool(admission.get("admitted", not config.full_harness))
        admission_failure = admission.get("failure")
        official_evaluated = False
        if not admitted:
            kept, reason, deltas = (
                False,
                f"candidate admission rejected: {admission_failure}",
                {domain: 0.0 for domain in incumbent_summary.domain_scores},
            )
            candidate_summary = incumbent_summary
        elif not (run_dir / pending["edit_path"]).read_text():
            candidate_summary = evaluator.evaluate(
                worker_dir=candidate,
                tasks=optimize,
                split="optimize",
                checkpoint=f"iteration-{iteration}-candidate",
                run_dir=run_dir,
            )
            _, _, deltas = _accept_candidate(
                incumbent_summary, candidate_summary, config
            )
            kept, reason = False, "candidate made no change"
            official_evaluated = True
        elif signature in set(state["rejected_edit_signatures"]):
            candidate_summary = evaluator.evaluate(
                worker_dir=candidate,
                tasks=optimize,
                split="optimize",
                checkpoint=f"iteration-{iteration}-candidate",
                run_dir=run_dir,
            )
            _, _, deltas = _accept_candidate(
                incumbent_summary, candidate_summary, config
            )
            kept, reason = False, "candidate repeats a rejected edit"
            official_evaluated = True
        else:
            candidate_summary = evaluator.evaluate(
                worker_dir=candidate,
                tasks=optimize,
                split="optimize",
                checkpoint=f"iteration-{iteration}-candidate",
                run_dir=run_dir,
            )
            kept, reason, deltas = _accept_candidate(incumbent_summary, candidate_summary, config)
            official_evaluated = True

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
            admitted=admitted,
            admission_failure=admission_failure,
            evidence_digest=pending.get("evidence_digest"),
            official_evaluated=official_evaluated,
        )
        state["records"].append(asdict(record))
        state["history"].append({
            "iteration": iteration,
            "edit_signature": signature,
            "candidate_worker_digest": pending["candidate_worker_digest"],
            "admitted": admitted,
            "admission_failure": admission_failure,
            "kept": kept,
            "reason": reason,
            "incumbent_before": incumbent_summary.overall,
            "candidate_overall": candidate_summary.overall,
            "incumbent_after": incumbent_after,
            "evidence_digest": pending.get("evidence_digest"),
            "official_evaluated": official_evaluated,
        })
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
        "schema_version": 2,
        "run_id": result.run_id,
        "arm": state["arm"],
        "identity": state["identity"],
        "records": [asdict(record) for record in result.records],
        "optimize_trajectory": result.optimize_trajectory,
        "optimize_final": _summary_dict(result.optimize_final),
        "held_out_seed": _summary_dict(result.held_out_seed),
        "held_out_final": _summary_dict(result.held_out_final),
        "final_worker_dir": str(result.final_worker_dir),
    })
    return result
