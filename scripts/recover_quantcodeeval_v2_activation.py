#!/usr/bin/env python3
"""Recover a completed QuantCodeEval activation after post-run persistence failed."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qea.quantcodeeval_v2_live import recover_quantcodeeval_v2_activation_canary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--release", required=True, type=Path)
    args = parser.parse_args(argv)
    result = recover_quantcodeeval_v2_activation_canary(
        run_dir=args.run_dir, release_dir=args.release
    )
    print(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
