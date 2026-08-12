import shutil
import sys
import json
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

from qea.evaluation import OfficialTaskScore, TaskAttempt
from qea.quantcodeeval_candidate import (
    recover_quantcodeeval_candidate_artifact_zero,
    run_quantcodeeval_candidate,
)


def _worker(root: Path) -> Path:
    source = Path(__file__).resolve().parents[1] / "qea" / "worker_gdpval_weak"
    shutil.copytree(source, root)
    return root


def test_candidate_preflight_keeps_worker_and_admission_digests_distinct(
    tmp_path, monkeypatch
):
    if not hasattr(sys, "stdlib_module_names"):
        monkeypatch.setattr(sys, "stdlib_module_names", frozenset(), raising=False)
    seed = _worker(tmp_path / "seed")
    snapshot = SimpleNamespace(
        commit="9" * 40,
        optimize=SimpleNamespace(task_ids=("T16", "T24")),
    )
    preflight = {
        "public_manifest_sha256": "1" * 64,
        "trusted_manifest_sha256": "2" * 64,
        "runtime_identity_sha256": "3" * 64,
    }

    def fake_prepare(**kwargs):
        return snapshot, object(), preflight, seed

    monkeypatch.setattr(
        "qea.quantcodeeval_candidate.prepare_quantcodeeval_h0", fake_prepare
    )
    result = run_quantcodeeval_candidate(
        config_path=tmp_path / "config.json",
        public_root=tmp_path / "public",
        trusted_root=tmp_path / "trusted",
        run_dir=tmp_path / "candidate-run",
        seed_worker_dir=seed,
        parent_worker_dir=seed,
        failure_class="quant_definition_estimation",
        iteration=1,
        worker_image_ref="sha256:" + "4" * 64,
        verifier_image_ref="sha256:" + "5" * 64,
        proxy_image_ref="sha256:" + "6" * 64,
        token_file=tmp_path / "token",
        source_h0_evaluation_id="7" * 64,
        preflight_only=True,
    )

    assert result["status"] == "preflight_complete"
    assert result["candidate_coordinator_source_sha256"][
        "quantcodeeval_candidate.py"
    ]
    assert result["admission"]["admitted"] is True
    assert result["candidate_worker_digest"] == result["mutation"]["candidate_digest"]
    assert result["candidate_admission_manifest_digest"] == result["admission"][
        "candidate_digest"
    ]
    assert result["candidate_worker_digest"] != result[
        "candidate_admission_manifest_digest"
    ]

    resumed = run_quantcodeeval_candidate(
        config_path=tmp_path / "config.json",
        public_root=tmp_path / "public",
        trusted_root=tmp_path / "trusted",
        run_dir=tmp_path / "candidate-run",
        seed_worker_dir=seed,
        parent_worker_dir=seed,
        failure_class="quant_definition_estimation",
        iteration=1,
        worker_image_ref="sha256:" + "4" * 64,
        verifier_image_ref="sha256:" + "5" * 64,
        proxy_image_ref="sha256:" + "6" * 64,
        token_file=tmp_path / "token",
        source_h0_evaluation_id="7" * 64,
        preflight_only=True,
    )
    assert resumed == result


def test_recover_artifact_zero_marks_all_properties_skipped_without_resample(
    tmp_path, monkeypatch
):
    run = tmp_path / "candidate-recovery"
    run.mkdir()
    worker_digest = "4" * 64
    commit = "9" * 40
    plan = {
        "schema_version": 1,
        "protocol": "quant_property_v1_candidate",
        "status": "preflight_complete",
        "run_id": run.name,
        "checkpoint": "quantcodeeval-pgbs-iteration-01",
        "candidate_worker_digest": worker_digest,
        "panel_identity_sha256": "1" * 64,
        "sampling_identity_sha256": "2" * 64,
        "task_ids": ["T16", "T24"],
        "model_request_count": 0,
    }
    (run / "CANDIDATE-PREFLIGHT.json").write_text(json.dumps(plan))
    (run / "H0-PREFLIGHT.json").write_text(
        json.dumps({"benchmark_commit": commit})
    )
    h0 = tmp_path / "h0"
    h0.mkdir()

    def evidence(task_id, a_total, b_total, passing):
        return {
            "schema_version": 1,
            "benchmark": "quantcodeeval",
            "official_reward": 1.0 if passing else 0.0,
            "property_families": {
                "type_a": {
                    "total": a_total,
                    "passed": a_total if passing else a_total - 1,
                    "failed": 0 if passing else 1,
                    "skipped": 0,
                    "errors": 0,
                },
                "type_b": {
                    "total": b_total,
                    "passed": b_total if passing else b_total - 1,
                    "failed": 0 if passing else 1,
                    "skipped": 0,
                    "errors": 0,
                },
            },
            "diagnostic_tags": [] if passing else ["properties_incomplete"],
        }

    h0_attempts = [
        {"task_id": "T16", "answer_free_evidence": evidence("T16", 6, 12, True)},
        {"task_id": "T24", "answer_free_evidence": evidence("T24", 7, 10, False)},
    ]
    (h0 / "H0-RESULT.json").write_text(json.dumps({"attempts": h0_attempts}))
    for task_id in ("T16", "T24"):
        attempt = TaskAttempt.create(
            run_id=run.name,
            benchmark_commit=commit,
            task_id=task_id,
            split="engineering_canary_optimize",
            checkpoint=plan["checkpoint"],
            worker_digest=worker_digest,
        )
        attempt_dir = run / "attempts" / attempt.attempt_id
        attempt_dir.mkdir(parents=True)
        if task_id == "T16":
            score = OfficialTaskScore(
                task_id="T16", domain="volatility", reward=1.0
            )
            (attempt_dir / "completed-score.json").write_text(
                json.dumps(asdict(score))
            )
            verifier = attempt_dir / "verifier"
            verifier.mkdir()
            (verifier / "answer-free-evidence.json").write_text(
                json.dumps(h0_attempts[0]["answer_free_evidence"])
            )
        else:
            trace = attempt_dir / "raw-trace.jsonl"
            final = attempt_dir / "final.txt"
            trace.write_text("{}\n")
            final.write_text("maximum iterations reached\n")
            (attempt_dir / "worker-command.json").write_text(
                json.dumps(
                    {"exit_code": 0, "stdout": "", "stderr": "", "timed_out": False}
                )
            )
            (attempt_dir / "worker-artifact-contract.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "outcome": "official_worker_artifact_contract_zero",
                        "expected_paths": ["strategy.py"],
                        "found_paths": [],
                        "artifact_records": [],
                        "trace_uri": str(trace.resolve()),
                        "final_text_uri": str(final.resolve()),
                    }
                )
            )
            (attempt_dir / "completed-score.json").write_text(
                json.dumps(
                    asdict(
                        OfficialTaskScore(
                            task_id="T24",
                            domain="event_strategy",
                            reward=0.0,
                            diagnostic_tags=("missing_artifact",),
                            log_uri=str((attempt_dir / "raw-trace.jsonl").resolve()),
                        )
                    )
                )
            )

    monkeypatch.setattr(
        "qea.quantcodeeval_candidate.audit_fixed_checkpoint_proxy_costs",
        lambda *args, **kwargs: {"request_count": 68},
    )
    monkeypatch.setattr(
        "qea.quantcodeeval_candidate._route_evidence",
        lambda *args, **kwargs: {"required_provider": "deepseek"},
    )
    result = recover_quantcodeeval_candidate_artifact_zero(
        run_dir=run, source_h0_run_dir=h0, token_file=tmp_path / "token"
    )

    assert result["worker_behavior_zero_tasks"] == ["T24"]
    assert result["model_request_count"] == 68
    t24 = next(row for row in result["attempts"] if row["task_id"] == "T24")
    assert t24["answer_free_evidence"]["property_families"]["type_a"] == {
        "total": 7,
        "passed": 0,
        "failed": 0,
        "skipped": 7,
        "errors": 0,
    }
    assert recover_quantcodeeval_candidate_artifact_zero(
        run_dir=run, source_h0_run_dir=h0, token_file=tmp_path / "token"
    ) == result
