import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from qea.loop_benchmark import hash_worker_directory
from qea.quantcodeeval_full_candidate import (
    QuantCodeEvalFullCandidateError,
    run_quantcodeeval_full_candidate,
)


def _worker(root: Path) -> Path:
    source = Path(__file__).resolve().parents[1] / "qea/worker_gdpval_weak"
    shutil.copytree(source, root)
    return root


def _candidate(parent: Path, root: Path) -> Path:
    shutil.copytree(parent, root)
    (root / "tools").mkdir()
    (root / "tools/__init__.py").write_text("")
    (root / "tools/check.py").write_text(
        "def check(value):\n    return {'ok': bool(value)}\n"
    )
    (root / "tool_descriptions/check.tool.yaml").write_text(
        "type: tool\nname: check\ndescription: Check one value.\n"
        "input_schema:\n  type: object\n  properties:\n"
        "    value: {type: boolean}\n  required: [value]\n"
        "  additionalProperties: false\n"
    )
    agent = (root / "agent.yaml").read_text()
    agent = agent.replace(
        "\ntracers:\n",
        "\n  - name: check\n"
        "    yaml_path: ./tool_descriptions/check.tool.yaml\n"
        "    binding: tools.check:check\n"
        "\ntracers:\n",
    )
    (root / "agent.yaml").write_text(agent)
    return root


def test_full_candidate_preflight_accepts_coherent_multifile_component(
    tmp_path, monkeypatch
):
    if not hasattr(sys, "stdlib_module_names"):
        monkeypatch.setattr(sys, "stdlib_module_names", frozenset(), raising=False)
    seed = _worker(tmp_path / "seed")
    candidate = _candidate(seed, tmp_path / "candidate")
    snapshot = SimpleNamespace(
        commit="9" * 40,
        optimize=SimpleNamespace(task_ids=("T16", "T24")),
    )
    preflight = {
        "public_manifest_sha256": "1" * 64,
        "trusted_manifest_sha256": "2" * 64,
        "runtime_identity_sha256": "3" * 64,
    }

    def fake_prepare(**kwargs):
        return snapshot, object(), preflight, seed

    monkeypatch.setattr(
        "qea.quantcodeeval_full_candidate.prepare_quantcodeeval_h0", fake_prepare
    )
    digest = hash_worker_directory(candidate)
    result = run_quantcodeeval_full_candidate(
        config_path=tmp_path / "config.json",
        public_root=tmp_path / "public",
        trusted_root=tmp_path / "trusted",
        run_dir=tmp_path / "candidate-run",
        seed_worker_dir=seed,
        parent_worker_dir=seed,
        candidate_worker_dir=candidate,
        iteration=1,
        mechanism="register one public boolean check",
        primary_components=("tools",),
        declared_roles=("agent_config", "tool_descriptions", "tools"),
        component_tests=(
            {"status": "passed", "kind": "tool", "candidate_digest": digest},
        ),
        activation={"status": "not_run"},
        worker_image_ref="sha256:" + "4" * 64,
        verifier_image_ref="sha256:" + "5" * 64,
        proxy_image_ref="sha256:" + "6" * 64,
        token_file=tmp_path / "token",
        source_h0_evaluation_id="7" * 64,
        preflight_only=True,
    )

    assert result["protocol"] == "quant_property_v2_full_candidate"
    assert result["candidate_worker_digest"] == digest
    assert result["primary_components"] == ["tools"]
    assert result["declared_roles"] == [
        "agent_config",
        "tool_descriptions",
        "tools",
    ]
    assert result["mutation_metrics"]["changed_file_count"] == 4
    assert result["mutation_metrics"]["declared_roles_match_actual"] is True


def test_full_candidate_rejects_failed_smoke_and_role_mismatch(tmp_path, monkeypatch):
    seed = _worker(tmp_path / "seed")
    candidate = _candidate(seed, tmp_path / "candidate")
    snapshot = SimpleNamespace(
        commit="9" * 40,
        optimize=SimpleNamespace(task_ids=("T16", "T24")),
    )
    monkeypatch.setattr(
        "qea.quantcodeeval_full_candidate.prepare_quantcodeeval_h0",
        lambda **kwargs: (
            snapshot,
            object(),
            {
                "public_manifest_sha256": "1" * 64,
                "trusted_manifest_sha256": "2" * 64,
                "runtime_identity_sha256": "3" * 64,
            },
            seed,
        ),
    )
    common = dict(
        config_path=tmp_path / "config.json",
        public_root=tmp_path / "public",
        trusted_root=tmp_path / "trusted",
        seed_worker_dir=seed,
        parent_worker_dir=seed,
        candidate_worker_dir=candidate,
        iteration=1,
        mechanism="test",
        primary_components=("tools",),
        activation={"status": "passed"},
        worker_image_ref="sha256:" + "4" * 64,
        verifier_image_ref="sha256:" + "5" * 64,
        proxy_image_ref="sha256:" + "6" * 64,
        token_file=tmp_path / "token",
        source_h0_evaluation_id="7" * 64,
        preflight_only=True,
    )
    with pytest.raises(QuantCodeEvalFullCandidateError, match="status=passed"):
        run_quantcodeeval_full_candidate(
            **common,
            run_dir=tmp_path / "failed-smoke",
            declared_roles=("agent_config", "tool_descriptions", "tools"),
            component_tests=({"status": "failed"},),
        )
    with pytest.raises(QuantCodeEvalFullCandidateError, match="declared"):
        run_quantcodeeval_full_candidate(
            **common,
            run_dir=tmp_path / "role-mismatch",
            declared_roles=("tools",),
            component_tests=({"status": "passed"},),
        )
