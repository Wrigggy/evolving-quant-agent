"""Deterministic triage before a quantitative protection review.

The triage is deliberately answer-free and JSON-shaped.  It separates an
ordinary protection pass, a numerically ambiguous comparison, and a clear
candidate regression.  It does not promote a candidate or mutate a lineage;
the fixed controller remains responsible for those decisions.
"""

from __future__ import annotations

import json
from typing import Callable, Mapping, Sequence


_BROKEN_RELATION_OUTCOMES = {"BROKEN", "FAIL", "FAILED"}
_OUTCOME_SEVERITIES = {
    "WITHIN_PROVISIONAL_VARIABILITY",
    "MEANINGFUL_CANDIDATE_REGRESSION",
    "UNRESOLVED",
}
_CAUSAL_ATTRIBUTIONS = {
    "COMPONENT_CAUSAL",
    "WORKER_TRAJECTORY",
    "HARNESS_WORKER_INTERACTION",
    "UNRESOLVED",
}
_QUANTITATIVE_DIAGNOSES = {
    "NUMERIC_TOLERANCE_ONLY",
    "PUBLIC_RELATION_BROKEN",
    "UPSTREAM_STATE_UNVERIFIED",
    "DOWNSTREAM_RECONCILIATION_WITHOUT_UPSTREAM_VALIDITY",
    "COMPONENT_NOT_APPLICABLE",
    "NO_QUANT_SPECIFIC_EVIDENCE",
}
_NEXT_EVIDENCE = {
    "NO_EXTRA_RUN",
    "PAIRED_PROTECTION_REPEAT",
    "HOLD_FOR_REFINE",
    "RETIRE_CURRENT_INTEGRATION",
}


class QuantitativeProtectionReviewError(ValueError):
    """Raised when a Reviewer response violates the small QPR-1 contract."""


def _new_critical_relation_breaks(
    outcomes: Sequence[Mapping[str, object]],
) -> list[str]:
    breaks = []
    for relation in outcomes:
        if not relation.get("critical", False):
            continue
        parent = str(relation.get("parent", "UNKNOWN")).upper()
        candidate = str(relation.get("candidate", "UNKNOWN")).upper()
        if (
            candidate in _BROKEN_RELATION_OUTCOMES
            and parent not in _BROKEN_RELATION_OUTCOMES
        ):
            breaks.append(str(relation.get("name", "unnamed_relation")))
    return breaks


def _adverse_property_families(
    deltas: Mapping[str, int],
) -> list[str]:
    """Return families with more candidate failures than parent failures."""

    return sorted(name for name, delta in deltas.items() if delta > 0)


def triage_quantitative_protection(
    *,
    parent: Mapping[str, object],
    candidate: Mapping[str, object],
    provisional_margin: int,
    public_critical_relations: Sequence[Mapping[str, object]] = (),
    same_harness: bool = False,
    property_family_deltas: Mapping[str, int] | None = None,
    trace_attribution_hints: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Classify one matched quantitative protection comparison.

    ``parent`` and ``candidate`` contain official aggregate fields such as
    ``tests_passed`` and ``reward``.  A property-family delta is candidate
    failed-count minus parent failed-count, so a positive value is adverse.
    Critical relation outcomes use ordinary records with ``name``, ``critical``,
    ``parent``, and ``candidate`` fields.

    Trace hints may supply an evidence-backed ``causal_attribution`` and
    ``quantitative_diagnosis``.  They never override the score/relation gate.
    """

    family_deltas = property_family_deltas or {}
    hints = trace_attribution_hints or {}
    parent_passed = int(parent["tests_passed"])
    candidate_passed = int(candidate["tests_passed"])
    passed_delta = candidate_passed - parent_passed
    reward_delta = float(candidate.get("reward", 0.0)) - float(
        parent.get("reward", 0.0)
    )
    new_relation_breaks = _new_critical_relation_breaks(
        public_critical_relations
    )
    adverse_families = _adverse_property_families(family_deltas)

    evidence = {
        "passed_property_delta": passed_delta,
        "reward_delta": reward_delta,
        "provisional_margin": provisional_margin,
        "new_critical_relation_breaks": new_relation_breaks,
        "adverse_property_families": adverse_families,
        "same_harness": same_harness,
    }

    if same_harness:
        return {
            "verdict": "INCONCLUSIVE",
            "outcome_severity": "WITHIN_PROVISIONAL_VARIABILITY"
            if abs(passed_delta) <= provisional_margin
            else "UNRESOLVED",
            "causal_attribution": "WORKER_TRAJECTORY",
            "quantitative_diagnosis": "NO_QUANT_SPECIFIC_EVIDENCE",
            "next_evidence": "NO_EXTRA_RUN",
            "evidence": evidence,
        }

    causal_attribution = str(
        hints.get("causal_attribution", "UNRESOLVED")
    )
    hinted_diagnosis = str(
        hints.get("quantitative_diagnosis", "NO_QUANT_SPECIFIC_EVIDENCE")
    )

    if new_relation_breaks:
        return {
            "verdict": "FAIL",
            "outcome_severity": "MEANINGFUL_CANDIDATE_REGRESSION",
            "causal_attribution": causal_attribution,
            "quantitative_diagnosis": "PUBLIC_RELATION_BROKEN",
            "next_evidence": "HOLD_FOR_REFINE",
            "evidence": evidence,
        }

    if -passed_delta > provisional_margin:
        return {
            "verdict": "FAIL",
            "outcome_severity": "MEANINGFUL_CANDIDATE_REGRESSION",
            "causal_attribution": causal_attribution,
            "quantitative_diagnosis": hinted_diagnosis,
            "next_evidence": "HOLD_FOR_REFINE",
            "evidence": evidence,
        }

    aggregate_non_regression = passed_delta >= 0 and reward_delta >= 0
    if aggregate_non_regression and not adverse_families:
        return {
            "verdict": "PASS",
            "outcome_severity": "WITHIN_PROVISIONAL_VARIABILITY",
            "causal_attribution": causal_attribution,
            "quantitative_diagnosis": hinted_diagnosis,
            "next_evidence": "NO_EXTRA_RUN",
            "evidence": evidence,
        }

    return {
        "verdict": "INCONCLUSIVE",
        "outcome_severity": "UNRESOLVED",
        "causal_attribution": causal_attribution,
        "quantitative_diagnosis": hinted_diagnosis,
        "next_evidence": "PAIRED_PROTECTION_REPEAT",
        "evidence": evidence,
    }


def build_quantitative_regression_reviewer_prompt(
    cases: Sequence[Mapping[str, object]],
) -> str:
    """Build one answer-free prompt that reviews all supplied evidence cards."""

    case_payload = json.dumps(
        list(cases), indent=2, ensure_ascii=False, sort_keys=True
    )
    return f"""You are the Quantitative Regression Reviewer inside a harness-evolution experiment.

Review all evidence cards in one response. This is an answer-free protection
review: use only the public task relations, matched aggregate observations,
property-family changes, harness diff, and runtime trace excerpts present in
the cards. You do not have checker answers, expected values, hidden tests, a
reference solution, or sealed outcomes. Do not infer or request them.

Your role is evidence classification, not candidate selection. You cannot
PROMOTE a harness, change the current parent, or repair a task artifact. The
fixed controller owns those actions. Distinguish ordinary Worker trajectory
variation from a structural quantitative-state break and from unsafe
harness--Worker interaction. A same-harness fluctuation inside a provisional
margin is not by itself a capability regression. Conversely, the Main-0B
35-to-29 protection drop is outside its three-property margin and has
structural trace evidence; it must not be relabeled as mere numerical noise.

Return one plain JSON object with schema_version=1 and a `reviews` array. Return
exactly one review for each case_id, in the supplied order, and no other cases.
Each review must contain:

- case_id;
- outcome_severity: one of {sorted(_OUTCOME_SEVERITIES)};
- causal_attribution: one of {sorted(_CAUSAL_ATTRIBUTIONS)};
- quantitative_diagnosis: one of {sorted(_QUANTITATIVE_DIAGNOSES)};
- next_evidence: one of {sorted(_NEXT_EVIDENCE)}; and
- evidence_refs: a non-empty list of evidence_ref strings copied from that card.

Do not add a PROMOTE or ROLLBACK field. `HOLD_FOR_REFINE` rejects the current
integration while retaining its component evidence; it is not promotion.

Evidence cards:
{case_payload}
"""


def validate_quantitative_regression_review(
    payload: Mapping[str, object],
    expected_case_ids: Sequence[str],
) -> dict[str, object]:
    """Validate the small, ordinary-JSON QPR-1 Reviewer response."""

    if payload.get("schema_version") != 1:
        raise QuantitativeProtectionReviewError("schema_version must be 1")
    reviews = payload.get("reviews")
    if not isinstance(reviews, list):
        raise QuantitativeProtectionReviewError("reviews must be a list")
    case_ids = [review.get("case_id") for review in reviews]
    if case_ids != list(expected_case_ids):
        raise QuantitativeProtectionReviewError(
            "Reviewer case IDs must exactly match the requested cases"
        )

    allowed = {
        "outcome_severity": _OUTCOME_SEVERITIES,
        "causal_attribution": _CAUSAL_ATTRIBUTIONS,
        "quantitative_diagnosis": _QUANTITATIVE_DIAGNOSES,
        "next_evidence": _NEXT_EVIDENCE,
    }
    for review in reviews:
        for field, values in allowed.items():
            if review.get(field) not in values:
                raise QuantitativeProtectionReviewError(
                    f"invalid {field} for {review.get('case_id')}"
                )
        evidence_refs = review.get("evidence_refs")
        if not isinstance(evidence_refs, list) or not evidence_refs or not all(
            isinstance(ref, str) and ref for ref in evidence_refs
        ):
            raise QuantitativeProtectionReviewError(
                f"evidence_refs required for {review.get('case_id')}"
            )
    return dict(payload)


def run_quantitative_regression_review(
    cases: Sequence[Mapping[str, object]],
    *,
    complete: Callable[[str], str],
) -> dict[str, object]:
    """Make one batched Reviewer call and validate its JSON response."""

    prompt = build_quantitative_regression_reviewer_prompt(cases)
    raw = complete(prompt).strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.splitlines()[1:-1]).strip()
    payload = json.loads(raw)
    expected_case_ids = [str(case["case_id"]) for case in cases]
    return validate_quantitative_regression_review(payload, expected_case_ids)
