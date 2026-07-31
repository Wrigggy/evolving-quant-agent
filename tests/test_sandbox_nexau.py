import hashlib
import io
import json
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from qea.evaluation import ArtifactRecord, OfficialTaskScore, TaskAttempt
from qea.qfbench_images import NEXAU_REQUIREMENTS_LOCK, NEXAU_RUNTIME_PYTHON
from qea.sandbox_backend import (
    KillResult,
    SandboxCommandResult,
    SandboxHandle,
)


def test_sandbox_nexau_reexports_neutral_runtime_contracts():
    from qea.executors import sandbox_nexau, sandbox_runtime

    assert (
        sandbox_nexau.SandboxInfrastructureError
        is sandbox_runtime.SandboxInfrastructureError
    )
    assert sandbox_nexau.SandboxResourceContract is sandbox_runtime.SandboxResourceContract


def _tar_bytes(files):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        for name, value in sorted(files.items()):
            payload = value if isinstance(value, bytes) else value.encode()
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    return output.getvalue()


def _tar_members(payload):
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:*") as archive:
        return tuple(sorted(member.name for member in archive if member.isfile()))


def test_neutral_output_archive_rejects_traversal_without_e2b_import(tmp_path) -> None:
    from qea.executors.output_archive import OutputArchiveError, extract_output_archive

    malicious = _tar_bytes({"../escape.txt": "owned"})
    with pytest.raises(OutputArchiveError, match="unsafe output member"):
        extract_output_archive(malicious, tmp_path / "artifacts")
    assert not (tmp_path / "escape.txt").exists()


class FakeBackend:
    backend_name = "fake-backend"

    def __init__(self, *, failure=None, task_timed_out=False):
        self.failure = failure
        self.task_timed_out = task_timed_out
        self.events = []
        self.specs = []
        self.uploads = {}
        self.lifecycle_root = None

    def _fail(self, event):
        if self.failure == event:
            raise RuntimeError(f"synthetic {event} failure with token-do-not-persist")

    def create(self, spec):
        self.events.append(f"create:{spec.role}")
        self._fail("create")
        self.specs.append(spec)
        return SandboxHandle(
            backend=self.backend_name,
            native_id=f"sandbox-{spec.role}",
            immutable_image_ref=spec.image_ref,
            spec_sha256=spec.spec_sha256,
        )

    def start(self, handle):
        role = handle.native_id.removeprefix("sandbox-")
        lifecycle_exists = bool(
            self.lifecycle_root
            and tuple(Path(self.lifecycle_root).rglob(f"{role}-sandbox-lifecycle-v2.json"))
        )
        self.events.append(f"start:{role}:lifecycle={lifecycle_exists}")
        self._fail("start")

    def put_bytes(self, handle, path, payload):
        role = handle.native_id.removeprefix("sandbox-")
        self.events.append(f"upload:{role}:{path}")
        self._fail("upload")
        self.uploads[(role, path)] = payload

    def read_bytes(self, handle, path):
        role = handle.native_id.removeprefix("sandbox-")
        self.events.append(f"read:{role}:{path}")
        if role == "worker":
            values = {
                NEXAU_REQUIREMENTS_LOCK: b"nexau==0.3.9\n",
                "/qea/output.tar": _tar_bytes({"answer.txt": "42\n"}),
                "/qea/result/raw_trace.jsonl": b'{"role":"assistant","content":"done"}\n',
                "/qea/result/final.txt": b"done\n",
                "/qea/result/summary.json": (
                    b'{"files":1,"secs":0.5,"tool_calls":1,"tool_errors":0,"turns":1}\n'
                ),
            }
        else:
            values = {
                "/opt/qea/verifier-requirements.lock": b"pytest==8.4.1\n",
                "/logs/verifier/reward.txt": b"1\n",
                "/logs/verifier/ctrf.json": (
                    b'{"results":{"summary":{"passed":3,"failed":0}}}\n'
                ),
                "/qea/artifact-integrity.json": (
                    b'{"answer.txt":{"sha256":"'
                    + hashlib.sha256(b"42\n").hexdigest().encode()
                    + b'","size_bytes":3}}\n'
                ),
            }
        return values[path]

    def run(self, handle, argv, *, environment, timeout_seconds):
        role = handle.native_id.removeprefix("sandbox-")
        command = tuple(argv)
        if command and command[0] == NEXAU_RUNTIME_PYTHON:
            event = "task"
        elif command == ("bash", "/tmp/qea-offline-test.sh"):
            event = "verifier"
        elif command and command[0] == "python3":
            event = "artifact-integrity"
        else:
            event = "setup"
        self.events.append(
            (f"run:{role}:{event}", command, dict(environment), timeout_seconds)
        )
        self._fail(event)
        if event == "task" and self.task_timed_out:
            return SandboxCommandResult(124, "partial", "timeout", True)
        if event == "task" and self.failure == "task-exit":
            return SandboxCommandResult(7, "", "failed", False)
        return SandboxCommandResult(0, "3 passed", "", False)

    def kill(self, native_id):
        self.events.append(f"kill:{native_id}")
        self._fail("cleanup")
        return KillResult(native_id=native_id, outcome="killed")


def _roots(tmp_path):
    public_root = tmp_path / "public"
    public_task = public_root / "tasks" / "fixture-task"
    (public_task / "environment" / "data").mkdir(parents=True)
    (public_task / "instruction.md").write_text("Create answer.txt.\n")
    (public_task / "task.toml").write_text("[agent]\ntimeout_sec=90\n")
    (public_task / "environment" / "Dockerfile").write_text("FROM scratch\n")
    (public_task / "environment" / "data" / "input.csv").write_text("x\n1\n")

    trusted_root = tmp_path / "trusted"
    tests = trusted_root / "tasks" / "fixture-task" / "tests"
    tests.mkdir(parents=True)
    (tests / "test.sh").write_text(
        "#!/bin/bash\n"
        "curl -LsSf https://astral.sh/uv/0.9.5/install.sh | sh\n"
        "source $HOME/.local/bin/env\n"
        "pytest /tests/test_outputs.py\n"
        "echo 1 > /logs/verifier/reward.txt\n"
    )
    (tests / "test_outputs.py").write_text("def test_output(): pass\n")
    solution = trusted_root / "tasks" / "fixture-task" / "solution"
    solution.mkdir()
    (solution / "solve.sh").write_text("echo forbidden\n")
    return public_root, trusted_root


def _worker(tmp_path):
    worker = tmp_path / "worker"
    worker.mkdir()
    (worker / "agent.yaml").write_text("name: worker\n")
    (worker / "systemprompt.md").write_text("Solve the task.\n")
    return worker


def _task():
    return SimpleNamespace(
        task_id="fixture-task",
        domain="risk",
        agent_timeout_seconds=90,
        verifier_timeout_seconds=30,
    )


def _attempt():
    return TaskAttempt.create(
        run_id="run-001",
        benchmark_commit="0" * 40,
        task_id="fixture-task",
        split="optimize",
        checkpoint="seed",
        worker_digest="a" * 64,
    )


def _resources(timeout_seconds=120, *, verifier=False):
    from qea.executors.sandbox_nexau import SandboxResourceContract

    writable_tmpfs_mb = {
        "/tmp": 256,
        "/qea": 512,
        "/app": 1024,
        "/tests": 64,
        "/logs": 64,
    }
    if verifier:
        writable_tmpfs_mb.update(
            {
                "/opt/qea/uv-cache": 256,
                "/opt/qea/uv-tools": 64,
            }
        )
    return SandboxResourceContract(
        cpu_count=2,
        memory_mb=4096,
        pids_limit=256,
        timeout_seconds=timeout_seconds,
        writable_tmpfs_mb=writable_tmpfs_mb,
    )


def _executor(tmp_path, backend):
    from qea.executors.sandbox_nexau import SandboxNexAUExecutor

    public_root, _ = _roots(tmp_path)
    lifecycle_root = tmp_path / "lifecycles"
    backend.lifecycle_root = lifecycle_root
    return SandboxNexAUExecutor(
        backend=backend,
        lifecycle_root=lifecycle_root,
        worker_image_ref="sha256:" + "a" * 64,
        public_task_root=public_root,
        resource_contract=_resources(),
        worker_network_name="qea-run-001-internal",
        proxy_base_url="http://qea-model-proxy:8080/v1",
        model_name="fixture-model",
    )


def test_worker_uses_public_bundle_placeholder_and_persist_before_start(tmp_path):
    backend = FakeBackend()
    executor = _executor(tmp_path, backend)

    execution = executor.execute(
        attempt=_attempt(),
        task=_task(),
        worker_dir=_worker(tmp_path),
        run_dir=tmp_path / "run",
        model_env={},
    )

    spec = backend.specs[0]
    assert spec.role == "worker"
    assert spec.network_policy == "worker-proxy-only"
    assert spec.network_scope is None
    assert dict(spec.environment) == {
        "LLM_API_KEY": "qea-proxy-placeholder",
        "LLM_BASE_URL": "http://qea-model-proxy:8080/v1",
        "LLM_MODEL": "fixture-model",
        "SSL_CERT_FILE": "/etc/ssl/certs/ca-certificates.crt",
    }
    members = _tar_members(backend.uploads[("worker", "/qea/worker-input.tar")])
    assert members == (
        "task/environment/data/input.csv",
        "task/instruction.md",
        "worker/agent.yaml",
        "worker/systemprompt.md",
    )
    assert not any("tests" in member or "solution" in member for member in members)
    assert backend.events[:2] == [
        "create:worker",
        "start:worker:lifecycle=True",
    ]
    upload_index = next(
        index
        for index, event in enumerate(backend.events)
        if isinstance(event, str) and event.startswith("upload:worker")
    )
    run_index = next(
        index
        for index, event in enumerate(backend.events)
        if isinstance(event, tuple) and event[0] == "run:worker:task"
    )
    assert upload_index < run_index
    assert execution.artifacts == (
        ArtifactRecord(
            path="answer.txt",
            sha256=hashlib.sha256(b"42\n").hexdigest(),
            size_bytes=3,
        ),
    )
    assert execution.cleaned_up is True
    assert not hasattr(executor, "oracle")


def test_worker_setup_accepts_official_task_without_data_directory(tmp_path):
    backend = FakeBackend()
    executor = _executor(tmp_path, backend)
    data_root = (
        executor.public_task_root
        / "tasks"
        / "fixture-task"
        / "environment"
        / "data"
    )
    (data_root / "input.csv").unlink()
    data_root.rmdir()

    executor.execute(
        attempt=_attempt(),
        task=_task(),
        worker_dir=_worker(tmp_path),
        run_dir=tmp_path / "run",
        model_env={},
    )

    members = _tar_members(backend.uploads[("worker", "/qea/worker-input.tar")])
    assert members == (
        "task/instruction.md",
        "worker/agent.yaml",
        "worker/systemprompt.md",
    )
    setup_commands = [
        event[1]
        for event in backend.events
        if isinstance(event, tuple) and event[0] == "run:worker:setup"
    ]
    assert (
        "sh",
        "-c",
        "if [ -d /qea/task/environment/data ]; then "
        "cp -R /qea/task/environment/data/. /app/data/; fi",
    ) in setup_commands


def test_worker_uses_explicit_attempt_network_scope_when_supplied(tmp_path):
    from qea.executors.sandbox_nexau import SandboxNexAUExecutor

    backend = FakeBackend()
    public_root, _ = _roots(tmp_path)
    lifecycle_root = tmp_path / "lifecycles"
    backend.lifecycle_root = lifecycle_root
    attempt = _attempt()
    executor = SandboxNexAUExecutor(
        backend=backend,
        lifecycle_root=lifecycle_root,
        worker_image_ref="sha256:" + "a" * 64,
        public_task_root=public_root,
        resource_contract=_resources(),
        worker_network_name="qea-run-001-attempt-network",
        network_scope=attempt.attempt_id,
        proxy_base_url="http://qea-model-proxy:8080/v1",
        model_name="fixture-model",
    )

    executor.execute(
        attempt=attempt,
        task=_task(),
        worker_dir=_worker(tmp_path),
        run_dir=tmp_path / "run",
        model_env={},
    )

    assert backend.specs[0].network_scope == attempt.attempt_id


def test_worker_refuses_real_model_credentials(tmp_path):
    from qea.executors.sandbox_nexau import SandboxInfrastructureError

    executor = _executor(tmp_path, FakeBackend())
    with pytest.raises(SandboxInfrastructureError, match="public proxy environment"):
        executor.execute(
            attempt=_attempt(),
            task=_task(),
            worker_dir=_worker(tmp_path),
            run_dir=tmp_path / "run",
            model_env={"LLM_API_KEY": "real-secret"},
        )


def test_only_task_command_timeout_maps_to_existing_official_zero_path(tmp_path):
    from qea.executors.e2b_nexau import E2BWorkerTimeout
    from qea.executors.execution_record import WorkerBehaviorTimeout
    from qea.executors.sandbox_nexau import SandboxWorkerTimeout
    from qea.loop_benchmark import QFBenchE2BEvaluator, QFBenchSandboxEvaluator

    backend = FakeBackend(task_timed_out=True)
    executor = _executor(tmp_path, backend)

    class NeverVerifier:
        def verify(self, **kwargs):
            raise AssertionError("timeout must not invoke verifier")

    evaluator = QFBenchE2BEvaluator(
        benchmark_commit="0" * 40,
        run_id="run-001",
        executor=executor,
        verifier=NeverVerifier(),
        model_env={},
        max_workers=1,
    )
    assert evaluator.worker_concurrency == 1
    assert evaluator.verifier_concurrency == 3
    summary = evaluator.evaluate(
        worker_dir=_worker(tmp_path),
        tasks=(_task(),),
        split="optimize",
        checkpoint="seed",
        run_dir=tmp_path / "run",
    )
    assert issubclass(SandboxWorkerTimeout, E2BWorkerTimeout)
    assert issubclass(SandboxWorkerTimeout, WorkerBehaviorTimeout)
    assert QFBenchE2BEvaluator is QFBenchSandboxEvaluator
    assert summary.scores[0].reward == 0.0
    assert summary.scores[0].diagnostic_tags == ("timeout",)


@pytest.mark.parametrize(
    ("failure", "phase"),
    [
        ("create", "worker.create"),
        ("start", "worker.start"),
        ("upload", "worker.upload"),
        ("task-exit", "worker.command"),
        ("cleanup", "worker.cleanup"),
    ],
)
def test_worker_failures_remain_typed_infrastructure_errors(tmp_path, failure, phase):
    from qea.executors.sandbox_nexau import SandboxInfrastructureError

    backend = FakeBackend(failure=failure)
    executor = _executor(tmp_path, backend)
    with pytest.raises(SandboxInfrastructureError) as raised:
        executor.execute(
            attempt=_attempt(),
            task=_task(),
            worker_dir=_worker(tmp_path),
            run_dir=tmp_path / "run",
            model_env={},
        )
    assert raised.value.phase == phase


def test_verifier_is_independent_offline_and_rehashes_artifacts(tmp_path):
    from qea.executors.sandbox_nexau import SandboxQFBenchVerifier

    worker_backend = FakeBackend()
    executor = _executor(tmp_path, worker_backend)
    task = _task()
    attempt = _attempt()
    execution = executor.execute(
        attempt=attempt,
        task=task,
        worker_dir=_worker(tmp_path),
        run_dir=tmp_path / "run",
        model_env={},
    )

    _, trusted_root = _roots(tmp_path / "verifier-roots")
    verifier_backend = FakeBackend()
    lifecycle_root = tmp_path / "verifier-lifecycles"
    verifier_backend.lifecycle_root = lifecycle_root
    verifier = SandboxQFBenchVerifier(
        backend=verifier_backend,
        lifecycle_root=lifecycle_root,
        verifier_image_ref="sha256:" + "b" * 64,
        trusted_task_root=trusted_root,
        resource_contract=_resources(verifier=True),
    )
    score = verifier.verify(
        attempt=attempt,
        task=task,
        execution=execution,
        run_dir=tmp_path / "run",
    )

    spec = verifier_backend.specs[0]
    assert spec.role == "verifier"
    assert spec.network_policy == "none"
    assert dict(spec.environment) == {}
    assert spec.executable_tmpfs_paths == frozenset(
        {"/opt/qea/uv-cache", "/opt/qea/uv-tools"}
    )
    assert dict(spec.writable_tmpfs_mb) == {
        "/tmp": 256,
        "/qea": 512,
        "/app": 1024,
        "/tests": 64,
        "/logs": 64,
        "/opt/qea/uv-cache": 256,
        "/opt/qea/uv-tools": 64,
    }
    members = _tar_members(
        verifier_backend.uploads[("verifier", "/qea/verifier-input.tar")]
    )
    assert members == (
        "artifacts/answer.txt",
        "tests/test.sh",
        "tests/test_outputs.py",
    )
    assert not any("solution" in member or "instruction" in member for member in members)
    assert any(
        isinstance(event, tuple) and event[0] == "run:verifier:artifact-integrity"
        for event in verifier_backend.events
    )
    cache_copy = (
        "cp",
        "-a",
        "/opt/qea/uv-cache-seed/.",
        "/opt/qea/uv-cache/",
    )
    cache_copy_index = next(
        index
        for index, event in enumerate(verifier_backend.events)
        if isinstance(event, tuple) and event[1] == cache_copy
    )
    verifier_index, verifier_event = next(
        (index, event)
        for index, event in enumerate(verifier_backend.events)
        if isinstance(event, tuple) and event[0] == "run:verifier:verifier"
    )
    assert cache_copy_index < verifier_index
    assert verifier_event[2] == {
        "TMPDIR": "/opt/qea/uv-tools",
        "UV_OFFLINE": "1",
        "UV_CACHE_DIR": "/opt/qea/uv-cache",
        "UV_TOOL_DIR": "/opt/qea/uv-tools",
        "UV_TOOL_BIN_DIR": "/opt/qea/uv-bin",
        "PATH": "/opt/qea/uv-bin:/root/.local/bin:/usr/local/bin:/usr/bin:/bin",
    }
    assert score.reward == 1.0
    assert score.tests_passed == 3
    evidence = json.loads(
        (
            tmp_path
            / "run"
            / "attempts"
            / attempt.attempt_id
            / "verifier"
            / "verifier-evidence.json"
        ).read_text()
    )
    assert evidence["network_policy"] == "none"
    assert evidence["artifact_records"] == [
        {
            "path": "answer.txt",
            "sha256": hashlib.sha256(b"42\n").hexdigest(),
            "size_bytes": 3,
        }
    ]
    assert evidence["artifact_integrity_verified"] is True


@pytest.mark.parametrize(
    ("failure", "phase"),
    [
        ("upload", "verifier.upload"),
        ("verifier", "verifier.command"),
        ("cleanup", "verifier.cleanup"),
    ],
)
def test_verifier_failures_remain_infrastructure_errors(tmp_path, failure, phase):
    from qea.executors.sandbox_nexau import (
        SandboxInfrastructureError,
        SandboxQFBenchVerifier,
    )

    worker_backend = FakeBackend()
    executor = _executor(tmp_path, worker_backend)
    task = _task()
    attempt = _attempt()
    execution = executor.execute(
        attempt=attempt,
        task=task,
        worker_dir=_worker(tmp_path),
        run_dir=tmp_path / "run",
        model_env={},
    )
    _, trusted_root = _roots(tmp_path / "trusted-roots")
    backend = FakeBackend(failure=failure)
    lifecycle_root = tmp_path / "verifier-lifecycles"
    backend.lifecycle_root = lifecycle_root
    verifier = SandboxQFBenchVerifier(
        backend=backend,
        lifecycle_root=lifecycle_root,
        verifier_image_ref="sha256:" + "b" * 64,
        trusted_task_root=trusted_root,
        resource_contract=_resources(verifier=True),
    )
    with pytest.raises(SandboxInfrastructureError) as raised:
        verifier.verify(
            attempt=attempt,
            task=task,
            execution=execution,
            run_dir=tmp_path / "run",
        )
    assert raised.value.phase == phase


def test_verifier_rejects_read_only_uv_runtime(tmp_path):
    from qea.executors.sandbox_nexau import (
        SandboxInfrastructureError,
        SandboxQFBenchVerifier,
    )

    _, trusted_root = _roots(tmp_path / "trusted-roots")
    with pytest.raises(SandboxInfrastructureError, match="missing tmpfs mounts"):
        SandboxQFBenchVerifier(
            backend=FakeBackend(),
            lifecycle_root=tmp_path / "lifecycles",
            verifier_image_ref="sha256:" + "b" * 64,
            trusted_task_root=trusted_root,
            resource_contract=_resources(),
        )


def test_proposer_feedback_stays_on_existing_answer_free_contract():
    from qea.loop_benchmark import _answer_free_diagnosis

    score = OfficialTaskScore(
        task_id="fixture-task",
        domain="risk",
        reward=0.0,
        diagnostic_tags=("tests_failed",),
        tests_passed=2,
        tests_failed=1,
        log_uri="trusted/raw-assertion-log.json",
    )
    summary = SimpleNamespace(scores=(score,), overall=0.0)
    feedback = _answer_free_diagnosis(summary)
    encoded = json.dumps(feedback, sort_keys=True)
    assert feedback["optimize_feedback"] == [
        {
            "task_id": "fixture-task",
            "official_reward": 0.0,
            "diagnostic_tags": ["tests_failed"],
        }
    ]
    assert "raw-assertion" not in encoded
    assert "tests_passed" not in encoded
    assert '\"tests_failed\": 1' not in encoded
