#!/usr/bin/env python3
"""Materialize the ten-field A6 launch identity from exact live inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Mapping

if __name__ == "__main__":
    # A6 releases are content-addressed and must not be mutated by imports.
    sys.dont_write_bytecode = True

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.a6_source_release import validate_a6_source_release  # noqa: E402
from qea.qfbench_a6 import (  # noqa: E402
    materialized_a6_launch_identity_digest,
    validate_a6_prelaunch_identity,
)
from qea.rootless_full_harness import (  # noqa: E402
    load_rootless_full_harness_config,
    rootless_model_route_identity,
    rootless_scheduler_identity,
)
from qea.rootless_images import verify_role_root  # noqa: E402


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"required regular JSON file is unavailable: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _canonical_bytes(payload: object) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _external_destination(
    *,
    source_root: Path,
    destination: Path,
    overwrite: bool,
) -> Path:
    raw = destination.expanduser()
    if raw.is_symlink():
        raise ValueError("A6 prelaunch identity destination may not be a symlink")
    resolved = raw.resolve()
    if resolved == source_root or source_root in resolved.parents:
        raise ValueError(
            "A6 prelaunch identity must live outside the source release root"
        )
    if resolved.exists() and not overwrite:
        raise ValueError(f"A6 prelaunch identity already exists: {resolved}")
    return resolved


def materialize(
    *,
    source_release_root: Path,
    source_release_manifest: Path,
    a6_manifest: Path,
    rootless_config: Path,
    image_set_manifest: Path,
    destination: Path,
    overwrite: bool = False,
    execution_root: Path | None = None,
) -> dict[str, object]:
    """Build, validate, and atomically write one materialized A6 identity."""

    raw_source_root = source_release_root.expanduser()
    if raw_source_root.is_symlink() or not raw_source_root.is_dir():
        raise ValueError("A6 source release root is unavailable")
    source_root = raw_source_root.resolve()
    expected_execution_root = (
        execution_root.resolve()
        if execution_root is not None
        else Path(__file__).resolve().parents[1]
    )
    if source_root != expected_execution_root:
        raise ValueError(
            "A6 source release root differs from the executing materializer source"
        )
    protocol_path = a6_manifest.expanduser()
    expected_protocol = (
        source_root / "data/qfbench/MANIFEST_A6_EXPANDED_CANARY.json"
    )
    if protocol_path.is_symlink() or protocol_path.resolve() != expected_protocol:
        raise ValueError("A6 protocol manifest is not the source release manifest")
    frozen = _json(protocol_path)
    if frozen.get("stage") != "A6":
        raise ValueError("A6 protocol manifest has the wrong stage")
    output = _external_destination(
        source_root=source_root,
        destination=destination,
        overwrite=overwrite,
    )
    identity_spec = frozen.get("prelaunch_identity_freeze")
    identity_spec = identity_spec if isinstance(identity_spec, Mapping) else {}
    record_path = identity_spec.get("record_path")
    if not isinstance(record_path, str) or not record_path:
        raise ValueError("A6 protocol has no external identity record path")
    if output != (source_root / record_path).resolve():
        raise ValueError("A6 prelaunch identity destination differs from the protocol")
    config_path = rootless_config.expanduser()
    image_path = image_set_manifest.expanduser()
    for label, path in (
        ("rootless config", config_path),
        ("image-set manifest", image_path),
    ):
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"A6 {label} is unavailable")
    config_path = config_path.resolve()
    image_path = image_path.resolve()
    config = load_rootless_full_harness_config(config_path)
    runtime = frozen.get("frozen_runtime")
    runtime = runtime if isinstance(runtime, Mapping) else {}
    runtime_drift = sorted(
        label
        for label, observed, expected in (
            ("model", config.allowed_model, runtime.get("model")),
            ("provider", config.required_provider, runtime.get("provider")),
        )
        if observed != expected
    )
    if runtime_drift:
        raise ValueError(
            "A6 effective model route differs from the protocol: "
            + ", ".join(runtime_drift)
        )
    if not isinstance(config.scheduler_epoch, str) or not config.scheduler_epoch:
        raise ValueError("A6 rootless config has no scheduler epoch")

    source_identity = validate_a6_source_release(
        source_root,
        source_release_manifest.expanduser(),
    )
    public_role = verify_role_root(config.public_root, "public")
    trusted_role = verify_role_root(config.trusted_root, "trusted-verifier")
    effective_identity = {
        "rootless_config_sha256": _sha256(config_path),
        "image_set_manifest_sha256": _sha256(image_path),
        "public_task_role_manifest_sha256": public_role.manifest_sha256,
        "trusted_task_role_manifest_sha256": trusted_role.manifest_sha256,
        "scheduler_epoch": config.scheduler_epoch,
        "scheduler_identity_sha256": rootless_scheduler_identity(config),
        "provider_route_identity_sha256": rootless_model_route_identity(
            upstream_base_url=config.upstream_base_url,
            allowed_path_prefix=config.allowed_path_prefix,
            allowed_model=config.allowed_model,
            required_provider=config.required_provider,
        ),
        "a6_source_release_sha256": source_identity["tree_sha256"],
    }
    record: dict[str, object] = {
        "schema_version": 1,
        "stage": "A6",
        "status": "materialized",
        "protocol_manifest_sha256": _sha256(protocol_path),
        **effective_identity,
    }
    record["materialized_launch_identity_sha256"] = (
        materialized_a6_launch_identity_digest(record)
    )
    validate_a6_prelaunch_identity(
        frozen=frozen,
        freeze_record=record,
        protocol_manifest_path=protocol_path,
        effective_identity=effective_identity,
    )
    encoded = _canonical_bytes(record)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=output.parent,
            prefix=output.name + ".tmp-",
            delete=False,
        ) as temporary:
            temporary.write(encoded)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_name = temporary.name
        os.replace(temporary_name, output)
        temporary_name = None
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)
    return {
        "identity_record_sha256": hashlib.sha256(encoded).hexdigest(),
        "materialized_launch_identity_sha256": record[
            "materialized_launch_identity_sha256"
        ],
        "protocol_manifest_sha256": record["protocol_manifest_sha256"],
        "source_release_manifest_sha256": source_identity["manifest_sha256"],
        "source_release_member_count": source_identity["member_count"],
        **effective_identity,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-release-root", type=Path, required=True)
    parser.add_argument("--source-release-manifest", type=Path, required=True)
    parser.add_argument("--a6-manifest", type=Path, required=True)
    parser.add_argument("--rootless-config", type=Path, required=True)
    parser.add_argument("--image-set-manifest", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    report = materialize(
        source_release_root=args.source_release_root,
        source_release_manifest=args.source_release_manifest,
        a6_manifest=args.a6_manifest,
        rootless_config=args.rootless_config,
        image_set_manifest=args.image_set_manifest,
        destination=args.destination,
        overwrite=args.overwrite,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
