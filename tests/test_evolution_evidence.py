import json
from pathlib import Path
from types import SimpleNamespace


def _task(tmp_path: Path, task_id: str):
    root = tmp_path / "tasks" / task_id
    data = root / "environment" / "data"
    data.mkdir(parents=True)
    (root / "instruction.md").write_text(
        f"Solve public task {task_id} using the supplied public input.\n"
    )
    (data / "input.csv").write_text("x,y\n1,2\n")
    return SimpleNamespace(
        task_id=task_id,
        root=root,
        instruction_path=root / "instruction.md",
        worker_files=(root / "instruction.md", data / "input.csv"),
    )


def _attempt(
    run_dir: Path,
    *,
    task_id: str,
    split: str,
    checkpoint: str,
    private_canary: str = "PRIVATE_VERIFIER_CANARY",
):
    attempt_dir = run_dir / "attempts" / f"attempt-{task_id}-{checkpoint}"
    artifacts = attempt_dir / "artifacts"
    verifier = attempt_dir / "verifier"
    artifacts.mkdir(parents=True)
    verifier.mkdir()
    attempt = {
        "run_id": "run-1",
        "benchmark_commit": "0" * 40,
        "task_id": task_id,
        "split": split,
        "checkpoint": checkpoint,
        "worker_digest": "1" * 64,
        "attempt_id": attempt_dir.name,
    }
    (attempt_dir / "attempt.json").write_text(json.dumps(attempt))
    (attempt_dir / "raw-trace.jsonl").write_text(
        json.dumps({"role": "assistant", "content": f"worked on {task_id}"}) + "\n"
    )
    (attempt_dir / "final.txt").write_text(f"final deliverable for {task_id}\n")
    (attempt_dir / "summary.json").write_text(json.dumps({
        "turns": 3, "tool_calls": 2, "tool_errors": 0, "files": 1,
    }))
    (artifacts / "result.json").write_text(json.dumps({"task": task_id, "value": 7}))
    (attempt_dir / "worker-execution.json").write_text(json.dumps({
        "attempt_id": attempt_dir.name,
        "artifact_dir": "artifacts",
        "artifacts": [],
        "trace_uri": "raw-trace.jsonl",
        "log_uri": "worker-command.json",
        "final_text_uri": "final.txt",
        "summary": {"turns": 3, "tool_calls": 2, "tool_errors": 0, "files": 1},
        "sandbox_id": "worker-sandbox",
        "cleaned_up": True,
    }))
    (attempt_dir / "completed-score.json").write_text(json.dumps({
        "task_id": task_id,
        "domain": "risk",
        "reward": 0.25,
        "diagnostic_tags": ["tests_failed"],
        "verifier_exit_code": 1,
        "tests_passed": 1,
        "tests_failed": 1,
        "log_uri": str(verifier / "private-command.json"),
    }))
    (verifier / "ctrf.json").write_text(json.dumps({
        "results": {
            "tests": [{
                "name": f"test_outputs.py::test_schema_{private_canary}",
                "status": "failed",
                "message": "expected 123.456, got 7",
            }]
        }
    }))
    return attempt_dir


def _contracts():
    from qea.evolution_feedback import (
        PublicCriterion,
        PublicTaskRubric,
        VerifierCriterionRule,
    )

    rubric = PublicTaskRubric(
        task_id="optimize-1",
        criteria=(PublicCriterion(
            "deliverables",
            "Produce the requested public deliverables.",
            "schema_or_structure_mismatch",
        ),),
    )
    mapping = (
        VerifierCriterionRule("*schema*", "deliverables"),
    )
    return {"optimize-1": rubric}, {"optimize-1": mapping}


def _all_text(root: Path) -> str:
    chunks = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            chunks.append(path.read_text())
        except UnicodeDecodeError:
            pass
    return "\n".join(chunks)


def test_rich_corpus_contains_optimize_trace_artifacts_and_public_feedback(tmp_path):
    from qea.evolution_evidence import build_evolution_evidence
    from qea.evolution_feedback import FeedbackMode

    run_dir = tmp_path / "run"
    optimize = _task(tmp_path, "optimize-1")
    _attempt(
        run_dir,
        task_id="optimize-1",
        split="optimize",
        checkpoint="seed-optimize",
    )
    feedback, mapping = _contracts()

    record = build_evolution_evidence(
        mode=FeedbackMode.RICH,
        optimize_tasks=(optimize,),
        held_out_task_ids={"holdout-secret"},
        run_dir=run_dir,
        destination=tmp_path / "evidence",
        feedback_manifest=feedback,
        verifier_mapping=mapping,
        history=({"iteration": 1, "kept": False},),
    )

    task_root = record.root / "tasks/optimize-1"
    attempt_root = task_root / "attempts/seed-optimize"
    assert (task_root / "instruction.md").is_file()
    assert (task_root / "environment/data/input.csv").is_file()
    assert (task_root / "public_rubric.json").is_file()
    assert (attempt_root / "worker_trace.jsonl").is_file()
    assert (attempt_root / "worker_final.txt").is_file()
    assert (attempt_root / "process_summary.json").is_file()
    assert (attempt_root / "artifacts/result.json").is_file()
    public_eval = json.loads((attempt_root / "public_evaluation.json").read_text())
    assert public_eval["official_reward"] == 0.25
    assert public_eval["criterion_results"][0]["criterion_id"] == "deliverables"
    assert public_eval["criterion_results"][0]["status"] == "failed"
    assert len(record.sha256) == 64
    assert record.members == tuple(sorted(record.members))


def test_rich_corpus_records_completed_worker_timeout_without_execution_manifest(
    tmp_path,
):
    from qea.evolution_evidence import build_evolution_evidence
    from qea.evolution_feedback import FeedbackMode

    run_dir = tmp_path / "run"
    optimize = _task(tmp_path, "optimize-1")
    attempt_dir = _attempt(
        run_dir,
        task_id="optimize-1",
        split="optimize",
        checkpoint="seed-optimize",
    )
    (attempt_dir / "worker-execution.json").unlink()
    (attempt_dir / "completed-score.json").write_text(json.dumps({
        "task_id": "optimize-1",
        "domain": "risk",
        "reward": 0.0,
        "diagnostic_tags": ["timeout"],
        "tests_passed": None,
        "tests_failed": None,
    }))
    feedback, mapping = _contracts()

    record = build_evolution_evidence(
        mode=FeedbackMode.RICH,
        optimize_tasks=(optimize,),
        held_out_task_ids={"holdout-secret"},
        run_dir=run_dir,
        destination=tmp_path / "evidence",
        feedback_manifest=feedback,
        verifier_mapping=mapping,
        history=(),
    )

    attempt_root = record.root / "tasks/optimize-1/attempts/seed-optimize"
    public_eval = json.loads((attempt_root / "public_evaluation.json").read_text())
    assert public_eval["official_reward"] == 0.0
    assert public_eval["diagnostic_tags"] == ["timeout"]
    assert public_eval["criterion_results"] == []
    assert not (attempt_root / "worker_trace.jsonl").exists()
    assert not (attempt_root / "worker_final.txt").exists()
    assert not (attempt_root / "process_summary.json").exists()
    assert not (attempt_root / "artifacts").exists()


def test_evidence_corpus_never_contains_heldout_or_private_verifier_material(tmp_path):
    from qea.evolution_evidence import build_evolution_evidence
    from qea.evolution_feedback import FeedbackMode

    run_dir = tmp_path / "run"
    optimize = _task(tmp_path, "optimize-1")
    _task(tmp_path, "holdout-secret")
    _attempt(
        run_dir,
        task_id="optimize-1",
        split="optimize",
        checkpoint="seed-optimize",
    )
    _attempt(
        run_dir,
        task_id="holdout-secret",
        split="held_out",
        checkpoint="seed-held-out",
        private_canary="HELDOUT_PRIVATE_CANARY",
    )
    feedback, mapping = _contracts()

    record = build_evolution_evidence(
        mode=FeedbackMode.RICH,
        optimize_tasks=(optimize,),
        held_out_task_ids={"holdout-secret"},
        run_dir=run_dir,
        destination=tmp_path / "evidence",
        feedback_manifest=feedback,
        verifier_mapping=mapping,
        history=(),
    )
    text = _all_text(record.root)

    assert "holdout-secret" not in text
    assert "HELDOUT_PRIVATE_CANARY" not in text
    assert "PRIVATE_VERIFIER_CANARY" not in text
    assert "123.456" not in text
    assert "private-command.json" not in text


def test_evidence_corpus_skips_validation_test_and_diagnostic_splits(tmp_path):
    from qea.evolution_evidence import build_evolution_evidence
    from qea.evolution_feedback import FeedbackMode

    run_dir = tmp_path / "run"
    optimize = _task(tmp_path, "optimize-1")
    _attempt(
        run_dir,
        task_id="optimize-1",
        split="optimize",
        checkpoint="seed-optimize",
    )
    forbidden = {
        "validation-secret": "validation",
        "test-secret": "test",
        "diagnostic-secret": "diagnostic",
    }
    for task_id, split in forbidden.items():
        _attempt(
            run_dir,
            task_id=task_id,
            split=split,
            checkpoint=f"seed-{split}",
            private_canary=f"{split.upper()}_PRIVATE_CANARY",
        )
    feedback, mapping = _contracts()

    record = build_evolution_evidence(
        mode=FeedbackMode.RICH,
        optimize_tasks=(optimize,),
        held_out_task_ids=set(forbidden),
        run_dir=run_dir,
        destination=tmp_path / "evidence",
        feedback_manifest=feedback,
        verifier_mapping=mapping,
        history=(),
    )
    text = _all_text(record.root)

    assert all(task_id not in text for task_id in forbidden)
    assert "VALIDATION_PRIVATE_CANARY" not in text
    assert "TEST_PRIVATE_CANARY" not in text
    assert "DIAGNOSTIC_PRIVATE_CANARY" not in text


def test_control_corpus_excludes_public_task_trace_artifact_and_rubric(tmp_path):
    from qea.evolution_evidence import build_evolution_evidence
    from qea.evolution_feedback import FeedbackMode

    run_dir = tmp_path / "run"
    optimize = _task(tmp_path, "optimize-1")
    _attempt(
        run_dir,
        task_id="optimize-1",
        split="optimize",
        checkpoint="seed-optimize",
    )
    feedback, mapping = _contracts()

    record = build_evolution_evidence(
        mode=FeedbackMode.CONTROL,
        optimize_tasks=(optimize,),
        held_out_task_ids={"holdout-secret"},
        run_dir=run_dir,
        destination=tmp_path / "evidence",
        feedback_manifest=feedback,
        verifier_mapping=mapping,
        history=(),
    )

    assert (record.root / "contract.json").is_file()
    assert (record.root / "feedback/task_scores.json").is_file()
    assert (record.root / "history/iterations.json").is_file()
    assert not (record.root / "tasks").exists()
    text = _all_text(record.root)
    assert "Solve public task" not in text
    assert "worked on optimize-1" not in text
    assert "final deliverable" not in text
    assert "Produce the requested public deliverables" not in text


def test_rejects_attempt_that_claims_optimize_for_an_unknown_task(tmp_path):
    import pytest

    from qea.evolution_evidence import EvidenceContractError, build_evolution_evidence
    from qea.evolution_feedback import FeedbackMode

    run_dir = tmp_path / "run"
    optimize = _task(tmp_path, "optimize-1")
    _attempt(
        run_dir,
        task_id="unknown-optimize",
        split="optimize",
        checkpoint="seed-optimize",
    )
    feedback, mapping = _contracts()

    with pytest.raises(EvidenceContractError, match="unknown optimize task"):
        build_evolution_evidence(
            mode=FeedbackMode.RICH,
            optimize_tasks=(optimize,),
            held_out_task_ids={"holdout-secret"},
            run_dir=run_dir,
            destination=tmp_path / "evidence",
            feedback_manifest=feedback,
            verifier_mapping=mapping,
            history=(),
        )


def test_rejects_history_that_mentions_heldout_task(tmp_path):
    import pytest

    from qea.evolution_evidence import EvidenceContractError, build_evolution_evidence
    from qea.evolution_feedback import FeedbackMode

    optimize = _task(tmp_path, "optimize-1")
    feedback, mapping = _contracts()

    with pytest.raises(EvidenceContractError, match="held-out identity in history"):
        build_evolution_evidence(
            mode=FeedbackMode.RICH,
            optimize_tasks=(optimize,),
            held_out_task_ids={"holdout-secret"},
            run_dir=tmp_path / "run",
            destination=tmp_path / "evidence",
            feedback_manifest=feedback,
            verifier_mapping=mapping,
            history=({"confirm": {"task_id": "holdout-secret", "score": 1.0}},),
        )
