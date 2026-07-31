#!/usr/bin/env python3
"""Assemble one explicit immutable QFBench rootless image-set index."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.rootless_image_set import RootlessImageSet, RootlessImageSetError


def assemble_image_set(*, benchmark_commit, task_ids, manifest_paths):
    """Assemble an immutable image set for CLI and batch-builder callers."""

    return RootlessImageSet.from_manifest_paths(
        benchmark_commit=benchmark_commit,
        task_ids=task_ids,
        manifest_paths=manifest_paths,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-commit", required=True)
    parser.add_argument("--task-id", action="append", required=True)
    parser.add_argument(
        "--manifest",
        type=Path,
        action="append",
        required=True,
        help="Explicit MANIFEST.json path; repeat for every selected image.",
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        image_set = assemble_image_set(
            benchmark_commit=args.benchmark_commit,
            task_ids=args.task_id,
            manifest_paths=args.manifest,
        )
        output = image_set.write(args.output)
    except RootlessImageSetError as exc:
        parser.error(str(exc))
    print(f"image set: {output}")
    print(f"identity sha256: {image_set.identity_sha256}")
    print(f"tasks: {', '.join(image_set.task_ids)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
