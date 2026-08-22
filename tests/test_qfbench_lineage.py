from qea.qfbench_lineage import (
    freeze_lineage,
    import_pilot_report,
    new_lineage,
)


def _state(limit="1"):
    return new_lineage(
        lineage_id="lineage-a",
        parent_version="h0",
        parent_path="/workers/h0",
        candidate_version="c1",
        candidate_path="/workers/c1",
        target_task_id="target",
        protection_task_id="protect",
        worker_route="route-a",
        worker_budget="normal",
        cost_limit_usd=limit,
    )


def _report(run_id, task, parent, candidate, cost="0.1"):
    def summary(score):
        passed, total, reward = score
        return {
            "scores": [{
                "task_id": task,
                "reward": reward,
                "tests_passed": passed,
                "tests_failed": total - passed,
                "verifier_exit_code": 0,
            }]
        }

    return {
        "status": "complete",
        "run_id": run_id,
        "summaries": {
            "h0": summary(parent),
            "candidate": summary(candidate),
        },
        "cost": {
            "provider_cost_usd": cost,
            "completed_request_count": 2,
            "total_tokens": 100,
        },
    }


def _apply(state, stage, report, *, property_set_safe=None):
    return import_pilot_report(
        state,
        stage=stage,
        report=report,
        report_path=f"/{report['run_id']}/pilot-report.json",
        parent_arm="h0",
        candidate_arm="candidate",
        property_set_safe=property_set_safe,
    )


def test_repeated_gain_and_safe_protection_promote_then_freeze():
    state = _apply(_state(), "target", _report("target-run", "target", (48, 51, 0), (50, 51, 0)))
    state = _apply(state, "repeat", _report("repeat-run", "target", (37, 51, 0), (50, 51, 0)))
    state = _apply(
        state,
        "protection",
        _report("protect-run", "protect", (42, 42, 1), (42, 42, 1)),
        property_set_safe=True,
    )

    assert state["decision"] == "PROMOTE"
    assert state["current_parent"]["version"] == "c1"
    assert freeze_lineage(state)["phase"] == "FROZEN"


def test_property_swap_rolls_back_aggregate_tie():
    state = _apply(_state(), "target", _report("target-run", "target", (65, 68, 0), (68, 68, 1)))
    state = _apply(state, "repeat", _report("repeat-run", "target", (66, 68, 0), (68, 68, 1)))
    state = _apply(
        state,
        "protection",
        _report("protect-run", "protect", (38, 39, 0.96), (38, 39, 0.96)),
        property_set_safe=False,
    )

    assert state["decision"] == "ROLLBACK"
    assert state["current_parent"]["version"] == "h0"


def test_target_without_gain_rolls_back_without_repeat():
    state = _apply(_state(), "target", _report("target-run", "target", (50, 51, 0), (49, 51, 0)))

    assert state["decision"] == "ROLLBACK"
    assert "repeat" not in state["observations"]


def test_reimporting_accounted_report_is_idempotent():
    report = _report("target-run", "target", (48, 51, 0), (50, 51, 0))
    state = _apply(_state(), "target", report)
    again = _apply(state, "target", report)

    assert again == state
    assert again["cost"]["provider_cost_usd"] == "0.1"


def test_cost_limit_stops_before_repeat():
    state = _apply(
        _state(limit="0.1"),
        "target",
        _report("target-run", "target", (48, 51, 0), (50, 51, 0)),
    )

    assert state["decision"] == "BUDGET_STOP"
    assert state["phase"] == "BUDGET_STOP"
