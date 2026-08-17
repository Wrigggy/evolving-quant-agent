import json

import pytest

from qea.quantcodeeval_optimization import (
    QuantCodeEvalOptimizationError,
    assess_transfer_eligibility,
    build_quantcodeeval_optimization_diagnostic,
    extend_quantcodeeval_optimization_diagnostic,
)


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _signature(task, *, family="task_conditioned_formula_reconciliation"):
    return {
        "task_id": task,
        "mechanism_family": family,
        "semantic_state": "paper formula and return-scale state",
        "pipeline_phase": "estimation through end-to-end reconciliation",
        "observable": "intermediate formula and final metrics disagree",
        "observed_failure": True,
        "property_ids": ["B5", "A10"],
    }


def test_builds_item_timeline_for_evolver_only(tmp_path):
    manifest = tmp_path / "manifest.json"
    _write(
        manifest,
        {
            "task_id": "T26",
            "checkers": [
                {
                    "property_id": "A3",
                    "property_name": "no_future_data_access",
                    "task_function": "select_gamma_by_cv",
                },
                {
                    "property_id": "B5",
                    "property_name": "cv_objective_cross_sectional_oos_r2",
                    "task_function": "select_gamma_by_cv",
                },
            ],
        },
    )
    h0 = tmp_path / "h0.json"
    candidate = tmp_path / "candidate.json"
    _write(
        h0,
        {
            "total": 2,
            "pass": 0,
            "fail": 2,
            "results": [
                {
                    "property_id": "A3",
                    "verdict": "FAIL",
                    "detail": "future rows affect CV",
                    "evidence": "training gate absent",
                },
                {
                    "property_id": "B5",
                    "verdict": "FAIL",
                    "detail": "metric formula absent",
                    "evidence": "plain MSE used",
                },
            ],
        },
    )
    _write(
        candidate,
        {
            "total": 2,
            "pass": 1,
            "fail": 1,
            "results": [
                {"property_id": "A3", "verdict": "PASS", "detail": "causal CV"},
                {
                    "property_id": "B5",
                    "verdict": "FAIL",
                    "detail": "metric formula still absent",
                },
            ],
        },
    )

    result = build_quantcodeeval_optimization_diagnostic(
        destination=tmp_path / "optimization-diagnostic.json",
        task_id="T26",
        attempts=[
            {"label": "h0", "role": "baseline", "ctrf_path": str(h0)},
            {
                "label": "candidate-1",
                "role": "candidate",
                "ctrf_path": str(candidate),
                "candidate_change": "independent clause audit",
            },
        ],
        rubric_manifest_path=manifest,
        rubric_overrides={
            "B5": {
                "criterion": "CV uses the declared objective",
                "expected_behavior": "use the public HJ-metric residual formula",
                "public_contract_refs": ["R6"],
            }
        },
        failure_signatures=[_signature("T26")],
    )

    diagnostic = json.loads(
        (tmp_path / "optimization-diagnostic.json").read_text()
    )
    assert result["attempt_count"] == 2
    assert diagnostic["visibility"] == "evolver_only"
    assert diagnostic["worker_visible"] is False
    assert "COMPOSE" in diagnostic["evolver_assignment"]["choose"]
    by_id = {row["property_id"]: row for row in diagnostic["rubric_items"]}
    assert [row["verdict"] for row in by_id["A3"]["observations"]] == [
        "FAIL",
        "PASS",
    ]
    assert by_id["B5"]["expected_behavior"].startswith("use the public")
    assert diagnostic["evolver_assignment"]["failure_signature_required_for_act"]


def test_transfer_requires_observed_destination_failure_in_same_mechanism():
    component = _signature("T26")
    eligible = assess_transfer_eligibility(
        component_signature=component,
        source_signatures=[_signature("T26")],
        destination_signatures=[_signature("T27")],
    )
    unrelated = assess_transfer_eligibility(
        component_signature=component,
        source_signatures=[_signature("T26")],
        destination_signatures=[
            _signature("T27", family="artifact_delivery_recovery")
        ],
    )

    assert eligible["candidate_run_allowed"] is True
    assert len(eligible["destination_matches"]) == 1
    assert unrelated["candidate_run_allowed"] is False
    assert unrelated["unmatched_destination_may_be_protection_only"] is True


def test_extends_answer_rich_timeline_without_rewriting_prior_attempts(tmp_path):
    base = tmp_path / "base-diagnostic.json"
    _write(
        base,
        {
            "schema_version": 1,
            "benchmark": "quantcodeeval",
            "task_id": "T26",
            "feedback_mode": "answer_rich_evolver",
            "visibility": "evolver_only",
            "worker_visible": False,
            "attempts": [
                {
                    "label": "h0",
                    "role": "baseline",
                    "score": {"passed": 13, "failed": 4, "total": 17},
                }
            ],
            "rubric_items": [
                {
                    "property_id": "A10",
                    "criterion": "end-to-end numeric identity",
                    "expected_behavior": "match the declared final metrics",
                    "observations": [
                        {
                            "attempt": "h0",
                            "role": "baseline",
                            "verdict": "FAIL",
                            "observed_behavior": "large mismatch",
                            "checker_evidence": "relative error 0.4",
                        }
                    ],
                },
                {
                    "property_id": "B5",
                    "criterion": "declared CV objective",
                    "expected_behavior": "use inverse covariance weighting",
                    "observations": [
                        {
                            "attempt": "h0",
                            "role": "baseline",
                            "verdict": "FAIL",
                            "observed_behavior": "plain MSE",
                            "checker_evidence": "objective mismatch",
                        }
                    ],
                },
            ],
            "candidate_changes": [],
            "observed_failure_signatures": [_signature("T26")],
            "evolver_assignment": {"choose": ["REFINE", "ABSTAIN"]},
        },
    )
    repeat = tmp_path / "repeat.json"
    _write(
        repeat,
        {
            "total": 2,
            "pass": 1,
            "fail": 1,
            "results": [
                {
                    "property_id": "A10",
                    "verdict": "FAIL",
                    "detail": "relative error 0.08645",
                    "evidence": "worst=sharpe",
                },
                {
                    "property_id": "B5",
                    "verdict": "PASS",
                    "detail": "declared objective realized",
                    "evidence": "inverse covariance pattern present",
                },
            ],
        },
    )

    result = extend_quantcodeeval_optimization_diagnostic(
        destination=tmp_path / "extended.json",
        base_diagnostic_path=base,
        attempts=[
            {
                "label": "candidate-repeat-16-of-17",
                "role": "independent_repeat",
                "ctrf_path": str(repeat),
                "candidate_change": "quant-contract auditor",
            }
        ],
        candidate_changes=[
            {
                "label": "quant-contract-auditor",
                "components": ["tools", "agent_config", "systemprompt"],
            }
        ],
    )

    extended = json.loads((tmp_path / "extended.json").read_text())
    by_id = {row["property_id"]: row for row in extended["rubric_items"]}
    assert result["prior_attempt_count"] == 1
    assert result["added_attempt_count"] == 1
    assert [row["attempt"] for row in by_id["A10"]["observations"]] == [
        "h0",
        "candidate-repeat-16-of-17",
    ]
    assert by_id["A10"]["observations"][-1]["observed_behavior"] == (
        "relative error 0.08645"
    )
    assert by_id["B5"]["observations"][-1]["verdict"] == "PASS"
    assert "COMPOSE" in extended["evolver_assignment"]["choose"]
    assert json.loads(base.read_text())["attempts"] == [
        {
            "label": "h0",
            "role": "baseline",
            "score": {"passed": 13, "failed": 4, "total": 17},
        }
    ]


def test_extension_accepts_new_analysis_without_a_new_scored_attempt(tmp_path):
    base = tmp_path / "base.json"
    _write(
        base,
        {
            "schema_version": 1,
            "task_id": "T26",
            "feedback_mode": "answer_rich_evolver",
            "visibility": "evolver_only",
            "worker_visible": False,
            "attempts": [{"label": "r1", "role": "candidate"}],
            "rubric_items": [
                {"property_id": "A10", "observations": []}
            ],
            "candidate_changes": [],
            "observed_failure_signatures": [],
            "evolver_assignment": {},
        },
    )

    result = extend_quantcodeeval_optimization_diagnostic(
        destination=tmp_path / "extended.json",
        base_diagnostic_path=base,
        attempts=[],
        candidate_changes=[
            {
                "component": "trusted_numeric_localization",
                "runtime_outcome": "grid resolution changes the selected parameter",
            }
        ],
        failure_signatures=[
            _signature("T26", family="hyperparameter_resolution")
        ],
    )

    extended = json.loads((tmp_path / "extended.json").read_text())
    assert result["added_attempt_count"] == 0
    assert result["added_candidate_change_count"] == 1
    assert result["added_failure_signature_count"] == 1
    assert extended["attempts"] == [{"label": "r1", "role": "candidate"}]
    assert extended["candidate_changes"][-1]["component"] == (
        "trusted_numeric_localization"
    )
    assert extended["observed_failure_signatures"][-1][
        "mechanism_family"
    ] == "hyperparameter_resolution"


def test_extension_rejects_when_it_adds_no_evidence(tmp_path):
    base = tmp_path / "base.json"
    _write(
        base,
        {
            "schema_version": 1,
            "task_id": "T26",
            "feedback_mode": "answer_rich_evolver",
            "visibility": "evolver_only",
            "worker_visible": False,
            "attempts": [{"label": "r1", "role": "candidate"}],
            "rubric_items": [
                {"property_id": "A10", "observations": []}
            ],
            "candidate_changes": [],
            "observed_failure_signatures": [],
            "evolver_assignment": {},
        },
    )

    with pytest.raises(QuantCodeEvalOptimizationError, match="analysis record"):
        extend_quantcodeeval_optimization_diagnostic(
            destination=tmp_path / "extended.json",
            base_diagnostic_path=base,
            attempts=[],
        )


def test_extension_rejects_a_duplicate_attempt_label(tmp_path):
    base = tmp_path / "base.json"
    _write(
        base,
        {
            "schema_version": 1,
            "task_id": "T26",
            "feedback_mode": "answer_rich_evolver",
            "visibility": "evolver_only",
            "worker_visible": False,
            "attempts": [{"label": "r2", "role": "candidate"}],
            "rubric_items": [
                {"property_id": "A10", "observations": []}
            ],
            "candidate_changes": [],
            "observed_failure_signatures": [],
            "evolver_assignment": {},
        },
    )
    ctrf = tmp_path / "ctrf.json"
    _write(
        ctrf,
        {
            "results": [
                {"property_id": "A10", "verdict": "FAIL"}
            ]
        },
    )

    with pytest.raises(QuantCodeEvalOptimizationError, match="duplicate attempt"):
        extend_quantcodeeval_optimization_diagnostic(
            destination=tmp_path / "extended.json",
            base_diagnostic_path=base,
            attempts=[
                {"label": "r2", "role": "candidate", "ctrf_path": str(ctrf)}
            ],
        )
