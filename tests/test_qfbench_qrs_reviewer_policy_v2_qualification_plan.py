from __future__ import annotations

import json
import sys
from pathlib import Path

from qea.frozen_base_harness import (
    build_selected_runtime,
    freeze_base_harness,
    inspect_base_harness,
)
from qea.qfbench_trajectory_bank import build_trajectory_bank
from qea.qrs_global_scheduler import _panel_evaluation_tasks, run_scheduler
from qea.qrs_main_launch import build_qrs_main_launch
from qea.qrs_public_contracts import materialize_qrs_public_contracts


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = (
    ROOT
    / "data/breadth/QF_QRS_REVIEWER_POLICY_V2_QUALIFICATION_PLAN.json"
)
MANIFEST_PATH = ROOT / "data/qfbench/MANIFEST_85_BASELINE.json"
MAIN_PLAN_PATH = (
    ROOT
    / "data/breadth/QF_GLOBAL_S6_PRIMITIVE_H0_TRAJECTORY_SCHEDULER_PLAN.json"
)
PLAN = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
MANIFEST = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
MAIN_PLAN = json.loads(MAIN_PLAN_PATH.read_text(encoding="utf-8"))
EARLIER_MINI_PLAN_PATHS = [
    ROOT / "data/breadth/QF_QRS_MINI_SCHEDULER_CANARY_PLAN.json",
    ROOT / "data/breadth/QF_QRS_MINI_SCHEDULER_CANARY_R2_PLAN.json",
    ROOT / "data/breadth/QF_QRS_MINI_SCHEDULER_CANARY_R3_PLAN.json",
]
EARLIER_MINI_TASKS = {
    task_id
    for path in EARLIER_MINI_PLAN_PATHS
    for panel in json.loads(path.read_text(encoding="utf-8"))["development_panels"]
    for task_id in panel["task_ids"]
}
PRIMITIVE = ROOT / "qea/worker_quant_h0_s6_primitive_v1"


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


def _manifest_rows():
    baseline = MANIFEST["baseline"]
    return {
        row["task_id"]: row
        for row in [*baseline["primary"], *baseline["diagnostic"]]
    }


def test_policy_v2_qualification_is_separate_frozen_and_not_authorized() -> None:
    experiment_id = "qf-qrs-reviewer-policy-v2-qualification-20260825-r1"
    assert PLAN["schema_version"] == 2
    assert PLAN["date"] == "2026-08-25"
    assert PLAN["experiment_id"] == experiment_id
    assert PLAN["status"] == (
        "frozen_not_run_launch_not_authorized_pending_source_commit"
    )
    source = PLAN["source_freeze"]
    assert source["engineering_source_revision"] == f"FUTURE_COMMIT:{experiment_id}"
    assert source["launch_blocked_while_future_commit"] is True
    assert source["code_and_focused_tests_must_be_green"] is True
    authority = PLAN["authority"]
    assert authority == {
        "engineering_canary_only": True,
        "launch_authorized": False,
        "paid_or_remote_authority": False,
        "main_authority": False,
        "authorization_condition": authority["authorization_condition"],
    }


def test_schema_v2_executable_partition_matches_existing_scheduler_contract() -> None:
    assert PLAN["phase_order"] == [
        "import_frozen_primitive_h0",
        "phase0_all_n_h0_development_bank",
        "phase1_six_panel_curriculum",
        "phase2_feedback_sealed_main",
        "terminal_report",
    ]
    partition = PLAN["public_task_partition_rule"]
    assert partition["role"] == "engineering_canary_only"
    assert partition["development_n"] == 4
    panels = PLAN["development_panels"]
    assert [panel["panel_index"] for panel in panels] == [1, 2, 3]
    assert [panel["family"] for panel in panels] == [
        "execution_microstructure",
        "rates_fx_macro",
        "risk_credit",
    ]
    assert panels[0]["task_ids"] == ["crypto-funding-rate-basis-carry"]
    assert panels[1]["task_ids"] == ["cir-bond-pricing"]
    assert panels[2]["task_ids"] == [
        "copula-equity-fitting",
        "historical-var-data-prep",
    ]
    assert panels[1]["parent"] == panels[0]["proposal"]
    assert panels[2]["parent"] == panels[1]["proposal"]
    anchors = PLAN["cross_family_workflow_evidence"][
        "anchor_task_by_family"
    ]
    assert anchors == {
        "execution_microstructure": "crypto-funding-rate-basis-carry",
        "rates_fx_macro": "cir-bond-pricing",
        "risk_credit": "historical-var-data-prep",
    }
    sealed = PLAN["sealed_main_tasks"]
    assert [(row["task_id"], row["group"]) for row in sealed] == [
        ("corporate-action-adjustment", "a"),
        ("fx-forward-cross-rate", "b"),
    ]
    assert all(
        row["role"] == "controller_only_schema_placeholder_never_dispatched"
        for row in sealed
    )
    assert PLAN["phase2_feedback_sealed_main"]["canary_dispatch"] == (
        "forbidden_by_stop_after_panel_1"
    )


def test_no_prior_mini_material_path_or_scientific_state_is_reused() -> None:
    independence = PLAN["independence"]
    assert independence["separately_frozen_policy_qualification"] is True
    assert independence["not_r4"] is True
    assert independence["fresh_run_identity"] is True
    assert independence["prior_mini_material_paths"] == []
    assert independence["prior_mini_material_path_count"] == 0
    for field in (
        "reuses_prior_run",
        "reuses_prior_candidate",
        "reuses_prior_claim",
        "reuses_prior_trace",
        "reuses_prior_access_state",
        "reuses_prior_score_or_verdict",
        "automatic_retry_authorized",
    ):
        assert independence[field] is False
    serialized = json.dumps(PLAN, sort_keys=True).casefold()
    for forbidden_path_fragment in (
        "qf-qrs-mini-scheduler-canary-20260824-r1/",
        "qf-qrs-mini-scheduler-canary-20260825-r2/",
        "qf-qrs-mini-scheduler-canary-20260825-r3/",
        "panel-01-proposal/",
        "panel-01-review/",
    ):
        assert forbidden_path_fragment not in serialized


def test_tasks_follow_exact_public_metadata_rule_and_use_no_sealed_task() -> None:
    selection = PLAN["task_selection"]
    tasks = selection["tasks"]
    expected = [
        (
            "crypto-funding-rate-basis-carry",
            "focus_visible_and_matched",
            "execution_microstructure",
            "medium",
        ),
        (
            "cir-bond-pricing",
            "cross_family_anchor_visible_and_matched",
            "rates_fx_macro",
            "hard",
        ),
        (
            "historical-var-data-prep",
            "cross_family_anchor_visible_and_matched",
            "risk_credit",
            "easy",
        ),
        (
            "copula-equity-fitting",
            "controller_only_bank_sentinel",
            "risk_credit",
            "hard",
        ),
    ]
    assert [
        (row["task_id"], row["role"], row["domain"], row["difficulty"])
        for row in tasks
    ] == expected
    manifest_rows = _manifest_rows()
    construct_exclusions = set(
        MAIN_PLAN["public_task_partition_rule"][
            "construct_calibration_exclusions"
        ]
    )
    sealed = {row["task_id"] for row in MAIN_PLAN["sealed_main_tasks"]}
    assert EARLIER_MINI_TASKS == {
        "13f-amendment-aware-crowding",
        "dupire-local-vol",
        "localvol-barrier",
        "swap-curve-bootstrap-ois",
    }
    for row in tasks:
        metadata = manifest_rows[row["task_id"]]
        for field in (
            "task_id",
            "domain",
            "difficulty",
            "reward_kind",
            "resource_source",
        ):
            assert row[field] == metadata[field]
        eligible_stratum = sorted(
            task_id
            for task_id, candidate in manifest_rows.items()
            if candidate["domain"] == row["domain"]
            and candidate["difficulty"] == row["difficulty"]
            and candidate["reward_kind"] == "binary"
            and candidate["resource_source"] == "upstream"
            and task_id not in construct_exclusions
            and task_id not in sealed
            and task_id not in EARLIER_MINI_TASKS
        )
        assert row["task_id"] == eligible_stratum[0]
        assert row["stratum_rank_by_task_id"] == 1
    task_ids = {row["task_id"] for row in tasks}
    assert task_ids.isdisjoint(sealed)
    assert task_ids.isdisjoint(EARLIER_MINI_TASKS)
    assert selection["fresh_development_task_count"] == 4
    assert selection["sealed_task_count"] == 2
    assert selection["sealed_dispatch_authorized"] is False
    assert selection["score_or_headroom_selected"] is False
    forbidden = set(selection["selector_forbidden_inputs"])
    assert {"prior_or_current_score", "headroom", "researcher_outcome_preference"} <= forbidden


def test_proposal_uses_only_fresh_answer_free_three_family_evidence() -> None:
    proposal = PLAN["proposal"]
    assert proposal["proposal_calls"] == 1
    assert proposal["proposal_scope"] == "workflow_global"
    assert proposal["involved_states"] == [
        "S1",
        "S2",
        "S3",
        "S4",
        "S5",
        "S6",
    ]
    assert proposal["focus_task"] == "crypto-funding-rate-basis-carry"
    assert proposal["visible_anchor_tasks"] == [
        "cir-bond-pricing",
        "historical-var-data-prep",
    ]
    assert proposal["controller_only_task"] == "copula-equity-fitting"
    assert proposal["visible_task_family_count"] == 3
    assert set(proposal["allowed_evolver_sources"]) == {
        "fresh_public_contract",
        "fresh_answer_free_h0_trace",
        "frozen_answer_free_framework_reference",
        "fresh_frozen_parent_material",
    }
    forbidden = set(proposal["forbidden_evolver_sources"])
    assert {
        "official_score_or_reward",
        "optimization_diagnostic",
        "controller_only_copula_trace",
        "prior_run_candidate_claim_trace_or_access_state",
    } <= forbidden
    assert PLAN["primitive_h0_bank"]["fresh_cells"] == 4
    assert "ABSTAIN" in proposal["abstain_semantics"]
    assert "cannot trigger an automatic retry" in proposal["abstain_semantics"]


def test_policy_v2_scopes_and_source_kinds_enforce_the_answer_boundary() -> None:
    policy = PLAN["reviewer_policy_v2"]
    assert policy["allowed_claim_scopes"] == [
        "task_agnostic_harness_policy",
        "task_specific_requirement",
    ]
    assert set(policy["allowed_source_kinds"]) == {
        "public_contract",
        "public_reference",
        "framework_reference",
        "answer_free_development_observation",
    }
    assert "optimize_only_diagnostic" in policy["forbidden_source_kinds"]
    assert policy["optimize_only_sources"] == []
    assert policy["utility_blind"] is True
    task_specific = policy["task_specific_requirement_rule"]
    assert "public_contract or public_reference" in task_specific
    assert "cannot entail a task-specific" in task_specific
    task_agnostic = policy["task_agnostic_harness_policy_rule"]
    assert "framework_reference" in task_agnostic
    assert "answer_free_development_observation" in task_agnostic
    assert "at least two distinct visible task families" in task_agnostic
    observation = policy["development_observation_rule"]
    for forbidden in (
        "score",
        "verifier result",
        "failed property",
        "expected value",
        "official outcome",
        "reconstructed hidden predicate",
    ):
        assert forbidden in observation


def test_mandatory_review_pass_precedes_exact_reviewed_snapshot_dispatch() -> None:
    gate = PLAN["mandatory_review_gate"]
    assert gate["candidate_worker_dispatch_before_review"] == 0
    assert gate["required_overall_verdict"] == "PASS"
    assert gate["required_coverage_verdict"] == "PASS"
    assert gate["all_claims_must_pass"] is True
    assert gate["undeclared_exposures_must_be_empty"] is True
    assert gate["exact_reviewed_snapshot_required"] is True
    assert "Every candidate Worker cell must load exactly that snapshot" in gate[
        "snapshot_rule"
    ]
    assert "REJECT or INCONCLUSIVE" in gate["nonpass_rule"]
    assert "cannot trigger an automatic retry" in gate["nonpass_rule"]
    assert PLAN["matched_gate"][
        "authorized_only_after_mandatory_review_pass"
    ] is True


def test_matched_path_is_exactly_three_tasks_two_arms_two_repetitions() -> None:
    gate = PLAN["matched_gate"]
    assert gate["tasks"] == [
        "crypto-funding-rate-basis-carry",
        "cir-bond-pricing",
        "historical-var-data-prep",
    ]
    assert gate["arms"] == [
        "fresh_primitive_h0_parent",
        "exact_reviewed_policy_v2_candidate",
    ]
    assert gate["repetitions"] == 2
    assert len(gate["tasks"]) * len(gate["arms"]) * gate["repetitions"] == 12
    assert gate["exact_cell_count"] == 12
    assert gate["cell_formula"] == "3 tasks x 2 arms x 2 fresh repetitions"
    assert gate["arm_order"][0]["order"] == list(
        reversed(gate["arm_order"][1]["order"])
    )
    assert gate["fresh_sessions"] is True
    assert gate["matched_runtime"] is True
    assert "wrong-snapshot" in gate["invalid_cell_rule"]
    assert "cannot trigger an automatic retry" in gate["invalid_cell_rule"]


def test_complete_promote_retain_or_rollback_can_clear_engineering_only() -> None:
    decision = PLAN["full_path_decision"]
    assert decision["allowed_complete_decisions"] == [
        "PROMOTE",
        "RETAIN",
        "ROLLBACK",
    ]
    assert decision["utility_gain_required_for_engineering_clearance"] is False
    clearance = PLAN["engineering_clearance"]
    assert clearance["initial_status"] == "NO_GO"
    assert clearance["utility_gain_required"] is False
    assert "complete PROMOTE, RETAIN, or ROLLBACK decision" in clearance[
        "pass_requires"
    ]
    terminal = clearance["abstain_nonpass_invalid_or_cleanup_failure"]
    assert "keep engineering clearance and Main at NO-GO" in terminal
    assert "authorize no automatic retry" in terminal
    assert "does not authorize Main" in clearance["main_after_clearance"]


def test_answer_free_carry_cleanup_accounting_and_zero_work_resume_are_required() -> None:
    carry = PLAN["answer_free_carry"]
    assert carry["required"] is True
    assert carry["worker_visibility"] is False
    assert {"score", "verifier_output", "reviewer_reasoning"} <= set(
        carry["always_forbidden"]
    )
    cleanup = PLAN["accounting_and_cleanup"]
    assert cleanup["request_reconciliation_required"] is True
    assert cleanup["record_completed_requests_tokens_and_cost"] is True
    assert cleanup["exact_run_id_lifecycle_cleanup_required"] is True
    assert "follow_on_dispatch" in cleanup["required_zero_residue"]
    resume = PLAN["same_stop_resume"]
    assert resume["stop_after_panel"] == 1
    for field in (
        "new_actions",
        "new_qfbench_cells",
        "new_evolver_calls",
        "new_reviewer_calls",
        "new_cost",
    ):
        assert resume[field] == 0
    assert {
        "scheduler_state",
        "cost_accounting",
        "reviewed_snapshot",
        "panel_handoff",
        "child_results",
    } <= set(resume["must_preserve_exactly"])


def test_measured_estimate_and_conservative_envelope_are_internally_consistent() -> None:
    limits = PLAN["limits"]
    assert limits["phase0_h0_cells"] == 4
    assert limits["panel_gate_parent_cells"] == 20
    assert limits["panel_gate_proposal_cells"] == 20
    assert limits["sealed_main_h0_cells"] == 4
    assert limits["sealed_main_final_candidate_cells"] == 4
    assert limits["qfbench_primary_cells"] == 52
    assert limits["evolver_calls"] == limits["reviewer_calls"] == 3
    assert limits["maximum_qfbench_recovery_cells"] == 0
    assert limits["maximum_qfbench_sessions_including_recovery"] == 52
    assert limits["maximum_all_worker_sessions"] == 52
    assert limits["maximum_worker_turn_iterations"] == 52 * 60
    assert limits["paid_or_remote_authority"] is False
    basis = limits["measured_estimate_basis"]
    assert "retained final mini R3" in basis["provenance"]
    assert "only for budget sizing" in basis["provenance"]
    assert "No R3 artifact path or scientific material" in basis["provenance"]
    h0 = basis["four_fresh_h0_cells"]
    proposal = basis["one_workflow_global_proposal"]
    reviewer = basis["one_reviewer_call"]
    estimate = limits["measured_full_path_estimate"]
    assert estimate["qfbench_cells"] == 4 + 12
    assert estimate["evolver_calls"] == 1
    assert estimate["reviewer_calls"] == 1
    assert estimate["completed_requests"] == (
        h0["completed_requests"]
        + proposal["completed_requests"]
        + reviewer["completed_requests"]
        + 12 * h0["completed_requests"] // 4
    )
    assert estimate["total_tokens"] == (
        h0["total_tokens"]
        + proposal["total_tokens"]
        + reviewer["scheduler_accounted_tokens"]
        + 3 * h0["total_tokens"]
    )
    expected_cost = (
        h0["provider_cost_usd"]
        + proposal["provider_cost_usd"]
        + reviewer["provider_cost_usd"]
        + 3 * h0["provider_cost_usd"]
    )
    assert abs(estimate["provider_cost_usd"] - expected_cost) < 1e-12
    hard = limits["conservative_hard_envelope"]
    assert hard["qfbench_cells"] == 16
    assert hard["maximum_qfbench_recovery_cells"] == 0
    assert hard["maximum_all_worker_sessions"] == 16
    assert hard["maximum_worker_turn_iterations"] == 16 * 60
    assert hard["evolver_calls"] == hard["reviewer_calls"] == 1
    assert hard["maximum_completed_requests"] > estimate["completed_requests"]
    assert hard["maximum_total_tokens"] > estimate["total_tokens"]
    assert hard["maximum_provider_cost_usd"] > estimate["provider_cost_usd"]
    assert hard["worker_concurrency"] == 1
    assert hard["verifier_concurrency"] == 1
    assert hard["max_parallel_runs"] == 1
    assert hard["hard_stop_on_any_cap"] is True


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _public_task_source(tmp_path: Path) -> Path:
    root = tmp_path / "qfbench-public"
    for panel in PLAN["development_panels"]:
        for task_id in panel["task_ids"]:
            instruction = root / "tasks" / task_id / "instruction.md"
            instruction.parent.mkdir(parents=True, exist_ok=True)
            instruction.write_text(
                f"# Public contract\n\nComplete the public task {task_id}.\n",
                encoding="utf-8",
            )
    return root


def _fresh_h0_run(tmp_path: Path) -> Path:
    run = tmp_path / "fresh-h0-run"
    for panel in PLAN["development_panels"]:
        for task_id in panel["task_ids"]:
            attempt = run / "attempts" / task_id
            _write_json(
                attempt / "attempt.json",
                {"attempt_id": f"fresh-{task_id}", "task_id": task_id},
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
                '{"event":"fresh answer-free H0 work"}\n',
                encoding="utf-8",
            )
            (attempt / "final.txt").write_text(
                "Fresh answer-free H0 final.\n",
                encoding="utf-8",
            )
    return run


def _frozen_h0_handoff(tmp_path: Path, rootless: Path) -> Path:
    selection = tmp_path / "external-selection"
    selection.mkdir()
    inspection = inspect_base_harness(PRIMITIVE)
    runtime = build_selected_runtime(
        inspection["agent_config"],
        worker_model_route="test-worker-route",
        rootless_config=str(rootless.resolve()),
    )
    handoff = tmp_path / "frozen-h0-handoff.json"
    freeze_base_harness(
        worker_dir=PRIMITIVE,
        run_root=tmp_path / "adapter-run",
        selected_profile_id="primitive-policy-v2-r1",
        selected_runtime=runtime,
        selection_artifact_root=selection,
        handoff_path=handoff,
    )
    return handoff


def test_existing_materializers_and_scheduler_accept_dry_schema_v2_path(
    tmp_path: Path,
) -> None:
    contracts = tmp_path / "public-contracts"
    contract_report = materialize_qrs_public_contracts(
        qfbench_public_source_root=_public_task_source(tmp_path),
        method_plan_path=PLAN_PATH,
        destination=contracts,
    )
    assert contract_report["development_task_count"] == 4
    assert contract_report["sealed_task_count"] == 2
    observed_contract_tasks = {
        path.name for path in contracts.iterdir() if path.is_dir()
    }
    assert observed_contract_tasks == {
        "crypto-funding-rate-basis-carry",
        "cir-bond-pricing",
        "copula-equity-fitting",
        "historical-var-data-prep",
    }
    assert not any(
        (contracts / row["task_id"]).exists()
        for row in PLAN["sealed_main_tasks"]
    )

    bank = tmp_path / "trajectory-bank"
    bank_report = build_trajectory_bank(
        manifest_path=MANIFEST_PATH,
        scheduler_plan_path=PLAN_PATH,
        public_contracts_root=contracts,
        h0_run_dirs=[_fresh_h0_run(tmp_path)],
        destination=bank,
        require_complete=True,
    )
    assert bank_report["complete"] is True
    assert bank_report["expected_task_count"] == 4
    panel_one = json.loads(
        (
            bank
            / "evolver-answer-free/panels/panel-01-execution_microstructure.json"
        ).read_text(encoding="utf-8")
    )
    assert panel_one["visible_task_ids"] == [
        "cir-bond-pricing",
        "crypto-funding-rate-basis-carry",
        "historical-var-data-prep",
    ]
    assert panel_one["visible_family_count"] == 3
    assert "copula-equity-fitting" not in panel_one["visible_task_ids"]
    generated_bank_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in bank.rglob("*")
        if path.is_file()
    )
    assert all(
        row["task_id"] not in generated_bank_text
        for row in PLAN["sealed_main_tasks"]
    )

    rootless = tmp_path / "runtime/rootless.json"
    _write_json(rootless, {})
    handoff = _frozen_h0_handoff(tmp_path, rootless)
    launch = build_qrs_main_launch(
        method_plan_path=PLAN_PATH,
        frozen_h0_handoff_path=handoff,
        scheduler_run_id=PLAN["experiment_id"],
        runtime={
            "python": sys.executable,
            "source_root": ROOT,
            "qfbench_root": tmp_path / "qfbench",
            "qfbench_manifest": MANIFEST_PATH,
            "rootless_config": rootless,
            "image_set_manifest": tmp_path / "runtime/images.json",
            "results_dir": tmp_path / "runs",
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
        output_root=tmp_path / "launch",
    )
    assert launch["panel_count"] == 3
    assert launch["builder_dispatched_children"] is False
    assert set(launch["panel_controller_plans"]) == {"1", "2", "3"}
    panel_one_controller = json.loads(
        Path(launch["panel_controller_plans"]["1"]).read_text(encoding="utf-8")
    )
    public_catalog = panel_one_controller["lineages"][0][
        "candidate_information_set_review"
    ]["public_source_catalog"]
    assert {
        Path(source["source_path"]).parent.name for source in public_catalog
    } == {
        "crypto-funding-rate-basis-carry",
        "cir-bond-pricing",
        "historical-var-data-prep",
    }

    runner_calls: list[dict[str, object]] = []

    def no_dispatch(action):
        runner_calls.append(dict(action))
        raise AssertionError("dry integration must not dispatch")

    dry_state = run_scheduler(
        PLAN_PATH,
        launch["launch_plan_path"],
        tmp_path / "dry-scheduler-state",
        action_runner=no_dispatch,
        stop_after_phase="IMPORT_H0",
    )
    assert runner_calls == []
    assert dry_state["phase"] == "H0_BANK"
    assert dry_state["stopped_after_phase"] == "IMPORT_H0"

    panel_one_tasks = _panel_evaluation_tasks(
        PLAN, PLAN["development_panels"][0]
    )
    assert panel_one_tasks == [
        "cir-bond-pricing",
        "crypto-funding-rate-basis-carry",
        "historical-var-data-prep",
    ]
    canary = PLAN["canary_execution"]
    calculated_matched_cells = 2 * 2 * len(panel_one_tasks)
    assert calculated_matched_cells == canary["actual_max_panel_matched_cells"] == 12
    assert 4 + calculated_matched_cells == canary["actual_max_qfbench_cells"] == 16
    assert canary["stop_after_panel"] == 1
    assert canary["sealed_dispatch_authorized"] is False
    assert canary["later_panel_dispatch_authorized"] is False


def test_qualification_grants_no_main_reuse_or_scientific_claim() -> None:
    reuse = PLAN["main_reuse"]
    assert all(value is False for value in reuse.values())
    assert PLAN["authority"]["main_authority"] is False
    claim = PLAN["claim_boundary"]["does_not_support"]
    for boundary in (
        "not R4",
        "Main result",
        "benchmark gain",
        "reusable candidate",
        "stable promotion",
        "sealed evaluation",
        "representative task estimate",
        "No canary material is reusable in Main",
    ):
        assert boundary in claim
    serialized = " ".join(_strings(PLAN))
    assert "task-agnostic harness-policy hypotheses" in serialized
    assert "Review PASS establishes admissibility, not truth or utility" in serialized
    assert "utility gain required for engineering clearance" not in serialized.casefold()
