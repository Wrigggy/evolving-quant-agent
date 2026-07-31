from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


COMMIT = "024921eb507fcc0c4ffe3e0a96802724be1ae84a"
UPSTREAM_BASE = "docker.io/library/python@sha256:" + "a" * 64
BASE_IMAGE_ID = "sha256:" + "b" * 64
PLAN_IDENTITY_KEYS = (
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
_DEFAULT_VERIFIER_TEST_SHA256 = object()


def _sha256_json(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _result_identity(manifest: dict[str, object]) -> str:
    return _sha256_json(
        {
            "plan_identity_sha256": manifest["plan_identity_sha256"],
            "image_id": manifest["image_id"],
            "dependency_lock_sha256": manifest["dependency_lock_sha256"],
            "docker_version": manifest["docker_version"],
            "docker_security_options": sorted(
                manifest["docker_security_options"]
            ),
        }
    )


def _rehash_manifest(path: Path) -> dict[str, object]:
    manifest = json.loads(path.read_text())
    manifest["plan_identity_sha256"] = _sha256_json(
        {key: manifest[key] for key in PLAN_IDENTITY_KEYS}
    )
    manifest["result_identity_sha256"] = _result_identity(manifest)
    manifest["identity_sha256"] = manifest["result_identity_sha256"]
    path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    return manifest


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
    verifier_test_script_sha256: object = _DEFAULT_VERIFIER_TEST_SHA256,
) -> Path:
    lock = f"{role}-runtime==1.0\n".encode()
    dockerfile = f"FROM {base_image_ref}\n".encode()
    context_files = [
        {
            "path": "Dockerfile",
            "mode": "0o644",
            "sha256": hashlib.sha256(dockerfile).hexdigest(),
            "size_bytes": len(dockerfile),
        }
    ]
    if verifier_test_script_sha256 is _DEFAULT_VERIFIER_TEST_SHA256:
        verifier_test_script_sha256 = "d" * 64 if role == "verifier" else None
    identity_payload = {
        "role": role,
        "task_id": task_id,
        "benchmark_commit": benchmark_commit,
        "base_image_ref": base_image_ref,
        "source_manifest_sha256": "c" * 64,
        "verifier_test_script_sha256": verifier_test_script_sha256,
        "context_files": context_files,
        "cpu_count": cpu_count,
        "memory_mb": memory_mb,
        "build_timeout_seconds": build_timeout_seconds,
        "build_network": "default",
    }
    image_id = "sha256:" + image_digit * 64
    plan_identity = _sha256_json(identity_payload)
    manifest = {
        "schema_version": 1,
        **identity_payload,
        "dockerfile_sha256": hashlib.sha256(dockerfile).hexdigest(),
        "plan_identity_sha256": plan_identity,
        "identity_kind": "measured-result",
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
    manifest["result_identity_sha256"] = _result_identity(manifest)
    manifest["identity_sha256"] = manifest["result_identity_sha256"]
    publication = root / manifest["result_identity_sha256"]
    (publication / "context").mkdir(parents=True)
    (publication / "dependency-lock.txt").write_bytes(lock)
    (publication / "context" / "Dockerfile").write_bytes(dockerfile)
    path = publication / "MANIFEST.json"
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


def test_real_image_set_preserves_verifier_material_identity_for_factory(
    tmp_path, monkeypatch
) -> None:
    from qea.rootless_full_harness import (
        RootlessFullHarnessError,
        _verify_benchmark_materials,
    )
    from qea.rootless_image_set import RootlessImageSet
    import qea.rootless_images as rootless_images

    manifests = _image_manifests(tmp_path / "manifests", task_ids=("task-a",))
    rewritten_manifests = []
    for manifest_path in manifests:
        manifest = json.loads(manifest_path.read_text())
        if manifest["role"] in {"base", "proxy", "evolver"}:
            manifest["source_manifest_sha256"] = "a" * 64
            manifest_path.write_text(
                json.dumps(manifest, sort_keys=True, indent=2)
            )
            manifest = _rehash_manifest(manifest_path)
            publication = (
                manifest_path.parent.parent / manifest["result_identity_sha256"]
            )
            manifest_path.parent.rename(publication)
            manifest_path = publication / "MANIFEST.json"
        rewritten_manifests.append(manifest_path)
    manifests = tuple(rewritten_manifests)
    selected = RootlessImageSet.from_manifest_paths(
        benchmark_commit=COMMIT,
        task_ids=("task-a",),
        manifest_paths=manifests,
    )
    index = tmp_path / "image-set.json"
    selected.write(index)
    loaded = RootlessImageSet.load(index)

    verifier = loaded.tasks[0]["verifier"]
    assert verifier["verifier_test_script_sha256"] == "d" * 64

    public = SimpleNamespace(
        commit=COMMIT,
        task_ids=("task-a",),
        manifest_sha256="c" * 64,
        records={},
    )
    trusted = SimpleNamespace(
        commit=COMMIT,
        task_ids=("task-a",),
        manifest_sha256="e" * 64,
        records={
            "tasks/task-a/tests/test.sh": {
                "sha256": "d" * 64,
                "git_blob_oid": "f" * 40,
                "size_bytes": 17,
                "mode": "100755",
            }
        },
    )
    roots = {"public": public, "trusted-verifier": trusted}
    monkeypatch.setattr(
        rootless_images,
        "verify_role_root",
        lambda root, expected_role: roots[expected_role],
    )

    identity = _verify_benchmark_materials(
        config=SimpleNamespace(
            public_root=tmp_path / "public",
            trusted_root=tmp_path / "trusted",
        ),
        image_set=loaded,
        benchmark_commit=COMMIT,
        task_ids=("task-a",),
    )

    assert len(identity) == 64

    drifted_worker = dict(loaded.tasks[0]["worker"])
    drifted_worker["source_manifest_sha256"] = "f" * 64
    drifted_image_set = SimpleNamespace(
        base=loaded.base,
        proxy=loaded.proxy,
        evolver=loaded.evolver,
        tasks=(
            {
                "task_id": "task-a",
                "worker": drifted_worker,
                "verifier": loaded.tasks[0]["verifier"],
            },
        ),
    )
    with pytest.raises(
        RootlessFullHarnessError, match="selected task images"
    ):
        _verify_benchmark_materials(
            config=SimpleNamespace(
                public_root=tmp_path / "public",
                trusted_root=tmp_path / "trusted",
            ),
            image_set=drifted_image_set,
            benchmark_commit=COMMIT,
            task_ids=("task-a",),
        )


@pytest.mark.parametrize(
    ("role", "verifier_test_script_sha256"),
    (("verifier", None), ("worker", "d" * 64)),
)
def test_image_set_rejects_role_inconsistent_verifier_material_identity(
    tmp_path, role: str, verifier_test_script_sha256: str | None
) -> None:
    from qea.rootless_image_set import RootlessImageSet, RootlessImageSetError

    manifests = list(_image_manifests(tmp_path, task_ids=("task-a",)))
    role_index = next(
        index
        for index, path in enumerate(manifests)
        if json.loads(path.read_text())["role"] == role
    )
    manifests[role_index] = _write_image_manifest(
        tmp_path / f"invalid-{role}",
        role=role,
        task_id="task-a",
        image_digit="f",
        verifier_test_script_sha256=verifier_test_script_sha256,
    )

    with pytest.raises(
        RootlessImageSetError, match="verifier test script identity"
    ):
        RootlessImageSet.from_manifest_paths(
            benchmark_commit=COMMIT,
            task_ids=("task-a",),
            manifest_paths=manifests,
        )


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
    verifier_path.write_text(json.dumps(verifier, sort_keys=True, indent=2) + "\n")
    _rehash_manifest(verifier_path)
    with pytest.raises(RootlessImageSetError, match="referenced manifest"):
        RootlessImageSet.load(resource_index)


@pytest.mark.parametrize("mutation", ("resource", "role", "context"))
def test_fresh_assembly_rejects_self_consistent_manifest_edit_at_old_anchor(
    tmp_path, mutation: str
) -> None:
    from qea.rootless_image_set import RootlessImageSet, RootlessImageSetError

    manifests = _image_manifests(tmp_path, task_ids=("task-a",))
    evolver_path = next(
        path for path in manifests if json.loads(path.read_text())["role"] == "evolver"
    )
    manifest = json.loads(evolver_path.read_text())
    if mutation == "resource":
        manifest["cpu_count"] = 8
    elif mutation == "role":
        manifest["role"] = "proxy"
    else:
        dockerfile = b"FROM sha256:" + b"b" * 64 + b"\n# changed\n"
        dockerfile_sha256 = hashlib.sha256(dockerfile).hexdigest()
        manifest["context_files"][0]["sha256"] = dockerfile_sha256
        manifest["context_files"][0]["size_bytes"] = len(dockerfile)
        manifest["dockerfile_sha256"] = dockerfile_sha256
        (evolver_path.parent / "context" / "Dockerfile").write_bytes(dockerfile)
    evolver_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    _rehash_manifest(evolver_path)

    with pytest.raises(RootlessImageSetError, match="publication path"):
        RootlessImageSet.from_manifest_paths(
            benchmark_commit=COMMIT,
            task_ids=("task-a",),
            manifest_paths=manifests,
        )


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


def test_image_set_rejects_manifest_index_and_output_leaf_symlinks(tmp_path) -> None:
    from qea.rootless_image_set import RootlessImageSet, RootlessImageSetError

    manifests = list(_image_manifests(tmp_path / "manifests", task_ids=("task-a",)))
    proxy_index = next(
        index
        for index, path in enumerate(manifests)
        if json.loads(path.read_text())["role"] == "proxy"
    )
    proxy_link = tmp_path / "proxy-MANIFEST.json"
    proxy_link.symlink_to(manifests[proxy_index])
    manifests[proxy_index] = proxy_link
    with pytest.raises(RootlessImageSetError, match="non-symlink"):
        RootlessImageSet.from_manifest_paths(
            benchmark_commit=COMMIT,
            task_ids=("task-a",),
            manifest_paths=manifests,
        )

    real_manifests = _image_manifests(tmp_path / "real", task_ids=("task-a",))
    image_set = RootlessImageSet.from_manifest_paths(
        benchmark_commit=COMMIT,
        task_ids=("task-a",),
        manifest_paths=real_manifests,
    )
    index = tmp_path / "image-set.json"
    image_set.write(index)
    index_link = tmp_path / "image-set-link.json"
    index_link.symlink_to(index)
    with pytest.raises(RootlessImageSetError, match="non-symlink"):
        RootlessImageSet.load(index_link)

    output_link = tmp_path / "dangling-image-set.json"
    output_link.symlink_to(tmp_path / "does-not-exist.json")
    with pytest.raises(RootlessImageSetError, match="output symlink"):
        image_set.write(output_link)


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
