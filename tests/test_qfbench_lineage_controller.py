import json
from pathlib import Path

from scripts.run_qfbench_lineage_controller import (
    build_child_argv,
    build_proposal_argv,
    property_set_safe,
    run_controller,
)


def _report(root: Path, run_id: str, task: str, parent, candidate, failures):
    attempts = {}
    activations = {}
    summaries = {}
    for arm, score in (("h0", parent), ("candidate", candidate)):
        attempt_id = f"{run_id}-{arm}"
        attempts[arm] = attempt_id
        activations[arm] = {"attempts": [{"task_id": task, "attempt_id": attempt_id}]}
        summaries[arm] = {"scores": [{
            "task_id": task,
            "reward": score[2],
            "tests_passed": score[0],
            "tests_failed": score[1] - score[0],
            "verifier_exit_code": 0,
        }]}
        ctrf = root / "attempts" / attempt_id / "verifier/ctrf.json"
        ctrf.parent.mkdir(parents=True, exist_ok=True)
        ctrf.write_text(json.dumps({"results": {"tests": [
            {"name": name, "status": "failed"} for name in failures.get(arm, [])
        ]}}))
    report = {
        "status": "complete",
        "run_id": run_id,
        "summaries": summaries,
        "activations": activations,
        "cost": {
            "provider_cost_usd": "0.01",
            "completed_request_count": 2,
            "total_tokens": 100,
        },
    }
    path = root / "pilot-report.json"
    path.write_text(json.dumps(report))
    return path, report


def test_property_set_safety_detects_failure_swap(tmp_path):
    path, report = _report(
        tmp_path,
        "protect",
        "task-p",
        (38, 39, 0.96),
        (38, 39, 0.96),
        {"h0": ["barrier"], "candidate": ["vanilla"]},
    )

    assert not property_set_safe(
        path,
        report,
        parent_arm="h0",
        candidate_arm="candidate",
        task_id="task-p",
    )


def test_replay_runs_to_frozen_without_child_dispatch(tmp_path):
    reports = tmp_path / "reports"
    target_path, _ = _report(
        reports / "target", "target", "task-t", (48, 51, 0), (50, 51, 0), {}
    )
    repeat_path, _ = _report(
        reports / "repeat", "repeat", "task-t", (37, 51, 0), (50, 51, 0), {}
    )
    protect_path, _ = _report(
        reports / "protect", "protect", "task-p", (42, 42, 1), (42, 42, 1), {}
    )
    plan = {
        "schema_version": 1,
        "controller_run_id": "controller-r1",
        "mode": "replay",
        "runtime": {},
        "limits": {"provider_cost_usd": 1},
        "lineages": [{
            "lineage_id": "positive",
            "parent": {"version": "h0", "worker_dir": "/h0"},
            "candidate": {"version": "c1", "worker_dir": "/c1"},
            "stages": [
                {"name": "target", "task_id": "task-t", "replay_report": str(target_path), "parent_arm": "h0", "candidate_arm": "candidate"},
                {"name": "repeat", "task_id": "task-t", "replay_report": str(repeat_path), "parent_arm": "h0", "candidate_arm": "candidate"},
                {"name": "protection", "task_id": "task-p", "replay_report": str(protect_path), "parent_arm": "h0", "candidate_arm": "candidate"},
            ],
        }],
    }
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan))

    def fail_if_called(_argv):
        raise AssertionError("replay must not dispatch a child")

    result = run_controller(plan_path, tmp_path / "state", runner=fail_if_called)
    again = run_controller(plan_path, tmp_path / "state", runner=fail_if_called)

    assert result["lineages"]["positive"]["decision"] == "PROMOTE"
    assert result["lineages"]["positive"]["phase"] == "FROZEN"
    assert again == result


def test_live_child_argv_uses_existing_component_runner():
    plan = {
        "controller_run_id": "main0",
        "runtime": {
            "python": "/python",
            "source_root": "/source",
            "qfbench_root": "/qfbench",
            "qfbench_manifest": "/manifest.json",
            "rootless_config": "/config.json",
            "image_set_manifest": "/images.json",
            "results_dir": "/results",
        },
    }
    lineage = {
        "lineage_id": "a",
        "parent": {"worker_dir": "/h0"},
        "candidate": {"worker_dir": "/c1"},
    }
    stage = {"name": "protection", "task_id": "task-p"}

    argv = build_child_argv(plan, lineage, stage, approve_external_run=True)

    assert argv[1] == "/source/scripts/run_qfbench_component_pilot.py"
    assert "parent=/h0" in argv
    assert "candidate=/c1" in argv
    assert argv[-1] == "--approve-external-run"


def _proposal_report(path: Path, *, decision: str, admitted):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "decision": decision,
        "candidate_dir": "/proposal-output/candidate",
        "admission": {"admitted": admitted},
        "candidate_generation_throughput": {
            "provider_cost_usd": "0.02",
            "completed_request_count": 3,
            "total_tokens": 200,
        },
    }))
    return path


def _proposal_plan(proposal_path: Path):
    return {
        "schema_version": 1,
        "controller_run_id": "controller-r1",
        "mode": "replay",
        "runtime": {},
        "limits": {"provider_cost_usd": 1},
        "lineages": [{
            "lineage_id": "proposal-lineage",
            "parent": {"version": "h0", "worker_dir": "/h0"},
            "proposal": {
                "replay_report": str(proposal_path),
                "replay_run_id": "proposal-r1",
                "candidate_version": "candidate-r1",
            },
            "stages": [
                {"name": "target", "task_id": "task-t"},
                {"name": "repeat", "task_id": "task-t"},
                {"name": "protection", "task_id": "task-p"},
            ],
        }],
    }


def test_replay_abstain_is_terminal_and_resume_does_not_dispatch(tmp_path):
    proposal_path = _proposal_report(
        tmp_path / "proposal/proposal-report.json",
        decision="ABSTAIN",
        admitted=None,
    )
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(_proposal_plan(proposal_path)))

    def fail_if_called(_argv):
        raise AssertionError("completed proposal must not be dispatched")

    result = run_controller(plan_path, tmp_path / "state", runner=fail_if_called)
    again = run_controller(plan_path, tmp_path / "state", runner=fail_if_called)

    state = result["lineages"]["proposal-lineage"]
    assert state["decision"] == "ABSTAIN"
    assert state["candidate"] is None
    assert again == result


def test_stop_after_proposal_resumes_without_reimporting_proposal(tmp_path):
    proposal_path = _proposal_report(
        tmp_path / "proposal/proposal-report.json",
        decision="ACT",
        admitted=True,
    )
    plan = _proposal_plan(proposal_path)
    target_path, _ = _report(
        tmp_path / "target", "target", "task-t", (1, 2, 0), (2, 2, 1), {}
    )
    repeat_path, _ = _report(
        tmp_path / "repeat", "repeat", "task-t", (1, 2, 0), (2, 2, 1), {}
    )
    protect_path, _ = _report(
        tmp_path / "protect", "protect", "task-p", (2, 2, 1), (2, 2, 1), {}
    )
    for stage, path in zip(
        plan["lineages"][0]["stages"],
        (target_path, repeat_path, protect_path),
    ):
        stage.update({
            "replay_report": str(path),
            "parent_arm": "h0",
            "candidate_arm": "candidate",
        })
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan))

    paused = run_controller(
        plan_path,
        tmp_path / "state",
        stop_after_stage="proposal",
    )["lineages"]["proposal-lineage"]
    resumed = run_controller(
        plan_path,
        tmp_path / "state",
        stop_after_stage="proposal",
    )["lineages"]["proposal-lineage"]

    assert paused["phase"] == "TARGET"
    assert paused["accounted_run_ids"] == ["proposal-r1"]
    assert resumed["phase"] == "FROZEN"
    assert resumed["decision"] == "PROMOTE"
    assert resumed["archive"][0]["worker_dir"] == "/proposal-output/candidate"
    assert resumed["accounted_run_ids"].count("proposal-r1") == 1


def test_live_proposal_argv_uses_existing_discovery_runner():
    plan = {
        "controller_run_id": "main0b",
        "runtime": {
            "python": "/python",
            "source_root": "/source",
            "qfbench_root": "/qfbench",
            "qfbench_manifest": "/manifest.json",
            "rootless_config": "/config.json",
            "image_set_manifest": "/images.json",
            "results_dir": "/results",
        },
    }
    lineage = {
        "lineage_id": "a",
        "parent": {"worker_dir": "/h0"},
    }
    proposal = {
        "evidence": "/evidence",
        "evolver_dir": "/evolver",
        "arm": "quant-state-v2",
        "reasoning_effort": "high",
    }

    argv = build_proposal_argv(
        plan, lineage, proposal, approve_external_run=True
    )

    assert argv[1] == "/source/scripts/run_qfbench_discovery_pilot.py"
    assert argv[argv.index("--backbone") + 1] == "/h0"
    assert argv[argv.index("--arm") + 1] == "quant-state-v2"
    assert "--dispatch-selected-probe" not in argv


def test_qpr_replay_resumes_review_and_existing_protection_repeat(tmp_path):
    reports = tmp_path / "reports"
    target_path, _ = _report(
        reports / "target",
        "target-r1",
        "dupire-local-vol",
        (65, 68, 0),
        (68, 68, 1),
        {},
    )
    repeat_path, _ = _report(
        reports / "repeat",
        "target-r2",
        "dupire-local-vol",
        (66, 68, 0),
        (68, 68, 1),
        {},
    )
    protect_path, protect_report = _report(
        reports / "protect",
        "protect-r1",
        "localvol-barrier",
        (38, 39, 0.96),
        (38, 39, 0.96),
        {"h0": ["barrier"], "candidate": ["vanilla"]},
    )
    protection_repeat_path, protection_repeat_report = _report(
        reports / "protect-repeat",
        "protect-r2",
        "localvol-barrier",
        (39, 39, 1),
        (38, 39, 0.96),
        {"candidate": ["barrier"]},
    )

    # The QPR path consumes explicit answer-free triage results. Removing these
    # trusted CTRF files proves the controller does not guess property meaning.
    for report_path, report in (
        (protect_path, protect_report),
        (protection_repeat_path, protection_repeat_report),
    ):
        for arm in ("h0", "candidate"):
            attempt_id = report["activations"][arm]["attempts"][0]["attempt_id"]
            ctrf = report_path.parent / "attempts" / attempt_id / "verifier/ctrf.json"
            ctrf.unlink()

    review_path = tmp_path / "review/RESULT.json"
    review_path.parent.mkdir(parents=True)
    review_path.write_text(json.dumps({
        "schema_version": 1,
        "status": "complete",
        "review_scope": "answer_free_development_protection",
        "request": {
            "accounting": {
                "provider_cost_usd": 0.00966108,
                "prompt_tokens": 1998,
                "completion_tokens": 4165,
            },
            "response_usage": {
                "cost": 0.01,
                "prompt_tokens": 2227,
                "completion_tokens": 4137,
                "total_tokens": 6364,
            },
        },
        "review": {
            "schema_version": 1,
            "reviews": [{
                "case_id": "search-v2-protection",
                "outcome_severity": "UNRESOLVED",
                "causal_attribution": "UNRESOLVED",
                "quantitative_diagnosis": "NUMERIC_TOLERANCE_ONLY",
                "next_evidence": "PAIRED_PROTECTION_REPEAT",
                "evidence_refs": ["search-v2:protect-r1"],
            }],
        },
    }))
    plan = {
        "schema_version": 1,
        "controller_run_id": "qpr-controller-r1",
        "mode": "replay",
        "runtime": {},
        "limits": {"provider_cost_usd": 1},
        "lineages": [{
            "lineage_id": "search-v2",
            "parent": {"version": "h0", "worker_dir": "/h0"},
            "candidate": {"version": "search-v2", "worker_dir": "/search-v2"},
            "quantitative_protection_review": True,
            "quantitative_review": {
                "review_id": "qpr1-review-r1",
                "case_id": "search-v2-protection",
                "result_path": str(review_path),
            },
            "stages": [
                {
                    "name": "target",
                    "task_id": "dupire-local-vol",
                    "replay_report": str(target_path),
                    "parent_arm": "h0",
                    "candidate_arm": "candidate",
                },
                {
                    "name": "repeat",
                    "task_id": "dupire-local-vol",
                    "replay_report": str(repeat_path),
                    "parent_arm": "h0",
                    "candidate_arm": "candidate",
                },
                {
                    "name": "protection",
                    "task_id": "localvol-barrier",
                    "replay_report": str(protect_path),
                    "parent_arm": "h0",
                    "candidate_arm": "candidate",
                    "quantitative_triage": {
                        "verdict": "INCONCLUSIVE",
                        "outcome_severity": "UNRESOLVED",
                        "next_evidence": "PAIRED_PROTECTION_REPEAT",
                    },
                },
                {
                    "name": "protection_repeat",
                    "task_id": "localvol-barrier",
                    "replay_report": str(protection_repeat_path),
                    "parent_arm": "h0",
                    "candidate_arm": "candidate",
                    "quantitative_triage": {
                        "verdict": "INCONCLUSIVE",
                        "outcome_severity": "UNRESOLVED",
                        "decision_label": "STILL_INCONCLUSIVE",
                    },
                },
            ],
        }],
    }
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan))

    def fail_if_called(_argv):
        raise AssertionError("existing replay reports must not dispatch a child")

    paused = run_controller(
        plan_path,
        tmp_path / "state",
        runner=fail_if_called,
        stop_after_stage="protection",
    )["lineages"]["search-v2"]
    resumed = run_controller(
        plan_path,
        tmp_path / "state",
        runner=fail_if_called,
        stop_after_stage="protection",
    )["lineages"]["search-v2"]
    again = run_controller(
        plan_path,
        tmp_path / "state",
        runner=fail_if_called,
    )["lineages"]["search-v2"]

    assert paused["phase"] == "PROTECTION_REVIEW"
    assert paused["accounted_run_ids"] == [
        "target-r1",
        "target-r2",
        "protect-r1",
    ]
    assert paused["accounted_review_ids"] == []
    assert resumed == again
    assert resumed["phase"] == "HOLD_FOR_REFINE"
    assert resumed["decision"] == "HOLD_FOR_REFINE"
    assert resumed["accounted_run_ids"] == [
        "target-r1",
        "target-r2",
        "protect-r1",
        "protect-r2",
    ]
    assert resumed["accounted_review_ids"] == ["qpr1-review-r1"]
    assert resumed["cost"] == {
        "provider_cost_usd": "0.04966108",
        "completed_requests": 9,
        "total_tokens": 6764,
    }
    assert resumed["hold"]["reason"] == (
        "quantitative_protection_still_inconclusive"
    )


def test_protection_repeat_argv_reuses_component_pilot():
    plan = {
        "controller_run_id": "main0",
        "runtime": {
            "python": "/python",
            "source_root": "/source",
            "qfbench_root": "/qfbench",
            "qfbench_manifest": "/manifest.json",
            "rootless_config": "/config.json",
            "image_set_manifest": "/images.json",
            "results_dir": "/results",
        },
    }
    lineage = {
        "lineage_id": "a",
        "parent": {"worker_dir": "/h0"},
        "candidate": {"worker_dir": "/c1"},
    }
    stage = {
        "name": "protection_repeat",
        "task_id": "localvol-barrier",
    }

    argv = build_child_argv(plan, lineage, stage, approve_external_run=True)

    assert argv[1] == "/source/scripts/run_qfbench_component_pilot.py"
    assert argv[argv.index("--run-id") + 1] == "main0-a-protection_repeat"
    assert argv[argv.index("--task-id") + 1] == "localvol-barrier"
