"""Run one deterministic, admitted QuantCodeEval PGBHS candidate panel."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from .candidate_admission import AdmissionPolicy, admit_candidate
from .evaluation import OfficialTaskScore, TaskAttempt, aggregate_domain_macro
from .executors.execution_record import (
    load_persisted_worker_artifact_contract,
    persist_artifact_contract_recovery,
)
from .mutation_metrics import measure_mutation
from .qfbench_baseline import audit_fixed_checkpoint_proxy_costs
from .quantcodeeval_baseline import (
    MODEL,
    SPLIT,
    _atomic_private_json,
    _route_evidence,
    prepare_quantcodeeval_h0,
)
from .quantcodeeval_mutations import materialize_quantcodeeval_mutation


def _canonical_sha256(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _source_sha256() -> dict[str, str]:
    package = Path(__file__).resolve().parent
    paths = {
        "candidate_admission.py": package / "candidate_admission.py",
        "mutation_metrics.py": package / "mutation_metrics.py",
        "quantcodeeval_candidate.py": package / "quantcodeeval_candidate.py",
        "quantcodeeval_mutations.py": package / "quantcodeeval_mutations.py",
        "quantcodeeval_pgbs.py": package / "quantcodeeval_pgbs.py",
    }
    return {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in sorted(paths.items())
    }


def _answer_free_sidecar(attempt_dir: Path) -> Path:
    verifier = attempt_dir / "verifier" / "answer-free-evidence.json"
    worker_zero = attempt_dir / "answer-free-worker-zero.json"
    if verifier.is_file() == worker_zero.is_file():
        raise ValueError("attempt must have exactly one answer-free score surface")
    return verifier if verifier.is_file() else worker_zero


def run_quantcodeeval_candidate(
    *,
    config_path: str | Path,
    public_root: str | Path,
    trusted_root: str | Path,
    run_dir: str | Path,
    seed_worker_dir: str | Path,
    parent_worker_dir: str | Path,
    failure_class: str,
    iteration: int,
    worker_image_ref: str,
    verifier_image_ref: str,
    proxy_image_ref: str,
    token_file: str | Path,
    source_h0_evaluation_id: str,
    preflight_only: bool = False,
) -> dict[str, object]:
    """Materialize, admit, and evaluate one single-component candidate."""

    root = Path(run_dir).resolve()
    mutation = materialize_quantcodeeval_mutation(
        parent_worker_dir,
        failure_class,
        iteration,
        output_root=root / "mutations",
    )
    if mutation.candidate_dir is None:
        raise ValueError("candidate runner requires an ACT mutation")
    snapshot, evaluator, preflight, frozen_seed = prepare_quantcodeeval_h0(
        config_path=config_path,
        public_root=public_root,
        trusted_root=trusted_root,
        run_dir=root,
        worker_dir=seed_worker_dir,
        worker_image_ref=worker_image_ref,
        verifier_image_ref=verifier_image_ref,
        proxy_image_ref=proxy_image_ref,
    )
    admission_record = admit_candidate(
        frozen_seed,
        mutation.candidate_dir,
        AdmissionPolicy.qfbench_full(),
    )
    metrics = measure_mutation(
        before_root=Path(parent_worker_dir).resolve(),
        after_root=mutation.candidate_dir,
        declared_roles=("systemprompt",),
    )
    if (
        not admission_record.admitted
        or metrics["changed_file_count"] != 1
        or metrics["component_roles"] != ["systemprompt"]
        or metrics["declared_roles_match_actual"] is not True
    ):
        raise ValueError("candidate admission or single-component identity differs")
    checkpoint = f"quantcodeeval-pgbs-iteration-{iteration:02d}"
    panel_identity = {
        "benchmark_commit": snapshot.commit,
        "public_manifest_sha256": preflight["public_manifest_sha256"],
        "trusted_manifest_sha256": preflight["trusted_manifest_sha256"],
        "task_ids": list(snapshot.optimize.task_ids),
    }
    sampling_identity = {
        "model": MODEL,
        "required_provider": "deepseek",
        "allow_fallbacks": False,
        "split": SPLIT,
        "runtime_identity_sha256": preflight["runtime_identity_sha256"],
        "worker_image_ref": worker_image_ref,
        "verifier_image_ref": verifier_image_ref,
        "proxy_image_ref": proxy_image_ref,
        "worker_concurrency": 1,
        "verifier_concurrency": 1,
    }
    plan = {
        "schema_version": 1,
        "protocol": "quant_property_v1_candidate",
        "status": "preflight_complete",
        "run_id": root.name,
        "iteration": iteration,
        "failure_class": failure_class,
        "source_h0_evaluation_id": source_h0_evaluation_id,
        "h0_resampled": False,
        "model": MODEL,
        "runtime_identity_sha256": preflight["runtime_identity_sha256"],
        "candidate_coordinator_source_sha256": _source_sha256(),
        "panel_identity_sha256": _canonical_sha256(panel_identity),
        "sampling_identity_sha256": _canonical_sha256(sampling_identity),
        "mutation": mutation.record.to_dict(),
        "admission": asdict(admission_record),
        "candidate_worker_digest": mutation.record.candidate_digest,
        "candidate_admission_manifest_digest": admission_record.candidate_digest,
        "mutation_metrics": metrics,
        "checkpoint": checkpoint,
        "task_ids": list(snapshot.optimize.task_ids),
        "model_request_count": 0,
    }
    # ``asdict`` preserves tuple-valued dataclass fields, while JSON reloads
    # them as lists.  Normalize before both persistence and resume comparison.
    plan = json.loads(json.dumps(plan, sort_keys=True))
    plan_path = root / "CANDIDATE-PREFLIGHT.json"
    if plan_path.is_file():
        persisted_plan = json.loads(plan_path.read_text(encoding="utf-8"))
        if persisted_plan != plan:
            differing = sorted(
                key
                for key in set(persisted_plan) | set(plan)
                if persisted_plan.get(key) != plan.get(key)
            )
            raise ValueError(
                "persisted candidate preflight differs in fields: "
                + ", ".join(differing)
            )
    else:
        _atomic_private_json(plan_path, plan)
    if preflight_only:
        return plan

    summary = evaluator.evaluate(
        worker_dir=mutation.candidate_dir,
        tasks=snapshot.optimize.tasks,
        split=SPLIT,
        checkpoint=checkpoint,
        run_dir=root,
    )
    cost = audit_fixed_checkpoint_proxy_costs(
        root,
        expected_attempts=len(snapshot.optimize.tasks),
        checkpoint=checkpoint,
        split=SPLIT,
    )
    route = _route_evidence(root, Path(token_file).resolve())
    attempt_rows = []
    for task in snapshot.optimize.tasks:
        attempt = TaskAttempt.create(
            run_id=root.name,
            benchmark_commit=snapshot.commit,
            task_id=task.task_id,
            split=SPLIT,
            checkpoint=checkpoint,
            worker_digest=str(mutation.record.candidate_digest),
        )
        sidecar = _answer_free_sidecar(root / "attempts" / attempt.attempt_id)
        attempt_rows.append(
            {
                "task_id": task.task_id,
                "attempt_id": attempt.attempt_id,
                "answer_free_evidence": json.loads(
                    sidecar.read_text(encoding="utf-8")
                ),
            }
        )
    evaluation_identity = _canonical_sha256(
        {
            "checkpoint": checkpoint,
            "worker_digest": mutation.record.candidate_digest,
            "panel_identity_sha256": plan["panel_identity_sha256"],
            "sampling_identity_sha256": plan["sampling_identity_sha256"],
            "attempts": attempt_rows,
        }
    )
    result = {
        **plan,
        "status": "complete",
        "model_request_count": cost["request_count"],
        "attempts": attempt_rows,
        "score_summary": {
            "task_rewards": summary.task_rewards,
            "domain_scores": summary.domain_scores,
            "task_mean": summary.task_mean,
            "overall": summary.overall,
            "scores": [asdict(score) for score in summary.scores],
        },
        "cost_audit": cost,
        "route_evidence": route,
        "evaluation_identity_sha256": evaluation_identity,
    }
    result_path = root / "CANDIDATE-RESULT.json"
    if result_path.is_file():
        if json.loads(result_path.read_text(encoding="utf-8")) != result:
            raise ValueError("persisted candidate result differs")
    else:
        _atomic_private_json(result_path, result)
    return result


def recover_quantcodeeval_candidate_artifact_zero(
    *,
    run_dir: str | Path,
    source_h0_run_dir: str | Path,
    token_file: str | Path,
) -> dict[str, object]:
    """Finalize a panel whose missing artifact was already measured before a crash."""

    root = Path(run_dir).resolve()
    plan = json.loads((root / "CANDIDATE-PREFLIGHT.json").read_text(encoding="utf-8"))
    h0 = json.loads(
        (Path(source_h0_run_dir).resolve() / "H0-RESULT.json").read_text(
            encoding="utf-8"
        )
    )
    h0_families = {
        str(row["task_id"]): row["answer_free_evidence"]["property_families"]
        for row in h0["attempts"]
    }
    benchmark_commit = json.loads(
        (root / "H0-PREFLIGHT.json").read_text(encoding="utf-8")
    )["benchmark_commit"]
    worker_digest = str(plan["candidate_worker_digest"])
    checkpoint = str(plan["checkpoint"])
    for task_id in plan["task_ids"]:
        attempt = TaskAttempt.create(
            run_id=str(plan["run_id"]),
            benchmark_commit=str(benchmark_commit),
            task_id=str(task_id),
            split=SPLIT,
            checkpoint=checkpoint,
            worker_digest=worker_digest,
        )
        attempt_dir = root / "attempts" / attempt.attempt_id
        score_path = attempt_dir / "completed-score.json"
        if score_path.is_file() and (
            (attempt_dir / "verifier" / "answer-free-evidence.json").is_file()
            or (attempt_dir / "answer-free-worker-zero.json").is_file()
        ):
            continue
        evidence = load_persisted_worker_artifact_contract(attempt, root)
        if evidence is None:
            raise ValueError(f"{task_id} has no persisted artifact-contract zero")
        persist_artifact_contract_recovery(attempt_dir, evidence)
        score = OfficialTaskScore(
            task_id=str(task_id),
            domain="volatility" if task_id == "T16" else "event_strategy",
            reward=0.0,
            diagnostic_tags=("missing_artifact",),
            log_uri=evidence.log_uri,
        )
        if score_path.is_file():
            existing_score = json.loads(score_path.read_text(encoding="utf-8"))
            if (
                existing_score.get("reward") != 0.0
                or existing_score.get("diagnostic_tags") != ["missing_artifact"]
                or existing_score.get("task_id") != task_id
            ):
                raise ValueError("persisted artifact-zero score identity differs")
        else:
            _atomic_private_json(score_path, asdict(score))
        families = h0_families[str(task_id)]
        summary = {
            "schema_version": 1,
            "benchmark": "quantcodeeval",
            "official_reward": 0.0,
            "property_families": {
                name: {
                    "total": int(value["total"]),
                    "passed": 0,
                    "failed": 0,
                    "skipped": int(value["total"]),
                    "errors": 0,
                }
                for name, value in families.items()
            },
            "diagnostic_tags": ["missing_artifact"],
        }
        _atomic_private_json(attempt_dir / "answer-free-worker-zero.json", summary)

    scores: list[OfficialTaskScore] = []
    attempt_rows: list[dict[str, object]] = []
    for task_id in plan["task_ids"]:
        attempt = TaskAttempt.create(
            run_id=str(plan["run_id"]),
            benchmark_commit=str(benchmark_commit),
            task_id=str(task_id),
            split=SPLIT,
            checkpoint=checkpoint,
            worker_digest=worker_digest,
        )
        attempt_dir = root / "attempts" / attempt.attempt_id
        raw_score = json.loads(
            (attempt_dir / "completed-score.json").read_text(encoding="utf-8")
        )
        scores.append(
            OfficialTaskScore(
                **{
                    **raw_score,
                    "diagnostic_tags": tuple(raw_score.get("diagnostic_tags", ())),
                }
            )
        )
        attempt_rows.append(
            {
                "task_id": task_id,
                "attempt_id": attempt.attempt_id,
                "answer_free_evidence": json.loads(
                    _answer_free_sidecar(attempt_dir).read_text(encoding="utf-8")
                ),
            }
        )
    score_summary = aggregate_domain_macro(scores)
    cost = audit_fixed_checkpoint_proxy_costs(
        root,
        expected_attempts=len(plan["task_ids"]),
        checkpoint=checkpoint,
        split=SPLIT,
    )
    route = _route_evidence(root, Path(token_file).resolve())
    evaluation_identity = _canonical_sha256(
        {
            "checkpoint": checkpoint,
            "worker_digest": worker_digest,
            "panel_identity_sha256": plan["panel_identity_sha256"],
            "sampling_identity_sha256": plan["sampling_identity_sha256"],
            "attempts": attempt_rows,
        }
    )
    result = {
        **plan,
        "status": "complete",
        "model_request_count": cost["request_count"],
        "attempts": attempt_rows,
        "score_summary": {
            "task_rewards": score_summary.task_rewards,
            "domain_scores": score_summary.domain_scores,
            "task_mean": score_summary.task_mean,
            "overall": score_summary.overall,
            "scores": [asdict(score) for score in score_summary.scores],
        },
        "cost_audit": cost,
        "route_evidence": route,
        "evaluation_identity_sha256": evaluation_identity,
        "worker_behavior_zero_tasks": sorted(
            str(task_id)
            for task_id in plan["task_ids"]
            if (
                root
                / "attempts"
                / TaskAttempt.create(
                    run_id=str(plan["run_id"]),
                    benchmark_commit=str(benchmark_commit),
                    task_id=str(task_id),
                    split=SPLIT,
                    checkpoint=checkpoint,
                    worker_digest=worker_digest,
                ).attempt_id
                / "answer-free-worker-zero.json"
            ).is_file()
        ),
        "recovery_source_sha256": {
            "execution_record.py": hashlib.sha256(
                (Path(__file__).resolve().parent / "executors" / "execution_record.py").read_bytes()
            ).hexdigest(),
            "loop_benchmark.py": hashlib.sha256(
                (Path(__file__).resolve().parent / "loop_benchmark.py").read_bytes()
            ).hexdigest(),
            "quantcodeeval_candidate.py": hashlib.sha256(
                Path(__file__).read_bytes()
            ).hexdigest(),
        },
    }
    _atomic_private_json(root / "CANDIDATE-RESULT.json", result)
    return result
