#!/usr/bin/env python3
"""Record QuantCodeEval PGBHS iteration four and terminal round-five ABSTAIN."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from qea.quantcodeeval_experiment import record_iteration_four_and_finalize_success


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--master-run-dir", required=True)
    parser.add_argument("--h0-run-dir", required=True)
    parser.add_argument("--iteration-four-candidate-dir", required=True)
    parser.add_argument("--public-root", required=True)
    args = parser.parse_args()
    public_root = Path(args.public_root)
    result = record_iteration_four_and_finalize_success(
        master_run_dir=args.master_run_dir,
        h0_run_dir=args.h0_run_dir,
        iteration_four_candidate_dir=args.iteration_four_candidate_dir,
        public_task_roots={
            task_id: public_root / "tasks" / task_id for task_id in ("T16", "T24")
        },
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
