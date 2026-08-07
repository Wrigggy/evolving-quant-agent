#!/usr/bin/env python3
"""Materialize one model-bound QEA discovery-evolver runtime profile."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.evolver_profile import materialize_evolver_profile, profile_as_dict  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument(
        "--reasoning-effort",
        choices=("none", "minimal", "low", "medium", "high", "xhigh"),
        default="none",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    profile = materialize_evolver_profile(
        args.source,
        args.destination,
        model=args.model,
        provider=args.provider,
        reasoning_effort=args.reasoning_effort,
    )
    print(json.dumps(profile_as_dict(profile), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
