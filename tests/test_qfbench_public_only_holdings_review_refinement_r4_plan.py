from __future__ import annotations

import inspect
import json
import shutil
from copy import deepcopy
from pathlib import Path

from scripts import build_qfbench_candidate_review_refinement_evidence as builder
from scripts.run_qfbench_lineage_controller import (
    _candidate_information_set_review_package,
    _information_set_review_spec,
    build_candidate_information_set_review_argv,
    build_proposal_argv,
)


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = (
    ROOT
    / "data/breadth/QF_PUBLIC_ONLY_HOLDINGS_REVIEW_REFINEMENT_R4_PLAN.json"
)
R3_EVIDENCE = (
    ROOT
    / "results/bc-mirror/"
    "qf-public-only-holdings-review-refinement-evidence-20260824-r3"
)
C2_CANDIDATE = (
    ROOT
    / "results/bc-mirror/qf-public-only-holdings-refine-proposal-20260824-r3/"
    "evolutions/iteration-0001/candidate"
)
TARGET_INSTRUCTION = (
    R3_EVIDENCE
    / "benchmarks/qfbench/tasks/13f-amendment-aware-crowding/instruction.md"
)


def _plan() -> dict[str, object]:
    return json.loads(PLAN_PATH.read_text(encoding="utf-8"))


def _lineage(plan: dict[str, object]) -> dict[str, object]:
    assert len(plan["lineages"]) == 1
    return plan["lineages"][0]


def _option(argv: tuple[str, ...], option: str) -> str:
    return argv[argv.index(option) + 1]


def test_r4_freezes_c2_proposal_then_cumulative_review_with_zero_worker() -> None:
    plan = _plan()
    lineage = _lineage(plan)
    invocations = plan["controller_invocations"]

    assert plan["status"] == (
        "frozen_refinement_proposal_and_review_staged_not_run"
    )
    assert plan["controller_run_id"] == (
        "qf-public-only-holdings-review-refinement-20260824-r4"
    )
    assert plan["deploy_source_freeze"]["deploy_id"] == plan[
        "controller_run_id"
    ]
    assert lineage["lineage_id"] == (
        "qf-public-only-holdings-review-refinement-r4"
    )
    assert lineage["parent"]["version"] == "qf-public-only-holdings-c2-r3"
    assert lineage["proposal"]["candidate_version"] == (
        "qf-public-only-holdings-c3-r4"
    )
    assert [stage["stage"] for stage in plan["staged_execution"]] == [
        "proposal",
        "information_set_review",
        "target",
        "repeat",
        "protection",
    ]
    assert [
        stage["authorized_in_this_freeze"]
        for stage in plan["staged_execution"]
    ] == [True, True, False, False, False]

    proposal = tuple(invocations["proposal_stop"])
    review = tuple(invocations["review_stop_resume"])
    assert _option(proposal, "--state-dir") == _option(review, "--state-dir")
    assert _option(proposal, "--stop-after-stage") == "proposal"
    assert _option(review, "--stop-after-stage") == "information_set_review"
    assert invocations["target_invocation"] is None
    assert invocations["repeat_invocation"] is None
    assert invocations["protection_invocation"] is None
    assert all(
        stage["conditional_not_authorized"] is True
        for stage in lineage["stages"]
    )

    for limits in (
        plan["limits"]["proposal_stage"],
        plan["limits"]["reviewer_incremental"],
        plan["limits"]["proposal_plus_review_cumulative"],
    ):
        assert limits["max_worker_sessions"] == 0
        assert limits["max_verifier_executions"] == 0
        assert limits["max_selected_probe_dispatches"] == 0


def test_r4_caps_are_the_separately_frozen_proposal_and_review_limits() -> None:
    limits = _plan()["limits"]

    assert limits["provider_cost_usd"] == 0.17
    assert limits["lineage_candidate_versions"] == 1
    assert limits["proposal_stage"] == {
        "max_evolver_proposals": 1,
        "max_completed_requests": 35,
        "max_total_tokens": 3_500_000,
        "provider_cost_usd": 0.12,
        "hard_wall_time_seconds": 10_800,
        "max_reviewer_requests": 0,
        "max_worker_sessions": 0,
        "max_verifier_executions": 0,
        "max_selected_probe_dispatches": 0,
    }
    assert limits["reviewer_incremental"] == {
        "max_evolver_proposals": 0,
        "max_reviewer_requests": 1,
        "max_completed_requests": 1,
        "max_total_tokens": 40_000,
        "provider_cost_usd": 0.05,
        "hard_wall_time_seconds": 900,
        "max_worker_sessions": 0,
        "max_verifier_executions": 0,
        "max_selected_probe_dispatches": 0,
    }
    assert limits["proposal_plus_review_cumulative"] == {
        "max_evolver_proposals": 1,
        "max_reviewer_requests": 1,
        "max_completed_requests": 36,
        "max_total_tokens": 3_540_000,
        "provider_cost_usd": 0.17,
        "hard_wall_time_seconds": 11_700,
        "max_worker_sessions": 0,
        "max_verifier_executions": 0,
        "max_selected_probe_dispatches": 0,
    }


def test_r4_evidence_build_uses_exact_r3_chain_and_dual_diff_baselines() -> None:
    plan = _plan()
    evidence = plan["evidence_build"]
    argv = tuple(evidence["argv"])

    assert evidence["worker_model_requests"] == 0
    assert evidence["round_label"] == "holdings-c2-review-r3"
    assert evidence["destination"].endswith(
        "qf-public-only-holdings-review-refinement-evidence-20260824-r4"
    )
    assert _option(argv, "--base-view") == evidence["base_view"]
    assert _option(argv, "--proposal-report") == evidence["proposal_report"]
    assert _option(argv, "--proposal-parent-dir") == evidence[
        "proposal_parent_dir"
    ]
    assert _option(argv, "--candidate-dir") == evidence["candidate_dir"]
    assert _option(argv, "--review-baseline-dir") == evidence[
        "review_baseline_dir"
    ]
    assert _option(argv, "--review-input") == evidence["review_input"]
    assert _option(argv, "--review-result") == evidence["review_result"]
    assert _option(argv, "--destination") == evidence["destination"]
    assert _option(argv, "--round-label") == evidence["round_label"]
    assert evidence["proposal_parent_dir"].endswith(
        "qf-public-only-holdings-proposal-20260824-r1/"
        "evolutions/iteration-0001/candidate"
    )
    assert evidence["candidate_dir"].endswith(
        "qf-public-only-holdings-refine-proposal-20260824-r3/"
        "evolutions/iteration-0001/candidate"
    )
    assert "different baselines" in evidence["required_validation"]

    parameters = inspect.signature(builder.build).parameters
    assert "proposal_parent_dir" in parameters
    assert "review_baseline_dir" in parameters


def test_r4_proposal_argv_uses_exact_c2_and_new_refinement_evidence() -> None:
    plan = _plan()
    lineage = _lineage(plan)
    proposal = lineage["proposal"]
    argv = build_proposal_argv(
        plan, lineage, proposal, approve_external_run=True
    )

    assert _option(argv, "--run-id") == (
        "qf-public-only-holdings-refine-proposal-20260824-r4"
    )
    assert _option(argv, "--backbone") == lineage["parent"]["worker_dir"]
    assert _option(argv, "--backbone").endswith(
        "qf-public-only-holdings-refine-proposal-20260824-r3/"
        "evolutions/iteration-0001/candidate"
    )
    assert _option(argv, "--evidence").endswith(
        "qf-public-only-holdings-review-refinement-evidence-20260824-r4"
    )
    assert _option(argv, "--arm") == "quant-state"
    assert proposal["stage"] == "LINEAGE_REFINEMENT"
    assert "--dispatch-selected-probe" not in argv


def test_r4_review_is_arm_blind_exact_public_only_and_cumulative_from_h0() -> None:
    plan = _plan()
    lineage = _lineage(plan)
    spec = _information_set_review_spec(lineage)

    assert spec is not None
    assert spec["feedback_mode"] == "answer_free"
    assert spec["review_id"] == (
        "qf-public-only-holdings-information-set-review-20260824-r4"
    )
    assert spec["model"] == "deepseek/deepseek-v4-pro"
    assert spec["token_file"] == "/home/julius/qea/runtime/secrets/model-token"
    assert spec["arm_blind"] is True
    assert spec["optimize_only_sources"] == []
    assert spec["candidate_material_baseline_worker_dir"] == (
        "/data/qea-julius-storage/deploy/"
        "qf-public-only-holdings-review-refinement-20260824-r4/"
        "qea/worker_quant_h0"
    )
    assert [source["ref"] for source in spec["public_sources"]] == [
        "public:13f-full-instruction"
    ]
    assert spec["public_sources"][0]["excerpt"] == TARGET_INSTRUCTION.read_text(
        encoding="utf-8"
    )
    argv = build_candidate_information_set_review_argv(
        plan,
        spec,
        input_path=Path("/trusted/r4-review-input.json"),
        result_dir=Path("/trusted/r4-review-result"),
        approve_external_run=True,
    )
    assert _option(argv, "--model") == "deepseek/deepseek-v4-pro"
    assert _option(argv, "--token-file") == (
        "/home/julius/qea/runtime/secrets/model-token"
    )
    assert "--arm" not in argv
    assert lineage["candidate_policy"]["worker_exposure_policy"] == {
        "kind": "prompt_exposure_by_construction",
        "surface": "systemprompt",
        "callable_activation_required": False,
        "behavioral_uptake_assumed": False,
        "causal_effect_assumed": False,
    }


def test_cumulative_review_package_uses_h0_to_summary_only_c3_and_no_feedback(
    tmp_path: Path,
) -> None:
    plan = deepcopy(_plan())
    lineage = _lineage(plan)
    spec = _information_set_review_spec(lineage)
    c3 = tmp_path / "candidate-c3"
    shutil.copytree(ROOT / "qea/worker_quant_h0", c3)
    c3.joinpath("systemprompt.md").write_text(
        c3.joinpath("systemprompt.md").read_text(encoding="utf-8")
        + (
            "\nWhen the public task explicitly requires source-summary "
            "reconciliation, compute and record the differences used by its "
            "declared checks.\n"
        ),
        encoding="utf-8",
    )
    claims = [
        {
            "claim_id": "summary_page_reconciliation",
            "claim": (
                "When the public task explicitly requires source-summary "
                "reconciliation, compute and record the differences used by "
                "its declared checks."
            ),
            "surfaces": ["systemprompt"],
            "basis_refs": [
                {
                    "kind": "public_contract",
                    "ref": (
                        "benchmarks/qfbench/tasks/"
                        "13f-amendment-aware-crowding/instruction.md"
                    ),
                    "support": (
                        "The instruction explicitly requires filing totals to "
                        "reconcile with summary-page data."
                    ),
                }
            ],
        }
    ]
    spec["candidate_material_baseline_worker_dir"] = str(
        ROOT / "qea/worker_quant_h0"
    )
    state = {
        "current_parent": {
            "version": "qf-public-only-holdings-c2-r3",
            "worker_dir": str(C2_CANDIDATE),
        },
        "candidate": {
            "version": "qf-public-only-holdings-c3-r4",
            "worker_dir": str(c3),
        },
        "proposal": {"worker_visible_claims": claims},
    }

    package, hold = _candidate_information_set_review_package(state, spec)

    assert hold is None
    assert package is not None
    assert package["candidate_id"] == "qf-public-only-holdings-c3-r4"
    assert package["worker_visible_claims"] == claims
    assert package["optimize_only_sources"] == []
    assert "+When the public task explicitly requires" in package["candidate"][
        "diff"
    ]
    assert "Canonical keys before any join" not in package["candidate"]["diff"]
    rendered = json.dumps(package, ensure_ascii=False).casefold()
    for forbidden in (
        "qf-public-only-holdings-information-set-review-20260824-r3",
        "holdings-c2-review-r3",
        "semantic-review",
        "review_feedback",
        "reviewer feedback",
        "optimization-diagnostic",
        "search_arm",
    ):
        assert forbidden not in rendered


def test_r4_terminal_policy_stops_abstain_nonpass_pass_and_summary_only() -> None:
    policy = _plan()["decision_policy"]

    assert "valid calibrated terminal" in policy["proposal_abstain"]
    assert "zero Reviewer, Worker, verifier" in policy["proposal_abstain"]
    assert "HOLD_FOR_REFINE" in policy["review_reject_or_inconclusive"]
    assert "stop the holdings lineage" in policy[
        "review_reject_or_inconclusive"
    ]
    assert "cleanliness eligibility only" in policy["review_pass"]
    assert "CLEAN_BUT_NO_OBSERVED_HEADROOM" in policy["summary_only_pass"]
    assert "public H0 trajectory already realizes it" in policy[
        "summary_only_pass"
    ]
    assert "dispatch no Worker" in policy["summary_only_pass"]
    assert "both Reviewer PASS" in policy["later_worker_authority"]
    assert "No such plan is included" in policy["later_worker_authority"]


def test_r4_plan_has_no_official_outcome_or_content_identity_gate() -> None:
    plan = _plan()
    rendered = json.dumps(plan, ensure_ascii=False).casefold()
    for forbidden in (
        "official score",
        "official_tests_passed",
        "failed property",
        "weights_sum_to_one_by_book",
        "summary_max_turnover_matches",
        "summary_max_overlap_matches",
        "47/51",
    ):
        assert forbidden not in rendered

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
        for key in keys(plan)
    )
