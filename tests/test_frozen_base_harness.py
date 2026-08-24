from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml

from qea.frozen_base_harness import (
    FrozenBaseHarnessError,
    SIX_QUANT_STATES,
    build_selected_runtime,
    freeze_base_harness,
    inspect_base_harness,
    validate_selected_runtime,
)
from scripts.freeze_qrs_base_harness import main


ROOT = Path(__file__).resolve().parents[1]
PRIMITIVE = ROOT / "qea/worker_quant_h0_s6_primitive_v1"


def _worker(tmp_path: Path) -> Path:
    destination = tmp_path / "source-worker"
    shutil.copytree(PRIMITIVE, destination)
    return destination


def _runtime(worker: Path) -> dict[str, object]:
    inspection = inspect_base_harness(worker)
    return build_selected_runtime(
        inspection["agent_config"],
        worker_model_route="deepseek-v4-flash-main0",
        rootless_config="runtime/qfbench-rootless.json",
    )


def test_inspection_enumerates_declared_prompt_skill_tools_and_states(
    tmp_path: Path,
) -> None:
    inspection = inspect_base_harness(_worker(tmp_path))

    assert inspection["agent_name"] == "qea_quant_h0_s6_primitive_v1_worker"
    assert inspection["registered_tools"] == [
        "run_shell_command",
        "record_quant_state",
    ]
    assert inspection["state_identifiers"] == list(SIX_QUANT_STATES)
    assert inspection["declared_prompt_surface"] == "systemprompt.md"
    assert inspection["declared_skill_surfaces"] == [
        "skills/quant-research-six-stage-workflow/SKILL.md"
    ]
    assert "tool_descriptions/record_quant_state.tool.yaml" in inspection[
        "worker_visible_surfaces"
    ]


def test_freeze_copies_worker_and_writes_scheduler_handoff(tmp_path: Path) -> None:
    worker = _worker(tmp_path)
    artifacts = tmp_path / "external-selection"
    artifacts.mkdir()
    output = tmp_path / "handoffs/QF_PRIMITIVE_H0_SELECTED.json"

    manifest = freeze_base_harness(
        worker_dir=worker,
        run_root=tmp_path / "run",
        selected_profile_id="primitive-selected-v1",
        selected_runtime=_runtime(worker),
        selection_artifact_root=artifacts,
        handoff_path=output,
    )

    frozen = Path(manifest["selected_worker_root"])
    assert output.is_file()
    assert json.loads(output.read_text(encoding="utf-8")) == manifest
    assert manifest["selection_complete"] is True
    assert manifest["selected_profile_id"] == "primitive-selected-v1"
    assert manifest["selected_agent_name"] == (
        "qea_quant_h0_s6_primitive_v1_worker"
    )
    assert manifest["selection_artifact_root"] == str(artifacts.resolve())
    assert manifest["frozen_for_qrs_scheduler"] is True
    assert manifest["selected_runtime"]["max_iterations"] == 60
    assert manifest["adapter_contract"]["state_identifiers"] == list(
        SIX_QUANT_STATES
    )
    assert manifest["adapter_contract"]["mutation_surfaces"] == [
        "skills/quant-research-six-stage-workflow/SKILL.md",
        "systemprompt.md",
    ]
    assert frozen == (
        tmp_path
        / "run/frozen-base-harness/primitive-selected-v1/worker"
    ).resolve()
    assert (frozen / "agent.yaml").read_bytes() == (
        worker / "agent.yaml"
    ).read_bytes()

    (worker / "systemprompt.md").write_text("changed externally\n")
    assert (frozen / "systemprompt.md").read_text() != "changed externally\n"


def test_freeze_refuses_to_overwrite_existing_worker_or_manifest(
    tmp_path: Path,
) -> None:
    worker = _worker(tmp_path)
    artifacts = tmp_path / "selection"
    artifacts.mkdir()
    kwargs = {
        "worker_dir": worker,
        "run_root": tmp_path / "run",
        "selected_profile_id": "p0",
        "selected_runtime": _runtime(worker),
        "selection_artifact_root": artifacts,
        "handoff_path": tmp_path / "handoff.json",
    }
    freeze_base_harness(**kwargs)

    with pytest.raises(FrozenBaseHarnessError, match="refusing overwrite"):
        freeze_base_harness(**kwargs)


@pytest.mark.parametrize("missing_tool", ["run_shell_command", "record_quant_state"])
def test_inspection_rejects_missing_common_tool(
    tmp_path: Path, missing_tool: str
) -> None:
    worker = _worker(tmp_path)
    config_path = worker / "agent.yaml"
    config = yaml.safe_load(config_path.read_text())
    config["tools"] = [
        value for value in config["tools"] if value["name"] != missing_tool
    ]
    config_path.write_text(yaml.safe_dump(config, sort_keys=False))

    with pytest.raises(FrozenBaseHarnessError, match=missing_tool):
        inspect_base_harness(worker)


def test_inspection_rejects_non_six_state_recorder(tmp_path: Path) -> None:
    worker = _worker(tmp_path)
    descriptor = worker / "tool_descriptions/record_quant_state.tool.yaml"
    payload = yaml.safe_load(descriptor.read_text())
    payload["input_schema"]["properties"]["stage"]["enum"] = ["S1", "S2"]
    descriptor.write_text(yaml.safe_dump(payload, sort_keys=False))

    with pytest.raises(FrozenBaseHarnessError, match="exactly S1 through S6"):
        inspect_base_harness(worker)


@pytest.mark.parametrize(
    "field,value",
    [
        ("worker_model_route", "${env.LLM_MODEL}"),
        ("rootless_config", ""),
        ("max_iterations", 0),
    ],
)
def test_runtime_must_be_concrete_and_positive(
    tmp_path: Path, field: str, value: object
) -> None:
    runtime = _runtime(_worker(tmp_path))
    runtime[field] = value

    with pytest.raises(FrozenBaseHarnessError, match="selected_runtime"):
        validate_selected_runtime(runtime)


def test_freeze_requires_materialized_selection_artifact_root(
    tmp_path: Path,
) -> None:
    worker = _worker(tmp_path)
    with pytest.raises(FrozenBaseHarnessError, match="selection_artifact_root"):
        freeze_base_harness(
            worker_dir=worker,
            run_root=tmp_path / "run",
            selected_profile_id="p0",
            selected_runtime=_runtime(worker),
            selection_artifact_root=tmp_path / "missing",
            handoff_path=tmp_path / "handoff.json",
        )


def test_freeze_rejects_undeclared_mutation_surface(tmp_path: Path) -> None:
    worker = _worker(tmp_path)
    artifacts = tmp_path / "selection"
    artifacts.mkdir()
    with pytest.raises(FrozenBaseHarnessError, match="declared system-prompt"):
        freeze_base_harness(
            worker_dir=worker,
            run_root=tmp_path / "run",
            selected_profile_id="p0",
            selected_runtime=_runtime(worker),
            selection_artifact_root=artifacts,
            handoff_path=tmp_path / "handoff.json",
            mutation_surfaces=["agent.yaml"],
        )


def test_cli_materializes_handoff_without_executing_the_worker(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    worker = _worker(tmp_path)
    artifacts = tmp_path / "selection"
    artifacts.mkdir()
    output = tmp_path / "QF_PRIMITIVE_H0_SELECTED.json"

    result = main(
        [
            "--worker-dir",
            str(worker),
            "--run-root",
            str(tmp_path / "run"),
            "--profile-id",
            "primitive-v1",
            "--worker-model-route",
            "deepseek-v4-flash-main0",
            "--rootless-config",
            "runtime/qfbench-rootless.json",
            "--selection-artifact-root",
            str(artifacts),
            "--output",
            str(output),
        ]
    )

    assert result == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed == json.loads(output.read_text())
    assert printed["selected_worker_root"].endswith(
        "/frozen-base-harness/primitive-v1/worker"
    )
