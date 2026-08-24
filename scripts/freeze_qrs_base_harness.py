#!/usr/bin/env python3
"""Freeze one compatible external base harness for the QRS scheduler."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.frozen_base_harness import (  # noqa: E402
    FrozenBaseHarnessError,
    build_selected_runtime,
    freeze_base_harness,
    inspect_base_harness,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate and copy one externally selected base Worker into a "
            "run-scoped frozen QRS initialization. This command runs no model, "
            "benchmark, Evolver, Reviewer, or verifier."
        )
    )
    parser.add_argument("--worker-dir", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--worker-model-route", required=True)
    parser.add_argument("--rootless-config", required=True)
    parser.add_argument("--selection-artifact-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--mutation-surface",
        action="append",
        dest="mutation_surfaces",
        help=(
            "Worker-relative declared system-prompt or SKILL.md surface. "
            "Repeat for multiple surfaces; defaults to all declared prompt/skills."
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        inspection = inspect_base_harness(args.worker_dir)
        runtime = build_selected_runtime(
            inspection["agent_config"],
            worker_model_route=args.worker_model_route,
            rootless_config=args.rootless_config,
        )
        manifest = freeze_base_harness(
            worker_dir=args.worker_dir,
            run_root=args.run_root,
            selected_profile_id=args.profile_id,
            selected_runtime=runtime,
            selection_artifact_root=args.selection_artifact_root,
            handoff_path=args.output,
            mutation_surfaces=args.mutation_surfaces,
        )
    except FrozenBaseHarnessError as exc:
        print(f"freeze-qrs-base-harness: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
