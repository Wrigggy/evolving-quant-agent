from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
LEGACY_H0 = ROOT / "qea" / "worker_quant_h0"
QUANT_H0_S6 = ROOT / "qea" / "worker_quant_h0_s6"
SKILL = (
    QUANT_H0_S6
    / "skills"
    / "quant-research-six-stage-workflow"
    / "SKILL.md"
)


def _config(root: Path) -> dict:
    return yaml.safe_load((root / "agent.yaml").read_text(encoding="utf-8"))


def test_quant_h0_s6_keeps_legacy_runtime_and_shell_capability():
    legacy = _config(LEGACY_H0)
    s6 = _config(QUANT_H0_S6)

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
        assert s6[key] == legacy[key]
    assert s6["name"] == "qea_quant_h0_s6_worker"
    assert s6["skills"] == ["./skills/quant-research-six-stage-workflow"]
    assert (
        QUANT_H0_S6 / "tool_descriptions/run_shell_command.tool.yaml"
    ).read_bytes() == (
        LEGACY_H0 / "tool_descriptions/run_shell_command.tool.yaml"
    ).read_bytes()


def test_quant_h0_s6_is_admitted_as_prompt_and_skill_only_successor():
    from qea.candidate_admission import AdmissionPolicy, admit_candidate

    record = admit_candidate(
        LEGACY_H0,
        QUANT_H0_S6,
        AdmissionPolicy.qfbench_full(),
    )

    assert record.admitted is True
    assert record.failure is None
    assert "local_skills" in record.checks
    assert {item.path for item in record.files} == {
        "agent.yaml",
        "skills/quant-research-six-stage-workflow/SKILL.md",
        "systemprompt.md",
        "tool_descriptions/run_shell_command.tool.yaml",
    }


def test_quant_h0_s6_hardcodes_reusable_harness_goal_without_task_answer():
    prompt = (QUANT_H0_S6 / "systemprompt.md").read_text(encoding="utf-8")
    folded = prompt.casefold()

    assert "reusable quantitative-research harness" in prompt
    assert "current public task" in prompt
    assert "load and follow the `quant-research-six-stage-workflow` skill" in prompt
    assert "[qstate ...]" in folded
    assert "not private chain-of-thought" in folded
    for required in (
        "public instruction",
        "supplied public data",
        "hidden checker behavior",
        "reference answers",
        "official property identities",
        "benchmark-specific constants",
    ):
        assert required in folded


def test_quant_h0_s6_skill_defines_all_stages_and_observable_markers():
    text = SKILL.read_text(encoding="utf-8")
    metadata = yaml.safe_load(text.split("---", 2)[1])

    assert metadata["name"] == "quant-research-six-stage-workflow"
    assert "Required for every quantitative task" in metadata["description"]
    for stage, name in (
        ("S1", "Research Mandate and Contract"),
        ("S2", "Research Evidence and Data"),
        ("S3", "Quantitative Representation"),
        ("S4", "Research Operation"),
        ("S5", "Evaluation and Reconciliation"),
        ("S6", "Research Artifact and Completion"),
    ):
        assert f"## {stage}: {name}" in text
        assert f"[QSTATE {stage} ENTER]" in text
        assert f"[QSTATE {stage} COMPLETE]" in text
    assert "[QSTATE S5 REVISIT S2]" in text
    assert "[QSTATE S5 REVISIT S3]" in text
    assert "[QSTATE S5 REVISIT S4]" in text
    assert "NOT_APPLICABLE" in text
    assert "Do not silently skip a stage" in text


def test_quant_h0_s6_contains_no_observed_task_answer_patch():
    material = (
        (QUANT_H0_S6 / "systemprompt.md").read_text(encoding="utf-8")
        + "\n"
        + SKILL.read_text(encoding="utf-8")
    ).casefold()

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
        assert excluded not in material
