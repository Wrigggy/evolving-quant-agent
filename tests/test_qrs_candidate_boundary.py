from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from qea.qrs_candidate_boundary import inspect_qrs_candidate_boundary


ROOT = Path(__file__).resolve().parents[1]
CORE_V4 = ROOT / "qea/worker_quant_h0_s6_core_v4"
PROMPT = "systemprompt.md"
SKILL = "skills/quant-research-six-stage-workflow/SKILL.md"


def _workers(tmp_path: Path) -> tuple[Path, Path]:
    h0 = tmp_path / "frozen-h0"
    candidate = tmp_path / "reviewed-candidate"
    shutil.copytree(CORE_V4, h0)
    shutil.copytree(CORE_V4, candidate)
    return h0, candidate


def _inspect(
    h0: Path,
    candidate: Path,
    *,
    allowed=(PROMPT, SKILL),
    development_task_ids=("dev-task-017",),
    sealed_task_ids=("sealed-task-029",),
    development_family_labels=("rates-curves",),
    sealed_family_labels=("portfolio-holdings",),
):
    return inspect_qrs_candidate_boundary(
        frozen_h0_worker=h0,
        reviewed_candidate=candidate,
        allowed_mutation_surfaces=allowed,
        development_task_ids=development_task_ids,
        sealed_task_ids=sealed_task_ids,
        development_family_labels=development_family_labels,
        sealed_family_labels=sealed_family_labels,
    )


def _codes(result: dict[str, object]) -> set[str]:
    return {value["code"] for value in result["reasons"]}


def test_prompt_and_six_stage_skill_generic_mutation_passes(tmp_path: Path) -> None:
    h0, candidate = _workers(tmp_path)
    candidate.joinpath(PROMPT).write_text(
        candidate.joinpath(PROMPT).read_text(encoding="utf-8")
        + "\nKeep cross-stage handoffs explicit and answer-free.\n",
        encoding="utf-8",
    )
    candidate.joinpath(SKILL).write_text(
        candidate.joinpath(SKILL).read_text(encoding="utf-8")
        + "\nSummarize unresolved public ambiguity at each handoff.\n",
        encoding="utf-8",
    )

    result = _inspect(h0, candidate)

    assert result == {
        "schema_version": 1,
        "verdict": "PASS",
        "reasons": [],
        "changed_files": [SKILL, PROMPT],
    }
    json.dumps(result)


@pytest.mark.parametrize(
    "relative",
    [
        "agent.yaml",
        "tool_descriptions/run_shell_command.tool.yaml",
        "tool_descriptions/record_quant_state.tool.yaml",
        "tools/quant_state_telemetry.py",
    ],
)
def test_tool_shell_and_recorder_mutations_are_rejected(
    tmp_path: Path, relative: str
) -> None:
    h0, candidate = _workers(tmp_path)
    path = candidate / relative
    path.write_text(
        path.read_text(encoding="utf-8") + "\n# unreviewed runtime mutation\n",
        encoding="utf-8",
    )

    result = _inspect(h0, candidate)

    assert result["verdict"] == "REJECT"
    assert "non_allowed_file_changed" in _codes(result)
    assert result["changed_files"] == [relative]


@pytest.mark.parametrize(
    ("task_id", "scope"),
    [
        ("dev-task-017", "development"),
        ("sealed-task-029", "sealed"),
    ],
)
def test_changed_text_cannot_contain_exact_task_ids(
    tmp_path: Path, task_id: str, scope: str
) -> None:
    h0, candidate = _workers(tmp_path)
    prompt = candidate / PROMPT
    prompt.write_text(
        prompt.read_text(encoding="utf-8")
        + f"\nApply this overlay only to {task_id}.\n",
        encoding="utf-8",
    )

    result = _inspect(h0, candidate)

    assert result["verdict"] == "REJECT"
    assert {
        "code": "changed_text_contains_task_id",
        "path": PROMPT,
        "scope": scope,
    } in result["reasons"]
    assert task_id not in json.dumps(result)


@pytest.mark.parametrize(
    ("family_label", "scope"),
    [
        ("rates curves", "development"),
        ("portfolio_holdings", "sealed"),
    ],
)
def test_changed_text_cannot_add_obvious_family_overlay(
    tmp_path: Path, family_label: str, scope: str
) -> None:
    h0, candidate = _workers(tmp_path)
    skill = candidate / SKILL
    skill.write_text(
        skill.read_text(encoding="utf-8")
        + f"\nUse a dedicated {family_label} workflow.\n",
        encoding="utf-8",
    )

    result = _inspect(h0, candidate)

    assert result["verdict"] == "REJECT"
    assert {
        "code": "changed_text_contains_family_label",
        "path": SKILL,
        "scope": scope,
    } in result["reasons"]


def test_symlink_anywhere_in_candidate_tree_is_rejected(tmp_path: Path) -> None:
    h0, candidate = _workers(tmp_path)
    candidate.joinpath("skills/unreviewed-link").symlink_to(
        candidate / PROMPT
    )

    result = _inspect(h0, candidate)

    assert result["verdict"] == "REJECT"
    assert {
        "code": "symlink_not_allowed",
        "path": "skills/unreviewed-link",
        "scope": "reviewed_candidate",
    } in result["reasons"]


def test_added_ordinary_file_is_rejected_as_tree_change(tmp_path: Path) -> None:
    h0, candidate = _workers(tmp_path)
    candidate.joinpath("candidate-overlay.md").write_text(
        "unreviewed overlay\n", encoding="utf-8"
    )

    result = _inspect(h0, candidate)

    assert result["verdict"] == "REJECT"
    assert {
        "code": "tree_file_added",
        "path": "candidate-overlay.md",
    } in result["reasons"]
    assert result["changed_files"] == ["candidate-overlay.md"]


def test_candidate_must_still_satisfy_base_harness_contract(
    tmp_path: Path,
) -> None:
    h0, candidate = _workers(tmp_path)
    candidate.joinpath("systemprompt.md").write_text("", encoding="utf-8")

    result = _inspect(h0, candidate)

    assert result["verdict"] == "REJECT"
    assert "reviewed_candidate_contract_invalid" in _codes(result)


def test_only_declared_prompt_and_six_stage_skill_can_be_allowed(
    tmp_path: Path,
) -> None:
    h0, candidate = _workers(tmp_path)

    result = _inspect(
        h0,
        candidate,
        allowed=(PROMPT, "tools/quant_state_telemetry.py"),
    )

    assert result["verdict"] == "REJECT"
    assert "mutation_surface_not_prompt_or_six_stage_skill" in _codes(result)
