import hashlib

import pytest


def test_attempt_id_is_stable_and_changes_with_worker():
    from qea.evaluation import TaskAttempt

    kwargs = dict(
        run_id="run-001",
        benchmark_commit="0" * 40,
        task_id="historical-var-data-prep",
        split="optimize",
        checkpoint="iteration-2-candidate",
        worker_digest="a" * 64,
    )
    first = TaskAttempt.create(**kwargs)
    second = TaskAttempt.create(**kwargs)

    assert first.attempt_id == second.attempt_id
    assert len(first.attempt_id) == 64
    changed = TaskAttempt.create(**{**kwargs, "worker_digest": "b" * 64})
    assert changed.attempt_id != first.attempt_id


def test_artifact_record_hashes_bytes_and_requires_relative_path(tmp_path):
    from qea.evaluation import ArtifactRecord, EvaluationContractError

    output = tmp_path / "output"
    output.mkdir()
    artifact = output / "summary.json"
    artifact.write_bytes(b'{"ok": true}\n')

    record = ArtifactRecord.from_file(artifact, root=output)

    assert record.path == "summary.json"
    assert record.size_bytes == len(artifact.read_bytes())
    assert record.sha256 == hashlib.sha256(artifact.read_bytes()).hexdigest()
    with pytest.raises(EvaluationContractError, match="outside artifact root"):
        ArtifactRecord.from_file(tmp_path / "elsewhere.json", root=output)


def test_official_score_accepts_only_unit_reward_and_answer_free_tags():
    from qea.evaluation import EvaluationContractError, OfficialTaskScore

    score = OfficialTaskScore(
        task_id="evt-pot-var",
        domain="risk",
        reward=0.625,
        diagnostic_tags=("tests_failed", "invalid_schema"),
        verifier_exit_code=1,
        tests_passed=5,
        tests_failed=3,
        log_uri="runs/r1/verifier.log",
    )
    assert score.reward == 0.625

    with pytest.raises(EvaluationContractError, match=r"\[0, 1\]"):
        OfficialTaskScore(task_id="x", domain="risk", reward=1.1)
    with pytest.raises(EvaluationContractError, match="answer-free"):
        OfficialTaskScore(
            task_id="x",
            domain="risk",
            reward=0.0,
            diagnostic_tags=("expected_var_is_0.012345",),
        )


def test_domain_macro_weights_domains_equally_not_tasks():
    from qea.evaluation import OfficialTaskScore, aggregate_domain_macro

    summary = aggregate_domain_macro([
        OfficialTaskScore(task_id="risk-1", domain="risk", reward=1.0),
        OfficialTaskScore(task_id="risk-2", domain="risk", reward=0.0),
        OfficialTaskScore(task_id="fx-1", domain="fx", reward=1.0),
    ])

    assert summary.task_mean == pytest.approx(2 / 3)
    assert summary.domain_scores == {"fx": 1.0, "risk": 0.5}
    assert summary.overall == pytest.approx(0.75)
    assert summary.task_rewards == {"fx-1": 1.0, "risk-1": 1.0, "risk-2": 0.0}


def test_domain_macro_rejects_missing_expected_domain_and_duplicate_task():
    from qea.evaluation import (
        EvaluationContractError,
        OfficialTaskScore,
        aggregate_domain_macro,
    )

    score = OfficialTaskScore(task_id="risk-1", domain="risk", reward=1.0)
    with pytest.raises(EvaluationContractError, match="missing expected domains"):
        aggregate_domain_macro([score], expected_domains={"risk", "fx"})
    with pytest.raises(EvaluationContractError, match="duplicate task score"):
        aggregate_domain_macro([score, score])


def test_benchmark_split_rejects_duplicate_ids_and_bad_lineage_count():
    from qea.evaluation import BenchmarkSplit, EvaluationContractError

    split = BenchmarkSplit(
        name="optimize",
        task_ids=("a", "b"),
        lineages=("lineage-a", "lineage-b"),
    )
    assert split.task_ids == ("a", "b")

    with pytest.raises(EvaluationContractError, match="duplicate task"):
        BenchmarkSplit(name="x", task_ids=("a", "a"), lineages=("l1", "l2"))
    with pytest.raises(EvaluationContractError, match="one lineage"):
        BenchmarkSplit(name="x", task_ids=("a", "b"), lineages=("l1",))


def test_split_isolation_rejects_task_or_lineage_overlap():
    from qea.evaluation import (
        BenchmarkSplit,
        EvaluationContractError,
        validate_split_isolation,
    )

    optimize = BenchmarkSplit(
        name="optimize", task_ids=("a", "b"), lineages=("l1", "l2")
    )
    clean = BenchmarkSplit(name="held_out", task_ids=("c",), lineages=("l3",))
    validate_split_isolation(optimize, clean)

    with pytest.raises(EvaluationContractError, match="task overlap"):
        validate_split_isolation(
            optimize,
            BenchmarkSplit(name="held_out", task_ids=("b",), lineages=("l3",)),
        )
    with pytest.raises(EvaluationContractError, match="lineage overlap"):
        validate_split_isolation(
            optimize,
            BenchmarkSplit(name="held_out", task_ids=("c",), lineages=("l2",)),
        )
