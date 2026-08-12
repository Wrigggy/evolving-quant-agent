#!/usr/bin/env python3
"""Build one A5 contract arm from the shared expanded seed-evidence run."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_qfbench_a4_evidence import build  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-run", type=Path, required=True)
    parser.add_argument("--evolution-manifest", type=Path, required=True)
    parser.add_argument("--a5-manifest", type=Path, required=True)
    parser.add_argument("--evidence-run", type=Path, required=True)
    parser.add_argument("--seed-arm", default="seed-evidence")
    parser.add_argument(
        "--contract-arm",
        choices=("failure_only", "contrastive"),
        required=True,
    )
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args(argv)
    report = build(
        baseline_run=args.baseline_run,
        evolution_manifest_path=args.evolution_manifest,
        a4_manifest_path=args.a5_manifest,
        evidence_run=args.evidence_run,
        arm=args.seed_arm,
        destination=args.destination.expanduser().resolve(),
        contract_arm=args.contract_arm,
    )
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
