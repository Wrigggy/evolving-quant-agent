#!/usr/bin/env python3
"""Materialize the repository-pinned QFBench snapshot in an explicit cache."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.benchmarks.qfbench import default_manifest_path, materialize_qfbench_snapshot


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path, help="dedicated QFBench cache directory")
    parser.add_argument("--manifest", type=Path, default=default_manifest_path())
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--task", action="append", dest="tasks", help="sparse-fetch one task")
    scope.add_argument("--full", action="store_true", help="fetch all 86 task worktree files")
    parser.add_argument(
        "--force",
        action="store_true",
        help="discard tracked edits only in a cache created by this script",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest = json.loads(args.manifest.read_text())
    if args.full:
        task_ids = None
    elif args.tasks:
        task_ids = tuple(args.tasks)
    else:
        task_ids = tuple(
            item["task_id"]
            for split in ("optimize", "held_out")
            for item in manifest["pilot"][split]
        )
    root = materialize_qfbench_snapshot(
        manifest["repository_url"],
        args.destination,
        manifest["commit"],
        force=args.force,
        task_ids=task_ids,
    )
    scope_label = "full" if task_ids is None else f"pilot sparse ({len(task_ids)} tasks)"
    print(f"QFBench {manifest['commit']} materialized at {root} [{scope_label}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
