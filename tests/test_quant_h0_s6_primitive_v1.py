from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CORE_V4 = ROOT / "qea/worker_quant_h0_s6_core_v4"
PRIMITIVE = ROOT / "qea/worker_quant_h0_s6_primitive_v1"


def _config(path: Path) -> dict[str, object]:
    return yaml.safe_load((path / "agent.yaml").read_text(encoding="utf-8"))


def _material() -> str:
    return (
        (PRIMITIVE / "systemprompt.md").read_text(encoding="utf-8")
        + (
            PRIMITIVE
            / "skills/quant-research-six-stage-workflow/SKILL.md"
        ).read_text(encoding="utf-8")
    )


def test_primitive_preserves_core_v4_runtime_tools_and_skill_registration() -> None:
    core = _config(CORE_V4)
    primitive = _config(PRIMITIVE)
    expected = dict(core)
    expected["name"] = "qea_quant_h0_s6_primitive_v1_worker"

    assert primitive == expected
    for relative_path in (
        "tool_descriptions/run_shell_command.tool.yaml",
        "tool_descriptions/record_quant_state.tool.yaml",
        "tools/quant_state_telemetry.py",
    ):
        assert (PRIMITIVE / relative_path).read_bytes() == (
            CORE_V4 / relative_path
        ).read_bytes()


def test_primitive_keeps_answer_boundary_and_structured_trace_protocol() -> None:
    material = _material()

    for required in (
        "hidden checker behavior",
        "reference answers",
        "official property identities",
        "real structured `record_quant_state` tool call",
        "each recorder call by itself",
        "Wait for its acknowledgement",
        "first task-directed tool call",
        "Do not retrospectively backfill",
        "S6 COMPLETE",
        "normal final response on the next turn",
    ):
        assert required in material


def test_primitive_is_task_agnostic_trajectory_bank_seed() -> None:
    material = _material()
    skill = (
        PRIMITIVE / "skills/quant-research-six-stage-workflow/SKILL.md"
    ).read_text(encoding="utf-8")

    assert "deliberately underspecified state interface" in material
    assert "without prescribing their concrete implementation" in skill
    for stage_name in (
        "Research Mandate and Contract",
        "Research Evidence and Data",
        "Quantitative Representation",
        "Research Operation",
        "Evaluation and Reconciliation",
        "Research Artifact and Completion",
    ):
        assert stage_name in skill
    assert skill.count("Orient the work") == 6

    for excluded in (
        "revisit",
        "audit the requested",
        "checklist",
        "estimator",
        "missingness",
        "perturbation",
        "dupire",
        "swap-curve-bootstrap",
        "13f-amendment",
        "fx-forward-cross-rate",
    ):
        assert excluded not in material.casefold()


def test_primitive_targets_short_summaries_without_changing_schema() -> None:
    material = _material()
    descriptor = yaml.safe_load(
        (
            PRIMITIVE / "tool_descriptions/record_quant_state.tool.yaml"
        ).read_text(encoding="utf-8")
    )

    assert "at most 240 characters" in material
    assert descriptor["input_schema"]["properties"]["public_summary"][
        "maxLength"
    ] == 512


def test_primitive_is_structurally_admissible() -> None:
    from qea.candidate_admission import AdmissionPolicy, admit_candidate

    record = admit_candidate(
        CORE_V4,
        PRIMITIVE,
        AdmissionPolicy.qfbench_full(),
    )

    assert record.admitted is True
    assert record.failure is None
    assert "local_bindings" in record.checks
    assert "component_reachability" in record.checks
