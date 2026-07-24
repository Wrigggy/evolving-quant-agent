"""Compare complete QFBench evolution checkpoints without hiding split drift."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


class QFBenchComparisonError(ValueError):
    """Raised when a run artifact cannot support a valid comparison."""


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise QFBenchComparisonError(f"{label} must be an object")
    return value


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise QFBenchComparisonError(f"{label} must be numeric")
    return float(value)


def _summary(run: Mapping[str, Any], key: str) -> dict[str, Any]:
    payload = _mapping(run.get(key), key)
    rewards_payload = _mapping(payload.get("task_rewards"), f"{key}.task_rewards")
    domains_payload = _mapping(payload.get("domain_scores"), f"{key}.domain_scores")
    if not rewards_payload:
        raise QFBenchComparisonError(f"{key}.task_rewards must not be empty")
    rewards = {
        str(task_id): _number(reward, f"{key}.task_rewards[{task_id!r}]")
        for task_id, reward in rewards_payload.items()
    }
    domains = {
        str(domain): _number(score, f"{key}.domain_scores[{domain!r}]")
        for domain, score in domains_payload.items()
    }
    if not domains:
        raise QFBenchComparisonError(f"{key}.domain_scores must not be empty")
    return {
        "task_rewards": rewards,
        "domain_scores": domains,
        "task_mean": _number(payload.get("task_mean"), f"{key}.task_mean"),
        "overall": _number(payload.get("overall"), f"{key}.overall"),
    }


def _validated_run(payload: Mapping[str, Any], label: str) -> dict[str, Any]:
    if payload.get("phase") != "complete":
        raise QFBenchComparisonError(
            f"{label} must be a complete resume.json checkpoint"
        )
    run_id = payload.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise QFBenchComparisonError(f"{label}.run_id must be non-empty")
    n_iters = payload.get("n_iters")
    if isinstance(n_iters, bool) or not isinstance(n_iters, int) or n_iters < 0:
        raise QFBenchComparisonError(f"{label}.n_iters must be a non-negative integer")
    records_payload = payload.get("records")
    if not isinstance(records_payload, Sequence) or isinstance(records_payload, (str, bytes)):
        raise QFBenchComparisonError(f"{label}.records must be an array")
    records: list[dict[str, Any]] = []
    for index, item in enumerate(records_payload):
        record = _mapping(item, f"{label}.records[{index}]")
        kept = record.get("kept")
        if not isinstance(kept, bool):
            raise QFBenchComparisonError(f"{label}.records[{index}].kept must be boolean")
        records.append(dict(record))
    return {
        "run_id": run_id,
        "n_iters": n_iters,
        "seed_optimize": _summary(payload, "seed_optimize"),
        "incumbent_summary": _summary(payload, "incumbent_summary"),
        "held_out_seed": _summary(payload, "held_out_seed"),
        "held_out_final": _summary(payload, "held_out_final"),
        "records": records,
    }


def _run_metrics(run: Mapping[str, Any]) -> dict[str, Any]:
    seed_optimize = run["seed_optimize"]
    optimize_final = run["incumbent_summary"]
    held_seed = run["held_out_seed"]
    held_final = run["held_out_final"]
    records = run["records"]
    n_kept = sum(bool(record["kept"]) for record in records)
    held_count = len(held_seed["task_rewards"])
    return {
        "run_id": run["run_id"],
        "n_iters": run["n_iters"],
        "optimize_task_count": len(seed_optimize["task_rewards"]),
        "held_out_task_count": held_count,
        "optimize_seed_overall": seed_optimize["overall"],
        "optimize_seed_task_mean": seed_optimize["task_mean"],
        "optimize_seed_domain_scores": dict(seed_optimize["domain_scores"]),
        "optimize_final_overall": optimize_final["overall"],
        "optimize_final_task_mean": optimize_final["task_mean"],
        "optimize_final_domain_scores": dict(optimize_final["domain_scores"]),
        "optimize_overall_delta": optimize_final["overall"] - seed_optimize["overall"],
        "held_out_seed_overall": held_seed["overall"],
        "held_out_final_overall": held_final["overall"],
        "held_out_delta": held_final["overall"] - held_seed["overall"],
        "held_out_seed_domain_scores": dict(held_seed["domain_scores"]),
        "held_out_final_domain_scores": dict(held_final["domain_scores"]),
        "held_out_task_mean_single_binary_sensitivity": 1.0 / held_count,
        "n_kept": n_kept,
        "n_rolled_back": len(records) - n_kept,
        "iterations": [dict(record) for record in records],
    }


def _shared_rewards(
    baseline: Mapping[str, float],
    candidate: Mapping[str, float],
) -> list[dict[str, Any]]:
    return [
        {
            "task_id": task_id,
            "baseline_reward": baseline[task_id],
            "candidate_reward": candidate[task_id],
            "delta": round(candidate[task_id] - baseline[task_id], 12),
        }
        for task_id in sorted(set(baseline) & set(candidate))
    ]


def compare_qfbench_results(
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    """Return comparable run metrics and paired task-level intersections.

    Inputs must be complete ``resume.json`` checkpoints. Overall scores are
    reported for context, while shared-task tables provide the defensible
    paired view when the two runs use different task or domain sets.
    """

    baseline_run = _validated_run(_mapping(baseline, "baseline"), "baseline")
    candidate_run = _validated_run(_mapping(candidate, "candidate"), "candidate")

    baseline_seed = baseline_run["seed_optimize"]["task_rewards"]
    candidate_seed = candidate_run["seed_optimize"]["task_rewards"]
    baseline_final = baseline_run["incumbent_summary"]["task_rewards"]
    candidate_final = candidate_run["incumbent_summary"]["task_rewards"]
    baseline_held_seed = baseline_run["held_out_seed"]["task_rewards"]
    baseline_held_final = baseline_run["held_out_final"]["task_rewards"]
    candidate_held_seed = candidate_run["held_out_seed"]["task_rewards"]
    candidate_held_final = candidate_run["held_out_final"]["task_rewards"]

    shared_held_ids = sorted(
        set(baseline_held_seed)
        & set(baseline_held_final)
        & set(candidate_held_seed)
        & set(candidate_held_final)
    )
    return {
        "schema_version": 1,
        "baseline": _run_metrics(baseline_run),
        "candidate": _run_metrics(candidate_run),
        "overall_scores_are_same_panel": (
            set(baseline_seed) == set(candidate_seed)
            and set(baseline_held_seed) == set(candidate_held_seed)
        ),
        "shared_optimize_seed": _shared_rewards(baseline_seed, candidate_seed),
        "shared_optimize_final": _shared_rewards(baseline_final, candidate_final),
        "shared_held_out": [
            {
                "task_id": task_id,
                "baseline_seed": baseline_held_seed[task_id],
                "baseline_final": baseline_held_final[task_id],
                "candidate_seed": candidate_held_seed[task_id],
                "candidate_final": candidate_held_final[task_id],
            }
            for task_id in shared_held_ids
        ],
    }


def _format_score(value: Any) -> str:
    return f"{float(value):.4f}"


def render_qfbench_comparison_markdown(comparison: Mapping[str, Any]) -> str:
    """Render a compact human-readable report from a comparison payload."""

    baseline = _mapping(comparison.get("baseline"), "baseline")
    candidate = _mapping(comparison.get("candidate"), "candidate")
    same_panel = bool(comparison.get("overall_scores_are_same_panel"))
    lines = [
        "# QFBench Run Comparison",
        "",
        (
            "Overall scores use the same task panels."
            if same_panel
            else "Overall scores use different task panels; treat them as contextual, not paired estimates."
        ),
        "",
        "## Run Summary",
        "",
        "| Metric | Baseline | Candidate |",
        "| --- | ---: | ---: |",
        f"| Run ID | {baseline['run_id']} | {candidate['run_id']} |",
        f"| Iterations | {baseline['n_iters']} | {candidate['n_iters']} |",
        f"| Optimize tasks | {baseline['optimize_task_count']} | {candidate['optimize_task_count']} |",
        f"| Held-out tasks | {baseline['held_out_task_count']} | {candidate['held_out_task_count']} |",
        f"| Optimize seed overall | {_format_score(baseline['optimize_seed_overall'])} | {_format_score(candidate['optimize_seed_overall'])} |",
        f"| Optimize final overall | {_format_score(baseline['optimize_final_overall'])} | {_format_score(candidate['optimize_final_overall'])} |",
        f"| Held-out seed overall | {_format_score(baseline['held_out_seed_overall'])} | {_format_score(candidate['held_out_seed_overall'])} |",
        f"| Held-out final overall | {_format_score(baseline['held_out_final_overall'])} | {_format_score(candidate['held_out_final_overall'])} |",
        f"| Held-out delta | {_format_score(baseline['held_out_delta'])} | {_format_score(candidate['held_out_delta'])} |",
        f"| Kept / rolled back | {baseline['n_kept']} / {baseline['n_rolled_back']} | {candidate['n_kept']} / {candidate['n_rolled_back']} |",
        f"| One binary held-out task (task mean) | {_format_score(baseline['held_out_task_mean_single_binary_sensitivity'])} | {_format_score(candidate['held_out_task_mean_single_binary_sensitivity'])} |",
        "",
        "## Shared Optimize Seed Tasks",
        "",
        "| Task | Baseline | Candidate | Delta |",
        "| --- | ---: | ---: | ---: |",
    ]
    shared_seed = comparison.get("shared_optimize_seed", ())
    if shared_seed:
        for row in shared_seed:
            lines.append(
                f"| {row['task_id']} | {_format_score(row['baseline_reward'])} | "
                f"{_format_score(row['candidate_reward'])} | {_format_score(row['delta'])} |"
            )
    else:
        lines.append("| _No shared tasks_ | - | - | - |")

    lines.extend([
        "",
        "## Shared Held-Out Tasks",
        "",
        "| Task | Baseline seed | Baseline final | Candidate seed | Candidate final |",
        "| --- | ---: | ---: | ---: | ---: |",
    ])
    shared_held = comparison.get("shared_held_out", ())
    if shared_held:
        for row in shared_held:
            lines.append(
                f"| {row['task_id']} | {_format_score(row['baseline_seed'])} | "
                f"{_format_score(row['baseline_final'])} | {_format_score(row['candidate_seed'])} | "
                f"{_format_score(row['candidate_final'])} |"
            )
    else:
        lines.append("| _No shared tasks_ | - | - | - | - |")
    lines.append("")
    return "\n".join(lines)
