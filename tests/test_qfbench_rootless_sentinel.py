import json
import os
import stat

import pytest


def _identity_payload():
    return {
        "benchmark_commit": "0" * 40,
        "model": "deepseek/deepseek-v4-pro",
        "required_provider": "deepseek",
        "allow_fallbacks": False,
        "image_set_sha256": "2" * 64,
        "runtime_sha256": "3" * 64,
        "scheduler_sha256": "4" * 64,
        "config_sha256": "5" * 64,
        "checkpoint_sha256": "6" * 64,
    }


def _sentinel_config(tmp_path):
    run_dir = tmp_path / "runs" / "formal-r1"
    run_dir.mkdir(parents=True)
    pid_file = run_dir / "coordinator.pid"
    exit_file = run_dir / "coordinator.exit"
    log_file = run_dir / "coordinator.stderr"
    completion = run_dir / "formal-complete.json"
    pid_file.write_text("4242\n")
    exit_file.write_text("87\n")
    log_file.write_text("verifier artifact integrity mismatch\n")
    return {
        "schema_version": 1,
        "run_id": "formal-r1",
        "run_dir": str(run_dir),
        "source_commit": "1" * 40,
        "expected_identity": _identity_payload(),
        "coordinator_pid_file": str(pid_file),
        "coordinator_command_token": "formal-r1",
        "exit_code_file": str(exit_file),
        "failure_log": str(log_file),
        "completion_marker": str(completion),
        "state_dir": str(tmp_path / "supervisor"),
    }


def _load(tmp_path, payload=None):
    from scripts.run_qfbench_rootless_sentinel import load_config

    path = tmp_path / "sentinel.json"
    path.write_text(json.dumps(payload or _sentinel_config(tmp_path)))
    return load_config(path)


def _external_supervisor_config(tmp_path):
    payload = _sentinel_config(tmp_path)
    supervisor_dir = tmp_path / "launches" / "formal-r1-launch-01"
    supervisor_dir.mkdir(parents=True)
    paths = {
        "coordinator_pid_file": supervisor_dir / "coordinator.pid",
        "exit_code_file": supervisor_dir / "coordinator.exit",
        "failure_log": supervisor_dir / "coordinator.stderr",
        "completion_marker": supervisor_dir / "formal-complete.json",
    }
    paths["coordinator_pid_file"].write_text("4242\n")
    paths["exit_code_file"].write_text("1\n")
    paths["failure_log"].write_text("Traceback: worker transport failed\n")
    payload.update(
        {
            "schema_version": 2,
            "supervisor_dir": str(supervisor_dir),
            **{key: str(value) for key, value in paths.items()},
        }
    )
    return payload


def _orphan_supervisor_config(tmp_path):
    from qea.process_supervisor import ChildIdentity

    payload = _external_supervisor_config(tmp_path)
    supervisor_dir = payload["supervisor_dir"]
    child = ChildIdentity(
        pid=5252,
        process_group_id=5252,
        uid=os.getuid(),
        start_ticks=12345,
        command_sha256="a" * 64,
        run_id="formal-r1",
        source_commit="1" * 40,
    )
    child_path = os.path.join(supervisor_dir, "child-identity.json")
    with open(child_path, "w") as handle:
        json.dump(child.to_dict(), handle)
    os.chmod(child_path, 0o600)
    payload.update(
        {
            "schema_version": 3,
            "child_identity_file": child_path,
        }
    )
    return payload, child


def test_running_matching_coordinator_does_not_create_incident(tmp_path):
    from scripts.run_qfbench_rootless_sentinel import observe

    config = _load(tmp_path)
    result = observe(
        config,
        pid_alive=lambda pid: pid == 4242,
        pid_command=lambda pid: "python full-harness --run-id formal-r1",
    )

    assert result is None
    assert not (config.state_dir / "incidents").exists()


def test_external_supervisor_exit_freezes_incident_for_dead_coordinator(tmp_path):
    """Catch ignoring a real exit because launcher evidence sits outside run_dir."""

    from qea.repair_supervisor import IncidentState, IncidentStore
    from scripts.run_qfbench_rootless_sentinel import observe

    config = _load(tmp_path, _external_supervisor_config(tmp_path))

    incident = observe(config, pid_alive=lambda pid: False)

    assert incident.exit_code == 1
    assert incident.category == "harness_bug"
    assert IncidentStore(config.state_dir).load(incident.incident_id).state is (
        IncidentState.FROZEN
    )


def test_dead_wrapper_with_live_owned_child_is_supervisor_orphan_hard_stop(
    tmp_path,
):
    from qea.repair_supervisor import classify_incident
    from qea.qfbench_boundary import ProcessIdentity, ProcessSnapshot
    from scripts.run_qfbench_rootless_sentinel import observe

    payload, child = _orphan_supervisor_config(tmp_path)
    config = _load(tmp_path, payload)
    snapshot = ProcessSnapshot(
        identity=ProcessIdentity(
            child.pid,
            child.process_group_id,
            child.uid,
            child.start_ticks,
            child.command_sha256,
        ),
        state="S",
        argv=("python", "run.py", "formal-r1", "1" * 40),
    )

    incident = observe(
        config,
        pid_alive=lambda pid: pid == child.pid,
        child_snapshot=lambda pid: snapshot,
    )

    assert incident.category == "supervisor_orphan"
    assert classify_incident(incident).action == "hard_stop"


def test_schema_three_rejects_live_child_identity_drift(tmp_path):
    from qea.qfbench_boundary import ProcessIdentity, ProcessSnapshot
    from scripts.run_qfbench_rootless_sentinel import SentinelError, observe

    payload, child = _orphan_supervisor_config(tmp_path)
    config = _load(tmp_path, payload)
    drifted = ProcessSnapshot(
        identity=ProcessIdentity(
            child.pid,
            child.process_group_id,
            child.uid,
            child.start_ticks + 1,
            child.command_sha256,
        ),
        state="S",
        argv=("python", "run.py", "formal-r1", "1" * 40),
    )

    with pytest.raises(SentinelError, match="child identity"):
        observe(
            config,
            pid_alive=lambda pid: pid == child.pid,
            child_snapshot=lambda pid: drifted,
        )


def test_completion_marker_precedes_stopped_coordinator(tmp_path):
    from scripts.run_qfbench_rootless_sentinel import observe

    payload = _sentinel_config(tmp_path)
    completion = payload["completion_marker"]
    with open(completion, "w") as handle:
        json.dump({"run_id": "formal-r1", "status": "complete"}, handle)
    config = _load(tmp_path, payload)

    assert observe(config, pid_alive=lambda pid: False) is None


def test_stopped_run_freezes_one_sanitized_owner_only_incident(tmp_path):
    from qea.repair_supervisor import IncidentState, IncidentStore
    from scripts.run_qfbench_rootless_sentinel import observe

    config = _load(tmp_path)
    first = observe(config, pid_alive=lambda pid: False)
    second = observe(config, pid_alive=lambda pid: False)

    assert first == second
    assert first.category == "artifact_integrity"
    assert first.failure_signature == "verifier artifact integrity mismatch"
    store = IncidentStore(config.state_dir)
    assert store.load(first.incident_id).state is IncidentState.FROZEN
    incident_dir = config.state_dir / "incidents" / first.incident_id
    assert len(tuple((config.state_dir / "incidents").iterdir())) == 1
    assert stat.S_IMODE(incident_dir.stat().st_mode) == 0o700
    assert stat.S_IMODE((incident_dir / "incident.json").stat().st_mode) == 0o600


def test_provider_brand_does_not_mask_cost_omission(tmp_path):
    from scripts.run_qfbench_rootless_sentinel import observe

    payload = _sentinel_config(tmp_path)
    with open(payload["failure_log"], "w") as handle:
        handle.write("model transport label: openrouter-compatible\n")
        handle.write("cost audit missing successful usage\n")
    config = _load(tmp_path, payload)

    incident = observe(config, pid_alive=lambda pid: False)

    assert incident.category == "unsupported_cost_omission"
    assert incident.failure_signature == "unsupported cost ledger omission"
    assert "openrouter-compatible" in incident.excerpt


@pytest.mark.parametrize("marker", ("downstream_delivery", "post_accept_transport"))
def test_accepted_transport_ambiguity_is_a_hard_stop(tmp_path, marker):
    """Catch auto-resuming a scoring attempt whose provider call was accepted."""

    from qea.repair_supervisor import classify_incident
    from scripts.run_qfbench_rootless_sentinel import observe

    payload = _sentinel_config(tmp_path)
    with open(payload["failure_log"], "w") as handle:
        handle.write(f"model proxy quarantined request: {marker}\n")
    config = _load(tmp_path, payload)

    incident = observe(config, pid_alive=lambda pid: False)

    assert incident.category == "ambiguous_upstream"
    assert classify_incident(incident).action == "hard_stop"


def test_secret_like_binary_log_is_bounded_redacted_and_hard_stop(tmp_path):
    from qea.repair_supervisor import classify_incident
    from scripts.run_qfbench_rootless_sentinel import observe

    payload = _sentinel_config(tmp_path)
    with open(payload["failure_log"], "wb") as handle:
        handle.write(b"OPENROUTER_API_KEY=do-not-copy\x00\xff\n")
        handle.write(b"x" * 100_000)
    config = _load(tmp_path, payload)

    incident = observe(config, pid_alive=lambda pid: False)

    assert incident.category == "credential_exposure"
    assert classify_incident(incident).action == "hard_stop"
    assert "do-not-copy" not in incident.excerpt
    assert "OPENROUTER" not in incident.excerpt
    assert len(incident.excerpt) <= 2048


def test_symlinked_evidence_is_rejected(tmp_path):
    from scripts.run_qfbench_rootless_sentinel import SentinelError, observe

    payload = _sentinel_config(tmp_path)
    log_path = payload["failure_log"]
    os.unlink(log_path)
    os.symlink("coordinator.exit", log_path)
    config = _load(tmp_path, payload)

    with pytest.raises(SentinelError, match="symlink"):
        observe(config, pid_alive=lambda pid: False)


def test_config_rejects_extra_keys_and_paths_outside_run_root(tmp_path):
    from scripts.run_qfbench_rootless_sentinel import SentinelError, load_config

    payload = _sentinel_config(tmp_path)
    payload["unexpected"] = True
    path = tmp_path / "extra.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(SentinelError, match="schema"):
        load_config(path)

    payload.pop("unexpected")
    payload["failure_log"] = str(tmp_path / "outside.log")
    path.write_text(json.dumps(payload))
    with pytest.raises(SentinelError, match="run_dir"):
        load_config(path)


def test_external_supervisor_schema_rejects_evidence_outside_supervisor_root(
    tmp_path,
):
    from scripts.run_qfbench_rootless_sentinel import SentinelError, load_config

    payload = _external_supervisor_config(tmp_path)
    payload["failure_log"] = str(tmp_path / "outside.log")
    path = tmp_path / "external-outside.json"
    path.write_text(json.dumps(payload))

    with pytest.raises(SentinelError, match="supervisor_dir"):
        load_config(path)
