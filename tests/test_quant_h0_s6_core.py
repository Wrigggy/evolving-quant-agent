from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "qea/worker_quant_h0"
CORE = ROOT / "qea/worker_quant_h0_s6_core"
FULL = ROOT / "qea/worker_quant_h0_s6"


def _config(path: Path) -> dict[str, object]:
    return yaml.safe_load((path / "agent.yaml").read_text(encoding="utf-8"))


def test_core_changes_only_identity_prompt_and_registered_skill() -> None:
    legacy = _config(LEGACY)
    core = _config(CORE)

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
        CORE / "tool_descriptions/run_shell_command.tool.yaml"
    ).read_bytes() == (
        LEGACY / "tool_descriptions/run_shell_command.tool.yaml"
    ).read_bytes()


def test_core_is_thinner_than_full_but_keeps_state_protocol() -> None:
    core = (
        CORE / "skills/quant-research-six-stage-workflow/SKILL.md"
    ).read_text(encoding="utf-8")
    full = (
        FULL / "skills/quant-research-six-stage-workflow/SKILL.md"
    ).read_text(encoding="utf-8")

    assert len(core) < len(full) * 0.6
    for stage in range(1, 7):
        assert f"## S{stage}:" in core
    for marker in (
        "[QSTATE S1 ENTER]",
        "[QSTATE S1 COMPLETE]",
        "[QSTATE S5 REVISIT S3]",
        "[QSTATE S6 COMPLETE]",
        "NOT_APPLICABLE",
    ):
        assert marker in core
    for thick_advice in (
        "small independently computed example",
        "perturbation",
        "write the smallest structurally valid deliverables early",
        "missingness, duplicates, ordering",
        "parseability, schema, shapes, keys",
    ):
        assert thick_advice not in core.casefold()
        assert thick_advice in full.casefold()


def test_core_preserves_public_task_conditioning_and_hidden_answer_boundary() -> None:
    material = (
        (CORE / "systemprompt.md").read_text(encoding="utf-8")
        + (CORE / "skills/quant-research-six-stage-workflow/SKILL.md").read_text(
            encoding="utf-8"
        )
    ).casefold()

    assert "observable state interface, not as a fixed recipe" in material
    assert "public instruction" in material
    assert "supplied public data" in material
    assert "hidden checker behavior" in material
    assert "reference answers" in material
    assert "official property identities" in material
    for excluded in (
        "dupire",
        "svi",
        "turnover formula",
        "pair-array",
        "credit-migration",
        "22956",
        "22935",
    ):
        assert excluded not in material
