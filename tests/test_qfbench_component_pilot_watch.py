import json
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
