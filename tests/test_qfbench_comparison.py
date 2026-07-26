import json
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
    summary = {
        "scores": [],
        "task_rewards": task_rewards,
        "domain_scores": {"risk": optimize_final},
        "task_mean": optimize_final,
        "overall": optimize_final,
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
        "optimize_final": summary,
        "held_out_seed": {**summary, "overall": 0.5},
        "held_out_final": {**summary, "overall": 0.51},
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
        _write(attempt / "completed-score.json", {
            "task_id": task_id,
            "domain": "risk" if split == "optimize" else "fx",
            "reward": optimize_final if split == "optimize" else 0.5,
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


def test_comparison_audits_30x5_and_computes_rich_feedback_gain(tmp_path):
    from scripts.compare_qfbench_feedback_ab import compare_runs

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
    assert comparison["causal_comparison"] is True


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
