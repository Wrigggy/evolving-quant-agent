import json
import shutil
from pathlib import Path

import pytest

from qea.loop_benchmark import hash_worker_directory
from qea.quantcodeeval_v2_live import (
    QuantCodeEvalV2LiveError,
    _activation_from_component_tests,
    _proxy_audit,
    _seed_full_candidate_failure_history,
    _seed_rejected_attempt_history,
    _seed_scored_candidate_history,
    _prior_attempt_paths,
)
from qea.quantcodeeval_history import validate_quantcodeeval_history


def _candidate(root: Path) -> Path:
    candidate = root / "candidate"
    candidate.mkdir()
    (candidate / "agent.yaml").write_text("type: agent\n", encoding="utf-8")
    (candidate / "systemprompt.md").write_text("work\n", encoding="utf-8")
    (candidate / "tools").mkdir()
    (candidate / "tools/checkpoint.py").write_text(
        "def checkpoint():\n    return True\n", encoding="utf-8"
    )
    return candidate


def test_activation_requires_executable_digest_bound_final_smoke(tmp_path):
    candidate = _candidate(tmp_path)
    digest = hash_worker_directory(candidate)
    decision = {"primary_components": ["tools"]}
    tests = (
        {
            "schema_version": 1,
            "test_index": 1,
            "component": "tools",
            "status": "passed",
            "candidate_digest": digest,
        },
    )

    passed = _activation_from_component_tests(candidate, decision, tests, 1)
    stale = _activation_from_component_tests(
        candidate,
        decision,
        ({**tests[0], "candidate_digest": "0" * 64},),
        1,
    )
    prompt_only = _activation_from_component_tests(
        candidate,
        {"primary_components": ["systemprompt"]},
        (),
        1,
    )

    assert passed["status"] == "passed"
    assert passed["activated_primary_components"] == ["tools"]
    assert stale["status"] == "failed"
    assert prompt_only["status"] == "failed"


def test_comparison_run_paths_preserve_order_and_reject_duplicates(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"

    assert _prior_attempt_paths([first, second]) == (first, second)
    with pytest.raises(QuantCodeEvalV2LiveError, match="duplicated"):
        _prior_attempt_paths([first, first])


def test_proxy_audit_retains_exact_request_cost_and_ids(tmp_path):
    audit = tmp_path / "attempts/evolver-iteration-1/proxy-audit.jsonl"
    audit.parent.mkdir(parents=True)
    rows = [
        {
            "request_state": "completed",
            "failure_class": None,
            "upstream_status_code": 200,
            "provider_request_id": "gen-1",
            "provider_cost_usd": 0.01,
            "input_tokens": 10,
            "output_tokens": 2,
            "total_tokens": 12,
        },
        {
            "request_state": "completed",
            "failure_class": None,
            "upstream_status_code": 200,
            "provider_request_id": "gen-2",
            "provider_cost_usd": 0.02,
            "input_tokens": 20,
            "output_tokens": 3,
            "total_tokens": 23,
        },
    ]
    audit.write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )

    result = _proxy_audit(tmp_path)

    assert result["all_requests_completed"] is True
    assert result["cost_complete"] is True
    assert result["provider_cost_usd"] == 0.03
    assert result["total_tokens"] == 35
    assert result["provider_request_ids"] == ["gen-1", "gen-2"]


def test_prior_rejected_attempt_becomes_exact_searchable_history(tmp_path):
    source = Path(__file__).resolve().parents[1] / "qea/worker_gdpval_weak"
    seed = tmp_path / "seed"
    shutil.copytree(source, seed)
    prior = tmp_path / "qce-v2-prior"
    attempt = prior / "evolutions/iteration-0001"
    candidate = attempt / "candidate"
    candidate.parent.mkdir(parents=True)
    shutil.copytree(seed, candidate)
    prompt = candidate / "systemprompt.md"
    prompt.write_text(prompt.read_text() + "Validate units.\n")
    decision = {
        "decision": "ACT",
        "hypotheses_considered": [
            {"hypothesis_id": "h1", "mechanism": "validate units"}
        ],
        "selected_hypothesis_id": "h1",
        "primary_components": ["systemprompt"],
        "components": ["systemprompt", "validator"],
    }
    (attempt / "summary.json").write_text(
        json.dumps(
            {
                "discovery_hypothesis": {
                    "decision": "ACT",
                    "hypothesis": decision,
                },
                "component_tests": [],
            }
        )
    )
    digest = hash_worker_directory(candidate)
    (attempt / "result.json").write_text(json.dumps({"candidate_digest": digest}))

    imported = _seed_rejected_attempt_history(
        history_root=tmp_path / "history",
        prior_attempt_dir=prior,
        seed_worker_dir=seed,
        h0_rewards={"T16": 1.0, "T24": 0.0},
    )

    assert imported["candidate_digest"] == digest
    assert imported["declared_roles"] == ["systemprompt", "validator"]
    assert imported["actual_roles"] == ["systemprompt"]
    assert validate_quantcodeeval_history(tmp_path / "history")["entry_count"] == 1


def test_prior_admission_rejection_becomes_exact_searchable_history(tmp_path):
    source = Path(__file__).resolve().parents[1] / "qea/worker_gdpval_weak"
    seed = tmp_path / "seed"
    shutil.copytree(source, seed)
    prior = tmp_path / "qce-v2-admission-rejected"
    attempt = prior / "evolutions/iteration-0001"
    candidate = attempt / "candidate"
    candidate.parent.mkdir(parents=True)
    shutil.copytree(seed, candidate)
    (candidate / "tools").mkdir()
    (candidate / "tools/_selftest.py").write_text(
        "def run():\n    return True\n", encoding="utf-8"
    )
    decision = {
        "decision": "ACT",
        "hypotheses_considered": [
            {"hypothesis_id": "h1", "mechanism": "self-test delivery"}
        ],
        "selected_hypothesis_id": "h1",
        "primary_components": ["tools"],
        "components": ["tools"],
    }
    digest = hash_worker_directory(candidate)
    (attempt / "summary.json").write_text(
        json.dumps(
            {
                "discovery_hypothesis": {
                    "decision": "ACT",
                    "hypothesis": decision,
                },
                "component_tests": [
                    {
                        "schema_version": 1,
                        "test_index": 1,
                        "status": "passed",
                        "component": "tools",
                        "candidate_digest": digest,
                    }
                ],
            }
        )
    )
    (attempt / "result.json").write_text(
        json.dumps({"candidate_digest": digest})
    )

    imported = _seed_rejected_attempt_history(
        history_root=tmp_path / "history",
        prior_attempt_dir=prior,
        seed_worker_dir=seed,
        h0_rewards={"T16": 1.0, "T24": 0.0},
    )

    entry = json.loads(
        (tmp_path / "history/entries" / f"{imported['entry_id']}.json").read_text()
    )
    assert "not reachable" in imported["reason"]
    assert entry["activation"]["failure_stage"] == "candidate_admission"
    assert entry["selection"] == "rejected"
    assert validate_quantcodeeval_history(tmp_path / "history")["entry_count"] == 1


def test_failed_full_candidate_becomes_unscored_searchable_history(tmp_path):
    source = Path(__file__).resolve().parents[1] / "qea/worker_gdpval_weak"
    seed = tmp_path / "seed"
    shutil.copytree(source, seed)
    activation = tmp_path / "qce-v2-activation"
    candidate = activation / "evolutions/iteration-0001/candidate"
    candidate.parent.mkdir(parents=True)
    shutil.copytree(seed, candidate)
    (candidate / "tools").mkdir()
    (candidate / "tools/checkpoint.py").write_text(
        "def checkpoint():\n    return True\n", encoding="utf-8"
    )
    digest = hash_worker_directory(candidate)
    decision = {
        "decision": "ACT",
        "hypotheses_considered": [
            {"hypothesis_id": "h1", "mechanism": "checkpoint exact output"}
        ],
        "selected_hypothesis_id": "h1",
        "primary_components": ["tools"],
        "components": ["tools"],
    }
    component_tests = [
        {
            "status": "passed",
            "component": "tools",
            "candidate_digest": digest,
        }
    ]
    activation_payload = {
        "status": "passed",
        "candidate_digest": digest,
        "official_worker_evaluation_run": False,
    }
    (activation / "LIVE-RESULT.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "candidate_benchmark_evaluated": False,
                "candidate_digest": digest,
                "decision": decision,
                "component_tests": component_tests,
                "activation": activation_payload,
            }
        ),
        encoding="utf-8",
    )
    full = tmp_path / "qce-v2-full-candidate"
    full.mkdir()
    h0_id = "7" * 64
    (full / "FULL-CANDIDATE-PREFLIGHT.json").write_text(
        json.dumps(
            {
                "status": "preflight_complete",
                "source_h0_evaluation_id": h0_id,
                "candidate_worker_digest": digest,
                "declared_roles": ["tools"],
                "iteration": 1,
            }
        ),
        encoding="utf-8",
    )
    (full / "FULL-CANDIDATE-RESULT.json").write_text(
        json.dumps(
            {
                "status": "evaluation_failed",
                "official_evaluated": False,
                "benchmark_score_claimed": False,
                "candidate_worker_digest": digest,
                "attempts": [
                    {
                        "task_id": "T16",
                        "failure_stage": "worker_artifact_contract",
                        "failure_class": "output_membership_overflow",
                        "official_score_available": False,
                    },
                    {
                        "task_id": "T24",
                        "failure_stage": "worker_artifact_contract",
                        "failure_class": "missing_submission_artifact",
                        "official_score_available": False,
                    },
                ],
                "partial_cost_and_lifecycle_audit": {
                    "request_count": 15,
                    "all_recorded_resources_cleaned": True,
                },
            }
        ),
        encoding="utf-8",
    )

    imported = _seed_full_candidate_failure_history(
        history_root=tmp_path / "history",
        activation_run_dir=activation,
        full_candidate_run_dir=full,
        seed_worker_dir=seed,
        h0_evaluation_id=h0_id,
    )

    validation = validate_quantcodeeval_history(tmp_path / "history")
    entry = json.loads(
        (tmp_path / "history/entries" / f"{imported['entry_id']}.json").read_text()
    )
    assert validation["entry_count"] == 1
    assert entry["selection"] == "rejected"
    assert entry["activation"]["status"] == "passed"
    assert entry["evaluation"]["official_evaluated"] is False
    assert entry["evaluation"]["benchmark_score_claimed"] is False
    assert entry["evaluation"]["task_outcomes"][1]["failure_class"] == (
        "missing_submission_artifact"
    )


def test_completed_panel_becomes_rejected_searchable_history(tmp_path):
    source = Path(__file__).resolve().parents[1] / "qea/worker_gdpval_weak"
    seed = tmp_path / "seed"
    shutil.copytree(source, seed)
    activation = tmp_path / "qce-v2-activation"
    candidate = activation / "evolutions/iteration-0001/candidate"
    candidate.parent.mkdir(parents=True)
    shutil.copytree(seed, candidate)
    prompt = candidate / "systemprompt.md"
    prompt.write_text(prompt.read_text() + "Validate every task.\n")
    digest = hash_worker_directory(candidate)
    decision = {
        "decision": "ACT",
        "hypotheses_considered": [
            {"hypothesis_id": "h1", "mechanism": "broad validation"}
        ],
        "selected_hypothesis_id": "h1",
        "primary_components": ["systemprompt"],
        "components": ["systemprompt"],
    }
    component_tests = [
        {
            "status": "passed",
            "component": "systemprompt",
            "candidate_digest": digest,
        }
    ]
    activation_payload = {"status": "passed", "candidate_digest": digest}
    (activation / "LIVE-RESULT.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "candidate_benchmark_evaluated": False,
                "candidate_digest": digest,
                "decision": decision,
                "component_tests": component_tests,
                "activation": activation_payload,
            }
        )
    )
    full = tmp_path / "qce-v2-full-candidate"
    full.mkdir()
    h0_id = "7" * 64
    (full / "FULL-CANDIDATE-PREFLIGHT.json").write_text(
        json.dumps(
            {
                "status": "preflight_complete",
                "source_h0_evaluation_id": h0_id,
                "candidate_worker_digest": digest,
                "iteration": 1,
            }
        )
    )
    (full / "FULL-CANDIDATE-RESULT.json").write_text(
        json.dumps(
            {
                "status": "complete",
                "official_evaluated": True,
                "candidate_worker_digest": digest,
                "score_summary": {"task_rewards": {"T16": 0.0, "T24": 0.0}},
                "attempts": [
                    {
                        "task_id": "T16",
                        "answer_free_evidence": {"official_reward": 0.0},
                    },
                    {
                        "task_id": "T24",
                        "answer_free_evidence": {
                            "diagnostic_tags": ["missing_artifact"]
                        },
                    },
                ],
                "cost_audit": {"request_count": 24},
            }
        )
    )

    imported = _seed_scored_candidate_history(
        history_root=tmp_path / "history",
        activation_run_dir=activation,
        full_candidate_run_dir=full,
        seed_worker_dir=seed,
        h0_evaluation_id=h0_id,
        h0_rewards={"T16": 1.0, "T24": 0.0},
    )

    index = json.loads((tmp_path / "history/INDEX.json").read_text())
    entry = json.loads(
        (tmp_path / "history/entries" / f"{index['entries'][0]}.json").read_text()
    )
    assert imported["official_rewards"] == {"T16": 0.0, "T24": 0.0}
    assert entry["selection"] == "rejected"
    assert entry["evaluation"]["official_evaluated"] is True
    assert entry["evaluation"]["official_rewards"] == {"T16": 0.0, "T24": 0.0}
    assert entry["evaluation"]["h0_official_rewards"] == {"T16": 1.0, "T24": 0.0}


def test_prior_path_lists_preserve_multiple_scored_rounds():
    from qea.quantcodeeval_v2_live import _prior_attempt_paths

    assert _prior_attempt_paths([Path("activation-r6"), Path("activation-r8")]) == (
        Path("activation-r6"),
        Path("activation-r8"),
    )
