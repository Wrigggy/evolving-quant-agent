from __future__ import annotations

import json
from pathlib import Path

import pytest

from qea.qfbench_lineage import LineageError
from scripts.run_qfbench_discovery_pilot import main as run_discovery_pilot
from scripts.run_qfbench_lineage_controller import (
    _candidate_information_set_review_package,
    _candidate_information_set_review_result,
    _information_set_review_spec,
    _quantcodeeval_property_set_safe,
    _trajectory_line_excerpt,
    build_candidate_information_set_review_argv,
    build_child_argv,
    build_proposal_argv,
    build_quantcodeeval_child_argv,
    failed_property_delta_from_reports,
    property_set_safe,
    property_set_safe_from_reports,
    run_controller,
)


def test_existing_information_review_result_requires_same_retained_input(tmp_path):
    states_root = tmp_path / "states"
    result_dir = tmp_path / "results" / "review-r1"
    result_dir.mkdir(parents=True)
    result_dir.joinpath("RESULT.json").write_text("{}\n")
    input_dir = states_root / "review-inputs"
    input_dir.mkdir(parents=True)
    input_dir.joinpath("review-r1.json").write_text(
        json.dumps({"schema_version": 1, "candidate_id": "old"}) + "\n"
    )

    with pytest.raises(LineageError, match="differs from the current reviewed"):
        _candidate_information_set_review_result(
            {"runtime": {"results_dir": str(tmp_path / "results")}},
            {"review_id": "review-r1"},
            {"schema_version": 1, "candidate_id": "new"},
            states_root,
            approve_external_run=False,
            runner=lambda _argv: (_ for _ in ()).throw(
                AssertionError("existing Review must not dispatch")
            ),
        )


def test_existing_information_review_result_requires_retained_input(tmp_path):
    result_dir = tmp_path / "results" / "review-r1"
    result_dir.mkdir(parents=True)
    result_dir.joinpath("RESULT.json").write_text("{}\n")

    with pytest.raises(LineageError, match="has no matching retained input package"):
        _candidate_information_set_review_result(
            {"runtime": {"results_dir": str(tmp_path / "results")}},
            {"review_id": "review-r1"},
            {"schema_version": 1, "candidate_id": "new"},
            tmp_path / "states",
            approve_external_run=False,
            runner=lambda _argv: (_ for _ in ()).throw(
                AssertionError("existing Review must not dispatch")
            ),
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


def _single_arm_report(
    root: Path,
    run_id: str,
    task: str,
    arm: str,
    score,
    failures=(),
    *,
    cost="0.004",
):
    attempt_id = f"{run_id}-{arm}"
    ctrf = root / "attempts" / attempt_id / "verifier/ctrf.json"
    ctrf.parent.mkdir(parents=True, exist_ok=True)
    ctrf.write_text(json.dumps({"results": {"tests": [
        {"name": name, "status": "failed"} for name in failures
    ]}}))
    report = {
        "status": "complete",
        "run_id": run_id,
        "summaries": {arm: {"scores": [{
            "task_id": task,
            "reward": score[2],
            "tests_passed": score[0],
            "tests_failed": score[1] - score[0],
            "verifier_exit_code": 0,
        }]}},
        "activations": {arm: {"attempts": [{
            "task_id": task,
            "attempt_id": attempt_id,
        }]}},
        "cost": {
            "provider_cost_usd": cost,
            "completed_request_count": 1,
            "total_tokens": 25,
        },
    }
    path = root / "pilot-report.json"
    path.write_text(json.dumps(report))
    return path, report


def _qce_result(
    path: Path,
    *,
    run_id: str,
    task_id: str,
    passed: int | None,
    failed: int | None,
    reward: float,
    diagnostic_tags=(),
    verifier_exit_code: int | None = 0,
    cost="0.005",
):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "complete",
        "run_id": run_id,
        "score_summary": {
            "scores": [{
                "task_id": task_id,
                "domain": "portfolio",
                "reward": reward,
                "diagnostic_tags": list(diagnostic_tags),
                "verifier_exit_code": verifier_exit_code,
                "tests_passed": passed,
                "tests_failed": failed,
            }]
        },
    }
    if cost is not None:
        payload["cost_audit"] = {
            "provider_cost_usd": cost,
            "completed_request_count": 1,
            "total_tokens": 50,
            "cost_complete": True,
        }
    path.write_text(json.dumps(payload))
    return path


def _add_replay_candidate_reviews(plan, tmp_path: Path) -> None:
    """Give legacy transition fixtures one real universal Review PASS.

    These tests predate the universal gate.  Keep their lifecycle assertions
    focused by materializing small local parent/candidate workers and a retained
    answer-free Reviewer result for every changed candidate.
    """

    runtime = plan.setdefault("runtime", {})
    if "results_dir" not in runtime:
        runtime["results_dir"] = str(tmp_path / "review-results")
    results_dir = Path(str(runtime["results_dir"]))
    for index, lineage in enumerate(plan["lineages"]):
        lineage_id = str(lineage["lineage_id"])
        parent = lineage["parent"]
        parent_dir = Path(str(parent["worker_dir"]))
        if not parent_dir.is_dir():
            parent_dir = tmp_path / "review-workers" / lineage_id / "parent"
            parent_dir.mkdir(parents=True, exist_ok=True)
            parent_dir.joinpath("systemprompt.md").write_text(
                "Follow the public task instructions.\n"
            )
            parent["worker_dir"] = str(parent_dir)

        proposal = lineage.get("proposal")
        if isinstance(proposal, dict):
            report_path = Path(str(proposal["replay_report"]))
            report = json.loads(report_path.read_text())
            if report.get("decision") != "ACT" or report.get("admission", {}).get(
                "admitted"
            ) is not True:
                continue
            candidate_dir = Path(str(report.get("candidate_dir", "")))
            if not candidate_dir.is_dir():
                candidate_dir = (
                    tmp_path / "review-workers" / lineage_id / "candidate"
                )
                candidate_dir.mkdir(parents=True, exist_ok=True)
                candidate_dir.joinpath("systemprompt.md").write_text(
                    "Follow the public task instructions.\n"
                    "Apply the declared public output rule.\n"
                )
                report["candidate_dir"] = str(candidate_dir)
            hypothesis = report.setdefault("summary", {}).setdefault(
                "discovery_hypothesis", {}
            ).setdefault("hypothesis", {})
            claims = hypothesis.setdefault(
                "worker_visible_claims",
                [
                    {
                        "claim_id": "public-output-positive",
                        "claim": "Apply the declared public output rule.",
                        "surfaces": ["systemprompt"],
                        "basis_refs": ["public:instruction"],
                    }
                ],
            )
            report_path.write_text(json.dumps(report))
            candidate_version = str(
                proposal.get("candidate_version")
                or proposal.get("replay_run_id")
                or "candidate"
            )
        else:
            candidate = lineage["candidate"]
            candidate_dir = Path(str(candidate["worker_dir"]))
            if not candidate_dir.is_dir():
                candidate_dir = (
                    tmp_path / "review-workers" / lineage_id / "candidate"
                )
                candidate_dir.mkdir(parents=True, exist_ok=True)
                candidate_dir.joinpath("systemprompt.md").write_text(
                    "Follow the public task instructions.\n"
                    "Apply the declared public output rule.\n"
                )
                candidate["worker_dir"] = str(candidate_dir)
            candidate_version = str(candidate["version"])
            claims = [
                {
                    "claim_id": "public-output-positive",
                    "claim": "Apply the declared public output rule.",
                    "surfaces": ["systemprompt"],
                    "basis_refs": ["public:instruction"],
                }
            ]

        review_id = f"{lineage_id}-universal-review-{index}"
        sources = {
            "public_sources": [
                {
                    "ref": "public:instruction",
                    "source_type": "public_contract",
                    "excerpt": "Apply the declared public output rule.",
                }
            ],
            "optimize_only_sources": [],
        }
        review_spec = {
            "enabled": True,
            "feedback_mode": "answer_free",
            "review_id": review_id,
            "worker_visible_claims": claims,
            **sources,
        }
        lineage["candidate_information_set_review"] = review_spec
        package, hold_reason = _candidate_information_set_review_package(
            {
                "current_parent": parent,
                "candidate": {
                    "version": candidate_version,
                    "worker_dir": str(candidate_dir),
                },
                "proposal": {"worker_visible_claims": claims},
            },
            review_spec,
        )
        assert hold_reason is None
        _write_information_review_result(results_dir / review_id, package)


def _review_bound_lineage(lineage):
    """Bind an argv-only fixture to its declared reviewed candidate path."""

    candidate = lineage["candidate"]
    candidate_dir = candidate["worker_dir"]
    candidate["information_set_review"] = {
        "review_id": "argv-review",
        "overall_verdict": "PASS",
        "reviewed_candidate_dir": candidate_dir,
    }
    lineage["observations"] = {
        "information_set_review": {
            "review_id": "argv-review",
            "overall_verdict": "PASS",
            "reviewed_candidate_dir": candidate_dir,
            "coverage_review": {"verdict": "PASS"},
        }
    }
    return lineage


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


def test_reused_parent_property_safety_reads_each_report(tmp_path):
    parent_path, parent_report = _single_arm_report(
        tmp_path / "parent",
        "parent-r1",
        "task-p",
        "h0",
        (38, 39, 0.96),
        failures=("barrier",),
    )
    candidate_path, candidate_report = _single_arm_report(
        tmp_path / "candidate",
        "candidate-r1",
        "task-p",
        "candidate",
        (38, 39, 0.96),
        failures=("vanilla",),
    )

    assert not property_set_safe_from_reports(
        parent_report_path=parent_path,
        parent_report=parent_report,
        parent_arm="h0",
        candidate_report_path=candidate_path,
        candidate_report=candidate_report,
        candidate_arm="candidate",
        task_id="task-p",
    )
    assert failed_property_delta_from_reports(
        parent_report_path=parent_path,
        parent_report=parent_report,
        parent_arm="h0",
        candidate_report_path=candidate_path,
        candidate_report=candidate_report,
        candidate_arm="candidate",
        task_id="task-p",
    ) == {
        "parent_failed": ["barrier"],
        "candidate_failed": ["vanilla"],
        "resolved": ["barrier"],
        "introduced": ["vanilla"],
        "persistent": [],
    }

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
    _add_replay_candidate_reviews(plan, tmp_path)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan))

    def fail_if_called(_argv):
        raise AssertionError("replay must not dispatch a child")

    result = run_controller(plan_path, tmp_path / "state", runner=fail_if_called)
    again = run_controller(plan_path, tmp_path / "state", runner=fail_if_called)

    assert result["lineages"]["positive"]["decision"] == "PROMOTE"
    assert result["lineages"]["positive"]["phase"] == "FROZEN"
    assert again == result


def test_one_controller_replays_qfbench_and_quantcodeeval_lineages(tmp_path):
    qf_reports = tmp_path / "qf-reports"
    qf_target, _ = _report(
        qf_reports / "target", "qf-target", "task-t", (1, 2, 0), (2, 2, 1), {}
    )
    qf_repeat, _ = _report(
        qf_reports / "repeat", "qf-repeat", "task-t", (1, 2, 0), (2, 2, 1), {}
    )
    qf_protect, _ = _report(
        qf_reports / "protect", "qf-protect", "task-p", (2, 2, 1), (2, 2, 1), {}
    )
    qce_parent_target = _qce_result(
        tmp_path / "qce/parent-target.json",
        run_id="qce-parent-t26",
        task_id="T26",
        passed=None,
        failed=None,
        reward=0,
        diagnostic_tags=("missing_artifact",),
        verifier_exit_code=None,
        cost=None,
    )
    qce_candidate_target = _qce_result(
        tmp_path / "qce/candidate-target.json",
        run_id="qce-candidate-target",
        task_id="T26",
        passed=16,
        failed=1,
        reward=0,
        diagnostic_tags=("tests_failed",),
    )
    qce_candidate_repeat = _qce_result(
        tmp_path / "qce/candidate-repeat.json",
        run_id="qce-candidate-repeat",
        task_id="T26",
        passed=16,
        failed=1,
        reward=0,
        diagnostic_tags=("tests_failed",),
    )
    qce_parent_protect = _qce_result(
        tmp_path / "qce/parent-protect.json",
        run_id="qce-parent-t27",
        task_id="T27",
        passed=14,
        failed=0,
        reward=1,
        cost=None,
    )
    qce_candidate_protect = _qce_result(
        tmp_path / "qce/candidate-protect.json",
        run_id="qce-candidate-protect",
        task_id="T27",
        passed=14,
        failed=0,
        reward=1,
    )
    plan = {
        "schema_version": 1,
        "controller_run_id": "cross-benchmark-r1",
        "mode": "replay",
        "runtime": {},
        "limits": {"provider_cost_usd": 1},
        "lineages": [
            {
                "lineage_id": "qf",
                "parent": {"version": "h0", "worker_dir": "/qf-h0"},
                "candidate": {"version": "qf-c1", "worker_dir": "/qf-c1"},
                "stages": [
                    {
                        "name": "target",
                        "task_id": "task-t",
                        "replay_report": str(qf_target),
                        "parent_arm": "h0",
                        "candidate_arm": "candidate",
                    },
                    {
                        "name": "repeat",
                        "task_id": "task-t",
                        "replay_report": str(qf_repeat),
                        "parent_arm": "h0",
                        "candidate_arm": "candidate",
                    },
                    {
                        "name": "protection",
                        "task_id": "task-p",
                        "replay_report": str(qf_protect),
                        "parent_arm": "h0",
                        "candidate_arm": "candidate",
                    },
                ],
            },
            {
                "lineage_id": "qce",
                "parent": {"version": "quant-h0", "worker_dir": "/qce-h0"},
                "candidate": {"version": "qce-c1", "worker_dir": "/qce-c1"},
                "stages": [
                    {
                        "name": "target",
                        "benchmark": "quantcodeeval",
                        "task_id": "T26",
                        "parent_result": str(qce_parent_target),
                        "candidate_result": str(qce_candidate_target),
                        "official_property_total": 17,
                    },
                    {
                        "name": "repeat",
                        "benchmark": "quantcodeeval",
                        "task_id": "T26",
                        "parent_result": str(qce_parent_target),
                        "candidate_result": str(qce_candidate_repeat),
                        "official_property_total": 17,
                    },
                    {
                        "name": "protection",
                        "benchmark": "quantcodeeval",
                        "task_id": "T27",
                        "parent_result": str(qce_parent_protect),
                        "candidate_result": str(qce_candidate_protect),
                        "official_property_total": 14,
                        "property_set_safe": True,
                    },
                ],
            },
        ],
    }
    _add_replay_candidate_reviews(plan, tmp_path)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan))

    def fail_if_called(_argv):
        raise AssertionError("cross-benchmark replay must not dispatch a child")

    result = run_controller(
        plan_path, tmp_path / "state", runner=fail_if_called
    )
    again = run_controller(
        plan_path, tmp_path / "state", runner=fail_if_called
    )
    qce = result["lineages"]["qce"]

    assert result["lineages"]["qf"]["decision"] == "PROMOTE"
    assert qce["decision"] == "PROMOTE"
    assert qce["phase"] == "FROZEN"
    assert qce["cost"] == {
        "provider_cost_usd": "0.025",
        "completed_requests": 4,
        "total_tokens": 200,
    }
    assert qce["accounted_run_ids"] == [
        "qce-candidate-target",
        "qce-candidate-repeat",
        "qce-candidate-protect",
    ]
    assert qce["observations"]["target"]["parent"] == {
        "reward": 0.0,
        "tests_passed": 0,
        "tests_failed": 17,
        "official_valid": True,
        "verifier_executed": False,
        "verifier_exit_code": None,
        "selection_source": "official_worker_artifact_contract_zero",
    }
    assert qce["observations"]["target"]["provenance"][
        "cost_accounting"
    ] == "candidate_only"
    assert again == result


def test_quantcodeeval_infrastructure_incomplete_fails_closed(tmp_path):
    parent = _qce_result(
        tmp_path / "qce/parent.json",
        run_id="qce-parent",
        task_id="T26",
        passed=None,
        failed=None,
        reward=0,
        diagnostic_tags=("missing_artifact",),
        verifier_exit_code=None,
    )
    candidate = tmp_path / "qce/candidate-incomplete.json"
    candidate.write_text(json.dumps({
        "status": "evaluation_failed",
        "official_evaluated": False,
        "run_id": "qce-candidate-incomplete",
        "partial_cost_and_lifecycle_audit": {
            "provider_cost_usd": "0.003",
            "completed_request_count": 1,
            "total_tokens": 40,
            "cost_complete": True,
        },
    }))
    plan = {
        "schema_version": 1,
        "controller_run_id": "qce-incomplete-r1",
        "mode": "replay",
        "runtime": {},
        "limits": {"provider_cost_usd": 1},
        "lineages": [{
            "lineage_id": "qce",
            "parent": {"version": "quant-h0", "worker_dir": "/qce-h0"},
            "candidate": {"version": "qce-c1", "worker_dir": "/qce-c1"},
            "stages": [
                {
                    "name": "target",
                    "benchmark": "quantcodeeval",
                    "task_id": "T26",
                    "parent_result": str(parent),
                    "candidate_result": str(candidate),
                    "official_property_total": 17,
                },
                {"name": "repeat", "task_id": "T26"},
                {"name": "protection", "task_id": "T27"},
            ],
        }],
    }
    _add_replay_candidate_reviews(plan, tmp_path)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan))

    with pytest.raises(LineageError, match="incomplete infrastructure"):
        run_controller(plan_path, tmp_path / "state")


def test_quantcodeeval_candidate_without_cost_is_not_lineage_ready(tmp_path):
    parent = _qce_result(
        tmp_path / "qce/parent.json",
        run_id="qce-parent",
        task_id="T26",
        passed=None,
        failed=None,
        reward=0,
        diagnostic_tags=("missing_artifact",),
        verifier_exit_code=None,
        cost=None,
    )
    candidate = _qce_result(
        tmp_path / "qce/candidate.json",
        run_id="qce-candidate",
        task_id="T26",
        passed=16,
        failed=1,
        reward=0,
        diagnostic_tags=("tests_failed",),
        cost=None,
    )
    plan = {
        "schema_version": 1,
        "controller_run_id": "qce-no-cost-r1",
        "mode": "replay",
        "runtime": {},
        "limits": {"provider_cost_usd": 1},
        "lineages": [{
            "lineage_id": "qce",
            "parent": {"version": "quant-h0", "worker_dir": "/qce-h0"},
            "candidate": {"version": "qce-c1", "worker_dir": "/qce-c1"},
            "stages": [
                {
                    "name": "target",
                    "benchmark": "quantcodeeval",
                    "task_id": "T26",
                    "parent_result": str(parent),
                    "candidate_result": str(candidate),
                    "official_property_total": 17,
                },
                {"name": "repeat", "task_id": "T26"},
                {"name": "protection", "task_id": "T27"},
            ],
        }],
    }
    _add_replay_candidate_reviews(plan, tmp_path)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan))

    with pytest.raises(LineageError, match="explicit cost accounting"):
        run_controller(plan_path, tmp_path / "state")


def test_live_quantcodeeval_candidate_stages_resume_without_dispatch(tmp_path):
    parent_target = _qce_result(
        tmp_path / "parents/target.json",
        run_id="qce-parent-t26",
        task_id="T26",
        passed=15,
        failed=2,
        reward=0,
        diagnostic_tags=("tests_failed",),
        cost=None,
    )
    parent_target_payload = json.loads(parent_target.read_text())
    parent_target_payload.pop("run_id")
    parent_target.write_text(json.dumps(parent_target_payload))
    parent_protection = _qce_result(
        tmp_path / "parents/protection.json",
        run_id="qce-parent-t27",
        task_id="T27",
        passed=13,
        failed=1,
        reward=0,
        diagnostic_tags=("tests_failed",),
        cost=None,
    )
    plan = {
        "schema_version": 1,
        "controller_run_id": "qce-live-r1",
        "mode": "live",
        "runtime": {
            "python": "/python",
            "source_root": "/source",
            "results_dir": str(tmp_path / "results"),
            "quantcodeeval_config": "/config.json",
            "quantcodeeval_release": "/release",
            "quantcodeeval_worker_image": "worker:fixed",
            "quantcodeeval_verifier_image": "verifier:fixed",
            "quantcodeeval_proxy_image": "proxy:fixed",
        },
        "limits": {"provider_cost_usd": 1},
        "lineages": [{
            "lineage_id": "qce-live",
            "parent": {"version": "quant-h0", "worker_dir": "/qce-h0"},
            "candidate": {
                "version": "quant-h0",
                "worker_dir": "/qce-h0",
                "activation_run": "/activation",
            },
            "stages": [
                {
                    "name": "target",
                    "benchmark": "quantcodeeval",
                    "task_id": "T26",
                    "parent_result": str(parent_target),
                    "parent_run_id": "qce-parent-t26",
                    "official_property_total": 17,
                    "live_run_id": "qce-live-target",
                },
                {
                    "name": "repeat",
                    "benchmark": "quantcodeeval",
                    "task_id": "T26",
                    "parent_result": str(parent_target),
                    "parent_run_id": "qce-parent-t26",
                    "official_property_total": 17,
                    "live_run_id": "qce-live-repeat",
                },
                {
                    "name": "protection",
                    "benchmark": "quantcodeeval",
                    "task_id": "T27",
                    "parent_result": str(parent_protection),
                    "official_property_total": 14,
                    "live_run_id": "qce-live-protection",
                },
            ],
        }],
    }
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan))
    calls = []

    def fake_runner(argv):
        argv = list(argv)
        calls.append(argv)
        run_dir = Path(argv[argv.index("--run-dir") + 1])
        task_id = argv[argv.index("--task") + 1]
        if task_id == "T26":
            passed, failed, reward = 16, 1, 0
        else:
            passed, failed, reward = 14, 0, 1
        _qce_result(
            run_dir / "FULL-CANDIDATE-RESULT.json",
            run_id=run_dir.name,
            task_id=task_id,
            passed=passed,
            failed=failed,
            reward=reward,
            diagnostic_tags=(() if failed == 0 else ("tests_failed",)),
        )

    result = run_controller(
        plan_path,
        tmp_path / "state",
        approve_external_run=True,
        runner=fake_runner,
    )
    again = run_controller(
        plan_path,
        tmp_path / "state",
        approve_external_run=True,
        runner=fake_runner,
    )

    state = result["lineages"]["qce-live"]
    assert state["decision"] == "PROMOTE"
    assert state["phase"] == "FROZEN"
    assert state["accounted_run_ids"] == [
        "qce-live-target",
        "qce-live-repeat",
        "qce-live-protection",
    ]
    assert state["cost"] == {
        "provider_cost_usd": "0.015",
        "completed_requests": 3,
        "total_tokens": 150,
    }
    assert state["observations"]["protection"]["property_set_safe"] is True
    assert len(calls) == 3
    assert again == result


def test_live_quantcodeeval_evaluation_failure_remains_infrastructure(tmp_path):
    parent = _qce_result(
        tmp_path / "parent.json",
        run_id="qce-parent-t26",
        task_id="T26",
        passed=15,
        failed=2,
        reward=0,
        diagnostic_tags=("tests_failed",),
        cost=None,
    )
    plan = {
        "controller_run_id": "qce-live-failure",
        "mode": "live",
        "runtime": {
            "python": "/python",
            "source_root": "/source",
            "results_dir": str(tmp_path / "results"),
            "quantcodeeval_config": "/config.json",
            "quantcodeeval_release": "/release",
            "quantcodeeval_worker_image": "worker:fixed",
            "quantcodeeval_verifier_image": "verifier:fixed",
            "quantcodeeval_proxy_image": "proxy:fixed",
        },
        "lineages": [{
            "lineage_id": "qce-live",
            "parent": {"version": "quant-h0", "worker_dir": "/qce-h0"},
            "candidate": {
                "version": "quant-h0",
                "worker_dir": "/qce-h0",
                "activation_run": "/activation",
            },
            "stages": [
                {
                    "name": "target",
                    "benchmark": "quantcodeeval",
                    "task_id": "T26",
                    "parent_result": str(parent),
                    "official_property_total": 17,
                    "live_run_id": "qce-live-failed-target",
                },
                {"name": "repeat", "task_id": "T26"},
                {"name": "protection", "task_id": "T27"},
            ],
        }],
    }
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan))

    def failed_runner(argv):
        argv = list(argv)
        run_dir = Path(argv[argv.index("--run-dir") + 1])
        run_dir.mkdir(parents=True)
        (run_dir / "FULL-CANDIDATE-RESULT.json").write_text(json.dumps({
            "status": "evaluation_failed",
            "official_evaluated": False,
            "run_id": run_dir.name,
            "partial_cost_and_lifecycle_audit": {
                "provider_cost_usd": "0.003",
                "completed_request_count": 1,
                "total_tokens": 40,
                "cost_complete": True,
            },
        }))
        return type("Result", (), {"returncode": 1})()

    with pytest.raises(LineageError, match="incomplete infrastructure"):
        run_controller(
            plan_path,
            tmp_path / "state",
            approve_external_run=True,
            runner=failed_runner,
        )


def test_quantcodeeval_protection_infers_only_conclusive_count_cases():
    def comparison(parent_failed, candidate_failed):
        return {
            "parent": {"tests_failed": parent_failed},
            "candidate": {"tests_failed": candidate_failed},
        }

    assert _quantcodeeval_property_set_safe({}, comparison(3, 0))
    assert not _quantcodeeval_property_set_safe({}, comparison(0, 1))
    assert _quantcodeeval_property_set_safe(
        {"property_set_safe": True}, comparison(2, 1)
    )
    with pytest.raises(LineageError, match="needs explicit property_set_safe"):
        _quantcodeeval_property_set_safe({}, comparison(2, 1))


def test_live_quantcodeeval_child_requires_approval_and_fixed_run_dir(tmp_path):
    plan = {
        "controller_run_id": "main0",
        "runtime": {
            "python": "/python",
            "source_root": "/source",
            "results_dir": str(tmp_path / "results"),
            "quantcodeeval_config": "/config.json",
            "quantcodeeval_release": "/release",
            "quantcodeeval_worker_image": "worker:fixed",
            "quantcodeeval_verifier_image": "verifier:fixed",
            "quantcodeeval_proxy_image": "proxy:fixed",
        },
    }
    lineage = {
        "lineage_id": "qce",
        "parent": {"version": "quant-h0", "worker_dir": "/qce-h0"},
        "candidate": {
            "version": "quant-h0",
            "worker_dir": "/qce-h0",
            "activation_run": "/activation",
        },
    }
    stage = {
        "name": "target",
        "task_id": "T26",
        "live_run_id": "qce-target-fixed",
    }

    with pytest.raises(LineageError, match="was not approved"):
        build_quantcodeeval_child_argv(
            plan, lineage, stage, approve_external_run=False
        )
    argv = build_quantcodeeval_child_argv(
        plan, lineage, stage, approve_external_run=True
    )

    assert argv[1] == "/source/scripts/run_quantcodeeval_v2_candidate.py"
    run_dir = argv[argv.index("--run-dir") + 1]
    assert run_dir == str(tmp_path / "results/qce-target-fixed")
    assert argv[argv.index("--activation-run") + 1] == "/activation"
    assert argv[argv.index("--task") + 1] == "T26"


def test_live_quantcodeeval_child_reuses_h0_preflight_image_refs(tmp_path):
    release = tmp_path / "release"
    preflight = release / "h0/H0-PREFLIGHT.json"
    preflight.parent.mkdir(parents=True)
    preflight.write_text(json.dumps({
        "worker_image_ref": "existing-worker-id",
        "verifier_image_ref": "existing-verifier-id",
        "proxy_image_ref": "existing-proxy-id",
    }))
    plan = {
        "controller_run_id": "main0",
        "runtime": {
            "python": "/python",
            "source_root": "/source",
            "results_dir": str(tmp_path / "results"),
            "quantcodeeval_config": "/config.json",
            "quantcodeeval_release": str(release),
        },
    }
    lineage = {
        "lineage_id": "qce",
        "parent": {"version": "quant-h0", "worker_dir": "/qce-h0"},
        "candidate": {
            "version": "quant-h0",
            "worker_dir": "/qce-h0",
            "activation_run": "/activation",
        },
    }
    stage = {"name": "target", "task_id": "T26"}

    argv = build_quantcodeeval_child_argv(
        plan, lineage, stage, approve_external_run=True
    )

    assert argv[argv.index("--worker-image") + 1] == "existing-worker-id"
    assert argv[argv.index("--verifier-image") + 1] == "existing-verifier-id"
    assert argv[argv.index("--proxy-image") + 1] == "existing-proxy-id"


def test_live_quantcodeeval_changed_candidate_dispatch_is_blocked(tmp_path):
    plan = {
        "controller_run_id": "main0",
        "runtime": {
            "python": "/python",
            "source_root": "/source",
            "results_dir": str(tmp_path / "results"),
            "quantcodeeval_config": "/config.json",
            "quantcodeeval_release": "/release",
            "quantcodeeval_worker_image": "worker:fixed",
            "quantcodeeval_verifier_image": "verifier:fixed",
            "quantcodeeval_proxy_image": "proxy:fixed",
        },
    }
    lineage = _review_bound_lineage({
        "lineage_id": "qce",
        "parent": {"worker_dir": "/qce-h0"},
        "candidate": {
            "worker_dir": "/reviewed-candidate",
            "activation_run": "/activation",
        },
    })

    with pytest.raises(LineageError, match="cannot bind.*dispatch is blocked"):
        build_quantcodeeval_child_argv(
            plan,
            lineage,
            {"name": "target", "task_id": "T26"},
            approve_external_run=True,
        )


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

    argv = build_child_argv(
        plan, _review_bound_lineage(lineage), stage, approve_external_run=True
    )

    assert argv[1] == "/source/scripts/run_qfbench_component_pilot.py"
    assert "parent=/h0" in argv
    assert "candidate=/c1" in argv
    assert argv[-1] == "--approve-external-run"


def test_live_child_argv_requires_retained_review_coverage_observation():
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
        "lineage_id": "missing-review-observation",
        "parent": {"version": "h0", "worker_dir": "/h0"},
        "candidate": {
            "version": "c1",
            "worker_dir": "/reviewed-c1",
            "information_set_review": {
                "review_id": "candidate-only-binding",
                "overall_verdict": "PASS",
                "reviewed_candidate_dir": "/reviewed-c1",
            },
        },
    }

    with pytest.raises(LineageError, match="retained Review PASS coverage"):
        build_child_argv(
            plan,
            lineage,
            {"name": "target", "task_id": "task-t"},
            approve_external_run=True,
        )


def test_live_child_argv_prefers_proposal_bound_activation_token():
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
        "candidate": {
            "worker_dir": "/c1",
            "activation_binding": {"status": "singleton"},
            "activation_token": "actual_new_tool",
        },
    }
    stage = {
        "name": "target",
        "task_id": "task-t",
        "activation_token": "stale_plan_token",
    }

    argv = build_child_argv(
        plan, _review_bound_lineage(lineage), stage, approve_external_run=True
    )

    assert argv[argv.index("--activation-token") + 1] == "actual_new_tool"
    assert "property-P" not in argv


def test_live_child_argv_uses_modified_component_binding():
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
        "candidate": {
            "worker_dir": "/c1",
            "activation_binding": {
                "status": "singleton",
                "modified_registered_tools": ["audit_quant_state"],
            },
            "activation_token": "audit_quant_state",
        },
    }
    stage = {"name": "target", "task_id": "task-t"}

    argv = build_child_argv(
        plan, _review_bound_lineage(lineage), stage, approve_external_run=True
    )

    assert argv[argv.index("--activation-token") + 1] == "audit_quant_state"


def test_live_child_argv_uses_retained_component_binding():
    plan = {
        "controller_run_id": "refine",
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
        "lineage_id": "refinement",
        "parent": {"worker_dir": "/component-v1"},
        "candidate": {
            "worker_dir": "/component-v2",
            "activation_binding": {"status": "retained"},
            "activation_token": "audit_quant_state",
        },
    }
    stage = {"name": "target", "task_id": "task-t"}

    argv = build_child_argv(
        plan, _review_bound_lineage(lineage), stage, approve_external_run=True
    )

    assert argv[argv.index("--activation-token") + 1] == "audit_quant_state"


def test_live_child_argv_does_not_guess_for_ambiguous_proposal_binding():
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
        "candidate": {
            "worker_dir": "/c1",
            "activation_binding": {"status": "ambiguous"},
        },
    }
    stage = {
        "name": "target",
        "task_id": "task-t",
        "activation_token": "stale_plan_token",
    }

    argv = build_child_argv(
        plan, _review_bound_lineage(lineage), stage, approve_external_run=True
    )

    assert "--activation-token" not in argv


def test_reviewed_preconstructed_candidate_ignores_stage_activation_overlay():
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
    lineage = _review_bound_lineage({
        "lineage_id": "preconstructed",
        "parent": {"version": "h0", "worker_dir": "/h0"},
        "candidate": {"version": "c1", "worker_dir": "/reviewed-c1"},
    })

    argv = build_child_argv(
        plan,
        lineage,
        {
            "name": "target",
            "task_id": "task-t",
            "activation_token": "unreviewed-stage-token",
        },
        approve_external_run=True,
    )

    assert "--activation-token" not in argv
    assert "unreviewed-stage-token" not in argv


def test_live_child_argv_runs_only_candidate_when_parent_is_reused():
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
        "name": "target",
        "task_id": "task-t",
        "parent_arm": "h0",
        "candidate_arm": "candidate",
        "parent_comparator": {"id": "h0-task-t-r1"},
    }

    argv = build_child_argv(
        plan, _review_bound_lineage(lineage), stage, approve_external_run=True
    )

    arm_values = [
        argv[index + 1] for index, value in enumerate(argv) if value == "--arm"
    ]
    assert arm_values == ["candidate=/c1"]
    assert argv[-1] == "--approve-external-run"


def test_live_child_argv_runs_only_candidate_with_older_selection_reference():
    plan = {
        "controller_run_id": "refine",
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
        "lineage_id": "refine",
        "parent": {"worker_dir": "/c2"},
        "candidate": {
            "worker_dir": "/c3",
            "activation_binding": {"status": "retained"},
            "activation_token": "check_parameter_admissibility",
        },
    }
    stage = {
        "name": "target",
        "task_id": "dupire-local-vol",
        "parent_arm": "c1-reference",
        "candidate_arm": "c3",
        "selection_reference": {
            "id": "c1-repeat",
            "reference_version": "c1",
        },
    }

    argv = build_child_argv(
        plan, _review_bound_lineage(lineage), stage, approve_external_run=True
    )

    arm_values = [
        argv[index + 1] for index, value in enumerate(argv) if value == "--arm"
    ]
    assert argv[argv.index("--seed-worker") + 1] == "/c2"
    assert arm_values == ["c3=/c3"]
    assert argv[argv.index("--activation-token") + 1] == (
        "check_parameter_admissibility"
    )


def test_replay_reuses_parent_and_accounts_only_candidate_calls(tmp_path):
    parent_target_path, _ = _single_arm_report(
        tmp_path / "parent-target",
        "parent-target-r1",
        "task-t",
        "h0",
        (1, 2, 0),
        cost="0.02",
    )
    parent_protect_path, _ = _single_arm_report(
        tmp_path / "parent-protect",
        "parent-protect-r1",
        "task-p",
        "h0",
        (2, 2, 1),
        cost="0.02",
    )
    candidate_target_path, _ = _single_arm_report(
        tmp_path / "candidate-target",
        "candidate-target-r1",
        "task-t",
        "candidate",
        (2, 2, 1),
    )
    candidate_repeat_path, _ = _single_arm_report(
        tmp_path / "candidate-repeat",
        "candidate-target-r2",
        "task-t",
        "candidate",
        (2, 2, 1),
    )
    candidate_protect_path, _ = _single_arm_report(
        tmp_path / "candidate-protect",
        "candidate-protect-r1",
        "task-p",
        "candidate",
        (2, 2, 1),
    )

    def comparator(comparator_id, report_path, task_id):
        return {
            "id": comparator_id,
            "report_path": str(report_path),
            "parent_version": "h0",
            "task_id": task_id,
            "worker_route": "route-a",
            "worker_budget": "normal",
        }

    plan = {
        "schema_version": 1,
        "controller_run_id": "reuse-r1",
        "mode": "replay",
        "runtime": {"worker_route": "route-a"},
        "limits": {"provider_cost_usd": 1},
        "lineages": [{
            "lineage_id": "reuse",
            "parent": {"version": "h0", "worker_dir": "/h0"},
            "candidate": {"version": "c1", "worker_dir": "/c1"},
            "stages": [
                {
                    "name": "target",
                    "task_id": "task-t",
                    "replay_report": str(candidate_target_path),
                    "parent_arm": "h0",
                    "candidate_arm": "candidate",
                    "parent_comparator": comparator(
                        "h0-task-t-r1", parent_target_path, "task-t"
                    ),
                },
                {
                    "name": "repeat",
                    "task_id": "task-t",
                    "replay_report": str(candidate_repeat_path),
                    "parent_arm": "h0",
                    "candidate_arm": "candidate",
                    "parent_comparator": comparator(
                        "h0-task-t-r1", parent_target_path, "task-t"
                    ),
                },
                {
                    "name": "protection",
                    "task_id": "task-p",
                    "replay_report": str(candidate_protect_path),
                    "parent_arm": "h0",
                    "candidate_arm": "candidate",
                    "parent_comparator": comparator(
                        "h0-task-p-r1", parent_protect_path, "task-p"
                    ),
                },
            ],
        }],
    }
    _add_replay_candidate_reviews(plan, tmp_path)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan))

    def fail_if_called(_argv):
        raise AssertionError("replay must not dispatch a child")

    result = run_controller(
        plan_path, tmp_path / "state", runner=fail_if_called
    )
    again = run_controller(
        plan_path, tmp_path / "state", runner=fail_if_called
    )
    state = result["lineages"]["reuse"]

    assert state["phase"] == "FROZEN"
    assert state["decision"] == "PROMOTE"
    assert state["cost"] == {
        "provider_cost_usd": "0.022",
        "completed_requests": 4,
        "total_tokens": 125,
    }
    assert state["accounted_run_ids"] == [
        "candidate-target-r1",
        "candidate-target-r2",
        "candidate-protect-r1",
    ]
    assert state["observations"]["target"]["parent_comparator_reuse"][
        "id"
    ] == "h0-task-t-r1"
    assert state["observations"]["protection"][
        "parent_comparator_reuse"
    ]["cost_accounting"] == "candidate_only"
    assert again == result


def test_parent_comparator_version_must_match_active_parent(tmp_path):
    parent_path, _ = _single_arm_report(
        tmp_path / "parent", "parent-r1", "task-t", "h0", (1, 2, 0)
    )
    candidate_path, _ = _single_arm_report(
        tmp_path / "candidate",
        "candidate-r1",
        "task-t",
        "candidate",
        (2, 2, 1),
    )
    plan = {
        "schema_version": 1,
        "controller_run_id": "reuse-r1",
        "mode": "replay",
        "runtime": {"worker_route": "route-a"},
        "limits": {"provider_cost_usd": 1},
        "lineages": [{
            "lineage_id": "mismatch",
            "parent": {"version": "promoted-parent", "worker_dir": "/parent"},
            "candidate": {"version": "c2", "worker_dir": "/c2"},
            "stages": [
                {
                    "name": "target",
                    "task_id": "task-t",
                    "replay_report": str(candidate_path),
                    "parent_arm": "h0",
                    "candidate_arm": "candidate",
                    "parent_comparator": {
                        "id": "stale-h0-task-t",
                        "report_path": str(parent_path),
                        "parent_version": "h0",
                        "task_id": "task-t",
                        "worker_route": "route-a",
                        "worker_budget": "normal",
                    },
                },
                {"name": "repeat", "task_id": "task-t"},
                {"name": "protection", "task_id": "task-p"},
            ],
        }],
    }
    _add_replay_candidate_reviews(plan, tmp_path)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan))

    with pytest.raises(
        ValueError, match="parent_version does not match the active lineage"
    ):
        run_controller(plan_path, tmp_path / "state")


def test_selection_reference_can_precede_active_refinement_parent(tmp_path):
    reference_target_path, _ = _single_arm_report(
        tmp_path / "reference-target",
        "c1-target-r1",
        "task-t",
        "c1-reference",
        (1, 2, 0),
    )
    reference_protection_path, _ = _single_arm_report(
        tmp_path / "reference-protection",
        "c1-protection-r1",
        "task-p",
        "c1-reference",
        (2, 2, 1),
    )
    candidate_target_path, _ = _single_arm_report(
        tmp_path / "candidate-target",
        "c3-target-r1",
        "task-t",
        "c3",
        (2, 2, 1),
    )
    candidate_repeat_path, _ = _single_arm_report(
        tmp_path / "candidate-repeat",
        "c3-repeat-r1",
        "task-t",
        "c3",
        (2, 2, 1),
    )
    candidate_protection_path, _ = _single_arm_report(
        tmp_path / "candidate-protection",
        "c3-protection-r1",
        "task-p",
        "c3",
        (2, 2, 1),
    )

    def reference(reference_id, report_path, task_id):
        return {
            "id": reference_id,
            "report_path": str(report_path),
            "reference_version": "c1",
            "task_id": task_id,
            "worker_route": "route-a",
            "worker_budget": "normal",
        }

    plan = {
        "schema_version": 1,
        "controller_run_id": "refinement-selection-reference",
        "mode": "replay",
        "runtime": {"worker_route": "route-a"},
        "limits": {"provider_cost_usd": 1},
        "lineages": [
            {
                "lineage_id": "c2-to-c3",
                "parent": {"version": "c2", "worker_dir": "/c2"},
                "candidate": {"version": "c3", "worker_dir": "/c3"},
                "stages": [
                    {
                        "name": "target",
                        "task_id": "task-t",
                        "replay_report": str(candidate_target_path),
                        "parent_arm": "c1-reference",
                        "candidate_arm": "c3",
                        "selection_reference": reference(
                            "c1-target", reference_target_path, "task-t"
                        ),
                    },
                    {
                        "name": "repeat",
                        "task_id": "task-t",
                        "replay_report": str(candidate_repeat_path),
                        "parent_arm": "c1-reference",
                        "candidate_arm": "c3",
                        "selection_reference": reference(
                            "c1-target", reference_target_path, "task-t"
                        ),
                    },
                    {
                        "name": "protection",
                        "task_id": "task-p",
                        "replay_report": str(candidate_protection_path),
                        "parent_arm": "c1-reference",
                        "candidate_arm": "c3",
                        "selection_reference": reference(
                            "c1-protection",
                            reference_protection_path,
                            "task-p",
                        ),
                    },
                ],
            }
        ],
    }
    _add_replay_candidate_reviews(plan, tmp_path)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan))

    state = run_controller(plan_path, tmp_path / "state")["lineages"][
        "c2-to-c3"
    ]

    assert state["decision"] == "PROMOTE"
    assert state["observations"]["target"]["provenance"][
        "selection_reference_reuse"
    ]["reference_version"] == "c1"
    assert state["observations"]["target"]["provenance"][
        "selection_reference_reuse"
    ]["current_parent_version"] == "c2"


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
    _add_replay_candidate_reviews(plan, tmp_path)
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

    assert paused["phase"] == "INFORMATION_SET_REVIEW"
    assert paused["accounted_run_ids"] == ["proposal-r1"]
    assert resumed["phase"] == "FROZEN"
    assert resumed["decision"] == "PROMOTE"
    assert "stopped_after_stage" not in resumed
    assert "/reviewed-candidates/proposal-lineage/" in (
        resumed["archive"][0]["worker_dir"]
    )
    assert resumed["accounted_run_ids"].count("proposal-r1") == 1
    assert resumed["accounted_review_ids"] == [
        "proposal-lineage-universal-review-0"
    ]


def test_retained_component_refinement_controller_resumes_idempotently(tmp_path):
    parent = tmp_path / "workers/component-v1"
    candidate = tmp_path / "workers/component-v2"
    for worker, prompt in (
        (parent, "Use the registered audit when relevant.\n"),
        (candidate, "Route reconciliation through the registered audit.\n"),
    ):
        worker.joinpath("tool_descriptions").mkdir(parents=True)
        worker.joinpath("tools").mkdir()
        worker.joinpath("agent.yaml").write_text(json.dumps({
            "tools": [
                {
                    "name": "run_shell_command",
                    "yaml_path": "tool_descriptions/shell.yaml",
                },
                {
                    "name": "audit_quant_state",
                    "yaml_path": "tool_descriptions/audit.yaml",
                    "binding": "tools.audit:audit_quant_state",
                },
            ]
        }))
        worker.joinpath("tool_descriptions/shell.yaml").write_text(
            "name: run_shell_command\n"
        )
        worker.joinpath("tool_descriptions/audit.yaml").write_text(
            "name: audit_quant_state\n"
        )
        worker.joinpath("tools/audit.py").write_text(
            "def audit_quant_state():\n    return True\n"
        )
        worker.joinpath("systemprompt.md").write_text(prompt)

    proposal_path = tmp_path / "proposal/proposal-report.json"
    proposal_path.parent.mkdir(parents=True)
    proposal_path.write_text(json.dumps({
        "decision": "ACT",
        "candidate_dir": str(candidate),
        "admission": {"admitted": True},
        "candidate_generation_throughput": {
            "provider_cost_usd": "0.02",
            "completed_request_count": 3,
            "total_tokens": 200,
        },
    }))
    target_path, _ = _report(
        tmp_path / "target",
        "target-r1",
        "task-t",
        (1, 2, 0),
        (2, 2, 1),
        {},
    )
    repeat_path, _ = _report(
        tmp_path / "repeat",
        "repeat-r1",
        "task-t",
        (1, 2, 0),
        (2, 2, 1),
        {},
    )
    protection_path, _ = _report(
        tmp_path / "protection",
        "protection-r1",
        "task-p",
        (2, 2, 1),
        (2, 2, 1),
        {},
    )
    plan = {
        "schema_version": 1,
        "controller_run_id": "retained-refinement-controller",
        "mode": "replay",
        "runtime": {},
        "limits": {"provider_cost_usd": 1},
        "lineages": [{
            "lineage_id": "retained-refinement",
            "parent": {
                "version": "component-v1",
                "worker_dir": str(parent),
                "retained_activation_token": "audit_quant_state",
            },
            "proposal": {
                "replay_report": str(proposal_path),
                "replay_run_id": "proposal-r1",
                "candidate_version": "component-v2",
            },
            "stages": [
                {
                    "name": "target",
                    "task_id": "task-t",
                    "replay_report": str(target_path),
                    "parent_arm": "h0",
                    "candidate_arm": "candidate",
                },
                {
                    "name": "repeat",
                    "task_id": "task-t",
                    "replay_report": str(repeat_path),
                    "parent_arm": "h0",
                    "candidate_arm": "candidate",
                },
                {
                    "name": "protection",
                    "task_id": "task-p",
                    "replay_report": str(protection_path),
                    "parent_arm": "h0",
                    "candidate_arm": "candidate",
                },
            ],
        }],
    }
    _add_replay_candidate_reviews(plan, tmp_path)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan))
    state_dir = tmp_path / "state"

    first = run_controller(plan_path, state_dir)
    resumed = run_controller(plan_path, state_dir)

    state = first["lineages"]["retained-refinement"]
    archived = state["archive"][0]
    assert state["decision"] == "PROMOTE"
    assert archived["activation_token"] == "audit_quant_state"
    assert archived["activation_binding"]["status"] == "retained"
    assert archived["realized_component"]["source"] == (
        "lineage_parent_retained_activation_token"
    )
    assert state["accounted_run_ids"].count("proposal-r1") == 1
    assert resumed == first


def test_opt_in_semantic_repeat_controller_is_resume_idempotent(tmp_path):
    parent = tmp_path / "workers/h0"
    candidate = tmp_path / "workers/candidate"
    parent.mkdir(parents=True)
    candidate.mkdir(parents=True)
    parent.joinpath("agent.yaml").write_text(json.dumps({
        "tools": [{"name": "run_shell_command", "yaml_path": "shell.yaml"}]
    }))
    candidate.joinpath("agent.yaml").write_text(json.dumps({
        "tools": [
            {"name": "run_shell_command", "yaml_path": "shell.yaml"},
            {"name": "audit_component", "yaml_path": "audit.yaml"},
        ]
    }))
    proposal_path = tmp_path / "proposal/proposal-report.json"
    proposal_path.parent.mkdir(parents=True)
    proposal_path.write_text(json.dumps({
        "decision": "ACT",
        "candidate_dir": str(candidate),
        "admission": {"admitted": True},
        "candidate_generation_throughput": {
            "provider_cost_usd": "0.02",
            "completed_request_count": 3,
            "total_tokens": 200,
        },
        "summary": {
            "discovery_hypothesis": {
                "hypothesis": {
                    "selected_relation": {"relation_id": "open-relation"}
                }
            }
        },
    }))
    target_path, target_report = _report(
        tmp_path / "target",
        "target-r1",
        "task-t",
        (1, 3, 0),
        (2, 3, 1),
        {"h0": ["property-P", "property-Z"], "candidate": ["property-Z"]},
    )
    repeat_path, repeat_report = _report(
        tmp_path / "repeat",
        "repeat-r1",
        "task-t",
        (1, 3, 0),
        (2, 3, 1),
        {"h0": ["property-P", "property-Z"], "candidate": ["property-Z"]},
    )
    protection_path, _ = _report(
        tmp_path / "protection",
        "protection-r1",
        "task-p",
        (2, 2, 1),
        (2, 2, 1),
        {},
    )
    for path, report in ((target_path, target_report), (repeat_path, repeat_report)):
        report["activations"]["candidate"].update({
            "activation_count": 1,
        })
        report["activations"]["candidate"]["attempts"][0].update({
            "activation_token": "audit_component",
            "activated": True,
        })
        path.write_text(json.dumps(report))
    plan = {
        "schema_version": 1,
        "controller_run_id": "semantic-repeat-controller",
        "mode": "replay",
        "runtime": {},
        "limits": {"provider_cost_usd": 1},
        "lineages": [{
            "lineage_id": "semantic-repeat-lineage",
            "parent": {"version": "h0", "worker_dir": str(parent)},
            "proposal": {
                "replay_report": str(proposal_path),
                "replay_run_id": "proposal-r1",
                "candidate_version": "candidate-r1",
            },
            "repeat_consistency_policy": "resolved_property_footprint_v1",
            "stages": [
                {
                    "name": "target",
                    "task_id": "task-t",
                    "replay_report": str(target_path),
                    "parent_arm": "h0",
                    "candidate_arm": "candidate",
                },
                {
                    "name": "repeat",
                    "task_id": "task-t",
                    "replay_report": str(repeat_path),
                    "parent_arm": "h0",
                    "candidate_arm": "candidate",
                },
                {
                    "name": "protection",
                    "task_id": "task-p",
                    "replay_report": str(protection_path),
                    "parent_arm": "h0",
                    "candidate_arm": "candidate",
                    "property_set_safe": True,
                },
            ],
        }],
    }
    _add_replay_candidate_reviews(plan, tmp_path)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan))
    state_dir = tmp_path / "state"

    first = run_controller(plan_path, state_dir)
    resumed = run_controller(plan_path, state_dir)

    state = first["lineages"]["semantic-repeat-lineage"]
    assert state["decision"] == "PROMOTE"
    assert (
        state["observations"]["repeat"]["mechanism"]["semantic_repeat"][
            "verdict"
        ]
        == "CONSISTENT"
    )
    assert resumed == first
    assert state["accounted_run_ids"].count("proposal-r1") == 1


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


def test_discovery_direct_selected_probe_dispatch_is_disabled(tmp_path):
    with pytest.raises(
        ValueError,
        match="direct selected-probe Worker dispatch is disabled",
    ):
        run_discovery_pilot([
            "--qfbench-root",
            str(tmp_path / "qfbench"),
            "--qfbench-manifest",
            str(tmp_path / "manifest.json"),
            "--rootless-config",
            str(tmp_path / "rootless.json"),
            "--rootless-image-set-manifest",
            str(tmp_path / "images.json"),
            "--run-id",
            "selected-probe-bypass",
            "--results-dir",
            str(tmp_path / "results"),
            "--backbone",
            str(tmp_path / "h0"),
            "--evidence",
            str(tmp_path / "evidence"),
            "--evolver-dir",
            str(tmp_path / "evolver"),
            "--arm",
            "quant-state-v2",
            "--dispatch-selected-probe",
        ])


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
            "reviews": [
                {
                    "case_id": "same-harness-control",
                    "outcome_severity": "WITHIN_PROVISIONAL_VARIABILITY",
                    "causal_attribution": "WORKER_TRAJECTORY",
                    "quantitative_diagnosis": "NUMERIC_TOLERANCE_ONLY",
                    "next_evidence": "NO_EXTRA_RUN",
                    "evidence_refs": ["control:h0-r1", "control:h0-r2"],
                },
                {
                    "case_id": "search-v2-protection",
                    "outcome_severity": "UNRESOLVED",
                    "causal_attribution": "UNRESOLVED",
                    "quantitative_diagnosis": "NUMERIC_TOLERANCE_ONLY",
                    "next_evidence": "PAIRED_PROTECTION_REPEAT",
                    "evidence_refs": ["search-v2:protect-r1"],
                },
            ],
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
    _add_replay_candidate_reviews(plan, tmp_path)
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
    assert paused["accounted_review_ids"] == [
        "search-v2-universal-review-0"
    ]
    assert resumed == again
    assert resumed["phase"] == "HOLD_FOR_REFINE"
    assert resumed["decision"] == "HOLD_FOR_REFINE"
    assert resumed["accounted_run_ids"] == [
        "target-r1",
        "target-r2",
        "protect-r1",
        "protect-r2",
    ]
    assert resumed["accounted_review_ids"] == [
        "search-v2-universal-review-0",
        "qpr1-review-r1",
    ]
    assert resumed["cost"] == {
        "provider_cost_usd": "0.05966108",
        "completed_requests": 10,
        "total_tokens": 6814,
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

    argv = build_child_argv(
        plan, _review_bound_lineage(lineage), stage, approve_external_run=True
    )

    assert argv[1] == "/source/scripts/run_qfbench_component_pilot.py"
    assert argv[argv.index("--run-id") + 1] == "main0-a-protection_repeat"
    assert argv[argv.index("--task-id") + 1] == "localvol-barrier"


def _information_review_workers(tmp_path):
    parent = tmp_path / "workers/information-parent"
    candidate = tmp_path / "workers/information-candidate"
    for root in (parent, candidate):
        (root / "tool_descriptions").mkdir(parents=True)
        (root / "tools").mkdir()
        (root / "systemprompt.md").write_text("Use public task instructions.\n")
        (root / "tool_descriptions/run_shell_command.tool.yaml").write_text(
            "type: tool\nname: run_shell_command\n"
        )
    parent.joinpath("agent.yaml").write_text(
        "tools:\n  - name: run_shell_command\n"
        "    yaml_path: ./tool_descriptions/run_shell_command.tool.yaml\n"
    )
    candidate.joinpath("agent.yaml").write_text(
        "tools:\n  - name: run_shell_command\n"
        "    yaml_path: ./tool_descriptions/run_shell_command.tool.yaml\n"
        "  - name: audit_public_output\n"
        "    yaml_path: ./tool_descriptions/audit_public_output.tool.yaml\n"
        "    binding: tools.audit:audit_public_output\n"
    )
    candidate.joinpath(
        "tool_descriptions/audit_public_output.tool.yaml"
    ).write_text(
        "type: tool\nname: audit_public_output\n"
        "description: Check the public written-output relation.\n"
    )
    candidate.joinpath("tools/audit.py").write_text(
        "def audit_public_output(values):\n"
        "    return all(value > 0 for value in values)\n"
    )
    return parent, candidate


def _information_review_sources():
    return {
        "public_sources": [
            {
                "ref": "public:instruction",
                "source_type": "public_contract",
                "excerpt": "Written output values must be positive.",
            }
        ],
        "optimize_only_sources": [
            {
                "ref": "diagnostic:target",
                "source_type": "optimize_only_diagnostic",
                "worker_visible": False,
                "excerpt": "The prior artifact failed one hidden property.",
            }
        ],
    }


def _write_information_review_result(result_dir, package, verdict="PASS"):
    result_dir.mkdir(parents=True, exist_ok=True)
    source_input = result_dir / "REQUEST.json"
    source_input.write_text(json.dumps(package, indent=2) + "\n")
    claim_id = package["worker_visible_claims"][0]["claim_id"]
    if verdict == "PASS":
        ref, role = "public:instruction", "PUBLIC_SUPPORT"
    elif verdict == "REJECT":
        ref, role = "diagnostic:target", "OPTIMIZE_ONLY_ORIGIN"
    else:
        ref, role = "candidate:diff", "INSUFFICIENT_PUBLIC_SUPPORT"
    result = {
        "schema_version": 1,
        "status": "complete",
        "review_scope": "answer_rich_evolver_candidate_information_set",
        "source_input": str(source_input),
        "request": {
            "request_count": 1,
            "accounting": {
                "provider_cost_usd": "0.01",
                "prompt_tokens": 30,
                "completion_tokens": 20,
            },
            "response_usage": {"total_tokens": 50},
        },
        "review": {
            "schema_version": 1,
            "review_id": package["review_id"],
            "candidate_id": package["candidate_id"],
            "claim_reviews": [
                {
                    "claim_id": claim_id,
                    "verdict": verdict,
                    "reason": f"fixture {verdict.lower()} boundary",
                    "source_basis": [{"ref": ref, "role": role}],
                }
            ],
            "coverage_review": {
                "verdict": "PASS",
                "reason": "All changed rules are declared.",
                "source_basis": [
                    {"ref": "candidate:diff", "role": "CANDIDATE_EXPOSURE"}
                ],
                "undeclared_exposures": [],
            },
            "overall_verdict": verdict,
        },
        "worker_visible": False,
        "promotion_authority": False,
    }
    result_dir.joinpath("RESULT.json").write_text(json.dumps(result))


def _information_review_controller_plan(tmp_path, *, mode="live"):
    parent, candidate = _information_review_workers(tmp_path)
    proposal_path = tmp_path / "proposal/proposal-report.json"
    proposal_path.parent.mkdir(parents=True)
    proposal_path.write_text(
        json.dumps(
            {
                "decision": "ACT",
                "candidate_dir": str(candidate),
                "admission": {"admitted": True},
                "candidate_generation_throughput": {
                    "provider_cost_usd": "0.02",
                    "completed_request_count": 3,
                    "total_tokens": 200,
                },
                "summary": {
                    "discovery_hypothesis": {
                        "hypothesis": {
                            "worker_visible_claims": [
                                {
                                    "claim_id": "public-output-positive",
                                    "claim": "Written output values must be positive.",
                                    "surfaces": ["tools"],
                                    "basis_refs": [
                                        "public:instruction",
                                        "diagnostic:target",
                                    ],
                                }
                            ]
                        }
                    }
                },
            }
        )
    )
    target_path, _ = _report(
        tmp_path / "information-target",
        "information-target-r1",
        "task-t",
        (1, 2, 0),
        (2, 2, 1),
        {"h0": ["positive-output"]},
    )
    repeat_path, _ = _report(
        tmp_path / "information-repeat",
        "information-repeat-r1",
        "task-t",
        (1, 2, 0),
        (2, 2, 1),
        {"h0": ["positive-output"]},
    )
    protection_path, _ = _report(
        tmp_path / "information-protection",
        "information-protection-r1",
        "task-p",
        (2, 2, 1),
        (2, 2, 1),
        {},
    )
    review_spec = {
        "enabled": True,
        "feedback_mode": "answer_rich_evolver",
        "review_id": "information-review-r1",
        **_information_review_sources(),
    }
    plan = {
        "schema_version": 1,
        "controller_run_id": "information-controller-r1",
        "mode": mode,
        "runtime": {
            "python": "/python",
            "source_root": "/source",
            "results_dir": str(tmp_path / "review-results"),
        },
        "limits": {"provider_cost_usd": 1},
        "lineages": [
            {
                "lineage_id": "information-lineage",
                "parent": {"version": "h0", "worker_dir": str(parent)},
                "proposal": {
                    "replay_report": str(proposal_path),
                    "replay_run_id": "information-proposal-r1",
                    "candidate_version": "information-candidate-r1",
                },
                "candidate_information_set_review": review_spec,
                "stages": [
                    {
                        "name": "target",
                        "task_id": "task-t",
                        "replay_report": str(target_path),
                        "parent_arm": "h0",
                        "candidate_arm": "candidate",
                    },
                    {
                        "name": "repeat",
                        "task_id": "task-t",
                        "replay_report": str(repeat_path),
                        "parent_arm": "h0",
                        "candidate_arm": "candidate",
                    },
                    {
                        "name": "protection",
                        "task_id": "task-p",
                        "replay_report": str(protection_path),
                        "parent_arm": "h0",
                        "candidate_arm": "candidate",
                    },
                ],
            }
        ],
    }
    path = tmp_path / "information-plan.json"
    path.write_text(json.dumps(plan))
    return path, plan


def test_live_information_review_and_resume_account_once(tmp_path):
    plan_path, plan = _information_review_controller_plan(tmp_path)
    calls = []

    def run_reviewer(argv):
        calls.append(tuple(argv))
        assert argv[1] == (
            "/source/scripts/run_candidate_information_set_reviewer_canary.py"
        )
        package = json.loads(Path(argv[argv.index("--input") + 1]).read_text())
        assert "search_arm" not in package
        _write_information_review_result(
            Path(argv[argv.index("--out") + 1]), package
        )

    first = run_controller(
        plan_path,
        tmp_path / "information-state",
        approve_external_run=True,
        runner=run_reviewer,
    )
    resumed = run_controller(
        plan_path,
        tmp_path / "information-state",
        runner=lambda _argv: (_ for _ in ()).throw(
            AssertionError("resume must not dispatch Reviewer or Worker")
        ),
    )

    state = first["lineages"]["information-lineage"]
    assert len(calls) == 1
    assert state["phase"] == "FROZEN"
    assert state["decision"] == "PROMOTE"
    assert state["accounted_review_ids"] == ["information-review-r1"]
    assert state["cost"] == {
        "provider_cost_usd": "0.06",
        "completed_requests": 10,
        "total_tokens": 550,
    }
    assert resumed == first
    assert plan["lineages"][0]["parent"]["version"] == "h0"


def test_preconstructed_candidate_review_and_worker_share_exact_snapshot(
    tmp_path,
):
    target_path, _ = _report(
        tmp_path / "snapshot-target",
        "snapshot-target-r1",
        "task-t",
        (1, 2, 0),
        (2, 2, 1),
        {},
    )
    repeat_path, _ = _report(
        tmp_path / "snapshot-repeat",
        "snapshot-repeat-r1",
        "task-t",
        (1, 2, 0),
        (2, 2, 1),
        {},
    )
    protection_path, _ = _report(
        tmp_path / "snapshot-protection",
        "snapshot-protection-r1",
        "task-p",
        (2, 2, 1),
        (2, 2, 1),
        {},
    )
    plan = {
        "schema_version": 1,
        "controller_run_id": "snapshot-controller",
        "mode": "replay",
        "runtime": {},
        "limits": {"provider_cost_usd": 1},
        "lineages": [{
            "lineage_id": "preconstructed-snapshot",
            "parent": {"version": "h0", "worker_dir": "/fixture/h0"},
            "candidate": {
                "version": "candidate",
                "worker_dir": "/fixture/candidate",
            },
            "stages": [
                {
                    "name": "target",
                    "task_id": "task-t",
                    "replay_report": str(target_path),
                    "parent_arm": "h0",
                    "candidate_arm": "candidate",
                },
                {
                    "name": "repeat",
                    "task_id": "task-t",
                    "replay_report": str(repeat_path),
                    "parent_arm": "h0",
                    "candidate_arm": "candidate",
                },
                {
                    "name": "protection",
                    "task_id": "task-p",
                    "replay_report": str(protection_path),
                    "parent_arm": "h0",
                    "candidate_arm": "candidate",
                },
            ],
        }],
    }
    _add_replay_candidate_reviews(plan, tmp_path)
    source_candidate = Path(plan["lineages"][0]["candidate"]["worker_dir"])
    source_candidate.joinpath("systemprompt.md").chmod(0o755)
    source_text = source_candidate.joinpath("systemprompt.md").read_text()
    plan_path = tmp_path / "snapshot-plan.json"
    plan_path.write_text(json.dumps(plan))
    state_dir = tmp_path / "snapshot-state"

    paused = run_controller(
        plan_path,
        state_dir,
        stop_after_stage="information_set_review",
        runner=lambda _argv: (_ for _ in ()).throw(
            AssertionError("retained Review and reports must not dispatch")
        ),
    )["lineages"]["preconstructed-snapshot"]
    reviewed_dir = Path(paused["candidate"]["worker_dir"])

    assert paused["phase"] == "TARGET"
    assert reviewed_dir != source_candidate.resolve()
    assert reviewed_dir == (
        state_dir
        / "reviewed-candidates/preconstructed-snapshot/"
        "preconstructed-snapshot-universal-review-0"
    ).resolve()
    assert paused["candidate"]["information_set_review"] == {
        "review_id": "preconstructed-snapshot-universal-review-0",
        "overall_verdict": "PASS",
        "reviewed_candidate_dir": str(reviewed_dir),
    }
    assert paused["observations"]["information_set_review"][
        "coverage_review"
    ]["verdict"] == "PASS"
    assert paused["observations"]["information_set_review"][
        "reviewed_candidate_dir"
    ] == str(reviewed_dir)
    assert reviewed_dir.joinpath("systemprompt.md").read_text() == source_text
    assert reviewed_dir.joinpath("systemprompt.md").stat().st_mode & 0o777 == 0o555

    source_candidate.joinpath("systemprompt.md").write_text(
        "Post-review source mutation must not reach the Worker.\n"
    )
    assert reviewed_dir.joinpath("systemprompt.md").read_text() == source_text

    dispatch_plan = {
        "controller_run_id": "snapshot-controller",
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
    argv = build_child_argv(
        dispatch_plan,
        {
            "lineage_id": "preconstructed-snapshot",
            "parent": paused["current_parent"],
            "candidate": paused["candidate"],
            "observations": paused["observations"],
        },
        {"name": "target", "task_id": "task-t"},
        approve_external_run=True,
    )
    assert f"candidate={reviewed_dir}" in argv

    resumed = run_controller(
        plan_path,
        state_dir,
        runner=lambda _argv: (_ for _ in ()).throw(
            AssertionError("resume must reuse Review and replay reports")
        ),
    )["lineages"]["preconstructed-snapshot"]
    assert resumed["phase"] == "FROZEN"
    assert resumed["current_parent"]["worker_dir"] == str(reviewed_dir)
    assert resumed["accounted_review_ids"] == [
        "preconstructed-snapshot-universal-review-0"
    ]


@pytest.mark.parametrize("verdict", ["REJECT", "INCONCLUSIVE"])
def test_replay_information_review_nonpass_never_dispatches_worker(
    tmp_path, verdict
):
    plan_path, plan = _information_review_controller_plan(tmp_path, mode="replay")
    review_id = plan["lineages"][0]["candidate_information_set_review"][
        "review_id"
    ]
    state_dir = tmp_path / "information-replay-state"
    # Build the exact controller package before placing the retained result.
    parent = plan["lineages"][0]["parent"]
    proposal = json.loads(
        Path(plan["lineages"][0]["proposal"]["replay_report"]).read_text()
    )
    package = _candidate_information_set_review_package(
        {
            "current_parent": parent,
            "candidate": {
                "version": "information-candidate-r1",
                "worker_dir": proposal["candidate_dir"],
            },
            "proposal": {
                "worker_visible_claims": proposal["summary"][
                    "discovery_hypothesis"
                ]["hypothesis"]["worker_visible_claims"]
            },
        },
        plan["lineages"][0]["candidate_information_set_review"],
    )[0]
    _write_information_review_result(
        Path(plan["runtime"]["results_dir"]) / review_id,
        package,
        verdict,
    )

    result = run_controller(
        plan_path,
        state_dir,
        runner=lambda _argv: (_ for _ in ()).throw(
            AssertionError("non-PASS review must not dispatch a Worker")
        ),
    )["lineages"]["information-lineage"]

    assert result["phase"] == "HOLD_FOR_REFINE"
    assert result["decision"] == "HOLD_FOR_REFINE"
    assert result["current_parent"]["version"] == "h0"
    assert result["accounted_run_ids"] == ["information-proposal-r1"]
    assert result["accounted_review_ids"] == [review_id]


def test_candidate_review_trusted_sources_must_be_disjoint(tmp_path):
    parent, candidate = _information_review_workers(tmp_path)
    sources = _information_review_sources()
    sources["optimize_only_sources"][0]["ref"] = "public:instruction"
    spec = {
        "review_id": "disjoint-review",
        **sources,
    }
    state = {
        "current_parent": {"worker_dir": str(parent)},
        "candidate": {"version": "candidate", "worker_dir": str(candidate)},
        "proposal": {
            "worker_visible_claims": [
                {
                    "claim_id": "positive",
                    "claim": "Written output must be positive.",
                    "surfaces": ["tools"],
                    "basis_refs": ["public:instruction"],
                }
            ]
        },
    }

    with pytest.raises(LineageError, match="must be disjoint"):
        _candidate_information_set_review_package(state, spec)


def test_candidate_review_can_use_cumulative_material_baseline(tmp_path):
    h0 = tmp_path / "workers/cumulative-h0"
    c1 = tmp_path / "workers/cumulative-c1"
    c2 = tmp_path / "workers/cumulative-c2"
    for root, prompt in (
        (h0, "Use public task instructions.\n"),
        (
            c1,
            "Use public task instructions.\n"
            "Apply the publicly supported c1 canonicalization rule.\n",
        ),
        (
            c2,
            "Use public task instructions.\n"
            "Apply the publicly supported c1 canonicalization rule.\n"
            "Apply the publicly supported c2 numeric-coercion rule.\n",
        ),
    ):
        root.mkdir(parents=True)
        root.joinpath("systemprompt.md").write_text(prompt)

    state = {
        # c1 remains the proposal mutation parent and later Worker comparator.
        "current_parent": {"version": "c1", "worker_dir": str(c1)},
        "candidate": {"version": "c2", "worker_dir": str(c2)},
        "proposal": {
            "worker_visible_claims": [
                {
                    "claim_id": "c1-canonicalization",
                    "claim": "Use the public canonicalization rule.",
                    "surfaces": ["systemprompt"],
                    "basis_refs": ["public:instruction"],
                },
                {
                    "claim_id": "c2-numeric-coercion",
                    "claim": "Use the public numeric-coercion rule.",
                    "surfaces": ["systemprompt"],
                    "basis_refs": ["public:instruction"],
                },
            ]
        },
    }
    sources = _information_review_sources()
    default_spec = {
        "review_id": "cumulative-review",
        **sources,
    }
    cumulative_spec = {
        **default_spec,
        "candidate_material_baseline_worker_dir": str(h0),
        "review_feedback_path": str(tmp_path / "trusted/review-feedback.json"),
    }

    cumulative, hold_reason = _candidate_information_set_review_package(
        state, cumulative_spec
    )
    default, default_hold_reason = _candidate_information_set_review_package(
        state, default_spec
    )
    explicit_legacy, explicit_legacy_hold_reason = (
        _candidate_information_set_review_package(
            state,
            {
                **default_spec,
                "candidate_material_baseline_worker_dir": str(c1),
            },
        )
    )

    assert hold_reason is None
    assert default_hold_reason is None
    assert explicit_legacy_hold_reason is None
    assert default == explicit_legacy
    assert state["current_parent"] == {"version": "c1", "worker_dir": str(c1)}
    c1_added = (
        "+Apply the publicly supported c1 canonicalization rule."
    )
    c2_added = "+Apply the publicly supported c2 numeric-coercion rule."
    assert c1_added in cumulative["candidate"]["diff"]
    assert c2_added in cumulative["candidate"]["diff"]
    assert c1_added not in default["candidate"]["diff"]
    assert c2_added in default["candidate"]["diff"]
    rendered = json.dumps(cumulative)
    assert str(h0) not in rendered
    assert "review-feedback.json" not in rendered


@pytest.mark.parametrize("baseline", ["", "   ", 7])
def test_candidate_review_rejects_invalid_cumulative_baseline(
    tmp_path, baseline
):
    parent, candidate = _information_review_workers(tmp_path)
    state = {
        "current_parent": {"worker_dir": str(parent)},
        "candidate": {"version": "candidate", "worker_dir": str(candidate)},
        "proposal": {
            "worker_visible_claims": [
                {
                    "claim_id": "positive",
                    "claim": "Written output must be positive.",
                    "surfaces": ["tools"],
                    "basis_refs": ["public:instruction"],
                }
            ]
        },
    }
    spec = {
        "review_id": "invalid-baseline-review",
        "candidate_material_baseline_worker_dir": baseline,
        **_information_review_sources(),
    }

    with pytest.raises(LineageError, match="must be a non-empty string"):
        _candidate_information_set_review_package(state, spec)


def test_candidate_review_rejects_missing_cumulative_baseline(tmp_path):
    parent, candidate = _information_review_workers(tmp_path)
    state = {
        "current_parent": {"worker_dir": str(parent)},
        "candidate": {"version": "candidate", "worker_dir": str(candidate)},
        "proposal": {
            "worker_visible_claims": [
                {
                    "claim_id": "positive",
                    "claim": "Written output must be positive.",
                    "surfaces": ["tools"],
                    "basis_refs": ["public:instruction"],
                }
            ]
        },
    }
    missing = tmp_path / "workers/missing-cumulative-baseline"
    spec = {
        "review_id": "missing-baseline-review",
        "candidate_material_baseline_worker_dir": str(missing),
        **_information_review_sources(),
    }

    with pytest.raises(LineageError, match="is not an existing directory"):
        _candidate_information_set_review_package(state, spec)


def test_information_review_missing_candidate_material_holds_without_call(
    tmp_path,
):
    plan_path, plan = _information_review_controller_plan(tmp_path, mode="replay")
    proposal_path = Path(
        plan["lineages"][0]["proposal"]["replay_report"]
    )
    proposal = json.loads(proposal_path.read_text())
    proposal["candidate_dir"] = str(tmp_path / "missing-admitted-candidate")
    proposal_path.write_text(json.dumps(proposal))

    result = run_controller(
        plan_path,
        tmp_path / "missing-material-state",
        runner=lambda _argv: (_ for _ in ()).throw(
            AssertionError("missing candidate material must not call Reviewer or Worker")
        ),
    )["lineages"]["information-lineage"]

    assert result["phase"] == "HOLD_FOR_REFINE"
    assert result["current_parent"]["version"] == "h0"
    assert result["accounted_review_ids"] == []
    assert result["hold"]["reason"] == (
        "information_set_review_missing_candidate_material"
    )


def test_legacy_proposal_path_cannot_bypass_information_review(tmp_path):
    plan_path, plan = _information_review_controller_plan(tmp_path, mode="replay")
    del plan["lineages"][0]["candidate_information_set_review"]
    plan_path.write_text(json.dumps(plan))

    result = run_controller(
        plan_path,
        tmp_path / "legacy-state",
        runner=lambda _argv: (_ for _ in ()).throw(
            AssertionError("missing Review plan must not dispatch a child")
        ),
    )["lineages"]["information-lineage"]

    assert result["phase"] == "HOLD_FOR_REFINE"
    assert result["decision"] == "HOLD_FOR_REFINE"
    assert result["accounted_review_ids"] == []
    assert result["hold"]["reason"] == (
        "information_set_review_missing_trusted_plan"
    )


def test_preconstructed_candidate_without_review_plan_cannot_reach_target(
    tmp_path,
):
    plan = {
        "schema_version": 1,
        "controller_run_id": "preconstructed-no-review",
        "mode": "replay",
        "runtime": {},
        "limits": {"provider_cost_usd": 1},
        "lineages": [{
            "lineage_id": "preconstructed-no-review",
            "parent": {"version": "h0", "worker_dir": "/workers/h0"},
            "candidate": {
                "version": "candidate-v1",
                "worker_dir": "/workers/candidate-v1",
            },
            "stages": [
                {"name": "target", "task_id": "task-t"},
                {"name": "repeat", "task_id": "task-t"},
                {"name": "protection", "task_id": "task-p"},
            ],
        }],
    }
    plan_path = tmp_path / "preconstructed-no-review.json"
    plan_path.write_text(json.dumps(plan))

    state = run_controller(
        plan_path,
        tmp_path / "preconstructed-no-review-state",
        runner=lambda _argv: (_ for _ in ()).throw(
            AssertionError("missing Review plan must not dispatch")
        ),
    )["lineages"]["preconstructed-no-review"]

    assert state["phase"] == "HOLD_FOR_REFINE"
    assert state["decision"] == "HOLD_FOR_REFINE"
    assert state["hold"]["reason"] == (
        "information_set_review_missing_trusted_plan"
    )
    assert state["accounted_run_ids"] == []
    assert state["accounted_review_ids"] == []


def test_worker_argv_never_contains_review_reason_or_diagnostic():
    plan = {
        "controller_run_id": "information-controller",
        "runtime": {
            "python": "/python",
            "source_root": "/source",
            "qfbench_root": "/qfbench",
            "qfbench_manifest": "/manifest",
            "rootless_config": "/rootless",
            "image_set_manifest": "/images",
            "results_dir": "/results",
        },
    }
    lineage = {
        "lineage_id": "information-lineage",
        "parent": {"worker_dir": "/h0"},
        "candidate": {"worker_dir": "/candidate"},
        "candidate_information_set_review": {
            "reason": "secret-review-reason",
            "review_feedback_path": "/trusted/review-feedback.json",
            "optimize_only_sources": [
                {"excerpt": "secret-diagnostic-answer"}
            ],
        },
    }
    argv = build_child_argv(
        plan,
        _review_bound_lineage(lineage),
        {"name": "target", "task_id": "task-t"},
        approve_external_run=True,
    )

    rendered = " ".join(argv)
    assert "secret-review-reason" not in rendered
    assert "secret-diagnostic-answer" not in rendered
    assert "review-feedback.json" not in rendered


def test_information_review_live_argv_requires_explicit_approval(tmp_path):
    plan = {
        "runtime": {"python": "/python", "source_root": "/source"}
    }
    spec = {"backend": "openrouter"}
    with pytest.raises(LineageError, match="was not approved"):
        build_candidate_information_set_review_argv(
            plan,
            spec,
            input_path=tmp_path / "input.json",
            result_dir=tmp_path / "result",
            approve_external_run=False,
        )


def test_information_review_live_argv_uses_existing_raw_token_file(tmp_path):
    argv = build_candidate_information_set_review_argv(
        {"runtime": {"python": "/python", "source_root": "/source"}},
        {
            "backend": "openrouter",
            "token_file": "/runtime/secrets/model-token",
        },
        input_path=tmp_path / "input.json",
        result_dir=tmp_path / "result",
        approve_external_run=True,
    )

    assert argv[argv.index("--token-file") + 1] == (
        "/runtime/secrets/model-token"
    )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("status", "failed", "is not complete"),
        ("worker_visible", True, "must remain Worker-hidden"),
        ("promotion_authority", True, "no promotion authority"),
    ],
)
def test_information_review_rejects_invalid_wrapper_authority(
    tmp_path, field, value, message
):
    plan_path, plan = _information_review_controller_plan(tmp_path, mode="replay")
    review_id = plan["lineages"][0]["candidate_information_set_review"][
        "review_id"
    ]
    parent = plan["lineages"][0]["parent"]
    proposal = json.loads(
        Path(plan["lineages"][0]["proposal"]["replay_report"]).read_text()
    )
    package = _candidate_information_set_review_package(
        {
            "current_parent": parent,
            "candidate": {
                "version": "information-candidate-r1",
                "worker_dir": proposal["candidate_dir"],
            },
            "proposal": {
                "worker_visible_claims": proposal["summary"][
                    "discovery_hypothesis"
                ]["hypothesis"]["worker_visible_claims"]
            },
        },
        plan["lineages"][0]["candidate_information_set_review"],
    )[0]
    result_dir = Path(plan["runtime"]["results_dir"]) / review_id
    _write_information_review_result(result_dir, package)
    result_path = result_dir / "RESULT.json"
    wrapper = json.loads(result_path.read_text())
    wrapper[field] = value
    result_path.write_text(json.dumps(wrapper))

    with pytest.raises(LineageError, match=message):
        run_controller(plan_path, tmp_path / f"invalid-{field}-state")


def test_answer_free_information_review_requires_no_optimize_sources():
    sources = _information_review_sources()
    answer_free = {
        "candidate_information_set_review": {
            "enabled": True,
            "feedback_mode": "answer_free",
            "review_id": "public-only-review",
            "public_sources": sources["public_sources"],
            "optimize_only_sources": [],
        }
    }

    spec = _information_set_review_spec(answer_free)

    assert spec["feedback_mode"] == "answer_free"
    assert spec["optimize_only_sources"] == []
    answer_free["candidate_information_set_review"][
        "optimize_only_sources"
    ] = sources["optimize_only_sources"]
    with pytest.raises(LineageError, match="cannot include optimize-only"):
        _information_set_review_spec(answer_free)


def test_qrs_review_package_materializes_only_exact_r3_workflow_sources(
    tmp_path,
):
    parent, candidate = _information_review_workers(tmp_path)
    evidence = tmp_path / "panel-evidence"
    framework_ref = "guidance/qrs-workflow-framework.json"
    framework = evidence / framework_ref
    framework.parent.mkdir(parents=True)
    framework.write_text(
        '{"answer_free":true,"policy":"six-state workflow"}\n',
        encoding="utf-8",
    )
    workflow = []
    refs = [
        (
            "benchmarks/qfbench/tasks/holdings/worker_trace.jsonl",
            "data_engineering",
        ),
        (
            "benchmarks/qfbench/tasks/localvol/worker_trace.jsonl",
            "derivatives",
        ),
    ]
    for task_index, (ref, family) in enumerate(refs, start=1):
        source = evidence / ref
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(
            "\n".join(
                json.dumps({"line": number, "event": f"event-{number}"})
                for number in range(1, 6)
            )
            + "\n",
            encoding="utf-8",
        )
        workflow.append(
            {
                "task_key": f"qfbench:task-{task_index}",
                "task_family": family,
                "trajectory_ref": ref,
                "observed_handoff": "The state handoff is absent at lines 2-3.",
            }
        )
    claim = {
        "claim_id": "state-span-anchor",
        "claim_scope": "task_agnostic_harness_policy",
        "claim": "Keep each six-state span explicit and observable.",
        "surfaces": ["tools"],
        "basis_refs": [
            {"kind": "framework_reference", "ref": framework_ref},
            *[
                {
                    "kind": "answer_free_development_observation",
                    "ref": ref,
                }
                for ref, _family in refs
            ],
        ],
    }
    package, hold = _candidate_information_set_review_package(
        {
            "current_parent": {"version": "h0", "worker_dir": str(parent)},
            "candidate": {"version": "candidate", "worker_dir": str(candidate)},
            "proposal": {
                "worker_visible_claims": [claim],
                "workflow_evidence": workflow,
            },
        },
        {
            "review_id": "r3-shaped-review",
            "candidate_material_baseline_worker_dir": str(parent),
            "public_sources": [],
            "public_source_catalog": [],
            "answer_free_development_evidence_root": str(evidence),
            "optimize_only_sources": [],
        },
    )

    assert hold is None
    assert package is not None
    assert package["public_sources"] == []
    trusted = package["trusted_answer_free_sources"]
    assert [source["source_type"] for source in trusted] == [
        "framework_reference",
        "answer_free_development_observation",
        "answer_free_development_observation",
    ]
    assert {source.get("task_family") for source in trusted[1:]} == {
        "data_engineering",
        "derivatives",
    }
    assert all(len(source["excerpt"]) < 2_000 for source in trusted)


def _large_jsonl_trajectory(path: Path, *, payload_bytes: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            json.dumps({"line": number, "event": "x" * payload_bytes})
            for number in range(1, 13)
        )
        + "\n",
        encoding="utf-8",
    )


def test_workflow_trajectory_excerpt_accepts_compact_24kb_range(
    tmp_path: Path,
) -> None:
    trajectory = tmp_path / "worker_trace.jsonl"
    _large_jsonl_trajectory(trajectory, payload_bytes=1_900)

    excerpt = _trajectory_line_excerpt(
        trajectory,
        "The answer-free workflow observation is grounded at lines 1-12.",
    )

    excerpt_bytes = len(excerpt.encode("utf-8"))
    assert 22_000 < excerpt_bytes <= 24_000
    assert excerpt.startswith("line 1: ")
    assert excerpt.count("\n") == 11
    assert excerpt.splitlines()[-1].startswith("line 12: ")


def test_workflow_trajectory_excerpt_rejects_over_24kb(
    tmp_path: Path,
) -> None:
    trajectory = tmp_path / "worker_trace.jsonl"
    _large_jsonl_trajectory(trajectory, payload_bytes=2_100)

    with pytest.raises(LineageError, match="exceeds the Review bound"):
        _trajectory_line_excerpt(
            trajectory,
            "The answer-free workflow observation is grounded at lines 1-12.",
        )


def test_guarded_decision_and_controller_use_same_24kb_excerpt_boundary(
    tmp_path: Path,
) -> None:
    from qea.evolve_agent_full.tools.guarded_workspace import (
        GuardedWorkspaceError,
        _workflow_trajectory_line_excerpt,
    )

    trajectory = tmp_path / "worker_trace.jsonl"
    observation = "The handoff is grounded at lines 1-12."
    _large_jsonl_trajectory(trajectory, payload_bytes=1_900)
    assert _workflow_trajectory_line_excerpt(
        trajectory, observation
    ) == _trajectory_line_excerpt(trajectory, observation)

    _large_jsonl_trajectory(trajectory, payload_bytes=2_100)
    with pytest.raises(GuardedWorkspaceError, match="24000-byte Review bound"):
        _workflow_trajectory_line_excerpt(trajectory, observation)
    with pytest.raises(LineageError, match="exceeds the Review bound"):
        _trajectory_line_excerpt(trajectory, observation)


def test_qrs_review_package_still_rejects_overall_192kb_input(
    tmp_path: Path,
) -> None:
    parent, candidate = _information_review_workers(tmp_path)
    sources = [
        {
            "ref": f"public:large-source-{index}",
            "source_type": "public_contract",
            "excerpt": "x" * 40_000,
        }
        for index in range(5)
    ]
    claim = {
        "claim_id": "public-output-policy",
        "claim_scope": "task_specific_requirement",
        "claim": "Follow the exact supplied public output contract.",
        "surfaces": ["tools"],
        "basis_refs": [
            {
                "kind": "public_contract",
                "ref": sources[0]["ref"],
                "support": "The exact public contract directly supports the claim.",
            }
        ],
    }

    with pytest.raises(
        LineageError,
        match="candidate Review package exceeds the bounded model-input size",
    ):
        _candidate_information_set_review_package(
            {
                "current_parent": {"version": "h0", "worker_dir": str(parent)},
                "candidate": {
                    "version": "large-package-candidate",
                    "worker_dir": str(candidate),
                },
                "proposal": {"worker_visible_claims": [claim]},
            },
            {
                "review_id": "large-package-review",
                "candidate_material_baseline_worker_dir": str(parent),
                "public_sources": sources,
                "optimize_only_sources": [],
            },
        )


def test_live_oversized_review_source_holds_and_accounts_without_dispatch(
    tmp_path: Path,
) -> None:
    plan_path, plan = _information_review_controller_plan(tmp_path, mode="live")
    evidence = tmp_path / "answer-free-panel-evidence"
    framework_ref = "guidance/qrs-workflow-framework.json"
    framework = evidence / framework_ref
    framework.parent.mkdir(parents=True)
    framework.write_text(
        '{"answer_free":true,"policy":"six-state workflow"}\n',
        encoding="utf-8",
    )
    trajectory_ref = (
        "benchmarks/qfbench/tasks/oversized/worker_trace.jsonl"
    )
    trajectory = evidence / trajectory_ref
    trajectory.parent.mkdir(parents=True)
    trajectory.write_text(
        json.dumps({"line": 1, "event": "x" * 35_900}) + "\n",
        encoding="utf-8",
    )
    proposal_path = Path(
        plan["lineages"][0]["proposal"]["replay_report"]
    )
    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    hypothesis = proposal["summary"]["discovery_hypothesis"]["hypothesis"]
    hypothesis["workflow_evidence"] = [
        {
            "task_key": "qfbench:oversized",
            "task_family": "rates_fx_macro",
            "trajectory_ref": trajectory_ref,
            "observed_handoff": "The handoff is visible at line 1.",
        }
    ]
    hypothesis["worker_visible_claims"] = [
        {
            "claim_id": "workflow-handoff-policy",
            "claim_scope": "task_agnostic_harness_policy",
            "claim": "Keep the six-state workflow handoff explicit.",
            "surfaces": ["tools"],
            "basis_refs": [
                {"kind": "framework_reference", "ref": framework_ref},
                {
                    "kind": "answer_free_development_observation",
                    "ref": trajectory_ref,
                },
            ],
        }
    ]
    proposal_path.write_text(json.dumps(proposal), encoding="utf-8")
    review_spec = plan["lineages"][0]["candidate_information_set_review"]
    review_spec.update(
        {
            "feedback_mode": "answer_free",
            "public_sources": [],
            "public_source_catalog": [],
            "answer_free_development_evidence_root": str(evidence),
            "optimize_only_sources": [],
        }
    )
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    state_dir = tmp_path / "oversized-review-state"

    def no_reviewer_or_worker(_argv):
        raise AssertionError(
            "invalid Review package must not dispatch Reviewer or Worker"
        )

    first = run_controller(
        plan_path,
        state_dir,
        approve_external_run=True,
        runner=no_reviewer_or_worker,
    )
    resumed = run_controller(
        plan_path,
        state_dir,
        approve_external_run=True,
        runner=no_reviewer_or_worker,
    )

    state = first["lineages"]["information-lineage"]
    assert resumed == first
    assert state["phase"] == "HOLD_FOR_REFINE"
    assert state["decision"] == "HOLD_FOR_REFINE"
    assert state["status"] == "candidate_hold"
    assert state["current_parent"]["version"] == "h0"
    assert state["accounted_run_ids"] == ["information-proposal-r1"]
    assert state["accounted_review_ids"] == []
    assert state["cost"] == {
        "provider_cost_usd": "0.02",
        "completed_requests": 3,
        "total_tokens": 200,
    }
    assert state["hold"]["reason"].startswith(
        "information_set_review_package_engineering_invalid: "
        "workflow trajectory excerpt exceeds the Review bound"
    )
    assert state["hold"]["kind"] == (
        "candidate_information_set_review_package_engineering_invalid"
    )
    retained_result = json.loads(
        (state_dir / "CONTROLLER-RESULT.json").read_text(encoding="utf-8")
    )
    assert retained_result == first


def test_later_qrs_review_fails_closed_when_prior_accepted_claim_is_omitted(
    tmp_path,
):
    parent, candidate = _information_review_workers(tmp_path)
    evidence = tmp_path / "later-panel-evidence"
    accepted = evidence / "accepted-panels/panel-01-data"
    accepted.mkdir(parents=True)
    (evidence / "accepted-panels/INDEX.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "answer_free": True,
                "entries": [
                    {
                        "panel_index": 1,
                        "record": (
                            "accepted-panels/panel-01-data/ACCEPTED-PANEL.json"
                        ),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (accepted / "ACCEPTED-PANEL.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "answer_free": True,
                "accepted_claims": [
                    {
                        "claim_id": "prior-policy",
                        "claim_scope": "task_specific_requirement",
                        "claim": "Preserve the public output requirement.",
                        "surfaces": ["systemprompt"],
                        "basis_refs": [
                            {
                                "kind": "public_contract",
                                "ref": "public:instruction",
                            }
                        ],
                        "safe_sources": [
                            {
                                "ref": "public:instruction",
                                "source_type": "public_contract",
                                "excerpt": "Preserve the public output requirement.",
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    current_claim = {
        "claim_id": "new-policy",
        "claim": "Apply a new public rule.",
        "surfaces": ["systemprompt"],
        "basis_refs": ["public:instruction"],
    }

    with pytest.raises(LineageError, match="changed or omitted accepted claim"):
        _candidate_information_set_review_package(
            {
                "current_parent": {"worker_dir": str(parent)},
                "candidate": {"version": "candidate", "worker_dir": str(candidate)},
                "proposal": {"worker_visible_claims": [current_claim]},
            },
            {
                "review_id": "later-review",
                "public_sources": [
                    {
                        "ref": "public:instruction",
                        "source_type": "public_contract",
                        "excerpt": "Apply a new public rule.",
                    }
                ],
                "answer_free_development_evidence_root": str(evidence),
                "optimize_only_sources": [],
            },
        )
