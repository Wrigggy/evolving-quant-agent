from pathlib import Path
from types import ModuleType

import yaml


ROOT = Path(__file__).resolve().parents[1]
CORE_V3 = ROOT / "qea/worker_quant_h0_s6_core_v3"
CORE_V4 = ROOT / "qea/worker_quant_h0_s6_core_v4"


def _config(path: Path) -> dict[str, object]:
    return yaml.safe_load((path / "agent.yaml").read_text(encoding="utf-8"))


def _telemetry_module():
    path = CORE_V4 / "tools/quant_state_telemetry.py"
    module = ModuleType("quant_state_telemetry")
    source = path.read_text(encoding="utf-8")
    exec(compile(source, str(path), "exec"), module.__dict__)
    return module


def test_core_v4_preserves_runtime_and_shell_while_adding_one_recorder() -> None:
    v3 = _config(CORE_V3)
    v4 = _config(CORE_V4)
    expected = dict(v3)
    expected["name"] = "qea_quant_h0_s6_core_v4_worker"
    expected["tools"] = list(v3["tools"]) + [
        {
            "name": "record_quant_state",
            "yaml_path": "./tool_descriptions/record_quant_state.tool.yaml",
            "binding": "tools.quant_state_telemetry:record_quant_state",
        }
    ]

    assert v4 == expected
    assert v4["tools"][0] == v3["tools"][0]
    assert (
        CORE_V4 / "tool_descriptions/run_shell_command.tool.yaml"
    ).read_bytes() == (
        CORE_V3 / "tool_descriptions/run_shell_command.tool.yaml"
    ).read_bytes()


def test_core_v4_recorder_schema_is_minimal_and_answer_free() -> None:
    descriptor = yaml.safe_load(
        (CORE_V4 / "tool_descriptions/record_quant_state.tool.yaml").read_text(
            encoding="utf-8"
        )
    )
    schema = descriptor["input_schema"]

    assert descriptor["name"] == "record_quant_state"
    assert set(schema["properties"]) == {
        "stage",
        "action",
        "public_summary",
    }
    assert schema["required"] == ["stage", "action", "public_summary"]
    assert schema["additionalProperties"] is False
    assert schema["properties"]["stage"]["enum"] == [
        "S1",
        "S2",
        "S3",
        "S4",
        "S5",
        "S6",
    ]
    assert schema["properties"]["action"]["enum"] == [
        "ENTER",
        "COMPLETE",
        "NOT_APPLICABLE",
        "REVISIT",
    ]

    material = (
        descriptor["description"]
        + (CORE_V4 / "systemprompt.md").read_text(encoding="utf-8")
        + (
            CORE_V4 / "skills/quant-research-six-stage-workflow/SKILL.md"
        ).read_text(encoding="utf-8")
        + (
            CORE_V4 / "tools/quant_state_telemetry.py"
        ).read_text(encoding="utf-8")
    ).casefold()
    for forbidden in (
        "dupire",
        "svi",
        "turnover formula",
        "swap-curve-bootstrap",
        "13f-amendment",
        "fx-forward-cross-rate",
    ):
        assert forbidden not in material


def test_core_v4_recorder_is_nonterminal_and_does_not_echo_summary() -> None:
    recorder = _telemetry_module().record_quant_state

    result = recorder("S1", "ENTER", "identify the public mandate")

    assert result == {"status": "recorded"}
    assert "_is_stop_tool" not in result
    assert "identify the public mandate" not in str(result)


def test_core_v4_recorder_rejects_invalid_single_events() -> None:
    recorder = _telemetry_module().record_quant_state

    assert recorder("S7", "ENTER", "public summary")["status"] == "rejected"
    assert recorder("S1", "DONE", "public summary")["status"] == "rejected"
    assert recorder("S1", "ENTER", "")["status"] == "rejected"
    assert recorder("S1", "ENTER", "x" * 513)["status"] == "rejected"
    assert recorder("S1", "REVISIT", "public summary")["status"] == "rejected"
    assert recorder("S6", "NOT_APPLICABLE", "public summary")["status"] == (
        "rejected"
    )


def test_core_v4_prompt_requires_isolated_structured_transitions() -> None:
    material = (
        (CORE_V4 / "systemprompt.md").read_text(encoding="utf-8")
        + (
            CORE_V4 / "skills/quant-research-six-stage-workflow/SKILL.md"
        ).read_text(encoding="utf-8")
    )

    for required in (
        "real structured `record_quant_state` tool call",
        "each recorder call by itself",
        "Wait for its acknowledgement",
        "first task-directed tool call",
        "Do not retrospectively backfill",
        "S6 COMPLETE",
        "normal final response on the next turn",
    ):
        assert required in material


def test_core_v4_is_structurally_admissible() -> None:
    from qea.candidate_admission import AdmissionPolicy, admit_candidate

    record = admit_candidate(
        CORE_V3,
        CORE_V4,
        AdmissionPolicy.qfbench_full(),
    )

    assert record.admitted is True
    assert record.failure is None
    assert "local_bindings" in record.checks
    assert "component_reachability" in record.checks
