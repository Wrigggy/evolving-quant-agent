#!/usr/bin/env python3
"""Prepare, and optionally publish, the pinned QFBench E2B base template."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.benchmarks.qfbench import default_manifest_path, load_qfbench_snapshot
from qea.qfbench_images import prepare_qfbench_base_build_context


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qfbench-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=default_manifest_path())
    parser.add_argument("--output-dir", type=Path, default=Path("output/qfbench-e2b-images"))
    parser.add_argument("--name")
    parser.add_argument("--publish", action="store_true", help="perform a paid/networked E2B build")
    parser.add_argument("--skip-cache", action="store_true")
    return parser


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    snapshot = load_qfbench_snapshot(args.qfbench_root, manifest_path=args.manifest)
    dockerfile = snapshot.root / "docker" / "sandbox.Dockerfile"
    requirements = snapshot.root / "docker" / "requirements-sandbox.txt"
    if not dockerfile.is_file() or not requirements.is_file():
        raise SystemExit("pinned snapshot is missing docker/sandbox.Dockerfile or requirements")

    identity = hashlib.sha256(
        (snapshot.commit + _sha256(dockerfile) + _sha256(requirements)).encode()
    ).hexdigest()
    name = args.name or f"qea-qfbench-base-{snapshot.commit[:8]}-{identity[:12]}"
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    build_context = prepare_qfbench_base_build_context(snapshot.root, output_dir)
    staged_dockerfile = build_context / "docker" / "sandbox.Dockerfile"
    manifest_path = output_dir / "qfbench-base.image.json"
    payload = {
        "benchmark_commit": snapshot.commit,
        "identity_sha256": identity,
        "template_name": name,
        "dockerfile_path": str(dockerfile.resolve()),
        "dockerfile_sha256": _sha256(dockerfile),
        "requirements_sha256": _sha256(requirements),
        "build_context": str(build_context),
        "build_context_files": [
            "docker/requirements-sandbox.txt",
            "docker/sandbox.Dockerfile",
        ],
        "source_parent": "python:3.11-slim",
        "rebuild_note": (
            "Reuse the published template/build IDs; the upstream source parent tag and "
            "requirement ranges are mutable at rebuild time."
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "published_template_id": None,
        "published_build_id": None,
    }
    if manifest_path.is_file():
        existing = json.loads(manifest_path.read_text())
        if existing.get("published_template_id") or existing.get("published_build_id"):
            if existing.get("identity_sha256") != identity:
                raise SystemExit(
                    f"refusing to replace published QFBench base identity in {manifest_path}"
                )
            for key in ("published_template_id", "published_build_id", "published_at"):
                if key in existing:
                    payload[key] = existing[key]
    manifest_path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")
    print(f"prepared {name}: {manifest_path}")
    if not args.publish:
        print("dry run only; pass --publish to build the base template in E2B")
        return 0
    if payload.get("published_template_id") and payload.get("published_build_id"):
        print(
            "reusing published base: "
            f"template={payload['published_template_id']} "
            f"build={payload['published_build_id']}"
        )
        return 0

    from e2b import Template

    builder = Template(file_context_path=build_context).from_dockerfile(
        str(staged_dockerfile)
    )
    builder.run_cmd(
        "mkdir -p /opt/qea && python -m pip freeze --all | sort > /opt/qea/base-requirements.lock",
        user="root",
    )
    build = Template.build(
        builder,
        name,
        cpu_count=4,
        memory_mb=8192,
        skip_cache=args.skip_cache,
        on_build_logs=lambda entry: print(entry),
    )
    payload["published_template_id"] = str(build.template_id)
    payload["published_build_id"] = str(build.build_id)
    payload["published_at"] = datetime.now(timezone.utc).isoformat()
    manifest_path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")
    print(f"published {name}: template={build.template_id} build={build.build_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
