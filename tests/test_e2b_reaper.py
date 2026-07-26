import json
from pathlib import Path
import subprocess
import sys


def test_reaper_is_dry_run_by_default_and_updates_exact_lifecycle_on_apply(tmp_path):
    from qea.e2b_reaper import reap_e2b_sandboxes

    lifecycle = tmp_path / "run" / "attempts" / "a1" / "worker-sandbox-lifecycle.json"
    lifecycle.parent.mkdir(parents=True)
    lifecycle.write_text(json.dumps({
        "schema_version": 1,
        "run_id": "run-1",
        "attempt_id": "attempt-1",
        "task_id": "task-1",
        "role": "worker",
        "sandbox_id": "sandbox-exact-1",
        "cleaned_up": False,
    }))
    killed = []

    dry = reap_e2b_sandboxes(
        tmp_path, kill_sandbox=lambda sandbox_id: killed.append(sandbox_id) or True
    )
    assert dry.pending_ids == ("sandbox-exact-1",)
    assert dry.killed_ids == ()
    assert killed == []
    assert json.loads(lifecycle.read_text())["cleaned_up"] is False

    applied = reap_e2b_sandboxes(
        tmp_path,
        kill_sandbox=lambda sandbox_id: killed.append(sandbox_id) or True,
        apply=True,
    )
    assert applied.killed_ids == ("sandbox-exact-1",)
    assert killed == ["sandbox-exact-1"]
    payload = json.loads(lifecycle.read_text())
    assert payload["cleaned_up"] is True
    assert payload["cleanup_method"] == "reaper"


def test_reaper_rejects_duplicate_sandbox_identity(tmp_path):
    from qea.e2b_reaper import E2BReaperError, reap_e2b_sandboxes

    for index in (1, 2):
        path = tmp_path / f"run-{index}" / "worker-sandbox-lifecycle.json"
        path.parent.mkdir()
        path.write_text(json.dumps({
            "schema_version": 1,
            "run_id": f"run-{index}",
            "attempt_id": f"attempt-{index}",
            "task_id": "task",
            "role": "worker",
            "sandbox_id": "duplicate-id",
            "cleaned_up": False,
        }))

    try:
        reap_e2b_sandboxes(tmp_path, kill_sandbox=lambda _: True, apply=True)
    except E2BReaperError as exc:
        assert "duplicate sandbox ID" in str(exc)
    else:
        raise AssertionError("duplicate sandbox IDs must be rejected")


def test_reaper_script_is_directly_invokable():
    repository = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [sys.executable, "scripts/reap_qfbench_e2b.py", "--help"],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "--results-dir" in proc.stdout
    assert "--apply" in proc.stdout
