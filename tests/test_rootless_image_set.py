from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest


COMMIT = "024921eb507fcc0c4ffe3e0a96802724be1ae84a"
UPSTREAM_BASE = "docker.io/library/python@sha256:" + "a" * 64
BASE_IMAGE_ID = "sha256:" + "b" * 64


def _sha256_json(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _write_image_manifest(
    root: Path,
    *,
    role: str,
    image_digit: str,
    task_id: str | None = None,
    benchmark_commit: str = COMMIT,
    base_image_ref: str = BASE_IMAGE_ID,
    cpu_count: int = 2,
    memory_mb: int = 4096,
    build_timeout_seconds: int = 600,
) -> Path:
    root.mkdir(parents=True)
    lock = f"{role}-runtime==1.0\n".encode()
    (root / "dependency-lock.txt").write_bytes(lock)
    dockerfile = f"FROM {base_image_ref}\n".encode()
    context_files = [
        {
            "path": "Dockerfile",
            "mode": "0o644",
            "sha256": hashlib.sha256(dockerfile).hexdigest(),
            "size_bytes": len(dockerfile),
        }
    ]
    identity_payload = {
        "role": role,
        "task_id": task_id,
        "benchmark_commit": benchmark_commit,
        "base_image_ref": base_image_ref,
        "source_manifest_sha256": "c" * 64,
        "verifier_test_script_sha256": "d" * 64 if role == "verifier" else None,
        "context_files": context_files,
        "cpu_count": cpu_count,
        "memory_mb": memory_mb,
        "build_timeout_seconds": build_timeout_seconds,
        "build_network": "default",
    }
    image_id = "sha256:" + image_digit * 64
    manifest = {
        "schema_version": 1,
        **identity_payload,
        "dockerfile_sha256": hashlib.sha256(dockerfile).hexdigest(),
        "identity_sha256": _sha256_json(identity_payload),
        "image_id": image_id,
        "repo_digests": [],
        "build_tag": f"qea-rootless-{role}-fixture",
        "local_base_tag": None,
        "local_base_image_id": None,
        "docker_version": "29.4.1",
        "docker_security_options": ["name=rootless"],
        "dependency_lock_sha256": hashlib.sha256(lock).hexdigest(),
        "built_at": "2026-07-30T10:00:00+00:00",
    }
    path = root / "MANIFEST.json"
    path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    return path


def _image_manifests(
    tmp_path: Path,
    *,
    task_ids: tuple[str, ...] = ("task-b", "task-a"),
) -> tuple[Path, ...]:
    paths = [
        _write_image_manifest(
            tmp_path / "base",
            role="base",
            image_digit="b",
            base_image_ref=UPSTREAM_BASE,
            cpu_count=2,
            memory_mb=4096,
            build_timeout_seconds=1800,
        ),
        _write_image_manifest(
            tmp_path / "proxy",
            role="proxy",
            image_digit="2",
            cpu_count=1,
            memory_mb=512,
        ),
        _write_image_manifest(
            tmp_path / "evolver", role="evolver", image_digit="3"
        ),
    ]
    digits = iter("456789abcdef")
    for task_id in task_ids:
        paths.extend(
            (
                _write_image_manifest(
                    tmp_path / f"{task_id}-worker",
                    role="worker",
                    task_id=task_id,
                    image_digit=next(digits),
                ),
                _write_image_manifest(
                    tmp_path / f"{task_id}-verifier",
                    role="verifier",
                    task_id=task_id,
                    image_digit=next(digits),
                ),
            )
        )
    return tuple(paths)


def test_image_set_assembles_explicit_sorted_immutable_index(tmp_path) -> None:
    from qea.rootless_image_set import RootlessImageSet

    manifests = _image_manifests(tmp_path)
    image_set = RootlessImageSet.from_manifest_paths(
        benchmark_commit=COMMIT,
        task_ids=("task-b", "task-a"),
        manifest_paths=reversed(manifests),
    )
    payload = image_set.to_payload()

    assert image_set.task_ids == ("task-a", "task-b")
    assert payload["schema_version"] == 1
    assert payload["benchmark_commit"] == COMMIT
    assert payload["task_ids"] == ["task-a", "task-b"]
    assert [entry["task_id"] for entry in payload["tasks"]] == [
        "task-a",
        "task-b",
    ]
    assert {payload[role]["role"] for role in ("base", "proxy", "evolver")} == {
        "base",
        "proxy",
        "evolver",
    }
    for entry in (
        payload["base"],
        payload["proxy"],
        payload["evolver"],
        *(role for task in payload["tasks"] for role in (task["worker"], task["verifier"])),
    ):
        assert entry["image_id"].startswith("sha256:")
        assert len(entry["dependency_lock_sha256"]) == 64
        assert len(entry["manifest_sha256"]) == 64
        assert len(entry["manifest_identity_sha256"]) == 64
        assert entry["resource_contract"]["cpu_count"] > 0
        assert entry["docker_identity"]["security_options"] == ["name=rootless"]
    unsigned = dict(payload)
    identity = unsigned.pop("identity_sha256")
    assert identity == _sha256_json(unsigned)

    output = tmp_path / "image-set.json"
    image_set.write(output)
    assert RootlessImageSet.load(output).to_payload() == payload


def test_image_set_rejects_missing_duplicate_and_outside_panel_roles(tmp_path) -> None:
    from qea.rootless_image_set import RootlessImageSet, RootlessImageSetError

    manifests = list(_image_manifests(tmp_path / "missing", task_ids=("task-a",)))
    without_evolver = [
        path for path in manifests if json.loads(path.read_text())["role"] != "evolver"
    ]
    with pytest.raises(RootlessImageSetError, match="exactly one evolver"):
        RootlessImageSet.from_manifest_paths(
            benchmark_commit=COMMIT,
            task_ids=("task-a",),
            manifest_paths=without_evolver,
        )

    duplicate_proxy = _write_image_manifest(
        tmp_path / "duplicate-proxy",
        role="proxy",
        image_digit="a",
        cpu_count=1,
        memory_mb=512,
    )
    with pytest.raises(RootlessImageSetError, match="exactly one proxy"):
        RootlessImageSet.from_manifest_paths(
            benchmark_commit=COMMIT,
            task_ids=("task-a",),
            manifest_paths=(*manifests, duplicate_proxy),
        )

    outside = _image_manifests(tmp_path / "outside", task_ids=("task-c",))
    with pytest.raises(RootlessImageSetError, match="task panel"):
        RootlessImageSet.from_manifest_paths(
            benchmark_commit=COMMIT,
            task_ids=("task-a",),
            manifest_paths=outside,
        )


def test_image_set_rejects_commit_reference_lock_and_resource_drift(tmp_path) -> None:
    from qea.rootless_image_set import RootlessImageSet, RootlessImageSetError

    wrong_commit = list(_image_manifests(tmp_path / "commit", task_ids=("task-a",)))
    proxy_path = next(
        path for path in wrong_commit if json.loads(path.read_text())["role"] == "proxy"
    )
    proxy = json.loads(proxy_path.read_text())
    proxy["benchmark_commit"] = "f" * 40
    proxy_path.write_text(json.dumps(proxy, sort_keys=True, indent=2) + "\n")
    with pytest.raises(RootlessImageSetError, match="benchmark commit"):
        RootlessImageSet.from_manifest_paths(
            benchmark_commit=COMMIT,
            task_ids=("task-a",),
            manifest_paths=wrong_commit,
        )

    mutable = list(_image_manifests(tmp_path / "mutable", task_ids=("task-a",)))
    proxy_path = next(
        path for path in mutable if json.loads(path.read_text())["role"] == "proxy"
    )
    proxy = json.loads(proxy_path.read_text())
    proxy["image_id"] = "qea-proxy:latest"
    proxy_path.write_text(json.dumps(proxy, sort_keys=True, indent=2) + "\n")
    with pytest.raises(RootlessImageSetError, match="immutable image"):
        RootlessImageSet.from_manifest_paths(
            benchmark_commit=COMMIT,
            task_ids=("task-a",),
            manifest_paths=mutable,
        )

    lock_drift = _image_manifests(tmp_path / "lock", task_ids=("task-a",))
    proxy_path = next(
        path for path in lock_drift if json.loads(path.read_text())["role"] == "proxy"
    )
    proxy_path.with_name("dependency-lock.txt").write_text("changed==9.9\n")
    with pytest.raises(RootlessImageSetError, match="dependency lock"):
        RootlessImageSet.from_manifest_paths(
            benchmark_commit=COMMIT,
            task_ids=("task-a",),
            manifest_paths=lock_drift,
        )

    resources = _image_manifests(tmp_path / "resources", task_ids=("task-a",))
    resource_set = RootlessImageSet.from_manifest_paths(
        benchmark_commit=COMMIT,
        task_ids=("task-a",),
        manifest_paths=resources,
    )
    resource_index = tmp_path / "resource-image-set.json"
    resource_set.write(resource_index)
    verifier_path = next(
        path
        for path in resources
        if json.loads(path.read_text())["role"] == "verifier"
    )
    verifier = json.loads(verifier_path.read_text())
    verifier["cpu_count"] = 4
    identity_payload = {
        key: verifier[key]
        for key in (
            "role",
            "task_id",
            "benchmark_commit",
            "base_image_ref",
            "source_manifest_sha256",
            "verifier_test_script_sha256",
            "context_files",
            "cpu_count",
            "memory_mb",
            "build_timeout_seconds",
            "build_network",
        )
    }
    verifier["identity_sha256"] = _sha256_json(identity_payload)
    verifier_path.write_text(json.dumps(verifier, sort_keys=True, indent=2) + "\n")
    with pytest.raises(RootlessImageSetError, match="referenced manifest"):
        RootlessImageSet.load(resource_index)


def test_image_set_load_rejects_tampered_identity_and_referenced_manifest(tmp_path) -> None:
    from qea.rootless_image_set import RootlessImageSet, RootlessImageSetError

    manifests = _image_manifests(tmp_path / "manifests", task_ids=("task-a",))
    image_set = RootlessImageSet.from_manifest_paths(
        benchmark_commit=COMMIT,
        task_ids=("task-a",),
        manifest_paths=manifests,
    )
    index = tmp_path / "image-set.json"
    second_index = tmp_path / "image-set-referenced-tamper.json"
    image_set.write(index)
    image_set.write(second_index)

    tampered = json.loads(index.read_text())
    tampered["proxy"]["image_id"] = "sha256:" + "f" * 64
    index.write_text(json.dumps(tampered, sort_keys=True, indent=2) + "\n")
    with pytest.raises(RootlessImageSetError, match="top-level identity"):
        RootlessImageSet.load(index)

    proxy_path = next(
        path for path in manifests if json.loads(path.read_text())["role"] == "proxy"
    )
    proxy = json.loads(proxy_path.read_text())
    proxy["docker_version"] = "99.0.0"
    proxy_path.write_text(json.dumps(proxy, sort_keys=True, indent=2) + "\n")
    with pytest.raises(RootlessImageSetError, match="referenced manifest"):
        RootlessImageSet.load(second_index)


def test_explicit_image_set_assembler_cli_writes_one_index(tmp_path) -> None:
    manifests = _image_manifests(tmp_path / "manifests", task_ids=("task-a",))
    output = tmp_path / "formal-image-set.json"
    repository = Path(__file__).resolve().parents[1]
    argv = [
        sys.executable,
        "scripts/assemble_qfbench_rootless_image_set.py",
        "--benchmark-commit",
        COMMIT,
        "--task-id",
        "task-a",
        "--output",
        str(output),
    ]
    for path in manifests:
        argv.extend(("--manifest", str(path)))

    result = subprocess.run(
        argv,
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert output.is_file()
    assert "identity sha256:" in result.stdout
    assert "tasks: task-a" in result.stdout
