import json
from collections import Counter
from pathlib import Path
import subprocess
import sys

import pytest


def _write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def _make_completed_run(
    root: Path,
    *,
    arm: str,
    optimize_final: float,
    attempt_limit: int = 140,
    admission_digest: str = "admission-same",
    held_out_seed: float = 0.5,
    held_out_final: float = 0.51,
) -> Path:
    run = root / f"run-{arm}"
    final_worker = run / "workers" / "iteration-05-candidate"
    final_worker.mkdir(parents=True)
    (final_worker / "systemprompt.md").write_text("final worker\n")
    identity = {
        "arm": arm,
        "benchmark_commit": "0" * 40,
        "task_manifest_digest": "manifest-same",
        "feedback_contract_digest": f"feedback-{arm}",
        "public_rubric_digest": "rubric-same",
        "verifier_mapping_digest": "mapping-same",
        "admission_policy_digest": admission_digest,
        "model_identity": "model-same",
        "seed_digest": "seed-same",
        "template_identity_digest": "templates-same",
    }
    records = [
        {
            "iteration": index,
            "edit_signature": f"edit-{index}",
            "candidate_worker_digest": f"candidate-{index}",
            "incumbent_before": 0.2 + (index - 1) * 0.02,
            "candidate_overall": 0.2 + index * 0.02,
            "incumbent_after": 0.2 + index * 0.02,
            "kept": True,
            "reason": "gain",
            "domain_deltas": {"risk": 0.02},
            "admitted": True,
            "admission_failure": None,
            "evidence_digest": f"evidence-{index}",
        }
        for index in range(1, 6)
    ]
    task_rewards = {f"opt-{index:02d}": optimize_final for index in range(20)}
    optimize_summary = {
        "scores": [],
        "task_rewards": task_rewards,
        "domain_scores": {"risk": optimize_final},
        "task_mean": optimize_final,
        "overall": optimize_final,
    }
    held_out_task_ids = [f"hold-{index:02d}" for index in range(10)]

    def held_out_summary(reward: float) -> dict:
        return {
            "scores": [],
            "task_rewards": {task_id: reward for task_id in held_out_task_ids},
            "domain_scores": {"fx": reward},
            "task_mean": reward,
            "overall": reward,
        }

    _write(run / "resume.json", {
        "schema_version": 2,
        "run_id": run.name,
        "arm": arm,
        "n_iters": 5,
        "benchmark_commit": "0" * 40,
        "identity": identity,
        "phase": "complete",
        "next_iteration": 6,
        "incumbent_worker": "workers/iteration-05-candidate",
        "records": records,
        "pending_candidate": None,
        "costs": [{"iteration": index, "model_usage": {"total_tokens": 1000}}
                  for index in range(1, 6)],
    })
    _write(run / "result.json", {
        "schema_version": 2,
        "run_id": run.name,
        "arm": arm,
        "identity": identity,
        "records": records,
        "optimize_trajectory": [0.2, 0.22, 0.24, 0.26, 0.28, optimize_final],
        "optimize_final": optimize_summary,
        "held_out_seed": held_out_summary(held_out_seed),
        "held_out_final": held_out_summary(held_out_final),
        "final_worker_dir": str(final_worker.resolve()),
    })

    attempts = []
    for task_index in range(20):
        attempts.append((f"opt-{task_index:02d}", "optimize", "seed-optimize"))
    for iteration in range(1, 6):
        for task_index in range(20):
            attempts.append((
                f"opt-{task_index:02d}",
                "optimize",
                f"iteration-{iteration}-candidate",
            ))
    for checkpoint in ("seed-held-out", "final-held-out"):
        for task_index in range(10):
            attempts.append((f"hold-{task_index:02d}", "held_out", checkpoint))
    for attempt_index, (task_id, split, checkpoint) in enumerate(
        attempts[:attempt_limit]
    ):
        attempt_id = f"attempt-{attempt_index:03d}"
        attempt = run / "attempts" / attempt_id
        _write(attempt / "attempt.json", {
            "attempt_id": attempt_id,
            "task_id": task_id,
            "split": split,
            "checkpoint": checkpoint,
        })
        reward = optimize_final
        if checkpoint == "seed-held-out":
            reward = held_out_seed
        elif checkpoint == "final-held-out":
            reward = held_out_final
        _write(attempt / "completed-score.json", {
            "task_id": task_id,
            "domain": "risk" if split == "optimize" else "fx",
            "reward": reward,
            "diagnostic_tags": [],
        })
        for role, path in (
            ("worker", attempt / "worker-sandbox-lifecycle.json"),
            ("verifier", attempt / "verifier" / "verifier-sandbox-lifecycle.json"),
        ):
            _write(path, {
                "schema_version": 1,
                "role": role,
                "sandbox_id": f"{role}-{attempt_id}",
                "cleaned_up": True,
            })
    for iteration in range(1, 6):
        evolution = run / "evolutions" / f"iteration-{iteration:04d}"
        _write(evolution / f"evolver-{iteration}-sandbox-lifecycle.json", {
            "schema_version": 1,
            "role": "evolver",
            "sandbox_id": f"evolver-{iteration}",
            "cleaned_up": True,
        })
        _write(evolution / "access-summary.json", {
            "records": iteration,
            "operations": {"read": iteration},
            "evidence_paths": ["contract.json"],
        })
        _write(evolution / "summary.json", {
            "tool_errors": 0,
            "model_usage": {"total_tokens": 1000},
        })
        edit = run / f"iteration-{iteration:02d}" / "edit.diff"
        edit.parent.mkdir(parents=True)
        edit.write_text("+++ b/systemprompt.md\n+validate artifacts\n")
    return run


def _make_historical_run(root: Path) -> Path:
    run = root / "qfbench-30x5-20260725"
    _write(run / "result.json", {
        "run_id": run.name,
        "optimize_trajectory": [0.5],
        "optimize_final": {"overall": 0.5},
    })
    _write(run / "validity-audit.json", {
        "schema_version": 1,
        "run_id": run.name,
        "score_validity": {
            "status": "provisional",
            "affected_attempts": 14,
            "affected_tasks": {
                "delta-hedging-pnl-simulation": 6,
                "form4-cross-sectional-sale-pressure": 2,
                "swap-curve-bootstrap-ois": 6,
            },
        },
    })
    checkpoints = [
        "seed-optimize",
        *[f"iteration-{index}-candidate" for index in range(1, 6)],
        "seed-held-out",
        "final-held-out",
    ]
    counter = 0
    for checkpoint in checkpoints:
        split = "held_out" if "held-out" in checkpoint else "optimize"
        task_ids = (
            ["form4-cross-sectional-sale-pressure"]
            if split == "held_out"
            else [
                "delta-hedging-pnl-simulation",
                "swap-curve-bootstrap-ois",
            ]
        )
        scores = []
        for task_id in task_ids:
            attempt_id = f"historical-{counter:02d}"
            counter += 1
            (run / "attempts" / attempt_id).mkdir(parents=True)
            scores.append({
                "task_id": task_id,
                "domain": "data_engineering" if split == "held_out" else "derivatives",
                "reward": 0.0,
                "tests_passed": 0,
                "tests_failed": 0,
                "diagnostic_tags": [],
                "log_uri": str(
                    run / "attempts" / attempt_id / "verifier" / "verifier-command.trusted.json"
                ),
            })
        _write(run / "evaluations" / f"{checkpoint}.json", {
            "run_id": run.name,
            "checkpoint": checkpoint,
            "split": split,
            "summary": {"scores": scores},
        })
    return run


def test_comparison_audits_30x5_and_computes_rich_feedback_gain(tmp_path):
    from scripts.compare_qfbench_feedback_ab import _markdown, compare_runs

    control = _make_completed_run(
        tmp_path, arm="control", optimize_final=0.30
    )
    rich = _make_completed_run(tmp_path, arm="rich", optimize_final=0.38)

    comparison = compare_runs(control, rich)

    assert comparison["completion"]["control"]["official_scores"] == 140
    assert comparison["completion"]["rich"]["official_scores"] == 140
    assert comparison["primary"]["RichFeedbackGain"] == pytest.approx(0.08)
    assert comparison["arms"]["rich"]["evidence_read_records"] == 15
    assert comparison["arms"]["control"]["edit_categories"]["prompt"] == 5
    assert comparison["arms"]["control"]["held_out_seed"] == pytest.approx(0.5)
    assert comparison["arms"]["control"]["held_out_final"] == pytest.approx(0.51)
    assert comparison["arms"]["control"]["held_out_delta"] == pytest.approx(0.01)
    markdown = _markdown(comparison)
    assert "| Held-out seed | 0.500000 | 0.500000 |" in markdown
    assert "| Held-out delta | 0.010000 | 0.010000 |" in markdown
    assert comparison["causal_comparison"] is True


@pytest.mark.parametrize(
    ("replacement", "message"),
    [
        (0.52, "held-out final summary overall mismatch"),
        (float("nan"), "held-out final summary overall"),
        (1.2, "held-out final summary overall"),
    ],
)
def test_comparison_refuses_invalid_or_unreconciled_held_out_summary(
    tmp_path, replacement, message
):
    from scripts.compare_qfbench_feedback_ab import ComparisonError, compare_runs

    control = _make_completed_run(tmp_path, arm="control", optimize_final=0.30)
    rich = _make_completed_run(tmp_path, arm="rich", optimize_final=0.38)
    result_path = control / "result.json"
    result = json.loads(result_path.read_text())
    result["held_out_final"]["overall"] = replacement
    _write(result_path, result)

    with pytest.raises(ComparisonError, match=message):
        compare_runs(control, rich)


def test_comparison_enumerates_historical_contamination_from_validity_audit(
    tmp_path,
):
    from scripts.compare_qfbench_feedback_ab import ComparisonError, compare_runs

    control = _make_completed_run(tmp_path, arm="control", optimize_final=0.30)
    rich = _make_completed_run(tmp_path, arm="rich", optimize_final=0.38)
    historical = _make_historical_run(tmp_path)

    comparison = compare_runs(control, rich, historical)
    contamination = comparison["historical"]
    assert contamination["contaminated_record_count"] == 14
    assert len(contamination["contaminated_records"]) == 14
    assert Counter(
        record["task_id"] for record in contamination["contaminated_records"]
    ) == {
        "delta-hedging-pnl-simulation": 6,
        "form4-cross-sectional-sale-pressure": 2,
        "swap-curve-bootstrap-ois": 6,
    }

    validity_path = historical / "validity-audit.json"
    validity = json.loads(validity_path.read_text())
    validity["score_validity"]["affected_attempts"] = 13
    _write(validity_path, validity)
    with pytest.raises(ComparisonError, match="affected attempt count"):
        compare_runs(control, rich, historical)


def test_comparison_refuses_incomplete_or_identity_mismatched_runs(tmp_path):
    from scripts.compare_qfbench_feedback_ab import ComparisonError, compare_runs

    incomplete = _make_completed_run(
        tmp_path / "incomplete",
        arm="control",
        optimize_final=0.30,
        attempt_limit=139,
    )
    rich = _make_completed_run(
        tmp_path / "incomplete", arm="rich", optimize_final=0.38
    )
    with pytest.raises(ComparisonError, match="140"):
        compare_runs(incomplete, rich)

    control = _make_completed_run(
        tmp_path / "mismatch", arm="control", optimize_final=0.30
    )
    mismatched = _make_completed_run(
        tmp_path / "mismatch",
        arm="rich",
        optimize_final=0.38,
        admission_digest="different-policy",
    )
    with pytest.raises(ComparisonError, match="identity mismatch"):
        compare_runs(control, mismatched)


def test_comparison_script_is_directly_invokable():
    proc = subprocess.run(
        [sys.executable, "scripts/compare_qfbench_feedback_ab.py", "--help"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "--control" in proc.stdout
    assert "--rich" in proc.stdout
    assert "--historical" in proc.stdout
