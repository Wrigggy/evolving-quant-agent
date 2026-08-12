#!/usr/bin/env python3
"""Create disjoint QuantCodeEval worker/verifier roots from a pinned checkout."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.benchmarks.quantcodeeval import (
    default_manifest_path,
    materialize_quantcodeeval_role_snapshot,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="official checkout at the pinned commit")
    parser.add_argument("public_root", type=Path, help="new worker-visible role root")
    parser.add_argument("trusted_root", type=Path, help="new verifier-only role root")
    parser.add_argument("--manifest", type=Path, default=default_manifest_path())
    parser.add_argument(
        "--trusted-oracle-root",
        type=Path,
        help="separate pinned verifier-only root containing tasks/Txx/golden_ref.py",
    )
    parser.add_argument(
        "--task-panel",
        type=Path,
        help="optional public-task panel overriding the default T16/T24 canary",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = materialize_quantcodeeval_role_snapshot(
        args.source,
        args.public_root,
        args.trusted_root,
        manifest_path=args.manifest,
        trusted_oracle_root=args.trusted_oracle_root,
        task_panel_path=args.task_panel,
    )
    print(f"public role:  {result.public_root}")
    print(f"trusted role: {result.trusted_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
