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
    prepare_quantcodeeval_h0,
)


def _answer_free_attempt_evidence(attempt_dir: Path) -> dict[str, object]:
    """Load the normal summary or derive a compact missing-artifact summary."""

    for path in (
        attempt_dir / "verifier" / "answer-free-evidence.json",
        attempt_dir / "answer-free-worker-zero.json",
    ):
        value = _read_json_mapping(path)
        if value is not None:
            return value
    completed = _read_json_mapping(attempt_dir / "completed-score.json")
    if completed is None:
        raise QuantCodeEvalFullCandidateError(
            "completed attempt has no answer-free score evidence"
        )
    return {
        "benchmark": "quantcodeeval",
        "official_reward": completed.get("reward"),
        "diagnostic_tags": list(completed.get("diagnostic_tags") or []),
        "tests_passed": completed.get("tests_passed"),
        "tests_failed": completed.get("tests_failed"),
    }


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


def _read_json_mapping(path: Path) -> dict[str, object] | None:
    if path.is_symlink() or not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return dict(value) if isinstance(value, Mapping) else None


def _proxy_attempt_audit(path: Path) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    if path.is_file() and not path.is_symlink():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                return {
                    "audit_present": True,
                    "audit_complete": False,
                    "reason": "proxy audit contains malformed JSON",
                }
            if not isinstance(value, Mapping):
                return {
                    "audit_present": True,
                    "audit_complete": False,
                    "reason": "proxy audit contains a non-object row",
                }
            rows.append(dict(value))
    completed = [
        row
        for row in rows
        if row.get("request_state") == "completed"
        and row.get("failure_class") is None
        and row.get("upstream_status_code") == 200
    ]
    costs = [row.get("provider_cost_usd") for row in completed]
    numeric_costs = [
        float(value)
        for value in costs
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    ]
    return {
        "audit_present": path.is_file() and not path.is_symlink(),
        "audit_complete": bool(rows) and len(rows) == len(completed),
        "request_count": len(rows),
        "completed_request_count": len(completed),
        "input_tokens": sum(int(row.get("input_tokens") or 0) for row in completed),
        "output_tokens": sum(int(row.get("output_tokens") or 0) for row in completed),
        "total_tokens": sum(int(row.get("total_tokens") or 0) for row in completed),
        "provider_cost_usd": (
            sum(numeric_costs) if len(numeric_costs) == len(completed) else None
        ),
    }


def _answer_free_failed_attempts(
    root: Path, tasks: Iterable[object]
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Collect worker-contract failure facts without reading checker output."""

    lifecycle_by_task: dict[str, list[dict[str, object]]] = {}
    lifecycle_rows: list[dict[str, object]] = []
    for path in sorted(root.glob("lifecycles/**/*.json")):
        value = _read_json_mapping(path)
        if value is None:
            continue
        task_id = value.get("task_id")
        if isinstance(task_id, str):
            lifecycle_by_task.setdefault(task_id, []).append(value)
        lifecycle_rows.append(value)

    attempts: list[dict[str, object]] = []
    total_requests = 0
    total_input = 0
    total_output = 0
    total_tokens = 0
    total_cost = 0.0
    cost_complete = True
    for task in tasks:
        task_id = str(task if isinstance(task, str) else getattr(task, "task_id"))
        # Attempt identity also binds checkpoint and worker digest, so locate
        # the directory through its public attempt metadata rather than guessing.
        attempt_dir = None
        for metadata_path in sorted((root / "attempts").glob("*/attempt.json")):
            metadata = _read_json_mapping(metadata_path)
            if metadata is not None and metadata.get("task_id") == task_id:
                attempt_dir = metadata_path.parent
                break
        if attempt_dir is None:
            attempts.append(
                {
                    "task_id": task_id,
                    "attempt_id": None,
                    "failure_stage": "attempt_materialization",
                    "failure_class": "missing_attempt_record",
                    "official_score_available": False,
                }
            )
            continue
        metadata = _read_json_mapping(attempt_dir / "attempt.json") or {}
        contract = _read_json_mapping(
            attempt_dir / "worker-artifact-contract.json"
        )
        extracted = sorted(
            path.relative_to(attempt_dir / "artifacts").as_posix()
            for path in (attempt_dir / "artifacts").rglob("*")
            if path.is_file() and not path.is_symlink()
        ) if (attempt_dir / "artifacts").is_dir() else []
        lifecycles = lifecycle_by_task.get(task_id, [])
        failures = sorted(
            {
                str(value["failure"])
                for value in lifecycles
                if isinstance(value.get("failure"), str) and value["failure"]
            }
        )
        proxy = _proxy_attempt_audit(attempt_dir / "proxy-audit.jsonl")
        total_requests += int(proxy.get("request_count") or 0)
        total_input += int(proxy.get("input_tokens") or 0)
        total_output += int(proxy.get("output_tokens") or 0)
        total_tokens += int(proxy.get("total_tokens") or 0)
        cost = proxy.get("provider_cost_usd")
        if isinstance(cost, (int, float)) and not isinstance(cost, bool):
            total_cost += float(cost)
        else:
            cost_complete = False
        if contract is not None and contract.get("found_paths") == []:
            failure_class = "missing_submission_artifact"
        elif any("file limit exceeded" in value for value in failures):
            failure_class = "output_membership_overflow"
        else:
            failure_class = "worker_artifact_contract"
        attempts.append(
            {
                "task_id": task_id,
                "attempt_id": metadata.get("attempt_id"),
                "failure_stage": "worker_artifact_contract",
                "failure_class": failure_class,
                "failure_messages": failures,
                "required_submission_paths": (
                    list(contract.get("expected_paths", []))
                    if contract is not None
                    and isinstance(contract.get("expected_paths"), list)
                    else ["strategy.py"]
                ),
                "reported_submission_paths": (
                    list(contract.get("found_paths", []))
                    if contract is not None
                    and isinstance(contract.get("found_paths"), list)
                    else None
                ),
                "partially_extracted_paths": extracted,
                "official_score_available": False,
                "provider_audit": proxy,
            }
        )
    cleaned_rows = [
        value.get("cleaned_up")
        for value in lifecycle_rows
        if "cleaned_up" in value
    ]
    aggregate = {
        "request_count": total_requests,
        "input_tokens": total_input,
        "output_tokens": total_output,
        "total_tokens": total_tokens,
        "provider_cost_usd": total_cost if cost_complete else None,
        "cost_complete": cost_complete,
        "lifecycle_record_count": len(lifecycle_rows),
        "all_recorded_resources_cleaned": bool(cleaned_rows) and all(
            value is True for value in cleaned_rows
        ),
    }
    return attempts, aggregate


def materialize_quantcodeeval_full_candidate_failure_result(
    run_dir: str | Path,
) -> dict[str, object]:
    """Recover a structured failure result for a legacy interrupted panel.

    This reads only preflight, worker artifact-contract, proxy audit, and
    lifecycle records.  It deliberately does not inspect checker output.
    """

    root = Path(run_dir).expanduser().resolve()
    preflight_path = root / "FULL-CANDIDATE-PREFLIGHT.json"
    preflight = _read_json_mapping(preflight_path)
    if preflight is None or preflight.get("status") != "preflight_complete":
        raise QuantCodeEvalFullCandidateError(
            "legacy failure recovery requires a complete candidate preflight"
        )
    result_path = root / "FULL-CANDIDATE-RESULT.json"
    if result_path.exists() or result_path.is_symlink():
        result = _read_json_mapping(result_path)
        if result is None:
            raise QuantCodeEvalFullCandidateError(
                "persisted full-candidate result is invalid"
            )
        return result
    task_ids = preflight.get("task_ids")
    if not isinstance(task_ids, list) or any(
        not isinstance(value, str) for value in task_ids
    ):
        raise QuantCodeEvalFullCandidateError("candidate preflight task IDs are invalid")
    attempts, partial_audit = _answer_free_failed_attempts(root, task_ids)
    if not attempts or all(
        value.get("failure_class") == "missing_attempt_record" for value in attempts
    ):
        raise QuantCodeEvalFullCandidateError(
            "legacy run has no worker failure artifacts to recover"
        )
    result = {
        **preflight,
        "status": "evaluation_failed",
        "official_evaluated": False,
        "benchmark_score_claimed": False,
        "evaluation_attempted": True,
        "failure": {
            "exception_type": "RecoveredInterruptedPanel",
            "message": (
                "recovered from immutable worker artifact-contract and lifecycle "
                "records; the original coordinator exited before result persistence"
            ),
        },
        "attempts": attempts,
        "partial_cost_and_lifecycle_audit": partial_audit,
        "preflight_sha256": _canonical_sha256(preflight),
        "recovered_from_existing_artifacts": True,
    }
    _atomic_private_json(result_path, result)
    return result


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
    token_file: str | Path | None = None,
    source_h0_evaluation_id: str,
    task_ids: Iterable[str] | None = None,
    task_panel_path: str | Path | None = None,
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
        task_panel_path=task_panel_path,
    )
    available_tasks = {task.task_id: task for task in snapshot.optimize.tasks}
    requested_task_ids = tuple(task_ids or available_tasks)
    if (
        not requested_task_ids
        or len(set(requested_task_ids)) != len(requested_task_ids)
        or any(task_id not in available_tasks for task_id in requested_task_ids)
    ):
        raise QuantCodeEvalFullCandidateError(
            "requested tasks must be a unique non-empty subset of the optimize panel"
        )
    selected_tasks = tuple(available_tasks[task_id] for task_id in requested_task_ids)
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
        "task_ids": list(requested_task_ids),
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
            "task_ids": list(requested_task_ids),
            "model_request_count": 0,
        },
        label="candidate preflight",
    )
    assert isinstance(plan, dict)
    preflight_path = root / "FULL-CANDIDATE-PREFLIGHT.json"
    if preflight_path.is_file():
        persisted_plan = _read_json_mapping(preflight_path)
        if persisted_plan is None:
            raise QuantCodeEvalFullCandidateError(
                "persisted full-candidate preflight is invalid"
            )
        # Resume is governed by the experimental setup, not by unrelated
        # coordinator implementation details.  This allows a result-writing
        # bug to be fixed after the paid task attempts have completed.
        resume_keys = (
            "protocol",
            "run_id",
            "iteration",
            "mechanism",
            "primary_components",
            "declared_roles",
            "source_h0_evaluation_id",
            "candidate_worker_digest",
            "checkpoint",
            "task_ids",
            "model",
        )
        if any(persisted_plan.get(key) != plan.get(key) for key in resume_keys):
            raise QuantCodeEvalFullCandidateError(
                "persisted full-candidate experimental setup differs"
            )
        plan = persisted_plan
    else:
        _atomic_private_json(preflight_path, plan)
    if preflight_only:
        return plan
    result_path = root / "FULL-CANDIDATE-RESULT.json"
    if result_path.exists() or result_path.is_symlink():
        if result_path.is_symlink() or not result_path.is_file():
            raise QuantCodeEvalFullCandidateError(
                "persisted full-candidate result is unsafe"
            )
        persisted = _read_json_mapping(result_path)
        if persisted is None:
            raise QuantCodeEvalFullCandidateError(
                "persisted full-candidate result is invalid"
            )
        if persisted.get("status") not in {
            "activation_failed",
            "evaluation_failed",
            "complete",
        }:
            raise QuantCodeEvalFullCandidateError(
                "persisted full-candidate result status is invalid"
            )
        bound_keys = (
            "plan_identity_sha256",
            "candidate_worker_digest",
            "source_h0_evaluation_id",
            "checkpoint",
        )
        # Older plans predate an explicit plan identity.  Every other bound
        # field remains exact, and new results carry the preflight SHA below.
        for key in bound_keys:
            if key in persisted and persisted.get(key) != plan.get(key):
                raise QuantCodeEvalFullCandidateError(
                    "persisted full-candidate result differs from preflight"
                )
        persisted_preflight = persisted.get("preflight_sha256")
        if (
            persisted_preflight is not None
            and persisted_preflight != _canonical_sha256(plan)
        ):
            raise QuantCodeEvalFullCandidateError(
                "persisted full-candidate result preflight differs"
            )
        return persisted
    if require_activation and activation_payload.get("status") != "passed":
        result = {
            **plan,
            "status": "activation_failed",
            "official_evaluated": False,
            "activation_failure": activation_payload,
        }
        _atomic_private_json(result_path, result)
        return result

    try:
        summary = evaluator.evaluate(
            worker_dir=candidate,
            tasks=selected_tasks,
            split=SPLIT,
            checkpoint=checkpoint,
            run_dir=root,
        )
    except Exception as exc:
        failed_attempts, partial_audit = _answer_free_failed_attempts(
            root, selected_tasks
        )
        result = {
            **plan,
            "status": "evaluation_failed",
            "official_evaluated": False,
            "benchmark_score_claimed": False,
            "evaluation_attempted": True,
            "failure": {
                "exception_type": type(exc).__name__,
                "message": str(exc)[:2_000],
            },
            "attempts": failed_attempts,
            "partial_cost_and_lifecycle_audit": partial_audit,
            "preflight_sha256": _canonical_sha256(plan),
        }
        _atomic_private_json(result_path, result)
        return result
    cost = audit_fixed_checkpoint_proxy_costs(
        root,
        expected_attempts=len(selected_tasks),
        checkpoint=checkpoint,
        split=SPLIT,
    )
    # The completed proxy audit already records the actual provider, model,
    # requests, tokens, and cost.  A second provider-metadata lookup made a
    # completed panel fail when the provider later returned 404, so the token
    # path is retained only for CLI compatibility and is intentionally unused.
    route = {
        "model": MODEL,
        "provider": "deepseek",
        "allow_fallbacks": False,
        "basis": "completed proxy audit",
    }
    attempt_rows: list[dict[str, object]] = []
    for task in selected_tasks:
        attempt = TaskAttempt.create(
            run_id=root.name,
            benchmark_commit=snapshot.commit,
            task_id=task.task_id,
            split=SPLIT,
            checkpoint=checkpoint,
            worker_digest=candidate_digest,
        )
        attempt_rows.append(
            {
                "task_id": task.task_id,
                "attempt_id": attempt.attempt_id,
                "answer_free_evidence": _answer_free_attempt_evidence(
                    root / "attempts" / attempt.attempt_id
                ),
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
    if result_path.is_file():
        if json.loads(result_path.read_text(encoding="utf-8")) != result:
            raise QuantCodeEvalFullCandidateError(
                "persisted full-candidate result differs"
            )
    else:
        _atomic_private_json(result_path, result)
    return result


__all__ = [
    "QuantCodeEvalFullCandidateError",
    "materialize_quantcodeeval_full_candidate_failure_result",
    "run_quantcodeeval_full_candidate",
]
