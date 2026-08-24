import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


def test_stages_optional_repair_seed_at_output_path(tmp_path):
    from qea.executors import remote_nexau_worker

    work = tmp_path / "app"
    data = work / "data"
    output = work / "output"
    data.mkdir(parents=True)
    output.mkdir()
    (data / "probe_seed_strategy.py").write_text("VALUE = 1\n")

    assert remote_nexau_worker._stage_repair_seed(work, output) is True
    assert (output / "strategy.py").read_text() == "VALUE = 1\n"
    assert remote_nexau_worker._stage_repair_seed(work, output) is False


def test_no_replay_policy_overrides_nested_nexau_and_sdk_retries():
    from qea.executors import remote_nexau_worker

    class FakeLLMConfig:
        def __init__(self):
            self.max_retries = 3
            self.timeout = 180

        def to_client_kwargs(self):
            return {"api_key": "placeholder", "timeout": self.timeout}

    child = SimpleNamespace(
        retry_attempts=5,
        llm_config=FakeLLMConfig(),
        sub_agents={},
    )
    config = SimpleNamespace(
        retry_attempts=5,
        llm_config=FakeLLMConfig(),
        sub_agents={"child": child},
    )

    remote_nexau_worker._pin_no_replay_policy(config)

    for item in (config, child):
        assert item.retry_attempts == 1
        assert item.llm_config.max_retries == 0
        assert item.llm_config.timeout == 360.0
        assert item.llm_config.to_client_kwargs()["max_retries"] == 0


def test_no_replay_policy_rejects_constructed_client_retry_drift():
    from qea.executors import remote_nexau_worker

    with pytest.raises(RuntimeError, match="retry policy drifted"):
        remote_nexau_worker._verify_no_replay_client(
            SimpleNamespace(openai_client=SimpleNamespace(max_retries=2))
        )


def test_structured_tool_trace_preserves_skill_activation():
    from qea.executors import remote_nexau_worker

    tool_use = SimpleNamespace(
        type="tool_use",
        name="LoadSkill",
        input={"skill_name": "spec-driven-deliverables"},
    )
    tool_result = SimpleNamespace(
        type="tool_result",
        content=(
            "Found the skill details of `spec-driven-deliverables`.\n"
            "<SkillDetails><SkillName>spec-driven-deliverables</SkillName>"
            "</SkillDetails>"
        ),
    )

    use_text = remote_nexau_worker._message_text(
        SimpleNamespace(content=[tool_use], get_text_content=lambda: "")
    )
    result_text = remote_nexau_worker._message_text(
        SimpleNamespace(content=[tool_result], get_text_content=lambda: "")
    )

    assert "LoadSkill" in use_text
    assert "spec-driven-deliverables" in use_text
    assert "<SkillDetails>" in result_text
    assert "spec-driven-deliverables" in result_text


def test_trace_role_uses_enum_value_instead_of_debug_representation():
    from qea.executors import remote_nexau_worker

    role = SimpleNamespace(value="assistant")

    assert remote_nexau_worker._role_name(SimpleNamespace(role=role)) == "assistant"


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
        def __init__(self):
            self.retry_attempts = 5
            self.llm_config = SimpleNamespace(
                max_retries=3,
                timeout=180,
                to_client_kwargs=lambda: {"timeout": 180},
            )
            self.sub_agents = {}

        @classmethod
        def from_yaml(cls, *, config_path):
            from tools.fixture import echo

            assert config_path == worker / "agent.yaml"
            assert echo("loaded") == {"value": "loaded"}
            return cls()

    class FakeAgent:
        def __init__(self, config):
            self.config = config
            client_kwargs = config.llm_config.to_client_kwargs()
            self.openai_client = SimpleNamespace(
                max_retries=client_kwargs["max_retries"]
            )
            self.sandbox_manager = SimpleNamespace(
                instance=SimpleNamespace(work_dir=None)
            )
            self.full_trace = []

        def run(self, *, message, context):
            assert "Use the local fixture tool" in message
            assert "reusable quantitative-research behavior" in message
            assert "not a benchmark-specific answer patch" in message
            assert "Task-specific rules are allowed" in message
            assert "hidden checker behavior" in message
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


def test_remote_runner_preserves_artifacts_for_official_verification_after_empty_model_response(
    tmp_path, monkeypatch
):
    """A completed but empty model turn must not discard this sampled attempt."""

    from qea.executors import remote_nexau_worker

    task = tmp_path / "task"
    worker = tmp_path / "worker"
    work = tmp_path / "work"
    output = tmp_path / "output"
    result = tmp_path / "result"
    task.mkdir()
    worker.mkdir()
    work.mkdir()
    (task / "instruction.md").write_text("Produce the requested artifacts.\n")
    (worker / "agent.yaml").write_text("name: fixture\n")

    class FakeAgentConfig:
        def __init__(self):
            self.retry_attempts = 5
            self.llm_config = SimpleNamespace(
                max_retries=3,
                timeout=180,
                to_client_kwargs=lambda: {"timeout": 180},
            )
            self.sub_agents = {}

        @classmethod
        def from_yaml(cls, *, config_path):
            assert config_path == worker / "agent.yaml"
            return cls()

    class FakeAgent:
        def __init__(self, config):
            client_kwargs = config.llm_config.to_client_kwargs()
            self.openai_client = SimpleNamespace(
                max_retries=client_kwargs["max_retries"]
            )
            self.sandbox_manager = SimpleNamespace(
                instance=SimpleNamespace(work_dir=None)
            )
            self.full_trace = [
                SimpleNamespace(
                    role="assistant",
                    get_text_content=lambda: "partial work before the empty turn",
                )
            ]

        def run(self, *, message, context):
            output.mkdir(parents=True, exist_ok=True)
            (output / "partial.json").write_text('{"status":"partial"}\n')
            cause = Exception("No response content or tool calls")
            raise RuntimeError(
                "Error in agent execution: No response content or tool calls"
            ) from cause

    monkeypatch.setitem(
        sys.modules,
        "nexau",
        SimpleNamespace(Agent=FakeAgent, AgentConfig=FakeAgentConfig),
    )

    assert remote_nexau_worker.run(task, worker, work, output, result) == 0
    assert (result / "final.txt").read_text() == ""
    assert (output / "partial.json").is_file()
    summary = json.loads((result / "summary.json").read_text())
    assert summary["outcome"] == "model_empty_response"
    assert summary["files"] == 1
    assert summary["turns"] == 1
    assert "partial work" in (result / "raw_trace.jsonl").read_text()


def test_remote_runner_does_not_swallow_other_agent_failures(tmp_path, monkeypatch):
    from qea.executors import remote_nexau_worker

    task = tmp_path / "task"
    worker = tmp_path / "worker"
    work = tmp_path / "work"
    output = tmp_path / "output"
    result = tmp_path / "result"
    task.mkdir()
    worker.mkdir()
    work.mkdir()
    (task / "instruction.md").write_text("Produce the requested artifacts.\n")
    (worker / "agent.yaml").write_text("name: fixture\n")

    class FakeAgentConfig:
        def __init__(self):
            self.retry_attempts = 5
            self.llm_config = SimpleNamespace(
                max_retries=3,
                timeout=180,
                to_client_kwargs=lambda: {"timeout": 180},
            )
            self.sub_agents = {}

        @classmethod
        def from_yaml(cls, *, config_path):
            return cls()

    class FakeAgent:
        def __init__(self, config):
            client_kwargs = config.llm_config.to_client_kwargs()
            self.openai_client = SimpleNamespace(
                max_retries=client_kwargs["max_retries"]
            )
            self.sandbox_manager = SimpleNamespace(
                instance=SimpleNamespace(work_dir=None)
            )
            self.full_trace = []

        def run(self, *, message, context):
            raise RuntimeError("dependency import failed")

    monkeypatch.setitem(
        sys.modules,
        "nexau",
        SimpleNamespace(Agent=FakeAgent, AgentConfig=FakeAgentConfig),
    )

    with pytest.raises(RuntimeError, match="dependency import failed"):
        remote_nexau_worker.run(task, worker, work, output, result)


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
