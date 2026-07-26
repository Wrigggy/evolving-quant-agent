import json
from types import SimpleNamespace

import pytest

from qea.evaluation import OfficialTaskScore, aggregate_domain_macro


def _tasks():
    optimize = (
        SimpleNamespace(task_id="risk-train", domain="risk", lineage="risk-train-lineage"),
        SimpleNamespace(task_id="strategy-train", domain="strategy", lineage="strategy-lineage"),
    )
    held_out = (
        SimpleNamespace(task_id="fx-secret-holdout", domain="fx", lineage="fx-lineage"),
    )
    return optimize, held_out


def _seed_worker(tmp_path):
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "agent.yaml").write_text("name: qf-worker\n")
    (seed / "systemprompt.md").write_text("Solve the task.\n")
    return seed


class ImprovingEvaluator:
    def __init__(self):
        self.calls = []

    def evaluate(self, *, worker_dir, tasks, split, checkpoint, run_dir):
        markers = (worker_dir / "systemprompt.md").read_text().count("IMPROVEMENT")
        self.calls.append((split, checkpoint, tuple(task.task_id for task in tasks), markers))
        if split == "held_out":
            reward = 0.91 if checkpoint == "seed-held-out" else min(1.0, 0.91 + 0.01 * markers)
        else:
            reward = min(1.0, 0.20 + 0.10 * markers)
        return aggregate_domain_macro([
            OfficialTaskScore(
                task_id=task.task_id,
                domain=task.domain,
                reward=reward,
                diagnostic_tags=(() if reward == 1.0 else ("tests_failed",)),
            )
            for task in tasks
        ])


@pytest.mark.parametrize("iterations", [3, 5])
def test_runs_three_or_five_iterations_and_holds_out_seed_and_final_only(tmp_path, iterations):
    from qea.loop_benchmark import BenchmarkEvolutionConfig, run_benchmark_evolution

    optimize, held_out = _tasks()
    evaluator = ImprovingEvaluator()
    proposer_payloads = []

    def proposer(candidate_dir, diagnosis, iteration, run_dir):
        proposer_payloads.append(json.dumps(diagnosis, sort_keys=True))
        prompt = candidate_dir / "systemprompt.md"
        prompt.write_text(prompt.read_text() + f"IMPROVEMENT {iteration}\n")
        return {"trace": {"turns": 1}, "final_text": "improved process"}

    config = BenchmarkEvolutionConfig(
        run_id=f"pilot-{iterations}",
        n_iters=iterations,
        results_dir=tmp_path / "results",
        seed_worker_dir=_seed_worker(tmp_path),
        noise_floor=0.0,
    )
    result = run_benchmark_evolution(
        config,
        optimize_tasks=optimize,
        held_out_tasks=held_out,
        benchmark_commit="0" * 40,
        evaluator=evaluator,
        proposer=proposer,
    )

    assert len(result.records) == iterations
    assert result.n_kept == iterations
    assert len(result.optimize_trajectory) == iterations + 1
    assert [call[1] for call in evaluator.calls if call[0] == "held_out"] == [
        "seed-held-out",
        "final-held-out",
    ]
    assert len([call for call in evaluator.calls if call[0] == "optimize"]) == iterations + 1
    assert all("fx-secret-holdout" not in payload for payload in proposer_payloads)
    assert all("0.91" not in payload for payload in proposer_payloads)
    assert result.held_out_final.overall >= result.held_out_seed.overall


def test_domain_regression_rejects_candidate_even_when_overall_improves(tmp_path):
    from qea.loop_benchmark import BenchmarkEvolutionConfig, run_benchmark_evolution

    optimize, held_out = _tasks()

    class RegressingEvaluator:
        def evaluate(self, *, worker_dir, tasks, split, checkpoint, run_dir):
            if split == "held_out":
                return aggregate_domain_macro([
                    OfficialTaskScore(task_id=tasks[0].task_id, domain="fx", reward=0.5)
                ])
            candidate = "candidate" in checkpoint
            rewards = {"risk-train": 0.3, "strategy-train": 0.9} if candidate else {
                "risk-train": 0.5, "strategy-train": 0.5,
            }
            return aggregate_domain_macro([
                OfficialTaskScore(task_id=task.task_id, domain=task.domain, reward=rewards[task.task_id])
                for task in tasks
            ])

    def proposer(candidate_dir, diagnosis, iteration, run_dir):
        prompt = candidate_dir / "systemprompt.md"
        prompt.write_text(prompt.read_text() + "RISKY CHANGE\n")
        return {}

    result = run_benchmark_evolution(
        BenchmarkEvolutionConfig(
            run_id="domain-gate",
            n_iters=3,
            results_dir=tmp_path / "results",
            seed_worker_dir=_seed_worker(tmp_path),
            noise_floor=0.0,
            max_domain_regression=0.0,
        ),
        optimize_tasks=optimize,
        held_out_tasks=held_out,
        benchmark_commit="0" * 40,
        evaluator=RegressingEvaluator(),
        proposer=proposer,
    )

    assert result.n_kept == 0
    assert all(record.kept is False for record in result.records)
    assert "domain regression" in result.records[0].reason
    assert all("repeats a rejected edit" in record.reason for record in result.records[1:])
    assert result.optimize_trajectory == (0.5,)


def test_config_rejects_nonpilot_iteration_count(tmp_path):
    from qea.loop_benchmark import BenchmarkEvolutionConfig, EvolutionConfigError

    with pytest.raises(EvolutionConfigError, match="3 or 5"):
        BenchmarkEvolutionConfig(
            run_id="bad",
            n_iters=4,
            results_dir=tmp_path,
            seed_worker_dir=tmp_path,
        )


def test_e2b_evaluator_resume_does_not_repeat_completed_task_attempt(tmp_path):
    from qea.loop_benchmark import QFBenchE2BEvaluator

    tasks = (
        SimpleNamespace(task_id="task-a", domain="risk", lineage="a"),
        SimpleNamespace(task_id="task-b", domain="strategy", lineage="b"),
    )
    worker = _seed_worker(tmp_path)

    class FakeExecutor:
        def __init__(self):
            self.calls = []

        def execute(self, *, attempt, task, worker_dir, run_dir, model_env):
            self.calls.append(task.task_id)
            artifact_dir = run_dir / "fake-artifacts" / task.task_id
            artifact_dir.mkdir(parents=True, exist_ok=True)
            return SimpleNamespace(artifact_dir=artifact_dir, attempt_id=attempt.attempt_id)

    class InterruptingVerifier:
        def __init__(self):
            self.calls = []
            self.fail_task_b_once = True

        def verify(self, *, attempt, task, execution, run_dir):
            self.calls.append(task.task_id)
            if task.task_id == "task-b" and self.fail_task_b_once:
                self.fail_task_b_once = False
                raise RuntimeError("forced verifier interruption")
            return OfficialTaskScore(task_id=task.task_id, domain=task.domain, reward=0.5)

    executor = FakeExecutor()
    verifier = InterruptingVerifier()
    evaluator = QFBenchE2BEvaluator(
        benchmark_commit="0" * 40,
        run_id="attempt-resume",
        executor=executor,
        verifier=verifier,
        model_env={"LLM_API_KEY": "secret"},
        max_workers=1,
    )
    run_dir = tmp_path / "run"

    with pytest.raises(RuntimeError, match="forced verifier interruption"):
        evaluator.evaluate(
            worker_dir=worker,
            tasks=tasks,
            split="optimize",
            checkpoint="seed-optimize",
            run_dir=run_dir,
        )

    summary = evaluator.evaluate(
        worker_dir=worker,
        tasks=tasks,
        split="optimize",
        checkpoint="seed-optimize",
        run_dir=run_dir,
    )

    assert summary.overall == 0.5
    assert executor.calls.count("task-a") == 1
    assert verifier.calls.count("task-a") == 1
    assert executor.calls.count("task-b") == 2


def test_e2b_evaluator_records_worker_command_timeout_as_zero_reward(tmp_path):
    from qea.executors.e2b_nexau import E2BWorkerTimeout
    from qea.loop_benchmark import QFBenchE2BEvaluator

    task = SimpleNamespace(task_id="slow-task", domain="derivatives", lineage="slow")
    worker = _seed_worker(tmp_path)

    class TimeoutExecutor:
        def execute(self, **kwargs):
            raise E2BWorkerTimeout("worker exceeded the official agent timeout")

    class RefusingVerifier:
        def verify(self, **kwargs):
            raise AssertionError("a timed-out worker must not enter the verifier")

    evaluator = QFBenchE2BEvaluator(
        benchmark_commit="0" * 40,
        run_id="timeout-score",
        executor=TimeoutExecutor(),
        verifier=RefusingVerifier(),
        model_env={"LLM_API_KEY": "secret"},
        max_workers=1,
    )
    run_dir = tmp_path / "run"

    summary = evaluator.evaluate(
        worker_dir=worker,
        tasks=(task,),
        split="optimize",
        checkpoint="seed-optimize",
        run_dir=run_dir,
    )

    assert summary.overall == 0.0
    assert summary.scores[0].diagnostic_tags == ("timeout",)
    completed = tuple((run_dir / "attempts").glob("*/completed-score.json"))
    assert len(completed) == 1
    assert json.loads(completed[0].read_text())["reward"] == 0.0
    attempt_identity = completed[0].with_name("attempt.json")
    payload = json.loads(attempt_identity.read_text())
    assert payload["task_id"] == "slow-task"
    assert payload["split"] == "optimize"
    assert payload["checkpoint"] == "seed-optimize"
    assert payload["attempt_id"] == completed[0].parent.name
