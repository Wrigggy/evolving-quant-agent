"""Small candidate-lineage state machine for QFBench Main-0."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Mapping


class LineageError(ValueError):
    """Raised when a lineage or child report cannot be interpreted."""


_STAGE_PHASE = {
    "target": "TARGET",
    "repeat": "REPEAT",
    "protection": "PROTECTION",
}


def new_lineage(
    *,
    lineage_id: str,
    parent_version: str,
    parent_path: str,
    candidate_version: str,
    candidate_path: str,
    target_task_id: str,
    protection_task_id: str,
    worker_route: str,
    worker_budget: str,
    cost_limit_usd: float | str,
) -> dict[str, object]:
    """Create a one-candidate lineage ready for its target evaluation."""

    return {
        "schema_version": 1,
        "lineage_id": lineage_id,
        "status": "running",
        "phase": "TARGET",
        "current_parent": {
            "version": parent_version,
            "worker_dir": parent_path,
        },
        "candidate": {
            "version": candidate_version,
            "worker_dir": candidate_path,
        },
        "target_task_id": target_task_id,
        "protection_task_id": protection_task_id,
        "worker_route": worker_route,
        "worker_budget": worker_budget,
        "cost_limit_usd": str(cost_limit_usd),
        "cost": {
            "provider_cost_usd": "0",
            "completed_requests": 0,
            "total_tokens": 0,
        },
        "accounted_run_ids": [],
        "observations": {},
        "archive": [],
        "decision": None,
    }


def new_proposal_lineage(
    *,
    lineage_id: str,
    parent_version: str,
    parent_path: str,
    target_task_id: str,
    protection_task_id: str,
    worker_route: str,
    worker_budget: str,
    cost_limit_usd: float | str,
) -> dict[str, object]:
    """Create a lineage whose candidate will come from an Evolver report."""

    state = new_lineage(
        lineage_id=lineage_id,
        parent_version=parent_version,
        parent_path=parent_path,
        candidate_version="proposal-pending",
        candidate_path="",
        target_task_id=target_task_id,
        protection_task_id=protection_task_id,
        worker_route=worker_route,
        worker_budget=worker_budget,
        cost_limit_usd=cost_limit_usd,
    )
    state["phase"] = "PROPOSAL"
    state["candidate"] = None
    state["proposal"] = None
    return state


def load_lineage(path: str | Path) -> dict[str, object]:
    """Load a saved lineage state."""

    value = json.loads(Path(path).read_text())
    if not isinstance(value, dict):
        raise LineageError("lineage state must be a JSON object")
    return value


def save_lineage(path: str | Path, state: Mapping[str, object]) -> None:
    """Atomically save a lineage state as ordinary JSON."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    temporary.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, destination)


def _decimal(value: object, *, label: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise LineageError(f"{label} is not numeric") from exc


def _score(report: Mapping[str, object], arm: str, task_id: str) -> dict[str, object]:
    summaries = report.get("summaries")
    if not isinstance(summaries, Mapping) or not isinstance(
        summaries.get(arm), Mapping
    ):
        raise LineageError(f"pilot report has no {arm!r} summary")
    scores = summaries[arm].get("scores")
    if not isinstance(scores, list):
        raise LineageError(f"pilot report has no {arm!r} scores")
    matches = [item for item in scores if item.get("task_id") == task_id]
    if len(matches) != 1:
        raise LineageError(f"pilot report has no unique {arm!r}/{task_id!r} score")
    raw = matches[0]
    if raw.get("verifier_exit_code") != 0:
        raise LineageError(f"{arm!r}/{task_id!r} verifier did not complete")
    passed = raw.get("tests_passed")
    failed = raw.get("tests_failed")
    reward = raw.get("reward")
    if not isinstance(passed, int) or not isinstance(failed, int):
        raise LineageError(f"{arm!r}/{task_id!r} has no property counts")
    if not isinstance(reward, (int, float)):
        raise LineageError(f"{arm!r}/{task_id!r} has no official reward")
    return {
        "reward": float(reward),
        "tests_passed": passed,
        "tests_failed": failed,
    }


def _gain(parent: Mapping[str, object], candidate: Mapping[str, object]) -> bool:
    no_regression = (
        float(candidate["reward"]) >= float(parent["reward"])
        and int(candidate["tests_passed"]) >= int(parent["tests_passed"])
    )
    strict = (
        float(candidate["reward"]) > float(parent["reward"])
        or int(candidate["tests_passed"]) > int(parent["tests_passed"])
    )
    return no_regression and strict


def _aggregate_safe(
    parent: Mapping[str, object], candidate: Mapping[str, object]
) -> bool:
    return (
        float(candidate["reward"]) >= float(parent["reward"])
        and int(candidate["tests_passed"]) >= int(parent["tests_passed"])
    )


def _add_cost(state: dict[str, object], report: Mapping[str, object]) -> None:
    run_id = report.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise LineageError("pilot report has no run_id")
    accounted = state["accounted_run_ids"]
    if run_id in accounted:
        return
    raw = report.get("cost")
    if not isinstance(raw, Mapping):
        raise LineageError("pilot report has no cost summary")
    cost = state["cost"]
    total_cost = _decimal(
        cost["provider_cost_usd"], label="accounted provider cost"
    ) + _decimal(raw.get("provider_cost_usd"), label="report provider cost")
    cost["provider_cost_usd"] = format(total_cost, "f")
    cost["completed_requests"] = int(cost["completed_requests"]) + int(
        raw.get("completed_request_count", 0)
    )
    cost["total_tokens"] = int(cost["total_tokens"]) + int(
        raw.get("total_tokens", 0)
    )
    accounted.append(run_id)


def _add_proposal_cost(
    state: dict[str, object],
    *,
    proposal_run_id: str,
    report: Mapping[str, object],
) -> None:
    accounted = state["accounted_run_ids"]
    if proposal_run_id in accounted:
        return
    raw = report.get("candidate_generation_throughput")
    if not isinstance(raw, Mapping):
        raise LineageError("proposal report has no generation cost summary")
    cost = state["cost"]
    total_cost = _decimal(
        cost["provider_cost_usd"], label="accounted provider cost"
    ) + _decimal(raw.get("provider_cost_usd"), label="proposal provider cost")
    cost["provider_cost_usd"] = format(total_cost, "f")
    cost["completed_requests"] = (
        int(cost["completed_requests"])
        + int(raw.get("completed_request_count", 0))
        + int(raw.get("downstream_delivery_request_count", 0))
    )
    cost["total_tokens"] = int(cost["total_tokens"]) + int(
        raw.get("total_tokens", 0)
    )
    accounted.append(proposal_run_id)


def _budget_reached(state: Mapping[str, object]) -> bool:
    return _decimal(
        state["cost"]["provider_cost_usd"], label="accounted provider cost"
    ) >= _decimal(state["cost_limit_usd"], label="cost limit")


def _finish_candidate(
    state: dict[str, object], *, decision: str, reason: str
) -> dict[str, object]:
    candidate = deepcopy(state["candidate"])
    candidate["decision"] = decision
    candidate["reason"] = reason
    state["archive"].append(candidate)
    if decision == "PROMOTE":
        state["current_parent"] = {
            "version": candidate["version"],
            "worker_dir": candidate["worker_dir"],
        }
    state["decision"] = decision
    state["phase"] = "PROPOSE"
    state["status"] = "candidate_complete"
    return state


def import_proposal_report(
    state: Mapping[str, object],
    *,
    report: Mapping[str, object],
    report_path: str,
    proposal_run_id: str,
    candidate_version: str,
) -> dict[str, object]:
    """Import one existing discovery ``proposal-report.json`` exactly once."""

    result = deepcopy(dict(state))
    if proposal_run_id in result.get("accounted_run_ids", []):
        return result
    if result.get("phase") != "PROPOSAL":
        raise LineageError(
            f"cannot import proposal while lineage phase is {result.get('phase')}"
        )
    decision = str(report.get("decision", "")).strip().upper()
    if decision not in {"ACT", "ABSTAIN"}:
        raise LineageError("proposal report has no legal ACT or ABSTAIN decision")
    admission = report.get("admission")
    if not isinstance(admission, Mapping):
        raise LineageError("proposal report has no admission record")
    candidate_path = report.get("candidate_dir")
    _add_proposal_cost(
        result,
        proposal_run_id=proposal_run_id,
        report=report,
    )
    result["proposal"] = {
        "run_id": proposal_run_id,
        "report_path": report_path,
        "decision": decision,
        "admitted": admission.get("admitted"),
        "candidate_dir": candidate_path,
    }

    if decision == "ABSTAIN":
        result["decision"] = "ABSTAIN"
        result["phase"] = "FROZEN"
        result["status"] = "abstained"
        return result
    if admission.get("admitted") is not True:
        result["decision"] = "ROLLBACK"
        result["phase"] = "FROZEN"
        result["status"] = "proposal_rejected"
        return result
    if not isinstance(candidate_path, str) or not candidate_path:
        raise LineageError("admitted ACT proposal has no candidate_dir")

    result["candidate"] = {
        "version": candidate_version,
        "worker_dir": candidate_path,
    }
    result["decision"] = None
    result["phase"] = "TARGET"
    result["status"] = "running"
    if _budget_reached(result):
        result["decision"] = "BUDGET_STOP"
        result["phase"] = "BUDGET_STOP"
        result["status"] = "stopped"
    return result


def import_pilot_report(
    state: Mapping[str, object],
    *,
    stage: str,
    report: Mapping[str, object],
    report_path: str,
    parent_arm: str,
    candidate_arm: str,
    relation_observed: bool | None = None,
    property_set_safe: bool | None = None,
) -> dict[str, object]:
    """Apply one completed target, repeat, or protection child report."""

    if stage not in _STAGE_PHASE:
        raise LineageError(f"unknown lineage stage: {stage}")
    if report.get("status") != "complete":
        raise LineageError("pilot report is not complete")
    result = deepcopy(dict(state))
    run_id = report.get("run_id")
    if run_id in result.get("accounted_run_ids", []):
        return result
    if result.get("phase") != _STAGE_PHASE[stage]:
        raise LineageError(
            f"cannot import {stage} while lineage phase is {result.get('phase')}"
        )
    task_id = (
        result["protection_task_id"]
        if stage == "protection"
        else result["target_task_id"]
    )
    parent = _score(report, parent_arm, str(task_id))
    candidate = _score(report, candidate_arm, str(task_id))
    _add_cost(result, report)

    observation = {
        "run_id": run_id,
        "report_path": report_path,
        "task_id": task_id,
        "parent": parent,
        "candidate": candidate,
        "relation_observed": relation_observed,
    }
    result["observations"][stage] = observation

    if stage in {"target", "repeat"}:
        passed = _gain(parent, candidate)
        observation["gate_passed"] = passed
        if not passed:
            return _finish_candidate(
                result, decision="ROLLBACK", reason=f"{stage}_gain_not_observed"
            )
        if _budget_reached(result):
            result["decision"] = "BUDGET_STOP"
            result["phase"] = "BUDGET_STOP"
            result["status"] = "stopped"
            return result
        result["phase"] = "REPEAT" if stage == "target" else "PROTECTION"
        return result

    aggregate_safe = _aggregate_safe(parent, candidate)
    observation["aggregate_safe"] = aggregate_safe
    observation["property_set_safe"] = property_set_safe
    passed = aggregate_safe and property_set_safe is True
    observation["gate_passed"] = passed
    if passed:
        return _finish_candidate(
            result, decision="PROMOTE", reason="repeat_and_protection_safe"
        )
    return _finish_candidate(
        result, decision="ROLLBACK", reason="protection_not_property_safe"
    )


def freeze_lineage(state: Mapping[str, object]) -> dict[str, object]:
    """Freeze a completed candidate lineage."""

    result = deepcopy(dict(state))
    if result.get("phase") != "PROPOSE" or result.get("decision") not in {
        "PROMOTE",
        "ROLLBACK",
    }:
        raise LineageError("only a completed promote/rollback decision can freeze")
    result["phase"] = "FROZEN"
    result["status"] = "frozen"
    return result
