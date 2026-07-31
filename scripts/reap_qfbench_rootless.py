#!/usr/bin/env python3
"""Dry-run or reap exact unfinished QFBench rootless container/network IDs."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.backends.rootless_docker import RootlessDockerBackend
from qea.rootless_full_harness import load_rootless_full_harness_config
from qea.sandbox_reaper import reap_sandbox_networks, reap_sandboxes


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--rootless-config", type=Path, required=True)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="remove exact persisted IDs; default is a read-only dry run",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_dir = args.results_dir.expanduser().resolve()
    if not run_dir.is_dir():
        raise ValueError(f"results directory is unavailable: {run_dir}")
    config = load_rootless_full_harness_config(args.rootless_config)
    backend = RootlessDockerBackend(
        docker_host=config.docker_host,
        expected_uid=config.expected_uid,
    )

    containers = reap_sandboxes(
        run_dir, backend=backend, apply=args.apply
    )
    networks = reap_sandbox_networks(
        run_dir, backend=backend, apply=args.apply
    )
    final_containers = reap_sandboxes(run_dir, backend=backend)
    final_networks = reap_sandbox_networks(run_dir, backend=backend)
    inventory = backend.list(
        {"qea.managed": "true", "qea.run-id": run_dir.name}
    )
    payload = {
        "schema_version": 1,
        "backend": backend.backend_name,
        "run_id": run_dir.name,
        "apply": args.apply,
        "containers": asdict(containers),
        "networks": asdict(networks),
        "final_container_pending_ids": list(final_containers.pending_ids),
        "final_network_pending_ids": list(final_networks.pending_ids),
        "final_inventory_ids": [state.native_id for state in inventory],
    }
    print(json.dumps(payload, sort_keys=True, indent=2))

    unsafe = bool(
        containers.identity_mismatch_ids
        or containers.failed
        or networks.failed
        or final_containers.identity_mismatch_ids
        or final_containers.failed
        or final_networks.failed
    )
    if args.apply:
        unsafe = unsafe or bool(
            final_containers.pending_ids
            or final_networks.pending_ids
            or inventory
        )
    return 1 if unsafe else 0


if __name__ == "__main__":
    raise SystemExit(main())
