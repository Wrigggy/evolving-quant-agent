from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = (
    ROOT / "data/breadth/QF_GLOBAL_S6_PRIMITIVE_H0_TRAJECTORY_SCHEDULER_PLAN.json"
)
MANIFEST_PATH = ROOT / "data/qfbench/MANIFEST_85_BASELINE.json"


def _read(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _eligible_rows() -> list[dict[str, object]]:
    excluded = {
        "swap-curve-bootstrap-ois",
        "13f-amendment-aware-crowding",
        "fx-forward-cross-rate",
    }
    return [
        row
        for row in _read(MANIFEST_PATH)["baseline"]["primary"]
        if row["reward_kind"] == "binary"
        and row["resource_source"] == "upstream"
        and row["task_id"] not in excluded
    ]


def _sealed_draw(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    selected: list[dict[str, object]] = []
    for domain in sorted({row["domain"] for row in rows}):
        pool = sorted(
            (row for row in rows if row["domain"] == domain),
            key=lambda row: row["task_id"],
        )
        pair = random.Random(
            f"20260824:sealed-main:{domain}"
        ).sample(pool, 2)
        for group, row in zip(
            ("a", "b"), sorted(pair, key=lambda row: row["task_id"])
        ):
            selected.append(
                {
                    "domain": domain,
                    "group": group,
                    "difficulty": row["difficulty"],
                    "task_id": row["task_id"],
                }
            )
    return selected


def test_plan_has_local_scheduler_but_launch_waits_for_live_canaries() -> None:
    plan = _read(PLAN_PATH)
    support = plan["implementation_status"]

    assert plan["schema_version"] == 2
    assert plan["status"] == (
        "frozen_local_executable_pre_canary_not_launch_authorized"
    )
    assert support["plan_only"] is False
    assert support["scheduler_wrapper_support"] == "implemented_local_pre_canary"
    assert support["current_thin_campaign_auto_dispatches_h0_bank"] is False
    assert "pre-existing parent worker directories" in support[
        "current_thin_campaign_behavior"
    ]
    assert support["launch_authorized"] is False
    assert support["launch_argv"] is None
    assert "outer scheduler are implemented locally" in support[
        "implementation_boundary"
    ]
    assert "mini-scheduler live canary" in support["implementation_boundary"]
    assert plan["phase_order"] == [
        "import_frozen_primitive_h0",
        "phase0_all_n_h0_development_bank",
        "phase1_six_panel_curriculum",
        "phase2_feedback_sealed_main",
        "terminal_report",
    ]


def test_exploratory_primitive_selection_is_external_to_scheduler() -> None:
    plan = _read(PLAN_PATH)
    handoff = plan["external_primitive_h0_handoff"]

    assert handoff["owned_by_scheduler"] is False
    assert handoff["selection_stage"] == (
        "external_exploratory_harness_selection"
    )
    assert handoff["selection_rule_preregistered_by_this_scheduler"] is False
    assert handoff["selection_runs_dispatched_by_this_scheduler"] == 0
    assert handoff["selection_cost_counted_in_qrs_scheduler"] is False
    assert handoff["handoff_manifest"].endswith("QF_PRIMITIVE_H0_SELECTED.json")
    assert "selected_worker_root" in handoff["required_handoff_fields"]
    assert "selected_runtime" in handoff["required_handoff_fields"]
    assert "Import exactly one materialized" in handoff["acceptance_rule"]
    assert "does not rank, rerun, replace" in handoff["separation_rule"]


def test_frozen_base_harness_adapter_is_a_generic_scheduler_entry_contract() -> None:
    plan = _read(PLAN_PATH)
    adapter = plan["frozen_base_harness_adapter_contract"]

    assert adapter["method_role"] == (
        "standard_initialization_interface_for_qrs_evolution"
    )
    assert adapter["reference_implementation"] == (
        "qea/worker_quant_h0_s6_primitive_v1"
    )
    assert "Any independently authored base harness" in adapter["generality"]
    layout = " ".join(adapter["required_worker_layout"])
    assert "agent.yaml" in layout
    assert "run_shell_command" in layout
    assert "record_quant_state" in layout
    assert "Candidate Reviewer" in layout
    semantics = " ".join(adapter["required_semantics"])
    assert "hidden evaluator answers" in semantics
    assert "run independently before any Evolver call" in semantics
    assert "fresh matched controls" in semantics
    assert "initialization-agnostic" in adapter["scheduler_boundary"]
    assert "conditional on the imported frozen base harness" in adapter[
        "claim_boundary"
    ]


def test_h0_is_primitive_s6_and_checked_in_agent_is_concrete() -> None:
    plan = _read(PLAN_PATH)
    h0 = plan["arm_identities"]["h0"]
    agent = (
        ROOT / "qea/worker_quant_h0_s6_primitive_v1/agent.yaml"
    ).read_text(encoding="utf-8")

    assert h0["label"] == "quant-h0-s6-primitive-v1-fresh"
    assert h0["agent_name"] == "qea_quant_h0_s6_primitive_v1_worker"
    assert h0["worker_root"] == "qea/worker_quant_h0_s6_primitive_v1"
    assert h0["tools"] == ["run_shell_command", "record_quant_state"]
    assert "Strict genuine structured S1-through-S6" in h0[
        "protocol_expectation"
    ]
    assert "deliberately does not teach" in h0["protocol_expectation"]
    assert "name: qea_quant_h0_s6_primitive_v1_worker" in agent
    assert agent.count("yaml_path:") == 2
    assert "run_shell_command.tool.yaml" in agent
    assert "record_quant_state.tool.yaml" in agent
    assert "max_iterations: 60" in agent
    assert "max_tokens: 32000" in agent


def test_partition_is_public_only_all_n_development_and_disjoint_sealed() -> None:
    plan = _read(PLAN_PATH)
    rows = _eligible_rows()
    sealed = plan["sealed_main_tasks"]
    sealed_ids = {task["task_id"] for task in sealed}
    panels = plan["development_panels"]
    development_ids = {
        task_id for panel in panels for task_id in panel["task_ids"]
    }
    eligible_ids = {row["task_id"] for row in rows}

    assert len(rows) == plan["public_task_partition_rule"][
        "eligible_after_construct_exclusions"
    ] == 57
    assert sealed == _sealed_draw(rows)
    assert len(sealed_ids) == 12
    assert len(development_ids) == plan["public_task_partition_rule"][
        "development_n"
    ] == 45
    assert not sealed_ids & development_ids
    assert sealed_ids | development_ids == eligible_ids
    assert Counter(task["domain"] for task in sealed) == Counter(
        {panel["family"]: 2 for panel in panels}
    )
    assert [panel["panel_index"] for panel in panels] == list(range(1, 7))
    assert all(
        panel["matched_fitness_scope"]
        == "all_focus_tasks_plus_five_cross_family_anchors_two_fresh_repetitions"
        for panel in panels
    )
    assert "All eligible tasks not selected" in plan[
        "public_task_partition_rule"
    ]["development_definition"]
    assert "Prior or current score" in plan["public_task_partition_rule"][
        "selector_forbidden_inputs"
    ]


def test_phase0_runs_every_development_task_once_and_retains_full_history() -> None:
    plan = _read(PLAN_PATH)
    phase0 = plan["phase0_all_n_h0_development_bank"]

    assert phase0["arm"] == "quant-h0-s6-primitive-v1-fresh"
    assert phase0["task_count_n"] == phase0["primary_cells"] == 45
    assert phase0["repetitions"] == 1
    assert "one independent H0 Worker/verifier per task" in phase0["schedule"]
    assert "Complete all 45 before the first Evolver call" in phase0["schedule"]
    assert set(phase0["required_retention"]) == {
        "public_instruction",
        "raw_worker_trace",
        "final_response",
        "artifact_manifest_including_explicit_empty_set",
        "worker_produced_artifact_contents",
        "worker_execution_process_record",
        "turn_tool_error_and_timing_record",
        "request_token_cost_lifecycle_and_cleanup_accounting",
    }
    assert "45 of 45" in phase0["completion_gate"]
    assert "Never replace a task" in phase0["completion_gate"]
    assert "N=45, not a 12-task sample" in plan["epistemic_partitions"][
        "development_bank"
    ]


def test_each_family_has_one_proposal_review_matched_gate_and_exact_parent_chain() -> None:
    plan = _read(PLAN_PATH)
    panels = plan["development_panels"]
    curriculum = plan["phase1_six_panel_curriculum"]
    lineage = plan["arm_identities"]["candidate_lineage"]

    assert curriculum["panel_count"] == 6
    assert curriculum["proposal_calls"] == curriculum["reviewer_calls"] == 6
    assert [panel["parent"] for panel in panels] == [
        "quant-h0-s6-primitive-v1-fresh",
        "global-s6-p1",
        "global-s6-p2",
        "global-s6-p3",
        "global-s6-p4",
        "global-s6-p5",
    ]
    assert [panel["proposal"] for panel in panels] == lineage["labels"]
    assert lineage["parent_chain"].startswith(
        "quant-h0-s6-primitive-v1-fresh -> global-s6-p1"
    )
    assert lineage["parent_chain"].endswith("global-s6-p6-final")
    assert "Exactly one task-agnostic" in curriculum["proposal_rule"]
    assert "No single-family workflow_global proposal" in curriculum[
        "proposal_rule"
    ]
    assert "cumulative-H0-to-proposal" in curriculum["review_rule"]
    assert "genuine isolated structured S1-through-S6" in curriculum[
        "matched_gate_rule"
    ]
    assert "every focus and anchor task in both repetitions" in curriculum[
        "promotion_rule"
    ]
    assert "strictly greater" in curriculum["promotion_rule"]
    assert "identical focus task is a proposal win in both repetitions" in curriculum[
        "promotion_rule"
    ]
    assert "retains the incumbent and continues" in curriculum[
        "promotion_rule"
    ]


def test_curriculum_firewall_excludes_scores_expected_checker_and_sealed() -> None:
    plan = _read(PLAN_PATH)
    firewall = plan["curriculum_evidence_firewall"]
    visible = " ".join(firewall["panel_k_evolver_visible"])
    denied = " ".join(firewall["never_evolver_visible"]).lower()

    assert "every focus-family task in panel k" in visible
    assert "five frozen cross-family anchor tasks" in visible
    assert "answer-free matched-gate traces" in visible
    for phrase in (
        "official score",
        "verifier",
        "failed-property",
        "expected value",
        "checker",
        "review reason",
        "sealed-main identity",
    ):
        assert phrase in denied
    assert "later-panel H0 history before that panel" in firewall[
        "never_evolver_visible"
    ]
    assert "stops before the panel Evolver" in firewall["failure_rule"]


def test_sealed_main_uses_fresh_h0_twice_with_reversed_order_and_no_feedback() -> None:
    plan = _read(PLAN_PATH)
    main = plan["phase2_feedback_sealed_main"]

    assert main["final_candidate"] == "retained-incumbent-after-panel-6"
    assert main["comparator"] == "quant-h0-s6-primitive-v1-fresh"
    assert main["task_count"] == 12
    assert main["repetitions"] == 2
    assert main["paired_observations"] == 24
    assert main["primary_cells"] == 48
    assert main["fresh_h0_cells"] == main["final_candidate_cells"] == 24
    for group in ("a", "b"):
        group_runs = [run for run in main["runs"] if run["group"] == group]
        assert group_runs[0]["arm_order"] == list(
            reversed(group_runs[1]["arm_order"])
        )
    assert "never performance" in main["automatic_dispatch"]
    assert "No sealed instruction or outcome" in main["feedback_rule"]


def test_counts_caps_metrics_and_current_scheduler_answer_are_consistent() -> None:
    plan = _read(PLAN_PATH)
    limits = plan["limits"]
    answer = plan["main_scheduler_h0_answer"]
    metrics = plan["metrics"]

    assert limits["qfbench_primary_cells"] == 45 + 150 + 150 + 24 + 24 == 393
    assert limits["qfbench_h0_cells"] == 45 + 14 + 24 == 83
    assert limits["qfbench_candidate_lineage_cells"] == 136 + 150 + 24 == 310
    assert limits["qfbench_h0_cells"] + limits[
        "qfbench_candidate_lineage_cells"
    ] == 393
    assert limits["maximum_qfbench_sessions_including_recovery"] == 393 + 3
    assert limits["external_primitive_selection_sessions"] == (
        "outside_scheduler_not_capped_here"
    )
    assert limits["maximum_all_worker_sessions"] == 396
    assert limits["maximum_worker_turn_iterations"] == 396 * 60 == 23760
    assert limits["evolver_calls"] == limits["reviewer_calls"] == 6
    assert limits["paid_or_remote_authority"] is False
    assert answer["planned_scheduler_includes_h0"] is True
    assert answer["current_executable_thin_scheduler_includes_fresh_h0"] is False
    assert answer["current_executable_global_scheduler_includes_fresh_h0"] is True
    assert "N=45 development tasks" in answer["exact_role"]
    assert "393 primary QFBench cells" in answer["counts"]
    assert "83 cells use the primitive H0" in answer["counts"]
    assert "equal-domain macro" in metrics["main_primary"]
    assert "headroom closure" in metrics["main_secondary"]
    assert "Never headline a pooled" in metrics["readability"]
    stop_text = " ".join(plan["stop_rules"])
    for marker in (
        "STOP_PRE_CANARY",
        "STOP_H0_HANDOFF",
        "STOP_BANK",
        "STOP_PANEL",
        "STOP_MAIN",
    ):
        assert marker in stop_text
