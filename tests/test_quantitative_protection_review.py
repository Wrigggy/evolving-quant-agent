import json

import pytest

from qea.quantitative_protection_review import (
    QuantitativeProtectionReviewError,
    build_quantitative_regression_reviewer_prompt,
    run_quantitative_regression_review,
    triage_quantitative_protection,
    validate_quantitative_regression_review,
)


def _score(passed, reward):
    return {"tests_passed": passed, "reward": reward}


def test_same_harness_variation_is_not_candidate_degradation():
    result = triage_quantitative_protection(
        parent=_score(38, 0.96),
        candidate=_score(35, 0.90),
        provisional_margin=3,
        same_harness=True,
    )

    assert result["verdict"] == "INCONCLUSIVE"
    assert result["outcome_severity"] == "WITHIN_PROVISIONAL_VARIABILITY"
    assert result["causal_attribution"] == "WORKER_TRAJECTORY"
    assert result["next_evidence"] == "NO_EXTRA_RUN"


def test_small_candidate_drop_requests_one_paired_repeat():
    result = triage_quantitative_protection(
        parent=_score(35, 0.90),
        candidate=_score(34, 0.88),
        provisional_margin=3,
        property_family_deltas={"barrier": 1},
    )

    assert result["verdict"] == "INCONCLUSIVE"
    assert result["outcome_severity"] == "UNRESOLVED"
    assert result["causal_attribution"] == "UNRESOLVED"
    assert result["next_evidence"] == "PAIRED_PROTECTION_REPEAT"


def test_main0b_structural_regression_holds_candidate_for_refinement():
    result = triage_quantitative_protection(
        parent=_score(35, 0.90),
        candidate=_score(29, 0.768857),
        provisional_margin=3,
        public_critical_relations=[{
            "name": "forward_parity",
            "critical": True,
            "parent": "PASS",
            "candidate": "UNVERIFIED",
        }],
        property_family_deltas={
            "surface_nodes": 2,
            "call_surface": 2,
            "local_vol": 0,
            "barrier": 0,
        },
        trace_attribution_hints={
            "causal_attribution": "HARNESS_WORKER_INTERACTION",
            "quantitative_diagnosis": "UPSTREAM_STATE_UNVERIFIED",
        },
    )

    assert result["verdict"] == "FAIL"
    assert result["outcome_severity"] == "MEANINGFUL_CANDIDATE_REGRESSION"
    assert result["causal_attribution"] == "HARNESS_WORKER_INTERACTION"
    assert result["quantitative_diagnosis"] == "UPSTREAM_STATE_UNVERIFIED"
    assert result["next_evidence"] == "HOLD_FOR_REFINE"


def test_equal_aggregate_cannot_hide_new_critical_relation_break():
    result = triage_quantitative_protection(
        parent=_score(38, 0.96),
        candidate=_score(38, 0.96),
        provisional_margin=3,
        public_critical_relations=[{
            "name": "unit_and_forward_parity",
            "critical": True,
            "parent": "PASS",
            "candidate": "FAIL",
        }],
    )

    assert result["verdict"] == "FAIL"
    assert result["quantitative_diagnosis"] == "PUBLIC_RELATION_BROKEN"
    assert result["next_evidence"] == "HOLD_FOR_REFINE"
    assert result["evidence"]["new_critical_relation_breaks"] == [
        "unit_and_forward_parity"
    ]
    json.dumps(result)


def _review(case_id, severity, attribution, diagnosis, next_evidence):
    return {
        "case_id": case_id,
        "outcome_severity": severity,
        "causal_attribution": attribution,
        "quantitative_diagnosis": diagnosis,
        "next_evidence": next_evidence,
        "evidence_refs": [f"evidence:{case_id}"],
    }


def test_batched_reviewer_uses_one_answer_free_call_and_validates_response():
    cases = [
        {"case_id": "h0-variation", "evidence_ref": "evidence:h0-variation"},
        {"case_id": "small-drop", "evidence_ref": "evidence:small-drop"},
        {"case_id": "main0b", "evidence_ref": "evidence:main0b"},
        {"case_id": "critical-break", "evidence_ref": "evidence:critical-break"},
    ]
    payload = {
        "schema_version": 1,
        "reviews": [
            _review(
                "h0-variation",
                "WITHIN_PROVISIONAL_VARIABILITY",
                "WORKER_TRAJECTORY",
                "NO_QUANT_SPECIFIC_EVIDENCE",
                "NO_EXTRA_RUN",
            ),
            _review(
                "small-drop",
                "UNRESOLVED",
                "UNRESOLVED",
                "NO_QUANT_SPECIFIC_EVIDENCE",
                "PAIRED_PROTECTION_REPEAT",
            ),
            _review(
                "main0b",
                "MEANINGFUL_CANDIDATE_REGRESSION",
                "HARNESS_WORKER_INTERACTION",
                "UPSTREAM_STATE_UNVERIFIED",
                "HOLD_FOR_REFINE",
            ),
            _review(
                "critical-break",
                "MEANINGFUL_CANDIDATE_REGRESSION",
                "UNRESOLVED",
                "PUBLIC_RELATION_BROKEN",
                "HOLD_FOR_REFINE",
            ),
        ],
    }
    prompts = []

    def complete(prompt):
        prompts.append(prompt)
        return json.dumps(payload)

    result = run_quantitative_regression_review(cases, complete=complete)

    assert result == payload
    assert len(prompts) == 1
    assert "answer-free protection" in prompts[0]
    assert "cannot\nPROMOTE" in prompts[0]
    assert "35-to-29" in prompts[0]


def test_reviewer_rejects_an_unrequested_case_id():
    payload = {
        "schema_version": 1,
        "reviews": [
            _review(
                "different-case",
                "UNRESOLVED",
                "UNRESOLVED",
                "NO_QUANT_SPECIFIC_EVIDENCE",
                "NO_EXTRA_RUN",
            )
        ],
    }

    with pytest.raises(QuantitativeProtectionReviewError, match="case IDs"):
        validate_quantitative_regression_review(payload, ["expected-case"])


def test_reviewer_prompt_forbids_answer_and_promotion_authority():
    prompt = build_quantitative_regression_reviewer_prompt([
        {"case_id": "one", "evidence_ref": "evidence:one"}
    ])

    assert "checker answers" in prompt
    assert "fixed controller owns those actions" in prompt
