"""Single trusted assembly point for the rootless QFBench full harness."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Mapping
from urllib.parse import urlsplit

from .executors.sandbox_runtime import (
    SandboxResourceContract,
    trusted_directory,
    trusted_regular_path,
)
from .resource_lease import HostHeadroomPolicy, ResourceCapacity
from .sandbox_backend import SandboxBackend

if TYPE_CHECKING:
    from .executors.sandbox_evolver import SandboxFullHarnessProposer
    from .loop_benchmark import QFBenchSandboxEvaluator


_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_MEM_AVAILABLE = re.compile(r"MemAvailable:\s+([0-9]+)\s+kB\s*\Z")
_ROLE_REQUIRED_TMPFS = {
    "evolver_resources": frozenset({"/qea", "/tmp"}),
    "proxy_resources": frozenset({"/run/qea-secrets", "/tmp"}),
    "worker_limits": frozenset({"/app", "/qea", "/tmp"}),
    "verifier_limits": frozenset(
        {
            "/app",
            "/logs",
            "/opt/qea/uv-cache",
            "/opt/qea/uv-tools",
            "/qea",
            "/tests",
            "/tmp",
        }
    ),
}


class RootlessFullHarnessError(RuntimeError):
    """The trusted rootless full-harness runtime cannot be assembled safely."""


def _canonical_digest(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _resource_payload(resource: SandboxResourceContract) -> dict[str, object]:
    return {
        "cpu_count": resource.cpu_count,
        "memory_mb": resource.memory_mb,
        "pids_limit": resource.pids_limit,
        "timeout_seconds": resource.timeout_seconds,
        "writable_tmpfs_mb": dict(resource.writable_tmpfs_mb),
    }


def _limits_payload(limits: "RoleExecutionLimits") -> dict[str, object]:
    return {
        "pids_limit": limits.pids_limit,
        "timeout_seconds": limits.timeout_seconds,
        "writable_tmpfs_mb": dict(limits.writable_tmpfs_mb),
    }


def _capacity_payload(capacity: ResourceCapacity) -> dict[str, int]:
    return {
        name: getattr(capacity, name)
        for name in ("cpu_count", "memory_mb", "pids_limit", "tmpfs_mb", "sandboxes")
    }


def _headroom_payload(policy: HostHeadroomPolicy) -> dict[str, int | float]:
    return {
        name: getattr(policy, name)
        for name in (
            "max_load_1m",
            "min_available_memory_mb",
            "min_free_disk_mb",
            "min_free_inodes",
        )
    }


def _validate_provider_route(
    upstream_base_url: str,
    allowed_path_prefix: str,
    allowed_model: str,
) -> tuple[str, str, str]:
    """Validate the fixed upstream base path and independent caller prefix."""

    from .model_proxy import (
        ModelProxyError,
        _parse_upstream,
        _validate_model,
        _validate_prefix,
    )

    if (
        not isinstance(upstream_base_url, str)
        or not upstream_base_url
        or len(upstream_base_url) > 2048
        or any(
            ord(character) < 0x21 or ord(character) > 0x7E
            for character in upstream_base_url
        )
    ):
        raise ValueError(
            "upstream_base_url must be one bounded fixed HTTPS origin and base path"
        )
    if "%" in upstream_base_url or "\\" in upstream_base_url:
        raise ValueError("upstream_base_url contains an unsafe encoded or backslash path")
    parsed = urlsplit(upstream_base_url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "upstream_base_url must be one bounded fixed HTTPS origin and base path"
        )
    path_parts = parsed.path.split("/")[1:]
    if parsed.path and (
        not parsed.path.startswith("/")
        or any(part in {"", ".", ".."} for part in path_parts)
    ):
        if parsed.path != "/":
            raise ValueError("upstream_base_url contains an unsafe base path")
    try:
        upstream = _parse_upstream(upstream_base_url)
    except ModelProxyError as exc:
        raise ValueError(f"upstream_base_url is unsafe: {exc}") from exc
    normalized_upstream = (
        f"{upstream.scheme}://{upstream.authority}{upstream.base_path}"
    )

    if (
        not isinstance(allowed_path_prefix, str)
        or not allowed_path_prefix
        or len(allowed_path_prefix) > 512
        or any(
            ord(character) < 0x21 or ord(character) > 0x7E
            for character in allowed_path_prefix
        )
        or "%" in allowed_path_prefix
        or "\\" in allowed_path_prefix
        or "?" in allowed_path_prefix
        or "#" in allowed_path_prefix
    ):
        raise ValueError("allowed path prefix must be a bounded absolute safe path")
    prefix_parts = allowed_path_prefix.rstrip("/").split("/")[1:]
    if any(part in {"", ".", ".."} for part in prefix_parts):
        raise ValueError("allowed path prefix must be a bounded absolute safe path")
    try:
        normalized_prefix = _validate_prefix(allowed_path_prefix)
        normalized_model = _validate_model(allowed_model)
    except ModelProxyError as exc:
        label = "allowed_model" if "model" in str(exc) else "allowed path prefix"
        raise ValueError(f"{label} is invalid: {exc}") from exc
    return normalized_upstream, normalized_prefix, normalized_model


def rootless_model_route_identity(
    *, upstream_base_url: str, allowed_path_prefix: str, allowed_model: str
) -> str:
    """Return the canonical answer-free identity of the fixed model route."""

    return _canonical_digest(
        {
            "schema_version": 1,
            "upstream_base_url": upstream_base_url,
            "allowed_path_prefix": allowed_path_prefix,
            "allowed_model": allowed_model,
        }
    )


class _CoordinatorLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._handle = None

    def acquire(self) -> "_CoordinatorLock":
        flags = os.O_RDWR | os.O_CREAT
        flags |= getattr(os, "O_CLOEXEC", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(self.path, flags, 0o600)
            os.fchmod(descriptor, 0o600)
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise RootlessFullHarnessError(
                    "coordinator lock must be a regular file"
                )
            handle = os.fdopen(descriptor, "r+b", buffering=0)
            descriptor = -1
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                handle.close()
                raise RootlessFullHarnessError(
                    f"coordinator lock is already held: {self.path}"
                ) from exc
            self._handle = handle
            return self
        except RootlessFullHarnessError:
            raise
        except OSError as exc:
            raise RootlessFullHarnessError(
                f"cannot acquire coordinator lock {self.path}"
            ) from exc
        finally:
            if "descriptor" in locals() and descriptor >= 0:
                os.close(descriptor)

    def close(self) -> None:
        handle = self._handle
        if handle is None:
            return
        self._handle = None
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


@dataclass(frozen=True)
class RoleExecutionLimits:
    pids_limit: int
    timeout_seconds: int
    writable_tmpfs_mb: Mapping[str, int]

    def __post_init__(self) -> None:
        for name in ("pids_limit", "timeout_seconds"):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if not isinstance(self.writable_tmpfs_mb, Mapping):
            raise ValueError("writable_tmpfs_mb must be a mapping")
        copied: dict[str, int] = {}
        for path, size_mb in self.writable_tmpfs_mb.items():
            if (
                not isinstance(path, str)
                or not path.startswith("/")
                or path == "/"
                or type(size_mb) is not int
                or size_mb <= 0
            ):
                raise ValueError(f"invalid writable tmpfs entry {path!r}")
            copied[path] = size_mb
        object.__setattr__(
            self,
            "writable_tmpfs_mb",
            MappingProxyType(dict(sorted(copied.items()))),
        )


def _existing_directory(path: Path, *, label: str) -> Path:
    unresolved = Path(path).expanduser()
    trusted_directory(unresolved, create=False, phase=f"rootless.{label}")
    try:
        metadata = unresolved.lstat()
    except OSError as exc:
        raise ValueError(f"{label} is unavailable: {unresolved}") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise ValueError(f"{label} must be a real directory")
    return unresolved.resolve()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _private_token_path(path: Path, *, expected_uid: int) -> Path:
    unresolved = Path(path).expanduser()
    trusted_regular_path(unresolved, phase="rootless.token-file")
    try:
        metadata = unresolved.lstat()
    except OSError as exc:
        raise ValueError(f"token_file is unavailable: {unresolved}") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise ValueError("token_file must be an owner-only regular file")
    if metadata.st_uid != expected_uid or metadata.st_mode & 0o077:
        raise ValueError("token_file must be an owner-only regular file")
    if not metadata.st_mode & stat.S_IRUSR:
        raise ValueError("token_file must be readable by its owner")
    return unresolved.resolve()


@dataclass(frozen=True)
class RootlessFullHarnessConfig:
    docker_host: str
    expected_uid: int
    public_root: Path
    trusted_root: Path
    token_file: Path
    upstream_base_url: str
    allowed_path_prefix: str
    allowed_model: str
    evolver_resources: SandboxResourceContract
    proxy_resources: SandboxResourceContract
    worker_limits: RoleExecutionLimits
    verifier_limits: RoleExecutionLimits
    capacity: ResourceCapacity
    headroom: HostHeadroomPolicy
    worker_concurrency: int
    verifier_concurrency: int

    def __post_init__(self) -> None:
        if type(self.expected_uid) is not int or self.expected_uid <= 0:
            raise ValueError("expected_uid must be a positive non-root integer")
        expected_socket = f"unix:///run/user/{self.expected_uid}/docker.sock"
        if self.docker_host != expected_socket:
            raise ValueError("docker_host must name the exact rootless user socket")
        public_root = _existing_directory(self.public_root, label="public_root")
        trusted_root = _existing_directory(self.trusted_root, label="trusted_root")
        trusted_metadata = trusted_root.stat()
        if (
            trusted_metadata.st_uid != self.expected_uid
            or trusted_metadata.st_mode & 0o077
        ):
            raise ValueError("trusted_root must be an owner-only directory")
        if _is_within(public_root, trusted_root) or _is_within(
            trusted_root, public_root
        ):
            raise ValueError("public_root and trusted_root must be disjoint")
        token_file = _private_token_path(
            self.token_file, expected_uid=self.expected_uid
        )
        if _is_within(token_file, public_root) or _is_within(token_file, trusted_root):
            raise ValueError("token_file must remain outside public and trusted roots")

        upstream_base_url, allowed_path_prefix, allowed_model = (
            _validate_provider_route(
                self.upstream_base_url,
                self.allowed_path_prefix,
                self.allowed_model,
            )
        )
        for name in ("evolver_resources", "proxy_resources"):
            if not isinstance(getattr(self, name), SandboxResourceContract):
                raise ValueError(f"{name} must be a SandboxResourceContract")
        for name in ("worker_limits", "verifier_limits"):
            if not isinstance(getattr(self, name), RoleExecutionLimits):
                raise ValueError(f"{name} must be a RoleExecutionLimits")
        for name, required in _ROLE_REQUIRED_TMPFS.items():
            missing = required - set(getattr(self, name).writable_tmpfs_mb)
            if missing:
                raise ValueError(
                    f"{name} is missing required tmpfs mounts: {sorted(missing)}"
                )
        if not isinstance(self.capacity, ResourceCapacity):
            raise ValueError("capacity must be a ResourceCapacity")
        if not isinstance(self.headroom, HostHeadroomPolicy):
            raise ValueError("headroom must be a HostHeadroomPolicy")
        if any(
            getattr(self.headroom, name) <= 0
            for name in (
                "max_load_1m",
                "min_available_memory_mb",
                "min_free_disk_mb",
                "min_free_inodes",
            )
        ):
            raise ValueError("rootless host headroom thresholds must be positive")
        for name in ("worker_concurrency", "verifier_concurrency"):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise ValueError(f"{name} must be a positive integer")
        object.__setattr__(self, "public_root", public_root)
        object.__setattr__(self, "trusted_root", trusted_root)
        object.__setattr__(self, "token_file", token_file)
        object.__setattr__(self, "upstream_base_url", upstream_base_url)
        object.__setattr__(self, "allowed_path_prefix", allowed_path_prefix)
        object.__setattr__(self, "allowed_model", allowed_model)


_CONFIG_KEYS = frozenset(
    {
        "schema_version",
        "docker_host",
        "expected_uid",
        "public_root",
        "trusted_root",
        "token_file",
        "upstream_base_url",
        "allowed_path_prefix",
        "allowed_model",
        "evolver_resources",
        "proxy_resources",
        "worker_limits",
        "verifier_limits",
        "capacity",
        "headroom",
        "worker_concurrency",
        "verifier_concurrency",
    }
)


def load_rootless_full_harness_config(
    path: str | Path,
) -> RootlessFullHarnessConfig:
    """Load one explicit path-only rootless coordinator configuration."""

    config_path = trusted_regular_path(
        Path(path).expanduser(), phase="rootless.config-file"
    )
    try:
        payload = json.loads(config_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("rootless config is not valid JSON") from exc
    if not isinstance(payload, dict) or set(payload) != _CONFIG_KEYS:
        raise ValueError("rootless config has unknown or missing fields")
    if payload["schema_version"] != 1:
        raise ValueError("rootless config schema_version must be 1")
    try:
        return RootlessFullHarnessConfig(
            docker_host=payload["docker_host"],
            expected_uid=payload["expected_uid"],
            public_root=Path(payload["public_root"]),
            trusted_root=Path(payload["trusted_root"]),
            token_file=Path(payload["token_file"]),
            upstream_base_url=payload["upstream_base_url"],
            allowed_path_prefix=payload["allowed_path_prefix"],
            allowed_model=payload["allowed_model"],
            evolver_resources=SandboxResourceContract(**payload["evolver_resources"]),
            proxy_resources=SandboxResourceContract(**payload["proxy_resources"]),
            worker_limits=RoleExecutionLimits(**payload["worker_limits"]),
            verifier_limits=RoleExecutionLimits(**payload["verifier_limits"]),
            capacity=ResourceCapacity(**payload["capacity"]),
            headroom=HostHeadroomPolicy(**payload["headroom"]),
            worker_concurrency=payload["worker_concurrency"],
            verifier_concurrency=payload["verifier_concurrency"],
        )
    except (KeyError, TypeError) as exc:
        raise ValueError("rootless config field types are invalid") from exc


@dataclass(frozen=True)
class RootlessFullHarnessRuntime:
    backend: SandboxBackend
    evaluator: "QFBenchSandboxEvaluator"
    proposer: "SandboxFullHarnessProposer"
    image_identity_digest: str
    scheduler_identity_digest: str
    runtime_identity_digest: str
    _coordinator_lock: _CoordinatorLock = field(repr=False, compare=False)

    def close(self) -> None:
        """Release this run's exclusive coordinator ownership idempotently."""

        self._coordinator_lock.close()


def _selected_image_entries(image_set) -> tuple[Mapping[str, object], ...]:
    entries: list[Mapping[str, object]] = []
    for role in ("base", "proxy", "evolver"):
        entry = getattr(image_set, role, None)
        if not isinstance(entry, Mapping):
            raise RootlessFullHarnessError(
                f"selected {role} image entry is unavailable"
            )
        entries.append(entry)
    tasks = getattr(image_set, "tasks", None)
    if isinstance(tasks, (str, bytes)) or not isinstance(tasks, (tuple, list)):
        raise RootlessFullHarnessError("selected task image entries are unavailable")
    for task in tasks:
        if not isinstance(task, Mapping):
            raise RootlessFullHarnessError("selected task image entry is invalid")
        for role in ("worker", "verifier"):
            entry = task.get(role)
            if not isinstance(entry, Mapping):
                raise RootlessFullHarnessError(
                    f"selected task {role} image entry is unavailable"
                )
            entries.append(entry)
    return tuple(entries)


def _verify_benchmark_materials(
    *,
    config: RootlessFullHarnessConfig,
    image_set,
    benchmark_commit: str,
    task_ids: tuple[str, ...],
) -> str:
    from .rootless_images import RootlessImageError, verify_role_root

    try:
        public = verify_role_root(config.public_root, "public")
        trusted = verify_role_root(config.trusted_root, "trusted-verifier")
    except RootlessImageError as exc:
        raise RootlessFullHarnessError(
            f"benchmark material manifest verification failed: {exc}"
        ) from exc
    panel = tuple(sorted(task_ids))
    if (
        public.commit != benchmark_commit
        or trusted.commit != benchmark_commit
        or public.task_ids != panel
        or trusted.task_ids != panel
    ):
        raise RootlessFullHarnessError(
            "benchmark material commit or exact task panel differs"
        )
    for entry in _selected_image_entries(image_set):
        if entry.get("source_manifest_sha256") != public.manifest_sha256:
            raise RootlessFullHarnessError(
                "public material manifest differs from selected image sources"
            )
    selected_tasks = {
        str(task["task_id"]): task
        for task in image_set.tasks
        if isinstance(task, Mapping) and isinstance(task.get("task_id"), str)
    }
    if tuple(sorted(selected_tasks)) != panel:
        raise RootlessFullHarnessError(
            "selected image task membership differs from benchmark materials"
        )
    trusted_task_identities: list[dict[str, str]] = []
    for task_id in panel:
        prefix = f"tasks/{task_id}/"
        records = [
            (path, record)
            for path, record in trusted.records.items()
            if path.startswith(prefix)
        ]
        test_script = f"tasks/{task_id}/tests/test.sh"
        try:
            test_script_sha256 = trusted.records[test_script]["sha256"]
            verifier_entry = selected_tasks[task_id]["verifier"]
        except (KeyError, TypeError) as exc:
            raise RootlessFullHarnessError(
                f"trusted verifier material is incomplete for {task_id!r}"
            ) from exc
        if (
            not isinstance(verifier_entry, Mapping)
            or verifier_entry.get("verifier_test_script_sha256")
            != test_script_sha256
        ):
            raise RootlessFullHarnessError(
                f"trusted verifier script differs from selected image for {task_id!r}"
            )
        trusted_task_identities.append(
            {
                "task_id": task_id,
                "identity_sha256": _canonical_digest(
                    {
                        "task_id": task_id,
                        "files": [
                            {
                                "path": path.removeprefix(prefix),
                                "sha256": record["sha256"],
                                "git_blob_oid": record["git_blob_oid"],
                                "size_bytes": record["size_bytes"],
                                "mode": record.get("mode"),
                            }
                            for path, record in sorted(records)
                        ],
                    }
                ),
            }
        )
    return _canonical_digest(
        {
            "schema_version": 1,
            "benchmark_commit": benchmark_commit,
            "task_ids": list(panel),
            "public_manifest_sha256": public.manifest_sha256,
            "trusted_manifest_sha256": trusted.manifest_sha256,
            "trusted_task_identities": trusted_task_identities,
        }
    )


def _expected_docker_preflight(image_set) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    entries = _selected_image_entries(image_set)
    daemon_identities: set[tuple[str, tuple[str, ...]]] = set()
    image_ids: list[str] = []
    for entry in entries:
        docker_identity = entry.get("docker_identity")
        if not isinstance(docker_identity, Mapping):
            raise RootlessFullHarnessError(
                "selected image omits its Docker daemon identity"
            )
        version = docker_identity.get("version")
        security = docker_identity.get("security_options")
        if (
            not isinstance(version, str)
            or not version
            or not isinstance(security, (list, tuple))
            or not all(isinstance(value, str) for value in security)
            or "name=rootless" not in security
        ):
            raise RootlessFullHarnessError(
                "selected image has an invalid Docker daemon identity"
            )
        daemon_identities.add((version, tuple(sorted(security))))
        image_id = entry.get("image_id")
        if not isinstance(image_id, str):
            raise RootlessFullHarnessError("selected image ID is unavailable")
        image_ids.append(image_id)
    if len(daemon_identities) != 1:
        raise RootlessFullHarnessError(
            "selected images were built by inconsistent Docker daemon identities"
        )
    version, security = next(iter(daemon_identities))
    return version, security, tuple(sorted(set(image_ids)))


def _resolved_catalog(catalog, config: RootlessFullHarnessConfig):
    from .rootless_runtime import RootlessRuntimeCatalog, RootlessTaskRuntime

    resolved: dict[str, RootlessTaskRuntime] = {}
    for task_id, task in catalog.tasks.items():
        worker = SandboxResourceContract(
            cpu_count=task.worker_resources.cpu_count,
            memory_mb=task.worker_resources.memory_mb,
            pids_limit=config.worker_limits.pids_limit,
            timeout_seconds=config.worker_limits.timeout_seconds,
            writable_tmpfs_mb=config.worker_limits.writable_tmpfs_mb,
        )
        verifier = SandboxResourceContract(
            cpu_count=task.verifier_resources.cpu_count,
            memory_mb=task.verifier_resources.memory_mb,
            pids_limit=config.verifier_limits.pids_limit,
            timeout_seconds=config.verifier_limits.timeout_seconds,
            writable_tmpfs_mb=config.verifier_limits.writable_tmpfs_mb,
        )
        identity = _canonical_digest(
            {
                "task7_task_runtime_identity_sha256": task.identity_sha256,
                "task_id": task_id,
                "worker_resources": _resource_payload(worker),
                "verifier_resources": _resource_payload(verifier),
            }
        )
        resolved[task_id] = RootlessTaskRuntime(
            task_id=task_id,
            worker_image_ref=task.worker_image_ref,
            verifier_image_ref=task.verifier_image_ref,
            worker_resources=worker,
            verifier_resources=verifier,
            identity_sha256=identity,
        )
    resolved_identity = _canonical_digest(
        {
            "schema_version": 1,
            "task7_catalog_identity_sha256": catalog.identity_sha256,
            "worker_limits": _limits_payload(config.worker_limits),
            "verifier_limits": _limits_payload(config.verifier_limits),
            "tasks": [
                {"task_id": task_id, "identity_sha256": task.identity_sha256}
                for task_id, task in sorted(resolved.items())
            ],
        }
    )
    return RootlessRuntimeCatalog(
        benchmark_commit=catalog.benchmark_commit,
        base_image_ref=catalog.base_image_ref,
        evolver_image_ref=catalog.evolver_image_ref,
        proxy_image_ref=catalog.proxy_image_ref,
        tasks=MappingProxyType(dict(sorted(resolved.items()))),
        image_set_identity_sha256=catalog.image_set_identity_sha256,
        identity_sha256=resolved_identity,
    )


def _request_payload(*resources: SandboxResourceContract) -> dict[str, int]:
    return {
        "cpu_count": sum(resource.cpu_count for resource in resources),
        "memory_mb": sum(resource.memory_mb for resource in resources),
        "pids_limit": sum(resource.pids_limit for resource in resources),
        "tmpfs_mb": sum(
            sum(resource.writable_tmpfs_mb.values()) for resource in resources
        ),
        "sandboxes": len(resources),
    }


def _validate_capacity(
    config: RootlessFullHarnessConfig,
    catalog,
) -> None:
    requests = {
        "evolver": _request_payload(
            config.evolver_resources, config.proxy_resources
        ),
        **{
            f"worker:{task_id}": _request_payload(
                task.worker_resources, config.proxy_resources
            )
            for task_id, task in catalog.tasks.items()
        },
        **{
            f"verifier:{task_id}": _request_payload(task.verifier_resources)
            for task_id, task in catalog.tasks.items()
        },
    }
    capacity = _capacity_payload(config.capacity)
    for role, request in requests.items():
        if any(request[name] > capacity[name] for name in capacity):
            raise RootlessFullHarnessError(
                f"host capacity cannot admit declared {role} resources"
            )


def _linux_available_memory_mb(
    meminfo_path: Path = Path("/proc/meminfo"),
) -> int:
    """Return Linux reclaim-aware available memory, failing closed on drift."""

    try:
        lines = Path(meminfo_path).read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeError) as exc:
        raise RootlessFullHarnessError(
            "host health preflight could not read MemAvailable"
        ) from exc
    matches = [
        match
        for line in lines
        if (match := _MEM_AVAILABLE.fullmatch(line)) is not None
    ]
    if len(matches) != 1:
        raise RootlessFullHarnessError(
            "host health preflight requires exactly one MemAvailable kB record"
        )
    return int(matches[0].group(1)) // 1024


def _default_health_probe(results_root: Path):
    from .resource_lease import HostHealthSnapshot

    def probe() -> HostHealthSnapshot:
        try:
            load_1m = os.getloadavg()[0]
            filesystem = os.statvfs(results_root)
        except (AttributeError, OSError, ValueError) as exc:
            raise RootlessFullHarnessError("host health preflight failed") from exc
        return HostHealthSnapshot(
            load_1m=load_1m,
            available_memory_mb=_linux_available_memory_mb(),
            free_disk_mb=(filesystem.f_bavail * filesystem.f_frsize) // (1024 * 1024),
            free_inodes=filesystem.f_favail,
        )

    return probe


def build_rootless_full_harness_runtime(
    *,
    config: RootlessFullHarnessConfig,
    image_set_manifest: str | Path,
    benchmark_commit: str,
    tasks,
    run_id: str,
    results_root: str | Path,
) -> RootlessFullHarnessRuntime:
    """Assemble one E2B-independent rootless full-harness runtime."""

    if not isinstance(config, RootlessFullHarnessConfig):
        raise RootlessFullHarnessError(
            "config must be a RootlessFullHarnessConfig"
        )
    if os.getuid() != config.expected_uid:
        raise RootlessFullHarnessError(
            "coordinator UID differs from expected rootless Docker UID"
        )
    if not isinstance(run_id, str) or _RUN_ID.fullmatch(run_id) is None:
        raise RootlessFullHarnessError("run_id must be a path-safe identifier")
    selected_tasks = tuple(tasks)
    if not selected_tasks:
        raise RootlessFullHarnessError("task panel must not be empty")
    task_ids = tuple(getattr(task, "task_id", None) for task in selected_tasks)
    if any(not isinstance(task_id, str) or not task_id for task_id in task_ids):
        raise RootlessFullHarnessError("task panel contains an invalid task identity")
    if len(set(task_ids)) != len(task_ids):
        raise RootlessFullHarnessError("task panel contains duplicate task identities")

    from . import rootless_runtime
    from .backends.rootless_docker import RootlessDockerBackend
    from .executors.sandbox_evolver import (
        SandboxEvolverConfig,
        SandboxFullHarnessProposer,
    )
    from .executors.sandbox_proxy import SandboxProxyConfig, SandboxProxyManager
    from .executors.sandbox_runtime import public_model_environment, trusted_directory
    from .loop_benchmark import QFBenchSandboxEvaluator
    from .resource_lease import HostResourceLeasePool
    from .rootless_image_set import RootlessImageSet, RootlessImageSetError

    image_set_path = Path(image_set_manifest)
    try:
        image_set = RootlessImageSet.load(image_set_path)
    except (OSError, RootlessImageSetError, TypeError, ValueError) as exc:
        raise RootlessFullHarnessError("cannot load explicit rootless image set") from exc
    source_catalog = rootless_runtime.load_rootless_runtime_catalog(
        image_set_path,
        task_ids,
        benchmark_commit=benchmark_commit,
    )
    if (
        image_set.benchmark_commit != source_catalog.benchmark_commit
        or image_set.task_ids != tuple(sorted(task_ids))
        or image_set.identity_sha256 != source_catalog.image_set_identity_sha256
    ):
        raise RootlessFullHarnessError(
            "Task 5 image set differs from the Task 7 runtime catalog"
        )
    material_identity = _verify_benchmark_materials(
        config=config,
        image_set=image_set,
        benchmark_commit=benchmark_commit,
        task_ids=task_ids,
    )
    expected_docker_version, expected_docker_security, selected_image_ids = (
        _expected_docker_preflight(image_set)
    )
    for role, configured in (
        ("evolver", config.evolver_resources),
        ("proxy", config.proxy_resources),
    ):
        selected = getattr(image_set, role)
        declared = selected.get("resource_contract")
        actual = (configured.cpu_count, configured.memory_mb)
        expected = (
            declared.get("cpu_count") if isinstance(declared, Mapping) else None,
            declared.get("memory_mb") if isinstance(declared, Mapping) else None,
        )
        if actual != expected:
            raise RootlessFullHarnessError(
                f"{role} image resource contract differs from rootless config"
            )
    by_id = {task.task_id: task for task in selected_tasks}
    for task_id, selected in source_catalog.tasks.items():
        task = by_id[task_id]
        expected = (getattr(task, "cpus", None), getattr(task, "memory_mb", None))
        worker_actual = (
            selected.worker_resources.cpu_count,
            selected.worker_resources.memory_mb,
        )
        verifier_actual = (
            selected.verifier_resources.cpu_count,
            selected.verifier_resources.memory_mb,
        )
        if expected != worker_actual or expected != verifier_actual:
            raise RootlessFullHarnessError(
                f"task resource identity differs for {task_id!r}"
            )
        if config.worker_limits.timeout_seconds < getattr(
            task, "agent_timeout_seconds", 0
        ) or config.verifier_limits.timeout_seconds < getattr(
            task, "verifier_timeout_seconds", 0
        ):
            raise RootlessFullHarnessError(
                f"role timeout is below benchmark contract for {task_id!r}"
            )
    catalog = _resolved_catalog(source_catalog, config)
    _validate_capacity(config, catalog)

    root = trusted_directory(
        Path(results_root).expanduser(), create=True, phase="rootless.results"
    )
    run_root = trusted_directory(
        root / run_id,
        create=True,
        phase="rootless.run",
        contained_by=root,
    )
    lock = _CoordinatorLock(run_root / ".coordinator.lock").acquire()
    try:
        try:
            backend = RootlessDockerBackend(
                docker_host=config.docker_host,
                expected_uid=config.expected_uid,
            )
            measured_preflight = backend.preflight(
                expected_server_version=expected_docker_version,
                expected_security_options=expected_docker_security,
                image_ids=selected_image_ids,
            )
        except Exception as exc:
            raise RootlessFullHarnessError(
                "rootless Docker daemon and image preflight failed"
            ) from exc
        probe = _default_health_probe(root)
        pool = HostResourceLeasePool(config.capacity, config.headroom, probe)
        proxy_config = SandboxProxyConfig(
            image_ref=catalog.proxy_image_ref,
            resource_contract=config.proxy_resources,
            token_file=config.token_file,
            upstream_base_url=config.upstream_base_url,
            allowed_path_prefix=config.allowed_path_prefix,
            allowed_model=config.allowed_model,
        )
        proxy_manager = SandboxProxyManager(
            backend=backend,
            config=proxy_config,
        )
        worker_router = rootless_runtime.RootlessWorkerRouter(
            catalog=catalog,
            backend=backend,
            lifecycle_root=run_root / "lifecycles",
            public_task_root=config.public_root,
            proxy_manager=proxy_manager,
            resource_pool=pool,
            model_name=config.allowed_model,
        )
        verifier_router = rootless_runtime.RootlessVerifierRouter(
            catalog=catalog,
            backend=backend,
            lifecycle_root=run_root / "lifecycles",
            trusted_task_root=config.trusted_root,
            resource_pool=pool,
        )
        evolver_config = SandboxEvolverConfig(
            image_ref=catalog.evolver_image_ref,
            resource_contract=config.evolver_resources,
            command_timeout_seconds=config.evolver_resources.timeout_seconds,
        )
        proposer = SandboxFullHarnessProposer(
            config=evolver_config,
            backend=backend,
            lifecycle_root=run_root / "lifecycles",
            proxy_manager=proxy_manager,
            resource_pool=pool,
            model_name=config.allowed_model,
        )
        model_env = public_model_environment(
            proxy_base_url=(
                "http://qea-model-proxy:8080" + config.allowed_path_prefix
            ),
            model_name=config.allowed_model,
        )
        evaluator = QFBenchSandboxEvaluator(
            benchmark_commit=benchmark_commit,
            run_id=run_id,
            executor=worker_router,
            verifier=verifier_router,
            model_env=model_env,
            worker_concurrency=config.worker_concurrency,
            verifier_concurrency=config.verifier_concurrency,
        )

        scheduler_identity = _canonical_digest(
            {
                "schema_version": 1,
                "capacity": _capacity_payload(config.capacity),
                "headroom": _headroom_payload(config.headroom),
                "worker_concurrency": config.worker_concurrency,
                "verifier_concurrency": config.verifier_concurrency,
            }
        )
        task_panel = [
            {
                "task_id": task.task_id,
                "cpus": task.cpus,
                "memory_mb": task.memory_mb,
                "agent_timeout_seconds": task.agent_timeout_seconds,
                "verifier_timeout_seconds": task.verifier_timeout_seconds,
            }
            for task in sorted(selected_tasks, key=lambda item: item.task_id)
        ]
        runtime_identity = _canonical_digest(
            {
                "schema_version": 1,
                "backend_preflight": {
                    "backend": backend.backend_name,
                    "docker_host": config.docker_host,
                    "expected_uid": config.expected_uid,
                    "actual_uid": measured_preflight.actual_uid,
                    "server_version": measured_preflight.server_version,
                    "security_options": list(
                        measured_preflight.security_options
                    ),
                    "selected_image_ids": list(measured_preflight.image_ids),
                    "measurement_identity_sha256": (
                        measured_preflight.identity_sha256
                    ),
                },
                "benchmark_commit": benchmark_commit,
                "task_panel": task_panel,
                "benchmark_material_identity_sha256": material_identity,
                "task7_catalog_identity_sha256": source_catalog.identity_sha256,
                "resolved_catalog_identity_sha256": catalog.identity_sha256,
                "image_set_identity_sha256": catalog.image_set_identity_sha256,
                "evolver_image_ref": catalog.evolver_image_ref,
                "proxy_image_ref": catalog.proxy_image_ref,
                "evolver_resources": _resource_payload(config.evolver_resources),
                "proxy_resources": _resource_payload(config.proxy_resources),
                "worker_limits": _limits_payload(config.worker_limits),
                "verifier_limits": _limits_payload(config.verifier_limits),
                "model_egress_policy": {
                    "upstream_base_url": config.upstream_base_url,
                    "allowed_path_prefix": config.allowed_path_prefix,
                    "allowed_model": config.allowed_model,
                    "token_file": str(config.token_file),
                    "identity_sha256": rootless_model_route_identity(
                        upstream_base_url=config.upstream_base_url,
                        allowed_path_prefix=config.allowed_path_prefix,
                        allowed_model=config.allowed_model,
                    ),
                },
                "proxy_runtime_policy": {
                    "listen_port": proxy_config.listen_port,
                    "timeout_seconds": proxy_config.timeout_seconds,
                    "expect_request": proxy_config.expect_request,
                },
                "evolver_runtime_policy": {
                    "command_timeout_seconds": (
                        evolver_config.command_timeout_seconds
                    ),
                    "max_input_files": evolver_config.max_input_files,
                    "max_input_bytes": evolver_config.max_input_bytes,
                    "max_candidate_files": evolver_config.max_candidate_files,
                    "max_candidate_bytes": evolver_config.max_candidate_bytes,
                    "lease_timeout_seconds": evolver_config.lease_timeout_seconds,
                },
                "router_runtime_policy": {
                    "worker_lease_timeout_seconds": (
                        worker_router.lease_timeout_seconds
                    ),
                    "verifier_lease_timeout_seconds": (
                        verifier_router.lease_timeout_seconds
                    ),
                    "public_model_environment": dict(model_env),
                },
                "public_root": str(config.public_root),
                "trusted_root": str(config.trusted_root),
                "scheduler_identity_sha256": scheduler_identity,
            }
        )
        return RootlessFullHarnessRuntime(
            backend=backend,
            evaluator=evaluator,
            proposer=proposer,
            image_identity_digest=catalog.image_set_identity_sha256,
            scheduler_identity_digest=scheduler_identity,
            runtime_identity_digest=runtime_identity,
            _coordinator_lock=lock,
        )
    except Exception:
        lock.close()
        raise


__all__ = [
    "RoleExecutionLimits",
    "RootlessFullHarnessError",
    "RootlessFullHarnessConfig",
    "RootlessFullHarnessRuntime",
    "build_rootless_full_harness_runtime",
    "load_rootless_full_harness_config",
    "rootless_model_route_identity",
]
