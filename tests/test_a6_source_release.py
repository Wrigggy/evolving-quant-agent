import json
import subprocess
import sys
from pathlib import Path

import pytest

from qea.a6_source_release import (
    A6SourceReleaseError,
    build_a6_source_release_manifest,
    validate_a6_source_release,
)


_REQUIRED = (
    "pyproject.toml",
    "run.py",
    "qea/__init__.py",
    "qea/a6_source_release.py",
    "qea/qfbench_a6.py",
    "scripts/audit_qfbench_a6_discovery.py",
    "scripts/build_qfbench_a6_evidence.py",
    "scripts/materialize_a6_prelaunch_identity.py",
    "scripts/run_qfbench_component_pilot.py",
    "scripts/run_qfbench_discovery_pilot.py",
    "data/qfbench/MANIFEST_A6_EXPANDED_CANARY.json",
    "docs/PROJECT_MEMORY.md",
    (
        "docs/decisions/2026-08-09-qfbench-a6-expanded-panel-"
        "feedback-and-mutation-protocol.md"
    ),
)


def _release(tmp_path: Path) -> Path:
    root = tmp_path / "release"
    for relative in _REQUIRED:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"fixture:{relative}\n")
    (root / "qea/evolve_agent_full/agent.yaml").parent.mkdir(
        parents=True, exist_ok=True
    )
    (root / "qea/evolve_agent_full/agent.yaml").write_text("type: agent\n")
    return root


def _canonical_write(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )


def test_source_release_manifest_is_canonical_and_binds_exact_tree(tmp_path):
    root = _release(tmp_path)
    manifest = tmp_path / "release-manifest.json"

    built = build_a6_source_release_manifest(root, manifest)
    validated = validate_a6_source_release(root, manifest)

    assert built == validated
    assert built["member_count"] == len(_REQUIRED) + 1
    payload = json.loads(manifest.read_text())
    paths = [item["path"] for item in payload["members"]]
    assert paths == sorted(paths)
    assert payload["tree_sha256"] == built["tree_sha256"]

    (root / "qea/qfbench_a6.py").write_text("drift\n")
    with pytest.raises(A6SourceReleaseError, match="size drifted|digest drifted"):
        validate_a6_source_release(root, manifest)


@pytest.mark.parametrize(
    "relative,error",
    (
        ("qea/._qfbench_a6.py", "AppleDouble"),
        ("qea/__pycache__/module.py", "cache, result, runtime, or secret"),
        ("qea/secrets/token.json", "cache, result, runtime, or secret"),
        ("results/result.json", "cache, result, runtime, or secret"),
        ("notes.txt", "outside the A6 allowlist"),
    ),
)
def test_source_release_builder_rejects_junk_and_unallowlisted_files(
    tmp_path, relative, error
):
    root = _release(tmp_path)
    junk = root / relative
    junk.parent.mkdir(parents=True, exist_ok=True)
    junk.write_text("junk\n")

    with pytest.raises(A6SourceReleaseError, match=error):
        build_a6_source_release_manifest(root, tmp_path / "manifest.json")


def test_source_release_rejects_symlinks_and_internal_manifest(tmp_path):
    root = _release(tmp_path)
    target = root / "qea/qfbench_a6.py"
    link = root / "qea/linked.py"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlinks are unavailable")

    with pytest.raises(A6SourceReleaseError, match="symlink"):
        build_a6_source_release_manifest(root, tmp_path / "manifest.json")
    link.unlink()
    with pytest.raises(A6SourceReleaseError, match="outside the release root"):
        build_a6_source_release_manifest(root, root / "manifest.json")


def test_source_release_validator_rejects_unsorted_duplicate_and_extra_members(
    tmp_path,
):
    root = _release(tmp_path)
    manifest = tmp_path / "manifest.json"
    build_a6_source_release_manifest(root, manifest)

    payload = json.loads(manifest.read_text())
    payload["members"] = list(reversed(payload["members"]))
    _canonical_write(manifest, payload)
    with pytest.raises(A6SourceReleaseError, match="not canonically sorted"):
        validate_a6_source_release(root, manifest)

    build_a6_source_release_manifest(root, manifest, overwrite=True)
    payload = json.loads(manifest.read_text())
    payload["members"].insert(1, dict(payload["members"][0]))
    payload["member_count"] += 1
    _canonical_write(manifest, payload)
    with pytest.raises(A6SourceReleaseError, match="not canonically sorted|duplicate"):
        validate_a6_source_release(root, manifest)

    build_a6_source_release_manifest(root, manifest, overwrite=True)
    (root / "qea/new_module.py").write_text("new = True\n")
    with pytest.raises(A6SourceReleaseError, match="membership differs"):
        validate_a6_source_release(root, manifest)


def test_source_release_validator_requires_canonical_manifest_bytes(tmp_path):
    root = _release(tmp_path)
    manifest = tmp_path / "manifest.json"
    build_a6_source_release_manifest(root, manifest)
    payload = json.loads(manifest.read_text())
    manifest.write_text(json.dumps(payload) + "\n")

    with pytest.raises(A6SourceReleaseError, match="not canonical JSON"):
        validate_a6_source_release(root, manifest)


def test_release_manifest_entrypoint_does_not_mutate_release_with_bytecode(
    tmp_path,
):
    repository = Path(__file__).resolve().parents[1]
    root = _release(tmp_path)
    (root / "qea/__init__.py").write_text("")
    for relative in (
        "qea/a6_source_release.py",
        "scripts/build_a6_source_release_manifest.py",
    ):
        (root / relative).write_bytes((repository / relative).read_bytes())
    manifest = tmp_path / "manifest.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/build_a6_source_release_manifest.py"),
            "--release-root",
            str(root),
            "--manifest",
            str(manifest),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert not list(root.rglob("__pycache__"))
    assert not list(root.rglob("*.pyc"))
    validate_a6_source_release(root, manifest)
