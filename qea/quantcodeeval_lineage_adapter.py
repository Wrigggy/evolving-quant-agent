"""Normalize retained QuantCodeEval results for candidate lineages.

The adapter is intentionally independent of the QFBench lineage controller.
It preserves the existing QuantCodeEval score semantics, including the
difference between an official worker-artifact zero and an incomplete
infrastructure run.  It does not infer missing run or cost accounting.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from .benchmarks.quantcodeeval import public_track_task_ids
from .evaluation import EvaluationContractError, OfficialTaskScore


_STAGES = frozenset({"target", "repeat", "protection"})


class QuantCodeEvalLineageAdapterError(ValueError):
    """A QuantCodeEval result cannot be normalized without changing meaning."""


def _load_result(source: str | Path | Mapping[str, object]) -> dict[str, object]:
    if isinstance(source, Mapping):
        return dict(source)
    try:
        payload = json.loads(Path(source).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise QuantCodeEvalLineageAdapterError(
            f"cannot read QuantCodeEval result: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise QuantCodeEvalLineageAdapterError(
            "QuantCodeEval result must be a JSON object"
        )
    return payload


def _run_id(payload: Mapping[str, object], override: str | None) -> str | None:
    recorded = payload.get("run_id")
    if recorded is not None and (not isinstance(recorded, str) or not recorded):
        raise QuantCodeEvalLineageAdapterError("QuantCodeEval run_id is invalid")
    if override is not None and not override.strip():
        raise QuantCodeEvalLineageAdapterError("run_id override must be non-empty")
    if isinstance(recorded, str) and override is not None and recorded != override:
        raise QuantCodeEvalLineageAdapterError(
            "run_id override disagrees with the QuantCodeEval result"
        )
    return recorded if isinstance(recorded, str) else override


def _cost_source(
    payload: Mapping[str, object],
    override: Mapping[str, object] | None,
) -> Mapping[str, object] | None:
    if override is not None:
        return override
    for key in ("cost_audit", "partial_cost_and_lifecycle_audit"):
        value = payload.get(key)
        if isinstance(value, Mapping):
            return value
    return None


def _cost(
    payload: Mapping[str, object],
    override: Mapping[str, object] | None,
) -> dict[str, object] | None:
    source = _cost_source(payload, override)
    if source is None:
        return None
    provider_cost = source.get("provider_cost_usd")
    completed = source.get("completed_request_count")
    total_tokens = source.get("total_tokens")
    if isinstance(provider_cost, bool) or (
        provider_cost is not None and not isinstance(provider_cost, (int, float, str))
    ):
        raise QuantCodeEvalLineageAdapterError("provider cost is invalid")
    if isinstance(completed, bool) or (
        completed is not None and not isinstance(completed, int)
    ):
        raise QuantCodeEvalLineageAdapterError(
            "completed request count is invalid"
        )
    if isinstance(total_tokens, bool) or (
        total_tokens is not None and not isinstance(total_tokens, int)
    ):
        raise QuantCodeEvalLineageAdapterError("total token count is invalid")
    return {
        "provider_cost_usd": (
            str(provider_cost) if provider_cost is not None else None
        ),
        "completed_request_count": completed,
        "total_tokens": total_tokens,
        "cost_complete": source.get("cost_complete"),
        "provider_cost_is_lower_bound": source.get(
            "provider_cost_is_lower_bound"
        ),
    }


def _score_row(
    payload: Mapping[str, object], task_id: str
) -> Mapping[str, object] | None:
    summary = payload.get("score_summary")
    if not isinstance(summary, Mapping):
        return None
    rows = summary.get("scores")
    if not isinstance(rows, list):
        raise QuantCodeEvalLineageAdapterError(
            "QuantCodeEval score_summary has no scores list"
        )
    matches = [
        row
        for row in rows
        if isinstance(row, Mapping) and row.get("task_id") == task_id
    ]
    if len(matches) != 1:
        raise QuantCodeEvalLineageAdapterError(
            f"QuantCodeEval result has no unique score for {task_id}"
        )
    return matches[0]


def _official_score(row: Mapping[str, object]) -> OfficialTaskScore:
    try:
        return OfficialTaskScore(
            task_id=row.get("task_id"),
            domain=row.get("domain"),
            reward=row.get("reward"),
            diagnostic_tags=tuple(row.get("diagnostic_tags", ())),
            verifier_exit_code=row.get("verifier_exit_code"),
            tests_passed=row.get("tests_passed"),
            tests_failed=row.get("tests_failed"),
            log_uri=row.get("log_uri"),
        )
    except (AttributeError, EvaluationContractError, TypeError) as exc:
        raise QuantCodeEvalLineageAdapterError(
            f"invalid persisted QuantCodeEval score: {exc}"
        ) from exc


def _cost_is_lineage_ready(cost: Mapping[str, object] | None) -> bool:
    return bool(
        cost is not None
        and cost.get("provider_cost_usd") is not None
        and isinstance(cost.get("completed_request_count"), int)
        and isinstance(cost.get("total_tokens"), int)
    )


def _property_total(value: int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise QuantCodeEvalLineageAdapterError(
            "official_property_total must be a positive integer"
        )
    return value


def _selection_metric(
    *,
    status: str,
    score: OfficialTaskScore,
    official_property_total: int | None,
) -> dict[str, object] | None:
    total = _property_total(official_property_total)
    if status == "official_complete":
        assert isinstance(score.tests_passed, int)
        assert isinstance(score.tests_failed, int)
        observed_total = score.tests_passed + score.tests_failed
        if total is not None and total != observed_total:
            raise QuantCodeEvalLineageAdapterError(
                "official_property_total disagrees with the verifier counts"
            )
        return {
            "official_valid": True,
            "reward": float(score.reward),
            "selection_passed": score.tests_passed,
            "selection_failed": score.tests_failed,
            "official_property_total": observed_total,
            "verifier_executed": True,
            "verifier_exit_code": score.verifier_exit_code,
            "source": "official_verifier",
        }
    if status == "official_zero_missing_strategy" and total is not None:
        return {
            "official_valid": True,
            "reward": 0.0,
            "selection_passed": 0,
            "selection_failed": total,
            "official_property_total": total,
            "verifier_executed": False,
            "verifier_exit_code": None,
            "source": "official_worker_artifact_contract_zero",
        }
    return None


def normalize_quantcodeeval_lineage_observation(
    source: str | Path | Mapping[str, object],
    *,
    task_id: str,
    stage: str,
    run_id: str | None = None,
    cost: Mapping[str, object] | None = None,
    official_property_total: int | None = None,
) -> dict[str, object]:
    """Return one answer-free QuantCodeEval lineage observation.

    ``run_id`` and ``cost`` are explicit wrappers for older result files that
    do not persist those fields.  Missing values remain ``None`` and make the
    observation non-ready rather than being replaced with invented zeroes.
    """

    if stage not in _STAGES:
        raise QuantCodeEvalLineageAdapterError(
            f"unsupported QuantCodeEval lineage stage: {stage}"
        )
    if not isinstance(task_id, str) or not task_id:
        raise QuantCodeEvalLineageAdapterError("task_id must be non-empty")
    if task_id not in public_track_task_ids():
        raise QuantCodeEvalLineageAdapterError(
            f"{task_id} is not in the credential-free QuantCodeEval track"
        )
    payload = _load_result(source)
    resolved_run_id = _run_id(payload, run_id)
    normalized_cost = _cost(payload, cost)

    result_complete = payload.get("status") == "complete"
    officially_evaluated = payload.get("official_evaluated")
    if not result_complete or officially_evaluated is False:
        return {
            "schema_version": 1,
            "benchmark": "quantcodeeval",
            "stage": stage,
            "status": "infra_incomplete",
            "task_id": task_id,
            "reward": None,
            "tests_passed": None,
            "tests_failed": None,
            "verifier_exit_code": None,
            "diagnostic_tags": ["worker_error"],
            "run_id": resolved_run_id,
            "cost": normalized_cost,
            "selection_metric": None,
            "lineage_ready": False,
        }

    row = _score_row(payload, task_id)
    if row is None:
        raise QuantCodeEvalLineageAdapterError(
            "complete QuantCodeEval result has no score_summary"
        )
    score = _official_score(row)
    tags = list(score.diagnostic_tags)
    missing_strategy_zero = (
        score.reward == 0.0 and "missing_artifact" in score.diagnostic_tags
    )
    verifier_complete = (
        score.verifier_exit_code == 0
        and isinstance(score.tests_passed, int)
        and isinstance(score.tests_failed, int)
    )
    if missing_strategy_zero:
        status = "official_zero_missing_strategy"
    elif verifier_complete and "verifier_error" not in score.diagnostic_tags:
        status = "official_complete"
    else:
        status = "infra_incomplete"

    selection_metric = _selection_metric(
        status=status,
        score=score,
        official_property_total=official_property_total,
    )
    lineage_ready = bool(
        status in {"official_complete", "official_zero_missing_strategy"}
        and selection_metric is not None
        and isinstance(resolved_run_id, str)
        and _cost_is_lineage_ready(normalized_cost)
    )
    return {
        "schema_version": 1,
        "benchmark": "quantcodeeval",
        "stage": stage,
        "status": status,
        "task_id": score.task_id,
        "reward": float(score.reward),
        "tests_passed": score.tests_passed,
        "tests_failed": score.tests_failed,
        "verifier_exit_code": score.verifier_exit_code,
        "diagnostic_tags": tags,
        "run_id": resolved_run_id,
        "cost": normalized_cost,
        "selection_metric": selection_metric,
        "lineage_ready": lineage_ready,
    }


def quantcodeeval_lineage_metric(
    observation: Mapping[str, object],
    *,
    official_property_total: int | None = None,
) -> dict[str, object]:
    """Return a selection metric without rewriting raw official fields."""

    status = observation.get("status")
    if status == "infra_incomplete":
        raise QuantCodeEvalLineageAdapterError(
            "incomplete infrastructure run has no official selection metric"
        )
    existing = observation.get("selection_metric")
    if isinstance(existing, Mapping):
        metric = dict(existing)
        total = _property_total(official_property_total)
        if total is not None and total != metric.get("official_property_total"):
            raise QuantCodeEvalLineageAdapterError(
                "official_property_total disagrees with the retained selection metric"
            )
        return metric
    if status != "official_zero_missing_strategy":
        raise QuantCodeEvalLineageAdapterError(
            "QuantCodeEval observation has no official selection metric"
        )
    total = _property_total(official_property_total)
    if total is None:
        raise QuantCodeEvalLineageAdapterError(
            "missing-strategy zero needs explicit official_property_total"
        )
    return {
        "official_valid": True,
        "reward": 0.0,
        "selection_passed": 0,
        "selection_failed": total,
        "official_property_total": total,
        "verifier_executed": False,
        "verifier_exit_code": None,
        "source": "official_worker_artifact_contract_zero",
    }


def quantcodeeval_lineage_score(
    observation: Mapping[str, object],
    *,
    official_property_total: int | None = None,
) -> dict[str, object]:
    """Project an official observation to a controller selection score.

    Missing-strategy zeroes retain ``verifier_exit_code=None`` and carry a
    source marker because no verifier process executed.
    """

    metric = quantcodeeval_lineage_metric(
        observation,
        official_property_total=official_property_total,
    )
    if (
        not isinstance(observation.get("run_id"), str)
        or not _cost_is_lineage_ready(observation.get("cost"))
    ):
        raise QuantCodeEvalLineageAdapterError(
            "QuantCodeEval observation lacks explicit run or cost accounting"
        )
    return {
        "task_id": observation["task_id"],
        "reward": metric["reward"],
        "tests_passed": metric["selection_passed"],
        "tests_failed": metric["selection_failed"],
        "verifier_exit_code": metric["verifier_exit_code"],
        "selection_source": metric["source"],
        "official_valid": metric["official_valid"],
        "verifier_executed": metric["verifier_executed"],
    }


__all__ = [
    "QuantCodeEvalLineageAdapterError",
    "normalize_quantcodeeval_lineage_observation",
    "quantcodeeval_lineage_metric",
    "quantcodeeval_lineage_score",
]
