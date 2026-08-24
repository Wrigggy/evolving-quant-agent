from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CORE_V2 = ROOT / "qea/worker_quant_h0_s6_core_v2"
CORE_V3 = ROOT / "qea/worker_quant_h0_s6_core_v3"

SYSTEM_CHANNEL_RULE = (
    "Emit every `[QSTATE ...]` marker as direct assistant-role plain text on its "
    "own line. Never place a marker inside a `ToolUse` payload, a "
    "`run_shell_command` command or description, an `echo`/`printf` command, "
    "tool stdout/stderr, or any other tool call or tool result. Tool-channel "
    "text does not count as a marker. Do not defer earlier markers to a "
    "final-only retrospective backfill; emit each direct assistant marker at "
    "the transition it records."
)
SKILL_CHANNEL_RULE = "Marker channel is part of the protocol. " + (
    SYSTEM_CHANNEL_RULE.replace(
        "Do not defer earlier markers", "Do not defer missed earlier markers"
    )
)


def _config(path: Path) -> dict[str, object]:
    return yaml.safe_load((path / "agent.yaml").read_text(encoding="utf-8"))


def test_core_v3_changes_only_identity_and_marker_channel_text() -> None:
    v2_config = _config(CORE_V2)
    v3_config = _config(CORE_V3)
    expected_config = dict(v2_config)
    expected_config["name"] = "qea_quant_h0_s6_core_v3_worker"

    assert v3_config == expected_config
    assert {
        path.relative_to(CORE_V3).as_posix()
        for path in CORE_V3.rglob("*")
        if path.is_file()
    } == {
        "agent.yaml",
        "skills/quant-research-six-stage-workflow/SKILL.md",
        "systemprompt.md",
        "tool_descriptions/run_shell_command.tool.yaml",
    }
    assert (
        CORE_V3 / "tool_descriptions/run_shell_command.tool.yaml"
    ).read_bytes() == (
        CORE_V2 / "tool_descriptions/run_shell_command.tool.yaml"
    ).read_bytes()

    v2_system = (CORE_V2 / "systemprompt.md").read_text(encoding="utf-8")
    v3_system = (CORE_V3 / "systemprompt.md").read_text(encoding="utf-8")
    assert v3_system == v2_system.rstrip() + "\n\n" + SYSTEM_CHANNEL_RULE + "\n"

    skill_path = "skills/quant-research-six-stage-workflow/SKILL.md"
    v2_skill = (CORE_V2 / skill_path).read_text(encoding="utf-8")
    v3_skill = (CORE_V3 / skill_path).read_text(encoding="utf-8")
    assert v3_skill.replace(SKILL_CHANNEL_RULE + "\n\n", "", 1) == v2_skill


def test_core_v3_channel_rule_excludes_tool_and_final_backfill_markers() -> None:
    material = (
        (CORE_V3 / "systemprompt.md").read_text(encoding="utf-8")
        + (CORE_V3 / "skills/quant-research-six-stage-workflow/SKILL.md").read_text(
            encoding="utf-8"
        )
    )

    for required in (
        "direct assistant-role plain text",
        "ToolUse",
        "run_shell_command",
        "echo`/`printf",
        "tool stdout/stderr",
        "Tool-channel text does not count",
        "final-only retrospective backfill",
        "at the transition it records",
    ):
        assert required in material


def test_core_v3_delta_contains_no_quant_method_or_answer_patch() -> None:
    delta = (SYSTEM_CHANNEL_RULE + "\n" + SKILL_CHANNEL_RULE).casefold()

    for excluded in (
        "formula",
        "estimator",
        "calibration",
        "turnover",
        "dupire",
        "svi",
        "expected value",
        "hidden property",
        "task identifier",
        "swap-curve",
        "13f-amendment",
        "fx-forward",
    ):
        assert excluded not in delta
