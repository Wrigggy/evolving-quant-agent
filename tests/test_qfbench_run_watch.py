import hashlib
import json
import os
import signal
from pathlib import Path

import pytest


def _attempt(tmp_path):
    run_dir = tmp_path / "formal-run"
    attempt = run_dir / "attempts" / "attempt-timeout"
    attempt.mkdir(parents=True)
    (attempt / "attempt.json").write_text(
        json.dumps(
            {
                "attempt_id": "attempt-timeout",
                "run_id": "formal-run",
                "benchmark_commit": "0" * 40,
                "task_id": "yield-curve-bond-immunization",
                "split": "baseline_primary",
                "checkpoint": "repetition-01-primary",
                "worker_digest": "1" * 64,
            }
        )
    )
    (attempt / "completed-score.json").write_text(
        json.dumps(
            {
                "task_id": "yield-curve-bond-immunization",
                "domain": "fixed_income",
                "reward": 0.0,
                "diagnostic_tags": ["timeout"],
            }
        )
    )
    (attempt / "proxy-audit.quarantined.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "request_state": "quarantined",
                "reason": "audit_download_or_validation_failed",
            }
        )
    )
    lifecycle = run_dir / "lifecycles" / "formal-run" / "attempt-timeout"
    lifecycle.mkdir(parents=True)
    for name in (
        "worker-sandbox-lifecycle-v2.json",
        "proxy-sandbox-lifecycle-v2.json",
        "proxy-network-lifecycle-v1.json",
    ):
        (lifecycle / name).write_text(
            json.dumps(
                {
                    "schema_version": 1 if "network" in name else 2,
                    "run_id": "formal-run",
                    "attempt_id": "attempt-timeout",
                    "native_id": name,
                    "cleaned_up": True,
                }
            )
        )
    return run_dir, attempt


def _audit_record(**changes):
    record = {
        "schema_version": 1,
        "request_identity_sha256": "a" * 64,
        "model": "deepseek/deepseek-v4-flash",
        "started_at": "2026-08-03T00:00:00+00:00",
        "finished_at": "2026-08-03T00:00:01+00:00",
        "latency_ms": 1000,
        "request_state": "completed",
        "upstream_status_code": 200,
        "provider_request_id": "request-1",
        "input_tokens": 10,
        "output_tokens": 5,
        "total_tokens": 15,
        "provider_cost_usd": "0.01",
        "failure_class": None,
    }
    record.update(changes)
    return record


def test_exact_official_timeout_is_unreconciled_cost_lower_bound(tmp_path):
    from qea.qfbench_run_watch import classify_attempt_evidence

    run_dir, attempt = _attempt(tmp_path)

    result = classify_attempt_evidence(attempt, run_dir=run_dir)

    assert result.status == "timeout_cost_lower_bound"
    assert result.hard_stop is False
    assert result.category is None


@pytest.mark.parametrize(
    "corruption",
    (
        "reward_nonzero",
        "missing_timeout",
        "unsupported_reason",
        "malformed_marker",
        "both_ledger_and_marker",
        "unclean_lifecycle",
        "downstream_delivery",
        "post_accept_transport",
        "http_200_quarantine",
        "duplicate_request_identity",
    ),
)
def test_ambiguous_or_nonexact_timeout_evidence_is_fatal(tmp_path, corruption):
    from qea.qfbench_run_watch import classify_attempt_evidence

    run_dir, attempt = _attempt(tmp_path)
    score_path = attempt / "completed-score.json"
    score = json.loads(score_path.read_text())
    marker_path = attempt / "proxy-audit.quarantined.json"
    marker = json.loads(marker_path.read_text())
    records = None
    if corruption == "reward_nonzero":
        score["reward"] = 1.0
    elif corruption == "missing_timeout":
        score["diagnostic_tags"] = []
    elif corruption == "unsupported_reason":
        marker["reason"] = "post_accept_transport"
    elif corruption == "malformed_marker":
        marker["schema_version"] = 2
    elif corruption == "both_ledger_and_marker":
        records = [_audit_record()]
    elif corruption == "unclean_lifecycle":
        lifecycle = next((run_dir / "lifecycles").rglob("*sandbox-lifecycle-v2.json"))
        payload = json.loads(lifecycle.read_text())
        payload["cleaned_up"] = False
        lifecycle.write_text(json.dumps(payload))
    elif corruption in {"downstream_delivery", "post_accept_transport"}:
        marker_path.unlink()
        records = [
            _audit_record(
                request_state="quarantined",
                upstream_status_code=None,
                failure_class=corruption,
                input_tokens=None,
                output_tokens=None,
                total_tokens=None,
                provider_cost_usd=None,
            )
        ]
    elif corruption == "http_200_quarantine":
        marker_path.unlink()
        records = [
            _audit_record(
                request_state="quarantined",
                failure_class="downstream_delivery",
            )
        ]
    elif corruption == "duplicate_request_identity":
        marker_path.unlink()
        records = [_audit_record(), _audit_record()]
    score_path.write_text(json.dumps(score))
    if marker_path.exists():
        marker_path.write_text(json.dumps(marker))
    if records is not None:
        (attempt / "proxy-audit.jsonl").write_text(
            "".join(json.dumps(record) + "\n" for record in records)
        )

    result = classify_attempt_evidence(attempt, run_dir=run_dir)

    assert result.hard_stop is True
    assert result.category is not None


def test_observe_run_persists_only_sanitized_paths_and_evidence_hash(tmp_path):
    from qea.qfbench_run_watch import observe_run

    run_dir, _ = _attempt(tmp_path)

    result = observe_run(run_dir)

    assert result.hard_stop is False
    assert result.timeout_cost_lower_bound_paths == (
        "attempts/attempt-timeout",
    )
    state = json.loads((run_dir / "watch-state.json").read_text())
    encoded = json.dumps(state).lower()
    assert "yield-curve" not in encoded
    assert "prompt" not in encoded
    assert len(state["evidence_sha256"]) == 64


def test_observe_run_hard_stops_on_symlink_attempt_directory(tmp_path):
    from qea.qfbench_run_watch import observe_run

    run_dir, _ = _attempt(tmp_path)
    outside = tmp_path / "outside-attempt"
    outside.mkdir()
    (run_dir / "attempts" / "attempt-link").symlink_to(
        outside, target_is_directory=True
    )

    result = observe_run(run_dir)

    assert result.hard_stop is True
    assert result.category == "identity_drift"
    assert any(item.attempt_id == "attempt-link" for item in result.attempts)


def test_watch_signals_validated_child_pgid_not_wrapper_pid(tmp_path):
    from qea.process_supervisor import ChildIdentity
    from qea.qfbench_boundary import ProcessIdentity, ProcessSnapshot
    from qea.qfbench_run_watch import WatchConfig, run_watch_once

    run_dir, attempt = _attempt(tmp_path)
    marker = attempt / "proxy-audit.quarantined.json"
    payload = json.loads(marker.read_text())
    payload["reason"] = "post_accept_transport"
    marker.write_text(json.dumps(payload))
    state_dir = tmp_path / "watch"
    state_dir.mkdir()
    child = ChildIdentity(
        pid=5252,
        process_group_id=6262,
        uid=os.getuid(),
        start_ticks=777,
        command_sha256="a" * 64,
        run_id="formal-run",
        source_commit="0" * 40,
    )
    child_path = state_dir / "child-identity.json"
    child_path.write_text(json.dumps(child.to_dict()))
    child_path.chmod(0o600)
    config = WatchConfig(
        run_id="formal-run",
        source_commit="0" * 40,
        run_dir=run_dir,
        state_dir=state_dir,
        child_identity_file=child_path,
        command_token="run.py",
    )
    snapshot = ProcessSnapshot(
        identity=ProcessIdentity(
            child.pid,
            child.process_group_id,
            child.uid,
            child.start_ticks,
            child.command_sha256,
        ),
        state="S",
        argv=("python", "run.py", "formal-run", "0" * 40),
    )
    signals = []

    observation = run_watch_once(
        config,
        process_reader=lambda pid: snapshot,
        signal_group=lambda pgid, requested: signals.append((pgid, requested)),
    )

    assert observation.hard_stop is True
    assert signals == [(6262, signal.SIGTERM)]
    hard_stop = json.loads((state_dir / "hard-stop.json").read_text())
    assert hard_stop["run_id"] == "formal-run"
    assert len(hard_stop["evidence_sha256"]) == 64
    assert hard_stop["created_at"].endswith("+00:00")


def test_load_watch_config_uses_metadata_from_the_open_file(tmp_path, monkeypatch):
    from qea.qfbench_run_watch import load_watch_config

    run_dir, _ = _attempt(tmp_path)
    state_dir = tmp_path / "watch-config-state"
    state_dir.mkdir()
    child_path = state_dir / "child-identity.json"
    child_path.write_text("{}")
    config_path = tmp_path / "watch-config.json"
    config_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run_id": "formal-run",
                "source_commit": "0" * 40,
                "run_dir": str(run_dir),
                "state_dir": str(state_dir),
                "child_identity_file": str(child_path),
                "command_token": "run.py",
            }
        )
    )
    config_path.chmod(0o600)
    original_stat = Path.stat

    def reject_followup_stat(path, *args, **kwargs):
        if path == config_path:
            raise AssertionError("config path must not be stat'ed after reading")
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", reject_followup_stat)

    config = load_watch_config(config_path)

    assert config.run_id == "formal-run"
