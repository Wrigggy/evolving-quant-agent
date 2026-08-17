import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from qea.loop_benchmark import hash_worker_directory
from qea.quantcodeeval_full_candidate import (
    QuantCodeEvalFullCandidateError,
    _answer_free_attempt_row,
    materialize_quantcodeeval_full_candidate_failure_result,
    run_quantcodeeval_full_candidate,
)
from qea.evaluation import TaskAttempt


def _worker(root: Path) -> Path:
    source = Path(__file__).resolve().parents[1] / "qea/worker_gdpval_weak"
    shutil.copytree(source, root)
    return root


def _candidate(parent: Path, root: Path) -> Path:
    shutil.copytree(parent, root)
    (root / "tools").mkdir()
    (root / "tools/__init__.py").write_text("")
    (root / "tools/check.py").write_text(
        "def check(value):\n    return {'ok': bool(value)}\n"
    )
    (root / "tool_descriptions/check.tool.yaml").write_text(
        "type: tool\nname: check\ndescription: Check one value.\n"
        "input_schema:\n  type: object\n  properties:\n"
        "    value: {type: boolean}\n  required: [value]\n"
        "  additionalProperties: false\n"
    )
    agent = (root / "agent.yaml").read_text()
    agent = agent.replace(
        "\ntracers:\n",
        "\n  - name: check\n"
        "    yaml_path: ./tool_descriptions/check.tool.yaml\n"
        "    binding: tools.check:check\n"
        "\ntracers:\n",
    )
    (root / "agent.yaml").write_text(agent)
    return root


def test_full_candidate_preflight_accepts_coherent_multifile_component(
    tmp_path, monkeypatch
):
    if not hasattr(sys, "stdlib_module_names"):
        monkeypatch.setattr(sys, "stdlib_module_names", frozenset(), raising=False)
    seed = _worker(tmp_path / "seed")
    candidate = _candidate(seed, tmp_path / "candidate")
    tasks = (SimpleNamespace(task_id="T16"), SimpleNamespace(task_id="T24"))
    snapshot = SimpleNamespace(
        commit="9" * 40,
        optimize=SimpleNamespace(task_ids=("T16", "T24"), tasks=tasks),
    )
    preflight = {
        "public_manifest_sha256": "1" * 64,
        "trusted_manifest_sha256": "2" * 64,
        "runtime_identity_sha256": "3" * 64,
    }

    def fake_prepare(**kwargs):
        return snapshot, object(), preflight, seed

    monkeypatch.setattr(
        "qea.quantcodeeval_full_candidate.prepare_quantcodeeval_h0", fake_prepare
    )
    digest = hash_worker_directory(candidate)
    result = run_quantcodeeval_full_candidate(
        config_path=tmp_path / "config.json",
        public_root=tmp_path / "public",
        trusted_root=tmp_path / "trusted",
        run_dir=tmp_path / "candidate-run",
        seed_worker_dir=seed,
        parent_worker_dir=seed,
        candidate_worker_dir=candidate,
        iteration=1,
        mechanism="register one public boolean check",
        primary_components=("tools",),
        declared_roles=("agent_config", "tool_descriptions", "tools"),
        component_tests=(
            {
                "status": "failed",
                "kind": "tool",
                "component": "tools",
                "candidate_digest": "0" * 64,
            },
            {
                "status": "passed",
                "kind": "tool",
                "component": "tools",
                "candidate_digest": digest,
            },
        ),
        activation={"status": "not_run"},
        worker_image_ref="sha256:" + "4" * 64,
        verifier_image_ref="sha256:" + "5" * 64,
        proxy_image_ref="sha256:" + "6" * 64,
        token_file=tmp_path / "token",
        source_h0_evaluation_id="7" * 64,
        task_ids=("T24",),
        preflight_only=True,
    )

    assert result["protocol"] == "quant_property_v2_full_candidate"
    assert result["candidate_worker_digest"] == digest
    assert result["primary_components"] == ["tools"]
    assert result["declared_roles"] == [
        "agent_config",
        "tool_descriptions",
        "tools",
    ]
    assert result["mutation_metrics"]["changed_file_count"] == 4
    assert result["mutation_metrics"]["declared_roles_match_actual"] is True
    assert result["task_ids"] == ["T24"]


def test_component_smoke_requires_executable_primary_not_prompt_binding():
    from qea.quantcodeeval_full_candidate import _validate_component_tests

    digest = "a" * 64
    tests = _validate_component_tests(
        (
            {
                "status": "passed",
                "component": "tools",
                "candidate_digest": digest,
            },
        ),
        candidate_digest=digest,
        primary_components=("tools", "systemprompt"),
    )

    assert tests[0]["component"] == "tools"


def test_answer_free_row_uses_completed_replacement_attempt(tmp_path, monkeypatch):
    logical = TaskAttempt.create(
        run_id="replacement-run",
        benchmark_commit="9" * 40,
        task_id="T26",
        split="engineering_canary_optimize",
        checkpoint="iteration-1",
        worker_digest="a" * 64,
    )
    replacement = TaskAttempt.create(
        run_id="replacement-run",
        benchmark_commit="9" * 40,
        task_id="T26",
        split="engineering_canary_optimize",
        checkpoint="iteration-1+infra-replacement-01",
        worker_digest="a" * 64,
    )
    verifier = tmp_path / "attempts" / replacement.attempt_id / "verifier"
    verifier.mkdir(parents=True)
    evidence = {"benchmark": "quantcodeeval", "official_reward": 0.0}
    (verifier / "answer-free-evidence.json").write_text(json.dumps(evidence))
    monkeypatch.setattr(
        "qea.quantcodeeval_full_candidate.resolve_worker_attempt",
        lambda attempt, run_dir: replacement,
    )

    row = _answer_free_attempt_row(logical, tmp_path)

    assert row == {
        "task_id": "T26",
        "attempt_id": replacement.attempt_id,
        "answer_free_evidence": evidence,
    }


def test_full_candidate_rejects_failed_smoke_and_role_mismatch(tmp_path, monkeypatch):
    if not hasattr(sys, "stdlib_module_names"):
        monkeypatch.setattr(sys, "stdlib_module_names", frozenset(), raising=False)
    seed = _worker(tmp_path / "seed")
    candidate = _candidate(seed, tmp_path / "candidate")
    tasks = (SimpleNamespace(task_id="T16"), SimpleNamespace(task_id="T24"))
    snapshot = SimpleNamespace(
        commit="9" * 40,
        optimize=SimpleNamespace(task_ids=("T16", "T24"), tasks=tasks),
    )
    monkeypatch.setattr(
        "qea.quantcodeeval_full_candidate.prepare_quantcodeeval_h0",
        lambda **kwargs: (
            snapshot,
            object(),
            {
                "public_manifest_sha256": "1" * 64,
                "trusted_manifest_sha256": "2" * 64,
                "runtime_identity_sha256": "3" * 64,
            },
            seed,
        ),
    )
    common = dict(
        config_path=tmp_path / "config.json",
        public_root=tmp_path / "public",
        trusted_root=tmp_path / "trusted",
        seed_worker_dir=seed,
        parent_worker_dir=seed,
        candidate_worker_dir=candidate,
        iteration=1,
        mechanism="test",
        primary_components=("tools",),
        activation={"status": "passed"},
        worker_image_ref="sha256:" + "4" * 64,
        verifier_image_ref="sha256:" + "5" * 64,
        proxy_image_ref="sha256:" + "6" * 64,
        token_file=tmp_path / "token",
        source_h0_evaluation_id="7" * 64,
        preflight_only=True,
    )
    with pytest.raises(QuantCodeEvalFullCandidateError, match="final digest-bound"):
        run_quantcodeeval_full_candidate(
            **common,
            run_dir=tmp_path / "failed-smoke",
            declared_roles=("agent_config", "tool_descriptions", "tools"),
            component_tests=({"status": "failed"},),
        )
    with pytest.raises(QuantCodeEvalFullCandidateError, match="declared"):
        run_quantcodeeval_full_candidate(
            **common,
            run_dir=tmp_path / "role-mismatch",
            declared_roles=("tools",),
            component_tests=(
                {
                    "status": "passed",
                    "component": "tools",
                    "candidate_digest": hash_worker_directory(candidate),
                },
            ),
        )


def test_full_candidate_persists_answer_free_failure_and_reuses_it(
    tmp_path, monkeypatch
):
    if not hasattr(sys, "stdlib_module_names"):
        monkeypatch.setattr(sys, "stdlib_module_names", frozenset(), raising=False)
    seed = _worker(tmp_path / "seed")
    candidate = _candidate(seed, tmp_path / "candidate")
    task = SimpleNamespace(task_id="T16")
    snapshot = SimpleNamespace(
        commit="9" * 40,
        optimize=SimpleNamespace(task_ids=("T16",), tasks=(task,)),
    )
    calls = []

    class FailedEvaluator:
        def evaluate(self, **kwargs):
            calls.append(kwargs)
            root = Path(kwargs["run_dir"])
            attempt = root / "attempts/a1"
            attempt.mkdir(parents=True)
            (attempt / "attempt.json").write_text(
                json.dumps({"attempt_id": "a1", "task_id": "T16"})
            )
            (attempt / "proxy-audit.jsonl").write_text(
                json.dumps(
                    {
                        "request_state": "completed",
                        "failure_class": None,
                        "upstream_status_code": 200,
                        "input_tokens": 10,
                        "output_tokens": 2,
                        "total_tokens": 12,
                        "provider_cost_usd": 0.01,
                    }
                )
                + "\n"
            )
            lifecycle = root / "lifecycles/a1/worker-sandbox-lifecycle-v2.json"
            lifecycle.parent.mkdir(parents=True)
            lifecycle.write_text(
                json.dumps(
                    {
                        "task_id": "T16",
                        "failure": "output file limit exceeded: 4 > 3",
                        "cleaned_up": True,
                    }
                )
            )
            raise RuntimeError("output file limit exceeded")

    evaluator = FailedEvaluator()
    monkeypatch.setattr(
        "qea.quantcodeeval_full_candidate.prepare_quantcodeeval_h0",
        lambda **kwargs: (
            snapshot,
            evaluator,
            {
                "public_manifest_sha256": "1" * 64,
                "trusted_manifest_sha256": "2" * 64,
                "runtime_identity_sha256": "3" * 64,
            },
            seed,
        ),
    )
    digest = hash_worker_directory(candidate)
    kwargs = dict(
        config_path=tmp_path / "config.json",
        public_root=tmp_path / "public",
        trusted_root=tmp_path / "trusted",
        run_dir=tmp_path / "candidate-run",
        seed_worker_dir=seed,
        parent_worker_dir=seed,
        candidate_worker_dir=candidate,
        iteration=1,
        mechanism="validate output",
        primary_components=("tools",),
        declared_roles=("agent_config", "tool_descriptions", "tools"),
        component_tests=(
            {
                "status": "passed",
                "component": "tools",
                "candidate_digest": digest,
            },
        ),
        activation={"status": "passed"},
        worker_image_ref="sha256:" + "4" * 64,
        verifier_image_ref="sha256:" + "5" * 64,
        proxy_image_ref="sha256:" + "6" * 64,
        token_file=tmp_path / "token",
        source_h0_evaluation_id="7" * 64,
    )

    first = run_quantcodeeval_full_candidate(**kwargs)
    monkeypatch.setattr(
        "qea.quantcodeeval_full_candidate._source_sha256",
        lambda: {"coordinator.py": "updated"},
    )
    second = run_quantcodeeval_full_candidate(**kwargs)

    assert first == second
    assert len(calls) == 1
    assert first["status"] == "evaluation_failed"
    assert first["official_evaluated"] is False
    assert first["benchmark_score_claimed"] is False
    assert first["attempts"][0]["failure_class"] == "output_membership_overflow"
    assert first["partial_cost_and_lifecycle_audit"]["request_count"] == 1
    assert first["partial_cost_and_lifecycle_audit"]["provider_cost_usd"] == 0.01
    assert (tmp_path / "candidate-run/FULL-CANDIDATE-RESULT.json").is_file()


def test_legacy_failure_recovery_requires_worker_evidence_and_never_scores(tmp_path):
    root = tmp_path / "legacy-run"
    attempt = root / "attempts/a1"
    attempt.mkdir(parents=True)
    (root / "FULL-CANDIDATE-PREFLIGHT.json").write_text(
        json.dumps(
            {
                "status": "preflight_complete",
                "task_ids": ["T24"],
                "candidate_worker_digest": "1" * 64,
            }
        )
    )
    (attempt / "attempt.json").write_text(
        json.dumps({"attempt_id": "a1", "task_id": "T24"})
    )
    (attempt / "worker-artifact-contract.json").write_text(
        json.dumps({"expected_paths": ["strategy.py"], "found_paths": []})
    )
    lifecycle = root / "lifecycles/a1/worker-sandbox-lifecycle-v2.json"
    lifecycle.parent.mkdir(parents=True)
    lifecycle.write_text(
        json.dumps(
            {
                "task_id": "T24",
                "failure": "worker output membership differs",
                "cleaned_up": True,
            }
        )
    )

    result = materialize_quantcodeeval_full_candidate_failure_result(root)

    assert result["status"] == "evaluation_failed"
    assert result["recovered_from_existing_artifacts"] is True
    assert result["official_evaluated"] is False
    assert result["benchmark_score_claimed"] is False
    assert result["attempts"][0]["failure_class"] == "missing_submission_artifact"
    assert "score_summary" not in result


def test_failed_replacement_cost_includes_both_worker_attempts(tmp_path):
    from qea.quantcodeeval_full_candidate import _answer_free_failed_attempts

    root = tmp_path / "run"
    first = root / "attempts/first"
    second = root / "attempts/second"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    for directory, cost, tokens in (
        (first, 0.02, 40),
        (second, 0.03, 60),
    ):
        (directory / "attempt.json").write_text(
            json.dumps({"attempt_id": directory.name, "task_id": "T26"})
        )
        (directory / "worker-artifact-contract.json").write_text(
            json.dumps({"expected_paths": ["strategy.py"], "found_paths": []})
        )
        (directory / "proxy-audit.jsonl").write_text(
            json.dumps({
                "request_state": "completed",
                "failure_class": None,
                "upstream_status_code": 200,
                "input_tokens": tokens - 10,
                "output_tokens": 10,
                "total_tokens": tokens,
                "provider_cost_usd": cost,
            }) + "\n"
        )
    (first / "worker-attempt-replacement.json").write_text(
        json.dumps({
            "superseded_attempt_id": "first",
            "replacement_attempt_id": "second",
        })
    )

    attempts, cost = _answer_free_failed_attempts(root, ["T26"])

    assert attempts[0]["attempt_id"] == "second"
    assert attempts[0]["provider_audit"]["attempt_count"] == 2
    assert cost["request_count"] == 2
    assert cost["total_tokens"] == 100
    assert cost["provider_cost_usd"] == pytest.approx(0.05)
