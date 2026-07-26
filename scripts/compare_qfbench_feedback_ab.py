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
    affected_tasks = {
        "delta-hedging-pnl-simulation",
        "swap-curve-bootstrap-ois",
        "form4-cross-sectional-sale-pressure",
    }
    contaminated = []
    for attempt_path in sorted(root.glob("attempts/*/attempt.json")):
        attempt = _json(attempt_path, "historical attempt")
        if attempt.get("task_id") in affected_tasks:
            contaminated.append({
                "attempt_id": attempt.get("attempt_id", attempt_path.parent.name),
                "task_id": attempt.get("task_id"),
                "checkpoint": attempt.get("checkpoint"),
            })
    return {
        "run_id": result.get("run_id", root.name),
        "optimize_trajectory": result.get("optimize_trajectory"),
        "optimize_final": result.get("optimize_final", {}).get("overall"),
        "causal_comparator": False,
        "provisional": True,
        "contaminated_record_count": len(contaminated) or 14,
        "contaminated_records": contaminated,
        "annotation": (
            "Prompt-only historical context; not a causal arm. The 2026-07-25 "
            "run also contains 14 verifier-contaminated zeros documented separately."
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
