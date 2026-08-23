from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from scripts.run_qfbench_campaign import (
    _build_child_plan,
    _new_state,
    build_parser as build_campaign_parser,
    run_campaign,
)
from scripts.run_qfbench_lineage_controller import (
    build_child_argv,
    build_proposal_argv,
)


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = (
    ROOT / "data/breadth/QF_FINAL_H0_MATCHED_GENERIC_QRS_CANARY_PLAN.json"
)


def _plan() -> dict[str, object]:
    return json.loads(PLAN_PATH.read_text())


def _arm(plan: dict[str, object], arm_id: str) -> dict[str, object]:
    return next(value for value in plan["arms"] if value["arm_id"] == arm_id)


def _normalized_treatment(arm: dict[str, object]) -> dict[str, object]:
    value = deepcopy(arm)
    value.pop("arm_id")
    value.pop("treatment")
    for round_spec in value["rounds"]:
        proposal = round_spec["lineage"]["proposal"]
        proposal["candidate_version"] = "<arm-labelled-candidate>"
        proposal["evidence"] = "<matched-arm-evidence>"
        proposal["arm"] = "<arm-label>"
        for stage in round_spec["lineage"]["stages"]:
            stage["candidate_arm"] = "<arm-label>"
    return value


def _arm_arguments(argv: tuple[str, ...]) -> list[str]:
    return [
        argv[index + 1]
        for index, value in enumerate(argv)
        if value == "--arm"
    ]


def _terminal_child(plan_path: Path, decision: str) -> dict[str, object]:
    child_plan = json.loads(plan_path.read_text())
    lineage = child_plan["lineages"][0]
    candidate = {
        "version": lineage["proposal"]["candidate_version"],
        "worker_dir": f"/candidate/{lineage['lineage_id']}",
    }
    return {
        "schema_version": 1,
        "controller_run_id": child_plan["controller_run_id"],
        "lineages": {
            lineage["lineage_id"]: {
                "phase": "FROZEN",
                "decision": decision,
                "current_parent": (
                    candidate if decision == "PROMOTE" else lineage["parent"]
                ),
                "candidate": candidate,
                "observations": {
                    stage["name"]: {
                        "task_id": stage["task_id"],
                        "run_id": stage["live_run_id"],
                        "report_path": f"/reports/{stage['live_run_id']}.json",
                    }
                    for stage in lineage["stages"]
                },
                "cost": {
                    "provider_cost_usd": "0.01",
                    "completed_requests": 1,
                    "total_tokens": 100,
                },
            }
        },
    }


def test_final_h0_canary_schema_budget_refs_and_sealing_boundary() -> None:
    plan = _plan()

    assert plan["schema_version"] == 1
    assert plan["status"] == "prepared_not_run"
    assert plan["campaign_run_id"] == (
        "qf-final-h0-matched-generic-qrs-20260824-r1"
    )
    assert plan["execution"]["round_order"] == [
        "holdings-r1",
        "localvol-r2",
    ]
    assert plan["execution"]["sealed_evaluation_included"] is False
    assert plan["execution"]["sealed_feedback_allowed"] is False
    assert plan["limits"] == {
        "candidate_versions_per_round": 1,
        "max_rounds_per_arm": 2,
        "max_evolver_proposals": 4,
        "max_new_initial_parent_worker_sessions": 0,
        "max_candidate_worker_sessions": 12,
        "max_candidate_verifier_executions": 12,
        "provider_cost_usd": 0.55,
        "arm_provider_cost_usd": 1.1,
        "campaign_provider_cost_usd": 2.2,
        "wall_time_hours": 8,
    }
    assert plan["execution"]["wall_time_enforcement"] == (
        "systemd RuntimeMaxSec=8h"
    )
    assert plan["execution"]["wrapper_wall_time_field_role"] == (
        "metadata_only"
    )

    arms = {_arm(plan, arm_id)["arm_id"]: _arm(plan, arm_id) for arm_id in (
        "generic",
        "qrs",
    )}
    assert set(arms) == {"generic", "qrs"}
    assert {
        json.dumps(value["initial_incumbent"], sort_keys=True)
        for value in arms.values()
    } == {
        json.dumps(
            {
                "version": "quant-h0",
                "worker_dir": (
                    "/data/qea-julius-storage/deploy/"
                    "qf-final-h0-matched-20260824-r1/qea/worker_quant_h0"
                ),
            },
            sort_keys=True,
        )
    }

    expected_reference_keys = {
        ("target", "13f-amendment-aware-crowding"),
        ("repeat", "13f-amendment-aware-crowding"),
        ("protection", "brinson-sector-attribution"),
        ("target", "dupire-local-vol"),
        ("repeat", "dupire-local-vol"),
        ("protection", "localvol-barrier"),
    }
    reference_lists = []
    for arm in arms.values():
        references = arm["initial_selection_references"]
        assert len(references) == 6
        assert {(value["stage"], value["task_id"]) for value in references} == (
            expected_reference_keys
        )
        assert {value["reference_version"] for value in references} == {
            "quant-h0"
        }
        assert {value["arm"] for value in references} == {"parent"}
        reference_lists.append(references)
        for round_spec in arm["rounds"]:
            assert round_spec["lineage"]["repeat_consistency_policy"] == (
                "resolved_property_footprint_v1"
            )
            assert (
                round_spec["lineage"]["quantitative_protection_review"]
                is False
            )
        assert arm["rounds"][0]["on_hold"] == (
            "retain_incumbent_and_continue"
        )
        assert "on_hold" not in arm["rounds"][1]
    assert reference_lists[0] == reference_lists[1]


def test_generic_and_qrs_are_matched_except_evidence_and_arm_labels() -> None:
    plan = _plan()
    generic = _arm(plan, "generic")
    qrs = _arm(plan, "qrs")

    assert _normalized_treatment(generic) == _normalized_treatment(qrs)
    assert [
        value["lineage"]["proposal"]["arm"] for value in generic["rounds"]
    ] == ["generic", "generic"]
    assert [
        value["lineage"]["proposal"]["arm"] for value in qrs["rounds"]
    ] == ["quant-state", "quant-state"]
    for generic_round, qrs_round in zip(generic["rounds"], qrs["rounds"]):
        generic_evidence = generic_round["lineage"]["proposal"]["evidence"]
        qrs_evidence = qrs_round["lineage"]["proposal"]["evidence"]
        assert "/generic/" in generic_evidence
        assert "/quant-state/" in qrs_evidence
        assert generic_evidence.rsplit("/generic/", 1)[0] == (
            qrs_evidence.rsplit("/quant-state/", 1)[0]
        )
        assert generic_evidence.rsplit("/", 1)[1] == qrs_evidence.rsplit(
            "/", 1
        )[1]


def test_campaign_child_argv_uses_initial_refs_then_paired_fallback() -> None:
    plan = _plan()
    campaign_state = _new_state(plan)

    for arm_id, proposal_arm in (("generic", "generic"), ("qrs", "quant-state")):
        arm = _arm(plan, arm_id)
        arm_state = campaign_state["arms"][arm_id]
        first_round = arm["rounds"][0]
        first = _build_child_plan(
            plan,
            arm_id=arm_id,
            arm_state=arm_state,
            round_spec=first_round,
        )
        lineage = first["lineages"][0]
        stages = lineage["stages"]
        assert [value["selection_reference"]["id"] for value in stages] == [
            "main0b-holdings-target-parent-20260823-r1",
            "main0b-holdings-repeat-parent-20260823-r1",
            "main0-thin-brinson-parent-20260822-r1",
        ]

        proposal_argv = build_proposal_argv(
            first,
            lineage,
            lineage["proposal"],
            approve_external_run=True,
        )
        assert proposal_argv[proposal_argv.index("--arm") + 1] == proposal_arm
        assert proposal_argv[proposal_argv.index("--backbone") + 1].endswith(
            "/qea/worker_quant_h0"
        )

        candidate_lineage = {
            **lineage,
            "candidate": {
                "version": lineage["proposal"]["candidate_version"],
                "worker_dir": f"/candidate/{arm_id}/holdings",
            },
        }
        target_argv = build_child_argv(
            first,
            candidate_lineage,
            stages[0],
            approve_external_run=True,
        )
        assert _arm_arguments(target_argv) == [
            f"{proposal_arm}=/candidate/{arm_id}/holdings"
        ]

        initial_second = _build_child_plan(
            plan,
            arm_id=arm_id,
            arm_state=arm_state,
            round_spec=arm["rounds"][1],
        )
        assert [
            value["selection_reference"]["id"]
            for value in initial_second["lineages"][0]["stages"]
        ] == [
            "main0b-localvol-target-parent-20260823-r1",
            "main0b-localvol-repeat-parent-20260823-r1",
            "main0b-localvol-protection-parent-20260823-r1",
        ]

        promoted_state = deepcopy(arm_state)
        promoted_state["current_incumbent"] = {
            "version": f"{arm_id}-holdings-c1",
            "worker_dir": f"/candidate/{arm_id}/holdings",
        }
        promoted_state["mutation_parent"] = deepcopy(
            promoted_state["current_incumbent"]
        )
        second = _build_child_plan(
            plan,
            arm_id=arm_id,
            arm_state=promoted_state,
            round_spec=arm["rounds"][1],
        )
        second_lineage = second["lineages"][0]
        second_target = second_lineage["stages"][0]
        assert second_lineage["parent"] == promoted_state["current_incumbent"]
        assert second_target["parent_arm"] == "parent"
        assert "selection_reference" not in second_target

        second_candidate = {
            **second_lineage,
            "candidate": {
                "version": second_lineage["proposal"]["candidate_version"],
                "worker_dir": f"/candidate/{arm_id}/localvol",
            },
        }
        fallback_argv = build_child_argv(
            second,
            second_candidate,
            second_target,
            approve_external_run=True,
        )
        assert _arm_arguments(fallback_argv) == [
            f"parent=/candidate/{arm_id}/holdings",
            f"{proposal_arm}=/candidate/{arm_id}/localvol",
        ]

    parsed = build_campaign_parser().parse_args(
        [
            "--plan",
            str(PLAN_PATH),
            "--state-dir",
            "/tmp/qf-final-h0-canary",
            "--arm",
            "generic",
            "--arm",
            "qrs",
        ]
    )
    assert parsed.arm == ["generic", "qrs"]


def test_fake_campaign_promotes_holdings_then_pairs_localvol(tmp_path) -> None:
    plan = _plan()
    calls: list[dict[str, object]] = []

    def fake_controller(plan_path, state_dir, **kwargs):
        calls.append(json.loads(Path(plan_path).read_text()))
        decision = (
            "PROMOTE" if str(plan_path).endswith("holdings-r1/plan.json") else "ROLLBACK"
        )
        return _terminal_child(Path(plan_path), decision)

    result = run_campaign(
        PLAN_PATH,
        tmp_path / "campaign-state",
        child_controller=fake_controller,
    )

    assert result["status"] == "COMPLETE"
    assert len(calls) == 4
    by_id = {value["controller_run_id"]: value for value in calls}
    for arm_id, proposal_arm in (("generic", "generic"), ("qrs", "quant-state")):
        holdings_id = (
            "qf-final-h0-matched-generic-qrs-20260824-r1-"
            f"{arm_id}-holdings-r1"
        )
        localvol_id = (
            "qf-final-h0-matched-generic-qrs-20260824-r1-"
            f"{arm_id}-localvol-r2"
        )
        holdings = by_id[holdings_id]["lineages"][0]
        assert [
            stage["selection_reference"]["id"]
            for stage in holdings["stages"]
        ] == [
            "main0b-holdings-target-parent-20260823-r1",
            "main0b-holdings-repeat-parent-20260823-r1",
            "main0-thin-brinson-parent-20260822-r1",
        ]
        localvol = by_id[localvol_id]["lineages"][0]
        assert localvol["parent"] == {
            "version": holdings["proposal"]["candidate_version"],
            "worker_dir": f"/candidate/{arm_id}-holdings-r1",
        }
        assert all(
            stage["parent_arm"] == "parent" for stage in localvol["stages"]
        )
        assert all(
            "selection_reference" not in stage for stage in localvol["stages"]
        )
        assert localvol["proposal"]["arm"] == proposal_arm
        assert localvol["repeat_consistency_policy"] == (
            "resolved_property_footprint_v1"
        )
