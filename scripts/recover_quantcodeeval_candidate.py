#!/usr/bin/env python3
"""Recover a measured QuantCodeEval artifact-zero panel without resampling."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.quantcodeeval_candidate import recover_quantcodeeval_candidate_artifact_zero


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--source-h0-run-dir", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    result = recover_quantcodeeval_candidate_artifact_zero(
        run_dir=args.run_dir,
        source_h0_run_dir=args.source_h0_run_dir,
        token_file=config["token_file"],
    )
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
