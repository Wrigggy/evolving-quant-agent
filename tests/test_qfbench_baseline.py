import json
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

from qea.evaluation import OfficialTaskScore, aggregate_domain_macro


COMMIT = "0" * 40
DIGESTS = {
    "task_manifest_digest": "1" * 64,
    "runtime_identity_digest": "2" * 64,
    "scheduler_identity_digest": "3" * 64,
    "template_identity_digest": "4" * 64,
}


def _tasks():
    primary = (
        SimpleNamespace(
            task_id="risk-task",
            domain="risk_credit",
            reward_kind="binary",
            resource_source="upstream",
        ),
        SimpleNamespace(
            task_id="derivative-task",
            domain="derivatives",
            reward_kind="partial",
            resource_source="qea_fallback",
        ),
    )
    diagnostic = (
        SimpleNamespace(
            task_id="copy-task",
            domain="derivatives",
            reward_kind="binary",
            resource_source="upstream",
        ),
    )
    return primary, diagnostic


def _summary(tasks, reward):
    return aggregate_domain_macro(tuple(
        OfficialTaskScore(task_id=task.task_id, domain=task.domain, reward=reward)
        for task in tasks
    ))


class RecordingEvaluator:
    def __init__(self):
        self.calls = []

    def evaluate(self, *, worker_dir, tasks, split, checkpoint, run_dir):
        self.calls.append((split, checkpoint))
        repetition = int(checkpoint.split("-")[1])
        reward = repetition / 10
        return _summary(tuple(tasks), reward)


def _config(tmp_path: Path, worker: Path, **changes):
    from qea.qfbench_baseline import BaselineConfig

    values = {
        "run_id": "baseline-five",
        "repetitions": 5,
        "results_dir": tmp_path / "results",
        "seed_worker_dir": worker,
        "model_identity": "fixture-model",
        "worker_concurrency": 4,
        "verifier_concurrency": 3,
        **DIGESTS,
    }
    values.update(changes)
    return BaselineConfig(**values)


def test_runs_primary_then_diagnostic_for_five_repetitions_without_evolver(
    tmp_path,
) -> None:
    from qea.qfbench_baseline import run_qfbench_baseline

    worker = tmp_path / "worker"
    worker.mkdir()
    (worker / "systemprompt.md").write_text("base worker\n")
    primary, diagnostic = _tasks()
    evaluator = RecordingEvaluator()

    result = run_qfbench_baseline(
        _config(tmp_path, worker),
        primary_tasks=primary,
        diagnostic_tasks=diagnostic,
        benchmark_commit=COMMIT,
        evaluator=evaluator,
    )

    assert evaluator.calls == [
        item
        for repetition in range(1, 6)
        for item in (
            ("baseline_primary", f"repetition-{repetition:02d}-primary"),
            ("baseline_diagnostic", f"repetition-{repetition:02d}-diagnostic"),
        )
    ]
    assert result.complete is True
    assert len(result.repetitions) == 5
    assert not (result.run_dir / "evidence").exists()
    assert not (result.run_dir / "iteration-01").exists()


def test_calibration_stop_then_resume_starts_at_repetition_two(tmp_path) -> None:
    from qea.qfbench_baseline import run_qfbench_baseline

    worker = tmp_path / "worker"
    worker.mkdir()
    (worker / "agent.yaml").write_text("name: base\n")
    primary, diagnostic = _tasks()
    first = RecordingEvaluator()

    partial = run_qfbench_baseline(
        _config(tmp_path, worker),
        primary_tasks=primary,
        diagnostic_tasks=diagnostic,
        benchmark_commit=COMMIT,
        evaluator=first,
        stop_after_repetition=1,
    )

    assert partial.complete is False
    assert first.calls == [
        ("baseline_primary", "repetition-01-primary"),
        ("baseline_diagnostic", "repetition-01-diagnostic"),
    ]
    state = json.loads((partial.run_dir / "resume.json").read_text())
    assert state["next_repetition"] == 2
    assert state["phase"] == "calibration_stop"

    resumed = RecordingEvaluator()
    complete = run_qfbench_baseline(
        _config(tmp_path, worker),
        primary_tasks=primary,
        diagnostic_tasks=diagnostic,
        benchmark_commit=COMMIT,
        evaluator=resumed,
    )

    assert complete.complete is True
    assert resumed.calls[0] == (
        "baseline_primary",
        "repetition-02-primary",
    )
    assert len(resumed.calls) == 8


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("model_identity", "other-model"),
        ("task_manifest_digest", "a" * 64),
        ("runtime_identity_digest", "b" * 64),
        ("scheduler_identity_digest", "c" * 64),
        ("template_identity_digest", "d" * 64),
        ("worker_concurrency", 3),
        ("verifier_concurrency", 2),
    ],
)
def test_resume_rejects_immutable_identity_change(tmp_path, field, value) -> None:
    from qea.qfbench_baseline import BaselineConfigError, run_qfbench_baseline

    worker = tmp_path / "worker"
    worker.mkdir()
    (worker / "agent.yaml").write_text("name: base\n")
    primary, diagnostic = _tasks()
    run_qfbench_baseline(
        _config(tmp_path, worker),
        primary_tasks=primary,
        diagnostic_tasks=diagnostic,
        benchmark_commit=COMMIT,
        evaluator=RecordingEvaluator(),
        stop_after_repetition=1,
    )

    with pytest.raises(BaselineConfigError, match="identity mismatch"):
        run_qfbench_baseline(
            _config(tmp_path, worker, **{field: value}),
            primary_tasks=primary,
            diagnostic_tasks=diagnostic,
            benchmark_commit=COMMIT,
            evaluator=RecordingEvaluator(),
        )


def test_resume_rejects_worker_digest_and_benchmark_changes(tmp_path) -> None:
    from qea.qfbench_baseline import BaselineConfigError, run_qfbench_baseline

    worker = tmp_path / "worker"
    worker.mkdir()
    prompt = worker / "systemprompt.md"
    prompt.write_text("base\n")
    primary, diagnostic = _tasks()
    run_qfbench_baseline(
        _config(tmp_path, worker),
        primary_tasks=primary,
        diagnostic_tasks=diagnostic,
        benchmark_commit=COMMIT,
        evaluator=RecordingEvaluator(),
        stop_after_repetition=1,
    )

    prompt.write_text("mutated\n")
    with pytest.raises(BaselineConfigError, match="identity mismatch"):
        run_qfbench_baseline(
            _config(tmp_path, worker),
            primary_tasks=primary,
            diagnostic_tasks=diagnostic,
            benchmark_commit=COMMIT,
            evaluator=RecordingEvaluator(),
        )
    prompt.write_text("base\n")
    with pytest.raises(BaselineConfigError, match="checkpoint mismatch"):
        run_qfbench_baseline(
            _config(tmp_path, worker),
            primary_tasks=primary,
            diagnostic_tasks=diagnostic,
            benchmark_commit="f" * 40,
            evaluator=RecordingEvaluator(),
        )


def test_aggregate_repetitions_uses_repeat_level_t_interval_and_separate_panels():
    from qea.qfbench_baseline import aggregate_repetitions

    primary_tasks, diagnostic_tasks = _tasks()
    primary = tuple(_summary(primary_tasks, reward) for reward in (0.4, 0.5, 0.6, 0.7, 0.8))
    diagnostic = tuple(_summary(diagnostic_tasks, 1.0) for _ in range(5))

    aggregate = aggregate_repetitions(
        primary,
        diagnostic,
        resource_fallback_task_ids=frozenset({"derivative-task"}),
        primary_tasks=primary_tasks,
        diagnostic_tasks=diagnostic_tasks,
        expected_repetitions=5,
    )

    headline = aggregate["primary"]["repeat_domain_macro"]
    expected_sd = math.sqrt(0.025)
    expected_se = math.sqrt(0.005)
    half_width = 2.7764451051977987 * expected_se
    assert headline["mean"] == pytest.approx(0.6)
    assert headline["sample_sd"] == pytest.approx(expected_sd)
    assert headline["standard_error"] == pytest.approx(expected_se)
    assert headline["confidence_interval_95"] == pytest.approx(
        [0.6 - half_width, 0.6 + half_width]
    )
    assert aggregate["diagnostic"]["repeat_domain_macro"]["mean"] == 1.0
    assert aggregate["resource_declared_sensitivity"]["task_count"] == 1
    assert aggregate["primary"]["tasks"]["risk-task"]["success_count"] == 0
    assert "success_count" not in aggregate["primary"]["tasks"]["derivative-task"]


def test_partial_aggregate_has_no_confidence_interval() -> None:
    from qea.qfbench_baseline import aggregate_repetitions

    primary_tasks, diagnostic_tasks = _tasks()
    aggregate = aggregate_repetitions(
        (_summary(primary_tasks, 0.5),),
        (_summary(diagnostic_tasks, 0.0),),
        resource_fallback_task_ids=frozenset({"derivative-task"}),
        primary_tasks=primary_tasks,
        diagnostic_tasks=diagnostic_tasks,
        expected_repetitions=5,
    )

    assert aggregate["complete"] is False
    headline = aggregate["primary"]["repeat_domain_macro"]
    assert headline["mean"] == 0.5
    assert headline["sample_sd"] is None
    assert headline["confidence_interval_95"] is None
