"""Immutable rootless QFBench runtime catalog and task routers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Sequence

from .evaluation import OfficialTaskScore, TaskAttempt
from .executors.execution_record import WorkerExecution
from .executors.sandbox_nexau import (
    SandboxNexAUExecutor,
    SandboxQFBenchVerifier,
)
from .executors.sandbox_proxy import SandboxProxyManager
from .executors.sandbox_runtime import PLACEHOLDER_API_KEY, SandboxResourceContract
from .resource_lease import HostResourceLeasePool, ResourceRequest
from .rootless_image_set import RootlessImageSet, RootlessImageSetError
from .sandbox_backend import SandboxBackend


DEFAULT_WORKER_PIDS_LIMIT = 256
DEFAULT_WORKER_TIMEOUT_SECONDS = 5_400
DEFAULT_WORKER_TMPFS_MB: Mapping[str, int] = MappingProxyType(
    {"/app": 2_048, "/qea": 512, "/tmp": 256}
)
DEFAULT_VERIFIER_PIDS_LIMIT = 256
DEFAULT_VERIFIER_TIMEOUT_SECONDS = 5_400
DEFAULT_VERIFIER_TMPFS_MB: Mapping[str, int] = MappingProxyType(
    {
        "/app": 2_048,
        "/logs": 128,
        "/opt/qea/uv-cache": 256,
        "/opt/qea/uv-tools": 64,
        "/qea": 512,
        "/tests": 128,
        "/tmp": 256,
    }
)


class RootlessRuntimeError(RuntimeError):
    """An explicit rootless runtime selection is invalid or inconsistent."""


def _canonical_digest(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _resource_contract(
    entry: Mapping[str, object],
    *,
    pids_limit: int,
    timeout_seconds: int,
    writable_tmpfs_mb: Mapping[str, int],
) -> SandboxResourceContract:
    declared = entry.get("resource_contract")
    if not isinstance(declared, Mapping):
        raise RootlessRuntimeError("image resource contract is unavailable")
    try:
        cpu_count = declared["cpu_count"]
        memory_mb = declared["memory_mb"]
    except KeyError as exc:
        raise RootlessRuntimeError(
            f"image resource contract omits {exc.args[0]!r}"
        ) from exc
    return SandboxResourceContract(
        cpu_count=cpu_count,
        memory_mb=memory_mb,
        pids_limit=pids_limit,
        timeout_seconds=timeout_seconds,
        writable_tmpfs_mb=writable_tmpfs_mb,
    )


def _resource_payload(contract: SandboxResourceContract) -> dict[str, object]:
    return {
        "cpu_count": contract.cpu_count,
        "memory_mb": contract.memory_mb,
        "pids_limit": contract.pids_limit,
        "timeout_seconds": contract.timeout_seconds,
        "writable_tmpfs_mb": dict(contract.writable_tmpfs_mb),
    }


def _resource_request(
    primary: SandboxResourceContract,
    secondary: SandboxResourceContract | None = None,
) -> ResourceRequest:
    resources = (primary,) if secondary is None else (primary, secondary)
    return ResourceRequest(
        cpu_count=sum(resource.cpu_count for resource in resources),
        memory_mb=sum(resource.memory_mb for resource in resources),
        pids_limit=sum(resource.pids_limit for resource in resources),
        tmpfs_mb=sum(
            sum(resource.writable_tmpfs_mb.values()) for resource in resources
        ),
        sandboxes=len(resources),
    )


@dataclass(frozen=True)
class RootlessTaskRuntime:
    """Immutable worker and verifier selection for one benchmark task."""

    task_id: str
    worker_image_ref: str
    verifier_image_ref: str
    worker_resources: SandboxResourceContract
    verifier_resources: SandboxResourceContract
    identity_sha256: str


@dataclass(frozen=True)
class RootlessRuntimeCatalog:
    """One exact rootless image selection for one task panel."""

    benchmark_commit: str
    base_image_ref: str
    evolver_image_ref: str
    proxy_image_ref: str
    tasks: Mapping[str, RootlessTaskRuntime]
    identity_sha256: str


def load_rootless_runtime_catalog(
    image_set_manifest: Path,
    task_ids: Sequence[str],
    *,
    benchmark_commit: str,
) -> RootlessRuntimeCatalog:
    """Load and revalidate one explicit image-set manifest and exact task panel.

    CPU and memory are the selected images' authenticated build declarations.
    The public role defaults fill the runtime-only PID, timeout, and tmpfs fields
    until the Task 8 assembly point replaces or validates them from its explicit
    rootless configuration; build timeouts are intentionally not reused here.
    """

    requested = tuple(task_ids)
    if (
        not requested
        or any(not isinstance(task_id, str) or not task_id for task_id in requested)
        or len(set(requested)) != len(requested)
    ):
        raise RootlessRuntimeError("requested task panel is invalid")
    try:
        image_set = RootlessImageSet.load(Path(image_set_manifest))
    except (OSError, RootlessImageSetError, TypeError, ValueError) as exc:
        raise RootlessRuntimeError(str(exc)) from exc
    if image_set.benchmark_commit != benchmark_commit:
        raise RootlessRuntimeError("image-set benchmark commit differs")
    panel = tuple(sorted(requested))
    if image_set.task_ids != panel:
        raise RootlessRuntimeError("image-set task panel differs from requested task panel")

    runtimes: dict[str, RootlessTaskRuntime] = {}
    for task in image_set.tasks:
        task_id = task["task_id"]
        worker = task["worker"]
        verifier = task["verifier"]
        if (
            not isinstance(task_id, str)
            or not isinstance(worker, Mapping)
            or not isinstance(verifier, Mapping)
        ):
            raise RootlessRuntimeError("image-set task role entry is invalid")
        worker_resources = _resource_contract(
            worker,
            pids_limit=DEFAULT_WORKER_PIDS_LIMIT,
            timeout_seconds=DEFAULT_WORKER_TIMEOUT_SECONDS,
            writable_tmpfs_mb=DEFAULT_WORKER_TMPFS_MB,
        )
        verifier_resources = _resource_contract(
            verifier,
            pids_limit=DEFAULT_VERIFIER_PIDS_LIMIT,
            timeout_seconds=DEFAULT_VERIFIER_TIMEOUT_SECONDS,
            writable_tmpfs_mb=DEFAULT_VERIFIER_TMPFS_MB,
        )
        identity = _canonical_digest(
            {
                "task_id": task_id,
                "worker_image_ref": worker["image_id"],
                "worker_manifest_identity_sha256": worker[
                    "manifest_identity_sha256"
                ],
                "worker_dependency_lock_sha256": worker[
                    "dependency_lock_sha256"
                ],
                "worker_build_resource_sha256": worker[
                    "resource_contract_sha256"
                ],
                "worker_resources": _resource_payload(worker_resources),
                "verifier_image_ref": verifier["image_id"],
                "verifier_manifest_identity_sha256": verifier[
                    "manifest_identity_sha256"
                ],
                "verifier_dependency_lock_sha256": verifier[
                    "dependency_lock_sha256"
                ],
                "verifier_build_resource_sha256": verifier[
                    "resource_contract_sha256"
                ],
                "verifier_resources": _resource_payload(verifier_resources),
            }
        )
        runtimes[task_id] = RootlessTaskRuntime(
            task_id=task_id,
            worker_image_ref=str(worker["image_id"]),
            verifier_image_ref=str(verifier["image_id"]),
            worker_resources=worker_resources,
            verifier_resources=verifier_resources,
            identity_sha256=identity,
        )

    return RootlessRuntimeCatalog(
        benchmark_commit=image_set.benchmark_commit,
        base_image_ref=str(image_set.base["image_id"]),
        evolver_image_ref=str(image_set.evolver["image_id"]),
        proxy_image_ref=str(image_set.proxy["image_id"]),
        tasks=MappingProxyType(dict(sorted(runtimes.items()))),
        identity_sha256=image_set.identity_sha256,
    )


class _RootlessTaskRouter:
    def __init__(
        self,
        *,
        catalog: RootlessRuntimeCatalog,
        backend: SandboxBackend,
        lifecycle_root: str | Path,
        resource_pool: HostResourceLeasePool,
        lease_timeout_seconds: float,
    ) -> None:
        if not isinstance(catalog, RootlessRuntimeCatalog):
            raise RootlessRuntimeError("catalog must be a RootlessRuntimeCatalog")
        if not callable(getattr(resource_pool, "acquire", None)):
            raise RootlessRuntimeError("resource pool must provide acquire")
        if (
            isinstance(lease_timeout_seconds, bool)
            or not isinstance(lease_timeout_seconds, (int, float))
            or lease_timeout_seconds < 0
        ):
            raise RootlessRuntimeError(
                "lease_timeout_seconds must be a non-negative number"
            )
        self.catalog = catalog
        self.backend = backend
        self.lifecycle_root = Path(lifecycle_root).expanduser().resolve()
        self.resource_pool = resource_pool
        self.lease_timeout_seconds = float(lease_timeout_seconds)

    def _task_runtime(self, *, attempt, task) -> RootlessTaskRuntime:
        task_id = getattr(task, "task_id", None)
        if not isinstance(task_id, str) or not task_id:
            raise RootlessRuntimeError("task has no stable task_id")
        if getattr(attempt, "task_id", None) != task_id:
            raise RootlessRuntimeError("attempt and task identities differ")
        if getattr(attempt, "benchmark_commit", None) != self.catalog.benchmark_commit:
            raise RootlessRuntimeError("attempt and catalog benchmark commits differ")
        try:
            return self.catalog.tasks[task_id]
        except KeyError as exc:
            raise RootlessRuntimeError(
                f"task {task_id!r} is outside the rootless runtime catalog"
            ) from exc


class RootlessWorkerRouter(_RootlessTaskRouter):
    """Route each QFBench worker through its exact image and scoped proxy."""

    def __init__(
        self,
        *,
        catalog: RootlessRuntimeCatalog,
        backend: SandboxBackend,
        lifecycle_root: str | Path,
        public_task_root: str | Path,
        proxy_manager: SandboxProxyManager,
        resource_pool: HostResourceLeasePool,
        model_name: str,
        lease_timeout_seconds: float = 120.0,
    ) -> None:
        super().__init__(
            catalog=catalog,
            backend=backend,
            lifecycle_root=lifecycle_root,
            resource_pool=resource_pool,
            lease_timeout_seconds=lease_timeout_seconds,
        )
        proxy_resources = getattr(
            getattr(proxy_manager, "config", None), "resource_contract", None
        )
        if getattr(proxy_manager, "backend", None) is not backend:
            raise RootlessRuntimeError("worker and proxy must use the same backend")
        if not isinstance(proxy_resources, SandboxResourceContract):
            raise RootlessRuntimeError("proxy resource contract is unavailable")
        if getattr(proxy_manager.config, "image_ref", None) != catalog.proxy_image_ref:
            raise RootlessRuntimeError(
                "proxy image differs from the selected rootless catalog"
            )
        if (
            not isinstance(model_name, str)
            or not model_name.strip()
            or getattr(proxy_manager.config, "allowed_model", None) != model_name
        ):
            raise RootlessRuntimeError("worker and proxy model identities differ")
        self.public_task_root = Path(public_task_root).expanduser().resolve()
        self.proxy_manager = proxy_manager
        self.proxy_resources = proxy_resources
        self.model_name = model_name

    def execute(
        self,
        *,
        attempt: TaskAttempt,
        task,
        worker_dir: str | Path,
        run_dir: str | Path,
        model_env: Mapping[str, str] | None = None,
    ) -> WorkerExecution:
        runtime = self._task_runtime(attempt=attempt, task=task)
        request = _resource_request(runtime.worker_resources, self.proxy_resources)
        lease = self.resource_pool.acquire(
            f"worker:{attempt.attempt_id}",
            request,
            timeout_seconds=self.lease_timeout_seconds,
        )
        run_root = Path(run_dir).expanduser().resolve()
        with lease:
            with self.proxy_manager.open(
                run_id=attempt.run_id,
                attempt_id=attempt.attempt_id,
                task_id=task.task_id,
                caller_role="worker",
                run_dir=run_root,
            ) as session:
                if (
                    session.network_scope != attempt.attempt_id
                    or session.allowed_model != self.model_name
                ):
                    raise RootlessRuntimeError(
                        "worker proxy session identity differs from the attempt"
                    )
                executor = SandboxNexAUExecutor(
                    backend=self.backend,
                    lifecycle_root=self.lifecycle_root,
                    worker_image_ref=runtime.worker_image_ref,
                    public_task_root=self.public_task_root,
                    resource_contract=runtime.worker_resources,
                    worker_network_name=session.network_name,
                    network_scope=session.network_scope,
                    proxy_base_url=session.base_url,
                    model_name=self.model_name,
                    placeholder_api_key=PLACEHOLDER_API_KEY,
                )
                return executor.execute(
                    attempt=attempt,
                    task=task,
                    worker_dir=worker_dir,
                    run_dir=run_root,
                    model_env=model_env,
                )


class RootlessVerifierRouter(_RootlessTaskRouter):
    """Route each trusted verifier through its exact networkless image."""

    def __init__(
        self,
        *,
        catalog: RootlessRuntimeCatalog,
        backend: SandboxBackend,
        lifecycle_root: str | Path,
        trusted_task_root: str | Path,
        resource_pool: HostResourceLeasePool,
        lease_timeout_seconds: float = 120.0,
    ) -> None:
        super().__init__(
            catalog=catalog,
            backend=backend,
            lifecycle_root=lifecycle_root,
            resource_pool=resource_pool,
            lease_timeout_seconds=lease_timeout_seconds,
        )
        self.trusted_task_root = Path(trusted_task_root).expanduser().resolve()

    def verify(
        self,
        *,
        attempt: TaskAttempt,
        task,
        execution: WorkerExecution,
        run_dir: str | Path,
    ) -> OfficialTaskScore:
        runtime = self._task_runtime(attempt=attempt, task=task)
        request = _resource_request(runtime.verifier_resources)
        lease = self.resource_pool.acquire(
            f"verifier:{attempt.attempt_id}",
            request,
            timeout_seconds=self.lease_timeout_seconds,
        )
        with lease:
            verifier = SandboxQFBenchVerifier(
                backend=self.backend,
                lifecycle_root=self.lifecycle_root,
                verifier_image_ref=runtime.verifier_image_ref,
                trusted_task_root=self.trusted_task_root,
                resource_contract=runtime.verifier_resources,
            )
            return verifier.verify(
                attempt=attempt,
                task=task,
                execution=execution,
                run_dir=Path(run_dir).expanduser().resolve(),
            )
