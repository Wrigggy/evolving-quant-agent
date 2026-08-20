#!/usr/bin/env python3
"""Materialize every fixed task-pair view in a coordination canary panel."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qea.component_experience import build_coordinated_evolver_view  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument(
        "--arm",
        choices=("task-only", "history-enabled"),
        default="history-enabled",
    )
    args = parser.parse_args(argv)

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    pairs = plan.get("pairs")
    if not isinstance(pairs, list) or not pairs:
        raise ValueError("coordination panel has no pairs")
    destination = args.destination.expanduser().resolve()
    if destination.exists():
        raise ValueError(f"destination already exists: {destination}")
    destination.mkdir(parents=True)

    results = []
    seen_ids: set[str] = set()
    for pair in pairs:
        if not isinstance(pair, dict):
            raise ValueError("coordination pair must be an object")
        pair_id = pair.get("pair_id")
        target = pair.get("target_task_key")
        protection = pair.get("protection_task_key")
        if not all(isinstance(value, str) and value for value in (pair_id, target, protection)):
            raise ValueError("coordination pair is incomplete")
        if pair_id in seen_ids:
            raise ValueError(f"duplicate pair ID: {pair_id}")
        seen_ids.add(pair_id)
        result = build_coordinated_evolver_view(
            corpus_root=args.corpus,
            destination=destination / pair_id,
            task_keys=(target, protection),
            include_component_history=args.arm == "history-enabled",
        )
        results.append({"pair_id": pair_id, **result})

    report = {
        "schema_version": 1,
        "status": "preflight_complete",
        "pair_count": len(results),
        "arm": args.arm,
        "pairs": results,
        "model_requests": 0,
        "worker_requests": 0,
    }
    (destination / "PANEL-PREFLIGHT.json").write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
