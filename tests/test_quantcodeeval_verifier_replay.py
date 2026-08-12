import json
from pathlib import Path


def test_contract_adjusted_replay_uses_saved_strategy_only(tmp_path):
    from qea.evaluation import TaskAttempt
    from scripts.replay_quantcodeeval_verifier import _replay_execution

    attempt = TaskAttempt.create(
        run_id="source-run",
        benchmark_commit="9" * 40,
        task_id="T18",
        split="engineering_canary_optimize",
        checkpoint="h0",
        worker_digest="8" * 64,
    )
    attempt_dir = tmp_path / "attempts" / attempt.attempt_id
    artifacts = attempt_dir / "artifacts"
    artifacts.mkdir(parents=True)
    (artifacts / "strategy.py").write_text("VALUE = 1\n")
    (artifacts / "output").mkdir()
    (artifacts / "output/metrics.json").write_text("{}\n")
    (attempt_dir / "worker-artifact-contract.json").write_text(json.dumps({
        "outcome": "official_worker_artifact_contract_zero",
    }))

    execution, adjusted = _replay_execution(attempt, tmp_path)

    assert adjusted is True
    assert [record.path for record in execution.artifacts] == ["strategy.py"]
    assert execution.summary == {"contract_adjusted_replay": True}
