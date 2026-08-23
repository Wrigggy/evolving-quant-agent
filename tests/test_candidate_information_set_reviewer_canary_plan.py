import json
from pathlib import Path

from qea.candidate_information_set_review import (
    build_candidate_information_set_reviewer_prompt,
    validate_candidate_information_set_review_package,
)


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data/breadth/CANDIDATE_INFORMATION_SET_REVIEWER_CANARY_INPUT.json"
PLAN = ROOT / "data/breadth/CANDIDATE_INFORMATION_SET_REVIEWER_CANARY_PLAN.json"


def test_canary_package_is_valid_and_reviewer_is_arm_blind():
    package = json.loads(INPUT.read_text(encoding="utf-8"))

    validate_candidate_information_set_review_package(package)
    prompt = build_candidate_information_set_reviewer_prompt(package)

    assert '"search_arm"' not in prompt
    assert len(package["worker_visible_claims"]) == 5
    assert package["candidate"]["diff"].count("\n+") == 4


def test_canary_freezes_one_request_no_worker_and_all_expected_verdicts():
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    expected = plan["predeclared_expectations"]

    assert plan["status"] == "frozen_before_model_call"
    assert plan["max_model_requests"] == 1
    assert plan["provider_cost_limit_usd"] == "0.05"
    assert plan["worker_calls_allowed"] == 0
    assert plan["promotion_authority"] is False
    assert plan["worker_visible"] is False
    assert expected == {
        "raw-svi-a-positive": "REJECT",
        "terminal-local-vol-atm-positive": "REJECT",
        "pair-array-only": "REJECT",
        "written-local-vol-positive": "PASS",
        "effective-state-downstream-reconciliation": "PASS",
        "coverage_review": "PASS",
        "overall_verdict": "REJECT",
    }


def test_canary_sources_are_existing_retained_evidence():
    package = json.loads(INPUT.read_text(encoding="utf-8"))

    for source in package["public_sources"] + package["optimize_only_sources"]:
        assert (ROOT / source["source_path"]).exists(), source["source_path"]
