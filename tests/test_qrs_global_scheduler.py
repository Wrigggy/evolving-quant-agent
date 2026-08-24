from __future__ import annotations

import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest

from qea.frozen_base_harness import build_selected_runtime, freeze_base_harness
from qea.qrs_global_scheduler import GlobalSchedulerError, run_scheduler


REPO_ROOT = Path(__file__).resolve().parents[1]
METHOD = REPO_ROOT / "data/breadth/QF_GLOBAL_S6_PRIMITIVE_H0_TRAJECTORY_SCHEDULER_PLAN.json"


def _handoff(tmp_path: Path) -> Path:
    selection = tmp_path / "selection"
    selection.mkdir()
    worker = REPO_ROOT / "qea/worker_quant_h0_s6_primitive_v1"
    agent = __import__("yaml").safe_load((worker / "agent.yaml").read_text())
    runtime = build_selected_runtime(
        agent,
        worker_model_route="deepseek-v4-flash-main0",
        rootless_config="/runtime/qfbench.json",
    )
    handoff = tmp_path / "handoff.json"
    freeze_base_harness(
        worker_dir=worker,
        run_root=tmp_path / "run",
        selected_profile_id="primitive-v1",
        selected_runtime=runtime,
        selection_artifact_root=selection,
        handoff_path=handoff,
    )
    return handoff


def _launch(tmp_path: Path) -> Path:
    value = {
        "schema_version": 1,
        "scheduler_run_id": "qrs-main-test",
        "method_plan_path": str(METHOD),
        "frozen_h0_handoff": str(_handoff(tmp_path)),
        "scheduler_state_root": str(tmp_path / "controller-states"),
        "trajectory_bank_output": str(tmp_path / "bank"),
        "trajectory_bank_manifest": str(tmp_path / "manifest.json"),
        "qfbench_public_manifest": str(tmp_path / "public-manifest.json"),
        "public_contracts_root": str(tmp_path / "public-contracts"),
        "runtime": {
            "python": "python",
            "source_root": str(REPO_ROOT),
            "qfbench_root": "/runtime/qfbench",
            "qfbench_manifest": "/runtime/manifest.json",
            "rootless_config": "/runtime/qfbench.json",
            "image_set_manifest": "/runtime/images.json",
            "results_dir": str(tmp_path / "results"),
            "worker_route": "deepseek-v4-flash-main0",
        },
        "panel_controller_plans": {
            str(index): str(tmp_path / f"panel-{index}.json")
            for index in range(1, 7)
        },
    }
    path = tmp_path / "launch.json"
    path.write_text(json.dumps(value))
    return path


class FakeRunner:
    def __init__(self, tmp_path: Path, *, regression_panel: int | None = None):
        self.tmp_path = tmp_path
        self.calls: list[dict[str, object]] = []
        self.regression_panel = regression_panel

    def __call__(self, action):
        self.calls.append(deepcopy(dict(action)))
        if action["kind"] == "build_trajectory_bank":
            return {
                "status": "complete",
                "accounting_complete": True,
                "indexed_task_ids": action["task_ids"],
                "sealed_task_ids_present": [],
                "panel_views": {
                    str(index): f"panels/{index}" for index in range(1, 7)
                },
                "cost": {},
            }
        if action["kind"] == "panel_proposal_review":
            worker = self.tmp_path / f"candidate-{action['panel_index']}"
            shutil.copytree(
                action["frozen_h0_worker_dir"], worker, dirs_exist_ok=True
            )
            prompt = worker / "systemprompt.md"
            addition = (
                f"\nKeep public workflow handoff {action['panel_index']} explicit.\n"
            )
            if addition not in prompt.read_text(encoding="utf-8"):
                prompt.write_text(
                    prompt.read_text(encoding="utf-8") + addition,
                    encoding="utf-8",
                )
            return {
                "status": "complete",
                "accounting_complete": True,
                "review_verdict": "PASS",
                "coverage": "PASS",
                "reviewed_parent": action["current_parent"],
                "candidate": {
                    "version": action["proposal_version"],
                    "worker_dir": str(worker),
                },
                "review_result_path": f"reviews/{action['panel_index']}.json",
                "accepted_claims": [
                    {
                        "claim_id": f"workflow-{action['panel_index']}",
                        "claim": "Use the public six-stage handoff consistently.",
                        "surfaces": ["systemprompt"],
                        "basis_refs": ["public:workflow-contract"],
                    }
                ],
                "cost": {
                    "completed_requests": 1,
                    "total_tokens": 100,
                    "provider_cost_usd": "0.01",
                },
            }
        if action["kind"] == "augment_panel_evidence":
            return {
                "status": "complete",
                "accounting_complete": True,
                "answer_free": True,
                "panel_index": action["panel_index"],
                "next_evidence_root": action["next_evidence_root"],
                "accepted_claim_count": len(action["accepted_claims"]),
                "matched_repetition_count": 2,
                "sealed_task_ids_present": [],
                "cost": {},
            }
        if action["kind"] == "carry_panel_evidence":
            return {
                "status": "complete",
                "accounting_complete": True,
                "answer_free": True,
                "next_evidence_root": action["next_evidence_root"],
                "carried_entry_count": 0,
                "sealed_task_ids_present": [],
                "cost": {},
            }
        labels = [value["label"] for value in action["arms"]]
        rewards = {}
        for label in labels:
            base = 0.25
            if action["purpose"] == "panel_matched_fitness" and label == "candidate":
                base = 0.5
            if action["purpose"] == "panel_matched_fitness" and label == "parent":
                base = 0.25
            if (
                action["purpose"] == "panel_matched_fitness"
                and action["panel_index"] == self.regression_panel
                and action["repetition"] == 2
                and label == "candidate"
            ):
                base = 0.0
            rewards[label] = {task: base for task in action["task_ids"]}
        return {
            "status": "complete",
            "accounting_complete": True,
            "task_ids": action["task_ids"],
            "summaries": {
                label: {"task_rewards": rewards[label]} for label in labels
            },
            "worker_executions": {
                label: {"valid_for_selection": True} for label in labels
            },
            "scheduler_protocol": {
                label: {task: True for task in action["task_ids"]}
                for label in labels
            },
            "report_path": f"reports/{action['action_id']}.json",
            "cost": {
                "completed_request_count": len(action["task_ids"]) * len(labels),
                "total_tokens": 1000,
                "provider_cost_usd": "0.02",
            },
        }


def test_full_schedule_runs_45_bank_cells_six_panels_and_four_sealed_blocks(tmp_path):
    launch = _launch(tmp_path)
    runner = FakeRunner(tmp_path)
    result = run_scheduler(METHOD, launch, tmp_path / "state", action_runner=runner)

    assert result["status"] == "COMPLETE"
    assert len(result["bank_results"]) == 45
    assert len(result["panel_results"]) == 6
    assert all(value["decision"] == "PROMOTE" for value in result["panel_results"])
    assert result["current_parent"]["version"] == "global-s6-p6-final"
    assert [value["after_panel"] for value in result["checkpoints"]] == [2, 4, 6]
    assert len(result["sealed_results"]) == 4
    assert result["sealed_summary"]["task_count"] == 12
    assert result["sealed_summary"]["repetitions"] == 2
    assert len(result["sealed_summary"]["per_task"]) == 12
    assert len(result["sealed_summary"]["per_domain"]) == 6
    assert result["sealed_summary"]["primary_metric"] == (
        "official_binary_task_reward"
    )
    assert len(runner.calls) == 45 + 1 + 6 + 12 + 5 + 4
    assert len(result["curriculum_handoffs"]) == 5
    assert sum(
        len(call.get("task_ids", [])) * len(call.get("arms", []))
        for call in runner.calls
        if call.get("kind") == "component_pilot"
    ) == 393

    matched = [
        call for call in runner.calls if call.get("purpose") == "panel_matched_fitness"
    ]
    first_panel = matched[0]
    assert set(first_panel["focus_task_ids"]) == set(
        json.loads(METHOD.read_text())["development_panels"][0]["task_ids"]
    )
    assert len(first_panel["anchor_task_ids"]) == 5
    assert set(first_panel["task_ids"]) == set(first_panel["focus_task_ids"]).union(
        first_panel["anchor_task_ids"]
    )

    assert [value["label"] for value in matched[0]["arms"]] == ["parent", "candidate"]
    assert [value["label"] for value in matched[1]["arms"]] == ["candidate", "parent"]
    sealed = [call for call in runner.calls if call.get("sealed") is True]
    assert [tuple(value["label"] for value in call["arms"]) for call in sealed] == [
        ("h0", "candidate"),
        ("candidate", "h0"),
        ("candidate", "h0"),
        ("h0", "candidate"),
    ]


def test_resume_after_child_import_dispatches_nothing_twice_and_cost_is_stable(tmp_path):
    launch = _launch(tmp_path)
    runner = FakeRunner(tmp_path)
    first = run_scheduler(METHOD, launch, tmp_path / "state", action_runner=runner)
    call_count = len(runner.calls)
    second = run_scheduler(METHOD, launch, tmp_path / "state", action_runner=runner)

    assert second == first
    assert len(runner.calls) == call_count
    assert len(second["accounted_action_ids"]) == call_count


def test_resume_rejects_method_or_launch_drift(tmp_path):
    launch = _launch(tmp_path)
    runner = FakeRunner(tmp_path)
    run_scheduler(
        METHOD,
        launch,
        tmp_path / "state",
        action_runner=runner,
        stop_after_phase="IMPORT_H0",
    )
    changed = json.loads(launch.read_text(encoding="utf-8"))
    changed["runtime"]["worker_route"] = "different-route"
    launch.write_text(json.dumps(changed), encoding="utf-8")

    with pytest.raises(GlobalSchedulerError, match="input changed"):
        run_scheduler(METHOD, launch, tmp_path / "state", action_runner=runner)


def test_stop_after_bank_finishes_all_h0_cells_then_resume_starts_builder(tmp_path):
    launch = _launch(tmp_path)
    runner = FakeRunner(tmp_path)
    paused = run_scheduler(
        METHOD,
        launch,
        tmp_path / "state",
        action_runner=runner,
        stop_after_phase="H0_BANK",
    )
    assert paused["status"] == "RUNNING"
    assert paused["phase"] == "BUILD_BANK"
    assert paused["stopped_after_phase"] == "H0_BANK"
    assert len(runner.calls) == 45

    resumed = run_scheduler(
        METHOD, launch, tmp_path / "state", action_runner=runner
    )
    assert resumed["status"] == "COMPLETE"
    assert runner.calls[45]["kind"] == "build_trajectory_bank"


def test_stop_after_panel_waits_for_answer_free_handoff_then_pauses(tmp_path):
    launch = _launch(tmp_path)
    runner = FakeRunner(tmp_path)
    paused = run_scheduler(
        METHOD,
        launch,
        tmp_path / "state",
        action_runner=runner,
        stop_after_panel=1,
    )

    assert paused["status"] == "RUNNING"
    assert paused["stopped_after_panel"] == 1
    assert paused["panel_next_index"] == 1
    assert len(paused["panel_results"]) == 1
    assert paused["panel_results"][0]["decision"] == "PROMOTE"
    assert len(paused["curriculum_handoffs"]) == 1
    assert not any(call.get("panel_index") == 2 for call in runner.calls)

    resumed = run_scheduler(
        METHOD, launch, tmp_path / "state", action_runner=runner
    )
    assert resumed["status"] == "COMPLETE"
    assert len(resumed["panel_results"]) == 6


def test_same_stop_after_panel_resume_is_zero_work(tmp_path):
    launch = _launch(tmp_path)
    runner = FakeRunner(tmp_path)
    paused = run_scheduler(
        METHOD,
        launch,
        tmp_path / "state",
        action_runner=runner,
        stop_after_panel=1,
    )
    call_count = len(runner.calls)
    paused_snapshot = deepcopy(paused)

    resumed = run_scheduler(
        METHOD,
        launch,
        tmp_path / "state",
        action_runner=runner,
        stop_after_panel=1,
    )

    assert len(runner.calls) == call_count
    assert resumed == paused_snapshot
    assert resumed["cost"] == paused_snapshot["cost"]


def test_panel_regression_retains_parent_and_continues_to_sealed(tmp_path):
    launch = _launch(tmp_path)
    runner = FakeRunner(tmp_path, regression_panel=2)
    result = run_scheduler(METHOD, launch, tmp_path / "state", action_runner=runner)

    assert result["status"] == "COMPLETE"
    assert len(result["panel_results"]) == 6
    assert result["panel_results"][1]["decision"] == "RETAIN_NO_STABLE_GAIN"
    assert any(call.get("sealed") is True for call in runner.calls)
    assert any(call.get("panel_index") == 3 for call in runner.calls)
    assert any(call.get("kind") == "carry_panel_evidence" for call in runner.calls)
    assert result["current_parent"]["version"] == "global-s6-p6-final"


def test_nonpass_review_retains_parent_continues_and_runs_no_candidate_workers(tmp_path):
    launch = _launch(tmp_path)
    runner = FakeRunner(tmp_path)
    original = runner.__call__

    def nonpass(action):
        result = original(action)
        if action["kind"] == "panel_proposal_review":
            result["review_verdict"] = "INCONCLUSIVE"
        return result

    result = run_scheduler(METHOD, launch, tmp_path / "state", action_runner=nonpass)
    assert result["status"] == "COMPLETE"
    assert not any(call.get("purpose") == "panel_matched_fitness" for call in runner.calls)
    assert [value["decision"] for value in result["panel_results"]] == [
        "RETAIN_REVIEW_NONPASS"
    ] * 6
    assert result["current_parent"]["version"] == "primitive-v1"
    assert len([call for call in runner.calls if call.get("sealed")]) == 4


def test_sealed_scores_do_not_change_the_frozen_dispatch_sequence(tmp_path):
    launch = _launch(tmp_path)
    runner = FakeRunner(tmp_path)
    result = run_scheduler(METHOD, launch, tmp_path / "state", action_runner=runner)
    assert result["status"] == "COMPLETE"
    sealed = [call["action_id"] for call in runner.calls if call.get("sealed")]

    other_root = tmp_path / "other"
    other_root.mkdir()
    other_launch = _launch(other_root)
    other = FakeRunner(other_root)
    original = other.__call__

    def inverted_sealed(action):
        value = original(action)
        if action.get("sealed"):
            for summary in value["summaries"].values():
                summary["task_rewards"] = {
                    task: 1.0 - reward for task, reward in summary["task_rewards"].items()
                }
        return value

    other_result = run_scheduler(
        METHOD, other_launch, other_root / "state", action_runner=inverted_sealed
    )
    assert other_result["status"] == "COMPLETE"
    assert [call["action_id"] for call in other.calls if call.get("sealed")] == sealed


def test_invalid_protocol_and_incomplete_bank_fail_closed(tmp_path):
    launch = _launch(tmp_path)
    runner = FakeRunner(tmp_path)
    original = runner.__call__

    def invalid(action):
        result = original(action)
        if action.get("purpose") == "h0_bank" and len(runner.calls) == 1:
            result["scheduler_protocol"]["h0"][action["task_ids"][0]] = False
        return result

    result = run_scheduler(METHOD, launch, tmp_path / "state", action_runner=invalid)
    assert result["status"] == "STOP_BANK"
    assert "failed S1-S6 protocol" in result["stop_reason"]


def test_launch_requires_all_six_panel_controller_plans(tmp_path):
    launch = _launch(tmp_path)
    value = json.loads(launch.read_text())
    value["panel_controller_plans"].pop("6")
    launch.write_text(json.dumps(value))
    with pytest.raises(GlobalSchedulerError, match="panel 6"):
        run_scheduler(METHOD, launch, tmp_path / "state", action_runner=lambda action: {})
