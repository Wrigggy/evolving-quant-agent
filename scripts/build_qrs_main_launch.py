#!/usr/bin/env python3
"""Materialize the global QRS launch manifest and six Review-only plans."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qea.qrs_main_launch import build_qrs_main_launch  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--method-plan", type=Path, required=True)
    parser.add_argument("--frozen-h0-handoff", type=Path, required=True)
    parser.add_argument("--scheduler-run-id", required=True)
    parser.add_argument("--python", required=True)
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--qfbench-root", required=True)
    parser.add_argument("--qfbench-manifest", required=True)
    parser.add_argument("--rootless-config", required=True)
    parser.add_argument("--image-set-manifest", required=True)
    parser.add_argument("--results-dir", required=True)
    parser.add_argument("--worker-route", required=True)
    parser.add_argument("--qfbench-public-manifest", type=Path, required=True)
    parser.add_argument("--trajectory-bank-output", type=Path, required=True)
    parser.add_argument("--public-contracts-root", type=Path, required=True)
    parser.add_argument("--reviewer-config", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)

    reviewer = json.loads(args.reviewer_config.read_text(encoding="utf-8"))
    if not isinstance(reviewer, dict):
        parser.error("--reviewer-config must contain one JSON object")
    result = build_qrs_main_launch(
        method_plan_path=args.method_plan,
        frozen_h0_handoff_path=args.frozen_h0_handoff,
        scheduler_run_id=args.scheduler_run_id,
        runtime={
            "python": args.python,
            "source_root": args.source_root,
            "qfbench_root": args.qfbench_root,
            "qfbench_manifest": args.qfbench_manifest,
            "rootless_config": args.rootless_config,
            "image_set_manifest": args.image_set_manifest,
            "results_dir": args.results_dir,
            "worker_route": args.worker_route,
        },
        qfbench_public_manifest=args.qfbench_public_manifest,
        trajectory_bank_output=args.trajectory_bank_output,
        public_contracts_root=args.public_contracts_root,
        reviewer_config=reviewer,
        output_root=args.output_root,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
