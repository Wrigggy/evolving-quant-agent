from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "qea/worker_quant_h0"
CORE_V1 = ROOT / "qea/worker_quant_h0_s6_core"
CORE_V2 = ROOT / "qea/worker_quant_h0_s6_core_v2"
FULL = ROOT / "qea/worker_quant_h0_s6"


def _config(path: Path) -> dict[str, object]:
    return yaml.safe_load((path / "agent.yaml").read_text(encoding="utf-8"))


def _material(path: Path) -> str:
    return (
        (path / "systemprompt.md").read_text(encoding="utf-8")
        + "\n"
        + (
            path
            / "skills/quant-research-six-stage-workflow/SKILL.md"
        ).read_text(encoding="utf-8")
    )


def test_core_v2_changes_only_identity_prompt_and_registered_skill() -> None:
    legacy = _config(LEGACY)
    core = _config(CORE_V2)

    for key in (
        "type",
        "max_context_tokens",
        "system_prompt_type",
        "tool_call_mode",
        "max_iterations",
        "llm_config",
        "tools",
        "tracers",
    ):
        assert core[key] == legacy[key]
    assert core["skills"] == ["./skills/quant-research-six-stage-workflow"]
    assert (
        CORE_V2 / "tool_descriptions/run_shell_command.tool.yaml"
    ).read_bytes() == (
        LEGACY / "tool_descriptions/run_shell_command.tool.yaml"
    ).read_bytes()


def test_core_v2_is_admitted_as_prompt_and_skill_only_successor() -> None:
    from qea.candidate_admission import AdmissionPolicy, admit_candidate

    record = admit_candidate(
        LEGACY,
        CORE_V2,
        AdmissionPolicy.qfbench_full(),
    )

    assert record.admitted is True
    assert record.failure is None
    assert {item.path for item in record.files} == {
        "agent.yaml",
        "skills/quant-research-six-stage-workflow/SKILL.md",
        "systemprompt.md",
        "tool_descriptions/run_shell_command.tool.yaml",
    }


def test_core_v2_only_strengthens_protocol_relative_to_core_v1() -> None:
    v1 = _material(CORE_V1)
    v2 = _material(CORE_V2)

    assert "terminal protocol audit" in v2
    assert "close each entered state before entering the next one" in v2
    assert "[QSTATE S6 ENTER]" in v2
    assert "Do not write `[QSTATE S3 REVISIT]`" in v2
    assert "Do not backfill an earlier state's marker" in v2
    assert "manufacturing a" in v2
    assert "retroactive event" in v2
    for stage in range(1, 7):
        assert f"## S{stage}:" in v1
        assert f"## S{stage}:" in v2
    for sentence in (
        "State what the public task asks for and what must be delivered.",
        "Identify and inspect the public evidence or data needed for the task.",
        "Perform the task-appropriate quantitative research operation.",
    ):
        assert sentence in v1
        assert sentence in v2


def test_core_v2_remains_thinner_than_full_and_contains_no_answer_patch() -> None:
    material = _material(CORE_V2)
    full = _material(FULL)

    assert len(material) < len(full)
    folded = material.casefold()
    assert "observable state interface, not as a fixed recipe" in folded
    for excluded in (
        "dupire",
        "svi",
        "a > 0",
        "turnover formula",
        "pair-array",
        "credit-migration",
        "22956",
        "22935",
        "106/107",
    ):
        assert excluded not in folded
