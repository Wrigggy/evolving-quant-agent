from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from qea.evolver_profile import materialize_evolver_profile


def _source_evolver(root: Path) -> Path:
    source = root / "source"
    source.mkdir()
    (source / "agent.yaml").write_text(
        "type: agent\n"
        "llm_config:\n"
        "  model: ${env.LLM_MODEL}\n"
        "  timeout: 180\n",
        encoding="utf-8",
    )
    (source / "systemprompt.md").write_text("Discover.\n", encoding="utf-8")
    return source


def test_materialized_evolver_binds_route_without_hardcoding_model(tmp_path: Path) -> None:
    source = _source_evolver(tmp_path)
    destination = tmp_path / "run" / "evolver"

    profile = materialize_evolver_profile(
        source,
        destination,
        model="research/model-a",
        provider="provider-a",
        reasoning_effort="none",
    )

    agent = (destination / "agent.yaml").read_text(encoding="utf-8")
    assert "${env.LLM_MODEL}" in agent
    assert "research/model-a" not in agent
    assert "extra_body" not in agent
    manifest = json.loads(
        (destination / ".qea-runtime-profile.json").read_text(encoding="utf-8")
    )
    assert manifest["model"] == "research/model-a"
    assert manifest["provider"] == "provider-a"
    assert manifest["reasoning_effort"] == "none"
    assert profile.materialized_dir == str(destination.resolve())


def test_materialized_evolver_adds_only_selected_deliberation_request(
    tmp_path: Path,
) -> None:
    source = _source_evolver(tmp_path)
    destination = tmp_path / "run" / "evolver"

    first = materialize_evolver_profile(
        source,
        destination,
        model="research/model-r",
        provider="provider-r",
        reasoning_effort="high",
    )
    resumed = materialize_evolver_profile(
        source,
        destination,
        model="research/model-r",
        provider="provider-r",
        reasoning_effort="high",
    )

    agent = (destination / "agent.yaml").read_text(encoding="utf-8")
    agent_config = yaml.safe_load(agent)
    assert "effort: high" in agent
    assert "exclude: true" in agent
    assert agent_config["llm_config"]["extra_body"] == {
        "reasoning": {"effort": "high", "exclude": True}
    }
    assert first.materialized_sha256 == resumed.materialized_sha256


def test_materialized_evolver_refuses_route_change_on_resume(tmp_path: Path) -> None:
    source = _source_evolver(tmp_path)
    destination = tmp_path / "run" / "evolver"
    materialize_evolver_profile(
        source,
        destination,
        model="research/model-a",
        provider="provider-a",
        reasoning_effort="none",
    )

    with pytest.raises(ValueError, match="persisted evolver runtime profile differs"):
        materialize_evolver_profile(
            source,
            destination,
            model="research/model-b",
            provider="provider-b",
            reasoning_effort="none",
        )


def test_repository_evolver_source_is_model_neutral(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[1] / "qea" / "evolve_agent_full"
    destination = tmp_path / "evolver"

    materialize_evolver_profile(
        source,
        destination,
        model="research/model-a",
        provider="provider-a",
        reasoning_effort="xhigh",
    )

    source_agent = (source / "agent.yaml").read_text(encoding="utf-8")
    materialized_agent = (destination / "agent.yaml").read_text(encoding="utf-8")
    assert "extra_body" not in source_agent
    assert "effort: xhigh" in materialized_agent


def test_runtime_profile_digest_ignores_interpreter_cache(tmp_path: Path) -> None:
    source = _source_evolver(tmp_path)
    first_destination = tmp_path / "first" / "evolver"
    first = materialize_evolver_profile(
        source,
        first_destination,
        model="research/model-a",
        provider="provider-a",
        reasoning_effort="none",
    )
    cache = source / "__pycache__"
    cache.mkdir()
    (cache / "generated.cpython-314.pyc").write_bytes(b"runtime cache")
    second_destination = tmp_path / "second" / "evolver"
    second = materialize_evolver_profile(
        source,
        second_destination,
        model="research/model-a",
        provider="provider-a",
        reasoning_effort="none",
    )

    assert first.source_sha256 == second.source_sha256
    assert first.materialized_sha256 == second.materialized_sha256
    assert not (second_destination / "__pycache__").exists()


def test_runtime_profile_rejects_hardcoded_source_model(tmp_path: Path) -> None:
    source = _source_evolver(tmp_path)
    agent_path = source / "agent.yaml"
    agent_path.write_text(
        agent_path.read_text(encoding="utf-8").replace(
            "${env.LLM_MODEL}", "research/hardcoded"
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="runtime-selected model"):
        materialize_evolver_profile(
            source,
            tmp_path / "run" / "evolver",
            model="research/model-a",
            provider="provider-a",
            reasoning_effort="none",
        )
