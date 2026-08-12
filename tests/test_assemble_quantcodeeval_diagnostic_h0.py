import json
from pathlib import Path

from scripts.assemble_quantcodeeval_diagnostic_h0 import main


def _run(root: Path, name: str, tasks: dict[str, tuple[float, dict]]) -> Path:
    run = root / name
    (run / "attempts").mkdir(parents=True)
    task_ids = list(tasks)
    (run / "H0-PREFLIGHT.json").write_text(
        json.dumps({"task_ids": task_ids}), encoding="utf-8"
    )
    attempts = []
    scores = []
    for task_id, (reward, evidence) in tasks.items():
        attempt_id = f"attempt-{task_id}"
        (run / "attempts" / attempt_id).mkdir()
        attempts.append(
            {
                "task_id": task_id,
                "attempt_id": attempt_id,
                "answer_free_evidence": evidence,
            }
        )
        scores.append({"task_id": task_id, "domain": task_id, "reward": reward})
    result = {
        "runtime_identity_sha256": "runtime",
        "attempts": attempts,
        "score_summary": {"scores": scores},
        "cost_audit": {
            "attempt_count": len(tasks),
            "completed_request_count": len(tasks),
            "input_tokens": 1,
            "logical_request_count": len(tasks),
            "other_nonaccepted_request_count": 0,
            "output_tokens": 1,
            "rate_limited_retry_count": 0,
            "request_count": len(tasks),
            "superseded_attempt_count": 0,
            "total_tokens": 2,
            "unreconciled_attempt_count": 0,
            "unreconciled_request_count": 0,
            "provider_cost_usd": "0.0100000000",
            "cost_complete": True,
        },
        "route_evidence": {"requests": [], "generation_metadata": []},
    }
    (run / "H0-RESULT.json").write_text(json.dumps(result), encoding="utf-8")
    return run


def _evidence(passed: int, total: int) -> dict:
    family = {"passed": passed, "failed": total - passed, "errors": 0, "skipped": 0, "total": total}
    return {"property_families": {"type_a": family, "type_b": family}}


def test_stitches_retry_evidence_and_accounting(tmp_path):
    base = _run(tmp_path, "base", {"T01": (0.0, _evidence(0, 1)), "T18": (0.0, {})})
    retry = _run(tmp_path, "retry", {"T18": (1.0, _evidence(1, 1))})
    output = tmp_path / "stitched"

    assert main(["--base-run", str(base), "--replacement-run", str(retry), "--output-run", str(output)]) == 0

    result = json.loads((output / "H0-RESULT.json").read_text())
    assert result["score_summary"]["task_rewards"] == {"T01": 0.0, "T18": 1.0}
    assert result["cost_audit"]["request_count"] == 3
    assert result["diagnostic_sources"]["replacements"][0]["task_ids"] == ["T18"]
    assert (output / "attempts/attempt-T18").is_dir()
