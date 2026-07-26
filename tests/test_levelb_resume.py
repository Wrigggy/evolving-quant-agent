from types import SimpleNamespace

import pytest

from qea.evaluation import OfficialTaskScore, aggregate_domain_macro


def _summary(tasks, reward):
    return aggregate_domain_macro([
        OfficialTaskScore(
            task_id=task.task_id,
            domain=task.domain,
            reward=reward,
            diagnostic_tags=(() if reward == 1.0 else ("tests_failed",)),
        )
        for task in tasks
    ])


def test_resume_reuses_completed_proposal_after_candidate_evaluation_interrupt(tmp_path):
    from qea.loop_benchmark import BenchmarkEvolutionConfig, run_benchmark_evolution

    optimize = (SimpleNamespace(task_id="train", domain="risk", lineage="train-lineage"),)
    held_out = (SimpleNamespace(task_id="hold", domain="fx", lineage="hold-lineage"),)
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "agent.yaml").write_text("name: worker\n")
    (seed / "systemprompt.md").write_text("seed\n")
    proposer_calls = []

    def proposer(candidate_dir, diagnosis, iteration, run_dir):
        proposer_calls.append(iteration)
        prompt = candidate_dir / "systemprompt.md"
        prompt.write_text(prompt.read_text() + f"IMPROVED {iteration}\n")
        return {"trace": {"turns": 1}}

    class InterruptOnceEvaluator:
        def __init__(self):
            self.interrupted = False

        def evaluate(self, *, worker_dir, tasks, split, checkpoint, run_dir):
            if checkpoint == "iteration-1-candidate" and not self.interrupted:
                self.interrupted = True
                raise RuntimeError("forced coordinator interruption")
            markers = (worker_dir / "systemprompt.md").read_text().count("IMPROVED")
            return _summary(tasks, 0.2 + 0.1 * markers if split == "optimize" else 0.7)

    evaluator = InterruptOnceEvaluator()
    config = BenchmarkEvolutionConfig(
        run_id="resume-pilot",
        n_iters=3,
        results_dir=tmp_path / "results",
        seed_worker_dir=seed,
        noise_floor=0.0,
    )

    with pytest.raises(RuntimeError, match="forced coordinator interruption"):
        run_benchmark_evolution(
            config,
            optimize_tasks=optimize,
            held_out_tasks=held_out,
            benchmark_commit="0" * 40,
            evaluator=evaluator,
            proposer=proposer,
        )
    assert proposer_calls == [1]

    result = run_benchmark_evolution(
        config,
        optimize_tasks=optimize,
        held_out_tasks=held_out,
        benchmark_commit="0" * 40,
        evaluator=evaluator,
        proposer=proposer,
    )

    assert proposer_calls == [1, 2, 3]
    assert len(result.records) == 3
    assert result.n_kept == 3
    resume = result.run_dir / "resume.json"
    assert '"phase": "complete"' in resume.read_text()
