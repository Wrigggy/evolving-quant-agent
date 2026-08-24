from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "data/breadth/QF_PRIMITIVE_H0_PROTOCOL_CANARY_PLAN.json"


def _plan() -> dict[str, object]:
    return json.loads(PLAN.read_text(encoding="utf-8"))


def test_protocol_canary_is_three_excluded_primitive_cells_only() -> None:
    plan = _plan()
    scope = plan["scope"]
    assert scope["task_ids"] == [
        "13f-amendment-aware-crowding",
        "fx-forward-cross-rate",
        "swap-curve-bootstrap-ois",
    ]
    assert scope["task_role"] == "construct_calibration_excluded_from_main"
    assert scope["worker_sessions"] == scope["official_verifier_executions"] == 3
    assert scope["evolver_calls"] == scope["reviewer_calls"] == 0
    assert scope["candidate_sessions"] == 0
    assert scope["sealed_tasks_used"] is False


def test_launch_uses_exact_primitive_worker_and_single_arm() -> None:
    plan = _plan()
    argv = plan["launch_argv"]
    assert argv.count("--arm") == 1
    assert argv.count("--task-id") == 3
    assert argv[argv.index("--seed-worker") + 1] == plan["run"]["seed_worker"]
    assert argv[argv.index("--arm") + 1] == (
        "quant-h0-s6-primitive-v1=" + plan["run"]["arm_worker"]
    )
    assert argv[-1] == "--approve-external-run"


def test_protocol_gate_is_score_independent_and_strict_schema_v2() -> None:
    plan = _plan()
    gate = plan["protocol_gate"]
    assert gate["required_schema_version"] == 2
    assert gate["required_stage_ids"] == ["S1", "S2", "S3", "S4", "S5", "S6"]
    assert "exactly one S6 COMPLETE" in gate["per_task_rule"]
    assert "Scores are retained descriptively but never determine" in gate[
        "campaign_rule"
    ]
    assert [value["decision"] for value in plan["terminal_decisions"]] == [
        "PRIMITIVE_PROTOCOL_PASS",
        "STOP_CANARY",
    ]


def test_canary_has_hard_bounds_and_no_follow_on_dispatch() -> None:
    limits = _plan()["limits"]
    assert limits["max_worker_sessions"] == 3
    assert limits["max_official_verifier_executions"] == 3
    assert limits["max_completed_requests"] == 120
    assert limits["max_total_tokens"] == 8_000_000
    assert limits["provider_cost_usd"] == 0.40
    assert limits["wall_time_seconds"] == 7200
    assert limits["no_follow_on_dispatch_in_this_plan"] is True
