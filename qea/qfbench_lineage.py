"""Small candidate-lineage state machine with shared official transitions."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Mapping

import yaml


class LineageError(ValueError):
    """Raised when a lineage or child report cannot be interpreted."""


_STAGE_PHASE = {
    "target": "TARGET",
    "repeat": "REPEAT",
    "protection": "PROTECTION",
    "protection_repeat": "PROTECTION_REPEAT",
}
_REPEAT_CONSISTENCY_POLICIES = frozenset(
    {"aggregate_only", "resolved_property_footprint_v1"}
)


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
    quantitative_protection_review: bool = False,
    repeat_consistency_policy: str = "aggregate_only",
) -> dict[str, object]:
    """Create a one-candidate lineage ready for its target evaluation."""

    if repeat_consistency_policy not in _REPEAT_CONSISTENCY_POLICIES:
        raise LineageError(
            f"unknown repeat consistency policy: {repeat_consistency_policy}"
        )

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
        "accounted_review_ids": [],
        "observations": {},
        "archive": [],
        "decision": None,
        "quantitative_protection_review": quantitative_protection_review,
        "repeat_consistency_policy": repeat_consistency_policy,
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
    quantitative_protection_review: bool = False,
    repeat_consistency_policy: str = "aggregate_only",
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
        quantitative_protection_review=quantitative_protection_review,
        repeat_consistency_policy=repeat_consistency_policy,
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


def _add_review_cost(
    state: dict[str, object], accounting: Mapping[str, object]
) -> None:
    """Add one Reviewer request using the lineage's existing cost fields."""

    cost = state["cost"]
    total_cost = _decimal(
        cost["provider_cost_usd"], label="accounted provider cost"
    ) + _decimal(
        accounting.get("provider_cost_usd", 0), label="review provider cost"
    )
    cost["provider_cost_usd"] = format(total_cost, "f")
    cost["completed_requests"] = int(cost["completed_requests"]) + int(
        accounting.get("completed_request_count", 0)
    )
    cost["total_tokens"] = int(cost["total_tokens"]) + int(
        accounting.get("total_tokens", 0)
    )


def _budget_reached(state: Mapping[str, object]) -> bool:
    return _decimal(
        state["cost"]["provider_cost_usd"], label="accounted provider cost"
    ) >= _decimal(state["cost_limit_usd"], label="cost limit")


def _registered_tools(worker_dir: object) -> dict[str, str | None]:
    """Return the tools actually registered by one admitted Worker harness."""

    if not isinstance(worker_dir, str) or not worker_dir:
        return {}
    try:
        payload = yaml.safe_load((Path(worker_dir) / "agent.yaml").read_text())
    except (OSError, yaml.YAMLError):
        return {}
    if not isinstance(payload, Mapping) or not isinstance(
        payload.get("tools"), list
    ):
        return {}
    tools: dict[str, str | None] = {}
    for value in payload["tools"]:
        if not isinstance(value, Mapping):
            continue
        name = value.get("name")
        if isinstance(name, str) and name:
            path = value.get("yaml_path")
            tools[name] = path if isinstance(path, str) and path else None
    return tools


def _proposal_mechanism_claim(
    report: Mapping[str, object],
) -> dict[str, object] | None:
    """Keep the compact mechanism claim already emitted by the Evolver."""

    summary = report.get("summary")
    discovery = (
        summary.get("discovery_hypothesis")
        if isinstance(summary, Mapping)
        else None
    )
    hypothesis = (
        discovery.get("hypothesis") if isinstance(discovery, Mapping) else None
    )
    if not isinstance(hypothesis, Mapping):
        return None
    claim: dict[str, object] = {}
    for field in (
        "selected_relation",
        "research_state_transition",
        "component_routing",
        "prediction",
    ):
        if field in hypothesis:
            claim[field] = deepcopy(hypothesis[field])
    return claim or None


def _activation_binding(
    *, parent_dir: object, candidate_dir: object
) -> dict[str, object]:
    """Bind a singleton newly registered tool without guessing among tools."""

    parent_tools = _registered_tools(parent_dir)
    candidate_tools = _registered_tools(candidate_dir)
    added = sorted(set(candidate_tools) - set(parent_tools))
    binding: dict[str, object] = {
        "status": (
            "singleton"
            if len(added) == 1
            else "none"
            if not added
            else "ambiguous"
        ),
        "new_registered_tools": added,
    }
    if len(added) == 1:
        token = added[0]
        binding["realized_component"] = {
            "kind": "tool",
            "token": token,
            "descriptor_path": candidate_tools[token],
            "source": "admitted_candidate_registration",
        }
    return binding


def _mechanism_observation(
    state: Mapping[str, object],
    *,
    activation: Mapping[str, object] | None,
    parent: Mapping[str, object],
    candidate: Mapping[str, object],
) -> dict[str, object] | None:
    """Relate exact activation to official deltas without claiming causality."""

    proposal = state.get("proposal")
    claim = proposal.get("mechanism_claim") if isinstance(proposal, Mapping) else None
    selected_relation = (
        claim.get("selected_relation") if isinstance(claim, Mapping) else None
    )
    relation_id = (
        selected_relation.get("relation_id")
        if isinstance(selected_relation, Mapping)
        else None
    )
    if activation is None and relation_id is None:
        return None

    candidate_state = state.get("candidate")
    token = (
        candidate_state.get("activation_token")
        if isinstance(candidate_state, Mapping)
        else None
    )
    count = activation.get("activation_count") if activation is not None else None
    if isinstance(count, bool) or not isinstance(count, int):
        count = None
    if not isinstance(token, str) or not token:
        status = "UNKNOWN"
    elif count is None:
        status = "UNKNOWN"
    elif count > 0:
        status = "ACTIVATED"
    else:
        status = "NOT_ACTIVATED"

    gain = _gain(parent, candidate)
    if status == "ACTIVATED":
        relation_outcome = (
            "ACTIVATED_WITH_OFFICIAL_GAIN"
            if gain
            else "ACTIVATED_WITHOUT_OFFICIAL_GAIN"
        )
    elif status == "NOT_ACTIVATED":
        relation_outcome = "NOT_ACTIVATED"
    else:
        relation_outcome = "UNKNOWN"

    attempts: list[dict[str, object]] = []
    raw_attempts = activation.get("attempts") if activation is not None else None
    if isinstance(raw_attempts, list):
        for value in raw_attempts:
            if not isinstance(value, Mapping):
                continue
            attempts.append(
                {
                    field: value.get(field)
                    for field in (
                        "attempt_id",
                        "task_id",
                        "trace_path",
                        "activation_token",
                        "activated",
                    )
                    if field in value
                }
            )
    return {
        "relation_id": relation_id,
        "activation": {
            "token": token,
            "status": status,
            "count": count,
            "attempts": attempts,
        },
        "official_outcome": {
            "reward_delta": float(candidate["reward"]) - float(parent["reward"]),
            "tests_passed_delta": int(candidate["tests_passed"])
            - int(parent["tests_passed"]),
            "strict_gain_observed": gain,
        },
        "relation_outcome": relation_outcome,
        "boundary": "association_not_causal_semantic_verification",
    }


def _property_ids(
    delta: Mapping[str, object] | None, field: str
) -> frozenset[str]:
    if not isinstance(delta, Mapping) or not isinstance(delta.get(field), list):
        return frozenset()
    return frozenset(
        str(value) for value in delta[field] if isinstance(value, str) and value
    )


def _target_relation_footprint(
    observation: Mapping[str, object],
) -> dict[str, object]:
    """Bind a proposed relation to its first independent property correction."""

    mechanism = observation.get("mechanism")
    mechanism = mechanism if isinstance(mechanism, Mapping) else {}
    activation = mechanism.get("activation")
    activation = activation if isinstance(activation, Mapping) else {}
    relation_id = mechanism.get("relation_id")
    component_token = activation.get("token")
    activation_status = activation.get("status", "UNKNOWN")
    resolved = sorted(_property_ids(observation.get("property_delta"), "resolved"))
    introduced = sorted(
        _property_ids(observation.get("property_delta"), "introduced")
    )
    callable_component = isinstance(component_token, str) and bool(component_token)
    # Generic proposals do not have to name a research relation.  The
    # footprint is still an independently observed component/outcome anchor,
    # so requiring a relation ID here would make the matched QRS treatment
    # easier to promote than the generic arm.
    anchored = bool(resolved) and (
        not callable_component or activation_status == "ACTIVATED"
    )
    return {
        "policy": "resolved_property_footprint_v1",
        "relation_id": relation_id,
        "component_token": component_token,
        "activation_status": activation_status,
        "activation_required": callable_component,
        "resolved_property_ids": resolved,
        "introduced_property_ids": introduced,
        "status": "ANCHORED" if anchored else "UNBOUND",
        "boundary": "empirical_association_not_semantic_causality",
    }


def evaluate_repeat_semantic_consistency(
    state: Mapping[str, object], observation: Mapping[str, object]
) -> dict[str, object]:
    """Check whether repeat reproduces the target's empirical relation footprint."""

    target = state.get("observations", {}).get("target")
    target_mechanism = (
        target.get("mechanism") if isinstance(target, Mapping) else None
    )
    footprint = (
        target_mechanism.get("empirical_relation_footprint")
        if isinstance(target_mechanism, Mapping)
        else None
    )
    if not isinstance(footprint, Mapping) or footprint.get("status") != "ANCHORED":
        return {
            "policy": "resolved_property_footprint_v1",
            "verdict": "UNBOUND",
            "reason": "target_relation_footprint_unbound",
        }

    expected = _property_ids(footprint, "resolved_property_ids")
    delta = observation.get("property_delta")
    parent_failed = _property_ids(delta, "parent_failed")
    candidate_failed = _property_ids(delta, "candidate_failed")
    resolved = _property_ids(delta, "resolved")
    introduced = _property_ids(delta, "introduced")
    resolved_expected = expected & resolved
    persistent_expected = expected & parent_failed & candidate_failed
    introduced_expected = expected & candidate_failed - parent_failed
    not_exercised_expected = expected - parent_failed - candidate_failed
    unrelated_resolved = resolved - expected

    mechanism = observation.get("mechanism")
    mechanism = mechanism if isinstance(mechanism, Mapping) else {}
    activation = mechanism.get("activation")
    activation = activation if isinstance(activation, Mapping) else {}
    activation_status = activation.get("status", "UNKNOWN")
    activation_required = footprint.get("activation_required") is True
    component_token = activation.get("token")
    same_component = component_token == footprint.get("component_token")

    if activation_required and (
        activation_status != "ACTIVATED" or not same_component
    ):
        verdict = "INCONSISTENT"
        reason = "repeat_component_not_activated"
    elif persistent_expected or introduced_expected or introduced:
        verdict = "INCONSISTENT"
        reason = "repeat_relation_footprint_not_reproduced"
    elif not_exercised_expected:
        verdict = "NOT_EXERCISED"
        reason = "repeat_parent_did_not_expose_target_footprint"
    elif resolved_expected == expected:
        verdict = "CONSISTENT"
        reason = "repeat_relation_footprint_reproduced"
    else:
        verdict = "INCONSISTENT"
        reason = "repeat_relation_footprint_not_reproduced"

    return {
        "policy": "resolved_property_footprint_v1",
        "relation_id": footprint.get("relation_id"),
        "component_token": footprint.get("component_token"),
        "activation_status": activation_status,
        "expected_property_ids": sorted(expected),
        "resolved_expected": sorted(resolved_expected),
        "persistent_expected": sorted(persistent_expected),
        "introduced_expected": sorted(introduced_expected),
        "not_exercised_expected": sorted(not_exercised_expected),
        "unrelated_resolved": sorted(unrelated_resolved),
        "repeat_introduced": sorted(introduced),
        "verdict": verdict,
        "reason": reason,
    }


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


def _hold_candidate_for_refine(
    state: dict[str, object], *, reason: str
) -> dict[str, object]:
    """Keep the incumbent and candidate source while pausing for refinement."""

    state["decision"] = "HOLD_FOR_REFINE"
    state["phase"] = "HOLD_FOR_REFINE"
    state["status"] = "candidate_hold"
    state["hold"] = {
        "candidate_version": state["candidate"]["version"],
        "reason": reason,
    }
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
    mechanism_claim = _proposal_mechanism_claim(report)
    if mechanism_claim is not None:
        result["proposal"]["mechanism_claim"] = mechanism_claim

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

    activation_binding = _activation_binding(
        parent_dir=result["current_parent"]["worker_dir"],
        candidate_dir=candidate_path,
    )
    result["candidate"] = {
        "version": candidate_version,
        "worker_dir": candidate_path,
        "activation_binding": activation_binding,
    }
    realized = activation_binding.get("realized_component")
    if isinstance(realized, Mapping):
        result["candidate"]["realized_component"] = deepcopy(dict(realized))
        result["candidate"]["activation_token"] = realized["token"]
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
    property_delta: Mapping[str, object] | None = None,
    property_set_safe: bool | None = None,
    quantitative_protection_triage: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Apply one completed target, repeat, or protection child report."""

    if report.get("status") != "complete":
        raise LineageError("pilot report is not complete")
    run_id = report.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise LineageError("pilot report has no run_id")
    result = dict(state)
    task_id = (
        result["protection_task_id"]
        if stage in {"protection", "protection_repeat"}
        else result["target_task_id"]
    )
    parent = _score(report, parent_arm, str(task_id))
    candidate = _score(report, candidate_arm, str(task_id))
    provenance = None
    comparator_reuse = report.get("parent_comparator_reuse")
    if isinstance(comparator_reuse, Mapping):
        provenance = {"parent_comparator_reuse": dict(comparator_reuse)}
    activations = report.get("activations")
    candidate_activation = (
        activations.get(candidate_arm) if isinstance(activations, Mapping) else None
    )
    return import_comparison_observation(
        state,
        stage=stage,
        run_id=run_id,
        task_id=str(task_id),
        parent=parent,
        candidate=candidate,
        cost=report.get("cost"),
        benchmark="qfbench",
        report_path=report_path,
        provenance=provenance,
        relation_observed=relation_observed,
        mechanism_activation=(
            candidate_activation
            if isinstance(candidate_activation, Mapping)
            else None
        ),
        property_delta=property_delta,
        property_set_safe=property_set_safe,
        quantitative_protection_triage=quantitative_protection_triage,
    )


def _comparison_score(
    value: Mapping[str, object], *, label: str
) -> dict[str, object]:
    """Validate one benchmark-independent official selection score."""

    reward = value.get("reward")
    passed = value.get("tests_passed")
    failed = value.get("tests_failed")
    if isinstance(reward, bool) or not isinstance(reward, (int, float)):
        raise LineageError(f"{label} comparison score has no official reward")
    if (
        isinstance(passed, bool)
        or not isinstance(passed, int)
        or isinstance(failed, bool)
        or not isinstance(failed, int)
    ):
        raise LineageError(f"{label} comparison score has no property counts")
    if value.get("official_valid") is False:
        raise LineageError(f"{label} comparison score is not official-valid")
    result = {
        "reward": float(reward),
        "tests_passed": passed,
        "tests_failed": failed,
    }
    for field in (
        "official_valid",
        "verifier_executed",
        "verifier_exit_code",
        "selection_source",
    ):
        if field in value:
            result[field] = value[field]
    return result


def import_comparison_observation(
    state: Mapping[str, object],
    *,
    stage: str,
    run_id: str,
    task_id: str,
    parent: Mapping[str, object],
    candidate: Mapping[str, object],
    cost: Mapping[str, object] | None,
    benchmark: str,
    report_path: str,
    provenance: Mapping[str, object] | None = None,
    relation_observed: bool | None = None,
    mechanism_activation: Mapping[str, object] | None = None,
    property_delta: Mapping[str, object] | None = None,
    property_set_safe: bool | None = None,
    quantitative_protection_triage: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Apply one official parent--candidate comparison to a lineage."""

    if stage not in _STAGE_PHASE:
        raise LineageError(f"unknown lineage stage: {stage}")
    if not isinstance(run_id, str) or not run_id:
        raise LineageError("comparison has no run_id")
    if not isinstance(cost, Mapping):
        raise LineageError("comparison has no candidate cost summary")
    result = deepcopy(dict(state))
    if run_id in result.get("accounted_run_ids", []):
        existing = result.get("observations", {}).get(stage)
        if isinstance(existing, Mapping) and existing.get("run_id") == run_id:
            return result
        raise LineageError(
            f"comparison run_id {run_id!r} is already used by another stage"
        )
    if result.get("phase") != _STAGE_PHASE[stage]:
        raise LineageError(
            f"cannot import {stage} while lineage phase is {result.get('phase')}"
        )
    expected_task_id = (
        result["protection_task_id"]
        if stage in {"protection", "protection_repeat"}
        else result["target_task_id"]
    )
    if task_id != expected_task_id:
        raise LineageError(
            f"comparison task {task_id!r} differs from active {stage} task"
        )
    normalized_parent = _comparison_score(parent, label="parent")
    normalized_candidate = _comparison_score(candidate, label="candidate")
    _add_cost(result, {"run_id": run_id, "cost": dict(cost)})

    observation = {
        "run_id": run_id,
        "report_path": report_path,
        "benchmark": benchmark,
        "task_id": task_id,
        "parent": normalized_parent,
        "candidate": normalized_candidate,
        "relation_observed": relation_observed,
    }
    mechanism = _mechanism_observation(
        result,
        activation=mechanism_activation,
        parent=normalized_parent,
        candidate=normalized_candidate,
    )
    if mechanism is not None:
        observation["mechanism"] = mechanism
    if isinstance(property_delta, Mapping):
        observation["property_delta"] = deepcopy(dict(property_delta))
    if isinstance(provenance, Mapping):
        observation["provenance"] = deepcopy(dict(provenance))
        comparator_reuse = provenance.get("parent_comparator_reuse")
        if isinstance(comparator_reuse, Mapping):
            observation["parent_comparator_reuse"] = deepcopy(
                dict(comparator_reuse)
            )
    result["observations"][stage] = observation

    if stage in {"target", "repeat"}:
        passed = _gain(normalized_parent, normalized_candidate)
        observation["gate_passed"] = passed
        semantic_policy = result.get("repeat_consistency_policy")
        if (
            stage == "repeat"
            and semantic_policy == "resolved_property_footprint_v1"
        ):
            mechanism = observation.setdefault("mechanism", {})
            semantic_repeat = evaluate_repeat_semantic_consistency(
                result, observation
            )
            mechanism["semantic_repeat"] = semantic_repeat
            if semantic_repeat["verdict"] == "INCONSISTENT":
                return _finish_candidate(
                    result,
                    decision="ROLLBACK",
                    reason=str(semantic_repeat["reason"]),
                )
            if semantic_repeat["verdict"] in {"NOT_EXERCISED", "UNBOUND"}:
                return _hold_candidate_for_refine(
                    result, reason=str(semantic_repeat["reason"])
                )
            if not passed:
                return _finish_candidate(
                    result,
                    decision="ROLLBACK",
                    reason="repeat_gain_not_observed",
                )
        elif not passed:
            return _finish_candidate(
                result, decision="ROLLBACK", reason=f"{stage}_gain_not_observed"
            )
        if (
            stage == "target"
            and semantic_policy == "resolved_property_footprint_v1"
        ):
            mechanism = observation.setdefault("mechanism", {})
            footprint = _target_relation_footprint(observation)
            mechanism["empirical_relation_footprint"] = footprint
            if footprint["status"] != "ANCHORED":
                return _hold_candidate_for_refine(
                    result, reason="target_relation_footprint_unbound"
                )
        if _budget_reached(result):
            result["decision"] = "BUDGET_STOP"
            result["phase"] = "BUDGET_STOP"
            result["status"] = "stopped"
            return result
        result["phase"] = "REPEAT" if stage == "target" else "PROTECTION"
        return result

    aggregate_safe = _aggregate_safe(normalized_parent, normalized_candidate)
    observation["aggregate_safe"] = aggregate_safe
    observation["property_set_safe"] = property_set_safe
    quantitative_path = (
        result.get("quantitative_protection_review") is True
        and quantitative_protection_triage is not None
    )
    if quantitative_path:
        triage = deepcopy(dict(quantitative_protection_triage))
        observation["quantitative_protection_triage"] = triage
        verdict = triage.get("verdict")
        if verdict == "PASS":
            return _finish_candidate(
                result,
                decision="PROMOTE",
                reason="repeat_and_quantitative_protection_noninferior",
            )
        if verdict == "FAIL":
            return _hold_candidate_for_refine(
                result, reason="quantitative_protection_regression"
            )
        if verdict != "INCONCLUSIVE":
            raise LineageError("quantitative protection triage has no legal verdict")
        if stage == "protection_repeat":
            return _hold_candidate_for_refine(
                result, reason="quantitative_protection_still_inconclusive"
            )
        result["phase"] = "PROTECTION_REVIEW"
        result["status"] = "running"
        return result

    passed = aggregate_safe and property_set_safe is True
    observation["gate_passed"] = passed
    if passed:
        return _finish_candidate(
            result, decision="PROMOTE", reason="repeat_and_protection_safe"
        )
    return _finish_candidate(
        result, decision="ROLLBACK", reason="protection_not_property_safe"
    )


def import_quantitative_protection_review(
    state: Mapping[str, object],
    *,
    review_id: str,
    review_path: str,
    review_payload: Mapping[str, object],
    case_id: str,
    review_accounting: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Import and optionally account for one answer-free Reviewer result."""

    from qea.quantitative_protection_review import (
        validate_quantitative_regression_review,
    )

    result = deepcopy(dict(state))
    accounted = result.setdefault("accounted_review_ids", [])
    if review_id in accounted:
        return result
    if result.get("phase") != "PROTECTION_REVIEW":
        raise LineageError(
            "cannot import quantitative review outside PROTECTION_REVIEW"
        )
    validated = validate_quantitative_regression_review(
        review_payload, [case_id]
    )
    review = deepcopy(validated["reviews"][0])
    if review_accounting is not None:
        _add_review_cost(result, review_accounting)
    accounted.append(review_id)
    result["observations"]["protection_review"] = {
        "review_id": review_id,
        "review_path": review_path,
        "review": review,
    }
    next_evidence = review["next_evidence"]
    if next_evidence == "PAIRED_PROTECTION_REPEAT":
        result["phase"] = "PROTECTION_REPEAT"
        result["status"] = "running"
        return result
    return _hold_candidate_for_refine(
        result, reason=f"quantitative_review_{str(next_evidence).lower()}"
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
