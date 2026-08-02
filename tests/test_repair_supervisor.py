import hashlib
import json
import stat

import pytest


BENCHMARK_COMMIT = "0" * 40
SOURCE_COMMIT = "1" * 40
HASH_A = "a" * 64


def _identity():
    from qea.repair_supervisor import ExpectedIdentity

    return ExpectedIdentity(
        benchmark_commit=BENCHMARK_COMMIT,
        model="deepseek/deepseek-v4-pro",
        required_provider="deepseek",
        allow_fallbacks=False,
        image_set_sha256="2" * 64,
        runtime_sha256="3" * 64,
        scheduler_sha256="4" * 64,
        config_sha256="5" * 64,
        checkpoint_sha256="6" * 64,
    )


def _incident(category="artifact_integrity", signature="artifact integrity mismatch"):
    from qea.repair_supervisor import Incident

    return Incident.create(
        run_id="qfbench-formal-r1",
        source_commit=SOURCE_COMMIT,
        exit_code=87,
        exit_evidence_sha256=HASH_A,
        failure_signature=signature,
        category=category,
        excerpt="verifier artifact integrity mismatch",
        expected_identity=_identity(),
        evidence_hashes={"stderr": "7" * 64},
    )


def test_incident_id_is_content_addressed_and_stable():
    from qea.repair_supervisor import incident_id

    first = incident_id("run-1", SOURCE_COMMIT, HASH_A, "same failure")
    second = incident_id("run-1", SOURCE_COMMIT, HASH_A, "same failure")

    assert first == second
    assert len(first) == 64
    assert first == hashlib.sha256(
        b"run-1\n1111111111111111111111111111111111111111\n"
        b"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n"
        b"same failure"
    ).hexdigest()


@pytest.mark.parametrize(
    "category",
    [
        "verifier_firewall_drift",
        "credential_exposure",
        "official_data_exposure",
        "identity_drift",
        "historical_hash_drift",
        "ambiguous_upstream",
        "unsupported_cost_omission",
        "cleanup_failure",
        "unknown_failure",
    ],
)
def test_security_identity_history_and_cleanup_fail_closed(category):
    from qea.repair_supervisor import classify_incident

    classification = classify_incident(_incident(category=category))

    assert classification.action == "hard_stop"
    assert classification.reason


def test_artifact_integrity_is_repairable_and_known_interrupt_is_resumable():
    from qea.repair_supervisor import classify_incident

    assert classify_incident(_incident()).action == "repairable"
    assert classify_incident(
        _incident(category="replay_safe_interruption")
    ).action == "resume"


def test_incident_round_trip_rejects_extra_or_secret_fields():
    from qea.repair_supervisor import Incident, SupervisorPolicyError

    payload = _incident().to_dict()
    assert Incident.from_dict(payload) == _incident()

    with pytest.raises(SupervisorPolicyError, match="schema"):
        Incident.from_dict({**payload, "unexpected": True})
    with pytest.raises(SupervisorPolicyError, match="forbidden"):
        Incident.create(
            run_id="qfbench-formal-r1",
            source_commit=SOURCE_COMMIT,
            exit_code=1,
            exit_evidence_sha256=HASH_A,
            failure_signature="failed",
            category="harness_bug",
            excerpt="read /tmp/.env and API_KEY=secret",
            expected_identity=_identity(),
            evidence_hashes={},
        )


def test_store_transitions_atomically_and_deduplicates(tmp_path):
    from qea.repair_supervisor import IncidentState, IncidentStore

    store = IncidentStore(tmp_path / "state")
    incident = _incident()
    created = store.create(incident)
    duplicate = store.create(incident)

    assert created == duplicate
    assert created.state is IncidentState.OBSERVED
    assert stat.S_IMODE(store.root.stat().st_mode) == 0o700
    incident_dir = store.root / "incidents" / incident.incident_id
    assert stat.S_IMODE(incident_dir.stat().st_mode) == 0o700
    assert stat.S_IMODE((incident_dir / "incident.json").stat().st_mode) == 0o600

    for state in (
        IncidentState.FROZEN,
        IncidentState.CLASSIFIED,
        IncidentState.REPAIRING,
        IncidentState.TESTED,
        IncidentState.DEPLOYED,
        IncidentState.CANARY_PASSED,
        IncidentState.RESUMED,
        IncidentState.RESOLVED,
    ):
        snapshot = store.transition(incident.incident_id, state)
        assert snapshot.state is state
        assert store.transition(incident.incident_id, state) == snapshot

    assert json.loads((store.root / "active.json").read_text())["incident_id"] == ""


def test_store_rejects_skipped_transition_and_second_active_incident(tmp_path):
    from qea.repair_supervisor import (
        IncidentState,
        IncidentStore,
        SupervisorPolicyError,
    )

    store = IncidentStore(tmp_path / "state")
    incident = _incident()
    store.create(incident)

    with pytest.raises(SupervisorPolicyError, match="transition"):
        store.transition(incident.incident_id, IncidentState.TESTED)

    other = _incident(signature="another integrity failure")
    with pytest.raises(SupervisorPolicyError, match="active incident"):
        store.create(other)


def test_repair_budget_allows_three_cycles_then_exhausts(tmp_path):
    from qea.repair_supervisor import (
        IncidentState,
        IncidentStore,
        RepairBudgetError,
    )

    store = IncidentStore(tmp_path / "state")
    incident = _incident()
    store.create(incident)
    store.transition(incident.incident_id, IncidentState.FROZEN)
    store.transition(incident.incident_id, IncidentState.CLASSIFIED)

    assert store.record_repair(incident.incident_id).repair_count == 1
    assert store.record_repair(incident.incident_id).repair_count == 2
    assert store.record_repair(incident.incident_id).repair_count == 3
    with pytest.raises(RepairBudgetError, match="exhausted"):
        store.record_repair(incident.incident_id)
    assert store.load(incident.incident_id).state is IncidentState.REPAIR_BUDGET_EXHAUSTED


def test_any_live_state_can_fail_closed(tmp_path):
    from qea.repair_supervisor import IncidentState, IncidentStore

    store = IncidentStore(tmp_path / "state")
    incident = _incident()
    store.create(incident)

    snapshot = store.transition(incident.incident_id, IncidentState.HARD_STOP)

    assert snapshot.state is IncidentState.HARD_STOP
    assert json.loads((store.root / "active.json").read_text())["incident_id"] == ""
