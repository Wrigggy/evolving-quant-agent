import hashlib
import io
import json
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from qea.evaluation import TaskAttempt


def _tar_bytes(files):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for name, payload in sorted(files.items()):
            data = payload if isinstance(payload, bytes) else payload.encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


class FakeFiles:
    def __init__(self):
        self.data = {}

    def write(self, path, data, **kwargs):
        self.data[path] = data.read() if hasattr(data, "read") else data
        return SimpleNamespace(path=path)

    def read(self, path, format="text", **kwargs):
        value = self.data[path]
        if format == "bytes" and isinstance(value, str):
            return value.encode()
        if format == "text" and isinstance(value, bytes):
            return value.decode()
        return value


class CommandExitException(Exception):
    def __init__(self, *, exit_code, stdout, stderr):
        super().__init__(stderr)
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.error = stderr


def test_sandbox_file_write_retries_one_closed_http2_connection():
    from qea.executors.e2b_nexau import _write_sandbox_file

    class LocalProtocolError(Exception):
        pass

    class FlakyFiles:
        def __init__(self):
            self.calls = 0

        def write(self, path, data):
            self.calls += 1
            if self.calls == 1:
                raise LocalProtocolError(
                    "Invalid input ConnectionInputs.RECV_PING in state ConnectionState.CLOSED"
                )
            return SimpleNamespace(path=path)

    sandbox = SimpleNamespace(files=FlakyFiles())
    _write_sandbox_file(sandbox, "/tmp/input.tar", b"payload")
    assert sandbox.files.calls == 2


class FakeCommands:
    def __init__(
        self,
        sandbox,
        *,
        fail_worker=False,
        emit_ctrf=True,
        raise_verifier_exit=False,
    ):
        self.sandbox = sandbox
        self.fail_worker = fail_worker
        self.emit_ctrf = emit_ctrf
        self.raise_verifier_exit = raise_verifier_exit
        self.calls = []

    def run(self, command, **kwargs):
        self.calls.append((command, kwargs))
        if "remote_nexau_worker.py" in command:
            if self.fail_worker:
                return SimpleNamespace(exit_code=23, stdout="", stderr="model failed with sk-live-secret")
            self.sandbox.files.data["/qea/result/summary.json"] = json.dumps({
                "turns": 3, "tool_calls": 2, "tool_errors": 0, "files": 6,
            })
            self.sandbox.files.data["/qea/result/raw_trace.jsonl"] = (
                '{"role":"assistant","content":"done"}\n'
            )
            self.sandbox.files.data["/qea/result/final.txt"] = "completed"
        if "qea-output.tar" in command:
            self.sandbox.files.data["/tmp/qea-output.tar"] = _tar_bytes({
                "results.json": "{}\n",
                "table.csv": "x\n1\n",
                "report.html": "<p>ok</p>\n",
                "chart.png": b"\x89PNG\r\n",
                "solve.py": "print('ok')\n",
                "memo.pdf": b"%PDF-1.4\n",
            })
        if "tests/test.sh" in command or "qea-offline-test.sh" in command:
            self.sandbox.files.data["/logs/verifier/reward.txt"] = "0.625\n"
            if self.emit_ctrf:
                self.sandbox.files.data["/logs/verifier/ctrf.json"] = json.dumps({
                    "results": {"summary": {"tests": 8, "passed": 5, "failed": 3}}
                })
            if self.raise_verifier_exit:
                raise CommandExitException(
                    exit_code=1,
                    stdout="5 passed, 3 failed",
                    stderr="secret expected 17",
                )
            return SimpleNamespace(exit_code=1, stdout="5 passed, 3 failed", stderr="secret expected 17")
        return SimpleNamespace(exit_code=0, stdout="ok", stderr="")


class FakeSandbox:
    def __init__(
        self,
        sandbox_id,
        *,
        fail_worker=False,
        emit_ctrf=True,
        raise_verifier_exit=False,
    ):
        self.sandbox_id = sandbox_id
        self.files = FakeFiles()
        self.commands = FakeCommands(
            self,
            fail_worker=fail_worker,
            emit_ctrf=emit_ctrf,
            raise_verifier_exit=raise_verifier_exit,
        )
        self.killed = False

    def kill(self):
        self.killed = True
        return True


class FakeFactory:
    def __init__(
        self,
        *,
        fail_worker=False,
        emit_ctrf=True,
        emit_dependency_lock=True,
        emit_worker_dependency_lock=True,
        raise_verifier_exit=False,
    ):
        self.created = []
        self.fail_worker = fail_worker
        self.emit_ctrf = emit_ctrf
        self.emit_dependency_lock = emit_dependency_lock
        self.emit_worker_dependency_lock = emit_worker_dependency_lock
        self.raise_verifier_exit = raise_verifier_exit

    def create(self, **kwargs):
        role = kwargs["metadata"]["qea_role"]
        sandbox = FakeSandbox(
            f"sandbox-{role}-{len(self.created)}",
            fail_worker=self.fail_worker and role == "worker",
            emit_ctrf=self.emit_ctrf,
            raise_verifier_exit=self.raise_verifier_exit and role == "verifier",
        )
        if role == "verifier" and self.emit_dependency_lock:
            sandbox.files.data["/opt/qea/verifier-requirements.lock"] = (
                "pytest==8.4.1\n"
            )
        if role == "worker" and self.emit_worker_dependency_lock:
            sandbox.files.data["/opt/qea/nexau-requirements.lock"] = (
                "nexau @ git+https://github.com/nex-agi/NexAU.git@"
                "35ee1861546db3cb280a6e17e38a74060d7c96c3\n"
            )
        self.created.append((kwargs, sandbox))
        return sandbox


def _task(tmp_path):
    root = tmp_path / "task"
    (root / "environment" / "data").mkdir(parents=True)
    (root / "tests").mkdir()
    instruction = root / "instruction.md"
    data = root / "environment" / "data" / "input.csv"
    test = root / "tests" / "test_outputs.py"
    test_shell = root / "tests" / "test.sh"
    instruction.write_text("Create files in /root/output.\n")
    data.write_text("x\n1\n")
    test.write_text("def test_output(): pass\n")
    test_shell.write_text(
        "#!/bin/bash\n"
        "curl -LsSf https://astral.sh/uv/0.9.5/install.sh | sh\n"
        "source $HOME/.local/bin/env\n"
        "uvx -p 3.11 -w pytest==8.4.1 pytest /tests/test_outputs.py\n"
        "echo 1 > /logs/verifier/reward.txt\n"
    )
    return SimpleNamespace(
        task_id="fixture-task",
        domain="risk",
        root=root,
        instruction_path=instruction,
        worker_files=(data, instruction),
        verifier_files=(test_shell, test),
        agent_timeout_seconds=90,
        verifier_timeout_seconds=30,
    )


def _worker(tmp_path):
    root = tmp_path / "worker"
    root.mkdir()
    (root / "agent.yaml").write_text("name: worker\n")
    (root / "systemprompt.md").write_text("Solve the task.\n")
    return root


def _attempt():
    return TaskAttempt.create(
        run_id="run-001",
        benchmark_commit="0" * 40,
        task_id="fixture-task",
        split="optimize",
        checkpoint="seed",
        worker_digest="a" * 64,
    )


def _config():
    from qea.executors.e2b_nexau import E2BNexAUConfig

    return E2BNexAUConfig(
        worker_templates={"fixture-task": "worker-template@sha256:abc"},
        verifier_templates={"fixture-task": "verifier-template@sha256:def"},
        timeout_seconds=120,
        worker_allow_internet=True,
        verifier_allow_internet=False,
    )


def test_worker_runs_nexau_inside_e2b_collects_generic_outputs_and_cleans_up(tmp_path):
    from qea.e2b_lease import E2BLeasePool
    from qea.executors.e2b_nexau import E2BNexAUExecutor

    factory = FakeFactory()
    executor = E2BNexAUExecutor(
        _config(),
        sandbox_factory=factory,
        lease_pool=E2BLeasePool(tmp_path / "leases", max_leases=2),
    )
    result = executor.execute(
        attempt=_attempt(),
        task=_task(tmp_path),
        worker_dir=_worker(tmp_path),
        run_dir=tmp_path / "run",
        model_env={
            "LLM_API_KEY": "sk-live-secret",
            "LLM_BASE_URL": "https://model.example/v1",
            "LLM_MODEL": "example/model",
            "E2B_API_KEY": "must-not-enter-worker",
            "AWS_SECRET_ACCESS_KEY": "must-not-enter-worker",
        },
    )

    create_kwargs, sandbox = factory.created[0]
    assert create_kwargs["template"] == "worker-template@sha256:abc"
    assert create_kwargs["allow_internet_access"] is True
    assert create_kwargs["envs"] == {
        "LLM_API_KEY": "e2b-header-injected",
        "LLM_BASE_URL": "https://model.example/v1",
        "LLM_MODEL": "example/model",
        "SSL_CERT_FILE": "/etc/ssl/certs/ca-certificates.crt",
    }
    network = dict(create_kwargs["network"])
    deny_out = network.pop("deny_out")
    assert callable(deny_out)
    assert deny_out(SimpleNamespace(all_traffic="0.0.0.0/0")) == ["0.0.0.0/0"]
    assert network == {
        "allow_out": ["model.example"],
        "rules": {
            "model.example": [{
                "transform": {"headers": {"Authorization": "Bearer sk-live-secret"}}
            }]
        },
        "allow_public_traffic": False,
    }
    assert sandbox.killed is True
    assert any("remote_nexau_worker.py" in command for command, _ in sandbox.commands.calls)
    assert any(
        "--work-dir /app --output-dir /app/output" in command
        for command, _ in sandbox.commands.calls
    )
    worker_command = next(
        (command, kwargs) for command, kwargs in sandbox.commands.calls
        if "remote_nexau_worker.py" in command
    )
    assert worker_command[0].startswith(
        "/opt/qea/nexau-venv/bin/python /qea/remote_nexau_worker.py"
    )
    assert worker_command[1]["envs"]["LLM_API_KEY"] == "e2b-header-injected"
    assert worker_command[1]["envs"]["SSL_CERT_FILE"] == (
        "/etc/ssl/certs/ca-certificates.crt"
    )
    assert worker_command[1]["timeout"] == 90
    assert b"from nexau import Agent" in sandbox.files.data["/qea/remote_nexau_worker.py"]
    assert {record.path for record in result.artifacts} == {
        "chart.png", "memo.pdf", "report.html", "results.json", "solve.py", "table.csv",
    }
    assert result.cleaned_up is True
    lifecycle = json.loads(next(
        (tmp_path / "run").rglob("worker-sandbox-lifecycle.json")
    ).read_text())
    assert lifecycle["sandbox_id"].startswith("sandbox-worker-")
    assert lifecycle["cleaned_up"] is True
    assert Path(result.trace_uri).read_text().startswith('{"role"')
    dependency_lock = next(
        (tmp_path / "run").rglob("nexau-requirements.lock")
    )
    assert result.summary["dependency_lock_sha256"] == hashlib.sha256(
        dependency_lock.read_bytes()
    ).hexdigest()
    assert "sk-live-secret" not in Path(result.log_uri).read_text()
    assert all(
        "sk-live-secret" not in str(value)
        for value in sandbox.files.data.values()
    )


def test_worker_rejects_template_without_nexau_dependency_lock(tmp_path):
    from qea.e2b_lease import E2BLeasePool
    from qea.executors.e2b_nexau import E2BExecutionError, E2BNexAUExecutor

    factory = FakeFactory(emit_worker_dependency_lock=False)
    executor = E2BNexAUExecutor(
        _config(),
        sandbox_factory=factory,
        lease_pool=E2BLeasePool(tmp_path / "leases", max_leases=1),
    )
    with pytest.raises(E2BExecutionError, match="NexAU dependency lock"):
        executor.execute(
            attempt=_attempt(),
            task=_task(tmp_path),
            worker_dir=_worker(tmp_path),
            run_dir=tmp_path / "run",
            model_env={
                "LLM_API_KEY": "sk-live-secret",
                "LLM_BASE_URL": "https://model.example/v1",
                "LLM_MODEL": "example/model",
            },
        )

    sandbox = factory.created[0][1]
    assert sandbox.killed is True
    assert not any(
        "remote_nexau_worker.py" in command
        for command, _ in sandbox.commands.calls
    )


def test_worker_setup_accepts_official_task_without_data_directory(tmp_path):
    from qea.e2b_lease import E2BLeasePool
    from qea.executors.e2b_nexau import E2BNexAUExecutor

    task = _task(tmp_path)
    data_file = task.root / "environment" / "data" / "input.csv"
    data_file.unlink()
    data_file.parent.rmdir()
    task.worker_files = (task.instruction_path,)
    factory = FakeFactory()
    executor = E2BNexAUExecutor(
        _config(),
        sandbox_factory=factory,
        lease_pool=E2BLeasePool(tmp_path / "leases", max_leases=1),
    )

    executor.execute(
        attempt=_attempt(),
        task=task,
        worker_dir=_worker(tmp_path),
        run_dir=tmp_path / "run",
        model_env={
            "LLM_API_KEY": "secret",
            "LLM_BASE_URL": "https://model.example/v1",
            "LLM_MODEL": "example/model",
        },
    )

    commands = [command for command, _ in factory.created[0][1].commands.calls]
    setup = next(command for command in commands if "tar -xf /tmp/qea-worker.tar" in command)
    assert "if [ -d /qea/task/environment/data ]" in setup


def test_worker_failure_still_kills_sandbox_and_scrubs_log(tmp_path):
    from qea.e2b_lease import E2BLeasePool
    from qea.executors.e2b_nexau import E2BExecutionError, E2BNexAUExecutor

    factory = FakeFactory(fail_worker=True)
    executor = E2BNexAUExecutor(
        _config(),
        sandbox_factory=factory,
        lease_pool=E2BLeasePool(tmp_path / "leases", max_leases=1),
    )
    with pytest.raises(E2BExecutionError, match="worker command failed"):
        executor.execute(
            attempt=_attempt(),
            task=_task(tmp_path),
            worker_dir=_worker(tmp_path),
            run_dir=tmp_path / "run",
            model_env={
                "LLM_API_KEY": "sk-live-secret",
                "LLM_BASE_URL": "https://model.example/v1",
                "LLM_MODEL": "example/model",
            },
        )

    assert factory.created[0][1].killed is True
    lifecycle = json.loads(next(
        (tmp_path / "run").rglob("worker-sandbox-lifecycle.json")
    ).read_text())
    assert lifecycle["cleaned_up"] is True
    log = next((tmp_path / "run").rglob("worker-command.json")).read_text()
    assert "sk-live-secret" not in log
    assert "[REDACTED]" in log


def test_worker_command_timeout_is_normalized_and_persisted(tmp_path):
    from qea.e2b_lease import E2BLeasePool
    from qea.executors.e2b_nexau import E2BNexAUExecutor, E2BWorkerTimeout

    class TimeoutException(Exception):
        pass

    class TimeoutFactory(FakeFactory):
        def create(self, **kwargs):
            sandbox = super().create(**kwargs)
            original = sandbox.commands

            class TimeoutCommands:
                calls = original.calls

                def run(self, command, **command_kwargs):
                    if "remote_nexau_worker.py" in command:
                        raise TimeoutException(
                            "context deadline exceeded with sk-live-secret"
                        )
                    return original.run(command, **command_kwargs)

            sandbox.commands = TimeoutCommands()
            return sandbox

    factory = TimeoutFactory()
    executor = E2BNexAUExecutor(
        _config(),
        sandbox_factory=factory,
        lease_pool=E2BLeasePool(tmp_path / "leases", max_leases=1),
    )

    with pytest.raises(E2BWorkerTimeout, match="official agent timeout"):
        executor.execute(
            attempt=_attempt(),
            task=_task(tmp_path),
            worker_dir=_worker(tmp_path),
            run_dir=tmp_path / "run",
            model_env={
                "LLM_API_KEY": "sk-live-secret",
                "LLM_BASE_URL": "https://model.example/v1",
                "LLM_MODEL": "example/model",
            },
        )

    assert factory.created[0][1].killed is True
    command = json.loads(next(
        (tmp_path / "run").rglob("worker-command.json")
    ).read_text())
    assert command["timed_out"] is True
    assert "sk-live-secret" not in json.dumps(command)
    assert "[REDACTED]" in command["error"]


def test_verifier_uses_distinct_no_network_sandbox_and_official_reward(tmp_path):
    from qea.e2b_lease import E2BLeasePool
    from qea.executors.e2b_nexau import E2BNexAUExecutor, E2BQFBenchVerifier

    factory = FakeFactory(raise_verifier_exit=True)
    leases = E2BLeasePool(tmp_path / "leases", max_leases=2)
    task = _task(tmp_path)
    worker = E2BNexAUExecutor(_config(), sandbox_factory=factory, lease_pool=leases)
    execution = worker.execute(
        attempt=_attempt(),
        task=task,
        worker_dir=_worker(tmp_path),
        run_dir=tmp_path / "run",
        model_env={
            "LLM_API_KEY": "secret",
            "LLM_BASE_URL": "https://model.example/v1",
            "LLM_MODEL": "example/model",
        },
    )
    verifier = E2BQFBenchVerifier(_config(), sandbox_factory=factory, lease_pool=leases)
    score = verifier.verify(
        attempt=_attempt(),
        task=task,
        execution=execution,
        run_dir=tmp_path / "run",
    )

    verifier_kwargs, verifier_sandbox = factory.created[1]
    assert verifier_kwargs["metadata"]["qea_role"] == "verifier"
    assert verifier_kwargs["template"] == "verifier-template@sha256:def"
    assert verifier_kwargs["allow_internet_access"] is False
    assert verifier_kwargs["envs"] == {}
    assert verifier_sandbox.killed is True
    assert any(
        "cp -R /qea_verify/artifacts/. /app/output/" in command
        for command, _ in verifier_sandbox.commands.calls
    )
    assert any(
        "bash /tmp/qea-offline-test.sh" in command
        for command, _ in verifier_sandbox.commands.calls
    )
    verifier_command = next(
        kwargs for command, kwargs in verifier_sandbox.commands.calls
        if "qea-offline-test.sh" in command
    )
    assert verifier_command["timeout"] == 30
    assert verifier_command["envs"]["UV_CACHE_DIR"] == "/opt/qea/uv-cache"
    assert verifier_command["envs"]["UV_TOOL_DIR"] == "/opt/qea/uv-tools"
    assert verifier_command["envs"]["UV_TOOL_BIN_DIR"] == "/opt/qea/uv-bin"
    offline_script = verifier_sandbox.files.data["/tmp/qea-offline-test.sh"]
    assert "astral.sh" not in offline_script
    assert "UV_OFFLINE=1" in offline_script
    assert "echo 1 > /logs/verifier/reward.txt" in offline_script
    assert score.reward == 0.625
    assert score.diagnostic_tags == ("tests_failed",)
    persisted = next((tmp_path / "run").rglob("official-score.json")).read_text()
    assert "secret expected 17" not in persisted
    harness = next((tmp_path / "run").rglob("verifier-harness.json")).read_text()
    assert '"offline_transformed": true' in harness
    assert '"official_sha256"' in harness
    assert '"executed_sha256"' in harness
    assert '"dependency_lock_sha256"' in harness
    dependency_lock = next(
        (tmp_path / "run").rglob("verifier-requirements.lock")
    )
    assert dependency_lock.read_text() == "pytest==8.4.1\n"


def test_verifier_setup_tolerates_empty_artifact_bundle(tmp_path):
    from qea.e2b_lease import E2BLeasePool
    from qea.executors.e2b_nexau import E2BQFBenchVerifier

    factory = FakeFactory(raise_verifier_exit=True)
    artifacts = tmp_path / "empty-artifacts"
    artifacts.mkdir()
    verifier = E2BQFBenchVerifier(
        _config(),
        sandbox_factory=factory,
        lease_pool=E2BLeasePool(tmp_path / "leases", max_leases=1),
    )

    verifier.verify(
        attempt=_attempt(),
        task=_task(tmp_path),
        execution=SimpleNamespace(artifact_dir=artifacts),
        run_dir=tmp_path / "run",
    )

    setup_command = next(
        command for command, _ in factory.created[0][1].commands.calls
        if "qea-verifier.tar" in command
    )
    assert "mkdir -p /qea_verify/artifacts" in setup_command
    assert setup_command.index("mkdir -p /qea_verify/artifacts") < setup_command.index(
        "cp -R /qea_verify/artifacts/. /app/output/"
    )


def test_verifier_rejects_template_without_dependency_lock(tmp_path):
    from qea.e2b_lease import E2BLeasePool
    from qea.executors.e2b_nexau import (
        E2BExecutionError,
        E2BNexAUExecutor,
        E2BQFBenchVerifier,
    )

    factory = FakeFactory(emit_dependency_lock=False)
    leases = E2BLeasePool(tmp_path / "leases", max_leases=2)
    task = _task(tmp_path)
    execution = E2BNexAUExecutor(
        _config(), sandbox_factory=factory, lease_pool=leases
    ).execute(
        attempt=_attempt(),
        task=task,
        worker_dir=_worker(tmp_path),
        run_dir=tmp_path / "run",
        model_env={
            "LLM_API_KEY": "secret",
            "LLM_BASE_URL": "https://model.example/v1",
            "LLM_MODEL": "example/model",
        },
    )

    with pytest.raises(E2BExecutionError, match="dependency lock"):
        E2BQFBenchVerifier(
            _config(), sandbox_factory=factory, lease_pool=leases
        ).verify(
            attempt=_attempt(),
            task=task,
            execution=execution,
            run_dir=tmp_path / "run",
        )

    assert factory.created[-1][1].killed is True


def test_verifier_accepts_official_binary_reward_without_ctrf(tmp_path):
    from qea.e2b_lease import E2BLeasePool
    from qea.executors.e2b_nexau import E2BNexAUExecutor, E2BQFBenchVerifier

    factory = FakeFactory(emit_ctrf=False)
    leases = E2BLeasePool(tmp_path / "leases", max_leases=2)
    task = _task(tmp_path)
    execution = E2BNexAUExecutor(
        _config(), sandbox_factory=factory, lease_pool=leases
    ).execute(
        attempt=_attempt(),
        task=task,
        worker_dir=_worker(tmp_path),
        run_dir=tmp_path / "run",
        model_env={
            "LLM_API_KEY": "secret",
            "LLM_BASE_URL": "https://model.example/v1",
            "LLM_MODEL": "example/model",
        },
    )

    score = E2BQFBenchVerifier(
        _config(), sandbox_factory=factory, lease_pool=leases
    ).verify(
        attempt=_attempt(), task=task, execution=execution, run_dir=tmp_path / "run"
    )

    assert score.reward == 0.625
    assert score.tests_passed == 5
    assert score.tests_failed == 3


def test_output_archive_rejects_path_traversal(tmp_path):
    from qea.executors.e2b_nexau import E2BExecutionError, extract_output_archive

    malicious = _tar_bytes({"../escape.txt": "owned"})
    with pytest.raises(E2BExecutionError, match="unsafe output member"):
        extract_output_archive(malicious, tmp_path / "artifacts")
    assert not (tmp_path / "escape.txt").exists()


def test_completed_worker_execution_is_loaded_without_new_sandbox(tmp_path):
    from qea.e2b_lease import E2BLeasePool
    from qea.executors.e2b_nexau import E2BNexAUExecutor, load_worker_execution

    factory = FakeFactory()
    executor = E2BNexAUExecutor(
        _config(),
        sandbox_factory=factory,
        lease_pool=E2BLeasePool(tmp_path / "leases", max_leases=1),
    )
    original = executor.execute(
        attempt=_attempt(),
        task=_task(tmp_path),
        worker_dir=_worker(tmp_path),
        run_dir=tmp_path / "run",
        model_env={
            "LLM_API_KEY": "secret",
            "LLM_BASE_URL": "https://model.example/v1",
            "LLM_MODEL": "example/model",
        },
    )

    restored = load_worker_execution(_attempt(), tmp_path / "run")

    assert restored.attempt_id == original.attempt_id
    assert restored.artifacts == original.artifacts
    assert restored.summary == original.summary
    assert restored.cleaned_up is True
    assert len(factory.created) == 1


def test_oracle_parity_runner_uses_no_llm_and_then_separate_verifier(tmp_path):
    from qea.e2b_lease import E2BLeasePool
    from qea.executors.e2b_nexau import E2BOracleRunner, E2BQFBenchVerifier

    task = _task(tmp_path)
    (task.root / "solution").mkdir()
    (task.root / "solution" / "solve.sh").write_text("mkdir -p /root/output\n")
    factory = FakeFactory()
    leases = E2BLeasePool(tmp_path / "leases", max_leases=2)
    oracle = E2BOracleRunner(_config(), sandbox_factory=factory, lease_pool=leases)
    execution = oracle.execute(
        attempt=_attempt(),
        task=task,
        run_dir=tmp_path / "run",
    )
    score = E2BQFBenchVerifier(
        _config(), sandbox_factory=factory, lease_pool=leases
    ).verify(
        attempt=_attempt(),
        task=task,
        execution=execution,
        run_dir=tmp_path / "run",
    )

    oracle_kwargs, oracle_sandbox = factory.created[0]
    verifier_kwargs, verifier_sandbox = factory.created[1]
    assert oracle_kwargs["metadata"]["qea_role"] == "oracle"
    assert oracle_kwargs["envs"] == {}
    assert oracle_kwargs["allow_internet_access"] is False
    assert oracle_sandbox.killed and verifier_sandbox.killed
    assert verifier_kwargs["metadata"]["qea_role"] == "verifier"
    assert score.reward == 0.625
