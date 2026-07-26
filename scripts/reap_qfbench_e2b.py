#!/usr/bin/env python3
"""Dry-run or reap exact unfinished QFBench E2B sandbox IDs."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import run as run_cli
from qea.e2b_reaper import reap_e2b_sandboxes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="kill the exact pending IDs; default is a read-only dry run",
    )
    args = parser.parse_args(argv)
    run_cli._load_dotenv()

    def kill(sandbox_id: str) -> bool:
        from e2b import Sandbox

        return bool(Sandbox.kill(sandbox_id))

    report = reap_e2b_sandboxes(
        args.results_dir,
        kill_sandbox=kill,
        apply=args.apply,
    )
    print(json.dumps(asdict(report), sort_keys=True, indent=2))
    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
