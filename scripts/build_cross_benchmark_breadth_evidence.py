#!/usr/bin/env python3
"""Build the no-model experience corpus for one breadth-canary benchmark slice."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.component_experience import build_cross_benchmark_experience  # noqa: E402


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--plan",
        type=Path,
        default=Path("data/breadth/BREADTH_CANARY.json"),
    )
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--benchmark", choices=("qfbench", "quantcodeeval", "all"), default="all")
    parser.add_argument("--qfbench-evidence-root", type=Path)
    parser.add_argument("--quantcodeeval-evidence-root", type=Path)
    parser.add_argument(
        "--task",
        dest="task_keys",
        action="append",
        help="optional benchmark:task_id selector; may be repeated",
    )
    parser.add_argument(
        "--component-ledger",
        type=Path,
        default=Path("data/quantcodeeval/COMPONENT_EVIDENCE_CANARY.json"),
    )
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    tasks = [
        row
        for row in plan["tasks"]
        if args.benchmark == "all" or row["benchmark"] == args.benchmark
    ]
    if args.task_keys:
        selected = set(args.task_keys)
        tasks = [
            row
            for row in tasks
            if f"{row['benchmark']}:{row['task_id']}" in selected
        ]
        found = {f"{row['benchmark']}:{row['task_id']}" for row in tasks}
        if found != selected:
            raise ValueError(f"task selectors not found in plan: {sorted(selected - found)}")
    result = build_cross_benchmark_experience(
        destination=args.destination,
        task_profiles=tasks,
        component_ledger_path=args.component_ledger,
        qfbench_evidence_root=args.qfbench_evidence_root,
        quantcodeeval_evidence_root=args.quantcodeeval_evidence_root,
        component_portability=plan.get("component_portability", {}),
        relevant_component_limit=plan["limits"]["max_relevant_components_per_task"],
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
