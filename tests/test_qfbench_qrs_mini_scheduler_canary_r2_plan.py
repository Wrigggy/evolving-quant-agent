from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
R1_PLAN = ROOT / "data/breadth/QF_QRS_MINI_SCHEDULER_CANARY_PLAN.json"
R2_PLAN = (
    ROOT / "data/breadth/QF_QRS_MINI_SCHEDULER_CANARY_R2_PLAN.json"
)


def _read(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _task_layout(plan: dict[str, object]) -> list[tuple[str, tuple[str, ...]]]:
    return [
        (str(panel["family"]), tuple(panel["task_ids"]))
        for panel in plan["development_panels"]
    ]


def test_r2_is_new_setup_recovery_not_r1_resume_or_repeat() -> None:
    r2 = _read(R2_PLAN)
    recovery = r2["setup_recovery"]

    assert r2["experiment_id"] == "qf-qrs-mini-scheduler-canary-20260825-r2"
    assert r2["canary_execution"]["scheduler_run_id"] == r2["experiment_id"]
    assert recovery["kind"] == "separately_frozen_setup_recovery_not_repeat"
    assert recovery["antecedent_run_id"] == (
        "qf-qrs-mini-scheduler-canary-20260824-r1"
    )
    assert recovery["antecedent_terminal"] == "STOP_PANEL"
    assert "R1 H0 trajectories" in recovery["reuse_forbidden"]
    assert "R1 repeat" in r2["claim_boundary"]


def test_r2_keeps_r1_tasks_anchors_sealed_partition_and_caps() -> None:
    r1 = _read(R1_PLAN)
    r2 = _read(R2_PLAN)

    assert _task_layout(r2) == _task_layout(r1)
    assert r2["cross_family_workflow_evidence"]["anchor_task_by_family"] == (
        r1["cross_family_workflow_evidence"]["anchor_task_by_family"]
    )
    assert r2["sealed_main_tasks"] == r1["sealed_main_tasks"]
    assert r2["limits"] == r1["limits"]
    assert r2["canary_execution"]["stop_after_panel"] == 1
    assert r2["canary_execution"]["actual_max_qfbench_cells"] == 16


def test_r2_discloses_only_observed_setup_repairs() -> None:
    r2 = _read(R2_PLAN)
    changes = " ".join(r2["setup_recovery"]["only_engineering_changes"])

    assert "decision_protocol quant_property_v2" in changes
    assert "answer_free_global_h0_trajectory_bank_v1" in changes
    assert "allowed_candidate_paths" in changes
    assert "same stop_after_panel resume" in changes
    assert "task answer" not in changes.casefold()
    assert "score" not in changes.casefold()


def test_r2_requires_real_pass_to_blind_worker_and_zero_work_resume() -> None:
    required = _read(R2_PLAN)["required_live_outcomes"]

    assert "overall Review PASS" in required["pass_side"]
    assert "dispatched unchanged" in required["pass_side"]
    assert "optimize_only_sources is empty" in required["answer_boundary"]
    assert "same stop_after_panel zero-work resume" in required["resume"]
    assert "creates no new action" in required["resume"]
    assert "does not satisfy" in required["terminal"]
