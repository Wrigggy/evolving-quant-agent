#!/usr/bin/env python3
"""Record the fifth QuantCodeEval PGBHS ACT and finalize its ledger."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.quantcodeeval_experiment import record_iteration_five_and_finalize


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--master-run-dir", type=Path, required=True)
    parser.add_argument("--h0-run-dir", type=Path, required=True)
    parser.add_argument("--iteration-five-candidate-dir", type=Path, required=True)
    args = parser.parse_args()
    result = record_iteration_five_and_finalize(
        master_run_dir=args.master_run_dir,
        h0_run_dir=args.h0_run_dir,
        iteration_five_candidate_dir=args.iteration_five_candidate_dir,
    )
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
