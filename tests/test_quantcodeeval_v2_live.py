import json
import shutil
from pathlib import Path

from qea.loop_benchmark import hash_worker_directory
from qea.quantcodeeval_v2_live import (
    _activation_from_component_tests,
    _proxy_audit,
    _seed_rejected_attempt_history,
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
