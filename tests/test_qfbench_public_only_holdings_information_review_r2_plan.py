from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from scripts.run_qfbench_lineage_controller import (
    _candidate_information_set_review_package,
    _information_set_review_spec,
    build_candidate_information_set_review_argv,
    run_controller,
)


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = (
    ROOT
    / "data/breadth/QF_PUBLIC_ONLY_HOLDINGS_INFORMATION_REVIEW_R2_PLAN.json"
)
R1_REPORT_PATH = (
    ROOT
    / "results/bc-mirror/qf-public-only-holdings-proposal-20260824-r1/proposal-report.json"
)
R1_CANDIDATE_PATH = (
    ROOT
    / "results/bc-mirror/qf-public-only-holdings-proposal-20260824-r1/"
    "evolutions/iteration-0001/candidate"
)
PUBLIC_EVIDENCE = (
    ROOT
    / "results/bc-mirror/"
    "qf-public-only-holdings-public-trajectory-evidence-20260824-r1"
)
TARGET_INSTRUCTION = (
    PUBLIC_EVIDENCE
    / "benchmarks/qfbench/tasks/13f-amendment-aware-crowding/instruction.md"
)
def _plan() -> dict[str, object]:
    return json.loads(PLAN_PATH.read_text(encoding="utf-8"))


def _lineage(plan: dict[str, object]) -> dict[str, object]:
    assert len(plan["lineages"]) == 1
    return plan["lineages"][0]


def _option(argv: tuple[str, ...], option: str) -> str:
    return argv[argv.index(option) + 1]


def _write_fake_review(result_dir: Path, package: dict[str, object]) -> None:
    result_dir.mkdir(parents=True)
    public_ref = package["public_sources"][0]["ref"]
    claim_reviews = [
        {
            "claim_id": claim["claim_id"],
            "verdict": "INCONCLUSIVE",
            "reason": "Focused fixture withholds a scientific PASS.",
            "source_basis": [
                {
                    "ref": public_ref,
                    "role": "INSUFFICIENT_PUBLIC_SUPPORT",
                }
            ],
        }
        for claim in package["worker_visible_claims"]
    ]
    wrapper = {
        "schema_version": 1,
        "status": "complete",
        "review_scope": "answer_free_candidate_information_set",
        "request": {
            "request_count": 1,
            "accounting": {
                "provider_cost_usd": "0.01",
                "prompt_tokens": 100,
                "completion_tokens": 50,
            },
            "response_usage": {"total_tokens": 150},
        },
        "review": {
            "schema_version": 1,
            "review_id": package["review_id"],
            "candidate_id": package["candidate_id"],
            "claim_reviews": claim_reviews,
            "coverage_review": {
                "verdict": "PASS",
                "reason": "The fixture records complete candidate material.",
                "source_basis": [
                    {
                        "ref": "candidate:diff",
                        "role": "CANDIDATE_EXPOSURE",
                    }
                ],
                "undeclared_exposures": [],
            },
            "overall_verdict": "INCONCLUSIVE",
        },
        "worker_visible": False,
        "promotion_authority": False,
    }
    result_dir.joinpath("RESULT.json").write_text(
        json.dumps(wrapper), encoding="utf-8"
    )


def test_r2_is_separate_live_reviewer_only_replay_with_new_state() -> None:
    plan = _plan()
    lineage = _lineage(plan)
    invocation = tuple(plan["controller_invocations"]["review_stop"])

    assert plan["status"] == "frozen_reviewer_only_replay_not_run"
    assert plan["mode"] == "live"
    assert plan["controller_run_id"] == (
        "qf-public-only-holdings-information-set-review-replay-20260824-r2"
    )
    assert plan["states_root"].endswith(
        "qf-public-only-holdings-information-set-review-replay-20260824-r2-controller-state"
    )
    assert "lineage-20260824-r1-controller-state" not in plan["states_root"]
    assert lineage["proposal"] == {
        "replay_report": (
            "/data/qea-julius-storage/runs/"
            "qf-public-only-holdings-proposal-20260824-r1/proposal-report.json"
        ),
        "replay_run_id": "qf-public-only-holdings-proposal-20260824-r1",
        "candidate_version": "qf-public-only-holdings-c1",
    }
    assert _option(invocation, "--stop-after-stage") == "information_set_review"
    assert plan["controller_invocations"]["proposal_invocation"] is None
    assert plan["controller_invocations"]["target_invocation"] is None
    assert plan["controller_invocations"]["repeat_invocation"] is None
    assert plan["controller_invocations"]["protection_invocation"] is None
    assert all(stage.get("conditional_not_authorized") is True for stage in lineage["stages"])


def test_prompt_exposure_is_reviewable_without_callable_activation() -> None:
    policy = _lineage(_plan())["candidate_policy"]
    exposure = policy["worker_exposure_policy"]

    assert policy["callable_component_activation_required_before_review"] is False
    assert exposure == {
        "kind": "prompt_exposure_by_construction",
        "surface": "systemprompt",
        "callable_activation_required": False,
        "behavioral_uptake_assumed": False,
        "causal_effect_assumed": False,
    }
    assert _plan()["methodological_recovery"]["worker_exposure_policy"] == exposure


def test_trusted_sources_are_complete_exact_answer_free_public_files() -> None:
    spec = _information_set_review_spec(_lineage(_plan()))

    assert spec is not None
    assert spec["feedback_mode"] == "answer_free"
    assert spec["arm_blind"] is True
    assert spec["optimize_only_sources"] == []
    assert [source["ref"] for source in spec["public_sources"]] == [
        "public:13f-full-instruction",
    ]
    assert spec["public_sources"][0]["excerpt"] == TARGET_INSTRUCTION.read_text(
        encoding="utf-8"
    )
    rendered = json.dumps(spec, ensure_ascii=False).casefold()
    for forbidden in (
        "official-score",
        "official_tests_passed",
        "optimization-diagnostic",
        "ctrf",
        "verifier output",
        "expected-versus-observed",
        "selection_reference",
    ):
        assert forbidden not in rendered


def test_frozen_limits_separate_inherited_proposal_from_incremental_review() -> None:
    limits = _plan()["limits"]
    inherited = limits["inherited_replay_accounting"]
    incremental = limits["incremental_r2_review"]
    cumulative = limits["proposal_plus_review_cumulative"]

    assert inherited == {
        "source_run_id": "qf-public-only-holdings-proposal-20260824-r1",
        "evolver_proposals": 1,
        "completed_requests": 22,
        "total_tokens": 2093270,
        "provider_cost_usd": 0.061361376,
        "interpretation": (
            "The controller imports and re-accounts the retained R1 proposal in "
            "the new R2 lineage's cumulative ledger. Those are inherited "
            "historical proposal resources, not newly dispatched R2 model work."
        ),
    }
    assert incremental == {
        "max_evolver_proposals": 0,
        "max_reviewer_requests": 1,
        "max_completed_requests": 1,
        "max_total_tokens": 40000,
        "provider_cost_usd": 0.05,
        "hard_wall_time_seconds": 900,
        "max_worker_sessions": 0,
        "max_verifier_executions": 0,
    }
    assert cumulative["max_completed_requests"] == 23
    assert cumulative["max_total_tokens"] == 2133270
    assert cumulative["provider_cost_usd"] == 0.111361376
    assert cumulative["max_worker_sessions"] == 0
    assert cumulative["max_verifier_executions"] == 0


def test_real_r1_replay_builds_exact_package_and_only_reviewer_argv(
    tmp_path: Path,
) -> None:
    plan = deepcopy(_plan())
    lineage = _lineage(plan)
    original_report = json.loads(R1_REPORT_PATH.read_text(encoding="utf-8"))
    replay_report = deepcopy(original_report)
    replay_report["candidate_dir"] = str(R1_CANDIDATE_PATH)
    local_report = tmp_path / "exact-r1-proposal-report.json"
    local_report.write_text(json.dumps(replay_report), encoding="utf-8")

    plan["runtime"]["python"] = "/python"
    plan["runtime"]["source_root"] = "/source"
    plan["runtime"]["results_dir"] = str(tmp_path / "review-results")
    lineage["parent"]["worker_dir"] = str(ROOT / "qea/worker_quant_h0")
    lineage["proposal"]["replay_report"] = str(local_report)
    local_plan = tmp_path / "plan.json"
    local_plan.write_text(json.dumps(plan), encoding="utf-8")
    calls: list[tuple[str, ...]] = []

    def reviewer_only(argv: tuple[str, ...]) -> None:
        calls.append(tuple(argv))
        assert argv[1] == "/source/scripts/run_candidate_information_set_reviewer_canary.py"
        package = json.loads(
            Path(_option(tuple(argv), "--input")).read_text(encoding="utf-8")
        )
        _write_fake_review(Path(_option(tuple(argv), "--out")), package)

    output = run_controller(
        local_plan,
        tmp_path / "fresh-r2-state",
        selected_lineages={lineage["lineage_id"]},
        stop_after_stage="information_set_review",
        approve_external_run=True,
        runner=reviewer_only,
    )
    state = output["lineages"][lineage["lineage_id"]]

    assert len(calls) == 1
    argv = calls[0]
    assert _option(argv, "--model") == "deepseek/deepseek-v4-pro"
    assert _option(argv, "--token-file") == "/home/julius/qea/runtime/secrets/model-token"
    assert "--arm" not in argv
    assert "run_qfbench_discovery_pilot.py" not in " ".join(argv)
    assert "run_qfbench_breadth_pilot.py" not in " ".join(argv)
    assert state["accounted_run_ids"] == ["qf-public-only-holdings-proposal-20260824-r1"]
    assert state["accounted_review_ids"] == [
        "qf-public-only-holdings-information-set-review-20260824-r2"
    ]
    assert state["cost"] == {
        "provider_cost_usd": "0.071361375999999995",
        "completed_requests": 23,
        "total_tokens": 2093420,
    }
    assert state["phase"] == "HOLD_FOR_REFINE"
    assert state["decision"] == "HOLD_FOR_REFINE"
    assert state["stopped_after_stage"] == "information_set_review"
    assert state["observations"].keys() == {"information_set_review"}
    assert state["candidate"]["activation_binding"]["status"] == "none"
    reviewed_snapshot = (
        tmp_path
        / "fresh-r2-state/reviewed-candidates"
        / lineage["lineage_id"]
        / "qf-public-only-holdings-information-set-review-20260824-r2"
    )
    assert state["candidate"]["worker_dir"] == str(reviewed_snapshot)
    assert state["candidate"]["worker_dir"] != str(R1_CANDIDATE_PATH)
    assert state["observations"]["information_set_review"][
        "reviewed_candidate_dir"
    ] == str(reviewed_snapshot)

    package = json.loads(
        (tmp_path / "fresh-r2-state/review-inputs/"
         "qf-public-only-holdings-information-set-review-20260824-r2.json").read_text(
            encoding="utf-8"
        )
    )
    expected_state = {
        "current_parent": state["current_parent"],
        "candidate": state["candidate"],
        "proposal": state["proposal"],
    }
    rebuilt, hold = _candidate_information_set_review_package(
        expected_state, _information_set_review_spec(lineage)
    )
    assert hold is None
    assert package == rebuilt
    assert package["candidate_id"] == "qf-public-only-holdings-c1"
    # The controller reconstructs the diff from the exact candidate tree and
    # deliberately uses parent/candidate labels instead of the report's a/b
    # labels.  The changed hunk itself must remain exact.
    assert package["candidate"]["diff"].splitlines()[2:] == original_report[
        "diff"
    ].splitlines()[2:]
    assert package["candidate"]["files"] == [
        {
            "ref": "candidate:file:systemprompt.md",
            "path": "systemprompt.md",
            "surface": "systemprompt",
            "change_type": "modified",
            "excerpt": R1_CANDIDATE_PATH.joinpath("systemprompt.md").read_text(
                encoding="utf-8"
            ),
        }
    ]
    assert package["worker_visible_claims"] == original_report["summary"][
        "discovery_hypothesis"
    ]["hypothesis"]["worker_visible_claims"]
    assert package["optimize_only_sources"] == []
    rendered = json.dumps(package, ensure_ascii=False).casefold()
    assert "selection_reference" not in rendered
    assert "official_tests_passed" not in rendered
    assert "optimization-diagnostic" not in rendered


def test_plan_adds_no_content_identity_fields() -> None:
    def keys(value: object) -> list[str]:
        if isinstance(value, dict):
            return [str(key) for key in value] + [
                nested for child in value.values() for nested in keys(child)
            ]
        if isinstance(value, list):
            return [nested for child in value for nested in keys(child)]
        return []

    assert not any(
        "sha" in key.casefold() or "digest" in key.casefold()
        for key in keys(_plan())
    )
