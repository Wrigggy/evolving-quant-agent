#!/usr/bin/env python3
"""Plan or build immutable QFBench images through a rootless Docker socket."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.rootless_images import (
    RootlessImageError,
    execute_rootless_image_build,
    prepare_rootless_image_plan,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--role",
        choices=("base", "proxy", "evolver", "worker", "verifier"),
        required=True,
    )
    parser.add_argument("--task-id")
    parser.add_argument("--public-root", type=Path, required=True)
    parser.add_argument("--trusted-root", type=Path)
    parser.add_argument("--manifest-root", type=Path, required=True)
    parser.add_argument("--base-image-ref", required=True)
    parser.add_argument("--docker-host", required=True)
    parser.add_argument("--expected-uid", type=int, default=os.getuid())
    parser.add_argument("--cpu-count", type=int, default=2)
    parser.add_argument("--memory-mb", type=int, default=4096)
    parser.add_argument("--build-timeout-seconds", type=int, default=1800)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan-only", action="store_true")
    mode.add_argument("--build", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        plan = prepare_rootless_image_plan(
            role=args.role,
            task_id=args.task_id,
            public_root=args.public_root,
            trusted_root=args.trusted_root,
            base_image_ref=args.base_image_ref,
            cpu_count=args.cpu_count,
            memory_mb=args.memory_mb,
            build_timeout_seconds=args.build_timeout_seconds,
        )
        print(f"role: {plan.role}")
        print(f"task: {plan.task_id}")
        print(f"benchmark commit: {plan.benchmark_commit}")
        print(f"identity sha256: {plan.identity_sha256}")
        print(f"context files: {len(plan.context_files)}")
        print(f"base image: {plan.base_image_ref}")
        if args.build:
            result = execute_rootless_image_build(
                plan,
                output_root=args.manifest_root,
                docker_host=args.docker_host,
                expected_uid=args.expected_uid,
            )
            print(f"image id: {result.image_id}")
            print(f"manifest: {result.manifest_path}")
        return 0
    except RootlessImageError as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
