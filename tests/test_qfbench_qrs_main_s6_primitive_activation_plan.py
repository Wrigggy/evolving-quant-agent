from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path

import scripts.run_qrs_global_scheduler as runner
from qea import qrs_global_scheduler as scheduler
from qea.qrs_main_launch import _anchors, _panels, _validate_public_partition


ROOT = Path(__file__).resolve().parents[1]
BASE_PATH = (
    ROOT
    / "data/breadth/QF_GLOBAL_S6_PRIMITIVE_H0_TRAJECTORY_SCHEDULER_PLAN.json"
)
PLAN_PATH = ROOT / "data/breadth/QF_QRS_MAIN_S6_PRIMITIVE_ACTIVATION_PLAN.json"
MANIFEST_PATH = ROOT / "data/qfbench/MANIFEST_85_BASELINE.json"


def _read(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


BASE = _read(BASE_PATH)
PLAN = _read(PLAN_PATH)


def _eligible_rows() -> list[dict[str, object]]:
    excluded = set(
        PLAN["public_task_partition_rule"]["construct_calibration_exclusions"]
    )
    return [
        row
        for row in _read(MANIFEST_PATH)["baseline"]["primary"]
        if row["reward_kind"] == "binary"
        and row["resource_source"] == "upstream"
        and row["task_id"] not in excluded
    ]


def _sealed_draw(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    selected: list[dict[str, object]] = []
    for domain in sorted({str(row["domain"]) for row in rows}):
        pool = sorted(
            (row for row in rows if row["domain"] == domain),
            key=lambda row: str(row["task_id"]),
        )
        pair = random.Random(f"20260824:sealed-main:{domain}").sample(pool, 2)
        for group, row in zip(
            ("a", "b"), sorted(pair, key=lambda value: str(value["task_id"]))
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


def test_main_activation_is_separate_authorized_qrs_only_and_r2_is_clearance_only(
) -> None:
    activation = PLAN["activation_decision"]
    authority = PLAN["authority"]
    qrs_only = PLAN["qrs_only_boundary"]
    clearance = PLAN["qualification_clearance"]
    nonreuse = PLAN["qualification_and_history_nonreuse"]

    assert PLAN_PATH != BASE_PATH
    assert PLAN["record_kind"] == "qrs_main_activation_launch_method_plan"
    assert PLAN["status"] == "frozen_launch_authorized"
    assert PLAN["source_freeze"]["audited_engineering_revision"] == (
        "4c636f43879d9f156529dcf170361e881b9548e2"
    )
    assert "production executable code is identical" in PLAN["source_freeze"][
        "activation_commit_resolution"
    ]
    assert activation["decision"] == "GO_QRS_ONLY_MAIN_R1"
    assert activation["separately_frozen_from_prospective_plan"] is True
    assert activation["prospective_method_plan"] == str(BASE_PATH.relative_to(ROOT))
    assert activation["activated_method_plan"] == str(PLAN_PATH.relative_to(ROOT))
    assert authority["launch_authorized"] is True
    assert authority["paid_or_remote_authority"] is True
    assert authority["main_authority"] is True
    assert authority["qrs_only"] is True
    assert PLAN["limits"]["paid_or_remote_authority"] is True
    runner._require_live_launch_authority(PLAN)
    scheduler._validate_method(PLAN)
    launch_panels = _panels(PLAN)
    _validate_public_partition(PLAN, launch_panels, _anchors(PLAN))

    assert set(PLAN["arm_identities"]) == {"h0", "candidate_lineage"}
    assert qrs_only["generic_in_main"] is False
    assert qrs_only["ahe_in_main"] is False
    assert qrs_only["qrs_no_state_in_main"] is False
    assert qrs_only["release_target"] == "The final code/library treatment remains QRS-only."
    assert clearance["qualification_run_id"] == (
        "qf-qrs-reviewer-policy-v2-qualification-20260825-r2"
    )
    assert clearance["clearance"] == "PASS_ENGINEERING_PATH_ONLY"
    assert clearance["measured_path"]["panel_decision"] == (
        "RETAIN_NO_STABLE_GAIN"
    )
    assert nonreuse["engineering_clearance_only"].startswith(
        "The R2 qualification verdict is used only"
    )
    forbidden = " ".join(nonreuse["forbidden_main_inputs_from_r2"]).lower()
    for term in (
        "worker copy",
        "h0 trajectory",
        "evolver prompt",
        "candidate diff",
        "worker-visible claim",
        "reviewer input",
        "score",
        "controller state",
    ):
        assert term in forbidden


def test_main_activation_preserves_frozen_public_metadata_partition_and_schedule(
) -> None:
    for key in (
        "phase_order",
        "epistemic_partitions",
        "shared_runtime_freeze",
        "frozen_base_harness_adapter_contract",
        "arm_identities",
        "public_task_partition_rule",
        "sealed_main_tasks",
        "development_panels",
        "cross_family_workflow_evidence",
        "phase0_all_n_h0_development_bank",
        "curriculum_evidence_firewall",
        "phase1_six_panel_curriculum",
        "phase2_feedback_sealed_main",
        "metrics",
        "main_scheduler_h0_answer",
    ):
        assert PLAN[key] == BASE[key]

    rows = _eligible_rows()
    panels = PLAN["development_panels"]
    development = {
        task_id for panel in panels for task_id in panel["task_ids"]
    }
    sealed = {row["task_id"] for row in PLAN["sealed_main_tasks"]}
    eligible = {row["task_id"] for row in rows}

    assert len(rows) == 57
    assert PLAN["sealed_main_tasks"] == _sealed_draw(rows)
    assert len(development) == 45
    assert len(sealed) == 12
    assert development.isdisjoint(sealed)
    assert development | sealed == eligible
    assert Counter(row["domain"] for row in PLAN["sealed_main_tasks"]) == Counter(
        {panel["family"]: 2 for panel in panels}
    )

    anchors = PLAN["cross_family_workflow_evidence"]["anchor_task_by_family"]
    assert len(panels) == len(anchors) == 6
    assert set(anchors) == {panel["family"] for panel in panels}
    for panel in panels:
        assert anchors[panel["family"]] in panel["task_ids"]
        matched_tasks = set(panel["task_ids"]) | {
            task_id
            for family, task_id in anchors.items()
            if family != panel["family"]
        }
        assert len(matched_tasks) == len(panel["task_ids"]) + 5

    primary_cells = len(development)
    primary_cells += sum(4 * (len(panel["task_ids"]) + 5) for panel in panels)
    primary_cells += 4 * len(sealed)
    assert primary_cells == PLAN["limits"]["qfbench_primary_cells"] == 393


def test_main_activation_freezes_policy_v2_dynamic_incumbent_and_sealed_boundary(
) -> None:
    review = PLAN["review_policy_v2_contract"]
    curriculum = PLAN["phase1_six_panel_curriculum"]
    firewall = PLAN["curriculum_evidence_firewall"]
    sealed = PLAN["phase2_feedback_sealed_main"]

    assert review["mandatory_before_candidate_worker"] is True
    assert review["review_scope"] == "answer_free_candidate_information_set"
    assert review["trusted_source_roles"] == [
        "public_contract",
        "public_reference",
        "framework_reference",
        "answer_free_development_observation",
    ]
    assert review["optimize_only_sources"] == []
    assert review["source_caps"] == {
        "maximum_single_answer_free_excerpt_bytes": 24000,
        "maximum_review_package_bytes": 192000,
    }
    assert "Overall PASS and coverage PASS" in review["pass_gate"]
    assert "immutable exact snapshot" in review["exact_snapshot_gate"]
    assert "controller-only" in review["reviewer_visibility"]
    assert "previously accepted answer-free history" in review[
        "accepted_history_carry"
    ]

    assert curriculum["panel_count"] == 6
    assert curriculum["proposal_calls"] == curriculum["reviewer_calls"] == 6
    assert "current-parent-to-proposal" in curriculum["review_rule"]
    assert "cumulative-H0-to-proposal" in curriculum["review_rule"]
    assert "retains the incumbent and continues" in curriculum[
        "promotion_rule"
    ]
    assert "resolved dynamically" in PLAN["arm_identities"][
        "candidate_lineage"
    ]["parent_resolution"]
    denied = " ".join(firewall["never_evolver_visible"]).lower()
    for term in ("official score", "verifier", "expected value", "review verdict", "sealed-main identity"):
        assert term in denied

    assert sealed["task_count"] == 12
    assert sealed["repetitions"] == 2
    assert sealed["primary_cells"] == 48
    assert sealed["fresh_h0_cells"] == sealed["final_candidate_cells"] == 24
    assert "never performance" in sealed["automatic_dispatch"]
    assert "No sealed instruction or outcome" in sealed["feedback_rule"]


def test_main_activation_fresh_ids_caps_and_launch_authority_are_exact() -> None:
    identity = PLAN["fresh_main_identity"]
    launch = PLAN["operational_launch_contract"]
    authority = PLAN["authority"]
    limits = PLAN["limits"]

    run_id = "qf-qrs-main-s6-primitive-20260825-r1"
    assert identity["scheduler_run_id"] == run_id
    assert identity["materialization_run_id"] == f"{run_id}-materialization"
    assert authority["authorized_scheduler_run_ids"] == [run_id]
    assert run_id in identity["h0_bank_run_id_rule"]
    assert run_id in identity["proposal_run_id_rule"]
    assert run_id in identity["review_run_id_rule"]
    assert run_id in identity["matched_run_id_rule"]
    assert run_id in identity["sealed_run_id_rule"]
    assert "No prior run directory" in identity["freshness_rule"]
    assert "exact Main R1" in identity["resume_rule"]
    assert "do not point at the R2" in launch["fresh_h0_handoff"]
    assert launch["method_plan_argument"] == str(PLAN_PATH.relative_to(ROOT))
    assert launch["scheduler_run_id_argument"] == run_id
    assert launch["required_runner_flags"] == ["--approve-external-run"]
    assert set(launch["forbidden_runner_flags"]) == {
        "--stop-after-panel",
        "--stop-after-phase",
    }

    assert authority["authorized_qfbench_primary_cells"] == 393
    assert authority["authorized_qfbench_recovery_cells"] == 3
    assert authority["authorized_maximum_worker_sessions"] == 396
    assert authority["authorized_evolver_calls"] == 6
    assert authority["authorized_reviewer_calls"] == 6
    assert limits["maximum_qfbench_sessions_including_recovery"] == 396
    assert limits["maximum_all_worker_sessions"] == 396
    assert limits["maximum_total_tokens"] == 900000000
    assert limits["maximum_provider_cost_usd"] == 60.0
    assert limits["maximum_wall_seconds"] == 1296000
    assert limits["worker_concurrency"] == 1
    assert limits["verifier_concurrency"] == 1
    assert limits["max_parallel_runs"] == 1
