from qea.qfbench_lineage import (
    freeze_lineage,
    import_pilot_report,
    import_proposal_report,
    import_quantitative_protection_review,
    load_lineage,
    new_lineage,
    new_proposal_lineage,
    save_lineage,
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


def _quant_state(limit="2"):
    return new_lineage(
        lineage_id="quant-lineage",
        parent_version="h0",
        parent_path="/workers/h0",
        candidate_version="search-v2",
        candidate_path="/workers/search-v2",
        target_task_id="dupire-local-vol",
        protection_task_id="localvol-barrier",
        worker_route="route-a",
        worker_budget="normal",
        cost_limit_usd=limit,
        quantitative_protection_review=True,
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


def _proposal_state(limit="1"):
    return new_proposal_lineage(
        lineage_id="lineage-a",
        parent_version="h0",
        parent_path="/workers/h0",
        target_task_id="target",
        protection_task_id="protect",
        worker_route="route-a",
        worker_budget="normal",
        cost_limit_usd=limit,
    )


def _proposal(decision, admitted, candidate_dir="/real/proposal/candidate"):
    return {
        "decision": decision,
        "candidate_dir": candidate_dir,
        "admission": {"admitted": admitted},
        "candidate_generation_throughput": {
            "provider_cost_usd": "0.02",
            "completed_request_count": 3,
            "downstream_delivery_request_count": 1,
            "total_tokens": 200,
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


def test_admitted_act_attaches_report_candidate_and_accounts_once():
    report = _proposal("ACT", True)
    state = import_proposal_report(
        _proposal_state(),
        report=report,
        report_path="/proposal/proposal-report.json",
        proposal_run_id="proposal-r1",
        candidate_version="candidate-r1",
    )
    again = import_proposal_report(
        state,
        report=report,
        report_path="/proposal/proposal-report.json",
        proposal_run_id="proposal-r1",
        candidate_version="candidate-r1",
    )

    assert state["phase"] == "TARGET"
    assert state["candidate"] == {
        "version": "candidate-r1",
        "worker_dir": "/real/proposal/candidate",
    }
    assert again == state
    assert state["cost"]["provider_cost_usd"] == "0.02"
    assert state["cost"]["completed_requests"] == 4


def test_abstain_is_a_terminal_proposal_without_candidate():
    state = import_proposal_report(
        _proposal_state(),
        report=_proposal("ABSTAIN", None),
        report_path="/proposal/proposal-report.json",
        proposal_run_id="proposal-r1",
        candidate_version="unused",
    )

    assert state["decision"] == "ABSTAIN"
    assert state["phase"] == "FROZEN"
    assert state["candidate"] is None


def test_unadmitted_act_never_enters_candidate_lineage():
    state = import_proposal_report(
        _proposal_state(),
        report=_proposal("ACT", False),
        report_path="/proposal/proposal-report.json",
        proposal_run_id="proposal-r1",
        candidate_version="unused",
    )

    assert state["decision"] == "ROLLBACK"
    assert state["status"] == "proposal_rejected"
    assert state["candidate"] is None


def test_search_v2_conflicting_protection_repeat_holds_for_refinement():
    state = _apply(
        _quant_state(),
        "target",
        _report(
            "target-run", "dupire-local-vol", (65, 68, 0), (68, 68, 1)
        ),
    )
    state = _apply(
        state,
        "repeat",
        _report(
            "target-repeat", "dupire-local-vol", (66, 68, 0), (68, 68, 1)
        ),
    )
    first_protection = _report(
        "protection-r1",
        "localvol-barrier",
        (38, 39, 0.96),
        (38, 39, 0.96),
    )
    state = import_pilot_report(
        state,
        stage="protection",
        report=first_protection,
        report_path="/protection-r1/pilot-report.json",
        parent_arm="h0",
        candidate_arm="candidate",
        property_set_safe=False,
        quantitative_protection_triage={
            "verdict": "INCONCLUSIVE",
            "outcome_severity": "UNRESOLVED",
            "failed_properties": {
                "parent": ["barrier_outputs_reasonable"],
                "candidate": ["vanilla_mc_close_to_surface"],
            },
        },
    )
    assert state["phase"] == "PROTECTION_REVIEW"

    review = {
        "schema_version": 1,
        "reviews": [{
            "case_id": "search-v2-protection",
            "outcome_severity": "UNRESOLVED",
            "causal_attribution": "UNRESOLVED",
            "quantitative_diagnosis": "NUMERIC_TOLERANCE_ONLY",
            "next_evidence": "PAIRED_PROTECTION_REPEAT",
            "evidence_refs": ["search-v2:protection-r1"],
        }],
    }
    state = import_quantitative_protection_review(
        state,
        review_id="review-r1",
        review_path="/review-r1/RESULT.json",
        review_payload=review,
        case_id="search-v2-protection",
        review_accounting={
            "provider_cost_usd": "0.012",
            "completed_request_count": 1,
            "total_tokens": 123,
        },
    )
    resumed_review = import_quantitative_protection_review(
        state,
        review_id="review-r1",
        review_path="/review-r1/RESULT.json",
        review_payload=review,
        case_id="search-v2-protection",
        review_accounting={
            "provider_cost_usd": "0.012",
            "completed_request_count": 1,
            "total_tokens": 123,
        },
    )
    assert resumed_review == state
    assert state["phase"] == "PROTECTION_REPEAT"

    repeat_report = _report(
        "protection-r2",
        "localvol-barrier",
        (39, 39, 1),
        (38, 39, 0.96),
    )
    state = import_pilot_report(
        state,
        stage="protection_repeat",
        report=repeat_report,
        report_path="/protection-r2/pilot-report.json",
        parent_arm="h0",
        candidate_arm="candidate",
        property_set_safe=False,
        quantitative_protection_triage={
            "verdict": "INCONCLUSIVE",
            "outcome_severity": "UNRESOLVED",
            "decision_label": "STILL_INCONCLUSIVE",
            "failed_properties": {
                "parent": [],
                "candidate": ["barrier_outputs_reasonable"],
            },
            "evidence_summary": (
                "candidate failure identity rotated across protection repeats"
            ),
        },
    )
    resumed_repeat = import_pilot_report(
        state,
        stage="protection_repeat",
        report=repeat_report,
        report_path="/protection-r2/pilot-report.json",
        parent_arm="h0",
        candidate_arm="candidate",
        property_set_safe=False,
        quantitative_protection_triage={"verdict": "INCONCLUSIVE"},
    )

    assert resumed_repeat == state
    assert state["decision"] == "HOLD_FOR_REFINE"
    assert state["phase"] == "HOLD_FOR_REFINE"
    assert state["current_parent"]["version"] == "h0"
    assert state["candidate"]["version"] == "search-v2"
    assert state["archive"] == []
    assert state["hold"]["reason"] == (
        "quantitative_protection_still_inconclusive"
    )
    assert state["cost"]["provider_cost_usd"] == "0.412"
    assert state["cost"]["completed_requests"] == 9
    assert state["cost"]["total_tokens"] == 523
    assert state["accounted_review_ids"] == ["review-r1"]


def test_main0b_clear_protection_failure_holds_component_for_refinement(
    tmp_path,
):
    state = _apply(
        _quant_state(),
        "target",
        _report(
            "target-run", "dupire-local-vol", (66, 68, 0), (68, 68, 1)
        ),
    )
    state = _apply(
        state,
        "repeat",
        _report(
            "target-repeat", "dupire-local-vol", (66, 68, 0), (68, 68, 1)
        ),
    )
    report = _report(
        "protection-main0b",
        "localvol-barrier",
        (35, 39, 0.9),
        (29, 39, 0.768857),
    )
    state = import_pilot_report(
        state,
        stage="protection",
        report=report,
        report_path="/protection-main0b/pilot-report.json",
        parent_arm="h0",
        candidate_arm="candidate",
        property_set_safe=False,
        quantitative_protection_triage={
            "verdict": "FAIL",
            "outcome_severity": "MEANINGFUL_CANDIDATE_REGRESSION",
            "causal_attribution": "HARNESS_WORKER_INTERACTION",
        },
    )
    resumed = import_pilot_report(
        state,
        stage="protection",
        report=report,
        report_path="/protection-main0b/pilot-report.json",
        parent_arm="h0",
        candidate_arm="candidate",
        property_set_safe=False,
        quantitative_protection_triage={"verdict": "FAIL"},
    )

    assert resumed == state
    assert state["decision"] == "HOLD_FOR_REFINE"
    assert state["phase"] == "HOLD_FOR_REFINE"
    assert state["current_parent"]["version"] == "h0"
    assert state["candidate"]["version"] == "search-v2"
    assert state["archive"] == []
    assert state["hold"]["reason"] == "quantitative_protection_regression"

    state_path = tmp_path / "lineage.json"
    save_lineage(state_path, state)
    restored = load_lineage(state_path)
    assert restored["phase"] == "HOLD_FOR_REFINE"
    assert restored["status"] == "candidate_hold"
    assert restored["current_parent"] == state["current_parent"]
    assert restored["candidate"] == state["candidate"]
    assert restored["hold"] == state["hold"]
