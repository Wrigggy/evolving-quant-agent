import json
from pathlib import Path

from qea.candidate_information_set_review import (
    build_candidate_information_set_reviewer_prompt,
    validate_candidate_information_set_review_package,
)
from scripts import run_candidate_information_set_reviewer_canary as runner


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


def test_openrouter_runner_uses_one_standard_library_request(monkeypatch):
    calls = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(
                {
                    "id": "gen-fixture-1",
                    "choices": [{"message": {"content": "review-json"}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 2},
                }
            ).encode("utf-8")

    def urlopen(request, timeout):
        calls.append((request, timeout))
        return Response()

    monkeypatch.setattr(runner.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(
        runner,
        "_generation_metadata",
        lambda request_id, token: {"provider_cost_usd": 0.01},
    )
    record = {}

    content = runner._openrouter_complete(
        "review this",
        model="deepseek/deepseek-v4-pro",
        provider="deepseek",
        token="fixture-token",
        request_record=record,
    )

    assert content == "review-json"
    assert len(calls) == 1
    payload = json.loads(calls[0][0].data)
    assert payload["provider"] == {
        "order": ["deepseek"],
        "allow_fallbacks": False,
    }
    assert record["request_count"] == 1
    assert record["accounting"] == {"provider_cost_usd": 0.01}
