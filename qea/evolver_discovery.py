"""Deterministic observability metrics for evolver discovery canaries.

These metrics do not grade whether a proposed harness change is truly correct.
They measure whether the evolver performed the observable parts of causal
discovery: inspected evidence, considered alternatives, recorded uncertainty,
made a falsifiable prediction, and kept its final report consistent with the
intervention it unlocked.
"""

from __future__ import annotations

from typing import Mapping, Sequence


_CAUSAL_FIELDS = (
    "hypotheses_considered",
    "selected_mechanism",
    "evidence_refs",
    "counterevidence",
    "uncertainty",
    "discriminating_probe",
    "component",
    "prediction",
    "risk_tasks",
)


def _nonempty(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (Mapping, Sequence)) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        return bool(value)
    return True


def _exact_paths(values: object, members: set[str]) -> set[str]:
    if not isinstance(values, list):
        return set()
    result: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        if value in members:
            result.add(value)
            continue
        for member in members:
            if value.startswith(member + " ") or value.startswith(member + " ("):
                result.add(member)
                break
    return result


def _failure_type_quality(
    *,
    final: Mapping[str, object],
    access: Mapping[str, object],
    state: Mapping[str, object],
    members: set[str],
) -> dict[str, object]:
    """Measure the A5 failure-type/probe/decision protocol."""

    protocol = str(state.get("protocol", "failure_type_v1"))

    hypothesis_value = state.get("hypothesis")
    hypothesis = (
        dict(hypothesis_value) if isinstance(hypothesis_value, Mapping) else {}
    )
    accessed = {
        str(value)
        for value in access.get("evidence_paths", [])
        if isinstance(value, str) and value in members
    }
    cited = _exact_paths(final.get("evidence_used"), members)
    decision_refs = _exact_paths(hypothesis.get("evidence_refs"), members)
    raw_types = hypothesis.get("failure_types")
    failure_types = [
        dict(value)
        for value in raw_types
        if isinstance(raw_types, list) and isinstance(value, Mapping)
    ] if isinstance(raw_types, list) else []
    type_refs: set[str] = set()
    typed_tasks: set[str] = set()
    recurrent_type_count = 0
    matched_type_count = 0
    for failure_type in failure_types:
        type_refs |= _exact_paths(failure_type.get("evidence_refs"), members)
        member_tasks = failure_type.get("member_tasks")
        if isinstance(member_tasks, list):
            task_values = {
                str(value) for value in member_tasks if isinstance(value, str)
            }
            typed_tasks |= task_values
            recurrent_type_count += len(task_values) >= 2
        matched = failure_type.get("matched_success_tasks")
        matched_type_count += isinstance(matched, list) and bool(matched)

    raw_hypotheses = hypothesis.get("hypotheses_considered")
    hypotheses = [
        dict(value)
        for value in raw_hypotheses
        if isinstance(raw_hypotheses, list) and isinstance(value, Mapping)
    ] if isinstance(raw_hypotheses, list) else []
    hypothesis_ids = {
        str(value.get("hypothesis_id"))
        for value in hypotheses
        if isinstance(value.get("hypothesis_id"), str)
    }
    counterfactual_count = sum(
        isinstance(value.get("success_counterfactual"), str)
        and bool(str(value.get("success_counterfactual")).strip())
        for value in hypotheses
    )
    insufficient_contrast_count = sum(
        value.get("insufficient_contrast") is True for value in hypotheses
    )
    probes = hypothesis.get("probe_records_used")
    probes = [dict(value) for value in probes if isinstance(value, Mapping)] \
        if isinstance(probes, list) else []
    eliminated = hypothesis.get("hypotheses_eliminated")
    eliminated_ids = {
        str(value) for value in eliminated if isinstance(value, str)
    } if isinstance(eliminated, list) else set()
    decision = str(state.get("decision", hypothesis.get("decision", ""))).upper()
    selected = hypothesis.get("selected_hypothesis_id")
    typed_probes = {
        str(value.get("probe_id")): value
        for value in probes
        if value.get("probe_kind") == "typed_contract_artifact_trace_v1"
        and isinstance(value.get("probe_id"), str)
    }
    grounded_ids_raw = hypothesis.get("grounded_comparison_probe_ids")
    grounded_ids = {
        str(value)
        for value in grounded_ids_raw
        if isinstance(value, str)
    } if isinstance(grounded_ids_raw, list) else set()
    semantic_refs: set[str] = set()
    valid_grounded_ids: set[str] = set()
    for probe_id in grounded_ids:
        probe = typed_probes.get(probe_id)
        if probe is None:
            continue
        semantic_refs |= _exact_paths(probe.get("evidence_paths"), members)
        expectations = probe.get("hypothesis_expectations")
        matches = probe.get("expectation_matches")
        if not isinstance(expectations, Mapping) or not isinstance(matches, Mapping):
            continue
        selected_matches = (
            isinstance(selected, str)
            and selected in expectations
            and matches.get(selected) is True
        )
        eliminated_mismatches = any(
            hypothesis_id in expectations and matches.get(hypothesis_id) is False
            for hypothesis_id in eliminated_ids
        )
        relation_is_resolvable = probe.get("semantic_relation") in {
            "supports",
            "contradicts",
        }
        if selected_matches and eliminated_mismatches and relation_is_resolvable:
            valid_grounded_ids.add(probe_id)
    final_decision = str(final.get("decision", "")).upper()
    final_selected = final.get("selected_hypothesis_id")
    state_components = hypothesis.get("components")
    state_component_set = {
        str(value) for value in state_components if isinstance(value, str)
    } if isinstance(state_components, list) else set()
    final_components = final.get("components_changed")
    if isinstance(final_components, list):
        final_component_set = {
            str(value) for value in final_components if isinstance(value, str)
        }
    elif isinstance(final.get("component_changed"), str):
        final_component_set = {str(final["component_changed"])}
    else:
        final_component_set = set()

    all_refs = cited | decision_refs | type_refs | semantic_refs
    grounded = all_refs & accessed
    is_act = decision == "ACT"
    is_abstain = decision == "ABSTAIN"
    checks = {
        "decision_recorded": is_act or is_abstain,
        "recurring_failure_type": recurrent_type_count >= 1,
        "multiple_hypotheses": len(hypotheses) >= 2,
        "probe_executed": bool(probes),
        "probe_discriminated_or_abstained": bool(eliminated_ids) or is_abstain,
        "selected_hypothesis_survives": (
            isinstance(selected, str)
            and selected in hypothesis_ids
            and selected not in eliminated_ids
        ) if is_act else selected is None or selected not in eliminated_ids,
        "counterevidence_recorded": _nonempty(hypothesis.get("counterevidence")),
        "uncertainty_recorded": _nonempty(hypothesis.get("uncertainty")),
        "all_decision_refs_accessed": bool(decision_refs | type_refs)
        and (decision_refs | type_refs) <= accessed,
        "act_components_or_abstain": (
            bool(state_component_set) if is_act else not state_component_set
        ),
        "final_decision_consistent": final_decision == decision,
        "final_hypothesis_consistent": (
            final_selected == selected if is_act else True
        ),
        "final_components_consistent": final_component_set == state_component_set,
        "falsifiable_prediction_or_abstain_reason": (
            _nonempty(hypothesis.get("prediction"))
            if is_act
            else _nonempty(hypothesis.get("abstain_reason"))
        ),
    }
    if protocol == "semantic_contract_v1":
        final_grounded = final.get("grounded_comparison_probe_ids")
        final_grounded_set = {
            str(value) for value in final_grounded if isinstance(value, str)
        } if isinstance(final_grounded, list) else set()
        checks.update(
            {
                "grounded_semantic_comparison_or_abstain": (
                    bool(valid_grounded_ids) if is_act else True
                ),
                "typed_probe_discriminates_selected_from_eliminated_or_abstain": (
                    bool(valid_grounded_ids) if is_act else True
                ),
                "semantic_evidence_paths_accessed_or_abstain": (
                    bool(semantic_refs) and semantic_refs <= accessed
                    if is_act
                    else True
                ),
                "final_grounded_comparisons_consistent": (
                    final_grounded_set == grounded_ids if is_act else True
                ),
            }
        )
    requirements = state.get("contract_requirements")
    requirements = dict(requirements) if isinstance(requirements, Mapping) else {}
    semantic_mode = requirements.get("semantic_comparison")
    semantic_required = semantic_mode == "required_for_act"
    semantic_optional = semantic_mode == "available_not_required"
    semantic_claimed = bool(grounded_ids)
    semantic_leap_applicable = is_act and (
        semantic_required or (semantic_optional and semantic_claimed)
    )
    unsupported_semantic_leap = (
        not bool(valid_grounded_ids) if semantic_leap_applicable else None
    )
    success_required = (
        requirements.get("success_counterfactual") == "required_or_insufficient"
    )
    if success_required:
        checks["success_counterfactual_or_insufficient"] = bool(hypotheses) and all(
            (
                isinstance(value.get("success_counterfactual"), str)
                and bool(str(value.get("success_counterfactual")).strip())
            )
            or value.get("insufficient_contrast") is True
            for value in hypotheses
        )

    operations = access.get("operations")
    operations = dict(operations) if isinstance(operations, Mapping) else {}
    return {
        "schema_version": 3 if protocol == "semantic_contract_v1" else 2,
        "protocol": protocol,
        "scope": (
            "observable type induction, probe discrimination, and decision "
            "calibration; not causal truth"
        ),
        "decision": decision or None,
        "checks": checks,
        "contract_score": sum(bool(value) for value in checks.values()) / len(checks),
        "failure_type_count": len(failure_types),
        "recurrent_failure_type_count": recurrent_type_count,
        "typed_failure_task_count": len(typed_tasks),
        "types_with_matched_success_count": matched_type_count,
        "hypotheses_considered_count": len(hypotheses),
        "hypotheses_eliminated_count": len(eliminated_ids),
        "probe_count": len(probes),
        "typed_semantic_probe_count": len(typed_probes),
        "grounded_semantic_comparison_count": len(grounded_ids),
        "valid_grounded_semantic_comparison_count": len(valid_grounded_ids),
        "unsupported_semantic_leap": unsupported_semantic_leap,
        "unsupported_semantic_leap_applicable": semantic_leap_applicable,
        "semantic_comparison_availability": (
            "required_for_act"
            if semantic_required
            else "available_optional"
            if semantic_optional
            else "structurally_unavailable"
            if semantic_mode == "not_required"
            else "not_declared"
        ),
        "semantic_comparison_mode": semantic_mode,
        "causal_truth_certified": False,
        "success_counterfactual_count": counterfactual_count,
        "insufficient_contrast_count": insufficient_contrast_count,
        "evidence_member_count": len(members),
        "exact_evidence_access_count": len(accessed),
        "evidence_access_ratio": len(accessed) / len(members) if members else None,
        "cited_evidence_count": len(all_refs),
        "grounded_citation_count": len(grounded),
        "grounded_citation_ratio": len(grounded) / len(all_refs) if all_refs else None,
        "debugger_files_accessed": sum(
            value.startswith("debugger/") for value in accessed
        ),
        "trace_files_accessed": sum("trace" in value.casefold() for value in accessed),
        "components_selected": sorted(state_component_set),
        "query_operations": {
            name: int(operations.get(name, 0) or 0)
            for name in (
                "map",
                "trace_slice",
                "compare",
                "probe",
                "semantic_probe",
                "read",
                "search",
                "decision",
            )
        },
    }


def measure_discovery_quality(
    *,
    prediction: Mapping[str, object] | None,
    access_summary: Mapping[str, object] | None,
    discovery_state: Mapping[str, object] | None,
    evidence_members: Sequence[str] = (),
) -> dict[str, object]:
    """Measure observable discovery behavior without judging benchmark truth."""

    final = dict(prediction or {})
    access = dict(access_summary or {})
    state = dict(discovery_state or {})
    members = set(str(value) for value in evidence_members)
    if state.get("protocol") in {"failure_type_v1", "semantic_contract_v1"}:
        return _failure_type_quality(
            final=final,
            access=access,
            state=state,
            members=members,
        )
    hypothesis_value = state.get("hypothesis")
    hypothesis = (
        dict(hypothesis_value) if isinstance(hypothesis_value, Mapping) else {}
    )
    accessed = {
        str(value)
        for value in access.get("evidence_paths", [])
        if isinstance(value, str) and value in members
    }
    cited = _exact_paths(final.get("evidence_used"), members)
    hypothesis_refs = _exact_paths(hypothesis.get("evidence_refs"), members)
    all_refs = cited | hypothesis_refs
    grounded = all_refs & accessed

    causal_presence = {
        field: _nonempty(hypothesis.get(field)) for field in _CAUSAL_FIELDS
    }
    alternatives = hypothesis.get("hypotheses_considered")
    alternative_count = len(alternatives) if isinstance(alternatives, list) else 0
    final_selected = final.get("selected_mechanism")
    final_component = final.get("component_changed")
    consistent_mechanism = (
        isinstance(final_selected, str)
        and final_selected.strip()
        == str(hypothesis.get("selected_mechanism", "")).strip()
    )
    consistent_component = (
        isinstance(final_component, str)
        and final_component.strip() == str(hypothesis.get("component", "")).strip()
    )
    checks = {
        "writes_unlocked": state.get("unlocked") is True,
        "multiple_hypotheses": alternative_count >= 2,
        "counterevidence_recorded": causal_presence["counterevidence"],
        "uncertainty_recorded": causal_presence["uncertainty"],
        "discriminating_probe_recorded": causal_presence["discriminating_probe"],
        "falsifiable_prediction_recorded": causal_presence["prediction"],
        "at_least_two_evidence_refs": len(hypothesis_refs) >= 2,
        "all_hypothesis_refs_accessed": bool(hypothesis_refs)
        and hypothesis_refs <= accessed,
        "final_mechanism_consistent": consistent_mechanism,
        "final_component_consistent": consistent_component,
        "predicted_process_changes_reported": _nonempty(
            final.get("predicted_process_changes")
        ),
    }
    operations = access.get("operations")
    operations = dict(operations) if isinstance(operations, Mapping) else {}
    return {
        "schema_version": 1,
        "scope": "observable discovery contract; not correctness or benchmark quality",
        "checks": checks,
        "contract_score": sum(bool(value) for value in checks.values()) / len(checks),
        "causal_field_presence": causal_presence,
        "hypotheses_considered_count": alternative_count,
        "evidence_member_count": len(members),
        "exact_evidence_access_count": len(accessed),
        "evidence_access_ratio": len(accessed) / len(members) if members else None,
        "cited_evidence_count": len(all_refs),
        "grounded_citation_count": len(grounded),
        "grounded_citation_ratio": len(grounded) / len(all_refs) if all_refs else None,
        "debugger_files_accessed": sum(
            value.startswith("debugger/") for value in accessed
        ),
        "trace_files_accessed": sum(
            "trace" in value.casefold() for value in accessed
        ),
        "query_operations": {
            name: int(operations.get(name, 0) or 0)
            for name in ("map", "trace_slice", "compare", "read", "search")
        },
    }


__all__ = ["measure_discovery_quality"]
