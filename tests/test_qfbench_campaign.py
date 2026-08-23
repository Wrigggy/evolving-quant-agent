from __future__ import annotations

import json
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


def _plan(tmp_path: Path, rounds):
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
                        "task_id": "target-task",
                        "id": "h0-target",
                        "report_path": "reports/h0-target.json",
                        "arm": "h0",
                    },
                    {
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
    path = tmp_path / "campaign-plan.json"
    path.write_text(json.dumps(value))
    return path


def _terminal(plan_path: Path, decision: str):
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
    assert result["arms"]["qrs"]["current_incumbent"]["version"] == "c1"
    assert len(calls) == 2
    assert calls[0]["controller_run_id"] == "campaign-01-qrs-r1"
    assert calls[0]["lineages"][0]["proposal"]["live_run_id"] == (
        "campaign-01-qrs-r1-proposal"
    )
    second = calls[1]["lineages"][0]
    assert second["parent"]["version"] == "c1"
    target = second["stages"][0]
    protection = second["stages"][2]
    assert target["parent_arm"] == "c1-repeat"
    assert target["selection_reference"]["id"] == (
        "campaign-01-qrs-r1-repeat"
    )
    assert target["selection_reference"]["reference_version"] == "c1"
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
    assert references["new-target"] == {
        "task_id": "new-target",
        "id": "campaign-01-qrs-family-b-repeat",
        "report_path": "reports/campaign-01-qrs-family-b-repeat.json",
        "arm": "c2-repeat",
        "reference_version": "c2",
    }
    assert references["new-protection"]["reference_version"] == "c2"
