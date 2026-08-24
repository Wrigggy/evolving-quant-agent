from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "data/breadth/QF_QRS_MINI_SCHEDULER_CANARY_PLAN.json"


def _plan() -> dict[str, object]:
    return json.loads(PLAN.read_text(encoding="utf-8"))


def test_mini_canary_banks_four_tasks_but_authorizes_only_first_panel() -> None:
    plan = _plan()
    tasks = [task for panel in plan["development_panels"] for task in panel["task_ids"]]
    execution = plan["canary_execution"]
    assert len(tasks) == len(set(tasks)) == 4
    assert execution["stop_after_panel"] == 1
    assert execution["actual_max_h0_bank_cells"] == 4
    assert execution["actual_max_panel_matched_cells"] == 12
    assert execution["actual_max_qfbench_cells"] == 16
    assert execution["actual_evolver_calls"] == execution["actual_reviewer_calls"] == 1
    assert execution["sealed_dispatch_authorized"] is False
    assert execution["later_panel_dispatch_authorized"] is False
    assert execution["main_reuse_allowed"] is False


def test_each_family_has_one_anchor_and_panel_one_is_cross_family() -> None:
    plan = _plan()
    panels = plan["development_panels"]
    anchors = plan["cross_family_workflow_evidence"]["anchor_task_by_family"]
    assert set(anchors) == {panel["family"] for panel in panels}
    for panel in panels:
        assert anchors[panel["family"]] in panel["task_ids"]
    panel_one_visible = set(panels[0]["task_ids"]) | {
        task for family, task in anchors.items() if family != panels[0]["family"]
    }
    assert len(panel_one_visible) == 3


def test_full_method_counts_are_consistent_while_live_cap_is_sixteen() -> None:
    plan = _plan()
    limits = plan["limits"]
    panel_sizes = [len(panel["task_ids"]) for panel in plan["development_panels"]]
    panel_cells = sum(4 * (size + 2) for size in panel_sizes)
    assert panel_cells == 40
    assert limits["qfbench_primary_cells"] == 4 + panel_cells + 8 == 52
    assert limits["canary_incremental_cap"]["qfbench_cells"] == 16
    assert limits["paid_or_remote_authority"] is False


def test_live_pass_requires_reviewed_snapshot_blind_worker_and_zero_work_resume() -> None:
    required = _plan()["required_live_outcomes"]
    assert "overall Review PASS" in required["pass_side"]
    assert "dispatched unchanged" in required["pass_side"]
    assert "optimize_only_sources is empty" in required["answer_boundary"]
    assert "zero-work resume" in required["resume"]
    assert "does not satisfy" in required["terminal"]
