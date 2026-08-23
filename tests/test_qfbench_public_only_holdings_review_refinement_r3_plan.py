from __future__ import annotations

import json
import shutil
from copy import deepcopy
from pathlib import Path

from scripts.run_qfbench_lineage_controller import (
    _candidate_information_set_review_package,
    _information_set_review_spec,
    build_candidate_information_set_review_argv,
    build_proposal_argv,
    run_controller,
)


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = (
    ROOT
    / "data/breadth/QF_PUBLIC_ONLY_HOLDINGS_REVIEW_REFINEMENT_R3_PLAN.json"
)
R3_EVIDENCE = (
    ROOT
    / "results/bc-mirror/"
    "qf-public-only-holdings-review-refinement-evidence-20260824-r3"
)
R1_REPORT_PATH = (
    ROOT
    / "results/bc-mirror/qf-public-only-holdings-proposal-20260824-r1/"
    "proposal-report.json"
)
R1_CANDIDATE_PATH = (
    ROOT
    / "results/bc-mirror/qf-public-only-holdings-proposal-20260824-r1/"
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


def _write_fake_review(result_dir: Path, package: dict[str, object]) -> None:
    result_dir.mkdir(parents=True)
    public_ref = package["public_sources"][0]["ref"]
    result = {
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
            "claim_reviews": [
                {
                    "claim_id": claim["claim_id"],
                    "verdict": "INCONCLUSIVE",
                    "reason": "The focused fixture withholds scientific PASS.",
                    "source_basis": [
                        {
                            "ref": public_ref,
                            "role": "INSUFFICIENT_PUBLIC_SUPPORT",
                        }
                    ],
                }
                for claim in package["worker_visible_claims"]
            ],
            "coverage_review": {
                "verdict": "PASS",
                "reason": "The focused fixture records cumulative material.",
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
        json.dumps(result), encoding="utf-8"
    )


def test_r3_freezes_same_state_proposal_then_review_and_no_worker() -> None:
    plan = _plan()
    lineage = _lineage(plan)
    invocations = plan["controller_invocations"]

    assert plan["status"] == (
        "frozen_refinement_proposal_and_review_staged_not_run"
    )
    assert plan["controller_run_id"] == (
        "qf-public-only-holdings-review-refinement-20260824-r3"
    )
    assert plan["deploy_source_freeze"]["deploy_id"] == plan["controller_run_id"]
    assert [stage["stage"] for stage in plan["staged_execution"]] == [
        "proposal",
        "information_set_review",
        "target",
        "repeat",
        "protection",
    ]
    assert [stage["authorized_in_this_freeze"] for stage in plan["staged_execution"]] == [
        True,
        True,
        False,
        False,
        False,
    ]
    proposal_argv = tuple(invocations["proposal_stop"])
    review_argv = tuple(invocations["review_stop_resume"])
    assert _option(proposal_argv, "--state-dir") == _option(
        review_argv, "--state-dir"
    )
    assert _option(proposal_argv, "--stop-after-stage") == "proposal"
    assert _option(review_argv, "--stop-after-stage") == "information_set_review"
    assert invocations["target_invocation"] is None
    assert invocations["repeat_invocation"] is None
    assert invocations["protection_invocation"] is None
    assert all(stage["conditional_not_authorized"] is True for stage in lineage["stages"])
    for limits in (
        plan["limits"]["proposal_stage"],
        plan["limits"]["proposal_plus_review_cumulative"],
    ):
        assert limits["max_worker_sessions"] == 0
        assert limits["max_verifier_executions"] == 0
        assert limits["max_selected_probe_dispatches"] == 0


def test_real_refinement_evidence_binds_exact_r1_candidate_and_answer_free_contract() -> None:
    plan = _plan()
    lineage = _lineage(plan)
    contract = json.loads(R3_EVIDENCE.joinpath("contract.json").read_text())
    record = json.loads(
        R3_EVIDENCE.joinpath(
            "CANDIDATE-REVIEW-REFINEMENT-RECORD.json"
        ).read_text()
    )
    history = json.loads(
        R3_EVIDENCE.joinpath(
            "history/archive/entries/holdings-c1-review-r2.json"
        ).read_text()
    )
    snapshot = R3_EVIDENCE / history["evidence_paths"]["candidate_snapshot"]

    assert contract["stage"] == "LINEAGE_REFINEMENT"
    assert contract["feedback_tier"] == "answer_free_property_family_v2"
    assert contract["optimization_answers_exposed_to_evolver"] is False
    assert contract["optimization_answers_exposed_to_worker"] is False
    assert contract["review_feedback_worker_visible"] is False
    assert contract["review_feedback_public_basis_allowed"] is False
    assert record == {
        "candidate_component_history_exposed": False,
        "candidate_id": "qf-public-only-holdings-c1",
        "feedback_mode": "answer_free",
        "required_history_entry": "history/archive/entries/holdings-c1-review-r2.json",
        "review_feedback_public_basis_allowed": False,
        "schema_version": 1,
        "stage": "LINEAGE_REFINEMENT",
        "worker_visible": False,
    }
    assert history["candidate_id"] == lineage["parent"]["version"]
    assert history["worker_visible"] is False
    assert history["review_feedback_public_basis_allowed"] is False
    assert set(history["candidate_snapshot_members"]) == {
        "agent.yaml",
        "systemprompt.md",
        "tool_descriptions/run_shell_command.tool.yaml",
    }
    for member in history["candidate_snapshot_members"]:
        assert snapshot.joinpath(member).read_bytes() == R1_CANDIDATE_PATH.joinpath(
            member
        ).read_bytes()
    assert plan["frozen_inputs"]["refinement_evidence"].endswith(
        "/evidence/qf-public-only-holdings-review-refinement-evidence-20260824-r3"
    )


def test_real_proposal_argv_uses_r1_c1_backbone_and_r3_refinement_evidence() -> None:
    plan = _plan()
    lineage = _lineage(plan)
    proposal = lineage["proposal"]
    argv = build_proposal_argv(
        plan, lineage, proposal, approve_external_run=True
    )

    assert _option(argv, "--run-id") == (
        "qf-public-only-holdings-refine-proposal-20260824-r3"
    )
    assert _option(argv, "--backbone") == lineage["parent"]["worker_dir"]
    assert _option(argv, "--backbone").endswith(
        "qf-public-only-holdings-proposal-20260824-r1/"
        "evolutions/iteration-0001/candidate"
    )
    assert _option(argv, "--evidence") == (
        "/data/qea-julius-storage/evidence/"
        "qf-public-only-holdings-review-refinement-evidence-20260824-r3"
    )
    assert _option(argv, "--arm") == "quant-state"
    assert proposal["candidate_version"] == "qf-public-only-holdings-c2-r3"
    assert proposal["stage"] == "LINEAGE_REFINEMENT"
    assert "run_qfbench_breadth_pilot.py" not in " ".join(argv)


def test_review_is_arm_blind_exact_public_only_and_cumulative_from_h0() -> None:
    plan = _plan()
    lineage = _lineage(plan)
    spec = _information_set_review_spec(lineage)

    assert spec is not None
    assert spec["feedback_mode"] == "answer_free"
    assert spec["review_id"] == (
        "qf-public-only-holdings-information-set-review-20260824-r3"
    )
    assert spec["model"] == "deepseek/deepseek-v4-pro"
    assert spec["token_file"] == "/home/julius/qea/runtime/secrets/model-token"
    assert spec["arm_blind"] is True
    assert spec["optimize_only_sources"] == []
    assert spec["candidate_material_baseline_worker_dir"] == (
        "/data/qea-julius-storage/deploy/"
        "qf-public-only-holdings-review-refinement-20260824-r3/"
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
        input_path=Path("/trusted/review-input.json"),
        result_dir=Path("/trusted/review-result"),
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


def test_cumulative_review_package_uses_h0_to_simulated_c2_and_excludes_feedback(
    tmp_path: Path,
) -> None:
    plan = deepcopy(_plan())
    lineage = _lineage(plan)
    spec = _information_set_review_spec(lineage)
    c2 = tmp_path / "candidate-c2"
    shutil.copytree(R1_CANDIDATE_PATH, c2)
    prompt = c2.joinpath("systemprompt.md")
    prompt.write_text(
        prompt.read_text(encoding="utf-8")
        + "\nUse only a refined rule directly entailed by the supplied public contract.\n",
        encoding="utf-8",
    )
    r1_report = json.loads(R1_REPORT_PATH.read_text(encoding="utf-8"))
    claims = deepcopy(
        r1_report["summary"]["discovery_hypothesis"]["hypothesis"][
            "worker_visible_claims"
        ]
    )
    claims.append(
        {
            "claim_id": "refined-public-contract-discipline",
            "claim": "Use only a refined rule entailed by the supplied public contract.",
            "surfaces": ["systemprompt"],
            "basis_refs": [
                {
                    "kind": "public_contract",
                    "ref": (
                        "benchmarks/qfbench/tasks/"
                        "13f-amendment-aware-crowding/instruction.md"
                    ),
                    "support": "The complete instruction is supplied for review.",
                }
            ],
        }
    )
    spec["candidate_material_baseline_worker_dir"] = str(
        ROOT / "qea/worker_quant_h0"
    )
    state = {
        "current_parent": {
            "version": "qf-public-only-holdings-c1",
            "worker_dir": str(R1_CANDIDATE_PATH),
        },
        "candidate": {
            "version": "qf-public-only-holdings-c2-r3",
            "worker_dir": str(c2),
        },
        "proposal": {"worker_visible_claims": claims},
    }

    package, hold = _candidate_information_set_review_package(state, spec)

    assert hold is None
    assert package is not None
    assert package["candidate_id"] == "qf-public-only-holdings-c2-r3"
    assert package["optimize_only_sources"] == []
    assert "+### Data-convention discipline" in package["candidate"]["diff"]
    assert "+Use only a refined rule directly entailed" in package["candidate"]["diff"]
    rendered = json.dumps(package, ensure_ascii=False).casefold()
    for forbidden in (
        "qf-public-only-holdings-review-refinement-evidence-20260824-r3",
        "holdings-c1-review-r2",
        "semantic_review_feedback",
        "review_feedback",
        "optimization-diagnostic",
        "search_arm",
    ):
        assert forbidden not in rendered


def test_same_state_controller_fixture_stops_proposal_then_review_only(
    tmp_path: Path,
) -> None:
    plan = deepcopy(_plan())
    lineage = _lineage(plan)
    c2 = tmp_path / "candidate-c2"
    shutil.copytree(R1_CANDIDATE_PATH, c2)
    c2.joinpath("systemprompt.md").write_text(
        c2.joinpath("systemprompt.md").read_text(encoding="utf-8")
        + "\nUse only refinements directly supported by the public task contract.\n",
        encoding="utf-8",
    )
    report = json.loads(R1_REPORT_PATH.read_text(encoding="utf-8"))
    report["candidate_dir"] = str(c2)
    claims = report["summary"]["discovery_hypothesis"]["hypothesis"][
        "worker_visible_claims"
    ]
    claims.append(
        {
            "claim_id": "refined-public-support-only",
            "claim": "Use only refinements directly supported by the public contract.",
            "surfaces": ["systemprompt"],
            "basis_refs": [
                {
                    "kind": "public_contract",
                    "ref": (
                        "benchmarks/qfbench/tasks/"
                        "13f-amendment-aware-crowding/instruction.md"
                    ),
                    "support": "The complete public instruction is supplied.",
                }
            ],
        }
    )
    local_report = tmp_path / "admitted-c2-proposal-report.json"
    local_report.write_text(json.dumps(report), encoding="utf-8")
    plan["runtime"]["python"] = "/python"
    plan["runtime"]["source_root"] = "/source"
    plan["runtime"]["results_dir"] = str(tmp_path / "results")
    lineage["parent"]["worker_dir"] = str(R1_CANDIDATE_PATH)
    lineage["proposal"]["replay_report"] = str(local_report)
    lineage["candidate_information_set_review"][
        "candidate_material_baseline_worker_dir"
    ] = str(ROOT / "qea/worker_quant_h0")
    local_plan = tmp_path / "plan.json"
    local_plan.write_text(json.dumps(plan), encoding="utf-8")
    state_dir = tmp_path / "same-r3-state"

    stage_a = run_controller(
        local_plan,
        state_dir,
        selected_lineages={lineage["lineage_id"]},
        stop_after_stage="proposal",
        approve_external_run=True,
        runner=lambda _argv: (_ for _ in ()).throw(
            AssertionError("stage A fixture must stop before any external call")
        ),
    )["lineages"][lineage["lineage_id"]]

    assert stage_a["phase"] == "INFORMATION_SET_REVIEW"
    assert stage_a["stopped_after_stage"] == "proposal"
    assert stage_a["candidate"]["version"] == "qf-public-only-holdings-c2-r3"
    assert stage_a["observations"] == {}
    calls: list[tuple[str, ...]] = []

    def reviewer_only(argv: tuple[str, ...]) -> None:
        calls.append(tuple(argv))
        assert argv[1] == (
            "/source/scripts/run_candidate_information_set_reviewer_canary.py"
        )
        package = json.loads(
            Path(_option(tuple(argv), "--input")).read_text(encoding="utf-8")
        )
        _write_fake_review(Path(_option(tuple(argv), "--out")), package)

    stage_b = run_controller(
        local_plan,
        state_dir,
        selected_lineages={lineage["lineage_id"]},
        stop_after_stage="information_set_review",
        approve_external_run=True,
        runner=reviewer_only,
    )["lineages"][lineage["lineage_id"]]

    assert len(calls) == 1
    assert "run_qfbench_discovery_pilot.py" not in " ".join(calls[0])
    assert "run_qfbench_breadth_pilot.py" not in " ".join(calls[0])
    assert stage_b["phase"] == "HOLD_FOR_REFINE"
    assert stage_b["decision"] == "HOLD_FOR_REFINE"
    assert stage_b["stopped_after_stage"] == "information_set_review"
    assert stage_b["observations"].keys() == {"information_set_review"}
    assert stage_b["accounted_review_ids"] == [
        "qf-public-only-holdings-information-set-review-20260824-r3"
    ]
    package = json.loads(
        state_dir.joinpath(
            "review-inputs/"
            "qf-public-only-holdings-information-set-review-20260824-r3.json"
        ).read_text(encoding="utf-8")
    )
    assert "+### Data-convention discipline" in package[
        "candidate"
    ]["diff"]
    assert "+Use only refinements directly supported" in package["candidate"][
        "diff"
    ]


def test_plan_contains_no_evaluator_outcomes_or_content_identity_fields() -> None:
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
