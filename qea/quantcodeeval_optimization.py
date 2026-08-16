"""Answer-rich optimization diagnostics and matched-family transfer gates.

The diagnostic is visible to the Evolver for a declared optimization task.  It
is not a Worker input.  Transfer eligibility stays answer-free with respect to
the destination task: the trusted coordinator compares compact failure
signatures after a blind H0 run.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Mapping


class QuantCodeEvalOptimizationError(ValueError):
    """Optimization evidence cannot form a usable Evolver diagnostic."""


_SIGNATURE_FIELDS = (
    "mechanism_family",
    "semantic_state",
    "pipeline_phase",
    "observable",
)


def _json(path: Path, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise QuantCodeEvalOptimizationError(f"cannot read {label}: {path}") from exc
    if not isinstance(value, dict):
        raise QuantCodeEvalOptimizationError(f"{label} must be a JSON object")
    return value


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _text(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise QuantCodeEvalOptimizationError(f"{label} must be non-empty text")
    return value.strip()


def _signature(value: Mapping[str, object], *, label: str) -> dict[str, object]:
    normalized = dict(value)
    for field in _SIGNATURE_FIELDS:
        normalized[field] = _text(value.get(field), label=f"{label}.{field}")
    observed = value.get("observed_failure", True)
    if type(observed) is not bool:
        raise QuantCodeEvalOptimizationError(
            f"{label}.observed_failure must be boolean"
        )
    normalized["observed_failure"] = observed
    property_ids = value.get("property_ids", [])
    if not isinstance(property_ids, list) or any(
        not isinstance(item, str) or not item.strip() for item in property_ids
    ):
        raise QuantCodeEvalOptimizationError(
            f"{label}.property_ids must be a list of property IDs"
        )
    normalized["property_ids"] = list(dict.fromkeys(property_ids))
    return normalized


def _rubric_items(
    manifest: Mapping[str, object],
    overrides: Mapping[str, Mapping[str, object]],
) -> dict[str, dict[str, object]]:
    raw = manifest.get("checkers")
    if not isinstance(raw, list) or not raw:
        raise QuantCodeEvalOptimizationError("rubric manifest has no checkers")
    items: dict[str, dict[str, object]] = {}
    for index, row in enumerate(raw):
        if not isinstance(row, Mapping):
            raise QuantCodeEvalOptimizationError(
                f"rubric checker {index} must be an object"
            )
        property_id = _text(
            row.get("property_id"), label=f"rubric checker {index}.property_id"
        )
        if property_id in items:
            raise QuantCodeEvalOptimizationError(
                f"duplicate rubric property: {property_id}"
            )
        property_name = _text(
            row.get("property_name", property_id),
            label=f"rubric checker {property_id}.property_name",
        )
        override = overrides.get(property_id, {})
        expected = override.get("expected_behavior")
        if expected is None:
            expected = property_name.replace("_", " ")
        public_refs = override.get("public_contract_refs", [])
        if not isinstance(public_refs, list) or any(
            not isinstance(item, str) or not item.strip() for item in public_refs
        ):
            raise QuantCodeEvalOptimizationError(
                f"rubric override {property_id}.public_contract_refs is invalid"
            )
        items[property_id] = {
            "property_id": property_id,
            "criterion": _text(
                override.get("criterion", property_name.replace("_", " ")),
                label=f"rubric override {property_id}.criterion",
            ),
            "expected_behavior": _text(
                expected, label=f"rubric override {property_id}.expected_behavior"
            ),
            "task_function": row.get("task_function"),
            "public_contract_refs": list(dict.fromkeys(public_refs)),
            "observations": [],
        }
    unknown = sorted(set(overrides) - set(items))
    if unknown:
        raise QuantCodeEvalOptimizationError(
            "rubric overrides contain unknown properties: " + ", ".join(unknown)
        )
    return items


def build_quantcodeeval_optimization_diagnostic(
    *,
    destination: str | Path,
    task_id: str,
    attempts: Iterable[Mapping[str, object]],
    rubric_manifest_path: str | Path,
    rubric_overrides: Mapping[str, Mapping[str, object]] | None = None,
    candidate_changes: Iterable[Mapping[str, object]] = (),
    failure_signatures: Iterable[Mapping[str, object]] = (),
) -> dict[str, object]:
    """Build an item-level, answer-rich diagnostic for one optimize task."""

    task = _text(task_id, label="task_id")
    target = Path(destination).expanduser().resolve()
    if target.exists():
        raise QuantCodeEvalOptimizationError(
            f"diagnostic destination already exists: {target}"
        )
    manifest = _json(
        Path(rubric_manifest_path).expanduser().resolve(), label="rubric manifest"
    )
    if manifest.get("task_id") not in (None, task):
        raise QuantCodeEvalOptimizationError("rubric manifest task does not match")
    rubric = _rubric_items(manifest, rubric_overrides or {})

    attempt_rows: list[dict[str, object]] = []
    labels: set[str] = set()
    for index, raw in enumerate(attempts):
        label = _text(raw.get("label"), label=f"attempt {index}.label")
        if label in labels:
            raise QuantCodeEvalOptimizationError(f"duplicate attempt label: {label}")
        labels.add(label)
        role = _text(raw.get("role"), label=f"attempt {label}.role")
        ctrf_path = Path(
            _text(raw.get("ctrf_path"), label=f"attempt {label}.ctrf_path")
        ).expanduser().resolve()
        ctrf = _json(ctrf_path, label=f"attempt {label} checker result")
        results = ctrf.get("results")
        if not isinstance(results, list):
            raise QuantCodeEvalOptimizationError(
                f"attempt {label} checker result has no result list"
            )
        seen: set[str] = set()
        for result_index, result in enumerate(results):
            if not isinstance(result, Mapping):
                raise QuantCodeEvalOptimizationError(
                    f"attempt {label} result {result_index} is invalid"
                )
            property_id = _text(
                result.get("property_id"),
                label=f"attempt {label} result {result_index}.property_id",
            )
            if property_id not in rubric:
                raise QuantCodeEvalOptimizationError(
                    f"attempt {label} has unknown property {property_id}"
                )
            if property_id in seen:
                raise QuantCodeEvalOptimizationError(
                    f"attempt {label} repeats property {property_id}"
                )
            seen.add(property_id)
            verdict = _text(
                result.get("verdict"), label=f"attempt {label}.{property_id}.verdict"
            ).upper()
            if verdict not in {"PASS", "FAIL", "SKIP", "ERROR"}:
                raise QuantCodeEvalOptimizationError(
                    f"attempt {label}.{property_id} has invalid verdict"
                )
            rubric[property_id]["observations"].append(
                {
                    "attempt": label,
                    "role": role,
                    "verdict": verdict,
                    "observed_behavior": result.get("detail"),
                    "checker_evidence": result.get("evidence"),
                }
            )
        attempt_rows.append(
            {
                "label": label,
                "role": role,
                "score": {
                    "passed": ctrf.get("pass", ctrf.get("summary", {}).get("passed") if isinstance(ctrf.get("summary"), Mapping) else None),
                    "failed": ctrf.get("fail", ctrf.get("summary", {}).get("failed") if isinstance(ctrf.get("summary"), Mapping) else None),
                    "total": ctrf.get("total"),
                },
                "candidate_change": raw.get("candidate_change"),
            }
        )
    if not attempt_rows:
        raise QuantCodeEvalOptimizationError("at least one attempt is required")

    signature_rows = [
        _signature(value, label=f"failure_signatures[{index}]")
        for index, value in enumerate(failure_signatures)
        if isinstance(value, Mapping)
    ]
    payload = {
        "schema_version": 1,
        "benchmark": "quantcodeeval",
        "task_id": task,
        "feedback_mode": "answer_rich_evolver",
        "visibility": "evolver_only",
        "worker_visible": False,
        "attempts": attempt_rows,
        "rubric_items": list(rubric.values()),
        "candidate_changes": [dict(value) for value in candidate_changes],
        "observed_failure_signatures": signature_rows,
        "evolver_assignment": {
            "separate_task_specific_evidence_from_reusable_capability": True,
            "choose": ["REFINE", "SPLIT", "SYNTHESIZE", "ABSTAIN"],
            "full_harness_mutation_allowed": True,
            "task_answers_must_not_enter_reusable_candidate": True,
            "failure_signature_required_for_act": True,
        },
    }
    _write_json(target, payload)
    return {
        "schema_version": 1,
        "destination": str(target),
        "task_id": task,
        "attempt_count": len(attempt_rows),
        "rubric_item_count": len(rubric),
        "failure_signature_count": len(signature_rows),
    }


def assess_transfer_eligibility(
    *,
    component_signature: Mapping[str, object],
    source_signatures: Iterable[Mapping[str, object]],
    destination_signatures: Iterable[Mapping[str, object]],
) -> dict[str, object]:
    """Check whether a blind destination H0 tests the component mechanism."""

    component = _signature(component_signature, label="component_signature")
    sources = [
        _signature(value, label=f"source_signatures[{index}]")
        for index, value in enumerate(source_signatures)
    ]
    destinations = [
        _signature(value, label=f"destination_signatures[{index}]")
        for index, value in enumerate(destination_signatures)
    ]
    family = str(component["mechanism_family"])
    matched_sources = [
        row
        for row in sources
        if row["observed_failure"] is True and row["mechanism_family"] == family
    ]
    matched_destinations = [
        row
        for row in destinations
        if row["observed_failure"] is True and row["mechanism_family"] == family
    ]
    eligible = bool(matched_sources and matched_destinations)
    if not matched_sources:
        reason = "the component mechanism is not grounded in an observed source failure"
    elif not matched_destinations:
        reason = "the destination H0 has no observed failure in the component mechanism"
    else:
        reason = "source and destination H0 expose the same component mechanism"
    return {
        "schema_version": 1,
        "eligible": eligible,
        "mechanism_family": family,
        "reason": reason,
        "source_matches": matched_sources,
        "destination_matches": matched_destinations,
        "candidate_run_allowed": eligible,
        "unmatched_destination_may_be_protection_only": not eligible,
    }


__all__ = [
    "QuantCodeEvalOptimizationError",
    "assess_transfer_eligibility",
    "build_quantcodeeval_optimization_diagnostic",
]
