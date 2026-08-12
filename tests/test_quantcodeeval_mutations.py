import json
from enum import Enum
from pathlib import Path

import pytest

from qea.mutation_metrics import measure_mutation
from qea.quantcodeeval_mutations import (
    MutationDecision,
    QuantCodeEvalFailureClass,
    QuantCodeEvalMutationError,
    materialize_quantcodeeval_mutation,
)
from qea.worker_identity import hash_worker_directory


AGENT_YAML = """type: agent
name: minimal_quant_worker
max_context_tokens: 200000
system_prompt: ./systemprompt.md
max_iterations: 60
llm_config:
  model: ${env.LLM_MODEL}
  base_url: ${env.LLM_BASE_URL}
  api_key: ${env.LLM_API_KEY}
tools:
  - name: run_shell_command
    yaml_path: ./tool_descriptions/run_shell_command.tool.yaml
"""


def _worker(root: Path) -> Path:
    root.mkdir()
    (root / "tool_descriptions").mkdir()
    (root / "agent.yaml").write_text(AGENT_YAML, encoding="utf-8")
    (root / "systemprompt.md").write_text(
        "Solve the public quantitative task with the shell tool.\n",
        encoding="utf-8",
    )
    (root / "tool_descriptions/run_shell_command.tool.yaml").write_text(
        "type: tool\nname: run_shell_command\n",
        encoding="utf-8",
    )
    return root


@pytest.mark.parametrize(
    ("failure_class", "expected_phrase"),
    [
        ("artifact_interface", "The only artifact you submit is `strategy.py`"),
        ("data_temporal_integrity", "future-data perturbation"),
        ("quant_definition_estimation", "convert a paper constant"),
        ("portfolio_execution", "formed position to realized return"),
        ("resource_termination", "within the first two tool calls"),
    ],
)
def test_supported_failure_classes_change_only_systemprompt(
    tmp_path, failure_class, expected_phrase
):
    parent = _worker(tmp_path / "parent")
    before_agent = (parent / "agent.yaml").read_bytes()
    before_tool = (
        parent / "tool_descriptions/run_shell_command.tool.yaml"
    ).read_bytes()

    result = materialize_quantcodeeval_mutation(
        parent,
        failure_class,
        1,
        output_root=tmp_path / "out",
    )

    assert result.candidate_dir is not None
    assert result.record.decision is MutationDecision.ACT
    assert result.record.failure_class.value == failure_class
    assert result.record.component == "systemprompt"
    assert result.record.changed_paths == ("systemprompt.md",)
    assert result.record.candidate_digest == hash_worker_directory(
        result.candidate_dir
    )
    assert result.candidate_dir.name == result.record.candidate_digest
    assert (result.candidate_dir / "agent.yaml").read_bytes() == before_agent
    assert (
        result.candidate_dir
        / "tool_descriptions/run_shell_command.tool.yaml"
    ).read_bytes() == before_tool
    prompt = (result.candidate_dir / "systemprompt.md").read_text(encoding="utf-8")
    assert expected_phrase in prompt
    assert "T16" not in prompt
    assert "T24" not in prompt
    measured = measure_mutation(
        before_root=parent,
        after_root=result.candidate_dir,
        declared_roles=("systemprompt",),
    )
    assert measured["changed_file_count"] == 1
    assert measured["component_roles"] == ["systemprompt"]
    assert measured["declared_roles_match_actual"] is True
    assert measured["prompt_or_description_only"] is True


def test_artifact_operator_requires_temp_validation_and_safe_cleanup(tmp_path):
    parent = _worker(tmp_path / "parent")

    result = materialize_quantcodeeval_mutation(
        parent,
        QuantCodeEvalFailureClass.ARTIFACT_INTERFACE,
        2,
        output_root=tmp_path / "out",
    )

    prompt = (result.candidate_dir / "systemprompt.md").read_text(encoding="utf-8")
    assert "fresh temporary directory" in prompt
    assert "remove only scratch files" in prompt
    assert "never delete or rewrite task-provided inputs" in prompt
    assert "regular, importable file" in prompt


def test_resource_operator_combines_early_checkpoint_with_unit_guard(tmp_path):
    parent = _worker(tmp_path / "parent")

    result = materialize_quantcodeeval_mutation(
        parent,
        QuantCodeEvalFailureClass.RESOURCE_TERMINATION,
        5,
        output_root=tmp_path / "out",
    )

    prompt = (result.candidate_dir / "systemprompt.md").read_text(encoding="utf-8")
    assert "within the first two tool calls" in prompt
    assert "convert a paper constant written as `x%` to `x / 100`" in prompt
    assert "stop before the iteration limit" in prompt


def test_same_input_is_idempotent_and_records_are_content_addressed(tmp_path):
    parent = _worker(tmp_path / "parent")
    output = tmp_path / "out"

    first = materialize_quantcodeeval_mutation(
        parent, "data_temporal_integrity", 3, output_root=output
    )
    second = materialize_quantcodeeval_mutation(
        parent, "data_temporal_integrity", 3, output_root=output
    )

    assert second.candidate_dir == first.candidate_dir
    assert second.record_path == first.record_path
    assert second.record == first.record
    assert second.record_path.stem == second.record.mutation_id
    assert json.loads(second.record_path.read_text(encoding="utf-8")) == (
        second.record.to_dict()
    )
    assert hash_worker_directory(parent) == first.record.parent_digest


def test_iteration_is_part_of_deterministic_mutation_identity(tmp_path):
    parent = _worker(tmp_path / "parent")
    output = tmp_path / "out"

    first = materialize_quantcodeeval_mutation(
        parent, "quant_definition_estimation", 1, output_root=output
    )
    second = materialize_quantcodeeval_mutation(
        parent, "quant_definition_estimation", 2, output_root=output
    )

    assert first.candidate_dir != second.candidate_dir
    assert first.record.candidate_digest != second.record.candidate_digest
    assert first.record.mutation_id != second.record.mutation_id


def test_three_required_inputs_use_a_deterministic_default_output_root(tmp_path):
    parent = _worker(tmp_path / "parent")

    result = materialize_quantcodeeval_mutation(
        parent,
        "artifact_interface",
        1,
    )

    expected_root = tmp_path / ".parent.quantcodeeval-mutations"
    assert result.candidate_dir is not None
    assert result.candidate_dir.parent == expected_root / "candidates"
    assert result.record_path.parent == expected_root / "records"


def test_compatible_external_failure_enum_is_accepted(tmp_path):
    class ExternalFailureClass(str, Enum):
        DATA_TEMPORAL_INTEGRITY = "data_temporal_integrity"

    parent = _worker(tmp_path / "parent")

    result = materialize_quantcodeeval_mutation(
        parent,
        ExternalFailureClass.DATA_TEMPORAL_INTEGRITY,
        1,
        output_root=tmp_path / "out",
    )

    assert result.record.failure_class is (
        QuantCodeEvalFailureClass.DATA_TEMPORAL_INTEGRITY
    )


@pytest.mark.parametrize("failure_class", ["isolated_task_specific", "unknown"])
def test_isolated_and_unknown_abstain_without_candidate(tmp_path, failure_class):
    parent = _worker(tmp_path / "parent")

    result = materialize_quantcodeeval_mutation(
        parent,
        failure_class,
        1,
        output_root=tmp_path / "out",
    )

    assert result.candidate_dir is None
    assert result.record.decision is MutationDecision.ABSTAIN
    assert result.record.component is None
    assert result.record.candidate_digest is None
    assert result.record.changed_paths == ()
    assert result.record.prompt_block_sha256 is None
    assert result.record.reason
    assert result.record_path.is_file()
    assert not (tmp_path / "out/candidates").exists()


def test_parent_is_never_modified(tmp_path):
    parent = _worker(tmp_path / "parent")
    before = {
        path.relative_to(parent).as_posix(): path.read_bytes()
        for path in parent.rglob("*")
        if path.is_file()
    }

    materialize_quantcodeeval_mutation(
        parent,
        "portfolio_execution",
        4,
        output_root=tmp_path / "out",
    )

    after = {
        path.relative_to(parent).as_posix(): path.read_bytes()
        for path in parent.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_existing_modified_candidate_is_rejected(tmp_path):
    parent = _worker(tmp_path / "parent")
    output = tmp_path / "out"
    first = materialize_quantcodeeval_mutation(
        parent, "resource_termination", 5, output_root=output
    )
    assert first.candidate_dir is not None
    (first.candidate_dir / "systemprompt.md").write_text(
        "tampered\n", encoding="utf-8"
    )

    with pytest.raises(
        QuantCodeEvalMutationError,
        match="content-addressed candidate was modified",
    ):
        materialize_quantcodeeval_mutation(
            parent, "resource_termination", 5, output_root=output
        )


def test_existing_candidate_symlink_is_rejected(tmp_path):
    parent = _worker(tmp_path / "parent")
    output = tmp_path / "out"
    first = materialize_quantcodeeval_mutation(
        parent, "resource_termination", 5, output_root=output
    )
    assert first.candidate_dir is not None
    moved = tmp_path / "moved-candidate"
    first.candidate_dir.rename(moved)
    first.candidate_dir.symlink_to(moved, target_is_directory=True)

    with pytest.raises(QuantCodeEvalMutationError, match="must not be a symlink"):
        materialize_quantcodeeval_mutation(
            parent, "resource_termination", 5, output_root=output
        )


def test_existing_record_tampering_is_rejected(tmp_path):
    parent = _worker(tmp_path / "parent")
    output = tmp_path / "out"
    first = materialize_quantcodeeval_mutation(
        parent, "artifact_interface", 1, output_root=output
    )
    first.record_path.write_text("{}\n", encoding="utf-8")

    with pytest.raises(QuantCodeEvalMutationError, match="record is not immutable"):
        materialize_quantcodeeval_mutation(
            parent, "artifact_interface", 1, output_root=output
        )


@pytest.mark.parametrize("iteration", [0, -1, True, 1.5, "1"])
def test_invalid_iteration_is_rejected_without_output(tmp_path, iteration):
    parent = _worker(tmp_path / "parent")
    output = tmp_path / "out"

    with pytest.raises(QuantCodeEvalMutationError, match="positive integer"):
        materialize_quantcodeeval_mutation(
            parent, "artifact_interface", iteration, output_root=output
        )

    assert not output.exists()


def test_unsupported_failure_class_is_rejected_without_output(tmp_path):
    parent = _worker(tmp_path / "parent")
    output = tmp_path / "out"

    with pytest.raises(QuantCodeEvalMutationError, match="unsupported"):
        materialize_quantcodeeval_mutation(
            parent, "secret_checker_failure", 1, output_root=output
        )

    assert not output.exists()


def test_symlink_parent_and_nested_output_are_rejected(tmp_path):
    parent = _worker(tmp_path / "parent")
    (parent / "linked").symlink_to(parent / "systemprompt.md")

    with pytest.raises(QuantCodeEvalMutationError, match="symlink"):
        materialize_quantcodeeval_mutation(
            parent,
            "artifact_interface",
            1,
            output_root=tmp_path / "out",
        )

    (parent / "linked").unlink()
    with pytest.raises(QuantCodeEvalMutationError, match="must not be inside"):
        materialize_quantcodeeval_mutation(
            parent,
            "artifact_interface",
            1,
            output_root=parent / "generated",
        )


def test_missing_or_non_utf8_system_prompt_is_rejected(tmp_path):
    missing = _worker(tmp_path / "missing")
    (missing / "systemprompt.md").unlink()
    with pytest.raises(QuantCodeEvalMutationError, match="systemprompt.md"):
        materialize_quantcodeeval_mutation(
            missing, "artifact_interface", 1, output_root=tmp_path / "missing-out"
        )

    invalid = _worker(tmp_path / "invalid")
    (invalid / "systemprompt.md").write_bytes(b"\xff\xfe")
    with pytest.raises(QuantCodeEvalMutationError, match="UTF-8"):
        materialize_quantcodeeval_mutation(
            invalid, "artifact_interface", 1, output_root=tmp_path / "invalid-out"
        )
