#!/usr/bin/env python3
"""Run the owner-only QFBench repetition-boundary migration guard."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.backends.rootless_docker import RootlessDockerBackend
from qea.qfbench_boundary import load_boundary_guard_config, run_boundary_guard
from qea.rootless_full_harness import load_rootless_full_harness_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--guard-config", type=Path, required=True)
    parser.add_argument("--rootless-config", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    guard = load_boundary_guard_config(args.guard_config)
    rootless = load_rootless_full_harness_config(args.rootless_config)
    if rootless.expected_uid != guard.expected_uid:
        raise ValueError("guard and rootless UID identities differ")
    backend = RootlessDockerBackend(
        docker_host=rootless.docker_host,
        expected_uid=rootless.expected_uid,
    )
    result = run_boundary_guard(guard, backend=backend)
    print(
        json.dumps(
            {
                "status": result.status,
                "manifest_sha256": result.manifest_sha256,
                "reason": result.reason,
            },
            sort_keys=True,
            indent=2,
        )
    )
    return 0 if result.status == "migrated" else 1


if __name__ == "__main__":
    raise SystemExit(main())
