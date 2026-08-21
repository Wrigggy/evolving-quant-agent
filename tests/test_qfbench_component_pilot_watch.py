import json
import os
import time
from pathlib import Path


def _state(monkeypatch, **overrides):
    values = {
        "ActiveState": "active",
        "SubState": "running",
        "Result": "success",
        "ExecMainStatus": "0",
        "NRestarts": "0",
    }
    values.update(overrides)
    monkeypatch.setattr(
        "scripts.watch_qfbench_component_pilot._unit_state",
        lambda unit: values,
    )


def test_health_is_healthy_then_complete(tmp_path, monkeypatch):
    from scripts.watch_qfbench_component_pilot import build_health

    _state(monkeypatch)
    attempt = tmp_path / "attempts/a"
    attempt.mkdir(parents=True)
    (attempt / "worker-execution.json").write_text("{}\n")
    health = build_health(run_id="pilot", unit="pilot.service", run_dir=tmp_path)
    assert health["category"] == "healthy"
    assert health["worker_count"] == 1
    assert health["needs_codex"] is False

    (tmp_path / "pilot-report.json").write_text(
        json.dumps({"status": "complete"}) + "\n"
    )
    complete = build_health(run_id="pilot", unit="pilot.service", run_dir=tmp_path)
    assert complete["category"] == "complete"
    assert complete["needs_codex"] is False


def test_health_recognizes_quantcodeeval_h0_result(tmp_path, monkeypatch):
    from scripts.watch_qfbench_component_pilot import build_health

    _state(
        monkeypatch,
        ActiveState="inactive",
        SubState="dead",
    )
    (tmp_path / "H0-RESULT.json").write_text(
        json.dumps({"status": "complete"}) + "\n"
    )

    health = build_health(run_id="qce-h0", unit="qea-qce-h0.service", run_dir=tmp_path)

    assert health["category"] == "complete"
    assert health["needs_codex"] is False


def test_health_alerts_after_bounded_restart_budget(tmp_path, monkeypatch):
    from scripts.watch_qfbench_component_pilot import build_health

    _state(
        monkeypatch,
        ActiveState="failed",
        SubState="failed",
        Result="exit-code",
        ExecMainStatus="1",
        NRestarts="3",
    )
    health = build_health(run_id="pilot", unit="pilot.service", run_dir=tmp_path)
    assert health["category"] == "restart_budget_exhausted"
    assert health["needs_codex"] is True


def test_health_treats_bounded_auto_restart_as_transient(tmp_path, monkeypatch):
    from scripts.watch_qfbench_component_pilot import build_health

    _state(
        monkeypatch,
        ActiveState="activating",
        SubState="auto-restart",
        Result="exit-code",
        ExecMainStatus="1",
    )
    health = build_health(run_id="pilot", unit="pilot.service", run_dir=tmp_path)
    assert health["category"] == "healthy"
    assert health["needs_codex"] is False


def test_health_allows_observed_long_numerical_worker_window(tmp_path, monkeypatch):
    from scripts.watch_qfbench_component_pilot import build_health

    _state(monkeypatch)
    attempt = tmp_path / "attempts/a"
    attempt.mkdir(parents=True)
    progress = attempt / "worker-execution.json"
    progress.write_text("{}\n")
    thirty_minutes_ago = time.time() - 1800
    os.utime(progress, (thirty_minutes_ago, thirty_minutes_ago))

    default_health = build_health(
        run_id="long-numerical",
        unit="long-numerical.service",
        run_dir=tmp_path,
    )
    strict_health = build_health(
        run_id="long-numerical",
        unit="long-numerical.service",
        run_dir=tmp_path,
        stalled_after_seconds=1200,
    )

    assert default_health["category"] == "healthy"
    assert default_health["stalled_after_seconds"] == 3600
    assert strict_health["category"] == "stalled"
    assert strict_health["needs_codex"] is True
