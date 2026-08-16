#!/usr/bin/env python3
"""Select one task-only or history-enabled view from a breadth corpus."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.component_experience import build_breadth_evolver_view  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--task-key", required=True)
    parser.add_argument(
        "--arm", choices=("task-only", "history-enabled"), required=True
    )
    args = parser.parse_args()
    result = build_breadth_evolver_view(
        corpus_root=args.corpus,
        destination=args.destination,
        task_key=args.task_key,
        include_component_history=args.arm == "history-enabled",
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
