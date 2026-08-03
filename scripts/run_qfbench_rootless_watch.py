#!/usr/bin/env python3
"""Watch bounded QFBench metadata and stop only a validated child PGID."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.qfbench_run_watch import (
    load_watch_config,
    run_watch_once,
    wait_for_run_event,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval-seconds", type=int, default=30)
    args = parser.parse_args(argv)
    if not 1 <= args.interval_seconds <= 3600:
        raise ValueError("interval-seconds must be between 1 and 3600")
    config = load_watch_config(args.config)
    while True:
        observation = run_watch_once(config)
        print(
            json.dumps(
                {
                    "hard_stop": observation.hard_stop,
                    "category": observation.category,
                    "evidence_sha256": observation.evidence_sha256,
                },
                sort_keys=True,
            )
        )
        if observation.hard_stop:
            return 1
        if args.once:
            return 0
        wait_for_run_event(
            config.run_dir, timeout_seconds=args.interval_seconds
        )


if __name__ == "__main__":
    raise SystemExit(main())
