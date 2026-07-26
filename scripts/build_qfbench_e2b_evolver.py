#!/usr/bin/env python3
"""Prepare or publish the immutable generic QFBench E2B evolver template."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.qfbench_images import (
    apply_qfbench_evolver_template,
    prepare_qfbench_evolver_template,
    record_published_template,
)


_PINNED_QFBENCH_COMMIT = "024921eb507fcc0c4ffe3e0a96802724be1ae84a"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    base = parser.add_mutually_exclusive_group(required=True)
    base.add_argument("--base-template", help="published shared base template ID")
    base.add_argument("--base-manifest", type=Path, help="published shared base manifest")
    parser.add_argument("--base-build-id", help="required with --base-template")
    parser.add_argument("--benchmark-commit", default=_PINNED_QFBENCH_COMMIT)
    parser.add_argument(
        "--output-dir", type=Path, default=Path("output/qfbench-e2b-images")
    )
    parser.add_argument("--cpu-count", type=int, default=2)
    parser.add_argument("--memory-mb", type=int, default=4096)
    parser.add_argument("--build-timeout-seconds", type=int, default=1800)
    parser.add_argument(
        "--publish", action="store_true", help="perform the paid E2B template build"
    )
    parser.add_argument("--skip-cache", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    base_template = args.base_template
    base_build_id = args.base_build_id
    if args.base_manifest:
        try:
            payload = json.loads(args.base_manifest.read_text())
            base_template = payload["published_template_id"]
            base_build_id = payload["published_build_id"]
        except (OSError, json.JSONDecodeError, KeyError) as exc:
            raise SystemExit(f"cannot load published base manifest: {exc}") from exc
    if not base_template or not base_build_id:
        raise SystemExit("a published base template and build ID are required")

    spec = prepare_qfbench_evolver_template(
        output_dir=args.output_dir,
        base_template_id=base_template,
        base_build_id=base_build_id,
        benchmark_commit=args.benchmark_commit,
        cpu_count=args.cpu_count,
        memory_mb=args.memory_mb,
        build_timeout_seconds=args.build_timeout_seconds,
    )
    print(f"prepared {spec.template_name}: {spec.manifest_path}")
    if not args.publish:
        print("dry run only; pass --publish to build the evolver template in E2B")
        return 0

    existing = json.loads(spec.manifest_path.read_text())
    if existing.get("published_template_id") and existing.get("published_build_id"):
        print(
            f"reusing published {spec.template_name}: "
            f"template={existing['published_template_id']} "
            f"build={existing['published_build_id']}"
        )
        return 0

    from e2b import Template

    builder = Template().from_template(spec.base_template_id)
    apply_qfbench_evolver_template(builder, spec)
    build = Template.build(
        builder,
        spec.template_name,
        cpu_count=spec.cpu_count,
        memory_mb=spec.memory_mb,
        skip_cache=args.skip_cache,
        on_build_logs=lambda entry: print(entry),
    )
    record_published_template(
        spec,
        template_id=str(build.template_id),
        build_id=str(build.build_id),
    )
    print(
        f"published {spec.template_name}: "
        f"template={build.template_id} build={build.build_id}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
