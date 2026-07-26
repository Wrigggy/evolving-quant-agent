import json
from types import SimpleNamespace

from qea.evaluation import OfficialTaskScore


PINNED_COMMIT = "024921eb507fcc0c4ffe3e0a96802724be1ae84a"
TASK_IDS = (
    "delta-hedging-pnl-simulation",
    "swap-curve-bootstrap-ois",
    "form4-cross-sectional-sale-pressure",
)


def _write_evidence(verifier, *, stdout="2 failed", cleaned=True):
    verifier.mkdir(parents=True)
    (verifier / "verifier-requirements.lock").write_text("pytest==8.4.1\n")
    (verifier / "verifier-harness.json").write_text(json.dumps({
        "official_sha256": "a" * 64,
        "executed_sha256": "b" * 64,
        "dependency_lock_sha256": "c" * 64,
        "offline_transformed": True,
    }))
    (verifier / "verifier-command.trusted.json").write_text(json.dumps({
        "stdout": stdout,
        "stderr": "",
        "exit_code": 1,
    }))
    (verifier / "verifier-sandbox-lifecycle.json").write_text(json.dumps({
        "schema_version": 1,
        "sandbox_id": "sandbox-1",
        "cleaned_up": cleaned,
    }))
    return verifier


def _evidence(tmp_path, *, stdout="2 failed", cleaned=True):
    return _write_evidence(tmp_path / "verifier", stdout=stdout, cleaned=cleaned)


def test_assess_evidence_accepts_real_offline_pytest_failure(tmp_path):
    from scripts.smoke_qfbench_e2b_verifier_template import _assess_evidence

    score = OfficialTaskScore(
        task_id="delta-hedging-pnl-simulation",
        domain="derivatives",
        reward=0.0,
        diagnostic_tags=("tests_failed",),
        tests_passed=0,
        tests_failed=2,
    )

    result = _assess_evidence(score, _evidence(tmp_path))

    assert result["accepted"] is True
    assert result["tests_executed"] == 2


def test_assess_evidence_rejects_zero_tests_and_dependency_failure(tmp_path):
    from scripts.smoke_qfbench_e2b_verifier_template import _assess_evidence

    score = OfficialTaskScore(
        task_id="swap-curve-bootstrap-ois",
        domain="rates_fx_macro",
        reward=0.0,
        tests_passed=0,
        tests_failed=0,
    )
    verifier = _evidence(
        tmp_path,
        stdout=(
            "No solution found when resolving tool dependencies. "
            "Packages were unavailable because the network was disabled."
        ),
    )

    result = _assess_evidence(score, verifier)

    assert result["accepted"] is False
    assert "no official tests executed" in result["failure_reasons"]
    assert "offline dependency resolution failed" in result["failure_reasons"]


def test_main_refuses_to_start_without_paid_gate(tmp_path, capsys):
    from scripts import smoke_qfbench_e2b_verifier_template as canary

    result = canary.main([
        "--qfbench-root",
        str(tmp_path / "missing"),
        "--template-manifest-dir",
        str(tmp_path / "manifests"),
    ])

    assert result == 2
    assert "NOT STARTED" in capsys.readouterr().out


def test_load_verifier_templates_requires_published_matching_manifests(tmp_path):
    from scripts.smoke_qfbench_e2b_verifier_template import _load_verifier_templates

    task = SimpleNamespace(task_id=TASK_IDS[0])
    (tmp_path / f"{task.task_id}.verifier.image.json").write_text(json.dumps({
        "task_id": task.task_id,
        "role": "verifier",
        "benchmark_commit": PINNED_COMMIT,
        "published_template_id": "template-1",
        "published_build_id": "build-1",
        "verifier_uvx_warm_command": (
            "uvx -p 3.11 -w pytest pytest --version"
        ),
    }))

    assert _load_verifier_templates(tmp_path, (task,), PINNED_COMMIT) == {
        task.task_id: "template-1"
    }


def test_main_runs_only_empty_artifact_offline_verifiers(tmp_path, monkeypatch):
    from scripts import smoke_qfbench_e2b_verifier_template as canary

    tasks = {
        task_id: SimpleNamespace(task_id=task_id, domain="test-domain")
        for task_id in TASK_IDS
    }
    snapshot = SimpleNamespace(
        commit=PINNED_COMMIT,
        task=lambda task_id: tasks[task_id],
    )
    observed = {"artifact_dirs": []}

    def fake_load_snapshot(root, *, manifest_path):
        observed["snapshot"] = (root, manifest_path)
        return snapshot

    def fake_load_templates(directory, selected_tasks, commit):
        observed["manifest_load"] = (directory, selected_tasks, commit)
        return {task.task_id: f"template-{task.task_id}" for task in selected_tasks}

    class FakeLeasePool:
        def __init__(self, root, *, max_leases):
            observed["lease"] = (root, max_leases)

    class FakeVerifier:
        def __init__(self, config, *, lease_pool):
            observed["config"] = config
            observed["lease_pool"] = lease_pool

        def verify(self, *, attempt, task, execution, run_dir):
            artifact_dir = execution.artifact_dir
            assert artifact_dir.is_dir()
            assert not tuple(artifact_dir.iterdir())
            observed["artifact_dirs"].append(artifact_dir)
            verifier_dir = run_dir / "attempts" / attempt.attempt_id / "verifier"
            _write_evidence(verifier_dir)
            return OfficialTaskScore(
                task_id=task.task_id,
                domain=task.domain,
                reward=0.0,
                diagnostic_tags=("tests_failed",),
                verifier_exit_code=1,
                tests_passed=0,
                tests_failed=2,
            )

    def fake_reap(root, *, kill_sandbox, apply):
        observed["reaper"] = (root, apply)
        return SimpleNamespace(pending_ids=())

    monkeypatch.setattr(canary, "load_qfbench_snapshot", fake_load_snapshot)
    monkeypatch.setattr(canary, "_load_verifier_templates", fake_load_templates)
    monkeypatch.setattr(canary, "E2BLeasePool", FakeLeasePool)
    monkeypatch.setattr(canary, "E2BQFBenchVerifier", FakeVerifier)
    monkeypatch.setattr(canary, "reap_e2b_sandboxes", fake_reap)

    result = canary.main([
        "--qfbench-root",
        str(tmp_path / "snapshot"),
        "--manifest",
        str(tmp_path / "manifest.json"),
        "--template-manifest-dir",
        str(tmp_path / "templates"),
        "--results-dir",
        str(tmp_path / "results"),
        "--run-id",
        "verifier-cache-test",
        "--approve-paid-e2b",
    ])

    summary = json.loads(
        (tmp_path / "results/verifier-cache-test/canary-summary.json").read_text()
    )
    config = observed["config"]
    assert result == 0
    assert config.worker_templates == {}
    assert config.worker_allow_internet is False
    assert config.verifier_allow_internet is False
    assert len(observed["artifact_dirs"]) == 3
    assert observed["lease"][1] == 12
    assert observed["reaper"][1] is False
    assert summary["model_calls"] == 0
    assert summary["worker_sandboxes"] == 0
    assert summary["verifier_sandboxes_expected"] == 3
    assert summary["final_pending_ids"] == []
    assert summary["accepted"] is True
