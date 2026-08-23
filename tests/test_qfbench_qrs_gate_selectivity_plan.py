from __future__ import annotations

import json
from pathlib import Path

from scripts.run_qfbench_lineage_controller import (
    build_child_argv,
    build_proposal_argv,
)


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = (
    ROOT / "data/breadth/QF_QRS_COORDINATED_GATE_SELECTIVITY_PLAN.json"
)


def _plan() -> dict[str, object]:
    return json.loads(PLAN_PATH.read_text())


def _case(plan: dict[str, object], case_id: str) -> dict[str, object]:
    return next(value for value in plan["cases"] if value["case_id"] == case_id)


def _arm_arguments(argv: tuple[str, ...]) -> list[str]:
    return [
        argv[index + 1]
        for index, value in enumerate(argv)
        if value == "--arm"
    ]


def test_gate_selectivity_plan_freezes_sequence_budget_and_stops() -> None:
    plan = _plan()

    assert plan["status"] == "frozen_not_run"
    assert plan["orchestration"] == "manual_existing_runners_only"
    assert plan["code_under_test"]["commit"] == "df5342e"
    assert [step["gate"] for step in plan["execution_sequence"]] == [
        "G+",
        "G-",
        "T",
        "R",
        "P",
    ]
    assert [step["order"] for step in plan["execution_sequence"]] == [
        1,
        2,
        3,
        4,
        5,
    ]
    assert [step.get("optional", False) for step in plan["execution_sequence"]] == [
        False,
        False,
        False,
        True,
        True,
    ]
    assert "ABSTAIN" in plan["execution_sequence"][0]["stop_when"]
    assert "ACT" in plan["execution_sequence"][1]["stop_when"]
    assert "no strict official gain" in plan["execution_sequence"][2][
        "stop_when"
    ]

    limits = plan["limits"]
    assert limits["max_evolver_proposals"] == 2
    assert limits["max_new_parent_worker_sessions"] == 0
    assert limits["required_path"] == {
        "max_candidate_worker_sessions": 1,
        "max_candidate_verifier_executions": 1,
        "max_completed_requests": 100,
        "max_total_tokens": 9000000,
        "provider_cost_usd": 0.35,
        "wall_time_hours": 3,
    }
    assert limits["conditional_full_path"] == {
        "max_candidate_worker_sessions": 3,
        "max_candidate_verifier_executions": 3,
        "max_completed_requests": 180,
        "max_total_tokens": 15000000,
        "provider_cost_usd": 0.6,
        "wall_time_hours": 6,
    }


def test_gate_selectivity_plan_reuses_final_h0_without_exposing_r4() -> None:
    plan = _plan()
    positive = _case(plan, "localvol-positive")
    negative = _case(plan, "holdings-negative-control")
    frozen = plan["frozen_inputs"]

    assert positive["expected_gate_decision"] == "ACT"
    assert negative["expected_gate_decision"] == "ABSTAIN"
    assert negative["dispatch_policy"] == "proposal_only_even_if_unexpected_act"
    assert positive["lineage"]["parent"] == negative["lineage"]["parent"]
    assert positive["lineage"]["parent"] == frozen["quant_h0"]
    assert positive["lineage"]["proposal"]["evidence"] == frozen[
        "localvol_qrs_evidence"
    ]
    assert negative["lineage"]["proposal"]["evidence"] == frozen[
        "holdings_qrs_evidence"
    ]
    assert negative["lineage"]["stages"] == []

    label = plan["experimenter_only_case_label"]
    assert label["exposed_to_evolver"] is False
    proposal_inputs = {
        positive["lineage"]["proposal"]["evidence"],
        negative["lineage"]["proposal"]["evidence"],
    }
    assert proposal_inputs.isdisjoint(label["forbidden_evolver_evidence"])
    assert all("qf-a02" not in value for value in proposal_inputs)
    assert "No R4 result" in plan["answer_boundary"]


def test_gate_selectivity_proposal_argv_uses_exact_ids_and_frozen_inputs() -> None:
    plan = _plan()
    expected = {
        "localvol-positive": (
            "qf-qrs-coordinated-gate-selectivity-20260824-r1-localvol-positive-proposal",
            plan["frozen_inputs"]["localvol_qrs_evidence"],
        ),
        "holdings-negative-control": (
            "qf-qrs-coordinated-gate-selectivity-20260824-r1-holdings-negative-proposal",
            plan["frozen_inputs"]["holdings_qrs_evidence"],
        ),
    }

    for case_id, (run_id, evidence) in expected.items():
        lineage = _case(plan, case_id)["lineage"]
        argv = build_proposal_argv(
            plan,
            lineage,
            lineage["proposal"],
            approve_external_run=True,
        )
        assert argv[argv.index("--run-id") + 1] == run_id
        assert argv[argv.index("--backbone") + 1] == plan["frozen_inputs"][
            "quant_h0"
        ]["worker_dir"]
        assert argv[argv.index("--evidence") + 1] == evidence
        assert argv[argv.index("--arm") + 1] == "quant-state"
        assert argv[argv.index("--reasoning-effort") + 1] == "high"
        assert argv[1].startswith(plan["runtime"]["source_root"])


def test_gate_selectivity_candidate_argv_is_candidate_only_and_conditional() -> None:
    plan = _plan()
    lineage = _case(plan, "localvol-positive")["lineage"]
    active = {
        **lineage,
        "candidate": {
            "version": lineage["proposal"]["candidate_version"],
            "worker_dir": "/candidate/qf-qrs-gate-selectivity-localvol-c1",
        },
    }
    expected = {
        "target": (
            "qf-qrs-coordinated-gate-selectivity-20260824-r1-localvol-target",
            "dupire-local-vol",
            "main0b-localvol-target-parent-20260823-r1",
        ),
        "repeat": (
            "qf-qrs-coordinated-gate-selectivity-20260824-r1-localvol-repeat",
            "dupire-local-vol",
            "main0b-localvol-repeat-parent-20260823-r1",
        ),
        "protection": (
            "qf-qrs-coordinated-gate-selectivity-20260824-r1-localvol-protection",
            "localvol-barrier",
            "main0b-localvol-protection-parent-20260823-r1",
        ),
    }

    for stage in lineage["stages"]:
        run_id, task_id, reference_id = expected[stage["name"]]
        assert stage["selection_reference"]["id"] == reference_id
        assert stage["selection_reference"]["reference_version"] == "quant-h0"
        assert stage["selection_reference"]["worker_budget"] == "normal"
        assert stage["selection_reference"]["worker_route"] == (
            "deepseek-v4-flash-main0"
        )

        argv = build_child_argv(
            plan,
            active,
            stage,
            approve_external_run=True,
        )
        assert argv[argv.index("--run-id") + 1] == run_id
        assert argv[argv.index("--task-id") + 1] == task_id
        assert argv[argv.index("--seed-worker") + 1] == lineage["parent"][
            "worker_dir"
        ]
        assert _arm_arguments(argv) == [
            "quant-state-gate-c1=/candidate/qf-qrs-gate-selectivity-localvol-c1"
        ]

    target = lineage["stages"][0]
    assert target["selection_reference"]["tests_passed"] == 66
    assert target["selection_reference"]["tests_total"] == 68
    assert target["selection_reference"]["reward"] == 0.0
    assert lineage["repeat_consistency_policy"] == (
        "resolved_property_footprint_v1"
    )
