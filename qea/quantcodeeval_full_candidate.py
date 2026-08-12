"""Admit and evaluate one Evolver-produced full-harness QuantCodeEval candidate.

Unlike the v1 candidate runner, this module never materializes a mutation and
never assumes ``systemprompt.md`` is the only changed file.  It accepts an
already-produced candidate tree, independently re-measures the exact mutation,
requires declared roles to match, and optionally gates official evaluation on
an answer-free activation probe.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, Mapping

from .candidate_admission import AdmissionPolicy, admit_candidate
from .evaluation import TaskAttempt
from .loop_benchmark import hash_worker_directory
from .mutation_metrics import measure_mutation
from .qfbench_baseline import audit_fixed_checkpoint_proxy_costs
from .quantcodeeval_baseline import (
    MODEL,
    SPLIT,
    _atomic_private_json,
    _route_evidence,
    prepare_quantcodeeval_h0,
)
from .quantcodeeval_candidate import _answer_free_sidecar


class QuantCodeEvalFullCandidateError(ValueError):
    """A full-harness candidate or its pre-evaluation evidence is invalid."""


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _source_sha256() -> dict[str, str]:
    package = Path(__file__).resolve().parent
    names = (
        "candidate_admission.py",
        "mutation_metrics.py",
        "quantcodeeval_full_candidate.py",
    )
    return {
        name: hashlib.sha256((package / name).read_bytes()).hexdigest()
        for name in names
    }


def _normalized_json(value: object, *, label: str) -> object:
    try:
        return json.loads(json.dumps(value, sort_keys=True))
    except (TypeError, ValueError) as exc:
        raise QuantCodeEvalFullCandidateError(f"{label} must be JSON-safe") from exc


def _validate_component_tests(
    values: Iterable[Mapping[str, object]],
    *,
    candidate_digest: str,
    primary_components: Iterable[str],
) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    latest: dict[str, dict[str, object]] = {}
    for index, value in enumerate(values):
        item = _normalized_json(dict(value), label=f"component_tests[{index}]")
        assert isinstance(item, dict)
        if item.get("status") not in {"passed", "failed"}:
            raise QuantCodeEvalFullCandidateError(
                "component test status must be passed or failed"
            )
        bound = item.get("candidate_digest")
        if bound is not None and (
            not isinstance(bound, str) or re.fullmatch(r"[0-9a-f]{64}", bound) is None
        ):
            raise QuantCodeEvalFullCandidateError(
                "component test candidate digest is invalid"
            )
        component = item.get("component")
        if isinstance(component, str):
            latest[component] = item
        normalized.append(item)
    if not normalized:
        raise QuantCodeEvalFullCandidateError(
            "full-harness candidate requires at least one component test"
        )
    missing = sorted(
        component
        for component in primary_components
        if latest.get(component, {}).get("status") != "passed"
        or latest.get(component, {}).get("candidate_digest") != candidate_digest
    )
    if missing:
        raise QuantCodeEvalFullCandidateError(
            "primary components lack a final digest-bound passed smoke: "
            + ", ".join(missing)
        )
    return normalized


def run_quantcodeeval_full_candidate(
    *,
    config_path: str | Path,
    public_root: str | Path,
    trusted_root: str | Path,
    run_dir: str | Path,
    seed_worker_dir: str | Path,
    parent_worker_dir: str | Path,
    candidate_worker_dir: str | Path,
    iteration: int,
    mechanism: str,
    primary_components: Iterable[str],
    declared_roles: Iterable[str],
    component_tests: Iterable[Mapping[str, object]],
    activation: Mapping[str, object] | None,
    worker_image_ref: str,
    verifier_image_ref: str,
    proxy_image_ref: str,
    token_file: str | Path,
    source_h0_evaluation_id: str,
    require_activation: bool = True,
    preflight_only: bool = False,
) -> dict[str, object]:
    """Admit and optionally evaluate one autonomous full-harness candidate."""

    if type(iteration) is not int or iteration < 1:
        raise QuantCodeEvalFullCandidateError("iteration must be positive")
    if not isinstance(mechanism, str) or not mechanism.strip():
        raise QuantCodeEvalFullCandidateError("mechanism must be non-empty")
    root = Path(run_dir).resolve()
    parent = Path(parent_worker_dir).resolve()
    candidate = Path(candidate_worker_dir).resolve()
    declared = tuple(sorted({str(value) for value in declared_roles}))
    primary = tuple(sorted({str(value) for value in primary_components}))
    if not primary or not declared or not set(primary) <= set(declared):
        raise QuantCodeEvalFullCandidateError(
            "primary components must be a subset of declared roles"
        )
    candidate_digest = hash_worker_directory(candidate)
    parent_digest = hash_worker_directory(parent)
    tests = _validate_component_tests(
        component_tests,
        candidate_digest=candidate_digest,
        primary_components=primary,
    )
    activation_payload = _normalized_json(
        dict(activation or {"status": "not_run"}), label="activation"
    )
    assert isinstance(activation_payload, dict)
    if activation_payload.get("status") not in {"not_run", "passed", "failed"}:
        raise QuantCodeEvalFullCandidateError("activation status is unsupported")

    snapshot, evaluator, baseline_preflight, frozen_seed = prepare_quantcodeeval_h0(
        config_path=config_path,
        public_root=public_root,
        trusted_root=trusted_root,
        run_dir=root,
        worker_dir=seed_worker_dir,
        worker_image_ref=worker_image_ref,
        verifier_image_ref=verifier_image_ref,
        proxy_image_ref=proxy_image_ref,
    )
    admission = admit_candidate(
        frozen_seed,
        candidate,
        AdmissionPolicy.qfbench_full(),
    )
    metrics = measure_mutation(
        before_root=parent,
        after_root=candidate,
        declared_roles=declared,
    )
    if (
        not admission.admitted
        or metrics["changed_file_count"] == 0
        or metrics["declared_roles_match_actual"] is not True
    ):
        raise QuantCodeEvalFullCandidateError(
            "candidate admission or declared full-harness identity differs"
        )
    checkpoint = f"quantcodeeval-v2-iteration-{iteration:04d}"
    panel_identity = {
        "benchmark_commit": snapshot.commit,
        "public_manifest_sha256": baseline_preflight["public_manifest_sha256"],
        "trusted_manifest_sha256": baseline_preflight["trusted_manifest_sha256"],
        "task_ids": list(snapshot.optimize.task_ids),
    }
    sampling_identity = {
        "model": MODEL,
        "required_provider": "deepseek",
        "allow_fallbacks": False,
        "split": SPLIT,
        "runtime_identity_sha256": baseline_preflight["runtime_identity_sha256"],
        "worker_image_ref": worker_image_ref,
        "verifier_image_ref": verifier_image_ref,
        "proxy_image_ref": proxy_image_ref,
        "worker_concurrency": 1,
        "verifier_concurrency": 1,
    }
    plan = _normalized_json(
        {
            "schema_version": 2,
            "protocol": "quant_property_v2_full_candidate",
            "status": "preflight_complete",
            "run_id": root.name,
            "iteration": iteration,
            "mechanism": mechanism.strip(),
            "primary_components": list(primary),
            "declared_roles": list(declared),
            "source_h0_evaluation_id": source_h0_evaluation_id,
            "h0_resampled": False,
            "model": MODEL,
            "runtime_identity_sha256": baseline_preflight["runtime_identity_sha256"],
            "candidate_coordinator_source_sha256": _source_sha256(),
            "panel_identity_sha256": _canonical_sha256(panel_identity),
            "sampling_identity_sha256": _canonical_sha256(sampling_identity),
            "parent_worker_digest": parent_digest,
            "candidate_worker_digest": candidate_digest,
            "candidate_admission_manifest_digest": admission.candidate_digest,
            "admission": asdict(admission),
            "mutation_metrics": metrics,
            "component_tests": tests,
            "activation": activation_payload,
            "checkpoint": checkpoint,
            "task_ids": list(snapshot.optimize.task_ids),
            "model_request_count": 0,
        },
        label="candidate preflight",
    )
    assert isinstance(plan, dict)
    preflight_path = root / "FULL-CANDIDATE-PREFLIGHT.json"
    if preflight_path.is_file():
        if json.loads(preflight_path.read_text(encoding="utf-8")) != plan:
            raise QuantCodeEvalFullCandidateError(
                "persisted full-candidate preflight differs"
            )
    else:
        _atomic_private_json(preflight_path, plan)
    if preflight_only:
        return plan
    if require_activation and activation_payload.get("status") != "passed":
        result = {
            **plan,
            "status": "activation_failed",
            "official_evaluated": False,
            "activation_failure": activation_payload,
        }
        _atomic_private_json(root / "FULL-CANDIDATE-RESULT.json", result)
        return result

    summary = evaluator.evaluate(
        worker_dir=candidate,
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
    attempt_rows: list[dict[str, object]] = []
    for task in snapshot.optimize.tasks:
        attempt = TaskAttempt.create(
            run_id=root.name,
            benchmark_commit=snapshot.commit,
            task_id=task.task_id,
            split=SPLIT,
            checkpoint=checkpoint,
            worker_digest=candidate_digest,
        )
        sidecar = _answer_free_sidecar(root / "attempts" / attempt.attempt_id)
        attempt_rows.append(
            {
                "task_id": task.task_id,
                "attempt_id": attempt.attempt_id,
                "answer_free_evidence": json.loads(sidecar.read_text(encoding="utf-8")),
            }
        )
    evaluation_identity = _canonical_sha256(
        {
            "checkpoint": checkpoint,
            "worker_digest": candidate_digest,
            "panel_identity_sha256": plan["panel_identity_sha256"],
            "sampling_identity_sha256": plan["sampling_identity_sha256"],
            "attempts": attempt_rows,
        }
    )
    result = {
        **plan,
        "status": "complete",
        "official_evaluated": True,
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
    result_path = root / "FULL-CANDIDATE-RESULT.json"
    if result_path.is_file():
        if json.loads(result_path.read_text(encoding="utf-8")) != result:
            raise QuantCodeEvalFullCandidateError(
                "persisted full-candidate result differs"
            )
    else:
        _atomic_private_json(result_path, result)
    return result


__all__ = ["QuantCodeEvalFullCandidateError", "run_quantcodeeval_full_candidate"]
