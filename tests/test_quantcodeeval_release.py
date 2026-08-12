from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from qea.quantcodeeval_release import (
    QuantCodeEvalReleaseError,
    build_quantcodeeval_release_manifest,
    publish_quantcodeeval_release,
    validate_quantcodeeval_release,
)


def _tree(root: Path, files: dict[str, str]) -> Path:
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root


def _inputs(tmp_path: Path) -> dict[str, Path]:
    return {
        "source_root": _tree(
            tmp_path / "source",
            {"qea/adapter.py": "adapter\n", "scripts/run.py": "run\n"},
        ),
        "public_root": _tree(
            tmp_path / "public",
            {
                "MANIFEST.json": "{}\n",
                "tasks/T16/instruction.md": "public instruction\n",
            },
        ),
        "trusted_root": _tree(
            tmp_path / "trusted",
            {
                "MANIFEST.json": "{}\n",
                "tasks/T16/tests/golden_ref.py": "answer = 1\n",
            },
        ),
        "image_result": _tree(
            tmp_path / "image-result",
            {
                "MANIFEST.json": '{"image_id":"sha256:test"}\n',
                "dependency-lock.txt": "numpy==2.4.6\n",
            },
        ),
        "no_model_audit_result": _tree(
            tmp_path / "no-model-audit",
            {"RESULT.json": '{"zero_model_requests":true}\n'},
        ),
    }


def test_release_is_content_addressed_canonical_and_reusable(tmp_path):
    inputs = _inputs(tmp_path)
    h0 = tmp_path / "h0.json"
    h0.write_text('{"status":"complete"}\n', encoding="utf-8")
    planned = build_quantcodeeval_release_manifest(**inputs, h0_result=h0)

    first = publish_quantcodeeval_release(
        **inputs,
        h0_result=h0,
        output_root=tmp_path / "published",
    )
    assert first.release_dir.name == planned["identity_sha256"]
    assert first.manifest_path.name == "RELEASE.json"
    assert not first.reused_existing
    assert json.loads(first.manifest_path.read_text()) == planned
    assert (first.release_dir / "h0/RESULT.json").read_bytes() == h0.read_bytes()
    report = validate_quantcodeeval_release(first.release_dir)
    assert report["identity_sha256"] == first.identity_sha256
    assert report["surface_names"] == [
        "source", "public", "trusted", "image", "no-model", "h0"
    ]

    second = publish_quantcodeeval_release(
        **inputs,
        h0_result=h0,
        output_root=tmp_path / "published",
    )
    assert second.release_dir == first.release_dir
    assert second.reused_existing
    assert second.manifest_sha256 == first.manifest_sha256


def test_optional_result_changes_identity_and_directory_result_is_complete(tmp_path):
    inputs = _inputs(tmp_path)
    base = build_quantcodeeval_release_manifest(**inputs)
    pgbhs = _tree(
        tmp_path / "pgbhs",
        {
            "RESULT.json": '{"iterations":5}\n',
            "iterations/01/evidence.json": '{"act":true}\n',
        },
    )
    expanded = build_quantcodeeval_release_manifest(**inputs, pgbhs_result=pgbhs)

    assert base["identity_sha256"] != expanded["identity_sha256"]
    pgbhs_surface = next(
        item for item in expanded["surfaces"] if item["name"] == "pgbhs"
    )
    assert [item["path"] for item in pgbhs_surface["members"]] == [
        "RESULT.json", "iterations/01/evidence.json"
    ]


@pytest.mark.parametrize(
    "surface_name",
    (
        "source_root",
        "public_root",
        "trusted_root",
        "image_result",
        "no_model_audit_result",
    ),
)
def test_release_rejects_symlink_in_every_required_surface(tmp_path, surface_name):
    inputs = _inputs(tmp_path)
    surface = inputs[surface_name]
    if surface.is_file():
        target = surface
        link = surface.with_name(surface.name + "-link")
        link.symlink_to(target)
        inputs[surface_name] = link
    else:
        target = next(path for path in surface.rglob("*") if path.is_file())
        link = surface / "unsafe-link"
        try:
            link.symlink_to(target)
        except OSError:
            pytest.skip("symlinks are unavailable")
    with pytest.raises(QuantCodeEvalReleaseError, match="symlink"):
        build_quantcodeeval_release_manifest(**inputs)


def test_validator_rejects_file_directory_and_top_level_extras(tmp_path):
    inputs = _inputs(tmp_path)
    first = publish_quantcodeeval_release(
        **inputs, output_root=tmp_path / "published-one"
    )
    (first.release_dir / "public/extra.txt").write_text("extra\n")
    with pytest.raises(QuantCodeEvalReleaseError, match="membership differs"):
        validate_quantcodeeval_release(first.release_dir)

    second = publish_quantcodeeval_release(
        **inputs, output_root=tmp_path / "published-two"
    )
    (second.release_dir / "source/empty-extra").mkdir()
    with pytest.raises(QuantCodeEvalReleaseError, match="membership differs"):
        validate_quantcodeeval_release(second.release_dir)

    third = publish_quantcodeeval_release(
        **inputs, output_root=tmp_path / "published-three"
    )
    (third.release_dir / "negative-evidence.json").write_text("{}\n")
    with pytest.raises(QuantCodeEvalReleaseError, match="top-level membership differs"):
        validate_quantcodeeval_release(third.release_dir)


def test_validator_and_republisher_reject_published_byte_drift(tmp_path):
    inputs = _inputs(tmp_path)
    result = publish_quantcodeeval_release(
        **inputs, output_root=tmp_path / "published"
    )
    member = result.release_dir / "trusted/tasks/T16/tests/golden_ref.py"
    member.write_text("answer = 2\n")

    with pytest.raises(QuantCodeEvalReleaseError, match="drifted"):
        validate_quantcodeeval_release(result.release_dir)
    with pytest.raises(QuantCodeEvalReleaseError, match="drifted"):
        publish_quantcodeeval_release(
            **inputs, output_root=tmp_path / "published"
        )


def test_existing_partial_and_negative_evidence_are_preserved(tmp_path):
    inputs = _inputs(tmp_path)
    manifest = build_quantcodeeval_release_manifest(**inputs)
    output = tmp_path / "published"
    partial = output / f"{manifest['identity_sha256']}.partial"
    partial.mkdir(parents=True)
    negative = partial / "negative-evidence.json"
    negative.write_text('{"failure":"interrupted"}\n')

    with pytest.raises(QuantCodeEvalReleaseError, match="preserved and blocks"):
        publish_quantcodeeval_release(**inputs, output_root=output)
    assert negative.read_text() == '{"failure":"interrupted"}\n'


def test_input_extra_appearing_during_publish_is_rejected_and_partial_preserved(
    tmp_path, monkeypatch
):
    import qea.quantcodeeval_release as release

    inputs = _inputs(tmp_path)
    expected = build_quantcodeeval_release_manifest(**inputs)
    original = release._copy_surface
    injected = False

    def copy_then_drift(surface, staging):
        nonlocal injected
        original(surface, staging)
        if surface.name == "source" and not injected:
            injected = True
            (inputs["source_root"] / "late-extra.py").write_text("late = True\n")

    monkeypatch.setattr(release, "_copy_surface", copy_then_drift)
    output = tmp_path / "published"
    with pytest.raises(QuantCodeEvalReleaseError, match="drifted while publishing"):
        publish_quantcodeeval_release(**inputs, output_root=output)
    partial = output / f"{expected['identity_sha256']}.partial"
    assert partial.is_dir()
    assert (partial / "source/qea/adapter.py").is_file()
    assert not (partial / "source/late-extra.py").exists()


def test_manifest_is_canonical_and_detects_permission_drift(tmp_path):
    inputs = _inputs(tmp_path)
    inputs["trusted_root"].chmod(0o700)
    member = inputs["trusted_root"] / "tasks/T16/tests/golden_ref.py"
    member.chmod(0o600)
    result = publish_quantcodeeval_release(
        **inputs, output_root=tmp_path / "published"
    )
    raw = result.manifest_path.read_bytes()
    payload = json.loads(raw)
    assert raw == (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode()
    published_member = result.release_dir / "trusted/tasks/T16/tests/golden_ref.py"
    published_member.chmod(0o644)
    with pytest.raises(QuantCodeEvalReleaseError, match="drifted"):
        validate_quantcodeeval_release(result.release_dir)


def test_cli_plan_only_does_not_publish_or_create_bytecode(tmp_path):
    inputs = _inputs(tmp_path)
    output = tmp_path / "published"
    script = Path(__file__).resolve().parents[1] / "scripts/publish_quantcodeeval_release.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--source-root", str(inputs["source_root"]),
            "--public-root", str(inputs["public_root"]),
            "--trusted-root", str(inputs["trusted_root"]),
            "--image-result", str(inputs["image_result"]),
            "--no-model-audit-result", str(inputs["no_model_audit_result"]),
            "--output-root", str(output),
            "--plan-only",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["benchmark"] == "quantcodeeval"
    assert not output.exists()
    assert not list(inputs["source_root"].rglob("__pycache__"))
    assert not list(inputs["source_root"].rglob("*.pyc"))
