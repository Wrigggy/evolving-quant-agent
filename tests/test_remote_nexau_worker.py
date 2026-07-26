import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


def test_remote_runner_imports_worker_local_tool_before_loading_config(
    tmp_path, monkeypatch
):
    from qea.executors import remote_nexau_worker

    task = tmp_path / "task"
    worker = tmp_path / "worker"
    work = tmp_path / "work"
    output = tmp_path / "output"
    result = tmp_path / "result"
    task.mkdir()
    (worker / "tools").mkdir(parents=True)
    work.mkdir()
    (task / "instruction.md").write_text("Use the local fixture tool.\n")
    (worker / "agent.yaml").write_text("name: fixture\n")
    (worker / "tools/__init__.py").write_text("")
    (worker / "tools/fixture.py").write_text(
        "def echo(value):\n    return {'value': value}\n"
    )

    class FakeAgentConfig:
        @classmethod
        def from_yaml(cls, *, config_path):
            from tools.fixture import echo

            assert config_path == worker / "agent.yaml"
            assert echo("loaded") == {"value": "loaded"}
            return cls()

    class FakeAgent:
        def __init__(self, config):
            self.config = config
            self.sandbox_manager = SimpleNamespace(
                instance=SimpleNamespace(work_dir=None)
            )
            self.full_trace = []

        def run(self, *, message, context):
            assert "Use the local fixture tool" in message
            assert context["working_directory"] == str(work)
            return "done"

    monkeypatch.setitem(
        sys.modules,
        "nexau",
        SimpleNamespace(Agent=FakeAgent, AgentConfig=FakeAgentConfig),
    )
    monkeypatch.delitem(sys.modules, "tools", raising=False)
    monkeypatch.delitem(sys.modules, "tools.fixture", raising=False)

    assert remote_nexau_worker.run(task, worker, work, output, result) == 0
    assert (result / "final.txt").read_text() == "done"
    assert json.loads((result / "summary.json").read_text())["files"] == 0


def test_task_python_bridge_runs_argv_with_minimal_environment(tmp_path):
    from qea.runtime_bridge import task_python

    work = tmp_path / "app"
    work.mkdir()
    result = task_python(
        ["-c", "import os; print(os.getcwd()); print(os.getenv('LLM_API_KEY'))"],
        cwd=work,
        allowed_root=work,
        timeout_seconds=5,
        max_output_bytes=4096,
        python_executable=sys.executable,
    )

    assert result["exit_code"] == 0
    assert result["stdout"].splitlines() == [str(work), "None"]
    assert result["stderr"] == ""


def test_task_python_bridge_enforces_timeout(tmp_path):
    from qea.runtime_bridge import TaskPythonBridgeError, task_python

    work = tmp_path / "app"
    work.mkdir()
    with pytest.raises(TaskPythonBridgeError, match="timed out"):
        task_python(
            ["-c", "import time; time.sleep(5)"],
            cwd=work,
            allowed_root=work,
            timeout_seconds=1,
            max_output_bytes=4096,
            python_executable=sys.executable,
        )


def test_task_python_bridge_enforces_output_limit(tmp_path):
    from qea.runtime_bridge import TaskPythonBridgeError, task_python

    work = tmp_path / "app"
    work.mkdir()
    with pytest.raises(TaskPythonBridgeError, match="output limit"):
        task_python(
            ["-c", "print('x' * 10000)"],
            cwd=work,
            allowed_root=work,
            timeout_seconds=5,
            max_output_bytes=100,
            python_executable=sys.executable,
        )


def test_task_python_bridge_rejects_cwd_outside_allowed_root(tmp_path):
    from qea.runtime_bridge import TaskPythonBridgeError, task_python

    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    with pytest.raises(TaskPythonBridgeError, match="outside allowed root"):
        task_python(
            ["-c", "print(1)"],
            cwd=outside,
            allowed_root=allowed,
            timeout_seconds=5,
            max_output_bytes=4096,
            python_executable=sys.executable,
        )


@pytest.mark.parametrize("argv", [[], ["/tmp/escape.py"], ["../escape.py"]])
def test_task_python_bridge_rejects_empty_or_escaping_script_argv(tmp_path, argv):
    from qea.runtime_bridge import TaskPythonBridgeError, task_python

    work = tmp_path / "app"
    work.mkdir()
    with pytest.raises(TaskPythonBridgeError, match="argv|script path"):
        task_python(
            argv,
            cwd=work,
            allowed_root=work,
            timeout_seconds=5,
            max_output_bytes=4096,
            python_executable=sys.executable,
        )
