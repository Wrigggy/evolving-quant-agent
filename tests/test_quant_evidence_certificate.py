from __future__ import annotations

import json
from pathlib import Path

import pytest

from qea.quant_evidence_certificate import (
    QuantEvidenceCertificateError,
    load_quant_evidence_cases,
    run_reviewer_arm,
    summarize_qec1,
    validate_quant_evidence_certificate,
)


CASES = Path("data/quant_evidence_certificate_canary/cases.json")


def _response(payload):
    return json.dumps(payload)


def test_certificate_accepts_one_task_supported_form():
    payload = validate_quant_evidence_certificate(
        {
            "schema_version": 1,
            "applicability": "applicable",
            "evidence_refs": ["evidence:1"],
            "alternative_explanations": ["scale", "formula"],
            "discriminating_observation": "normalization closes the residual",
            "semantic_coordinates": {"quote": "percent", "compute": "decimal"},
        }
    )
    assert payload["applicability"] == "applicable"


def test_applicable_certificate_needs_quantitative_evidence_form():
    with pytest.raises(QuantEvidenceCertificateError, match="evidence form"):
        validate_quant_evidence_certificate(
            {
                "schema_version": 1,
                "applicability": "applicable",
                "evidence_refs": ["evidence:1"],
                "alternative_explanations": ["scale", "formula"],
                "discriminating_observation": "replay",
            }
        )


def test_case_panel_contains_two_resolvable_and_one_ambiguous_case():
    cases = load_quant_evidence_cases(CASES)
    assert len(cases) == 3
    assert sum(case.true_mechanism is not None for case in cases) == 2
    assert sum(case.true_mechanism is None for case in cases) == 1


def test_reviewer_arm_executes_declared_audit_and_scores_diagnosis():
    case = load_quant_evidence_cases(CASES)[0]
    responses = iter(
        [
            _response(
                {
                    "status": "investigate",
                    "hypotheses": [
                        {"mechanism_id": "percent_scale_mismatch", "evidence": "evidence:1"},
                        {"mechanism_id": "cashflow_formula_error", "evidence": "evidence:2"},
                    ],
                    "audit_id": "normalize-rate-and-replay",
                    "audit_prediction": "normalization distinguishes scale",
                    "candidate_component_loci": ["validator"],
                }
            ),
            _response(
                {
                    "status": "resolved",
                    "surviving_mechanisms": ["percent_scale_mismatch"],
                    "eliminated_mechanisms": ["cashflow_formula_error"],
                    "candidate_component_loci": ["validator"],
                    "observation": "normalization closes residual",
                }
            ),
        ]
    )
    result = run_reviewer_arm(case, arm="generic", complete=lambda _: next(responses))
    assert result.audit_choice_correct is True
    assert result.diagnosis_correct is True


def test_qec1_requires_improvement_without_regression():
    cases = load_quant_evidence_cases(CASES)

    def run(case, arm, *, correct):
        proposal = {
            "status": "investigate",
            "hypotheses": [],
            "audit_id": (
                case.discriminating_audit_id
                or next(iter(case.audits))
            ),
            "audit_prediction": "test",
            "candidate_component_loci": ["validator"],
        }
        if case.true_mechanism is None:
            final = {
                "status": "insufficient_contrast",
                "surviving_mechanisms": [],
                "eliminated_mechanisms": [],
                "candidate_component_loci": [],
                "observation": "insufficient",
            }
        else:
            final = {
                "status": "resolved",
                "surviving_mechanisms": [
                    case.true_mechanism if correct else case.adjacent_mechanism
                ],
                "eliminated_mechanisms": [
                    case.adjacent_mechanism if correct else case.true_mechanism
                ],
                "candidate_component_loci": ["validator"],
                "observation": "resolved",
            }
        if arm == "certificate":
            final["quant_evidence_certificate"] = {
                "schema_version": 1,
                "applicability": (
                    "insufficient_evidence"
                    if case.true_mechanism is None
                    else "applicable"
                ),
                "evidence_refs": (["evidence:1"] if case.true_mechanism else []),
                "alternative_explanations": (
                    [case.true_mechanism, case.adjacent_mechanism]
                    if case.true_mechanism
                    else []
                ),
                "discriminating_observation": "audit result",
                **(
                    {"residual_probe": {"result": "changed"}}
                    if case.true_mechanism
                    else {}
                ),
            }
        responses = iter([_response(proposal), _response(final)])
        return run_reviewer_arm(case, arm=arm, complete=lambda _: next(responses))

    results = []
    for index, case in enumerate(cases):
        results.append(run(case, "generic", correct=index != 0))
        results.append(run(case, "certificate", correct=True))
    summary = summarize_qec1(tuple(results))
    assert summary["mechanism_gate"] == "positive"
    assert summary["improved_cases"] == ["rate-scale-vs-formula"]
    assert summary["regressed_cases"] == []
