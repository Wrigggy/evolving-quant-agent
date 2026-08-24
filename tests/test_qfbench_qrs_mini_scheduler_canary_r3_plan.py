import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
R2_PATH = ROOT / "data/breadth/QF_QRS_MINI_SCHEDULER_CANARY_R2_PLAN.json"
R3_PATH = ROOT / "data/breadth/QF_QRS_MINI_SCHEDULER_CANARY_R3_PLAN.json"
R2 = json.loads(R2_PATH.read_text(encoding="utf-8"))
R3 = json.loads(R3_PATH.read_text(encoding="utf-8"))


def _strings(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from _strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _strings(child)
    elif isinstance(value, str):
        yield value


def _normalized_r3_identity(value):
    if isinstance(value, dict):
        return {key: _normalized_r3_identity(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_normalized_r3_identity(child) for child in value]
    if isinstance(value, str):
        return value.replace("r3", "r2").replace("R3", "R2")
    return value


def test_r3_is_frozen_final_separate_setup_recovery() -> None:
    assert R3["schema_version"] == 2
    assert R3["date"] == "2026-08-25"
    assert R3["status"] == "frozen_not_run"
    assert R3["experiment_id"] == (
        "qf-qrs-mini-scheduler-canary-20260825-r3"
    )
    recovery = R3["setup_recovery"]
    assert recovery["kind"] == "final_separately_frozen_setup_recovery_not_repeat"
    assert recovery["engineering_source_revision"] == "2676e38"
    assert recovery["antecedent_run_id"] == R2["experiment_id"]
    final = R3["final_recovery_policy"]
    assert final["this_is_the_last_setup_recovery"] is True
    assert final["additional_setup_recovery_authorized"] is False
    assert final["r4_authorized"] is False


def test_r3_keeps_r2_scientific_setup_and_caps_with_fresh_identities() -> None:
    assert R3["phase_order"] == R2["phase_order"]
    assert R3["limits"] == R2["limits"]
    assert R3["sealed_main_tasks"] == R2["sealed_main_tasks"]
    assert R3["cross_family_workflow_evidence"]["anchor_task_by_family"] == (
        R2["cross_family_workflow_evidence"]["anchor_task_by_family"]
    )
    assert R3["cross_family_workflow_evidence"]["workflow_scope"] == (
        R2["cross_family_workflow_evidence"]["workflow_scope"]
    )
    assert len(R3["development_panels"]) == len(R2["development_panels"])
    for r2_panel, r3_panel in zip(
        R2["development_panels"], R3["development_panels"]
    ):
        assert r3_panel["panel_index"] == r2_panel["panel_index"]
        assert r3_panel["family"] == r2_panel["family"]
        assert r3_panel["task_ids"] == r2_panel["task_ids"]
        assert _normalized_r3_identity(r3_panel["parent"]) == r2_panel["parent"]
        assert _normalized_r3_identity(r3_panel["proposal"]) == r2_panel["proposal"]
    execution = R3["canary_execution"]
    r2_execution = R2["canary_execution"]
    assert execution["scheduler_run_id"].endswith("-r3")
    assert {
        key: value for key, value in execution.items() if key != "scheduler_run_id"
    } == {
        key: value
        for key, value in r2_execution.items()
        if key != "scheduler_run_id"
    }
    assert execution["stop_after_panel"] == 1
    assert execution["actual_max_h0_bank_cells"] == 4
    assert execution["actual_max_panel_matched_cells"] == 12
    assert execution["actual_max_qfbench_cells"] == 16
    assert execution["actual_evolver_calls"] == 1
    assert execution["actual_reviewer_calls"] == 1
    assert execution["sealed_dispatch_authorized"] is False
    assert execution["later_panel_dispatch_authorized"] is False
    assert execution["main_reuse_allowed"] is False
    assert _normalized_r3_identity(R3["phase2_feedback_sealed_main"]) == (
        R2["phase2_feedback_sealed_main"]
    )


def test_only_general_evidence_interface_and_abstain_control_changes_are_allowed() -> None:
    recovery = R3["setup_recovery"]
    changes = recovery["only_engineering_changes"]
    assert len(changes) == 5
    text = " ".join(changes).casefold()
    for required in (
        "partial result",
        "truncated=true",
        "64000 bytes",
        "jsonl",
        "zero context",
        "at most eight matches",
        "one-physical-line",
        "evidence_refs",
        "immutable evidence paths",
        "legal complete-information abstain",
        "unchanged frozen parent",
        "no review or candidate worker",
    ):
        assert required in text
    forbidden_keys = {
        "hypothesis",
        "candidate_suggestion",
        "suggested_candidate",
        "recommended_change",
        "selected_relation",
        "state_card",
    }
    assert forbidden_keys.isdisjoint(set(_strings(R3)))
    serialized = json.dumps(R3, sort_keys=True)
    assert '"H2"' not in serialized
    assert '"H3"' not in serialized
    assert '"S3"' not in serialized


def test_r3_forbids_all_antecedent_material_and_uses_fresh_r3_evidence() -> None:
    forbidden = " ".join(R3["setup_recovery"]["reuse_forbidden"]).casefold()
    for required in (
        "r2 primitive-h0 worker executions",
        "r2 trajectory bank",
        "r2 proposal",
        "r2 official scores",
        "r2 verifier material",
        "r2 controller outcomes",
        "r2 evidence read state",
        "any r1 material",
    ):
        assert required in forbidden
    visible = R3["cross_family_workflow_evidence"][
        "canary_panel_1_visible_rule"
    ]
    assert "fresh R3" in visible
    assert "No R1 or R2 material" in visible
    boundary = R3["answer_boundary"]
    assert "All four R3 Primitive-H0 Workers" in boundary
    assert "R2 material" in boundary
    assert "prior evidence access state" in boundary
    assert R3["public_task_partition_rule"]["development_n"] == 4
    assert R3["public_task_partition_rule"]["role"] == "engineering_canary_only"
    assert "No R1, R2 or R3" in R3["public_task_partition_rule"][
        "main_experiment_membership"
    ]


def test_legal_abstain_is_valid_but_cannot_clear_mini_or_main() -> None:
    abstain = R3["final_recovery_policy"]["legal_complete_information_abstain"]
    assert abstain == {
        "valid_terminal_outcome": True,
        "controller_action": (
            "retain_abstain_and_carry_unchanged_frozen_parent_without_review_or_"
            "candidate_dispatch"
        ),
        "mini_scheduler_gate_cleared": False,
        "main_status": "NO_GO",
        "follow_on_setup_recovery": "forbidden",
    }
    terminal = R3["required_live_outcomes"]["terminal"]
    assert "legal complete-information ABSTAIN" in terminal
    assert "does not clear the mini gate" in terminal
    assert "Main NO-GO" in terminal
    assert "no further setup recovery" in terminal


def test_only_complete_review_matched_handoff_resume_path_clears_mini() -> None:
    policy = R3["final_recovery_policy"]["mini_clear_rule"]
    assert "overall and coverage Review PASS" in policy
    assert "exact reviewed snapshot" in policy
    assert "all 12 matched parent-candidate cells" in policy
    assert "answer-free handoff" in policy
    assert "same-stop resume performs zero new work" in policy
    live = R3["required_live_outcomes"]
    assert "overall PASS and coverage PASS" in live["review_pass"]
    assert "all 12 matched cells" in live["matched_gate"]
    assert "three panel-visible tasks" in live["matched_gate"]
    assert "two arms" in live["matched_gate"]
    assert "two fresh repetitions" in live["matched_gate"]
    assert "answer-free panel handoff" in live["handoff"]
    assert "zero-work resume" in live["resume"]
    assert "Review-PASS, 12-cell matched, handoff and zero-work-resume" in live[
        "terminal"
    ]
    assert R3["final_recovery_policy"]["main_authority_after_mini_clear"].startswith(
        "Clearing this engineering mini gate does not reuse R3 material"
    )


def test_r3_keeps_review_matched_gate_and_claim_boundaries() -> None:
    phase1 = R3["phase1_six_panel_curriculum"]
    assert phase1["proposal_calls"] == R2["phase1_six_panel_curriculum"][
        "proposal_calls"
    ]
    assert phase1["reviewer_calls"] == R2["phase1_six_panel_curriculum"][
        "reviewer_calls"
    ]
    assert phase1["canary_authorized_panel_count"] == 1
    assert "scientific non-promotion" in phase1["promotion_rule"]
    assert "complete matched path" in phase1["promotion_rule"]
    assert R3["phase2_feedback_sealed_main"]["canary_dispatch"] == (
        "forbidden_by_stop_after_panel_1"
    )
    assert "optimize_only_sources is empty" in R3["required_live_outcomes"][
        "answer_boundary"
    ]
    claim = R3["claim_boundary"]
    for forbidden_claim in (
        "not an R2 repeat",
        "main result",
        "benchmark gain",
        "reusable candidate",
        "stable promotion",
        "sealed result",
        "evidence for QRS effectiveness",
    ):
        assert forbidden_claim in claim
