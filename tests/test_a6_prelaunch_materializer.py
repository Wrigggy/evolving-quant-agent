import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from qea.qfbench_a6 import materialized_a6_launch_identity_digest


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _fixture(tmp_path: Path):
    source = tmp_path / "bundle/source"
    protocol = source / "data/qfbench/MANIFEST_A6_EXPANDED_CANARY.json"
    required_fields = [
        "protocol_manifest_sha256",
        "rootless_config_sha256",
        "image_set_manifest_sha256",
        "public_task_role_manifest_sha256",
        "trusted_task_role_manifest_sha256",
        "scheduler_epoch",
        "scheduler_identity_sha256",
        "provider_route_identity_sha256",
        "a6_source_release_sha256",
        "materialized_launch_identity_sha256",
    ]
    _write_json(
        protocol,
        {
            "stage": "A6",
            "frozen_runtime": {
                "model": "provider/model",
                "provider": "provider",
            },
            "prelaunch_identity_freeze": {
                "schema_version": 1,
                "required_before_any_a6_model_call": True,
                "record_path": "../A6_PRELAUNCH_IDENTITY.json",
                "required_record_fields": required_fields,
            },
        },
    )
    rootless = tmp_path / "rootless.json"
    images = tmp_path / "images.json"
    source_manifest = tmp_path / "source-manifest.json"
    for path in (rootless, images, source_manifest):
        _write_json(path, {"schema_version": 1})
    config = SimpleNamespace(
        public_root=tmp_path / "public",
        trusted_root=tmp_path / "trusted",
        upstream_base_url="https://example.invalid/v1",
        allowed_path_prefix="/v1",
        allowed_model="provider/model",
        required_provider="provider",
        scheduler_epoch="a6-epoch",
    )
    return source, protocol, rootless, images, source_manifest, config


def _patch_identities(monkeypatch, materializer, config):
    monkeypatch.setattr(
        materializer,
        "load_rootless_full_harness_config",
        lambda path: config,
    )
    monkeypatch.setattr(
        materializer,
        "validate_a6_source_release",
        lambda root, manifest: {
            "manifest_sha256": "a" * 64,
            "tree_sha256": "7" * 64,
            "member_count": 123,
        },
    )
    role_digests = iter(("3" * 64, "4" * 64))
    monkeypatch.setattr(
        materializer,
        "verify_role_root",
        lambda root, role: SimpleNamespace(manifest_sha256=next(role_digests)),
    )
    monkeypatch.setattr(
        materializer,
        "rootless_scheduler_identity",
        lambda value: "5" * 64,
    )
    monkeypatch.setattr(
        materializer,
        "rootless_model_route_identity",
        lambda **kwargs: "6" * 64,
    )


def test_materializer_writes_validated_ten_field_external_record(
    tmp_path, monkeypatch
):
    import scripts.materialize_a6_prelaunch_identity as materializer

    source, protocol, rootless, images, source_manifest, config = _fixture(
        tmp_path
    )
    _patch_identities(monkeypatch, materializer, config)
    destination = tmp_path / "bundle/A6_PRELAUNCH_IDENTITY.json"

    report = materializer.materialize(
        source_release_root=source,
        source_release_manifest=source_manifest,
        a6_manifest=protocol,
        rootless_config=rootless,
        image_set_manifest=images,
        destination=destination,
        execution_root=source,
    )

    record = json.loads(destination.read_text())
    assert record["status"] == "materialized"
    assert record["a6_source_release_sha256"] == "7" * 64
    assert record["materialized_launch_identity_sha256"] == (
        materialized_a6_launch_identity_digest(record)
    )
    assert report["identity_record_sha256"] == hashlib.sha256(
        destination.read_bytes()
    ).hexdigest()
    assert report["source_release_member_count"] == 123


def test_materializer_rejects_internal_record_and_runtime_drift(
    tmp_path, monkeypatch
):
    import scripts.materialize_a6_prelaunch_identity as materializer

    source, protocol, rootless, images, source_manifest, config = _fixture(
        tmp_path
    )
    _patch_identities(monkeypatch, materializer, config)
    with pytest.raises(ValueError, match="outside the source release root"):
        materializer.materialize(
            source_release_root=source,
            source_release_manifest=source_manifest,
            a6_manifest=protocol,
            rootless_config=rootless,
            image_set_manifest=images,
            destination=source / "data/qfbench/A6_PRELAUNCH_IDENTITY.json",
            execution_root=source,
        )

    config.allowed_model = "different/model"
    with pytest.raises(ValueError, match="effective model route differs"):
        materializer.materialize(
            source_release_root=source,
            source_release_manifest=source_manifest,
            a6_manifest=protocol,
            rootless_config=rootless,
            image_set_manifest=images,
            destination=tmp_path / "bundle/A6_PRELAUNCH_IDENTITY.json",
            execution_root=source,
        )
