#!/usr/bin/env python3
"""Build or resume an All-N QFBench H0 trajectory bank from local run dirs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qea.qfbench_trajectory_bank import build_trajectory_bank  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--scheduler-plan", type=Path, required=True)
    parser.add_argument("--public-contracts-root", type=Path, required=True)
    parser.add_argument(
        "--h0-run",
        type=Path,
        action="append",
        required=True,
        help="Completed H0 run directory; repeat for multiple run directories.",
    )
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="Exit nonzero unless every development task has one valid history.",
    )
    args = parser.parse_args(argv)
    report = build_trajectory_bank(
        manifest_path=args.manifest,
        scheduler_plan_path=args.scheduler_plan,
        public_contracts_root=args.public_contracts_root,
        h0_run_dirs=args.h0_run,
        destination=args.destination,
        require_complete=args.require_complete,
    )
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
