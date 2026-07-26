#!/usr/bin/env python3
"""Generate, and optionally publish, pinned QFBench E2B task templates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.benchmarks.qfbench import default_manifest_path, load_qfbench_snapshot
from qea.qfbench_images import (
    NEXAU_WORKER_DEPENDENCY,
    apply_qfbench_e2b_task_overlay,
    prepare_qfbench_base_template_overlay,
    prepare_qfbench_overlay,
    record_published_template,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qfbench-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=default_manifest_path())
    base = parser.add_mutually_exclusive_group(required=True)
    base.add_argument("--base-image", help="registry image@sha256:digest")
    base.add_argument("--base-template", help="immutable E2B base template ID")
    base.add_argument("--base-manifest", type=Path, help="published base image manifest")
    parser.add_argument("--base-build-id", help="required with --base-template")
    parser.add_argument("--output-dir", type=Path, default=Path("output/qfbench-e2b-images"))
    parser.add_argument("--task", action="append", dest="tasks")
    parser.add_argument("--role", choices=("worker", "verifier", "both"), default="both")
    parser.add_argument("--publish", action="store_true", help="perform paid/networked E2B builds")
    parser.add_argument("--skip-cache", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    snapshot = load_qfbench_snapshot(args.qfbench_root, manifest_path=args.manifest)
    base_template = args.base_template
    base_build_id = args.base_build_id
    if args.base_manifest:
        try:
            base_payload = json.loads(args.base_manifest.read_text())
            base_template = base_payload["published_template_id"]
            base_build_id = base_payload["published_build_id"]
        except (OSError, json.JSONDecodeError, KeyError) as exc:
            raise SystemExit(f"cannot load published base manifest: {exc}") from exc
    if base_template and not base_build_id:
        raise SystemExit("--base-build-id is required with an E2B base template")
    task_ids = args.tasks or [task.task_id for task in snapshot.tasks]
    selected = [snapshot.task(task_id) for task_id in task_ids]
    roles = ("worker", "verifier") if args.role == "both" else (args.role,)

    specs = []
    for task in selected:
        for role in roles:
            dependencies = (
                (NEXAU_WORKER_DEPENDENCY,)
                if role == "worker"
                else ("uv==0.9.5",)
            )
            verifier_test_script = (
                (task.root / "tests" / "test.sh").read_text()
                if role == "verifier"
                else None
            )
            if args.base_image:
                spec = prepare_qfbench_overlay(
                    task_id=task.task_id,
                    upstream_dockerfile=task.dockerfile_path,
                    output_dir=args.output_dir,
                    base_image=args.base_image,
                    role=role,
                    dependencies=dependencies,
                    benchmark_commit=snapshot.commit,
                    cpu_count=task.cpus,
                    memory_mb=task.memory_mb,
                    build_timeout_seconds=task.build_timeout_seconds,
                    verifier_test_script=verifier_test_script,
                )
            else:
                assert base_template is not None and base_build_id is not None
                spec = prepare_qfbench_base_template_overlay(
                    task_id=task.task_id,
                    upstream_dockerfile=task.dockerfile_path,
                    output_dir=args.output_dir,
                    base_template_id=base_template,
                    base_build_id=base_build_id,
                    role=role,
                    dependencies=dependencies,
                    benchmark_commit=snapshot.commit,
                    cpu_count=task.cpus,
                    memory_mb=task.memory_mb,
                    build_timeout_seconds=task.build_timeout_seconds,
                    verifier_test_script=verifier_test_script,
                )
            specs.append(spec)
            location = getattr(spec, "overlay_path", spec.manifest_path)
            print(f"prepared {spec.template_name}: {location}")

    if not args.publish:
        print("dry run only; pass --publish to build templates in E2B")
        return 0

    from e2b import Template

    for spec in specs:
        existing = json.loads(spec.manifest_path.read_text())
        published_template = existing.get("published_template_id")
        published_build = existing.get("published_build_id")
        if published_template and published_build:
            print(
                f"reusing published {spec.template_name}: "
                f"template={published_template} build={published_build}"
            )
            continue
        if args.base_image:
            builder = Template(file_context_path=spec.context_dir).from_dockerfile(
                spec.overlay_path.read_text()
            )
        else:
            builder = Template(file_context_path=spec.context_dir).from_template(
                spec.base_template_id
            )
            apply_qfbench_e2b_task_overlay(builder, spec)
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
        print(f"published {spec.template_name}: template={build.template_id} build={build.build_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
