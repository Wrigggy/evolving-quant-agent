import json

import pytest

from qea.qfbench_scheduler_epochs import (
    SchedulerEpoch,
    SchedulerEpochError,
    epoch_for_repetition,
    migrate_v1_checkpoint,
    sampling_identity,
    validate_scheduler_epochs,
)


def _epochs():
    return (
        SchedulerEpoch(
            first_repetition=1,
            last_repetition=1,
            worker_concurrency=4,
            verifier_concurrency=3,
            scheduler_identity_digest="1" * 64,
            runtime_identity_digest="4" * 64,
        ),
        SchedulerEpoch(
            first_repetition=2,
            last_repetition=5,
            worker_concurrency=12,
            verifier_concurrency=3,
            scheduler_identity_digest="2" * 64,
            runtime_identity_digest="7" * 64,
        ),
    )


def _schema_v1_boundary_state():
    return {
        "schema_version": 1,
        "run_id": "baseline-five",
        "benchmark_commit": "0" * 40,
        "total_repetitions": 5,
        "identity": {
            "model_identity": "fixture-model",
            "task_manifest_digest": "3" * 64,
            "runtime_identity_digest": "4" * 64,
            "scheduler_identity_digest": "1" * 64,
            "template_identity_digest": "5" * 64,
            "worker_concurrency": 4,
            "verifier_concurrency": 3,
            "seed_worker_digest": "6" * 64,
            "primary_tasks": [{"task_id": "primary"}],
            "diagnostic_tasks": [{"task_id": "diagnostic"}],
        },
        "phase": "primary",
        "next_repetition": 2,
        "pending_primary": None,
        "completed": [
            {
                "repetition": 1,
                "primary": {"scores": [{"task_id": "primary", "reward": 1.0}]},
                "diagnostic": {
                    "scores": [{"task_id": "diagnostic", "reward": 0.0}]
                },
            }
        ],
    }


def test_epoch_contract_covers_each_repetition_exactly_once():
    epochs = _epochs()

    assert validate_scheduler_epochs(epochs, total_repetitions=5) == epochs
    assert epoch_for_repetition(epochs, 1).worker_concurrency == 4
    assert epoch_for_repetition(epochs, 5).worker_concurrency == 12


@pytest.mark.parametrize(
    "epochs",
    [
        (
            SchedulerEpoch(1, 2, 4, 3, "1" * 64, "4" * 64),
            SchedulerEpoch(2, 5, 12, 3, "2" * 64, "7" * 64),
        ),
        (
            SchedulerEpoch(1, 1, 4, 3, "1" * 64, "4" * 64),
            SchedulerEpoch(3, 5, 12, 3, "2" * 64, "7" * 64),
        ),
        (SchedulerEpoch(2, 5, 12, 3, "2" * 64, "7" * 64),),
        (SchedulerEpoch(1, 4, 4, 3, "1" * 64, "4" * 64),),
    ],
)
def test_epoch_contract_rejects_overlap_gap_or_wrong_endpoints(epochs):
    with pytest.raises(SchedulerEpochError, match="cover repetitions"):
        validate_scheduler_epochs(epochs, total_repetitions=5)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("first_repetition", 0),
        ("last_repetition", 0),
        ("worker_concurrency", 0),
        ("verifier_concurrency", True),
        ("scheduler_identity_digest", "not-a-digest"),
        ("runtime_identity_digest", "not-a-digest"),
    ],
)
def test_epoch_fields_reject_invalid_values(field, value):
    values = {
        "first_repetition": 1,
        "last_repetition": 1,
        "worker_concurrency": 4,
        "verifier_concurrency": 3,
        "scheduler_identity_digest": "1" * 64,
        "runtime_identity_digest": "4" * 64,
    }
    values[field] = value

    with pytest.raises(SchedulerEpochError, match=field):
        SchedulerEpoch(**values)


def test_sampling_identity_removes_only_scheduler_fields():
    identity = _schema_v1_boundary_state()["identity"]

    sampled = sampling_identity(identity)

    assert sampled == {
        key: value
        for key, value in identity.items()
        if key
        not in {
            "scheduler_identity_digest",
            "runtime_identity_digest",
            "worker_concurrency",
            "verifier_concurrency",
        }
    }


def test_clean_v1_boundary_migrates_without_rewriting_completed_values(tmp_path):
    state = _schema_v1_boundary_state()
    completed_before = json.loads(json.dumps(state["completed"]))
    resume = tmp_path / "resume.json"
    resume.write_text(json.dumps(state))

    migrated = migrate_v1_checkpoint(
        resume,
        scheduler_epochs=_epochs(),
        boundary_manifest_sha256="a" * 64,
    )

    assert migrated["schema_version"] == 2
    assert migrated["completed"] == completed_before
    assert migrated["sampling_identity"] == sampling_identity(state["identity"])
    assert migrated["scheduler_epochs"] == [epoch.to_dict() for epoch in _epochs()]
    assert migrated["boundary_manifest_sha256"] == "a" * 64
    assert "identity" not in migrated
    assert json.loads(resume.read_text()) == migrated


def test_identical_v2_migration_is_idempotent(tmp_path):
    resume = tmp_path / "resume.json"
    resume.write_text(json.dumps(_schema_v1_boundary_state()))
    first = migrate_v1_checkpoint(
        resume,
        scheduler_epochs=_epochs(),
        boundary_manifest_sha256="a" * 64,
    )
    first_bytes = resume.read_bytes()

    second = migrate_v1_checkpoint(
        resume,
        scheduler_epochs=_epochs(),
        boundary_manifest_sha256="a" * 64,
    )

    assert second == first
    assert resume.read_bytes() == first_bytes


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("phase", "diagnostic", "phase"),
        ("next_repetition", 1, "next_repetition"),
        ("pending_primary", {"scores": []}, "pending_primary"),
        ("completed", [], "completed repetition 1"),
    ],
)
def test_migration_rejects_any_nonboundary_checkpoint(tmp_path, field, value, message):
    state = _schema_v1_boundary_state()
    state[field] = value
    resume = tmp_path / "resume.json"
    resume.write_text(json.dumps(state))

    with pytest.raises(SchedulerEpochError, match=message):
        migrate_v1_checkpoint(
            resume,
            scheduler_epochs=_epochs(),
            boundary_manifest_sha256="a" * 64,
        )


def test_migration_rejects_epoch_one_identity_drift(tmp_path):
    state = _schema_v1_boundary_state()
    state["identity"]["worker_concurrency"] = 5
    resume = tmp_path / "resume.json"
    resume.write_text(json.dumps(state))

    with pytest.raises(SchedulerEpochError, match="epoch 1 identity"):
        migrate_v1_checkpoint(
            resume,
            scheduler_epochs=_epochs(),
            boundary_manifest_sha256="a" * 64,
        )


def test_migration_rejects_different_second_publish(tmp_path):
    resume = tmp_path / "resume.json"
    resume.write_text(json.dumps(_schema_v1_boundary_state()))
    migrate_v1_checkpoint(
        resume,
        scheduler_epochs=_epochs(),
        boundary_manifest_sha256="a" * 64,
    )

    with pytest.raises(SchedulerEpochError, match="published migration differs"):
        migrate_v1_checkpoint(
            resume,
            scheduler_epochs=_epochs(),
            boundary_manifest_sha256="b" * 64,
        )
