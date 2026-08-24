from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from qea.frozen_base_harness import (
    build_selected_runtime,
    freeze_base_harness,
    inspect_base_harness,
)
from qea.qfbench_trajectory_bank import build_trajectory_bank
from qea.qrs_global_scheduler import _panel_evaluation_tasks, run_scheduler
from qea.qrs_main_launch import build_qrs_main_launch
from qea.qrs_public_contracts import materialize_qrs_public_contracts
from scripts.run_qrs_global_scheduler import (
    GlobalSchedulerError,
    _require_live_launch_authority,
)


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = (
    ROOT
    / "data/breadth/QF_QRS_REVIEWER_POLICY_V2_QUALIFICATION_R2_PLAN.json"
)
R1_PLAN_PATH = (
    ROOT
    / "data/breadth/QF_QRS_REVIEWER_POLICY_V2_QUALIFICATION_PLAN.json"
)
MANIFEST_PATH = ROOT / "data/qfbench/MANIFEST_85_BASELINE.json"
PRIMITIVE = ROOT / "qea/worker_quant_h0_s6_primitive_v1"
PLAN = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
R1 = json.loads(R1_PLAN_PATH.read_text(encoding="utf-8"))
R2_ID = "qf-qrs-reviewer-policy-v2-qualification-20260825-r2"
R1_ID = "qf-qrs-reviewer-policy-v2-qualification-20260825-r1"


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _public_task_source(tmp_path: Path) -> Path:
    root = tmp_path / R2_ID / "fresh-public-source"
    for panel in PLAN["development_panels"]:
        for task_id in panel["task_ids"]:
            instruction = root / "tasks" / task_id / "instruction.md"
            instruction.parent.mkdir(parents=True, exist_ok=True)
            instruction.write_text(
                f"# Fresh R2 public contract\n\nComplete {task_id}.\n",
                encoding="utf-8",
            )
    return root


def _fresh_h0_run(tmp_path: Path) -> Path:
    run = tmp_path / R2_ID / "fresh-h0-source"
    for panel in PLAN["development_panels"]:
        for task_id in panel["task_ids"]:
            attempt = run / "attempts" / task_id
            _write_json(
                attempt / "attempt.json",
                {"attempt_id": f"r2-fresh-{task_id}", "task_id": task_id},
            )
            _write_json(
                attempt / "worker-execution.json",
                {
                    "trace_uri": "raw-trace.jsonl",
                    "final_text_uri": "final.txt",
                    "summary": {
                        "outcome": "completed",
                        "turns": 2,
                        "tool_calls": 1,
                        "tool_errors": 0,
                    },
                },
            )
            (attempt / "raw-trace.jsonl").write_text(
                '{"event":"fresh R2 answer-free H0 work"}\n',
                encoding="utf-8",
            )
            (attempt / "final.txt").write_text(
                "Fresh R2 answer-free H0 final.\n",
                encoding="utf-8",
            )
    return run


def _frozen_h0_handoff(tmp_path: Path, rootless: Path) -> Path:
    inspection = inspect_base_harness(PRIMITIVE)
    runtime = build_selected_runtime(
        inspection["agent_config"],
        worker_model_route="test-worker-route",
        rootless_config=str(rootless.resolve()),
    )
    handoff = tmp_path / R2_ID / "frozen-h0-handoff.json"
    selection = tmp_path / R2_ID / "fresh-selection"
    selection.mkdir(parents=True)
    freeze_base_harness(
        worker_dir=PRIMITIVE,
        run_root=tmp_path / R2_ID / "fresh-adapter-run",
        selected_profile_id=(
            "quant-h0-s6-primitive-v1-fresh-reviewer-policy-v2-r2"
        ),
        selected_runtime=runtime,
        selection_artifact_root=selection,
        handoff_path=handoff,
    )
    return handoff


def _all_file_text(root: Path) -> str:
    return "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.suffix not in {".tar"}
    )


def test_r2_is_fresh_frozen_future_commit_and_not_launch_authorized() -> None:
    assert PLAN["schema_version"] == 2
    assert PLAN["record_kind"] == (
        "qrs_reviewer_policy_v2_engineering_qualification_r2_plan"
    )
    assert PLAN["experiment_id"] == R2_ID
    assert PLAN["status"] == "frozen_not_launch_authorized"
    source = PLAN["source_freeze"]
    assert source["engineering_source_revision"] == "FUTURE_COMMIT"
    assert source["launch_blocked_while_future_commit"] is True
    assert source["code_and_focused_tests_must_be_green"] is True
    assert PLAN["authority"] == {
        "engineering_canary_only": True,
        "launch_authorized": False,
        "paid_or_remote_authority": False,
        "main_authority": False,
        "authorization_condition": PLAN["authority"][
            "authorization_condition"
        ],
    }
    assert PLAN["limits"]["paid_or_remote_authority"] is False
    with pytest.raises(GlobalSchedulerError, match="frozen_launch_authorized"):
        _require_live_launch_authority(PLAN)


def test_r1_is_setup_invalid_and_only_aggregate_budget_sizing_is_reused() -> None:
    independence = PLAN["independence"]
    predecessor = independence["predecessor_r1"]
    assert predecessor["run_id"] == R1_ID
    assert predecessor["classification"] == "setup_invalid_pre_reviewer"
    assert predecessor["scientific_outcome"] is False
    assert predecessor["actual_reviewer_calls"] == 0
    assert predecessor["actual_candidate_worker_cells"] == 0
    assert predecessor["resume_authorized"] is False
    assert predecessor["repeat_authorized"] is False
    assert predecessor["reusable_material_paths"] == []
    assert {
        "scientific_material",
        "artifact_path",
        "candidate",
        "claim",
        "diff",
        "research_state_card",
        "trace",
        "score",
        "verdict",
        "outcome",
        "evidence_access_state",
    } == set(predecessor["forbidden_reuse"])
    for field in (
        "reuses_prior_run",
        "reuses_prior_candidate",
        "reuses_prior_claim",
        "reuses_prior_trace",
        "reuses_prior_access_state",
        "reuses_prior_score_or_verdict",
        "automatic_retry_authorized",
        "automatic_r3_authorized",
    ):
        assert independence[field] is False
    freshness = independence["r2_freshness"]
    assert freshness == {
        "fresh_h0_cells": 4,
        "fresh_proposal_calls": 1,
        "fresh_evidence_access_state": True,
        "fresh_candidate_if_act": True,
        "fresh_reviewer_call_if_package_valid": True,
        "no_predecessor_material_in_inputs": True,
    }
    aggregate = PLAN["limits"]["measured_estimate_basis"][
        "setup_invalid_r1_pre_review_aggregate_only"
    ]
    assert aggregate == {
        "completed_requests": 118,
        "total_tokens": 4148140,
        "provider_cost_usd": 0.150930328,
        "actual_reviewer_calls": 0,
        "actual_candidate_worker_cells": 0,
        "scientific_use": False,
    }


def test_scientific_design_and_sixteen_cell_envelope_match_r1() -> None:
    for field in (
        "phase_order",
        "task_selection",
        "cross_family_workflow_evidence",
        "sealed_main_tasks",
        "reviewer_policy_v2",
        "mandatory_review_gate",
        "matched_gate",
        "full_path_decision",
        "answer_free_carry",
    ):
        r2_value = PLAN[field]
        r1_value = R1[field]
        if field == "mandatory_review_gate":
            r2_value = {
                key: value
                for key, value in r2_value.items()
                if key != "actual_review_call_condition"
            }
        assert r2_value == r1_value
    assert [panel["task_ids"] for panel in PLAN["development_panels"]] == [
        ["crypto-funding-rate-basis-carry"],
        ["cir-bond-pricing"],
        ["copula-equity-fitting", "historical-var-data-prep"],
    ]
    panel_tasks = _panel_evaluation_tasks(
        PLAN, PLAN["development_panels"][0]
    )
    assert panel_tasks == [
        "cir-bond-pricing",
        "crypto-funding-rate-basis-carry",
        "historical-var-data-prep",
    ]
    execution = PLAN["canary_execution"]
    assert execution["actual_max_h0_bank_cells"] == 4
    assert execution["actual_max_panel_matched_cells"] == 12
    assert execution["actual_max_qfbench_cells"] == 4 + 12 == 16
    assert execution["actual_evolver_calls"] == 1
    assert execution["actual_reviewer_calls"] == 1
    condition = execution["reviewer_dispatch_condition"]
    assert "conditionally" in condition
    assert "ABSTAIN or package-invalid HOLD" in condition
    assert execution["stop_after_panel"] == 1
    assert execution["later_panel_dispatch_authorized"] is False
    assert execution["sealed_dispatch_authorized"] is False
    cap = PLAN["limits"]["canary_incremental_cap"]
    hard = PLAN["limits"]["conservative_hard_envelope"]
    assert cap["qfbench_cells"] == hard["qfbench_cells"] == 16
    assert cap["evolver_calls"] == hard["evolver_calls"] == 1
    assert cap["reviewer_calls"] == hard["reviewer_calls"] == 1
    assert cap["provider_cost_usd"] == hard[
        "maximum_provider_cost_usd"
    ] == 4.0


def test_only_three_observed_failure_repairs_are_frozen() -> None:
    repairs = PLAN["r2_observed_failure_repairs"]
    assert repairs["scientific_design_change_from_r1"] is False
    assert repairs["only_engineering_differences"] == [
        "decision_time_trajectory_excerpt_parity_validation",
        "controller_package_error_terminal_hold_and_accounting",
        "collected_unit_health_truth",
    ]
    parity = repairs["decision_time_trajectory_excerpt_parity_validation"]
    assert parity["exact_controller_parity"] is True
    assert parity["maximum_selected_lines"] == 24
    assert parity["maximum_single_range_span"] == 13
    assert parity["maximum_materialized_excerpt_bytes"] == 24000
    assert "before ACT admission or candidate write" in parity[
        "failure_semantics"
    ]
    hold = repairs["controller_package_error_terminal_hold_and_accounting"]
    assert hold["lineage_decision"] == hold["lineage_phase"] == (
        "HOLD_FOR_REFINE"
    )
    assert hold["lineage_status"] == "candidate_hold"
    assert hold["review_verdict"] == hold["coverage"] == "NOT_RUN"
    assert hold["candidate_worker_dispatch"] == 0
    assert hold["outer_stop_reason"] == (
        "STOP_PANEL_REVIEW_PACKAGE_INVALID"
    )
    assert "complete proposal accounting" in hold["state_rule"]
    assert "must not escape as an exception" in hold["state_rule"]
    health = repairs["collected_unit_health_truth"]
    assert health["required"] is True
    assert "Do not collect" in health["rule"]
    assert "unit-query-failed" in health["rule"]
    assert "scheduler result and journal" in health["rule"]
    assert PLAN["engineering_clearance"]["no_automatic_follow_on"].startswith(
        "R2 authorizes no automatic R3"
    )


def test_dry_integration_uses_only_fresh_r2_paths_and_surfaces(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / R2_ID
    contracts = run_root / "public-contracts"
    contract_report = materialize_qrs_public_contracts(
        qfbench_public_source_root=_public_task_source(tmp_path),
        method_plan_path=PLAN_PATH,
        destination=contracts,
    )
    assert contract_report["development_task_count"] == 4
    assert contract_report["sealed_task_count"] == 2

    bank = run_root / "trajectory-bank"
    bank_report = build_trajectory_bank(
        manifest_path=MANIFEST_PATH,
        scheduler_plan_path=PLAN_PATH,
        public_contracts_root=contracts,
        h0_run_dirs=[_fresh_h0_run(tmp_path)],
        destination=bank,
        require_complete=True,
    )
    assert bank_report["complete"] is True
    assert bank_report["valid_runtime_history_count"] == 4
    panel_evidence = (
        bank
        / "evolver-answer-free/panel-evidence/"
        "panel-01-execution_microstructure"
    )
    panel_contract = json.loads(
        (panel_evidence / "contract.json").read_text(encoding="utf-8")
    )
    assert panel_contract["task_ids"] == [
        "cir-bond-pricing",
        "crypto-funding-rate-basis-carry",
        "historical-var-data-prep",
    ]
    assert "copula-equity-fitting" not in panel_contract["task_ids"]

    rootless = run_root / "runtime/rootless.json"
    _write_json(rootless, {})
    handoff = _frozen_h0_handoff(tmp_path, rootless)
    launch = build_qrs_main_launch(
        method_plan_path=PLAN_PATH,
        frozen_h0_handoff_path=handoff,
        scheduler_run_id=R2_ID,
        runtime={
            "python": sys.executable,
            "source_root": ROOT,
            "qfbench_root": run_root / "qfbench",
            "qfbench_manifest": MANIFEST_PATH,
            "rootless_config": rootless,
            "image_set_manifest": run_root / "runtime/images.json",
            "results_dir": run_root / "runs",
            "worker_route": "test-worker-route",
        },
        qfbench_public_manifest=MANIFEST_PATH,
        trajectory_bank_output=bank,
        public_contracts_root=contracts,
        reviewer_config={
            "backend": "openrouter",
            "model": "reviewer/test-model",
            "reasoning_effort": "high",
        },
        output_root=run_root / "launch",
    )
    assert launch["scheduler_run_id"] == R2_ID
    assert R2_ID in launch["scheduler_state_root"]
    assert launch["panel_count"] == 3
    panel_plan = json.loads(
        Path(launch["panel_controller_plans"]["1"]).read_text(
            encoding="utf-8"
        )
    )
    lineage = panel_plan["lineages"][0]
    assert R2_ID in lineage["lineage_id"]
    assert R2_ID in lineage["proposal"]["live_run_id"]
    review = lineage["candidate_information_set_review"]
    assert R2_ID in review["review_id"]
    assert review["optimize_only_sources"] == []
    assert review["answer_free_development_evidence_root"] == str(
        panel_evidence.resolve()
    )

    evolver_input_surface = _all_file_text(panel_evidence)
    review_input_surface = json.dumps(review, sort_keys=True)
    frozen_handoff = json.loads(handoff.read_text(encoding="utf-8"))
    worker_input_surface = _all_file_text(
        Path(frozen_handoff["selected_worker_root"])
    ) + json.dumps(lineage["stages"], sort_keys=True)
    for surface in (
        evolver_input_surface,
        review_input_surface,
        worker_input_surface,
    ):
        assert R1_ID not in surface
        assert "reviewer-policy-v2-qualification-r1" not in surface
        assert "qf-qrs-reviewer-policy-v2-qualification-20260825-r1/" not in surface

    runner_calls: list[dict[str, object]] = []

    def no_dispatch(action):
        runner_calls.append(dict(action))
        raise AssertionError("R2 dry integration must not dispatch")

    state_dir = run_root / "dry-scheduler-state"
    dry_state = run_scheduler(
        PLAN_PATH,
        launch["launch_plan_path"],
        state_dir,
        action_runner=no_dispatch,
        stop_after_phase="IMPORT_H0",
    )
    assert runner_calls == []
    assert dry_state["scheduler_run_id"] == R2_ID
    assert dry_state["phase"] == "H0_BANK"
    assert dry_state["stopped_after_phase"] == "IMPORT_H0"
    assert dry_state["qfbench_cells_accounted"] == 0
    assert dry_state["current_panel_review"] is None
