import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]


def _write_child(tmp_path):
    child = tmp_path / "child.py"
    child.write_text(
        """
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

mode, pid_path = sys.argv[1:]
if mode == "ignore":
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    signal.signal(signal.SIGINT, signal.SIG_IGN)
grandchild = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
Path(pid_path).write_text(json.dumps({"child": os.getpid(), "grandchild": grandchild.pid}))
if mode == "success":
    raise SystemExit(0)
while True:
    time.sleep(0.05)
""".strip()
        + "\n"
    )
    return child


def _resume(run_dir, phase="primary"):
    run_dir.mkdir(parents=True)
    (run_dir / "resume.json").write_text(
        json.dumps({"run_id": "formal-run", "phase": phase})
    )


def _config(tmp_path, *, mode="success", grace=0.2):
    from qea.process_supervisor import SupervisorConfig

    child = _write_child(tmp_path)
    pid_path = tmp_path / "pids.json"
    run_dir = tmp_path / "formal-run"
    _resume(run_dir)
    argv = (sys.executable, str(child), mode, str(pid_path))
    command_sha256 = hashlib.sha256(
        ("\x00".join(argv) + "\x00").encode()
    ).hexdigest()
    return (
        SupervisorConfig(
            run_id="formal-run",
            source_commit="0" * 40,
            argv=argv,
            cwd=tmp_path,
            environment=dict(os.environ),
            state_dir=tmp_path / "supervisor",
            run_dir=run_dir,
            expected_child_command_sha256=command_sha256,
            termination_grace_seconds=grace,
        ),
        pid_path,
    )


def _wait_json(path, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.is_file():
            try:
                return json.loads(path.read_text())
            except json.JSONDecodeError:
                pass
        time.sleep(0.02)
    raise AssertionError(f"timed out waiting for {path}")


def _assert_absent(pid):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.02)
    pytest.fail(f"PID {pid} remains alive")


def test_successful_child_exit_reaps_orphaned_grandchild_and_writes_exit(tmp_path):
    from qea.process_supervisor import run_supervised

    config, pid_path = _config(tmp_path)

    exit_code = run_supervised(config)

    pids = _wait_json(pid_path)
    assert exit_code == 0
    _assert_absent(pids["child"])
    _assert_absent(pids["grandchild"])
    assert (config.state_dir / "exit-code").read_text().strip() == "0"
    assert not (config.state_dir / "completion.json").exists()


def _write_config_file(config, path):
    payload = config.to_dict()
    path.write_text(json.dumps(payload))
    path.chmod(0o600)


@pytest.mark.parametrize("requested_signal", [signal.SIGTERM, signal.SIGINT])
def test_supervisor_forwards_signal_to_complete_process_group(
    tmp_path, requested_signal
):
    config, pid_path = _config(tmp_path, mode="wait")
    config_path = tmp_path / "supervisor.json"
    _write_config_file(config, config_path)
    process = subprocess.Popen(
        [
            sys.executable,
            str(REPO / "scripts/run_qfbench_process_supervisor.py"),
            "--config",
            str(config_path),
        ],
        cwd=REPO,
    )
    pids = _wait_json(pid_path)

    os.kill(process.pid, requested_signal)
    process.wait(timeout=8)

    _assert_absent(pids["child"])
    _assert_absent(pids["grandchild"])
    assert (config.state_dir / "exit-code").is_file()


def test_ignored_term_escalates_to_exact_process_group_kill(tmp_path):
    config, pid_path = _config(tmp_path, mode="ignore", grace=0.1)
    config_path = tmp_path / "supervisor.json"
    _write_config_file(config, config_path)
    process = subprocess.Popen(
        [
            sys.executable,
            str(REPO / "scripts/run_qfbench_process_supervisor.py"),
            "--config",
            str(config_path),
        ],
        cwd=REPO,
    )
    pids = _wait_json(pid_path)

    os.kill(process.pid, signal.SIGTERM)
    process.wait(timeout=8)

    _assert_absent(pids["child"])
    _assert_absent(pids["grandchild"])
    assert int((config.state_dir / "exit-code").read_text()) != 0


def test_complete_resume_is_the_only_zero_exit_completion_marker(tmp_path):
    from qea.process_supervisor import run_supervised

    config, _ = _config(tmp_path)
    (config.run_dir / "resume.json").write_text(
        json.dumps({"run_id": "formal-run", "phase": "complete"})
    )

    assert run_supervised(config) == 0
    assert json.loads((config.state_dir / "completion.json").read_text()) == {
        "run_id": "formal-run",
        "status": "complete",
    }


def test_exec_gate_blocks_until_exact_owner_only_release(tmp_path):
    marker = tmp_path / "executed.json"
    target = tmp_path / "target.py"
    target.write_text(
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "Path(sys.argv[1]).write_text(json.dumps({'pid': os.getpid(), 'pgid': os.getpgrp()}))\n"
    )
    gate_dir = tmp_path / "gate"
    argv = (sys.executable, str(target), str(marker))
    process = subprocess.Popen(
        [
            sys.executable,
            str(REPO / "scripts/qfbench_exec_gate.py"),
            "--gate-dir",
            str(gate_dir),
            "--run-id",
            "formal-run",
            "--source-commit",
            "0" * 40,
            "--timeout-seconds",
            "5",
            "--",
            *argv,
        ],
        cwd=REPO,
    )
    ready = _wait_json(gate_dir / "gate-ready.json")
    assert not marker.exists()
    command_sha256 = hashlib.sha256(
        ("\x00".join(argv) + "\x00").encode()
    ).hexdigest()
    assert ready["command_sha256"] == command_sha256

    release = gate_dir / "gate-release.json"
    release.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run_id": "formal-run",
                "source_commit": "0" * 40,
                "command_sha256": command_sha256,
            }
        )
    )
    release.chmod(0o644)
    time.sleep(0.15)
    assert not marker.exists()
    release.chmod(0o600)

    process.wait(timeout=5)
    executed = _wait_json(marker)
    assert executed["pid"] == ready["pid"]
    assert executed["pgid"] == ready["process_group_id"]


def test_supervisor_config_loader_requires_mode_600(tmp_path):
    from qea.process_supervisor import SupervisorError, load_supervisor_config

    config, _ = _config(tmp_path)
    path = tmp_path / "supervisor.json"
    _write_config_file(config, path)
    assert load_supervisor_config(path) == config

    path.chmod(0o644)
    with pytest.raises(SupervisorError, match="mode 600"):
        load_supervisor_config(path)
