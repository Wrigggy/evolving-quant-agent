import json
from dataclasses import asdict
from pathlib import Path

import pytest


REPOSITORY = Path(__file__).resolve().parents[1]


def test_feedback_manifest_covers_exact_optimize_panel_and_no_heldout():
    from qea.evolution_feedback import load_feedback_manifest

    qfbench = json.loads(
        (REPOSITORY / "data/qfbench/MANIFEST_30.json").read_text()
    )
    expected = {item["task_id"] for item in qfbench["pilot"]["optimize"]}
    held_out = {item["task_id"] for item in qfbench["pilot"]["held_out"]}

    feedback = load_feedback_manifest(
        REPOSITORY / "data/qfbench/FEEDBACK_30.json",
        expected_task_ids=expected,
        forbidden_task_ids=held_out,
    )

    assert set(feedback) == expected
    assert set(feedback).isdisjoint(held_out)
    assert all(task.criteria for task in feedback.values())
    assert all(
        criterion.requirement.strip()
        for task in feedback.values()
        for criterion in task.criteria
    )


def test_trusted_mapping_covers_exact_public_feedback_tasks():
    from qea.evolution_feedback import (
        load_feedback_manifest,
        load_verifier_mapping,
    )

    feedback = load_feedback_manifest(
        REPOSITORY / "data/qfbench/FEEDBACK_30.json"
    )
    public_ids = {
        task_id: frozenset(item.criterion_id for item in task.criteria)
        for task_id, task in feedback.items()
    }
    mapping = load_verifier_mapping(
        REPOSITORY / "data/qfbench/VERIFIER_CRITERIA_30.json",
        public_criteria=public_ids,
    )

    assert set(mapping) == set(feedback)
    assert all(rules for rules in mapping.values())
    assert all(rules[-1].pattern == "*" for rules in mapping.values())


def test_sanitized_criterion_feedback_never_forwards_private_fields(tmp_path):
    from qea.evolution_feedback import (
        PublicCriterion,
        sanitize_ctrf_feedback,
    )

    ctrf = tmp_path / "ctrf.json"
    ctrf.write_text(json.dumps({
        "results": {
            "tests": [{
                "name": "test_private_canary_DO_NOT_EXPOSE",
                "status": "failed",
                "message": "expected 123.456, got 7.0",
                "trace": "PRIVATE_REFERENCE_PATH/solution.py",
            }]
        }
    }))
    criteria = {
        "required_output": PublicCriterion(
            criterion_id="required_output",
            requirement="Produce every output requested by the public instruction.",
        )
    }

    result = sanitize_ctrf_feedback(
        ctrf,
        {"test_private_canary_DO_NOT_EXPOSE": "required_output"},
        criteria,
    )
    encoded = json.dumps([asdict(item) for item in result], sort_keys=True)

    assert "DO_NOT_EXPOSE" not in encoded
    assert "123.456" not in encoded
    assert "solution.py" not in encoded
    assert result[0].criterion_id == "required_output"
    assert result[0].status == "failed"
    assert result[0].failed_checks == 1
    assert result[0].passed_checks == 0
    assert result[0].provenance == "sanitized_verifier"


def test_sanitized_feedback_aggregates_checks_by_public_criterion(tmp_path):
    from qea.evolution_feedback import PublicCriterion, sanitize_ctrf_feedback

    ctrf = tmp_path / "ctrf.json"
    ctrf.write_text(json.dumps({
        "results": {
            "tests": [
                {"name": "test_a", "status": "passed"},
                {"name": "test_b", "status": "failed"},
                {"name": "test_unmapped_private", "status": "failed"},
            ]
        }
    }))
    criteria = {
        "calculation": PublicCriterion(
            criterion_id="calculation",
            requirement="Perform the requested public calculation.",
        )
    }

    result = sanitize_ctrf_feedback(
        ctrf,
        {"test_a": "calculation", "test_b": "calculation"},
        criteria,
    )

    assert len(result) == 1
    assert result[0].status == "failed"
    assert result[0].passed_checks == 1
    assert result[0].failed_checks == 1
    assert result[0].evidence_kind == "requirement_not_satisfied"


def test_verifier_mapping_must_only_reference_public_criteria(tmp_path):
    from qea.evolution_feedback import FeedbackContractError, load_verifier_mapping

    path = tmp_path / "mapping.json"
    path.write_text(json.dumps({
        "schema_version": 1,
        "tasks": {
            "task-a": {
                "test_private_name": "not_a_public_criterion"
            }
        },
    }))

    with pytest.raises(FeedbackContractError, match="unknown public criterion"):
        load_verifier_mapping(
            path,
            public_criteria={"task-a": frozenset({"known_criterion"})},
        )


def test_glob_mapping_classifies_ctrf_nodeids_without_exposing_them(tmp_path):
    from qea.evolution_feedback import (
        PublicCriterion,
        load_verifier_mapping,
        sanitize_ctrf_feedback,
    )

    mapping_path = tmp_path / "mapping.json"
    mapping_path.write_text(json.dumps({
        "schema_version": 1,
        "tasks": {
            "task-a": [
                {"pattern": "*schema*", "criterion_id": "deliverables"},
                {"pattern": "*", "criterion_id": "numerical_consistency"},
            ]
        },
    }))
    mapping = load_verifier_mapping(
        mapping_path,
        public_criteria={
            "task-a": frozenset({"deliverables", "numerical_consistency"})
        },
    )
    ctrf = tmp_path / "ctrf.json"
    ctrf.write_text(json.dumps({
        "results": {"tests": [{
            "name": "test_outputs.py::test_private_schema_CANARY",
            "status": "failed",
        }]}
    }))
    criteria = {
        "deliverables": PublicCriterion(
            "deliverables", "Produce the required public deliverables."
        ),
        "numerical_consistency": PublicCriterion(
            "numerical_consistency", "Produce internally consistent calculations."
        ),
    }

    result = sanitize_ctrf_feedback(ctrf, mapping["task-a"], criteria)
    encoded = json.dumps([asdict(item) for item in result])

    assert [item.criterion_id for item in result] == ["deliverables"]
    assert "CANARY" not in encoded


def test_feedback_contract_digest_changes_only_with_mode_or_rubric(tmp_path):
    from qea.evolution_feedback import FeedbackMode, feedback_contract_digest

    rubric = tmp_path / "rubric.json"
    rubric.write_text('{"schema_version": 1, "tasks": {}}\n')

    control = feedback_contract_digest(FeedbackMode.CONTROL, rubric)
    rich = feedback_contract_digest(FeedbackMode.RICH, rubric)
    repeated = feedback_contract_digest(FeedbackMode.CONTROL, rubric)
    rubric.write_text('{"schema_version": 1, "tasks": {"changed": {}}}\n')
    changed = feedback_contract_digest(FeedbackMode.CONTROL, rubric)

    assert len(control) == 64
    assert control == repeated
    assert control != rich
    assert control != changed
