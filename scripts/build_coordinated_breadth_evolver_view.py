#!/usr/bin/env python3
"""Build a bounded multi-task Evolver view with one selectable Worker probe."""

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
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--task-key", action="append", required=True)
    parser.add_argument(
        "--arm",
        choices=("task-only", "history-enabled"),
        default="history-enabled",
    )
    args = parser.parse_args(argv)
    result = build_coordinated_evolver_view(
        corpus_root=args.corpus,
        destination=args.destination,
        task_keys=args.task_key,
        include_component_history=args.arm == "history-enabled",
    )
    print(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
