import json

from qea.qfbench_lineage import import_pilot_report, new_lineage
from scripts.run_qfbench_component_pilot import (
    _report_status,
    _worker_execution_payload,
)
from scripts.run_qfbench_lineage_controller import compose_reused_parent_report
from scripts.run_qfbench_lineage_controller import run_controller


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n")


def _attempt(root, *, outcome, turns, files, artifacts):
    attempt = root / "attempts/attempt-a"
    _write_json(
        attempt / "attempt.json",
        {
            "attempt_id": "attempt-a",
            "task_id": "fx-forward-cross-rate",
            "checkpoint": "fx-candidate",
        },
    )
    _write_json(
        attempt / "worker-execution.json",
        {
            "artifacts": artifacts,
            "summary": {
                "outcome": outcome,
                "turns": turns,
                "files": files,
            },
        },
    )


def _summary(passed, failed):
    return {
        "scores": [
            {
                "task_id": "fx-forward-cross-rate",
                "reward": 0.0,
                "tests_passed": passed,
                "tests_failed": failed,
                "verifier_exit_code": 0,
            }
        ]
    }


def _cost():
    return {
        "provider_cost_usd": "0.02",
        "completed_request_count": 3,
        "total_tokens": 100,
    }


def _state():
    return new_lineage(
        lineage_id="fx-lineage",
        parent_version="h0",
        parent_path="/workers/h0",
        candidate_version="c1",
        candidate_path="/workers/c1",
        target_task_id="fx-forward-cross-rate",
        protection_task_id="protect",
        worker_route="route",
        worker_budget="normal",
        cost_limit_usd="1",
    )


def _invalid_execution(arm):
    return {
        arm: {
            "valid_for_selection": False,
            "attempts": [
                {
                    "attempt_id": f"{arm}-attempt",
                    "task_id": "fx-forward-cross-rate",
                    "outcome": "model_empty_response",
                    "turns": 0,
                    "files": 0,
                    "artifact_count": 0,
                    "valid_for_selection": False,
                    "invalid_reason": "model_empty_response_before_worker_progress",
                }
            ],
        }
    }


def _controller_plan(target_stage):
    return {
        "schema_version": 1,
        "controller_run_id": "fx-controller",
        "mode": "live",
        "runtime": {},
        "limits": {"provider_cost_usd": "1"},
        "lineages": [
            {
                "lineage_id": "fx-lineage",
                "parent": {"version": "h0", "worker_dir": "/workers/h0"},
                "candidate": {
                    "version": "candidate-r1",
                    "worker_dir": "/workers/candidate-r1",
                },
                "repeat_consistency_policy": "resolved_property_footprint_v1",
                "stages": [
                    target_stage,
                    {"name": "protection", "task_id": "protect"},
                ],
            }
        ],
    }


def test_empty_model_response_before_worker_progress_is_not_selection_valid(tmp_path):
    _attempt(
        tmp_path,
        outcome="model_empty_response",
        turns=0,
        files=0,
        artifacts=[],
    )

    execution = _worker_execution_payload(tmp_path, "fx-candidate")

    assert execution["valid_for_selection"] is False
    assert execution["attempts"][0]["invalid_reason"] == (
        "model_empty_response_before_worker_progress"
    )
    assert _report_status({"candidate": execution}) == "invalid_worker_execution"


def test_low_score_worker_with_artifact_remains_selection_valid(tmp_path):
    _attempt(
        tmp_path,
        outcome="completed",
        turns=2,
        files=1,
        artifacts=[{"path": "answer.csv"}],
    )

    execution = _worker_execution_payload(tmp_path, "fx-candidate")

    assert execution["valid_for_selection"] is True
    assert _report_status({"candidate": execution}) == "complete"


def test_lineage_retains_invalid_execution_without_gain_or_rollback():
    report = {
        "run_id": "fx-invalid-r1",
        "status": "invalid_worker_execution",
        "summaries": {"h0": _summary(16, 0), "candidate": _summary(0, 16)},
        "worker_executions": {
            "candidate": {
                "valid_for_selection": False,
                "attempts": [
                    {
                        "attempt_id": "attempt-a",
                        "task_id": "fx-forward-cross-rate",
                        "outcome": "model_empty_response",
                        "turns": 0,
                        "files": 0,
                        "artifact_count": 0,
                        "valid_for_selection": False,
                        "invalid_reason": (
                            "model_empty_response_before_worker_progress"
                        ),
                    }
                ],
            }
        },
        "cost": _cost(),
    }

    state = import_pilot_report(
        _state(),
        stage="target",
        report=report,
        report_path="/runs/fx-invalid-r1/pilot-report.json",
        parent_arm="h0",
        candidate_arm="candidate",
    )
    resumed = import_pilot_report(
        state,
        stage="target",
        report=report,
        report_path="/runs/fx-invalid-r1/pilot-report.json",
        parent_arm="h0",
        candidate_arm="candidate",
    )

    assert state["decision"] == "INVALID_OBSERVATION"
    assert state["phase"] == "HOLD_FOR_REFINE"
    assert state["current_parent"]["version"] == "h0"
    assert state["archive"] == []
    assert state["observations"]["target"]["selection_valid"] is False
    assert state["observations"]["target"]["observation_kind"] == (
        "infrastructure_invalid"
    )
    assert state["cost"]["provider_cost_usd"] == "0.02"
    assert resumed == state


def test_reused_parent_comparison_preserves_parent_invalidity(tmp_path):
    parent_report = {
        "run_id": "h0-run",
        "status": "invalid_worker_execution",
        "summaries": {"h0": _summary(16, 0)},
        "activations": {"h0": {}},
        "worker_executions": {
            "h0": {
                "valid_for_selection": False,
                "attempts": [{"valid_for_selection": False}],
            }
        },
    }
    candidate_report = {
        "run_id": "candidate-run",
        "status": "complete",
        "summaries": {"candidate": _summary(0, 16)},
        "activations": {"candidate": {}},
        "cost": _cost(),
    }

    report = compose_reused_parent_report(
        parent_comparator=("fx-h0", tmp_path / "h0.json", parent_report),
        candidate_report=candidate_report,
        parent_arm="h0",
        candidate_arm="candidate",
        task_id="fx-forward-cross-rate",
    )

    assert report["status"] == "invalid_worker_execution"
    assert report["worker_executions"]["h0"]["valid_for_selection"] is False


def test_controller_short_circuits_candidate_invalidity_without_ctrf_or_rerun(
    tmp_path,
):
    report_path = tmp_path / "candidate-invalid/pilot-report.json"
    report = {
        "run_id": "candidate-invalid-r1",
        "status": "invalid_worker_execution",
        "summaries": {"h0": _summary(16, 0), "candidate": _summary(0, 16)},
        "activations": {"h0": {}, "candidate": {}},
        "worker_executions": _invalid_execution("candidate"),
        "cost": _cost(),
    }
    _write_json(report_path, report)
    plan = _controller_plan(
        {
            "name": "target",
            "task_id": "fx-forward-cross-rate",
            "replay_report": str(report_path),
            "parent_arm": "h0",
            "candidate_arm": "candidate",
        }
    )
    plan_path = tmp_path / "plan.json"
    _write_json(plan_path, plan)

    def no_dispatch(_argv):
        raise AssertionError("invalid replay must not dispatch a Worker")

    first = run_controller(plan_path, tmp_path / "state", runner=no_dispatch)
    resumed = run_controller(plan_path, tmp_path / "state", runner=no_dispatch)
    state = first["lineages"]["fx-lineage"]

    assert state["decision"] == "INVALID_OBSERVATION"
    assert state["phase"] == "HOLD_FOR_REFINE"
    assert state["current_parent"]["version"] == "h0"
    assert state["cost"]["provider_cost_usd"] == "0.02"
    assert state["accounted_run_ids"] == ["candidate-invalid-r1"]
    assert resumed == first


def test_controller_preserves_invalid_selection_reference_without_ctrf_or_rerun(
    tmp_path,
):
    parent_path = tmp_path / "h0-invalid/pilot-report.json"
    parent_report = {
        "run_id": "h0-invalid-r1",
        "status": "invalid_worker_execution",
        "summaries": {"h0": _summary(0, 16)},
        "activations": {"h0": {}},
        "worker_executions": _invalid_execution("h0"),
        "cost": _cost(),
    }
    candidate_path = tmp_path / "candidate-valid/pilot-report.json"
    candidate_report = {
        "run_id": "candidate-valid-r1",
        "status": "complete",
        "summaries": {"candidate": _summary(1, 15)},
        "activations": {"candidate": {}},
        "cost": {
            "provider_cost_usd": "0.004",
            "completed_request_count": 1,
            "total_tokens": 25,
        },
    }
    _write_json(parent_path, parent_report)
    _write_json(candidate_path, candidate_report)
    plan = _controller_plan(
        {
            "name": "target",
            "task_id": "fx-forward-cross-rate",
            "replay_report": str(candidate_path),
            "parent_arm": "h0",
            "candidate_arm": "candidate",
            "selection_reference": {
                "id": "fx-h0-r1",
                "report_path": str(parent_path),
                "task_id": "fx-forward-cross-rate",
                "worker_route": "declared-main0-route",
                "worker_budget": "normal",
                "reference_version": "h0",
            },
        }
    )
    plan_path = tmp_path / "selection-plan.json"
    _write_json(plan_path, plan)

    def no_dispatch(_argv):
        raise AssertionError("selection replay must not dispatch a Worker")

    first = run_controller(
        plan_path, tmp_path / "selection-state", runner=no_dispatch
    )
    resumed = run_controller(
        plan_path, tmp_path / "selection-state", runner=no_dispatch
    )
    state = first["lineages"]["fx-lineage"]

    assert state["decision"] == "INVALID_OBSERVATION"
    assert state["current_parent"]["version"] == "h0"
    assert state["cost"]["provider_cost_usd"] == "0.004"
    assert state["accounted_run_ids"] == ["candidate-valid-r1"]
    invalid = state["observations"]["target"]["invalid_worker_executions"]
    assert invalid[0]["arm"] == "h0"
    assert resumed == first
