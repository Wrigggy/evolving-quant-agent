from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.run_qfbench_campaign import run_campaign


def _lineage(
    candidate: str,
    *,
    evidence: str = "evidence/base",
    target_task: str = "target-task",
    protection_task: str = "protection-task",
):
    return {
        "proposal": {
            "candidate_version": candidate,
            "evidence": evidence,
            "evolver_dir": "evolver",
            "arm": "quant-state",
        },
        "stages": [
            {
                "name": "target",
                "task_id": target_task,
                "candidate_arm": f"{candidate}-target",
            },
            {
                "name": "repeat",
                "task_id": target_task,
                "candidate_arm": f"{candidate}-repeat",
            },
            {
                "name": "protection",
                "task_id": protection_task,
                "candidate_arm": f"{candidate}-protection",
            },
        ],
    }


def _plan(tmp_path: Path, rounds, *, arm_cost_cap=None):
    value = {
        "schema_version": 1,
        "campaign_run_id": "campaign-01",
        "mode": "live",
        "runtime": {
            "worker_route": "worker-route",
            "python": "python",
        },
        "limits": {"provider_cost_usd": 1},
        "arms": [
            {
                "arm_id": "qrs",
                "initial_incumbent": {
                    "version": "h0",
                    "worker_dir": "workers/h0",
                },
                "initial_selection_references": [
                    {
                        "stage": "target",
                        "task_id": "target-task",
                        "id": "h0-target",
                        "report_path": "reports/h0-target.json",
                        "arm": "h0",
                    },
                    {
                        "stage": "repeat",
                        "task_id": "target-task",
                        "id": "h0-repeat",
                        "report_path": "reports/h0-repeat.json",
                        "arm": "h0-repeat",
                    },
                    {
                        "stage": "protection",
                        "task_id": "protection-task",
                        "id": "h0-protection",
                        "report_path": "reports/h0-protection.json",
                        "arm": "h0",
                    },
                ],
                "rounds": rounds,
            }
        ],
    }
    if arm_cost_cap is not None:
        value["limits"]["arm_provider_cost_usd"] = arm_cost_cap
    path = tmp_path / "campaign-plan.json"
    path.write_text(json.dumps(value))
    return path


def _terminal(plan_path: Path, decision: str, *, cost="0.01"):
    plan = json.loads(plan_path.read_text())
    lineage = plan["lineages"][0]
    candidate_version = lineage["proposal"]["candidate_version"]
    candidate = {
        "version": candidate_version,
        "worker_dir": f"workers/{candidate_version}",
    }
    observations = {}
    for stage in lineage["stages"]:
        observations[stage["name"]] = {
            "task_id": stage["task_id"],
            "run_id": stage["live_run_id"],
            "report_path": f"reports/{stage['live_run_id']}.json",
        }
    return {
        "schema_version": 1,
        "controller_run_id": plan["controller_run_id"],
        "lineages": {
            lineage["lineage_id"]: {
                "phase": (
                    "HOLD_FOR_REFINE"
                    if decision == "HOLD_FOR_REFINE"
                    else "FROZEN"
                ),
                "decision": decision,
                "current_parent": (
                    candidate if decision == "PROMOTE" else lineage["parent"]
                ),
                "candidate": candidate,
                "observations": observations,
                "cost": {
                    "provider_cost_usd": cost,
                    "completed_requests": 2,
                    "total_tokens": 100,
                },
            }
        },
    }


def test_promotion_updates_next_parent_and_task_references_then_resume_is_noop(
    tmp_path,
):
    plan_path = _plan(
        tmp_path,
        [
            {"round_id": "r1", "lineage": _lineage("c1")},
            {"round_id": "r2", "lineage": _lineage("c2")},
        ],
    )
    calls = []

    def child(plan_path, state_dir, **kwargs):
        calls.append(json.loads(Path(plan_path).read_text()))
        decision = "PROMOTE" if len(calls) == 1 else "ROLLBACK"
        return _terminal(Path(plan_path), decision)

    result = run_campaign(plan_path, tmp_path / "state", child_controller=child)

    assert result["status"] == "COMPLETE"
    assert result["cost"] == {
        "provider_cost_usd": "0.02",
        "completed_requests": 4,
        "total_tokens": 200,
    }
    assert result["arms"]["qrs"]["current_incumbent"]["version"] == "c1"
    assert len(calls) == 2
    assert calls[0]["controller_run_id"] == "campaign-01-qrs-r1"
    assert calls[0]["lineages"][0]["proposal"]["live_run_id"] == (
        "campaign-01-qrs-r1-proposal"
    )
    first_stages = calls[0]["lineages"][0]["stages"]
    assert first_stages[0]["selection_reference"]["id"] == "h0-target"
    assert first_stages[0]["selection_reference"]["report_path"] == (
        "reports/h0-target.json"
    )
    assert first_stages[1]["selection_reference"]["id"] == "h0-repeat"
    assert first_stages[1]["selection_reference"]["report_path"] == (
        "reports/h0-repeat.json"
    )
    second = calls[1]["lineages"][0]
    assert second["parent"]["version"] == "c1"
    target = second["stages"][0]
    repeat = second["stages"][1]
    protection = second["stages"][2]
    assert target["parent_arm"] == "c1-target"
    assert target["selection_reference"]["id"] == (
        "campaign-01-qrs-r1-target"
    )
    assert target["selection_reference"]["reference_version"] == "c1"
    assert repeat["parent_arm"] == "c1-repeat"
    assert repeat["selection_reference"]["id"] == (
        "campaign-01-qrs-r1-repeat"
    )
    assert repeat["selection_reference"]["report_path"] == (
        "reports/campaign-01-qrs-r1-repeat.json"
    )
    assert protection["parent_arm"] == "c1-protection"
    assert protection["selection_reference"]["id"] == (
        "campaign-01-qrs-r1-protection"
    )

    resumed = run_campaign(
        plan_path, tmp_path / "state", child_controller=child
    )
    assert resumed == result
    assert len(calls) == 2


def test_hold_runs_one_evidence_grounded_refinement_against_incumbent(
    tmp_path,
):
    plan_path = _plan(
        tmp_path,
        [
            {"round_id": "r1", "lineage": _lineage("c1")},
            {
                "round_id": "r1-refine",
                "kind": "refinement",
                "evidence_from_round": "r1",
                "lineage": _lineage("c2", evidence="evidence/r1"),
            },
        ],
    )
    calls = []

    def child(plan_path, state_dir, **kwargs):
        calls.append(json.loads(Path(plan_path).read_text()))
        return _terminal(Path(plan_path), "HOLD_FOR_REFINE")

    result = run_campaign(plan_path, tmp_path / "state", child_controller=child)

    arm = result["arms"]["qrs"]
    assert result["status"] == "ATTENTION"
    assert arm["status"] == "HOLD_FOR_REFINE"
    assert arm["refinement_used"] is True
    assert len(calls) == 2
    refinement = calls[1]["lineages"][0]
    assert refinement["parent"] == {
        "version": "c1",
        "worker_dir": "workers/c1",
    }
    assert refinement["stages"][0]["selection_reference"] == {
        "id": "h0-target",
        "report_path": "reports/h0-target.json",
        "reference_version": "h0",
        "task_id": "target-task",
        "worker_route": "worker-route",
        "worker_budget": "normal",
    }

    run_campaign(plan_path, tmp_path / "state", child_controller=child)
    assert len(calls) == 2


def test_conditional_refinement_is_skipped_after_rollback(tmp_path):
    plan_path = _plan(
        tmp_path,
        [
            {"round_id": "r1", "lineage": _lineage("c1")},
            {
                "round_id": "r1-refine",
                "kind": "refinement",
                "evidence_from_round": "r1",
                "lineage": _lineage("c1b", evidence="evidence/r1"),
            },
            {"round_id": "r2", "lineage": _lineage("c2")},
        ],
    )
    calls = []

    def child(plan_path, state_dir, **kwargs):
        calls.append(json.loads(Path(plan_path).read_text()))
        return _terminal(Path(plan_path), "ROLLBACK")

    result = run_campaign(plan_path, tmp_path / "state", child_controller=child)

    rounds = result["arms"]["qrs"]["round_results"]
    assert [value["decision"] for value in rounds] == [
        "ROLLBACK",
        "SKIPPED_NO_HOLD",
        "ROLLBACK",
    ]
    assert len(calls) == 2
    assert calls[1]["lineages"][0]["parent"]["version"] == "h0"


def test_resume_imports_terminal_child_written_before_campaign_checkpoint(
    tmp_path,
):
    plan_path = _plan(
        tmp_path,
        [{"round_id": "r1", "lineage": _lineage("c1")}],
    )

    def completed_then_interrupted(plan_path, state_dir, **kwargs):
        result = _terminal(Path(plan_path), "ROLLBACK")
        output = Path(state_dir) / "CONTROLLER-RESULT.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result))
        raise RuntimeError("campaign process interrupted after child completion")

    with pytest.raises(RuntimeError, match="interrupted"):
        run_campaign(
            plan_path,
            tmp_path / "state",
            child_controller=completed_then_interrupted,
        )

    calls = 0

    def must_not_run(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("terminal child should be imported, not rerun")

    result = run_campaign(
        plan_path, tmp_path / "state", child_controller=must_not_run
    )
    assert result["status"] == "COMPLETE"
    assert result["cost"]["provider_cost_usd"] == "0.01"
    assert calls == 0

    resumed = run_campaign(
        plan_path, tmp_path / "state", child_controller=must_not_run
    )
    assert resumed["cost"]["provider_cost_usd"] == "0.01"
    assert resumed["cost"]["completed_requests"] == 2
    assert calls == 0


def test_new_task_family_runs_paired_then_becomes_incumbent_reference(tmp_path):
    plan_path = _plan(
        tmp_path,
        [
            {"round_id": "family-a", "lineage": _lineage("c1")},
            {
                "round_id": "family-b",
                "lineage": _lineage(
                    "c2",
                    target_task="new-target",
                    protection_task="new-protection",
                ),
            },
        ],
    )
    calls = []

    def child(plan_path, state_dir, **kwargs):
        calls.append(json.loads(Path(plan_path).read_text()))
        return _terminal(Path(plan_path), "PROMOTE")

    result = run_campaign(plan_path, tmp_path / "state", child_controller=child)

    second_stages = calls[1]["lineages"][0]["stages"]
    assert all(stage["parent_arm"] == "parent" for stage in second_stages)
    assert all("selection_reference" not in stage for stage in second_stages)
    assert calls[1]["lineages"][0]["parent"]["version"] == "c1"
    references = result["arms"]["qrs"]["selection_references"]
    assert references["repeat::new-target"] == {
        "stage": "repeat",
        "task_id": "new-target",
        "id": "campaign-01-qrs-family-b-repeat",
        "report_path": "reports/campaign-01-qrs-family-b-repeat.json",
        "arm": "c2-repeat",
        "reference_version": "c2",
    }
    assert references["target::new-target"]["id"] == (
        "campaign-01-qrs-family-b-target"
    )
    assert references["protection::new-protection"]["reference_version"] == (
        "c2"
    )


def test_arm_cost_cap_stops_before_next_child_at_round_boundary(tmp_path):
    plan_path = _plan(
        tmp_path,
        [
            {"round_id": "r1", "lineage": _lineage("c1")},
            {"round_id": "r2", "lineage": _lineage("c2")},
        ],
        arm_cost_cap="0.01",
    )
    calls = []

    def child(plan_path, state_dir, **kwargs):
        calls.append(json.loads(Path(plan_path).read_text()))
        return _terminal(Path(plan_path), "ROLLBACK", cost="0.01")

    result = run_campaign(plan_path, tmp_path / "state", child_controller=child)

    assert result["status"] == "BUDGET_STOP"
    assert result["arms"]["qrs"]["status"] == "BUDGET_STOP"
    assert result["arms"]["qrs"]["next_round_index"] == 1
    assert result["cost"] == {
        "provider_cost_usd": "0.01",
        "completed_requests": 2,
        "total_tokens": 100,
    }
    assert len(calls) == 1


def test_campaign_cost_cap_gates_later_arm_in_single_process(tmp_path):
    plan_path = _plan(
        tmp_path,
        [{"round_id": "r1", "lineage": _lineage("c1")}],
    )
    plan = json.loads(plan_path.read_text())
    plan["limits"]["campaign_provider_cost_usd"] = "0.01"
    second_arm = deepcopy(plan["arms"][0])
    second_arm["arm_id"] = "generic"
    plan["arms"].append(second_arm)
    plan_path.write_text(json.dumps(plan))
    calls = []

    def child(plan_path, state_dir, **kwargs):
        calls.append(json.loads(Path(plan_path).read_text()))
        return _terminal(Path(plan_path), "ROLLBACK", cost="0.01")

    result = run_campaign(plan_path, tmp_path / "state", child_controller=child)

    assert result["status"] == "BUDGET_STOP"
    assert result["arms"]["qrs"]["status"] == "COMPLETE"
    assert result["arms"]["generic"]["status"] == "BUDGET_STOP"
    assert result["cost"]["provider_cost_usd"] == "0.01"
    assert len(calls) == 1
