from __future__ import annotations

import json
import stat
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


def test_materialized_evolver_supports_read_only_content_addressed_source(
    tmp_path: Path,
) -> None:
    source = _source_evolver(tmp_path)
    nested = source / "reference"
    nested.mkdir()
    (nested / "guide.md").write_text("Public guidance.\n", encoding="utf-8")
    executable = source / "tools" / "runner.sh"
    executable.parent.mkdir()
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    source_files = [path for path in source.rglob("*") if path.is_file()]
    source_dirs = [source, *(path for path in source.rglob("*") if path.is_dir())]
    for path in source_files:
        path.chmod(0o555 if path == executable else 0o444)
    for path in reversed(source_dirs):
        path.chmod(0o555)
    source_snapshot = {
        path.relative_to(source).as_posix(): (
            path.read_bytes(),
            stat.S_IMODE(path.stat().st_mode),
        )
        for path in source_files
    }
    source_dir_modes = {
        path.relative_to(source).as_posix(): stat.S_IMODE(path.stat().st_mode)
        for path in source_dirs
    }

    destination = tmp_path / "run" / "evolver"
    profile = materialize_evolver_profile(
        source,
        destination,
        model="research/model-a",
        provider="provider-a",
        reasoning_effort="high",
    )

    assert "effort: high" in (destination / "agent.yaml").read_text(
        encoding="utf-8"
    )
    assert (destination / ".qea-runtime-profile.json").is_file()
    assert all(
        stat.S_IMODE(path.stat().st_mode) == 0o700
        for path in (
            destination,
            *(item for item in destination.rglob("*") if item.is_dir()),
        )
    )
    assert all(
        stat.S_IMODE(path.stat().st_mode)
        == (0o700 if path.relative_to(destination) == Path("tools/runner.sh") else 0o600)
        for path in destination.rglob("*")
        if path.is_file()
    )
    assert profile.source_sha256
    assert {
        path.relative_to(source).as_posix(): (
            path.read_bytes(),
            stat.S_IMODE(path.stat().st_mode),
        )
        for path in source_files
    } == source_snapshot
    assert {
        path.relative_to(source).as_posix(): stat.S_IMODE(path.stat().st_mode)
        for path in source_dirs
    } == source_dir_modes


def test_read_only_source_failure_removes_private_temporary_copy(
    tmp_path: Path,
) -> None:
    source = _source_evolver(tmp_path)
    agent_path = source / "agent.yaml"
    agent_path.write_text(
        agent_path.read_text(encoding="utf-8").replace(
            "${env.LLM_MODEL}", "research/hardcoded"
        ),
        encoding="utf-8",
    )
    for path in (item for item in source.rglob("*") if item.is_file()):
        path.chmod(0o444)
    for path in reversed(
        [source, *(item for item in source.rglob("*") if item.is_dir())]
    ):
        path.chmod(0o555)
    destination = tmp_path / "run" / "evolver"

    with pytest.raises(ValueError, match="runtime-selected model"):
        materialize_evolver_profile(
            source,
            destination,
            model="research/model-a",
            provider="provider-a",
            reasoning_effort="high",
        )

    assert not destination.exists()
    assert not list(destination.parent.glob(".qea-evolver-profile-*"))


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
