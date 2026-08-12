import json
from pathlib import Path

from qea.quantcodeeval_experiment import h0_evaluation_ref, prepare_initial_pgbs


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _answer_free(task_id: str) -> dict[str, object]:
    passing = task_id == "T16"
    return {
        "schema_version": 1,
        "benchmark": "quantcodeeval",
        "official_reward": 1.0 if passing else 0.0,
        "property_families": {
            "type_a": {
                "total": 6 if passing else 7,
                "passed": 6,
                "failed": 0 if passing else 1,
                "skipped": 0,
                "errors": 0,
            },
            "type_b": {
                "total": 12 if passing else 10,
                "passed": 12 if passing else 9,
                "failed": 0 if passing else 1,
                "skipped": 0,
                "errors": 0,
            },
        },
        "diagnostic_tags": [] if passing else ["properties_incomplete"],
    }


def _fixture(tmp_path: Path) -> tuple[Path, Path]:
    h0 = tmp_path / "h0-run"
    public = tmp_path / "public-role"
    worker_digest = "4" * 64
    evaluation_id = "d" * 64
    preflight = {
        "benchmark_commit": "9" * 40,
        "checkpoint": "quantcodeeval-h0-shell-only",
        "model": "deepseek/deepseek-v4-flash-0731",
        "required_provider": "deepseek",
        "allow_fallbacks": False,
        "split": "engineering_canary_optimize",
        "runtime_identity_sha256": "1" * 64,
        "worker_image_ref": "sha256:" + "2" * 64,
        "verifier_image_ref": "sha256:" + "3" * 64,
        "proxy_image_ref": "sha256:" + "5" * 64,
        "worker_concurrency": 1,
        "verifier_concurrency": 1,
        "public_manifest_sha256": "6" * 64,
        "trusted_manifest_sha256": "7" * 64,
        "task_ids": ["T16", "T24"],
        "worker_digest": worker_digest,
    }
    _write_json(h0 / "H0-PREFLIGHT.json", preflight)
    attempts = []
    for task_id in ("T16", "T24"):
        attempt_id = ("a" if task_id == "T16" else "b") * 64
        attempts.append(
            {
                "task_id": task_id,
                "attempt_id": attempt_id,
                "answer_free_evidence": _answer_free(task_id),
            }
        )
        attempt = h0 / "attempts" / attempt_id
        (attempt / "artifacts").mkdir(parents=True)
        (attempt / "artifacts" / "strategy.py").write_text(
            "VOL_SCALING_TARGET = 5.34\n\ndef run():\n    return 0\n",
            encoding="utf-8",
        )
        (attempt / "raw-trace.jsonl").write_text(
            json.dumps({"role": "assistant"}) + "\n", encoding="utf-8"
        )
        (attempt / "final.txt").write_text("done\n", encoding="utf-8")
        _write_json(
            attempt / "worker-execution.json",
            {
                "summary": {
                    "turns": 2,
                    "tool_calls": 1,
                    "tool_errors": 0,
                    "files": 1,
                    "secs": 2.5,
                    "outcome": "completed",
                    "dependency_lock_sha256": "8" * 64,
                }
            },
        )
        task = public / "tasks" / task_id
        (task / "environment" / "data").mkdir(parents=True)
        instruction = [f"line {index}" for index in range(1, 70)]
        instruction[55] = "### R3: Constant volatility scaling"
        instruction[58] = "The target is one paper-specified fixed constant."
        (task / "instruction.md").write_text(
            "\n".join(instruction) + "\n", encoding="utf-8"
        )
        (task / "environment" / "data" / "paper_text.md").write_text(
            "The aggregate market volatility is 5.34% per month.\n",
            encoding="utf-8",
        )
    _write_json(
        h0 / "H0-RESULT.json",
        {
            "status": "complete",
            "resampled": True,
            "evaluation_identity_sha256": evaluation_id,
            "attempts": attempts,
        },
    )
    return h0, public


def test_prepare_initial_pgbs_reuses_h0_and_records_answer_free_act(tmp_path):
    h0, public = _fixture(tmp_path)
    master = tmp_path / "qce-pgbs-test"

    result = prepare_initial_pgbs(
        master_run_dir=master,
        h0_run_dir=h0,
        public_task_roots={
            task_id: public / "tasks" / task_id for task_id in ("T16", "T24")
        },
    )

    evaluation = h0_evaluation_ref(h0)
    assert result["status"] == "preflight_complete"
    assert result["h0_resampled_by_search"] is False
    assert result["model_request_count"] == 0
    assert result["decision"]["decision"] == "ACT"
    assert result["decision"]["failure_class"] == "quant_definition_estimation"
    assert evaluation.task_results["T16"].official_reward == 1.0
    assert evaluation.task_results["T24"].type_a.passed == 6
    state = json.loads((master / "STATE.json").read_text())
    assert state["iterations"] == []
    evidence_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (master / "evidence" / "iteration-01").rglob("*")
        if path.is_file()
    )
    assert "VOL_SCALING_TARGET = 5.34" not in evidence_text
    assert "golden_ref" not in evidence_text
