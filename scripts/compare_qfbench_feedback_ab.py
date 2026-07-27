#!/usr/bin/env python3
"""Audit and compare completed matched QFBench Control/Rich 30x5 runs."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class ComparisonError(ValueError):
    """A run is incomplete, contaminated, or not matched to its comparator."""


_PRIVATE_MARKERS = (
    "PRIVATE_VERIFIER_CANARY",
    "DO_NOT_EXPOSE",
    "OFFICIAL_SOLUTION_CANARY",
)
_MATCHED_IDENTITIES = (
    "benchmark_commit",
    "task_manifest_digest",
    "public_rubric_digest",
    "verifier_mapping_digest",
    "admission_policy_digest",
    "model_identity",
    "seed_digest",
    "template_identity_digest",
)


def _json(path: Path, label: str) -> dict:
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ComparisonError(f"cannot read {label} {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ComparisonError(f"{label} must be an object: {path}")
    return payload


def _score_attempts(run: Path) -> tuple[tuple[Path, dict, dict], ...]:
    attempts = []
    for score_path in sorted(run.glob("attempts/*/completed-score.json")):
        attempt_path = score_path.with_name("attempt.json")
        if not attempt_path.is_file():
            raise ComparisonError(f"completed score has no attempt identity: {score_path}")
        attempts.append((score_path.parent, _json(attempt_path, "attempt"), _json(score_path, "score")))
    return tuple(attempts)


def _require_lifecycle(path: Path, *, label: str) -> dict:
    if not path.is_file():
        raise ComparisonError(f"missing {label} lifecycle: {path}")
    payload = _json(path, f"{label} lifecycle")
    if payload.get("cleaned_up") is not True:
        raise ComparisonError(
            f"unfinished exact sandbox ID {payload.get('sandbox_id')} in {path}"
        )
    return payload


def _scan_proposer_surface(run: Path) -> None:
    roots = (run / "evidence", run / "evolutions", run / "workers")
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {
                ".json", ".jsonl", ".md", ".py", ".txt", ".yaml", ".yml"
            }:
                continue
            text = path.read_text(errors="replace")
            marker = next((item for item in _PRIVATE_MARKERS if item in text), None)
            if marker:
                raise ComparisonError(
                    f"private canary {marker!r} found on proposer surface: {path}"
                )


def _trajectory_auc(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return sum((left + right) / 2 for left, right in zip(values, values[1:]))


def _edit_categories(run: Path) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for path in sorted(run.glob("iteration-*/edit.diff")):
        files = re.findall(r"^\+\+\+ b/(.+)$", path.read_text(), flags=re.MULTILINE)
        categories = set()
        for name in files:
            if name == "systemprompt.md":
                categories.add("prompt")
            elif name == "agent.yaml":
                categories.add("agent_config")
            elif name.startswith("tool_descriptions/"):
                categories.add("tool_description")
            elif name.startswith("tools/"):
                categories.add("local_tool")
            else:
                categories.add("other_harness")
        for category in categories or {"no_text_edit"}:
            counts[category] += 1
    return dict(sorted(counts.items()))


def _token_total(value: Any) -> int:
    if isinstance(value, dict):
        direct = value.get("total_tokens")
        if isinstance(direct, int) and not isinstance(direct, bool):
            return direct
        return sum(_token_total(item) for item in value.values())
    if isinstance(value, list):
        return sum(_token_total(item) for item in value)
    return 0


def _reward(value: Any, *, label: str) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
        or not 0.0 <= float(value) <= 1.0
    ):
        raise ComparisonError(f"{label} must be a finite reward in [0, 1]")
    return float(value)


def _checkpoint_summary(
    attempts: tuple[tuple[Path, dict, dict], ...],
    *,
    checkpoint: str,
    split: str,
    expected_tasks: int,
) -> dict:
    selected = [
        (attempt, score)
        for _, attempt, score in attempts
        if attempt.get("checkpoint") == checkpoint
    ]
    if len(selected) != expected_tasks:
        raise ComparisonError(
            f"{checkpoint} requires {expected_tasks} official scores, found {len(selected)}"
        )
    task_rewards: dict[str, float] = {}
    domain_rewards: defaultdict[str, list[float]] = defaultdict(list)
    for attempt, score in selected:
        if attempt.get("split") != split:
            raise ComparisonError(
                f"{checkpoint} contains non-{split} attempt {attempt.get('attempt_id')}"
            )
        attempt_task = str(attempt.get("task_id", ""))
        score_task = str(score.get("task_id", ""))
        if not attempt_task or attempt_task != score_task:
            raise ComparisonError(
                f"{checkpoint} attempt/score task identity mismatch: "
                f"{attempt_task!r}/{score_task!r}"
            )
        if score_task in task_rewards:
            raise ComparisonError(f"{checkpoint} duplicates task {score_task}")
        domain = str(score.get("domain", ""))
        if not domain:
            raise ComparisonError(f"{checkpoint} task {score_task} has no domain")
        reward = _reward(
            score.get("reward"), label=f"{checkpoint} task {score_task} reward"
        )
        task_rewards[score_task] = reward
        domain_rewards[domain].append(reward)
    domain_scores = {
        domain: sum(values) / len(values)
        for domain, values in sorted(domain_rewards.items())
    }
    return {
        "task_rewards": dict(sorted(task_rewards.items())),
        "domain_scores": domain_scores,
        "task_mean": sum(task_rewards.values()) / len(task_rewards),
        "overall": sum(domain_scores.values()) / len(domain_scores),
    }


def _audit_summary(summary: Any, actual: dict, *, label: str) -> None:
    if not isinstance(summary, dict):
        raise ComparisonError(f"{label} summary must be an object")
    for field in ("task_rewards", "domain_scores"):
        reported = summary.get(field)
        if not isinstance(reported, dict):
            raise ComparisonError(f"{label} summary {field} must be an object")
        if set(map(str, reported)) != set(actual[field]):
            raise ComparisonError(f"{label} summary {field} identity mismatch")
        for key, actual_value in actual[field].items():
            reported_value = _reward(
                reported.get(key), label=f"{label} summary {field}.{key}"
            )
            if not math.isclose(
                reported_value, actual_value, rel_tol=0.0, abs_tol=1e-12
            ):
                raise ComparisonError(
                    f"{label} summary {field}.{key} mismatch: "
                    f"{reported_value} != {actual_value}"
                )
    for field in ("task_mean", "overall"):
        reported_value = _reward(
            summary.get(field), label=f"{label} summary {field}"
        )
        if not math.isclose(
            reported_value, actual[field], rel_tol=0.0, abs_tol=1e-12
        ):
            raise ComparisonError(
                f"{label} summary {field} mismatch: "
                f"{reported_value} != {actual[field]}"
            )


def audit_run(run_dir: str | Path, *, expected_arm: str) -> dict:
    run = Path(run_dir).resolve()
    resume = _json(run / "resume.json", "resume checkpoint")
    result = _json(run / "result.json", "result")
    if resume.get("schema_version") != 2 or result.get("schema_version") != 2:
        raise ComparisonError("Control/Rich comparison requires checkpoint schema 2")
    if resume.get("phase") != "complete" or resume.get("pending_candidate") is not None:
        raise ComparisonError(f"run is incomplete or pending: {run}")
    if resume.get("n_iters") != 5 or len(resume.get("records", [])) != 5:
        raise ComparisonError("comparison requires exactly five completed iteration records")
    if resume.get("arm") != expected_arm or result.get("arm") != expected_arm:
        raise ComparisonError(
            f"expected {expected_arm} arm, found {resume.get('arm')}/{result.get('arm')}"
        )
    if resume.get("identity") != result.get("identity"):
        raise ComparisonError("resume/result immutable identities differ")
    final_worker = (run / str(resume.get("incumbent_worker", ""))).resolve()
    if not final_worker.is_dir() or Path(result.get("final_worker_dir", "")).resolve() != final_worker:
        raise ComparisonError("final incumbent worker is missing or inconsistent")

    attempts = _score_attempts(run)
    if len(attempts) != 140:
        raise ComparisonError(
            f"30x5 completion requires 140 unique official scores, found {len(attempts)}"
        )
    attempt_ids = [str(attempt.get("attempt_id", "")) for _, attempt, _ in attempts]
    if not all(attempt_ids) or len(attempt_ids) != len(set(attempt_ids)):
        raise ComparisonError("official attempt IDs are missing or duplicated")
    checkpoints = Counter(str(attempt.get("checkpoint", "")) for _, attempt, _ in attempts)
    expected_checkpoints = {
        "seed-optimize": 20,
        **{f"iteration-{index}-candidate": 20 for index in range(1, 6)},
        "seed-held-out": 10,
        "final-held-out": 10,
    }
    if dict(checkpoints) != expected_checkpoints:
        raise ComparisonError(
            f"official checkpoint schedule mismatch: {dict(checkpoints)}"
        )
    optimize_ids = {
        attempt["task_id"] for _, attempt, _ in attempts
        if attempt.get("split") == "optimize"
    }
    held_out_ids = {
        attempt["task_id"] for _, attempt, _ in attempts
        if attempt.get("split") == "held_out"
    }
    if len(optimize_ids) != 20 or len(held_out_ids) != 10 or optimize_ids & held_out_ids:
        raise ComparisonError("run does not contain an isolated 20/10 task split")

    lifecycle_ids = set()
    timeouts = 0
    for attempt_dir, _, score in attempts:
        worker = _require_lifecycle(
            attempt_dir / "worker-sandbox-lifecycle.json", label="worker"
        )
        lifecycle_ids.add(worker["sandbox_id"])
        tags = {str(tag) for tag in score.get("diagnostic_tags", [])}
        if "timeout" in tags:
            timeouts += 1
        else:
            verifier = _require_lifecycle(
                attempt_dir / "verifier" / "verifier-sandbox-lifecycle.json",
                label="verifier",
            )
            lifecycle_ids.add(verifier["sandbox_id"])
    evolver_lifecycles = sorted(
        (run / "evolutions").glob("iteration-*/*-sandbox-lifecycle.json")
    )
    if len(evolver_lifecycles) != 5:
        raise ComparisonError(
            f"expected five successful evolver lifecycles, found {len(evolver_lifecycles)}"
        )
    for path in evolver_lifecycles:
        lifecycle = _require_lifecycle(path, label="evolver")
        lifecycle_ids.add(lifecycle["sandbox_id"])
    all_lifecycles = sorted(run.rglob("*-sandbox-lifecycle.json"))
    for path in all_lifecycles:
        _require_lifecycle(path, label="sandbox")
    _scan_proposer_surface(run)

    trajectory = [float(value) for value in result.get("optimize_trajectory", [])]
    if len(trajectory) < 1 or not all(math.isfinite(value) for value in trajectory):
        raise ComparisonError("optimize trajectory is missing or non-finite")
    records = resume["records"]
    evidence_reads = 0
    tool_errors = 0
    for path in sorted((run / "evolutions").glob("iteration-*/access-summary.json")):
        evidence_reads += int(_json(path, "access summary").get("records", 0))
    for path in sorted((run / "evolutions").glob("iteration-*/summary.json")):
        tool_errors += int(_json(path, "evolver summary").get("tool_errors", 0))
    wall_seconds = 0.0
    for path in sorted(run.glob("attempts/*/worker-execution.json")):
        wall_seconds += float(
            _json(path, "worker execution").get("summary", {}).get("secs", 0.0)
        )
    for path in sorted((run / "evolutions").glob("iteration-*/summary.json")):
        wall_seconds += float(_json(path, "evolver summary").get("secs", 0.0))

    seed_rewards: dict[str, float] = {}
    seed_domains: defaultdict[str, list[float]] = defaultdict(list)
    for _, attempt, score in attempts:
        if attempt.get("checkpoint") != "seed-optimize":
            continue
        reward = float(score["reward"])
        seed_rewards[str(score["task_id"])] = reward
        seed_domains[str(score["domain"])].append(reward)
    final_summary = result.get("optimize_final", {})
    held_out_seed_summary = _checkpoint_summary(
        attempts,
        checkpoint="seed-held-out",
        split="held_out",
        expected_tasks=10,
    )
    held_out_final_summary = _checkpoint_summary(
        attempts,
        checkpoint="final-held-out",
        split="held_out",
        expected_tasks=10,
    )
    _audit_summary(
        result.get("held_out_seed"),
        held_out_seed_summary,
        label="held-out seed",
    )
    _audit_summary(
        result.get("held_out_final"),
        held_out_final_summary,
        label="held-out final",
    )
    held_out_seed = held_out_seed_summary["overall"]
    held_out_final = held_out_final_summary["overall"]
    final_rewards = {
        str(key): float(value)
        for key, value in final_summary.get("task_rewards", {}).items()
    }
    task_deltas = {
        task_id: final_rewards[task_id] - seed_rewards[task_id]
        for task_id in sorted(seed_rewards)
        if task_id in final_rewards
    }
    seed_domain_scores = {
        domain: sum(values) / len(values)
        for domain, values in seed_domains.items()
    }
    final_domains = {
        str(key): float(value)
        for key, value in final_summary.get("domain_scores", {}).items()
    }
    domain_deltas = {
        domain: final_domains[domain] - seed_domain_scores[domain]
        for domain in sorted(seed_domain_scores)
        if domain in final_domains
    }
    total_tokens = _token_total(resume.get("costs", []))
    candidate_trajectory = [trajectory[0], *(
        float(record.get("candidate_overall", trajectory[0])) for record in records
    )]
    improved_tasks = sum(delta > 0 for delta in task_deltas.values())
    regressed_tasks = sum(delta < 0 for delta in task_deltas.values())
    kept_iterations = [
        int(record["iteration"]) for record in records if record.get("kept")
    ]
    edit_categories = _edit_categories(run)
    return {
        "run_id": resume.get("run_id"),
        "arm": expected_arm,
        "identity": resume["identity"],
        "official_scores": len(attempts),
        "worker_lifecycles": len(attempts),
        "verifier_lifecycles": len(attempts) - timeouts,
        "evolver_lifecycles": len(evolver_lifecycles),
        "all_lifecycles_clean": len(all_lifecycles),
        "unique_sandbox_ids": len(lifecycle_ids),
        "trajectory": trajectory,
        "trajectory_auc": _trajectory_auc(trajectory),
        "candidate_trajectory": candidate_trajectory,
        "candidate_score_auc": _trajectory_auc(candidate_trajectory),
        "optimize_seed": trajectory[0],
        "optimize_final": float(final_summary["overall"]),
        "optimize_gain": float(final_summary["overall"]) - trajectory[0],
        "held_out_seed": float(held_out_seed),
        "held_out_final": float(held_out_final),
        "held_out_delta": float(held_out_final) - float(held_out_seed),
        "keep_rate": sum(bool(record.get("kept")) for record in records) / 5,
        "first_kept_iteration": kept_iterations[0] if kept_iterations else None,
        "kept_iterations": len(kept_iterations),
        "rolled_back_iterations": 5 - len(kept_iterations),
        "admission_rejections": sum(
            not bool(record.get("admitted", True)) for record in records
        ),
        "domain_deltas": domain_deltas,
        "task_deltas": task_deltas,
        "improved_tasks": improved_tasks,
        "regressed_tasks": regressed_tasks,
        "unchanged_tasks": len(task_deltas) - improved_tasks - regressed_tasks,
        "edit_categories": edit_categories,
        "custom_tool_edit_iterations": edit_categories.get("local_tool", 0),
        "evidence_read_records": evidence_reads,
        "timeouts": timeouts,
        "evolver_tool_errors": tool_errors,
        "recorded_execution_seconds": wall_seconds or None,
        "total_tokens": total_tokens or None,
        "monetary_cost": None,
        "monetary_cost_reason": "provider/E2B billing not exposed in run artifacts",
    }


def _historical(path: str | Path) -> dict:
    root = Path(path).resolve()
    result = _json(root / "result.json", "historical result")
    validity = _json(root / "validity-audit.json", "historical validity audit")
    run_id = str(result.get("run_id", ""))
    if not run_id or validity.get("run_id") != run_id or root.name != run_id:
        raise ComparisonError(
            "historical result, validity audit, and directory run IDs differ"
        )
    optimize_checkpoints = {
        "seed-optimize",
        *(f"iteration-{index}-candidate" for index in range(1, 6)),
    }
    expected_checkpoints = {
        "delta-hedging-pnl-simulation": optimize_checkpoints,
        "swap-curve-bootstrap-ois": optimize_checkpoints,
        "form4-cross-sectional-sale-pressure": {
            "seed-held-out",
            "final-held-out",
        },
    }
    expected_counts = {
        task_id: len(checkpoints)
        for task_id, checkpoints in expected_checkpoints.items()
    }
    score_validity = validity.get("score_validity")
    if not isinstance(score_validity, dict):
        raise ComparisonError("historical validity audit has no score_validity object")
    affected_count = score_validity.get("affected_attempts")
    reported_counts = score_validity.get("affected_tasks")
    if (
        not isinstance(affected_count, int)
        or isinstance(affected_count, bool)
        or affected_count != sum(expected_counts.values())
    ):
        raise ComparisonError("historical affected attempt count is inconsistent")
    if reported_counts != expected_counts:
        raise ComparisonError("historical affected task counts are inconsistent")
    contaminated = []
    for evaluation_path in sorted(root.glob("evaluations/*.json")):
        evaluation = _json(evaluation_path, "historical evaluation")
        if evaluation.get("run_id") != run_id:
            raise ComparisonError(
                f"historical evaluation run ID mismatch: {evaluation_path}"
            )
        checkpoint = str(evaluation.get("checkpoint", ""))
        split = str(evaluation.get("split", ""))
        summary = evaluation.get("summary")
        scores = summary.get("scores") if isinstance(summary, dict) else None
        if not isinstance(scores, list):
            raise ComparisonError(
                f"historical evaluation has no score list: {evaluation_path}"
            )
        for score in scores:
            if not isinstance(score, dict):
                raise ComparisonError(
                    f"historical evaluation contains non-object score: {evaluation_path}"
                )
            task_id = str(score.get("task_id", ""))
            if task_id not in expected_checkpoints:
                continue
            if checkpoint not in expected_checkpoints[task_id]:
                raise ComparisonError(
                    f"historical affected task {task_id} appears at unexpected {checkpoint}"
                )
            expected_split = "held_out" if "held-out" in checkpoint else "optimize"
            if split != expected_split:
                raise ComparisonError(
                    f"historical affected task {task_id} has wrong split at {checkpoint}"
                )
            reward = _reward(
                score.get("reward"),
                label=f"historical {checkpoint} {task_id} reward",
            )
            if reward != 0.0:
                raise ComparisonError(
                    f"historical contaminated score is not zero: {checkpoint}/{task_id}"
                )
            log_uri = str(score.get("log_uri", "")).replace("\\", "/")
            match = re.search(r"(?:^|/)attempts/([^/]+)/", log_uri)
            if not match:
                raise ComparisonError(
                    f"historical score has no attempt identity: {checkpoint}/{task_id}"
                )
            attempt_id = match.group(1)
            if not (root / "attempts" / attempt_id).is_dir():
                raise ComparisonError(
                    f"historical score references missing attempt {attempt_id}"
                )
            contaminated.append({
                "attempt_id": attempt_id,
                "task_id": task_id,
                "checkpoint": checkpoint,
                "split": split,
                "reward": reward,
            })
    actual_pairs = Counter(
        (record["task_id"], record["checkpoint"]) for record in contaminated
    )
    expected_pairs = Counter(
        (task_id, checkpoint)
        for task_id, checkpoints in expected_checkpoints.items()
        for checkpoint in checkpoints
    )
    if actual_pairs != expected_pairs:
        raise ComparisonError("historical contaminated checkpoint records are incomplete")
    attempt_ids = [record["attempt_id"] for record in contaminated]
    if len(attempt_ids) != len(set(attempt_ids)):
        raise ComparisonError("historical contaminated attempt IDs are duplicated")
    contaminated.sort(
        key=lambda record: (record["task_id"], record["checkpoint"])
    )
    return {
        "run_id": run_id,
        "optimize_trajectory": result.get("optimize_trajectory"),
        "optimize_final": result.get("optimize_final", {}).get("overall"),
        "causal_comparator": False,
        "provisional": True,
        "contaminated_record_count": len(contaminated),
        "contaminated_records": contaminated,
        "annotation": (
            "Prompt-only historical context; not a causal arm. The 2026-07-25 "
            f"run also contains {len(contaminated)} verifier-contaminated zeros "
            "documented separately."
        ),
    }


def compare_runs(
    control_dir: str | Path,
    rich_dir: str | Path,
    historical_dir: str | Path | None = None,
) -> dict:
    control = audit_run(control_dir, expected_arm="control")
    rich = audit_run(rich_dir, expected_arm="rich")
    mismatched = [
        key for key in _MATCHED_IDENTITIES
        if control["identity"].get(key) != rich["identity"].get(key)
    ]
    if mismatched:
        raise ComparisonError(f"matched-arm immutable identity mismatch: {mismatched}")
    output = {
        "schema_version": 1,
        "causal_comparison": True,
        "completion": {
            "control": {
                "official_scores": control["official_scores"],
                "all_lifecycles_clean": control["all_lifecycles_clean"],
            },
            "rich": {
                "official_scores": rich["official_scores"],
                "all_lifecycles_clean": rich["all_lifecycles_clean"],
            },
        },
        "primary": {
            "RichFeedbackGain": (
                rich["optimize_gain"] - control["optimize_gain"]
            ),
            "final_optimize_gap": (
                rich["optimize_final"] - control["optimize_final"]
            ),
            "rich_adaptation_gain": rich["optimize_gain"],
            "control_adaptation_gain": control["optimize_gain"],
            "difference_in_adaptation_gain": (
                rich["optimize_gain"] - control["optimize_gain"]
            ),
        },
        "arms": {"control": control, "rich": rich},
        "historical": _historical(historical_dir) if historical_dir else None,
    }
    return output


def _markdown(comparison: dict) -> str:
    control = comparison["arms"]["control"]
    rich = comparison["arms"]["rich"]
    primary = comparison["primary"]
    lines = [
        "# QFBench Full-Harness Feedback A/B",
        "",
        "Both arms passed the preregistered 30-task, five-iteration completion audit.",
        "",
        "| Metric | Control | Rich |",
        "|---|---:|---:|",
        f"| Optimize seed | {control['optimize_seed']:.6f} | {rich['optimize_seed']:.6f} |",
        f"| Optimize final | {control['optimize_final']:.6f} | {rich['optimize_final']:.6f} |",
        f"| Adaptation gain | {control['optimize_gain']:.6f} | {rich['optimize_gain']:.6f} |",
        f"| Held-out seed | {control['held_out_seed']:.6f} | {rich['held_out_seed']:.6f} |",
        f"| Held-out final | {control['held_out_final']:.6f} | {rich['held_out_final']:.6f} |",
        f"| Held-out delta | {control['held_out_delta']:.6f} | {rich['held_out_delta']:.6f} |",
        f"| Trajectory AUC | {control['trajectory_auc']:.6f} | {rich['trajectory_auc']:.6f} |",
        f"| Keep rate | {control['keep_rate']:.1%} | {rich['keep_rate']:.1%} |",
        f"| Evidence reads | {control['evidence_read_records']} | {rich['evidence_read_records']} |",
        f"| Timeouts | {control['timeouts']} | {rich['timeouts']} |",
        "",
        f"Primary RichFeedbackGain: **{primary['RichFeedbackGain']:.6f}**.",
        "",
        "Held-out seed/final results are secondary transfer checks and were not exposed to either evolver.",
    ]
    if comparison.get("historical"):
        lines.extend([
            "",
            "## Historical context",
            "",
            comparison["historical"]["annotation"],
        ])
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control", type=Path, required=True)
    parser.add_argument("--rich", type=Path, required=True)
    parser.add_argument("--historical", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    comparison = compare_runs(args.control, args.rich, args.historical)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "comparison.json"
    markdown_path = args.output_dir / "comparison.md"
    json_path.write_text(json.dumps(comparison, sort_keys=True, indent=2) + "\n")
    markdown_path.write_text(_markdown(comparison))
    print(json_path)
    print(markdown_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
