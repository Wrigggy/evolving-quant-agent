import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from qea.evaluation import OfficialTaskScore, aggregate_domain_macro


def _tasks(prefix: str, count: int, domains: tuple[str, ...]):
    return tuple(
        SimpleNamespace(
            task_id=f"{prefix}-{index:02d}",
            domain=domains[index % len(domains)],
            lineage=f"{prefix}-lineage-{index:02d}",
        )
        for index in range(count)
    )


def _panels():
    domains = ("data", "derivatives", "execution", "rates", "risk", "systematic")
    return (
        _tasks("train", 30, domains),
        _tasks("validation", 15, domains),
        _tasks("test", 32, domains),
        _tasks("diagnostic", 8, ("data", "derivatives", "risk", "systematic")),
    )


def _seed_worker(tmp_path: Path) -> Path:
    seed = tmp_path / "seed"
    seed.mkdir(exist_ok=True)
    (seed / "agent.yaml").write_text("name: worker\n")
    (seed / "systemprompt.md").write_text("Solve the public task.\n")
    return seed


def _config(tmp_path: Path, *, run_id: str, n_iters: int = 10, tolerance=0.02):
    from qea.loop_benchmark import BenchmarkEvolutionConfig

    return BenchmarkEvolutionConfig(
        run_id=run_id,
        n_iters=n_iters,
        results_dir=tmp_path / "results",
        seed_worker_dir=_seed_worker(tmp_path),
        noise_floor=0.0,
        validation_noise_tolerance=tolerance,
        validation_calibration_digest="c" * 64,
        validation_calibration_source_run_id="base-85x5",
    )


class ScheduleEvaluator:
    def __init__(self):
        self.calls = []

    def evaluate(self, *, worker_dir, tasks, split, checkpoint, run_dir):
        task_tuple = tuple(tasks)
        markers = (worker_dir / "systemprompt.md").read_text().count("IMPROVE")
        self.calls.append((split, checkpoint, len(task_tuple), markers))
        reward = {
            "optimize": min(0.9, 0.2 + markers * 0.05),
            "validation": 0.5,
            "test": 0.4,
            "diagnostic": 0.1,
        }[split]
        return aggregate_domain_macro(
            OfficialTaskScore(
                task_id=task.task_id,
                domain=task.domain,
                reward=reward,
            )
            for task in task_tuple
        )


def test_tvt_schedule_scores_575_attempts_with_blind_validation_each_iteration(
    tmp_path: Path,
) -> None:
    from qea.loop_benchmark import run_benchmark_evolution

    train, validation, test, diagnostic = _panels()
    evaluator = ScheduleEvaluator()

    def proposer(candidate_dir, diagnosis, iteration, run_dir):
        prompt = candidate_dir / "systemprompt.md"
        prompt.write_text(prompt.read_text() + f"IMPROVE {iteration}\n")
        return {}

    result = run_benchmark_evolution(
        _config(tmp_path, run_id="tvt-schedule"),
        optimize_tasks=train,
        validation_tasks=validation,
        test_tasks=test,
        diagnostic_tasks=diagnostic,
        benchmark_commit="0" * 40,
        evaluator=evaluator,
        proposer=proposer,
    )

    assert sum(call[2] for call in evaluator.calls) == 575
    assert [call[1] for call in evaluator.calls if call[0] == "validation"] == [
        "seed-validation",
        *[f"iteration-{iteration}-validation" for iteration in range(1, 11)],
    ]
    assert [call[1] for call in evaluator.calls if call[0] == "test"] == [
        "seed-test",
        "final-test",
    ]
    assert [call[1] for call in evaluator.calls if call[0] == "diagnostic"] == [
        "seed-diagnostic",
        "final-diagnostic",
    ]
    assert result.n_kept == 10
    assert len(result.records) == 10
    assert result.validation_seed.overall == pytest.approx(0.5)
    assert result.validation_final.overall == pytest.approx(0.5)
    assert result.test_seed.overall == pytest.approx(0.4)
    assert result.test_final.overall == pytest.approx(0.4)
    assert result.diagnostic_seed.overall == pytest.approx(0.1)
    assert result.diagnostic_final.overall == pytest.approx(0.1)


def test_train_gain_rolls_back_when_blind_validation_exceeds_tolerance(
    tmp_path: Path,
) -> None:
    from qea.loop_benchmark import run_benchmark_evolution

    train = _tasks("train", 1, ("risk",))
    validation = _tasks("validation", 1, ("risk",))
    test = _tasks("test", 1, ("risk",))
    diagnostic = _tasks("diagnostic", 1, ("risk",))

    class RegressingValidationEvaluator:
        def evaluate(self, *, worker_dir, tasks, split, checkpoint, run_dir):
            candidate = checkpoint.startswith("iteration-")
            reward = {
                "optimize": 0.8 if candidate else 0.4,
                "validation": 0.47 if candidate else 0.5,
                "test": 0.25,
                "diagnostic": 0.0,
            }[split]
            return aggregate_domain_macro(
                OfficialTaskScore(
                    task_id=task.task_id,
                    domain=task.domain,
                    reward=reward,
                )
                for task in tasks
            )

    def proposer(candidate_dir, diagnosis, iteration, run_dir):
        prompt = candidate_dir / "systemprompt.md"
        prompt.write_text(prompt.read_text() + "IMPROVE\n")
        return {}

    result = run_benchmark_evolution(
        _config(tmp_path, run_id="tvt-confirm", n_iters=1),
        optimize_tasks=train,
        validation_tasks=validation,
        test_tasks=test,
        diagnostic_tasks=diagnostic,
        benchmark_commit="0" * 40,
        evaluator=RegressingValidationEvaluator(),
        proposer=proposer,
    )

    assert result.n_kept == 0
    assert result.records[0].reason == "confirm_failed"
    assert result.records[0].candidate_validation_overall == pytest.approx(0.47)
    assert result.optimize_final.overall == pytest.approx(0.4)
    assert result.validation_final.overall == pytest.approx(0.5)
    state = json.loads((result.run_dir / "resume.json").read_text())
    proposer_history = json.dumps(state["history"], sort_keys=True)
    assert "0.47" not in proposer_history
    assert "candidate_validation" not in proposer_history
    assert state["history"][0]["reason"] == "confirm_failed"


def test_tvt_resume_rejects_validation_tolerance_identity_change(
    tmp_path: Path,
) -> None:
    from qea.loop_benchmark import EvolutionConfigError, run_benchmark_evolution

    train, validation, test, diagnostic = (
        _tasks("train", 1, ("risk",)),
        _tasks("validation", 1, ("risk",)),
        _tasks("test", 1, ("risk",)),
        _tasks("diagnostic", 1, ("risk",)),
    )

    def proposer(candidate_dir, diagnosis, iteration, run_dir):
        prompt = candidate_dir / "systemprompt.md"
        prompt.write_text(prompt.read_text() + "IMPROVE\n")
        return {}

    common = dict(
        optimize_tasks=train,
        validation_tasks=validation,
        test_tasks=test,
        diagnostic_tasks=diagnostic,
        benchmark_commit="0" * 40,
        evaluator=ScheduleEvaluator(),
        proposer=proposer,
    )
    run_benchmark_evolution(
        _config(tmp_path, run_id="tvt-identity", n_iters=1),
        **common,
    )

    with pytest.raises(
        EvolutionConfigError,
        match="validation_noise_tolerance",
    ):
        run_benchmark_evolution(
            _config(
                tmp_path,
                run_id="tvt-identity",
                n_iters=1,
                tolerance=0.03,
            ),
            **common,
        )
