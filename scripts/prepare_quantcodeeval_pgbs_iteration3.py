#!/usr/bin/env python3
"""Record QuantCodeEval PGBHS iteration two and prepare iteration three."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.quantcodeeval_experiment import record_iteration_two_and_prepare_third


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--master-run-dir", type=Path, required=True)
    parser.add_argument("--h0-run-dir", type=Path, required=True)
    parser.add_argument("--iteration-one-candidate-dir", type=Path, required=True)
    parser.add_argument("--iteration-two-candidate-dir", type=Path, required=True)
    parser.add_argument("--public-root", type=Path, required=True)
    args = parser.parse_args()
    result = record_iteration_two_and_prepare_third(
        master_run_dir=args.master_run_dir,
        h0_run_dir=args.h0_run_dir,
        iteration_one_candidate_dir=args.iteration_one_candidate_dir,
        iteration_two_candidate_dir=args.iteration_two_candidate_dir,
        public_task_roots={
            task_id: args.public_root.resolve() / "tasks" / task_id
            for task_id in ("T16", "T24")
        },
    )
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
