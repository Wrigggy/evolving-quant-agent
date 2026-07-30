from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from pathlib import Path
from threading import Event
from types import MappingProxyType, SimpleNamespace

import pytest


COMMIT = "024921eb507fcc0c4ffe3e0a96802724be1ae84a"
UPSTREAM_BASE = "docker.io/library/python@sha256:" + "a" * 64
BASE_IMAGE = "sha256:" + "b" * 64
def _digest(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _manifest(
    root: Path,
    *,
    role: str,
    image_digit: str,
    task_id: str | None = None,
    base_image_ref: str = BASE_IMAGE,
    cpu_count: int = 2,
    memory_mb: int = 4096,
) -> Path:
    lock = f"{role}-lock\n".encode()
    dockerfile = f"FROM {base_image_ref}\n".encode()
    context = [{
        "path": "Dockerfile",
        "mode": "0o644",
        "sha256": hashlib.sha256(dockerfile).hexdigest(),
        "size_bytes": len(dockerfile),
    }]
    plan = {
        "role": role,
        "task_id": task_id,
        "benchmark_commit": COMMIT,
        "base_image_ref": base_image_ref,
        "source_manifest_sha256": "c" * 64,
        "verifier_test_script_sha256": "d" * 64 if role == "verifier" else None,
        "context_files": context,
        "cpu_count": cpu_count,
        "memory_mb": memory_mb,
        "build_timeout_seconds": 600,
        "build_network": "default",
    }
    payload = {
        "schema_version": 1,
        **plan,
        "dockerfile_sha256": hashlib.sha256(dockerfile).hexdigest(),
        "plan_identity_sha256": _digest(plan),
        "identity_kind": "measured-result",
        "image_id": "sha256:" + image_digit * 64,
        "repo_digests": [],
        "build_tag": f"fixture-{role}",
        "local_base_tag": None,
        "local_base_image_id": None,
        "docker_version": "29.4.1",
        "docker_security_options": ["name=rootless"],
        "dependency_lock_sha256": hashlib.sha256(lock).hexdigest(),
        "built_at": "2026-07-30T10:00:00+00:00",
    }
    payload["result_identity_sha256"] = _digest({
        "plan_identity_sha256": payload["plan_identity_sha256"],
        "image_id": payload["image_id"],
        "dependency_lock_sha256": payload["dependency_lock_sha256"],
        "docker_version": payload["docker_version"],
        "docker_security_options": payload["docker_security_options"],
    })
    payload["identity_sha256"] = payload["result_identity_sha256"]
    publication = root / str(payload["result_identity_sha256"])
    (publication / "context").mkdir(parents=True)
    (publication / "context" / "Dockerfile").write_bytes(dockerfile)
    (publication / "dependency-lock.txt").write_bytes(lock)
    path = publication / "MANIFEST.json"
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")
    return path


def _image_set(tmp_path: Path) -> tuple[Path, tuple[Path, ...]]:
    from qea.rootless_image_set import RootlessImageSet

    manifests = (
        _manifest(
            tmp_path / "base",
            role="base",
            image_digit="b",
            base_image_ref=UPSTREAM_BASE,
        ),
        _manifest(
            tmp_path / "proxy",
            role="proxy",
            image_digit="2",
            cpu_count=1,
            memory_mb=512,
        ),
        _manifest(tmp_path / "evolver", role="evolver", image_digit="3"),
        _manifest(
            tmp_path / "task-a-worker",
            role="worker",
            task_id="task-a",
            image_digit="4",
            cpu_count=3,
            memory_mb=6144,
        ),
        _manifest(
            tmp_path / "task-a-verifier",
            role="verifier",
            task_id="task-a",
            image_digit="5",
            cpu_count=2,
            memory_mb=4096,
        ),
    )
    index = tmp_path / "image-set.json"
    RootlessImageSet.from_manifest_paths(
        benchmark_commit=COMMIT,
        task_ids=("task-a",),
        manifest_paths=manifests,
    ).write(index)
    return index, manifests


def test_rootless_runtime_catalog_module_exposes_immutable_schema() -> None:
    from qea.rootless_runtime import (
        RootlessRuntimeCatalog,
        RootlessTaskRuntime,
        load_rootless_runtime_catalog,
    )

    assert RootlessTaskRuntime.__dataclass_params__.frozen is True
    assert RootlessRuntimeCatalog.__dataclass_params__.frozen is True
    assert callable(load_rootless_runtime_catalog)


def test_catalog_loads_one_explicit_image_set_as_sorted_read_only_runtime(
    tmp_path,
) -> None:
    from qea.rootless_image_set import RootlessImageSet
    from qea.rootless_runtime import load_rootless_runtime_catalog

    index, _ = _image_set(tmp_path)
    selected = RootlessImageSet.load(index)
    catalog = load_rootless_runtime_catalog(
        index,
        ("task-a",),
        benchmark_commit=COMMIT,
    )

    assert catalog.image_set_identity_sha256 == selected.identity_sha256
    assert catalog.identity_sha256 != catalog.image_set_identity_sha256
    assert len(catalog.identity_sha256) == 64
    assert catalog.base_image_ref == BASE_IMAGE
    assert catalog.proxy_image_ref == "sha256:" + "2" * 64
    assert catalog.evolver_image_ref == "sha256:" + "3" * 64
    assert type(catalog.tasks) is MappingProxyType
    assert tuple(catalog.tasks) == ("task-a",)
    runtime = catalog.tasks["task-a"]
    assert runtime.worker_image_ref == "sha256:" + "4" * 64
    assert runtime.verifier_image_ref == "sha256:" + "5" * 64
    assert (runtime.worker_resources.cpu_count, runtime.worker_resources.memory_mb) == (
        3,
        6144,
    )
    assert (
        runtime.verifier_resources.cpu_count,
        runtime.verifier_resources.memory_mb,
    ) == (2, 4096)
    assert set(runtime.worker_resources.writable_tmpfs_mb) == {
        "/tmp",
        "/qea",
        "/app",
    }
    assert set(runtime.verifier_resources.writable_tmpfs_mb) == {
        "/tmp",
        "/qea",
        "/app",
        "/tests",
        "/logs",
        "/opt/qea/uv-cache",
        "/opt/qea/uv-tools",
    }
    assert len(runtime.identity_sha256) == 64
    with pytest.raises(TypeError):
        catalog.tasks["task-b"] = runtime


@pytest.mark.parametrize(
    ("task_ids", "benchmark_commit", "message"),
    [
        (("task-a", "task-a"), COMMIT, "task panel"),
        (("task-b",), COMMIT, "task panel"),
        (("task-a",), "f" * 40, "benchmark commit"),
    ],
)
def test_catalog_rejects_requested_panel_or_commit_drift(
    tmp_path,
    task_ids,
    benchmark_commit,
    message,
) -> None:
    from qea.rootless_runtime import (
        RootlessRuntimeError,
        load_rootless_runtime_catalog,
    )

    index, _ = _image_set(tmp_path)
    with pytest.raises(RootlessRuntimeError, match=message):
        load_rootless_runtime_catalog(
            index,
            task_ids,
            benchmark_commit=benchmark_commit,
        )


def test_catalog_revalidates_referenced_manifest_and_dependency_lock(tmp_path) -> None:
    from qea.rootless_runtime import (
        RootlessRuntimeError,
        load_rootless_runtime_catalog,
    )

    index, manifests = _image_set(tmp_path)
    verifier = next(
        path
        for path in manifests
        if json.loads(path.read_text())["role"] == "verifier"
    )
    verifier.with_name("dependency-lock.txt").write_text("drifted-lock\n")

    with pytest.raises(RootlessRuntimeError, match="dependency lock"):
        load_rootless_runtime_catalog(
            index,
            ("task-a",),
            benchmark_commit=COMMIT,
        )


class _Lease:
    def __init__(self, pool):
        self.pool = pool
        self.events = pool.events

    def __enter__(self):
        self.pool.active += 1
        self.events.append("lease:entered")
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.events.append("lease:released")
        self.pool.active -= 1


class _Pool:
    def __init__(self, events):
        self.events = events
        self.requests = []
        self.active = 0

    def acquire(self, key, request, *, timeout_seconds):
        self.events.append("lease:acquired")
        self.requests.append((key, request, timeout_seconds))
        return _Lease(self)


class _ProxyManager:
    def __init__(
        self,
        backend,
        events,
        resources,
        *,
        tamper=None,
        failure=None,
    ):
        self.backend = backend
        self.events = events
        self.tamper = tamper
        self.failure = failure
        self.opens = 0
        self.config = SimpleNamespace(
            resource_contract=resources,
            allowed_model="example/model",
            image_ref="sha256:" + "2" * 64,
            upstream_base_url="https://provider.example/v1",
            allowed_path_prefix="/v1",
            listen_port=8080,
            timeout_seconds=120,
            expect_request=True,
        )

    @contextmanager
    def open(self, **kwargs):
        from qea.model_proxy import (
            build_model_proxy_sandbox_plan,
            model_proxy_plan_identity,
        )
        from qea.sandbox_backend import SandboxHandle
        from qea.sandbox_lifecycle import (
            create_lifecycle,
            mark_cleaned,
            mark_finished,
            mark_started,
        )

        self.opens += 1
        self.events.append(("proxy:open", kwargs))
        if self.failure == "open":
            raise RuntimeError("synthetic proxy open failure")
        resources = self.config.resource_contract
        plan = build_model_proxy_sandbox_plan(
            run_id=kwargs["run_id"],
            attempt_id=kwargs["attempt_id"],
            task_id=kwargs["task_id"],
            image_ref=self.config.image_ref,
            upstream_base_url=self.config.upstream_base_url,
            allowed_path_prefix=self.config.allowed_path_prefix,
            listen_port=self.config.listen_port,
            cpu_count=resources.cpu_count,
            memory_mb=resources.memory_mb,
            pids_limit=resources.pids_limit,
            timeout_seconds=resources.timeout_seconds,
            network_scope=kwargs["attempt_id"],
            allowed_model=self.config.allowed_model,
            audit_path="/run/qea-secrets/proxy-audit.jsonl",
            writable_tmpfs_mb=resources.writable_tmpfs_mb,
        )
        public_plan, public_config, attempt_identity = model_proxy_plan_identity(plan)
        lifecycle_uri = (
            kwargs["run_dir"]
            / "lifecycles"
            / kwargs["attempt_id"]
            / "proxy-sandbox-lifecycle-v2.json"
        )
        handle = SandboxHandle(
            backend="fake",
            native_id="proxy-1",
            immutable_image_ref=plan.spec.image_ref,
            spec_sha256=plan.spec.spec_sha256,
        )
        create_lifecycle(
            lifecycle_uri,
            handle=handle,
            spec=plan.spec,
            attempt_identity_sha256=attempt_identity,
        )
        mark_started(lifecycle_uri)
        values = {
            "base_url": "http://qea-model-proxy:8080/v1",
            "network_scope": kwargs["attempt_id"],
            "network_name": "qea-run-001-attempt-network",
            "network_id": "network-1",
            "allowed_model": "example/model",
            "immutable_image_ref": handle.immutable_image_ref,
            "spec_sha256": handle.spec_sha256,
            "public_plan_sha256": public_plan,
            "public_config_sha256": public_config,
            "attempt_identity_sha256": attempt_identity,
            "native_id": handle.native_id,
            "lifecycle_uri": lifecycle_uri,
        }
        if self.tamper == "image":
            values["immutable_image_ref"] = "sha256:" + "9" * 64
        elif self.tamper == "spec":
            values["spec_sha256"] = "9" * 64
        elif self.tamper == "digest":
            values["attempt_identity_sha256"] = "9" * 64
        try:
            yield SimpleNamespace(**values)
        finally:
            mark_finished(lifecycle_uri)
            mark_cleaned(
                lifecycle_uri,
                cleanup_method="exact-id",
                cleanup_result="killed",
            )
            self.events.append("proxy:closed")
            if self.failure == "close":
                raise RuntimeError("synthetic proxy close failure")


def _sandbox_resources(*, verifier=False, proxy=False):
    from qea.executors.sandbox_runtime import SandboxResourceContract

    if proxy:
        return SandboxResourceContract(
            cpu_count=1,
            memory_mb=512,
            pids_limit=64,
            timeout_seconds=300,
            writable_tmpfs_mb={"/tmp": 64, "/run/qea-secrets": 8},
        )
    tmpfs = {"/tmp": 256, "/qea": 512, "/app": 2_048}
    if verifier:
        tmpfs.update(
            {
                "/tests": 128,
                "/logs": 128,
                "/opt/qea/uv-cache": 256,
                "/opt/qea/uv-tools": 64,
            }
        )
    return SandboxResourceContract(
        cpu_count=2 if verifier else 3,
        memory_mb=4096 if verifier else 6144,
        pids_limit=256,
        timeout_seconds=5400,
        writable_tmpfs_mb=tmpfs,
    )


def _catalog(task_ids=("task-a",)):
    from qea.rootless_runtime import RootlessRuntimeCatalog, RootlessTaskRuntime

    tasks = {
        task_id: RootlessTaskRuntime(
            task_id=task_id,
            worker_image_ref="sha256:" + "4" * 64,
            verifier_image_ref="sha256:" + "5" * 64,
            worker_resources=_sandbox_resources(),
            verifier_resources=_sandbox_resources(verifier=True),
            identity_sha256="6" * 64,
        )
        for task_id in task_ids
    }
    return RootlessRuntimeCatalog(
        benchmark_commit=COMMIT,
        base_image_ref=BASE_IMAGE,
        proxy_image_ref="sha256:" + "2" * 64,
        evolver_image_ref="sha256:" + "3" * 64,
        tasks=MappingProxyType(tasks),
        image_set_identity_sha256="7" * 64,
        identity_sha256="8" * 64,
    )


def _attempt():
    from qea.evaluation import TaskAttempt

    return TaskAttempt.create(
        run_id="run-001",
        benchmark_commit=COMMIT,
        task_id="task-a",
        split="optimize",
        checkpoint="seed",
        worker_digest="a" * 64,
    )


def _seed_worker(root: Path) -> Path:
    worker = root / "worker-source"
    worker.mkdir()
    (worker / "agent.yaml").write_text("name: qf-worker\n")
    (worker / "systemprompt.md").write_text("Solve the task.\n")
    return worker


def _worker_execution(attempt, run_dir: Path, task):
    from qea.evaluation import ArtifactRecord
    from qea.executors.execution_record import WorkerExecution

    attempt_dir = run_dir / "attempts" / attempt.attempt_id
    artifact_dir = attempt_dir / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact = artifact_dir / "answer.txt"
    artifact.write_text(f"{task.task_id}\n")
    trace = attempt_dir / "raw-trace.jsonl"
    log = attempt_dir / "worker-command.json"
    final = attempt_dir / "final.txt"
    trace.write_text("{}\n")
    log.write_text("{}\n")
    final.write_text("done\n")
    return WorkerExecution(
        attempt_id=attempt.attempt_id,
        artifact_dir=artifact_dir,
        artifacts=(ArtifactRecord.from_file(artifact, root=artifact_dir),),
        trace_uri=str(trace),
        log_uri=str(log),
        final_text_uri=str(final),
        summary={"files": 1},
        sandbox_id=f"worker-{task.task_id}",
        cleaned_up=True,
    )


def test_worker_router_atomically_leases_proxy_and_exact_task_runtime(
    tmp_path,
    monkeypatch,
) -> None:
    import qea.rootless_runtime as runtime_module
    from qea.evaluation import ArtifactRecord
    from qea.executors.execution_record import WorkerExecution
    from qea.resource_lease import ResourceRequest
    from qea.rootless_runtime import RootlessWorkerRouter

    events = []
    backend = object()
    pool = _Pool(events)
    proxy = _ProxyManager(backend, events, _sandbox_resources(proxy=True))
    execution = WorkerExecution(
        attempt_id=_attempt().attempt_id,
        artifact_dir=tmp_path / "artifacts",
        artifacts=(ArtifactRecord("answer.txt", "f" * 64, 3),),
        trace_uri="trace",
        log_uri="log",
        final_text_uri="final",
        summary={},
        sandbox_id="worker-1",
        cleaned_up=True,
    )

    class FakeExecutor:
        def __init__(self, **kwargs):
            events.append(("executor:init", kwargs))

        def execute(self, **kwargs):
            events.append(("executor:execute", kwargs))
            return execution

    monkeypatch.setattr(runtime_module, "SandboxNexAUExecutor", FakeExecutor)
    router = RootlessWorkerRouter(
        catalog=_catalog(),
        backend=backend,
        lifecycle_root=tmp_path / "lifecycles",
        public_task_root=tmp_path / "public",
        proxy_manager=proxy,
        resource_pool=pool,
        model_name="example/model",
    )
    attempt = _attempt()
    task = SimpleNamespace(task_id="task-a")
    result = router.execute(
        attempt=attempt,
        task=task,
        worker_dir=tmp_path / "worker",
        run_dir=tmp_path / "run",
        model_env={},
    )

    assert result is execution
    assert pool.requests == [
        (
            f"worker:{attempt.attempt_id}",
            ResourceRequest(
                cpu_count=4,
                memory_mb=6_656,
                pids_limit=320,
                tmpfs_mb=2_888,
                sandboxes=2,
            ),
            120.0,
        )
    ]
    proxy_event = next(
        event
        for event in events
        if isinstance(event, tuple) and event[0] == "proxy:open"
    )
    assert proxy_event[1] == {
        "run_id": "run-001",
        "attempt_id": attempt.attempt_id,
        "task_id": "task-a",
        "caller_role": "worker",
        "run_dir": (tmp_path / "run").resolve(),
    }
    init = next(
        event[1]
        for event in events
        if isinstance(event, tuple) and event[0] == "executor:init"
    )
    assert init["worker_image_ref"] == "sha256:" + "4" * 64
    assert init["resource_contract"] == _sandbox_resources()
    assert init["worker_network_name"] == "qea-run-001-attempt-network"
    assert init["network_scope"] == attempt.attempt_id
    assert init["proxy_base_url"] == "http://qea-model-proxy:8080/v1"
    assert init["model_name"] == "example/model"
    assert init["placeholder_api_key"] == "qea-proxy-placeholder"
    assert events.index("lease:entered") < events.index(proxy_event)
    assert events.index("proxy:closed") < events.index("lease:released")
    assert pool.active == 0


def test_verifier_router_leases_only_exact_offline_task_runtime(
    tmp_path,
    monkeypatch,
) -> None:
    import qea.rootless_runtime as runtime_module
    from qea.evaluation import OfficialTaskScore
    from qea.resource_lease import ResourceRequest
    from qea.rootless_runtime import RootlessVerifierRouter

    events = []
    backend = object()
    pool = _Pool(events)
    expected = OfficialTaskScore(task_id="task-a", domain="risk", reward=1.0)

    class FakeVerifier:
        def __init__(self, **kwargs):
            events.append(("verifier:init", kwargs))

        def verify(self, **kwargs):
            events.append(("verifier:verify", kwargs))
            return expected

    monkeypatch.setattr(runtime_module, "SandboxQFBenchVerifier", FakeVerifier)
    router = RootlessVerifierRouter(
        catalog=_catalog(),
        backend=backend,
        lifecycle_root=tmp_path / "lifecycles",
        trusted_task_root=tmp_path / "trusted",
        resource_pool=pool,
    )
    attempt = _attempt()
    task = SimpleNamespace(task_id="task-a")
    execution = SimpleNamespace(attempt_id=attempt.attempt_id)
    score = router.verify(
        attempt=attempt,
        task=task,
        execution=execution,
        run_dir=tmp_path / "run",
    )

    assert score is expected
    assert pool.requests == [
        (
            f"verifier:{attempt.attempt_id}",
            ResourceRequest(
                cpu_count=2,
                memory_mb=4096,
                pids_limit=256,
                tmpfs_mb=3_392,
                sandboxes=1,
            ),
            120.0,
        )
    ]
    init = next(
        event[1]
        for event in events
        if isinstance(event, tuple) and event[0] == "verifier:init"
    )
    assert init["verifier_image_ref"] == "sha256:" + "5" * 64
    assert init["resource_contract"] == _sandbox_resources(verifier=True)
    assert "proxy_manager" not in init
    assert events.index("lease:entered") < next(
        index
        for index, event in enumerate(events)
        if isinstance(event, tuple) and event[0] == "verifier:verify"
    )
    assert events[-1] == "lease:released"


def test_worker_router_rejects_proxy_image_outside_selected_catalog(tmp_path) -> None:
    from qea.rootless_runtime import RootlessRuntimeError, RootlessWorkerRouter

    events = []
    backend = object()
    proxy = _ProxyManager(backend, events, _sandbox_resources(proxy=True))
    proxy.config.image_ref = "sha256:" + "9" * 64

    with pytest.raises(RootlessRuntimeError, match="proxy image"):
        RootlessWorkerRouter(
            catalog=_catalog(),
            backend=backend,
            lifecycle_root=tmp_path / "lifecycles",
            public_task_root=tmp_path / "public",
            proxy_manager=proxy,
            resource_pool=_Pool(events),
            model_name="example/model",
        )


@pytest.mark.parametrize("tamper", ("image", "spec", "digest"))
def test_worker_router_rejects_executed_proxy_identity_before_worker_creation(
    tmp_path,
    monkeypatch,
    tamper,
) -> None:
    import qea.rootless_runtime as runtime_module
    from qea.rootless_runtime import RootlessRuntimeError, RootlessWorkerRouter

    events = []
    backend = object()
    proxy = _ProxyManager(
        backend,
        events,
        _sandbox_resources(proxy=True),
        tamper=tamper,
    )
    pool = _Pool(events)

    class RefusingExecutor:
        def __init__(self, **kwargs):
            raise AssertionError("worker executor must not be created")

    monkeypatch.setattr(runtime_module, "SandboxNexAUExecutor", RefusingExecutor)
    router = RootlessWorkerRouter(
        catalog=_catalog(),
        backend=backend,
        lifecycle_root=tmp_path / "lifecycles",
        public_task_root=tmp_path / "public",
        proxy_manager=proxy,
        resource_pool=pool,
        model_name="example/model",
    )

    with pytest.raises(RootlessRuntimeError, match="proxy session identity"):
        router.execute(
            attempt=_attempt(),
            task=SimpleNamespace(task_id="task-a"),
            worker_dir=tmp_path / "worker",
            run_dir=tmp_path / "run",
            model_env={},
        )
    assert "proxy:closed" in events
    assert "lease:released" in events
    assert pool.active == 0


@pytest.mark.parametrize(
    ("failure_source", "message", "proxy_closed"),
    [
        ("proxy-open", "synthetic proxy open failure", False),
        ("executor-init", "synthetic executor init failure", True),
        ("executor-execute", "synthetic worker execute failure", True),
        ("proxy-close", "synthetic proxy close failure", True),
    ],
)
def test_worker_router_releases_combined_lease_across_failure_boundaries(
    tmp_path,
    monkeypatch,
    failure_source,
    message,
    proxy_closed,
) -> None:
    import qea.rootless_runtime as runtime_module
    from qea.rootless_runtime import RootlessWorkerRouter

    events = []
    backend = object()
    pool = _Pool(events)
    proxy_failure = {
        "proxy-open": "open",
        "proxy-close": "close",
    }.get(failure_source)
    proxy = _ProxyManager(
        backend,
        events,
        _sandbox_resources(proxy=True),
        failure=proxy_failure,
    )

    class FailingExecutor:
        def __init__(self, **kwargs):
            events.append("executor:created")
            if failure_source == "executor-init":
                raise RuntimeError("synthetic executor init failure")

        def execute(self, **kwargs):
            events.append("executor:executed")
            if failure_source == "executor-execute":
                raise RuntimeError("synthetic worker execute failure")
            return object()

    monkeypatch.setattr(runtime_module, "SandboxNexAUExecutor", FailingExecutor)
    router = RootlessWorkerRouter(
        catalog=_catalog(),
        backend=backend,
        lifecycle_root=tmp_path / "lifecycles",
        public_task_root=tmp_path / "public",
        proxy_manager=proxy,
        resource_pool=pool,
        model_name="example/model",
    )

    with pytest.raises(RuntimeError, match=message):
        router.execute(
            attempt=_attempt(),
            task=SimpleNamespace(task_id="task-a"),
            worker_dir=tmp_path / "worker",
            run_dir=tmp_path / "run",
            model_env={},
        )

    assert pool.active == 0
    assert events[-1] == "lease:released"
    assert ("proxy:closed" in events) is proxy_closed


def test_actual_rootless_routers_resume_completed_score_without_acquisition(
    tmp_path,
    monkeypatch,
) -> None:
    import qea.rootless_runtime as runtime_module
    from qea.evaluation import OfficialTaskScore
    from qea.loop_benchmark import QFBenchSandboxEvaluator
    from qea.rootless_runtime import RootlessVerifierRouter, RootlessWorkerRouter

    events = []
    backend = object()
    pool = _Pool(events)
    proxy = _ProxyManager(backend, events, _sandbox_resources(proxy=True))
    calls = {"worker_init": 0, "worker_execute": 0, "verifier_init": 0,
             "verifier_verify": 0}

    class FakeExecutor:
        def __init__(self, **kwargs):
            calls["worker_init"] += 1

        def execute(self, *, attempt, task, run_dir, **kwargs):
            calls["worker_execute"] += 1
            return _worker_execution(attempt, run_dir, task)

    class FakeVerifier:
        def __init__(self, **kwargs):
            calls["verifier_init"] += 1

        def verify(self, *, task, **kwargs):
            calls["verifier_verify"] += 1
            return OfficialTaskScore(
                task_id=task.task_id,
                domain=task.domain,
                reward=0.75,
            )

    monkeypatch.setattr(runtime_module, "SandboxNexAUExecutor", FakeExecutor)
    monkeypatch.setattr(runtime_module, "SandboxQFBenchVerifier", FakeVerifier)
    worker_router = RootlessWorkerRouter(
        catalog=_catalog(),
        backend=backend,
        lifecycle_root=tmp_path / "lifecycles",
        public_task_root=tmp_path / "public",
        proxy_manager=proxy,
        resource_pool=pool,
        model_name="example/model",
    )
    verifier_router = RootlessVerifierRouter(
        catalog=_catalog(),
        backend=backend,
        lifecycle_root=tmp_path / "lifecycles",
        trusted_task_root=tmp_path / "trusted",
        resource_pool=pool,
    )
    evaluator = QFBenchSandboxEvaluator(
        benchmark_commit=COMMIT,
        run_id="rootless-score-resume",
        executor=worker_router,
        verifier=verifier_router,
        model_env={},
        worker_concurrency=1,
        verifier_concurrency=1,
    )
    task = SimpleNamespace(task_id="task-a", domain="risk", lineage="a")
    worker = _seed_worker(tmp_path)
    run_dir = tmp_path / "run"

    first = evaluator.evaluate(
        worker_dir=worker,
        tasks=(task,),
        split="optimize",
        checkpoint="seed-optimize",
        run_dir=run_dir,
    )
    acquisitions = tuple(pool.requests)
    opens = proxy.opens
    call_counts = dict(calls)
    second = evaluator.evaluate(
        worker_dir=worker,
        tasks=(task,),
        split="optimize",
        checkpoint="seed-optimize",
        run_dir=run_dir,
    )

    assert first == second
    assert tuple(pool.requests) == acquisitions
    assert proxy.opens == opens == 1
    assert calls == call_counts == {
        "worker_init": 1,
        "worker_execute": 1,
        "verifier_init": 1,
        "verifier_verify": 1,
    }
    assert pool.active == 0


def test_actual_rootless_routers_resume_worker_execution_without_worker_acquisition(
    tmp_path,
    monkeypatch,
) -> None:
    import qea.rootless_runtime as runtime_module
    from qea.evaluation import OfficialTaskScore
    from qea.loop_benchmark import QFBenchSandboxEvaluator
    from qea.rootless_runtime import RootlessVerifierRouter, RootlessWorkerRouter

    events = []
    backend = object()
    pool = _Pool(events)
    proxy = _ProxyManager(backend, events, _sandbox_resources(proxy=True))
    worker_calls = []
    verifier_calls = []

    class FakeExecutor:
        def __init__(self, **kwargs):
            worker_calls.append("init")

        def execute(self, *, attempt, task, run_dir, **kwargs):
            worker_calls.append("execute")
            return _worker_execution(attempt, run_dir, task)

    class InterruptingVerifier:
        def __init__(self, **kwargs):
            verifier_calls.append("init")

        def verify(self, *, task, **kwargs):
            verifier_calls.append("verify")
            if verifier_calls.count("verify") == 1:
                raise RuntimeError("synthetic verifier interruption")
            return OfficialTaskScore(
                task_id=task.task_id,
                domain=task.domain,
                reward=0.5,
            )

    monkeypatch.setattr(runtime_module, "SandboxNexAUExecutor", FakeExecutor)
    monkeypatch.setattr(
        runtime_module,
        "SandboxQFBenchVerifier",
        InterruptingVerifier,
    )
    evaluator = QFBenchSandboxEvaluator(
        benchmark_commit=COMMIT,
        run_id="rootless-worker-resume",
        executor=RootlessWorkerRouter(
            catalog=_catalog(),
            backend=backend,
            lifecycle_root=tmp_path / "lifecycles",
            public_task_root=tmp_path / "public",
            proxy_manager=proxy,
            resource_pool=pool,
            model_name="example/model",
        ),
        verifier=RootlessVerifierRouter(
            catalog=_catalog(),
            backend=backend,
            lifecycle_root=tmp_path / "lifecycles",
            trusted_task_root=tmp_path / "trusted",
            resource_pool=pool,
        ),
        model_env={},
        worker_concurrency=1,
        verifier_concurrency=1,
    )
    task = SimpleNamespace(task_id="task-a", domain="risk", lineage="a")
    worker = _seed_worker(tmp_path)
    run_dir = tmp_path / "run"

    with pytest.raises(RuntimeError, match="synthetic verifier interruption"):
        evaluator.evaluate(
            worker_dir=worker,
            tasks=(task,),
            split="optimize",
            checkpoint="seed-optimize",
            run_dir=run_dir,
        )
    worker_acquisitions = tuple(
        item for item in pool.requests if item[0].startswith("worker:")
    )
    requests_before_resume = len(pool.requests)
    summary = evaluator.evaluate(
        worker_dir=worker,
        tasks=(task,),
        split="optimize",
        checkpoint="seed-optimize",
        run_dir=run_dir,
    )

    assert summary.overall == 0.5
    assert tuple(
        item for item in pool.requests if item[0].startswith("worker:")
    ) == worker_acquisitions
    assert len(pool.requests) == requests_before_resume + 1
    assert pool.requests[-1][0].startswith("verifier:")
    assert proxy.opens == 1
    assert worker_calls == ["init", "execute"]
    assert verifier_calls == ["init", "verify", "init", "verify"]
    assert pool.active == 0


@pytest.mark.parametrize("verifier_fits_with_live_worker", (True, False))
def test_actual_rootless_routers_overlap_verifier_only_with_weighted_capacity(
    tmp_path,
    monkeypatch,
    verifier_fits_with_live_worker,
) -> None:
    from concurrent.futures import ThreadPoolExecutor

    import qea.rootless_runtime as runtime_module
    from qea.evaluation import OfficialTaskScore
    from qea.loop_benchmark import QFBenchSandboxEvaluator
    from qea.resource_lease import (
        HostHealthSnapshot,
        HostHeadroomPolicy,
        HostResourceLeasePool,
        ResourceCapacity,
    )
    from qea.rootless_runtime import RootlessVerifierRouter, RootlessWorkerRouter

    worker_b_live = Event()
    release_worker_b = Event()
    verifier_requested = Event()
    verifier_started = Event()
    events = []
    backend = object()
    # Two worker+proxy requests need (8, 13312, 640, 5776, 4). The extra
    # verifier overlaps one live worker only when tmpfs capacity reaches 6280.
    capacity = ResourceCapacity(
        cpu_count=8,
        memory_mb=13_312,
        pids_limit=640,
        tmpfs_mb=6_280 if verifier_fits_with_live_worker else 5_776,
        sandboxes=4,
    )
    real_pool = HostResourceLeasePool(
        capacity,
        HostHeadroomPolicy(
            max_load_1m=100.0,
            min_available_memory_mb=0,
            min_free_disk_mb=0,
            min_free_inodes=0,
        ),
        lambda: HostHealthSnapshot(
            load_1m=0.0,
            available_memory_mb=100_000,
            free_disk_mb=100_000,
            free_inodes=100_000,
        ),
    )

    class ObservingPool:
        def acquire(self, key, request, *, timeout_seconds):
            if key.startswith("verifier:"):
                verifier_requested.set()
            return real_pool.acquire(
                key,
                request,
                timeout_seconds=timeout_seconds,
            )

    pool = ObservingPool()
    proxy = _ProxyManager(backend, events, _sandbox_resources(proxy=True))

    class BarrierExecutor:
        def __init__(self, **kwargs):
            pass

        def execute(self, *, attempt, task, run_dir, **kwargs):
            if task.task_id == "task-b":
                worker_b_live.set()
                gate = verifier_started if verifier_fits_with_live_worker else release_worker_b
                assert gate.wait(2), "capacity gate did not make progress"
            else:
                assert worker_b_live.wait(2), "second worker never held its lease"
            return _worker_execution(attempt, run_dir, task)

    class BarrierVerifier:
        def __init__(self, **kwargs):
            pass

        def verify(self, *, task, **kwargs):
            if task.task_id == "task-a":
                verifier_started.set()
            return OfficialTaskScore(
                task_id=task.task_id,
                domain=task.domain,
                reward=0.5,
            )

    monkeypatch.setattr(runtime_module, "SandboxNexAUExecutor", BarrierExecutor)
    monkeypatch.setattr(runtime_module, "SandboxQFBenchVerifier", BarrierVerifier)
    catalog = _catalog(("task-a", "task-b"))
    evaluator = QFBenchSandboxEvaluator(
        benchmark_commit=COMMIT,
        run_id=f"rootless-capacity-{verifier_fits_with_live_worker}",
        executor=RootlessWorkerRouter(
            catalog=catalog,
            backend=backend,
            lifecycle_root=tmp_path / "lifecycles",
            public_task_root=tmp_path / "public",
            proxy_manager=proxy,
            resource_pool=pool,
            model_name="example/model",
            lease_timeout_seconds=2,
        ),
        verifier=RootlessVerifierRouter(
            catalog=catalog,
            backend=backend,
            lifecycle_root=tmp_path / "lifecycles",
            trusted_task_root=tmp_path / "trusted",
            resource_pool=pool,
            lease_timeout_seconds=2,
        ),
        model_env={},
        worker_concurrency=2,
        verifier_concurrency=1,
    )
    tasks = (
        SimpleNamespace(task_id="task-a", domain="risk", lineage="a"),
        SimpleNamespace(task_id="task-b", domain="strategy", lineage="b"),
    )

    with ThreadPoolExecutor(max_workers=1) as thread:
        future = thread.submit(
            evaluator.evaluate,
            worker_dir=_seed_worker(tmp_path),
            tasks=tasks,
            split="optimize",
            checkpoint="seed-optimize",
            run_dir=tmp_path / "run",
        )
        assert verifier_requested.wait(2), "verifier never requested a lease"
        if verifier_fits_with_live_worker:
            assert verifier_started.wait(2), (
                "verifier did not overlap a live worker despite exact capacity"
            )
        else:
            assert not verifier_started.is_set()
            release_worker_b.set()
            assert verifier_started.wait(2), (
                "verifier did not start after the live worker released capacity"
            )
        summary = future.result(timeout=2)

    assert summary.overall == 0.5
    assert [score.task_id for score in summary.scores] == ["task-a", "task-b"]
    with real_pool._condition:
        assert real_pool._live == {}
        assert all(
            getattr(real_pool._available, field) == getattr(capacity, field)
            for field in (
                "cpu_count",
                "memory_mb",
                "pids_limit",
                "tmpfs_mb",
                "sandboxes",
            )
        )
