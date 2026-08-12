#!/usr/bin/env python3
"""Prepare immutable H0 evidence and the first QuantCodeEval PGBHS ACT."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.quantcodeeval_experiment import prepare_initial_pgbs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--master-run-dir", type=Path, required=True)
    parser.add_argument("--h0-run-dir", type=Path, required=True)
    parser.add_argument("--public-root", type=Path, required=True)
    args = parser.parse_args()
    result = prepare_initial_pgbs(
        master_run_dir=args.master_run_dir,
        h0_run_dir=args.h0_run_dir,
        public_task_roots={
            task_id: args.public_root.resolve() / "tasks" / task_id
            for task_id in ("T16", "T24")
        },
    )
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
