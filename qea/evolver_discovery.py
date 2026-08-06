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
    hypothesis_value = state.get("hypothesis")
    hypothesis = (
        dict(hypothesis_value) if isinstance(hypothesis_value, Mapping) else {}
    )
    members = set(str(value) for value in evidence_members)
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
        and final_selected.strip() == str(hypothesis.get("selected_mechanism", "")).strip()
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
