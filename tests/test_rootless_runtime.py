from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from pathlib import Path
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

    assert catalog.identity_sha256 == selected.identity_sha256
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
    def __init__(self, events):
        self.events = events

    def __enter__(self):
        self.events.append("lease:entered")
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.events.append("lease:released")


class _Pool:
    def __init__(self, events):
        self.events = events
        self.requests = []

    def acquire(self, key, request, *, timeout_seconds):
        self.events.append("lease:acquired")
        self.requests.append((key, request, timeout_seconds))
        return _Lease(self.events)


class _ProxyManager:
    def __init__(self, backend, events, resources):
        self.backend = backend
        self.events = events
        self.config = SimpleNamespace(
            resource_contract=resources,
            allowed_model="example/model",
            image_ref="sha256:" + "2" * 64,
        )

    @contextmanager
    def open(self, **kwargs):
        self.events.append(("proxy:open", kwargs))
        try:
            yield SimpleNamespace(
                base_url="http://qea-model-proxy:8080/v1",
                network_scope=kwargs["attempt_id"],
                network_name="qea-run-001-attempt-network",
                allowed_model="example/model",
            )
        finally:
            self.events.append("proxy:closed")


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


def _catalog():
    from qea.rootless_runtime import RootlessRuntimeCatalog, RootlessTaskRuntime

    runtime = RootlessTaskRuntime(
        task_id="task-a",
        worker_image_ref="sha256:" + "4" * 64,
        verifier_image_ref="sha256:" + "5" * 64,
        worker_resources=_sandbox_resources(),
        verifier_resources=_sandbox_resources(verifier=True),
        identity_sha256="6" * 64,
    )
    return RootlessRuntimeCatalog(
        benchmark_commit=COMMIT,
        base_image_ref=BASE_IMAGE,
        proxy_image_ref="sha256:" + "2" * 64,
        evolver_image_ref="sha256:" + "3" * 64,
        tasks=MappingProxyType({"task-a": runtime}),
        identity_sha256="7" * 64,
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
