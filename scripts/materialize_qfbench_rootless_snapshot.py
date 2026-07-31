#!/usr/bin/env python3
"""Plan or materialize role-separated QFBench inputs for rootless Docker."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.benchmarks.qfbench import (
    QFBenchConfigError,
    materialize_qfbench_role_snapshot,
    plan_qfbench_role_snapshot,
)


OFFICIAL_REPOSITORY = "https://github.com/QF-Bench/QuantitativeFinance-Bench.git"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-tree", type=Path, required=True)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--task-id", action="append", dest="task_ids")
    selection.add_argument("--task-panel-manifest", type=Path)
    parser.add_argument("--repository-url", default=OFFICIAL_REPOSITORY)
    parser.add_argument("--commit")
    parser.add_argument("--public-root", type=Path, required=True)
    parser.add_argument("--trusted-root", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan-only", action="store_true")
    mode.add_argument("--apply", action="store_true")
    return parser


def _panel_contract(path: Path) -> tuple[str, str, tuple[str, ...]]:
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise QFBenchConfigError(f"cannot load task panel manifest {path}: {exc}") from exc
    if payload.get("schema_version") != 1:
        raise QFBenchConfigError("unsupported task panel manifest schema")
    repository_url = payload.get("repository_url")
    commit = payload.get("commit")
    pilot = payload.get("pilot")
    baseline = payload.get("baseline")
    if not isinstance(repository_url, str) or not repository_url:
        raise QFBenchConfigError("task panel repository_url must be non-empty")
    if not isinstance(commit, str) or not commit:
        raise QFBenchConfigError("task panel commit must be non-empty")
    if isinstance(pilot, dict) == isinstance(baseline, dict):
        raise QFBenchConfigError(
            "task panel must contain exactly one of pilot or baseline splits"
        )
    if isinstance(pilot, dict):
        entries = [*pilot.get("optimize", ()), *pilot.get("held_out", ())]
    else:
        entries = [*baseline.get("primary", ()), *baseline.get("diagnostic", ())]
    if not entries or any(not isinstance(entry, dict) for entry in entries):
        raise QFBenchConfigError("task panel splits must contain task objects")
    task_ids = tuple(str(entry.get("task_id", "")) for entry in entries)
    if any(not task_id for task_id in task_ids) or len(set(task_ids)) != len(task_ids):
        raise QFBenchConfigError("task panel task IDs must be non-empty and unique")
    return repository_url, commit, task_ids


def _arguments_contract(
    args: argparse.Namespace,
) -> tuple[str, str, tuple[str, ...]]:
    if args.task_panel_manifest is not None:
        repository_url, commit, task_ids = _panel_contract(
            args.task_panel_manifest.resolve()
        )
        if args.repository_url != OFFICIAL_REPOSITORY and args.repository_url != repository_url:
            raise QFBenchConfigError("repository URL differs from task panel manifest")
        if args.commit is not None and args.commit != commit:
            raise QFBenchConfigError("commit differs from task panel manifest")
        return repository_url, commit, task_ids
    if not args.commit:
        raise QFBenchConfigError("--commit is required with --task-id")
    return args.repository_url, args.commit, tuple(args.task_ids)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        repository_url, commit, task_ids = _arguments_contract(args)
        plan = plan_qfbench_role_snapshot(
            args.source_tree,
            repository_url=repository_url,
            commit=commit,
            task_ids=task_ids,
        )
        print(f"commit: {plan.commit}")
        print(f"tasks: {len(plan.task_ids)}")
        print(f"public files: {len(plan.public_blobs)}")
        print(f"trusted verifier files: {len(plan.trusted_verifier_blobs)}")
        print(f"denied solution files: {len(plan.denied_solution_blobs)}")
        print(f"public root: {args.public_root.resolve()}")
        print(f"trusted root: {args.trusted_root.resolve()}")
        if args.apply:
            result = materialize_qfbench_role_snapshot(
                args.source_tree,
                args.public_root,
                args.trusted_root,
                repository_url=repository_url,
                commit=commit,
                task_ids=task_ids,
            )
            print(f"materialized public: {result.public_root}")
            print(f"materialized trusted: {result.trusted_root}")
        return 0
    except QFBenchConfigError as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
