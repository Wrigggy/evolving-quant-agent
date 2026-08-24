#!/usr/bin/env python3
"""Materialize development-only public QFBench contracts for QRS main."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qea.qrs_public_contracts import materialize_qrs_public_contracts  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qfbench-public-source-root", type=Path, required=True)
    parser.add_argument("--method-plan", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args(argv)
    report = materialize_qrs_public_contracts(
        qfbench_public_source_root=args.qfbench_public_source_root,
        method_plan_path=args.method_plan,
        destination=args.destination,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
