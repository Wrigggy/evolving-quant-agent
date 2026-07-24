from pathlib import Path
import subprocess
import sys


def _summary(rewards, domains, overall):
    return {
        "scores": [],
        "task_rewards": rewards,
        "domain_scores": domains,
        "task_mean": sum(rewards.values()) / len(rewards),
        "overall": overall,
    }


def _result(run_id, n_iters, optimize, held_seed, held_final, records):
    return {
        "schema_version": 1,
        "phase": "complete",
        "run_id": run_id,
        "n_iters": n_iters,
        "seed_optimize": optimize,
        "incumbent_summary": optimize,
        "held_out_seed": held_seed,
        "held_out_final": held_final,
        "records": records,
    }


def test_compare_qfbench_results_reports_shared_tasks_and_paired_deltas():
    from qea.qfbench_comparison import compare_qfbench_results

    baseline = _result(
        "baseline-3",
        3,
        _summary({"shared-opt": 1.0, "old-only": 0.5}, {"risk": 0.75}, 0.75),
        _summary({"shared-held": 1.0, "old-held": 0.0}, {"fx": 0.5}, 0.5),
        _summary({"shared-held": 0.0, "old-held": 1.0}, {"fx": 0.5}, 0.5),
        [
            {"iteration": 1, "kept": False, "candidate_overall": 0.7},
            {"iteration": 2, "kept": True, "candidate_overall": 0.8},
            {"iteration": 3, "kept": False, "candidate_overall": 0.75},
        ],
    )
    candidate = _result(
        "candidate-5",
        5,
        _summary(
            {"shared-opt": 0.8, "new-a": 0.4, "new-b": 0.6},
            {"risk_credit": 0.6},
            0.6,
        ),
        _summary(
            {"shared-held": 0.5, "new-held-a": 1.0, "new-held-b": 0.0},
            {"rates_fx_macro": 0.5},
            0.5,
        ),
        _summary(
            {"shared-held": 1.0, "new-held-a": 1.0, "new-held-b": 0.0},
            {"rates_fx_macro": 2 / 3},
            2 / 3,
        ),
        [
            {"iteration": index, "kept": index in {2, 5}, "candidate_overall": 0.6 + index / 100}
            for index in range(1, 6)
        ],
    )

    comparison = compare_qfbench_results(baseline, candidate)

    assert comparison["baseline"]["run_id"] == "baseline-3"
    assert comparison["candidate"]["run_id"] == "candidate-5"
    assert comparison["baseline"]["n_kept"] == 1
    assert comparison["candidate"]["n_kept"] == 2
    assert comparison["candidate"]["held_out_delta"] == (2 / 3) - 0.5
    assert (
        comparison["candidate"]["held_out_task_mean_single_binary_sensitivity"]
        == 1 / 3
    )
    assert comparison["shared_optimize_seed"] == [
        {
            "task_id": "shared-opt",
            "baseline_reward": 1.0,
            "candidate_reward": 0.8,
            "delta": -0.2,
        }
    ]
    assert comparison["shared_held_out"] == [
        {
            "task_id": "shared-held",
            "baseline_seed": 1.0,
            "baseline_final": 0.0,
            "candidate_seed": 0.5,
            "candidate_final": 1.0,
        }
    ]


def test_render_qfbench_comparison_markdown_contains_core_tables():
    from qea.qfbench_comparison import (
        compare_qfbench_results,
        render_qfbench_comparison_markdown,
    )

    baseline = _result(
        "baseline-3",
        3,
        _summary({"task-a": 1.0}, {"risk": 1.0}, 1.0),
        _summary({"held-a": 1.0}, {"fx": 1.0}, 1.0),
        _summary({"held-a": 0.0}, {"fx": 0.0}, 0.0),
        [],
    )
    candidate = _result(
        "candidate-5",
        5,
        _summary({"task-a": 0.5}, {"risk_credit": 0.5}, 0.5),
        _summary({"held-a": 0.5}, {"rates_fx_macro": 0.5}, 0.5),
        _summary({"held-a": 1.0}, {"rates_fx_macro": 1.0}, 1.0),
        [],
    )

    markdown = render_qfbench_comparison_markdown(
        compare_qfbench_results(baseline, candidate)
    )

    assert "# QFBench Run Comparison" in markdown
    assert "baseline-3" in markdown
    assert "candidate-5" in markdown
    assert "Shared Optimize Seed Tasks" in markdown
    assert "Shared Held-Out Tasks" in markdown
    assert "One binary held-out task (task mean)" in markdown


def test_qfbench_comparison_script_is_directly_invokable():
    repository = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [sys.executable, "scripts/compare_qfbench_runs.py", "--help"],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "--baseline" in proc.stdout
    assert "--candidate" in proc.stdout
    assert "--json-output" in proc.stdout
    assert "--markdown-output" in proc.stdout
