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
    candidate_information_set_review: bool = False,
    quantitative_protection_review: bool = False,
    repeat_consistency_policy: str = "aggregate_only",
    retained_activation_token: str | None = None,
) -> dict[str, object]:
    """Create a one-candidate lineage ready for its target evaluation."""

    if repeat_consistency_policy not in _REPEAT_CONSISTENCY_POLICIES:
        raise LineageError(
            f"unknown repeat consistency policy: {repeat_consistency_policy}"
        )

    current_parent = {
        "version": parent_version,
        "worker_dir": parent_path,
    }
    if retained_activation_token is not None:
        if (
            not isinstance(retained_activation_token, str)
            or not retained_activation_token
        ):
            raise LineageError(
                "retained activation token must be a non-empty string"
            )
        current_parent["retained_activation_token"] = retained_activation_token

    candidate_changed = (
        candidate_version != parent_version
        or Path(parent_path).resolve(strict=False)
        != Path(candidate_path).resolve(strict=False)
    )
    review_required = candidate_changed or candidate_information_set_review
    state = {
        "schema_version": 1,
        "lineage_id": lineage_id,
        "status": "running",
        "phase": "INFORMATION_SET_REVIEW" if review_required else "TARGET",
        "current_parent": current_parent,
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
        "candidate_information_set_review": review_required,
    }
    return state


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
    candidate_information_set_review: bool = True,
    quantitative_protection_review: bool = False,
    repeat_consistency_policy: str = "aggregate_only",
    retained_activation_token: str | None = None,
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
        candidate_information_set_review=True,
        quantitative_protection_review=quantitative_protection_review,
        repeat_consistency_policy=repeat_consistency_policy,
        retained_activation_token=retained_activation_token,
    )
    state["phase"] = "PROPOSAL"
    state["candidate"] = None
    state["proposal"] = None
    state["candidate_information_set_review"] = True
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


def _registered_tools(worker_dir: object) -> dict[str, dict[str, str | None]]:
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
    tools: dict[str, dict[str, str | None]] = {}
    for value in payload["tools"]:
        if not isinstance(value, Mapping):
            continue
        name = value.get("name")
        if isinstance(name, str) and name:
            path = value.get("yaml_path")
            binding = value.get("binding")
            tools[name] = {
                "descriptor_path": (
                    path if isinstance(path, str) and path else None
                ),
                "binding": (
                    binding
                    if isinstance(binding, str) and binding
                    else None
                ),
            }
    return tools


def _descriptor_snapshot(
    worker_dir: object, descriptor_path: str | None
) -> tuple[bool, object]:
    """Read one registered descriptor for semantic parent/candidate comparison."""

    if not isinstance(worker_dir, str) or not worker_dir or not descriptor_path:
        return False, None
    try:
        payload = yaml.safe_load((Path(worker_dir) / descriptor_path).read_text())
    except (OSError, yaml.YAMLError):
        return False, None
    return True, payload


def _binding_source_snapshot(
    worker_dir: object, binding: str | None
) -> tuple[bool, str | None]:
    """Read a registered local Python binding when its module maps directly."""

    if not isinstance(worker_dir, str) or not worker_dir or not binding:
        return False, None
    module = binding.partition(":")[0]
    if not module:
        return False, None
    source_path = Path(worker_dir).joinpath(*module.split(".")).with_suffix(".py")
    try:
        return True, source_path.read_text()
    except OSError:
        return False, None


def _modified_registered_tools(
    *,
    parent_dir: object,
    candidate_dir: object,
    parent_tools: Mapping[str, Mapping[str, str | None]],
    candidate_tools: Mapping[str, Mapping[str, str | None]],
) -> dict[str, list[str]]:
    """Find common registered tools whose callable contract or source changed."""

    modified: dict[str, list[str]] = {}
    for name in sorted(set(parent_tools) & set(candidate_tools)):
        parent = parent_tools[name]
        candidate = candidate_tools[name]
        changed_surfaces: list[str] = []
        if parent.get("binding") != candidate.get("binding"):
            changed_surfaces.append("binding")
        if _descriptor_snapshot(
            parent_dir, parent.get("descriptor_path")
        ) != _descriptor_snapshot(
            candidate_dir, candidate.get("descriptor_path")
        ):
            changed_surfaces.append("descriptor")
        if _binding_source_snapshot(
            parent_dir, parent.get("binding")
        ) != _binding_source_snapshot(
            candidate_dir, candidate.get("binding")
        ):
            changed_surfaces.append("source")
        if changed_surfaces:
            modified[name] = changed_surfaces
    return modified


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


def _proposal_worker_visible_claims(
    report: Mapping[str, object],
) -> list[dict[str, object]] | None:
    """Read the structured claim list from the admitted Evolver decision."""

    summary = report.get("summary")
    discovery = (
        summary.get("discovery_hypothesis")
        if isinstance(summary, Mapping)
        else None
    )
    hypothesis = (
        discovery.get("hypothesis") if isinstance(discovery, Mapping) else None
    )
    claims = (
        hypothesis.get("worker_visible_claims")
        if isinstance(hypothesis, Mapping)
        else None
    )
    if not isinstance(claims, list) or not claims:
        return None
    if not all(isinstance(claim, Mapping) for claim in claims):
        return None
    return [deepcopy(dict(claim)) for claim in claims]


def _activation_binding(
    *,
    parent_dir: object,
    candidate_dir: object,
    retained_activation_token: object = None,
) -> dict[str, object]:
    """Bind one changed tool, or one explicitly retained unchanged tool."""

    parent_tools = _registered_tools(parent_dir)
    candidate_tools = _registered_tools(candidate_dir)
    added = sorted(set(candidate_tools) - set(parent_tools))
    modified = _modified_registered_tools(
        parent_dir=parent_dir,
        candidate_dir=candidate_dir,
        parent_tools=parent_tools,
        candidate_tools=candidate_tools,
    )
    changed = added + sorted(modified)
    binding: dict[str, object] = {
        "status": (
            "singleton"
            if len(changed) == 1
            else "none"
            if not changed
            else "ambiguous"
        ),
        "new_registered_tools": added,
        "modified_registered_tools": sorted(modified),
    }
    if len(changed) == 1:
        token = changed[0]
        change_kind = "added" if token in added else "modified"
        tool = candidate_tools[token]
        binding["realized_component"] = {
            "kind": "tool",
            "token": token,
            "change_kind": change_kind,
            "changed_surfaces": (
                ["registration"] if change_kind == "added" else modified[token]
            ),
            "descriptor_path": tool.get("descriptor_path"),
            "binding": tool.get("binding"),
            "source": "admitted_candidate_registration",
        }
    elif not changed and isinstance(retained_activation_token, str):
        if (
            retained_activation_token in parent_tools
            and retained_activation_token in candidate_tools
        ):
            tool = candidate_tools[retained_activation_token]
            binding["status"] = "retained"
            binding["realized_component"] = {
                "kind": "tool",
                "token": retained_activation_token,
                "change_kind": "retained",
                "changed_surfaces": [],
                "descriptor_path": tool.get("descriptor_path"),
                "binding": tool.get("binding"),
                "source": "lineage_parent_retained_activation_token",
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

    observations = state.get("observations")
    target = (
        observations.get("target")
        if isinstance(observations, Mapping)
        else None
    )
    target_mechanism = (
        target.get("mechanism") if isinstance(target, Mapping) else None
    )
    footprint = (
        target_mechanism.get("empirical_relation_footprint")
        if isinstance(target_mechanism, Mapping)
        else None
    )
    if (
        not isinstance(footprint, Mapping)
        or footprint.get("status") != "ANCHORED"
    ):
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


def _annotate_protection_mechanism(
    state: Mapping[str, object],
    observation: dict[str, object],
    *,
    safety_passed: bool | None,
) -> None:
    """Separate a protection safety gate from target-relation transfer."""

    mechanism = observation.get("mechanism")
    if not isinstance(mechanism, dict):
        return
    target = state.get("observations", {}).get("target")
    target_mechanism = (
        target.get("mechanism") if isinstance(target, Mapping) else None
    )
    footprint = (
        target_mechanism.get("empirical_relation_footprint")
        if isinstance(target_mechanism, Mapping)
        else None
    )
    marker = observation.get("relation_observed")
    if not isinstance(footprint, Mapping) or footprint.get("status") != "ANCHORED":
        # Legacy score-only lineages have no target relation footprint.  Their
        # decisions and existing observation shape remain unchanged.
        return

    expected = _property_ids(footprint, "resolved_property_ids")
    delta = observation.get("property_delta")
    observed_properties = frozenset().union(
        *(
            _property_ids(delta, field)
            for field in (
                "parent_failed",
                "candidate_failed",
                "resolved",
                "introduced",
                "persistent",
            )
        )
    )
    activation = mechanism.get("activation")
    activation = activation if isinstance(activation, Mapping) else {}
    activation_matches = (
        footprint.get("activation_required") is not True
        or (
            activation.get("status") == "ACTIVATED"
            and activation.get("token") == footprint.get("component_token")
        )
    )
    exact_footprint_observed = bool(expected & observed_properties) and (
        activation_matches
    )
    if marker is True:
        exercised = True
        reason = "matched_semantic_marker_observed"
    elif marker is False:
        exercised = False
        reason = "semantic_marker_declared_not_observed"
    elif exact_footprint_observed:
        exercised = True
        reason = "target_property_footprint_observed"
    else:
        exercised = False
        reason = "target_relation_not_observed_on_protection"

    if safety_passed is True:
        protection_outcome = "SAFE_NO_REGRESSION"
    elif safety_passed is False:
        protection_outcome = "SAFETY_GATE_FAILED"
    else:
        protection_outcome = "SAFETY_INCONCLUSIVE"
    mechanism["protection_outcome"] = protection_outcome
    mechanism["semantic_protection"] = {
        "policy": "target_relation_exercise_v1",
        "relation_id": footprint.get("relation_id"),
        "expected_property_ids": sorted(expected),
        "relation_observed": marker,
        "verdict": "MATCHED" if exercised else "NOT_EXERCISED",
        "reason": reason,
        "boundary": "safety_gate_not_relation_transfer",
    }
    if not exercised:
        mechanism["relation_outcome"] = "NOT_EXERCISED"


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
    worker_visible_claims = _proposal_worker_visible_claims(report)
    if worker_visible_claims is not None:
        result["proposal"]["worker_visible_claims"] = worker_visible_claims

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
        retained_activation_token=result["current_parent"].get(
            "retained_activation_token"
        ),
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
    if result.get("candidate_information_set_review") is True:
        if worker_visible_claims is None:
            return _hold_candidate_for_refine(
                result,
                reason="information_set_review_missing_worker_visible_claims",
            )
        result["phase"] = "INFORMATION_SET_REVIEW"
    else:
        result["phase"] = "TARGET"
    result["status"] = "running"
    if _budget_reached(result):
        result["decision"] = "BUDGET_STOP"
        result["phase"] = "BUDGET_STOP"
        result["status"] = "stopped"
    return result


def hold_candidate_information_set_review(
    state: Mapping[str, object], *, reason: str
) -> dict[str, object]:
    """Stop an opt-in candidate when its review package cannot be constructed."""

    result = deepcopy(dict(state))
    if result.get("phase") != "INFORMATION_SET_REVIEW":
        raise LineageError(
            "cannot hold information-set review outside INFORMATION_SET_REVIEW"
        )
    return _hold_candidate_for_refine(result, reason=reason)


def import_candidate_information_set_review(
    state: Mapping[str, object],
    *,
    review_id: str,
    review_path: str,
    review_package: Mapping[str, object],
    review_payload: Mapping[str, object],
    review_accounting: Mapping[str, object],
    reviewed_candidate_dir: str,
) -> dict[str, object]:
    """Import one pre-Worker answer-boundary review exactly once."""

    from qea.candidate_information_set_review import (
        validate_candidate_information_set_review,
    )

    result = deepcopy(dict(state))
    accounted = result.setdefault("accounted_review_ids", [])
    if review_id in accounted:
        return result
    if result.get("phase") != "INFORMATION_SET_REVIEW":
        raise LineageError(
            "cannot import candidate review outside INFORMATION_SET_REVIEW"
        )
    validated = validate_candidate_information_set_review(
        review_payload, review_package
    )
    candidate = result.get("candidate")
    if not isinstance(candidate, Mapping):
        raise LineageError("candidate review has no active candidate")
    candidate_worker_dir = candidate.get("worker_dir")
    if (
        not isinstance(reviewed_candidate_dir, str)
        or not reviewed_candidate_dir
        or candidate_worker_dir != reviewed_candidate_dir
    ):
        raise LineageError(
            "candidate review must bind the active reviewed_candidate snapshot"
        )
    _add_review_cost(result, review_accounting)
    accounted.append(review_id)
    result["observations"]["information_set_review"] = {
        "review_id": review_id,
        "review_path": review_path,
        "overall_verdict": validated["overall_verdict"],
        "claim_reviews": deepcopy(validated["claim_reviews"]),
        "coverage_review": deepcopy(validated["coverage_review"]),
        "worker_visible": False,
        "promotion_authority": False,
        "reviewed_candidate_dir": reviewed_candidate_dir,
    }
    verdict = validated["overall_verdict"]
    if verdict == "PASS":
        result["candidate"]["information_set_review"] = {
            "review_id": review_id,
            "overall_verdict": "PASS",
            "reviewed_candidate_dir": reviewed_candidate_dir,
        }
        result["phase"] = "TARGET"
        result["status"] = "running"
        if _budget_reached(result):
            result["decision"] = "BUDGET_STOP"
            result["phase"] = "BUDGET_STOP"
            result["status"] = "stopped"
        return result
    return _hold_candidate_for_refine(
        result,
        reason=f"information_set_review_{str(verdict).lower()}",
    )


def _require_candidate_information_set_review_pass(
    state: Mapping[str, object],
) -> None:
    """Fail closed before importing any changed-candidate Worker observation."""

    candidate = state.get("candidate")
    if not isinstance(candidate, Mapping):
        if state.get("candidate_information_set_review") is True:
            raise LineageError("changed candidate has no review-bound worker")
        return
    parent = state.get("current_parent")
    parent_dir = parent.get("worker_dir") if isinstance(parent, Mapping) else None
    parent_version = parent.get("version") if isinstance(parent, Mapping) else None
    candidate_dir = candidate.get("worker_dir")
    candidate_version = candidate.get("version")
    changed_candidate = (
        parent_version != candidate_version
        or (
            isinstance(parent_dir, str)
            and isinstance(candidate_dir, str)
            and Path(parent_dir).resolve(strict=False)
            != Path(candidate_dir).resolve(strict=False)
        )
    )
    if (
        state.get("candidate_information_set_review") is not True
        and not changed_candidate
    ):
        return
    binding = candidate.get("information_set_review")
    if not isinstance(binding, Mapping) or binding.get("overall_verdict") != "PASS":
        raise LineageError(
            "changed candidate cannot reach Worker evaluation without Review PASS"
        )
    worker_dir = candidate.get("worker_dir")
    if (
        not isinstance(worker_dir, str)
        or not worker_dir
        or binding.get("reviewed_candidate_dir") != worker_dir
    ):
        raise LineageError(
            "Worker candidate differs from the exact reviewed_candidate snapshot"
        )
    observations = state.get("observations")
    observation = (
        observations.get("information_set_review")
        if isinstance(observations, Mapping)
        else None
    )
    coverage = (
        observation.get("coverage_review")
        if isinstance(observation, Mapping)
        else None
    )
    if (
        not isinstance(observation, Mapping)
        or observation.get("overall_verdict") != "PASS"
        or observation.get("reviewed_candidate_dir") != worker_dir
        or not isinstance(coverage, Mapping)
        or coverage.get("verdict") != "PASS"
    ):
        raise LineageError(
            "changed candidate has no matching retained Review PASS observation"
        )


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

    if report.get("status") == "invalid_worker_execution":
        return _import_invalid_worker_observation(
            state,
            stage=stage,
            report=report,
            report_path=report_path,
            parent_arm=parent_arm,
            candidate_arm=candidate_arm,
        )
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
    selection_reference_reuse = report.get("selection_reference_reuse")
    if isinstance(selection_reference_reuse, Mapping):
        provenance = {
            "selection_reference_reuse": dict(selection_reference_reuse)
        }
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


def _import_invalid_worker_observation(
    state: Mapping[str, object],
    *,
    stage: str,
    report: Mapping[str, object],
    report_path: str,
    parent_arm: str,
    candidate_arm: str,
) -> dict[str, object]:
    """Retain an infrastructure-invalid Worker run without score selection."""

    if stage not in _STAGE_PHASE:
        raise LineageError(f"unknown lineage stage: {stage}")
    run_id = report.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise LineageError("pilot report has no run_id")
    cost = report.get("cost")
    if not isinstance(cost, Mapping):
        raise LineageError("invalid Worker report has no cost summary")
    result = deepcopy(dict(state))
    _require_candidate_information_set_review_pass(result)
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

    executions = report.get("worker_executions")
    invalid_attempts: list[dict[str, object]] = []
    if isinstance(executions, Mapping):
        for arm in (parent_arm, candidate_arm):
            arm_execution = executions.get(arm)
            if not isinstance(arm_execution, Mapping):
                continue
            attempts = arm_execution.get("attempts")
            if not isinstance(attempts, list):
                continue
            invalid_attempts.extend(
                {"arm": arm, **deepcopy(dict(attempt))}
                for attempt in attempts
                if isinstance(attempt, Mapping)
                and attempt.get("valid_for_selection") is False
            )
    if not invalid_attempts:
        raise LineageError(
            "invalid Worker report has no invalid compared-arm execution"
        )

    task_id = (
        result["protection_task_id"]
        if stage in {"protection", "protection_repeat"}
        else result["target_task_id"]
    )
    _add_cost(result, {"run_id": run_id, "cost": dict(cost)})
    result["observations"][stage] = {
        "run_id": run_id,
        "report_path": report_path,
        "benchmark": "qfbench",
        "task_id": task_id,
        "observation_kind": "infrastructure_invalid",
        "selection_valid": False,
        "invalid_worker_executions": invalid_attempts,
    }
    result["decision"] = "INVALID_OBSERVATION"
    result["phase"] = "HOLD_FOR_REFINE"
    result["status"] = "infrastructure_invalid"
    result["hold"] = {
        "candidate_version": result["candidate"]["version"],
        "kind": "infrastructure_invalid_observation",
        "reason": "model_empty_response_before_worker_progress",
    }
    return result


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
    _require_candidate_information_set_review_pass(result)
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
            _annotate_protection_mechanism(
                result, observation, safety_passed=True
            )
            return _finish_candidate(
                result,
                decision="PROMOTE",
                reason="repeat_and_quantitative_protection_noninferior",
            )
        if verdict == "FAIL":
            _annotate_protection_mechanism(
                result, observation, safety_passed=False
            )
            return _hold_candidate_for_refine(
                result, reason="quantitative_protection_regression"
            )
        if verdict != "INCONCLUSIVE":
            raise LineageError("quantitative protection triage has no legal verdict")
        if stage == "protection_repeat":
            _annotate_protection_mechanism(
                result, observation, safety_passed=None
            )
            return _hold_candidate_for_refine(
                result, reason="quantitative_protection_still_inconclusive"
            )
        _annotate_protection_mechanism(
            result, observation, safety_passed=None
        )
        result["phase"] = "PROTECTION_REVIEW"
        result["status"] = "running"
        return result

    passed = aggregate_safe and property_set_safe is True
    observation["gate_passed"] = passed
    _annotate_protection_mechanism(
        result, observation, safety_passed=passed
    )
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
