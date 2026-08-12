#!/usr/bin/env python3
"""Replace incomplete H0 tasks with measured retries for search diagnostics."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _read(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} is not a JSON object")
    return value


def _copy_run(source: Path, destination: Path) -> None:
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns("*.tar"),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-run", type=Path, required=True)
    parser.add_argument("--replacement-run", type=Path, action="append", required=True)
    parser.add_argument("--output-run", type=Path, required=True)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    base = args.base_run.expanduser().resolve()
    replacements = [path.expanduser().resolve() for path in args.replacement_run]
    output = args.output_run.expanduser().resolve()
    if output.exists():
        raise SystemExit(f"refusing existing output {output}")
    _copy_run(base, output)

    preflight = _read(output / "H0-PREFLIGHT.json")
    result = _read(output / "H0-RESULT.json")
    task_ids = [str(value) for value in preflight["task_ids"]]
    attempts = {
        str(row["task_id"]): dict(row)
        for row in result["attempts"]
        if isinstance(row, dict)
    }
    scores = {
        str(row["task_id"]): dict(row)
        for row in result["score_summary"]["scores"]
        if isinstance(row, dict)
    }
    costs = [dict(result["cost_audit"])]
    routes = [dict(result["route_evidence"])]
    replacement_sources: list[dict[str, object]] = []

    for source in replacements:
        replacement = _read(source / "H0-RESULT.json")
        rows = replacement.get("attempts")
        replacement_scores = replacement.get("score_summary", {}).get("scores")
        if not isinstance(rows, list) or not isinstance(replacement_scores, list):
            raise ValueError(f"replacement {source} lacks attempts or scores")
        for row in rows:
            if not isinstance(row, dict) or str(row.get("task_id")) not in task_ids:
                raise ValueError(f"replacement {source} contains an unexpected task")
            task_id = str(row["task_id"])
            attempt_id = str(row["attempt_id"])
            source_attempt = source / "attempts" / attempt_id
            destination_attempt = output / "attempts" / attempt_id
            if not source_attempt.is_dir():
                raise ValueError(f"replacement attempt is missing: {source_attempt}")
            if not destination_attempt.exists():
                _copy_run(source_attempt, destination_attempt)
            attempts[task_id] = dict(row)
        for row in replacement_scores:
            if isinstance(row, dict) and str(row.get("task_id")) in task_ids:
                scores[str(row["task_id"])] = dict(row)
        costs.append(dict(replacement["cost_audit"]))
        routes.append(dict(replacement["route_evidence"]))
        replacement_sources.append(
            {"run": source.name, "task_ids": [str(row["task_id"]) for row in rows]}
        )

    if set(attempts) != set(task_ids) or set(scores) != set(task_ids):
        raise ValueError("stitched diagnostic run does not cover the full task panel")
    for task_id, row in attempts.items():
        families = row.get("answer_free_evidence", {}).get("property_families")
        if not isinstance(families, dict):
            raise ValueError(f"stitched task {task_id} lacks property-family evidence")

    ordered_attempts = [attempts[task_id] for task_id in task_ids]
    ordered_scores = [scores[task_id] for task_id in task_ids]
    rewards = {task_id: float(scores[task_id]["reward"]) for task_id in task_ids}
    result["attempts"] = ordered_attempts
    result["score_summary"] = {
        "task_rewards": rewards,
        "domain_scores": {
            str(row["domain"]): float(row["reward"]) for row in ordered_scores
        },
        "task_mean": sum(rewards.values()) / len(rewards),
        "overall": sum(rewards.values()) / len(rewards),
        "scores": ordered_scores,
    }
    additive = (
        "attempt_count",
        "completed_request_count",
        "input_tokens",
        "logical_request_count",
        "other_nonaccepted_request_count",
        "output_tokens",
        "rate_limited_retry_count",
        "request_count",
        "superseded_attempt_count",
        "total_tokens",
        "unreconciled_attempt_count",
        "unreconciled_request_count",
    )
    combined_cost = dict(costs[0])
    for key in additive:
        combined_cost[key] = sum(int(value.get(key) or 0) for value in costs)
    combined_cost["provider_cost_usd"] = format(
        sum(float(value["provider_cost_usd"]) for value in costs), ".10f"
    )
    combined_cost["cost_complete"] = all(value.get("cost_complete") is True for value in costs)
    result["cost_audit"] = combined_cost
    combined_route = dict(routes[0])
    combined_route["requests"] = [
        row for route in routes for row in route.get("requests", [])
    ]
    combined_route["generation_metadata"] = [
        row for route in routes for row in route.get("generation_metadata", [])
    ]
    result["route_evidence"] = combined_route
    result["claim_boundary"] = (
        "stitched diagnostic search parent; not an independent benchmark sample"
    )
    result["diagnostic_sources"] = {
        "base_run": base.name,
        "replacements": replacement_sources,
    }
    # This legacy field name is consumed by the existing EvaluationRef loader.
    # An engineering diagnostic needs only a unique, path-safe evaluation ID;
    # do not create a new digest identity for it.
    result["evaluation_identity_sha256"] = output.name
    (output / "H0-RESULT.json").write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    if not args.quiet:
        print(
            json.dumps(
                {
                    "output_run": str(output),
                    "claim_boundary": result["claim_boundary"],
                    "diagnostic_sources": result["diagnostic_sources"],
                    "task_rewards": result["score_summary"]["task_rewards"],
                    "request_count": result["cost_audit"]["request_count"],
                    "total_tokens": result["cost_audit"]["total_tokens"],
                    "provider_cost_usd": result["cost_audit"]["provider_cost_usd"],
                },
                sort_keys=True,
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
