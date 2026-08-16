import json

from qea.quantcodeeval_optimization import (
    assess_transfer_eligibility,
    build_quantcodeeval_optimization_diagnostic,
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
