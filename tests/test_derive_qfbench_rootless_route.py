from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from scripts.derive_qfbench_rootless_route import derive_route_config


def test_derive_route_config_changes_only_model_route(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    destination = tmp_path / "derived.json"
    original = {
        "schema_version": 5,
        "allowed_model": "deepseek/deepseek-v4-flash-0731",
        "required_provider": "deepseek",
        "sentinel": {"unchanged": True},
    }
    source.write_text(json.dumps(original), encoding="utf-8")

    derived = derive_route_config(
        source,
        destination,
        model="research/model-a",
        provider="provider-a",
    )

    assert derived == {
        **original,
        "allowed_model": "research/model-a",
        "required_provider": "provider-a",
    }
    assert json.loads(destination.read_text(encoding="utf-8")) == derived
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600


def test_derive_route_config_refuses_overwrite(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    destination = tmp_path / "derived.json"
    source.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "allowed_model": "old/model",
                "required_provider": "old",
            }
        ),
        encoding="utf-8",
    )
    destination.write_text("preserve", encoding="utf-8")

    with pytest.raises(FileExistsError):
        derive_route_config(
            source,
            destination,
            model="research/model-a",
            provider="provider-a",
        )
    assert destination.read_text(encoding="utf-8") == "preserve"
