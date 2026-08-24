from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

import qea.qfbench_trajectory_bank as trajectory_bank
import scripts.run_qrs_global_scheduler as runner
from qea.qrs_global_scheduler import GlobalSchedulerError


ROOT = Path(__file__).resolve().parents[1]


def _write(path: Path, value: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    return path


def test_current_global_main_plan_is_not_launch_authorized() -> None:
    method = json.loads(
        (
            ROOT
            / "data/breadth/QF_GLOBAL_S6_PRIMITIVE_H0_TRAJECTORY_SCHEDULER_PLAN.json"
        ).read_text(encoding="utf-8")
    )

    with pytest.raises(GlobalSchedulerError, match="frozen_launch_authorized"):
        runner._require_live_launch_authority(method)


def test_engineering_canary_plan_remains_permitted_with_cli_approval() -> None:
    method = json.loads(
        (
            ROOT / "data/breadth/QF_QRS_MINI_SCHEDULER_CANARY_R3_PLAN.json"
        ).read_text(encoding="utf-8")
    )

    runner._require_live_launch_authority(method)


def test_explicitly_unauthorized_engineering_canary_is_rejected() -> None:
    method = json.loads(
        (
            ROOT
            / "data/breadth/QF_QRS_REVIEWER_POLICY_V2_QUALIFICATION_PLAN.json"
        ).read_text(encoding="utf-8")
    )

    method["status"] = "frozen_not_run_launch_not_authorized"
    method["authority"]["launch_authorized"] = False
    method["authority"]["paid_or_remote_authority"] = False
    method["limits"]["paid_or_remote_authority"] = False

    with pytest.raises(GlobalSchedulerError, match="explicit authority block"):
        runner._require_live_launch_authority(method)

    method["status"] = "frozen_launch_authorized"
    method["authority"]["launch_authorized"] = True
    method["authority"]["paid_or_remote_authority"] = True
    method["limits"]["paid_or_remote_authority"] = True
    runner._require_live_launch_authority(method)


def _component_action(tmp_path: Path) -> dict[str, object]:
    parent = tmp_path / "parent"
    candidate = tmp_path / "candidate"
    parent.mkdir(exist_ok=True)
    candidate.mkdir(exist_ok=True)
    return {
        "action_id": "main-bank-t1",
        "kind": "component_pilot",
        "purpose": "h0_bank",
        "run_id": "main-bank-t1",
        "seed_worker": str(parent),
        "task_ids": ["t1"],
        "arms": [
            {"label": "parent", "worker_dir": str(parent)},
            {"label": "candidate", "worker_dir": str(candidate)},
        ],
    }


def _complete_trace() -> dict[str, object]:
    return {
        "schema_version": 2,
        "record_kind": "research_state_tool_call_index",
        "telemetry_source": "nexau_structured_tool_call",
        "events": [
            {"stage": "S6", "action": "COMPLETE", "summary": "done"}
        ],
        "issues": [],
        "malformed_calls": [],
        "coverage": {"marker_protocol_complete": True},
    }


def _terminal_attempt(
    run_dir: Path,
    *,
    name: str,
    checkpoint: str,
    task_id: str = "t1",
    superseded_by: str | None = None,
) -> Path:
    attempt_dir = run_dir / "attempts" / name
    _write(
        attempt_dir / "attempt.json",
        {
            "attempt_id": name,
            "run_id": "main-bank-t1",
            "checkpoint": checkpoint,
            "task_id": task_id,
        },
    )
    _write(attempt_dir / "completed-score.json", {"task_id": task_id})
    _write(attempt_dir / "research-state-trace.json", _complete_trace())
    if superseded_by is not None:
        _write(
            attempt_dir / "worker-attempt-replacement.json",
            {
                "superseded_attempt_id": name,
                "replacement_attempt_id": superseded_by,
            },
        )
    return attempt_dir


def test_protocol_audit_requires_structured_complete_terminal_and_accepts_replacement(
    tmp_path: Path,
) -> None:
    action = _component_action(tmp_path)
    run_dir = tmp_path / "run"
    _terminal_attempt(
        run_dir,
        name="old",
        checkpoint="main-bank-t1-parent",
        superseded_by="new",
    )
    _terminal_attempt(
        run_dir,
        name="new",
        checkpoint="main-bank-t1-parent+infra-replacement-01",
    )
    candidate = _terminal_attempt(
        run_dir,
        name="candidate",
        checkpoint="main-bank-t1-candidate",
    )

    result = runner._protocol_audit(run_dir, action)

    assert result == {"parent": {"t1": True}, "candidate": {"t1": True}}
    trace_path = candidate / "research-state-trace.json"
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    trace["record_kind"] = "research_state_marker_index"
    trace["schema_version"] = 1
    _write(trace_path, trace)
    assert runner._protocol_audit(run_dir, action)["candidate"]["t1"] is False


def _component_run(
    tmp_path: Path,
) -> tuple[dict[str, object], dict[str, object], Path]:
    action = _component_action(tmp_path)
    results_dir = tmp_path / "results"
    run_dir = results_dir / str(action["run_id"])
    _write(
        run_dir / "pilot-plan.json",
        {
            "run_id": action["run_id"],
            "task_ids": action["task_ids"],
            "checkpoint_prefix": action["run_id"],
            "arms": action["arms"],
            "effective_runtime": {
                "worker_concurrency": 1,
                "verifier_concurrency": 1,
            },
        },
    )
    _write(
        run_dir / "pilot-report.json",
        {
            "status": "complete",
            "run_id": action["run_id"],
            "task_ids": action["task_ids"],
            "cost": {
                "cost_complete": True,
                "provider_cost_is_lower_bound": False,
                "completed_request_count": 2,
                "total_tokens": 10,
                "provider_cost_usd": "0.01",
            },
        },
    )
    for arm in action["arms"]:
        _terminal_attempt(
            run_dir,
            name=str(arm["label"]),
            checkpoint=f"{action['run_id']}-{arm['label']}",
        )
    launch = {"runtime": {"results_dir": str(results_dir)}}
    return action, launch, run_dir


def test_component_reuse_validates_exact_plan_and_complete_cost(tmp_path: Path) -> None:
    action, launch, run_dir = _component_run(tmp_path)

    result = runner._component_result(action, launch)

    assert result["accounting_complete"] is True
    assert result["scheduler_protocol"]["parent"]["t1"] is True
    plan = json.loads((run_dir / "pilot-plan.json").read_text(encoding="utf-8"))
    plan["arms"][0]["worker_dir"] = str(tmp_path / "different")
    _write(run_dir / "pilot-plan.json", plan)
    with pytest.raises(GlobalSchedulerError, match="different exact Worker arms"):
        runner._component_result(action, launch)


def test_component_reuse_rejects_incomplete_accounting(tmp_path: Path) -> None:
    action, launch, run_dir = _component_run(tmp_path)
    report = json.loads(
        (run_dir / "pilot-report.json").read_text(encoding="utf-8")
    )
    report["cost"]["cost_complete"] = False
    _write(run_dir / "pilot-report.json", report)

    with pytest.raises(GlobalSchedulerError, match="accounting is incomplete"):
        runner._component_result(action, launch)


def test_runner_input_snapshot_rejects_method_or_launch_drift(tmp_path: Path) -> None:
    method_path = _write(tmp_path / "method.json", {"schema_version": 1})
    launch_path = _write(
        tmp_path / "launch.json",
        {"method_plan_path": str(method_path.resolve()), "runtime": {}},
    )
    state_dir = tmp_path / "state"

    method, launch = runner._bind_runner_inputs(method_path, launch_path, state_dir)

    assert method == {"schema_version": 1}
    assert launch["method_plan_path"] == str(method_path.resolve())
    _write(
        launch_path,
        {
            "method_plan_path": str(method_path.resolve()),
            "runtime": {"python": "changed"},
        },
    )
    with pytest.raises(GlobalSchedulerError, match="changed after"):
        runner._bind_runner_inputs(method_path, launch_path, state_dir)


def _panel_fixture(
    tmp_path: Path,
) -> tuple[dict[str, object], dict[str, object], Path, Path]:
    contracts = tmp_path / "contracts"
    instruction = contracts / "tasks" / "t1" / "instruction.md"
    instruction.parent.mkdir(parents=True)
    instruction.write_text("public instruction\n", encoding="utf-8")
    clauses = _write(
        instruction.parent / "clauses.json", {"clauses": [{"id": "c1"}]}
    )
    candidate_dir = tmp_path / "controller-states" / "reviewed-candidate"
    candidate_dir.mkdir(parents=True)
    (tmp_path / "proposal" / "candidate").mkdir(parents=True)
    proposal_report = _write(
        tmp_path / "proposal" / "proposal-report.json",
        {
            "decision": "ACT",
            "admission": {"admitted": True},
            "candidate_dir": str(tmp_path / "proposal" / "candidate"),
            "candidate_generation_throughput": {
                "billable_or_delivered_request_count": 3,
                "completed_request_count": 3,
                "downstream_delivery_request_count": 0,
                "noncompleted_request_count": 0,
                "provider_cost_usd": "1.25",
                "total_tokens": 100,
            }
        },
    )
    review_id = "review-1"
    review_result = _write(
        tmp_path / "review" / "RESULT.json",
        {
            "status": "complete",
            "worker_visible": False,
            "promotion_authority": False,
            "request": {
                "request_count": 1,
                "accounting": {
                    "provider_cost_usd": "0.25",
                    "prompt_tokens": 20,
                    "completion_tokens": 30,
                },
                "response_usage": {"total_tokens": 50},
            },
            "review": {
                "review_id": review_id,
                "candidate_id": "candidate-v1",
                "overall_verdict": "PASS",
                "coverage_review": {"verdict": "PASS"},
            },
        },
    )
    parent = {"version": "h0", "worker_dir": str(tmp_path / "parent")}
    Path(parent["worker_dir"]).mkdir()
    evidence = str(tmp_path / "evidence")
    action = {
        "action_id": "main-panel-1-review",
        "kind": "panel_proposal_review",
        "panel_index": 1,
        "proposal_version": "candidate-v1",
        "controller_plan_path": str(tmp_path / "panel-plan.json"),
        "current_parent": parent,
        "trajectory_bank": {"panel_views": {"1": evidence}},
    }
    public_sources = [
        {
            "ref": "public:t1:instruction",
            "source_type": "public_contract",
            "source_path": str(instruction.resolve()),
            "excerpt": instruction.read_text(encoding="utf-8"),
        },
        {
            "ref": "public:t1:clauses",
            "source_type": "public_contract",
            "source_path": str(clauses.resolve()),
            "excerpt": json.dumps(
                json.loads(clauses.read_text(encoding="utf-8")),
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            ),
        },
    ]
    plan = {
        "states_root": str(tmp_path / "controller-states"),
        "lineages": [
            {
                "lineage_id": "lineage-1",
                "parent": parent,
                "proposal": {
                    "live_run_id": "proposal-1",
                    "candidate_version": "candidate-v1",
                    "evidence": evidence,
                },
                "candidate_information_set_review": {
                    "enabled": True,
                    "feedback_mode": "answer_free",
                    "review_id": review_id,
                    "public_sources": public_sources,
                    "optimize_only_sources": [],
                },
            }
        ],
    }
    _write(Path(action["controller_plan_path"]), plan)
    claims = [
        {
            "claim_id": "claim-1",
            "claim_scope": "task_specific_requirement",
            "claim": "Use the public contract.",
            "surfaces": ["systemprompt"],
            "basis_refs": [
                {
                    "kind": "public_contract",
                    "ref": "public:t1:instruction",
                    "support": "the public instruction directly supports it",
                }
            ],
            "reviewer_reason": "must never enter accepted_claims",
        }
    ]
    state = {
        "lineage_id": "lineage-1",
        "status": "running",
        "phase": "TARGET",
        "stopped_after_stage": "information_set_review",
        "current_parent": parent,
        "proposal": {
            "run_id": "proposal-1",
            "report_path": str(proposal_report),
            "decision": "ACT",
            "admitted": True,
            "candidate_dir": str(tmp_path / "proposal" / "candidate"),
            "worker_visible_claims": claims,
        },
        "candidate": {
            "version": "candidate-v1",
            "worker_dir": str(candidate_dir),
            "source_worker_dir": str(tmp_path / "proposal" / "candidate"),
            "reviewed_candidate_dir": str(candidate_dir),
            "information_set_review": {
                "review_id": review_id,
                "overall_verdict": "PASS",
                "reviewed_candidate_dir": str(candidate_dir),
            },
        },
        "observations": {
            "information_set_review": {
                "review_id": review_id,
                "review_path": str(review_result),
                "overall_verdict": "PASS",
                "coverage_review": {"verdict": "PASS"},
                "reviewed_candidate_dir": str(candidate_dir),
            }
        },
        "accounted_review_ids": [review_id],
        "cost": {
            "provider_cost_usd": "1.50",
            "completed_requests": 4,
            "total_tokens": 150,
        },
    }
    state_path = _write(
        tmp_path / "controller-states" / "lineage-1.json", state
    )
    _write(
        tmp_path
        / "controller-states"
        / "review-inputs"
        / f"{review_id}.json",
        {
            "schema_version": 1,
            "review_id": review_id,
            "candidate_id": "candidate-v1",
            "candidate": {"diff_ref": "candidate:diff", "diff": "+ rule\n"},
            "worker_visible_claims": claims,
            "public_sources": public_sources,
            "trusted_answer_free_sources": [],
            "optimize_only_sources": [],
        },
    )
    launch = {
        "scheduler_state_root": str(tmp_path / "wrong-controller-root"),
        "public_contracts_root": str(contracts),
    }
    return action, launch, state_path, instruction


def test_panel_resume_uses_plan_state_and_returns_clean_claims(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    action, launch, _, _ = _panel_fixture(tmp_path)

    def unexpected_controller(*args, **kwargs):
        raise AssertionError("retained Review state must short-circuit the controller")

    monkeypatch.setattr(runner, "run_controller", unexpected_controller)
    result = runner._panel_result(action, launch)

    assert result["accounting_complete"] is True
    assert result["review_verdict"] == "PASS"
    assert result["accepted_claims"] == [
        {
            "claim_id": "claim-1",
            "claim_scope": "task_specific_requirement",
            "claim": "Use the public contract.",
            "surfaces": ["systemprompt"],
            "basis_refs": [
                {
                    "kind": "public_contract",
                    "ref": "public:t1:instruction",
                    "support": "the public instruction directly supports it",
                }
            ],
            "safe_sources": [
                {
                    "ref": "public:t1:instruction",
                    "source_type": "public_contract",
                    "source_path": str((tmp_path / "contracts/tasks/t1/instruction.md").resolve()),
                    "excerpt": "public instruction\n",
                }
            ],
        }
    ]
    assert "reviewer_reason" not in result["accepted_claims"][0]


def test_panel_template_resolves_stale_promoted_parent_to_current_incumbent(
    tmp_path: Path,
) -> None:
    action, launch, _, _ = _panel_fixture(tmp_path)
    plan_path = Path(action["controller_plan_path"])
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["lineages"][0]["parent"] = {
        "version": "rolled-back-panel-1",
        "worker_dir": str(tmp_path / "rolled-back-panel-1"),
    }
    _write(plan_path, plan)

    result = runner._panel_result(action, launch)

    assert result["reviewed_parent"] == action["current_parent"]
    resolved = json.loads(
        (
            tmp_path
            / "controller-states"
            / "RESOLVED-CONTROLLER-PLAN.json"
        ).read_text(encoding="utf-8")
    )
    assert resolved["lineages"][0]["parent"] == action["current_parent"]
    assert plan["lineages"][0]["parent"] != action["current_parent"]


def test_nonpass_review_with_pass_coverage_returns_rollback_result(
    tmp_path: Path,
) -> None:
    action, launch, state_path, _ = _panel_fixture(tmp_path)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["phase"] = "HOLD_FOR_REFINE"
    state["status"] = "candidate_hold"
    del state["candidate"]["information_set_review"]
    observation = state["observations"]["information_set_review"]
    observation["overall_verdict"] = "INCONCLUSIVE"
    _write(state_path, state)
    review_path = Path(observation["review_path"])
    wrapper = json.loads(review_path.read_text(encoding="utf-8"))
    wrapper["review"]["overall_verdict"] = "INCONCLUSIVE"
    _write(review_path, wrapper)

    result = runner._panel_result(action, launch)

    assert result["review_verdict"] == "INCONCLUSIVE"
    assert result["coverage"] == "PASS"
    assert result["accepted_claims"] == []
    assert result["reviewed_parent"] == action["current_parent"]


def test_proposal_abstain_returns_clean_pre_review_result(tmp_path: Path) -> None:
    action, launch, state_path, _ = _panel_fixture(tmp_path)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    proposal_path = Path(state["proposal"]["report_path"])
    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    proposal["decision"] = "ABSTAIN"
    proposal["admission"] = {
        "admitted": None,
        "not_applicable": True,
        "reason": "candidate writes remained locked",
    }
    _write(proposal_path, proposal)
    state.update(
        {
            "status": "abstained",
            "phase": "FROZEN",
            "decision": "ABSTAIN",
            "candidate": None,
            "observations": {},
            "accounted_review_ids": [],
            "cost": {
                "provider_cost_usd": "1.25",
                "completed_requests": 3,
                "total_tokens": 100,
            },
        }
    )
    state["proposal"]["decision"] = "ABSTAIN"
    state["proposal"]["admitted"] = None
    state["proposal"].pop("worker_visible_claims", None)
    state.pop("stopped_after_stage", None)
    _write(state_path, state)

    result = runner._panel_result(action, launch)

    assert result["proposal_decision"] == "ABSTAIN"
    assert result["review_verdict"] == "NOT_RUN"
    assert result["coverage"] == "NOT_RUN"
    assert result["candidate"] is None
    assert result["review_result_path"] is None
    assert result["cost"] == {
        "provider_cost_usd": "1.25",
        "completed_requests": 3,
        "total_tokens": 100,
    }


def test_panel_rejects_answer_rich_sources_and_excerpt_drift(tmp_path: Path) -> None:
    action, launch, _, instruction = _panel_fixture(tmp_path)
    plan_path = Path(action["controller_plan_path"])
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    review = plan["lineages"][0]["candidate_information_set_review"]
    review["optimize_only_sources"] = [{"ref": "answer"}]
    _write(plan_path, plan)
    with pytest.raises(GlobalSchedulerError, match="answer-free"):
        runner._panel_result(action, launch)

    review["optimize_only_sources"] = []
    _write(plan_path, plan)
    instruction.write_text("changed public instruction\n", encoding="utf-8")
    with pytest.raises(GlobalSchedulerError, match="excerpt differs"):
        runner._panel_result(action, launch)


def test_panel_rejects_candidate_snapshot_drift(tmp_path: Path) -> None:
    action, launch, state_path, _ = _panel_fixture(tmp_path)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["observations"]["information_set_review"]["reviewed_candidate_dir"] = (
        str(tmp_path / "different")
    )
    _write(state_path, state)

    with pytest.raises(GlobalSchedulerError, match="retained candidate snapshot"):
        runner._panel_result(action, launch)


def test_dispatch_capacity_rejects_exact_cost_and_cell_caps(tmp_path: Path) -> None:
    state_path = _write(
        tmp_path / "scheduler-state.json",
        {
            "cost": {
                "provider_cost_usd": "2.0",
                "completed_requests": 1,
                "total_tokens": 99,
            },
            "qfbench_cells_accounted": 9,
            "accounted_action_ids": [],
        },
    )
    method = {
        "limits": {
            "maximum_total_tokens": 100,
            "maximum_provider_cost_usd": "2.0",
            "maximum_qfbench_sessions_including_recovery": 10,
            "maximum_all_worker_sessions": 10,
            "evolver_calls": 6,
            "reviewer_calls": 6,
        }
    }
    action = _component_action(tmp_path)

    with pytest.raises(GlobalSchedulerError, match="provider_cost_usd exhausted"):
        runner._require_dispatch_capacity(action, method, state_path)

    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["cost"]["provider_cost_usd"] = "1.0"
    _write(state_path, state)
    with pytest.raises(GlobalSchedulerError, match="sessions.*exceeded"):
        runner._require_dispatch_capacity(action, method, state_path)


def test_augment_panel_evidence_passes_two_matched_parent_dirs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reports = [
        _write(tmp_path / f"r{index}" / "pilot-report.json", {"status": "complete"})
        for index in (1, 2)
    ]
    calls: dict[str, object] = {}

    def fake_append(**kwargs):
        calls.update(kwargs)
        return {
            "status": "complete",
            "answer_free": True,
            "panel_index": 1,
            "next_evidence_root": str((tmp_path / "next").resolve()),
            "accepted_claim_count": 1,
            "matched_repetition_count": 2,
            "sealed_task_ids_present": [],
            "cost": {},
        }

    monkeypatch.setattr(trajectory_bank, "append_accepted_panel_history", fake_append)
    action = {
        "kind": "augment_panel_evidence",
        "source_evidence_root": str(tmp_path / "source"),
        "next_evidence_root": str((tmp_path / "next").resolve()),
        "panel_index": 1,
        "family": "family",
        "task_ids": ["t1"],
        "accepted_claims": [
            {
                "claim_id": "c1",
                "claim": "public claim",
                "surfaces": ["skills"],
                "basis_refs": ["public:t1"],
            }
        ],
        "matched_report_paths": [str(path) for path in reports],
    }

    result = runner._augment_panel_evidence_result(action)

    assert result["accounting_complete"] is True
    assert calls["matched_run_dirs"] == [path.parent for path in reports]


def test_carry_panel_evidence_preserves_only_prior_accepted_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: dict[str, object] = {}

    def fake_carry(**kwargs):
        calls.update(kwargs)
        return {
            "status": "complete",
            "answer_free": True,
            "next_evidence_root": str((tmp_path / "next").resolve()),
            "carried_entry_count": 1,
            "sealed_task_ids_present": [],
            "cost": {},
        }

    monkeypatch.setattr(trajectory_bank, "carry_accepted_panel_history", fake_carry)
    action = {
        "kind": "carry_panel_evidence",
        "source_evidence_root": str(tmp_path / "source"),
        "next_evidence_root": str((tmp_path / "next").resolve()),
    }

    result = runner._carry_panel_evidence_result(action)

    assert result["accounting_complete"] is True
    assert calls == {
        "source_evidence_root": tmp_path / "source",
        "next_evidence_root": (tmp_path / "next").resolve(),
    }


def test_bank_builder_uses_public_input_manifest_and_method_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pilot_report = _write(
        tmp_path / "h0" / "pilot-report.json", {"status": "complete"}
    )
    output_root = tmp_path / "bank"
    _write(
        output_root / "evolver-answer-free" / "bank-index.json",
        {
            "tasks": [{"task_id": "t1"}],
            "panels": [{"panel_index": 1, "evidence_root": "panel-1"}],
        },
    )
    calls: dict[str, object] = {}

    def fake_build(**kwargs):
        calls.update(kwargs)
        return {"complete": True, "cost": {}}

    monkeypatch.setattr(runner, "build_trajectory_bank", fake_build)
    public_manifest = tmp_path / "public-manifest.json"
    method_path = tmp_path / "method.json"
    launch = {
        "qfbench_public_manifest": str(public_manifest),
        "method_plan_path": str(method_path),
        "public_contracts_root": str(tmp_path / "contracts"),
    }
    action = {
        "controller_reports": [str(pilot_report)],
        "output_root": str(output_root),
        "task_ids": ["t1"],
    }

    result = runner._build_bank_result(action, launch)

    assert calls["manifest_path"] == public_manifest
    assert calls["scheduler_plan_path"] == method_path
    assert result["accounting_complete"] is True
