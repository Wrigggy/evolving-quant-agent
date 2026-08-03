#!/usr/bin/env python3
"""Own and supervise one QFBench coordinator process group."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.process_supervisor import load_supervisor_config, run_supervised


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args(argv)
    return run_supervised(load_supervisor_config(args.config))


if __name__ == "__main__":
    raise SystemExit(main())
