#!/usr/bin/env python3
"""Materialize selected QFBench files and verify them against a pinned Git tree."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.benchmarks.qfbench import (
    QFBenchConfigError,
    materialize_qfbench_raw_snapshot,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-tree",
        type=Path,
        required=True,
        help="local Git tree containing the pinned commit and tree objects",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        required=True,
        help="preregistered QFBench manifest selecting optimize and held-out tasks",
    )
    parser.add_argument(
        "--destination",
        type=Path,
        required=True,
        help="new dedicated QFBench cache directory; existing destinations are refused",
    )
    return parser


def _manifest_contract(path: Path) -> tuple[str, str, tuple[str, ...]]:
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise QFBenchConfigError(f"cannot load QFBench manifest {path}: {exc}") from exc
    if payload.get("schema_version") != 1:
        raise QFBenchConfigError("unsupported QFBench manifest schema")
    repository_url = payload.get("repository_url")
    commit = payload.get("commit")
    pilot = payload.get("pilot")
    if not isinstance(repository_url, str) or not repository_url:
        raise QFBenchConfigError("manifest repository_url must be non-empty")
    if not isinstance(commit, str):
        raise QFBenchConfigError("manifest commit must be a string")
    if not isinstance(pilot, dict):
        raise QFBenchConfigError("manifest must contain a pilot object")
    entries = [*pilot.get("optimize", ()), *pilot.get("held_out", ())]
    if not entries or any(not isinstance(entry, dict) for entry in entries):
        raise QFBenchConfigError("manifest pilot splits must contain task objects")
    task_ids = tuple(str(entry.get("task_id", "")) for entry in entries)
    if any(not task_id for task_id in task_ids) or len(set(task_ids)) != len(task_ids):
        raise QFBenchConfigError("manifest selected task IDs must be non-empty and unique")
    return repository_url, commit, task_ids


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repository_url, commit, task_ids = _manifest_contract(args.manifest.resolve())
    destination = materialize_qfbench_raw_snapshot(
        args.source_tree,
        args.destination,
        repository_url=repository_url,
        commit=commit,
        task_ids=task_ids,
    )
    file_count = sum(path.is_file() for path in destination.rglob("*"))
    print(f"commit: {commit}")
    print(f"tasks: {len(task_ids)}")
    print(f"files: {file_count}")
    print(f"destination: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
