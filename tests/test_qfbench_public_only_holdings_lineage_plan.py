from __future__ import annotations

import json
from pathlib import Path

from scripts.run_qfbench_lineage_controller import (
    _candidate_information_set_review_package,
    _information_set_review_spec,
    build_candidate_information_set_review_argv,
    build_child_argv,
    build_proposal_argv,
)


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "data/breadth/QF_PUBLIC_ONLY_HOLDINGS_LINEAGE_R1_PLAN.json"


def _plan() -> dict[str, object]:
    return json.loads(PLAN_PATH.read_text())


def _lineage(plan: dict[str, object]) -> dict[str, object]:
    assert len(plan["lineages"]) == 1
    return plan["lineages"][0]


def _stage(lineage: dict[str, object], name: str) -> dict[str, object]:
    return next(stage for stage in lineage["stages"] if stage["name"] == name)


def _option(argv: tuple[str, ...], option: str) -> str:
    return argv[argv.index(option) + 1]


def _arm_values(argv: tuple[str, ...]) -> list[str]:
    return [argv[index + 1] for index, value in enumerate(argv) if value == "--arm"]


def test_plan_freezes_two_stops_and_never_auto_dispatches_worker() -> None:
    plan = _plan()

    assert plan["status"] == "frozen_proposal_and_review_staged_not_run"
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
    invocations = plan["controller_invocations"]
    assert _option(tuple(invocations["proposal_stop"]), "--stop-after-stage") == "proposal"
    assert _option(tuple(invocations["review_stop_resume"]), "--stop-after-stage") == (
        "information_set_review"
    )
    assert invocations["target_invocation"] is None
    assert invocations["repeat_invocation"] is None
    assert invocations["protection_invocation"] is None
    assert plan["limits"]["proposal_stage"]["max_worker_sessions"] == 0
    assert plan["limits"]["proposal_plus_review_cumulative"]["max_worker_sessions"] == 0
    assert plan["limits"]["proposal_plus_review_cumulative"]["max_reviewer_requests"] == 1


def test_predecessor_request_breach_is_explicit_and_not_reaccounted() -> None:
    prior = _plan()["predecessor_prescreen"]

    assert prior["result"]["official_tests_passed"] == 47
    assert prior["result"]["official_tests_total"] == 51
    assert prior["result"]["completed_requests"] == 47
    assert prior["frozen_thresholds"]["max_completed_requests"] == 40
    assert prior["request_threshold_audit"] == {
        "status": "BREACHED",
        "excess_completed_requests": 7,
        "interpretation": (
            "The completed prescreen remains a valid target-selection observation, "
            "but its request threshold breach is retained and cannot be hidden by "
            "starting this lineage. The threshold was a post-run audit threshold, "
            "not a mid-turn interrupt. No follow-on dispatch occurred under the "
            "prescreen plan."
        ),
    }
    assert "not charged again" in prior["new_lineage_accounting"]


def test_real_proposal_argv_uses_current_h0_and_public_trajectory_only() -> None:
    plan = _plan()
    lineage = _lineage(plan)
    proposal = lineage["proposal"]

    argv = build_proposal_argv(
        plan,
        lineage,
        proposal,
        approve_external_run=True,
    )

    assert argv[1] == (
        plan["runtime"]["source_root"]
        + "/scripts/run_qfbench_discovery_pilot.py"
    )
    assert _option(argv, "--run-id") == "qf-public-only-holdings-proposal-20260824-r1"
    assert _option(argv, "--backbone") == plan["frozen_inputs"]["current_quant_h0"][
        "worker_dir"
    ]
    assert _option(argv, "--evidence") == (
        "/data/qea-julius-storage/evidence/"
        "qf-public-only-holdings-public-trajectory-evidence-20260824-r1"
    )
    assert _option(argv, "--arm") == "quant-state"
    assert _option(argv, "--reasoning-effort") == "high"
    rendered = " ".join(argv)
    assert "pilot-report.json" not in rendered
    assert "47/51" not in rendered
    assert "information-set-review" not in rendered


def test_answer_free_review_is_arm_blind_and_uses_only_exact_public_clauses() -> None:
    plan = _plan()
    spec = _information_set_review_spec(_lineage(plan))

    assert spec is not None
    assert spec["feedback_mode"] == "answer_free"
    assert spec["optimize_only_sources"] == []
    assert spec["arm_blind"] is True
    assert [source["ref"] for source in spec["public_sources"]] == [
        "public:13f-effective-filing-state",
        "public:13f-effective-book",
        "public:13f-derived-analytics",
        "public:13f-semantic-encoding-flexibility",
    ]
    assert {source["source_type"] for source in spec["public_sources"]} == {
        "public_contract"
    }
    assert {source["source_path"] for source in spec["public_sources"]} == {
        "benchmarks/qfbench/tasks/13f-amendment-aware-crowding/instruction.md"
    }
    excerpts = "\n".join(source["excerpt"] for source in spec["public_sources"])
    assert "reconstruct the effective filing state" in excerpts
    assert "From the resulting effective books" in excerpts
    assert "unambiguous list/pair encodings are acceptable" in excerpts
    assert "0.5 *" not in excerpts
    assert "test_turnover" not in excerpts


def test_controller_builds_arm_blind_review_package_from_complete_claims(
    tmp_path: Path,
) -> None:
    plan = _plan()
    lineage = _lineage(plan)
    spec = _information_set_review_spec(lineage)
    parent = tmp_path / "quant-h0"
    candidate = tmp_path / "candidate"
    for root, prompt in (
        (parent, "Use public task requirements.\n"),
        (
            candidate,
            "Recompute listed downstream analytics from the final effective book.\n",
        ),
    ):
        root.mkdir()
        root.joinpath("agent.yaml").write_text("tools: []\n")
        root.joinpath("systemprompt.md").write_text(prompt)
    claims = [
        {
            "claim_id": "effective-state-downstream-reconciliation",
            "claim": (
                "The listed downstream analytics must be recomputed from the final "
                "effective holdings book."
            ),
            "surfaces": ["systemprompt"],
            "basis_refs": [
                {
                    "kind": "public_contract",
                    "ref": (
                        "benchmarks/qfbench/tasks/"
                        "13f-amendment-aware-crowding/instruction.md"
                    ),
                    "support": "The contract computes the listed analytics from the resulting effective books.",
                }
            ],
        }
    ]
    state = {
        "current_parent": {"version": "quant-h0", "worker_dir": str(parent)},
        "candidate": {"version": "qf-public-only-holdings-c1", "worker_dir": str(candidate)},
        "proposal": {"worker_visible_claims": claims},
    }

    package, hold = _candidate_information_set_review_package(state, spec)

    assert hold is None
    assert package is not None
    assert package["worker_visible_claims"] == claims
    assert package["public_sources"] == spec["public_sources"]
    assert package["optimize_only_sources"] == []
    assert "search_arm" not in package
    assert "selection_reference" not in package
    rendered = json.dumps(package)
    assert "pilot-report.json" not in rendered
    assert "47/51" not in rendered
    assert "official_tests_passed" not in rendered
    argv = build_candidate_information_set_review_argv(
        plan,
        spec,
        input_path=tmp_path / "review-input.json",
        result_dir=tmp_path / "review-result",
        approve_external_run=True,
    )
    assert _option(argv, "--model") == "deepseek/deepseek-v4-pro"
    assert _option(argv, "--token-file") == (
        "/home/julius/qea/runtime/secrets/model-token"
    )
    assert "--dotenv" not in argv
    assert "--arm" not in argv


def test_target_uses_fresh_selection_reference_but_child_argv_is_candidate_only() -> None:
    plan = _plan()
    lineage = _lineage(plan)
    target = _stage(lineage, "target")
    reference = target["selection_reference"]

    assert reference["id"] == "qf-public-only-holdings-h0-prescreen-20260824-r1"
    assert reference["reference_version"] == "quant-h0"
    assert reference["tests_passed"] == 47
    assert reference["tests_total"] == 51
    assert reference["reward"] == 0.0
    active = {
        **lineage,
        "candidate": {
            "version": lineage["proposal"]["candidate_version"],
            "worker_dir": "/candidate/qf-public-only-holdings-c1",
            "activation_token": "reconcile_effective_holdings",
            "activation_binding": {"status": "singleton"},
        },
    }
    argv = build_child_argv(plan, active, target, approve_external_run=True)

    assert _option(argv, "--run-id") == "qf-public-only-holdings-target-20260824-r1"
    assert _option(argv, "--task-id") == "13f-amendment-aware-crowding"
    assert _option(argv, "--activation-token") == "reconcile_effective_holdings"
    assert _arm_values(argv) == [
        "public-holdings-c1=/candidate/qf-public-only-holdings-c1"
    ]
    rendered = " ".join(argv)
    assert "pilot-report.json" not in rendered
    assert "47/51" not in rendered


def test_repeat_and_protection_ids_are_reserved_but_not_authorized() -> None:
    plan = _plan()
    lineage = _lineage(plan)
    repeat = _stage(lineage, "repeat")
    protection = _stage(lineage, "protection")

    assert lineage["repeat_consistency_policy"] == "resolved_property_footprint_v1"
    assert repeat["live_run_id"] == "qf-public-only-holdings-repeat-20260824-r1"
    assert protection["live_run_id"] == (
        "qf-public-only-holdings-protection-20260824-r1"
    )
    assert repeat["conditional_not_authorized"] is True
    assert protection["conditional_not_authorized"] is True
    assert "selection_reference" not in repeat
    assert "selection_reference" not in protection
    assert plan["limits"]["repeat_and_protection"].startswith("IDs are reserved")
    policy = lineage["candidate_policy"]
    assert policy["complete_worker_visible_claim_inventory_required"] is True
    assert policy["every_claim_requires_exact_supplied_public_provenance"] is True
    assert policy["singleton_callable_component_activation_binding_required_before_review"] is True
    forbidden = "\n".join(policy["forbidden_worker_visible_content"])
    assert "turnover formula" in forbidden
    assert "canonical or representative" in forbidden
    assert "mandatory pair/list" in forbidden
    assert "official property identity" in forbidden


def test_plan_adds_no_content_identity_fields() -> None:
    def keys(value: object) -> list[str]:
        if isinstance(value, dict):
            return [str(key) for key in value] + [
                child_key
                for child in value.values()
                for child_key in keys(child)
            ]
        if isinstance(value, list):
            return [child_key for child in value for child_key in keys(child)]
        return []

    assert not any(
        "sha" in key.casefold() or "digest" in key.casefold()
        for key in keys(_plan())
    )
