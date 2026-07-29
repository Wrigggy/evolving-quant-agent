"""Ordered, resumable gates for the self-hosted QFBench rootless canary."""

from __future__ import annotations

import hashlib
import json
import math
import multiprocessing
import os
import pwd
import re
import signal
import tarfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Callable, Literal, Mapping
from urllib.parse import urlsplit


CANARY_STAGES = (
    "daemon",
    "immutable-images",
    "resources-2cpu-4gib",
    "resources-4cpu-8gib",
    "filesystem-and-capabilities",
    "verifier-no-egress",
    "worker-proxy-synthetic",
    "nexau-no-model",
    "force-kill-reap-resume",
    "verifier-replay",
    "historical-var-seed-worker",
)

_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
_EXPECTED_BRANCH = "qfbench-selfhosted-vm-backend"
_EXPECTED_TASK = "historical-var-data-prep"
_EXPECTED_DOMAIN = "risk"
_SYNTHETIC_PROXY_UPSTREAM_BASE_URL = "https://example.com/v1"
_PATH_KEYS = frozenset(
    {
        "source_root",
        "public_root",
        "trusted_root",
        "image_manifest_root",
        "secret_file",
        "run_output_root",
        "historical_artifact_manifest",
        "historical_e2b_score",
    }
)
_TASK_KEYS = frozenset(
    {
        "task_id",
        "domain",
        "worker_dir",
        "model_name",
        "proxy_upstream_base_url",
        "proxy_allowed_path_prefix",
    }
)
_TOP_LEVEL_KEYS = frozenset(
    {
        "schema_version",
        "run_id",
        "benchmark_commit",
        "branch",
        "docker_host",
        "expected_uid",
        "paths",
        "task",
    }
)
_DIRECT_NETWORK_PROBES = frozenset(
    {
        "dns",
        "public_ipv4_tcp",
        "public_ipv6_tcp",
        "http",
        "https",
        "github",
        "pypi",
        "model_host",
        "metadata_ipv4",
        "metadata_dns",
        "docker_socket",
    }
)


class CanaryConfigError(ValueError):
    """A rootless canary configuration is unsafe or ambiguous."""


class CanaryGateError(RuntimeError):
    """One canary gate failed closed and later gates must not run."""


def _arm_parent_death_signal(parent_pid: int) -> None:
    """Terminate a Linux child if its coordinator parent disappears."""

    if os.name != "posix" or not Path("/proc/self").exists():
        return
    try:
        import ctypes

        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(1, signal.SIGTERM, 0, 0, 0) != 0:  # PR_SET_PDEATHSIG
            raise OSError(ctypes.get_errno(), "prctl(PR_SET_PDEATHSIG) failed")
    except (AttributeError, OSError) as exc:
        raise CanaryGateError("cannot arm coordinator parent-death signal") from exc
    if os.getppid() != parent_pid:
        raise CanaryGateError("coordinator parent exited before child initialization")


def _force_kill_child(
    *,
    docker_host: str,
    expected_uid: int,
    spec_payload: Mapping[str, object],
    lifecycle_path: str,
    ready_marker_path: str,
    error_marker_path: str,
) -> None:
    """Persist one live lifecycle, then wait to be killed by the parent."""

    parent_pid = os.getppid()
    try:
        _arm_parent_death_signal(parent_pid)
        from .backends.rootless_docker import RootlessDockerBackend
        from .sandbox_backend import SandboxSpec
        from .sandbox_lifecycle import create_lifecycle, mark_started

        backend = RootlessDockerBackend(
            docker_host=docker_host,
            expected_uid=expected_uid,
        )
        spec = SandboxSpec(**dict(spec_payload))
        identity = hashlib.sha256(spec.canonical_json().encode()).hexdigest()
        handle = backend.create(spec)
        create_lifecycle(
            lifecycle_path,
            handle=handle,
            spec=spec,
            attempt_identity_sha256=identity,
        )
        backend.start(handle)
        mark_started(lifecycle_path)
        _atomic_json(
            Path(ready_marker_path),
            {
                "schema_version": 1,
                "coordinator_pid": os.getpid(),
                "parent_pid": parent_pid,
                "native_id": handle.native_id,
                "attempt_identity_sha256": identity,
            },
        )
        while True:
            signal.pause()
    except BaseException as exc:  # noqa: BLE001 - child must leave bounded evidence.
        try:
            _atomic_json(
                Path(error_marker_path),
                {
                    "schema_version": 1,
                    "error_type": type(exc).__name__,
                    "error": " ".join(str(exc).split())[:2_000],
                },
            )
        finally:
            raise


@dataclass(frozen=True)
class RootlessCanaryConfig:
    schema_version: int
    run_id: str
    benchmark_commit: str
    branch: str
    docker_host: str
    expected_uid: int
    paths: Mapping[str, str]
    task: Mapping[str, str]
    runtime_root: Path
    config_sha256: str

    def resolved_path(self, name: str) -> Path:
        try:
            relative = self.paths[name]
        except KeyError as exc:
            raise CanaryConfigError(f"unknown canary path {name!r}") from exc
        target = (self.runtime_root / relative).resolve()
        try:
            target.relative_to(self.runtime_root)
        except ValueError as exc:
            raise CanaryConfigError(f"canary path escapes runtime root: {name}") from exc
        return target

    def public_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "benchmark_commit": self.benchmark_commit,
            "branch": self.branch,
            "docker_host": self.docker_host,
            "expected_uid": self.expected_uid,
            "paths": dict(self.paths),
            "task": dict(self.task),
        }


StageStatus = Literal["pass", "fail", "not_run"]


@dataclass(frozen=True)
class CanaryStageResult:
    schema_version: int
    sequence: int
    stage: str
    status: StageStatus
    config_sha256: str
    source_commit: str
    started_at: str | None
    finished_at: str
    duration_seconds: float
    evidence: Mapping[str, object]
    failure: str | None
    reused: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence", MappingProxyType(dict(self.evidence)))

    def payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "sequence": self.sequence,
            "stage": self.stage,
            "status": self.status,
            "config_sha256": self.config_sha256,
            "source_commit": self.source_commit,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_seconds": self.duration_seconds,
            "evidence": dict(self.evidence),
            "failure": self.failure,
            "reused": self.reused,
        }


def _safe_relative(value: object, *, label: str) -> str:
    if not isinstance(value, str):
        raise CanaryConfigError(f"{label} must be a relative path")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or not path.parts
        or path.as_posix() != value
        or any(part in {"", ".", ".."} for part in path.parts)
        or "solution" in {part.lower() for part in path.parts}
    ):
        raise CanaryConfigError(f"unsafe {label}: {value!r}")
    return value


def _require_string(payload: Mapping[str, object], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value.strip():
        raise CanaryConfigError(f"{name} must be a non-empty string")
    return value.strip()


def _canonical_sha256(payload: Mapping[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def load_canary_config(
    path: str | Path,
    *,
    runtime_root: str | Path,
) -> RootlessCanaryConfig:
    """Load a public-only config without creating or probing runtime paths."""

    config_path = Path(path).expanduser().resolve()
    try:
        payload = json.loads(config_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise CanaryConfigError(f"cannot read canary config: {exc}") from exc
    if not isinstance(payload, dict) or set(payload) != _TOP_LEVEL_KEYS:
        raise CanaryConfigError("canary config has missing or forbidden top-level keys")
    if payload.get("schema_version") != 1:
        raise CanaryConfigError("unsupported canary config schema")
    run_id = _require_string(payload, "run_id")
    if _IDENTIFIER.fullmatch(run_id) is None:
        raise CanaryConfigError("run_id is unsafe")
    benchmark_commit = _require_string(payload, "benchmark_commit").lower()
    if _COMMIT.fullmatch(benchmark_commit) is None:
        raise CanaryConfigError("benchmark_commit must be a full SHA")
    branch = _require_string(payload, "branch")
    if branch != _EXPECTED_BRANCH:
        raise CanaryConfigError(f"canary branch must be {_EXPECTED_BRANCH!r}")
    expected_uid = payload.get("expected_uid")
    if type(expected_uid) is not int or expected_uid <= 0:
        raise CanaryConfigError("expected_uid must be a positive non-root integer")
    docker_host = _require_string(payload, "docker_host")
    if docker_host != f"unix:///run/user/{expected_uid}/docker.sock":
        raise CanaryConfigError("docker_host must be the exact rootless user socket")

    raw_paths = payload.get("paths")
    if not isinstance(raw_paths, dict) or set(raw_paths) != _PATH_KEYS:
        raise CanaryConfigError("canary paths have missing or forbidden keys")
    paths = {
        name: _safe_relative(value, label=name)
        for name, value in sorted(raw_paths.items())
    }
    raw_task = payload.get("task")
    if not isinstance(raw_task, dict) or set(raw_task) != _TASK_KEYS:
        raise CanaryConfigError("canary task has missing or forbidden keys")
    task = {name: _require_string(raw_task, name) for name in sorted(_TASK_KEYS)}
    if task["task_id"] != _EXPECTED_TASK:
        raise CanaryConfigError(f"canary task must be {_EXPECTED_TASK!r}")
    if task["domain"] != _EXPECTED_DOMAIN:
        raise CanaryConfigError(
            f"canary task domain must match the five-task manifest: {_EXPECTED_DOMAIN!r}"
        )
    task["worker_dir"] = _safe_relative(task["worker_dir"], label="worker_dir")
    upstream = urlsplit(task["proxy_upstream_base_url"])
    if (
        upstream.scheme != "https"
        or not upstream.hostname
        or upstream.username
        or upstream.password
        or upstream.query
        or upstream.fragment
    ):
        raise CanaryConfigError("proxy upstream must be one fixed HTTPS base URL")
    prefix = task["proxy_allowed_path_prefix"]
    if not prefix.startswith("/") or prefix == "/" or ".." in PurePosixPath(prefix).parts:
        raise CanaryConfigError("proxy path prefix is unsafe")
    root = Path(runtime_root).expanduser().resolve()
    public_payload = {
        "schema_version": 1,
        "run_id": run_id,
        "benchmark_commit": benchmark_commit,
        "branch": branch,
        "docker_host": docker_host,
        "expected_uid": expected_uid,
        "paths": paths,
        "task": task,
    }
    return RootlessCanaryConfig(
        **public_payload,
        runtime_root=root,
        config_sha256=_canonical_sha256(public_payload),
    )


def _require_commit(value: str) -> str:
    normalized = str(value).strip().lower()
    if _COMMIT.fullmatch(normalized) is None:
        raise CanaryConfigError("source_commit must be a full lowercase SHA")
    return normalized


def plan_canary(
    config: RootlessCanaryConfig,
    *,
    source_commit: str,
) -> dict[str, object]:
    """Return a side-effect-free public plan with no secret filesystem path."""

    commit = _require_commit(source_commit)
    containers = (
        "qea-canary-resource-2cpu-4096mb",
        "qea-canary-resource-4cpu-8192mb",
        "qea-canary-filesystem-a",
        "qea-canary-filesystem-b",
        "qea-verifier-verifier-no-egress",
        "qea-proxy-proxy-synthetic",
        "qea-worker-worker-proxy-synthetic",
        "qea-worker-nexau-no-model",
        "qea-canary-force-kill-reap-resume",
        "qea-proxy-proxy-paid",
    )
    return {
        "schema_version": 1,
        "mode": "plan-only",
        "mutates": False,
        "formal_scoring_available": False,
        "run_id": config.run_id,
        "branch": config.branch,
        "source_commit": commit,
        "benchmark_commit": config.benchmark_commit,
        "config_sha256": config.config_sha256,
        "docker_host": config.docker_host,
        "task_id": config.task["task_id"],
        "secret_source": "external-mode-600-file",
        "stages": list(CANARY_STAGES),
        "planned_resources": {
            "internal_network": f"qea-{config.run_id}-internal",
            "containers": list(containers),
            "dynamic_fresh_roles": ["worker", "verifier"],
        },
    }


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CanaryConfigError("canary clock must return timezone-aware values")
    return value.astimezone(timezone.utc).isoformat()


def _atomic_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    encoded = json.dumps(payload, sort_keys=True, indent=2).encode() + b"\n"
    try:
        with temporary.open("wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


def _stage_path(root: Path, sequence: int, stage: str) -> Path:
    return root / f"{sequence:02d}-{stage}.json"


def _load_reusable(
    path: Path,
    *,
    sequence: int,
    stage: str,
    config_sha256: str,
    source_commit: str,
) -> CanaryStageResult | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise CanaryConfigError(f"invalid existing stage result {path}: {exc}") from exc
    expected = {
        "schema_version": 1,
        "sequence": sequence,
        "stage": stage,
        "config_sha256": config_sha256,
        "source_commit": source_commit,
    }
    if any(payload.get(name) != value for name, value in expected.items()):
        raise CanaryConfigError(f"existing stage result identity mismatch: {path}")
    if payload.get("status") != "pass":
        return None
    try:
        return CanaryStageResult(
            **{
                **payload,
                "evidence": dict(payload.get("evidence", {})),
                "reused": True,
            }
        )
    except TypeError as exc:
        raise CanaryConfigError(f"malformed existing stage result {path}") from exc


def _sanitize_failure(value: object, forbidden_values: tuple[str, ...]) -> str:
    cleaned = f"{type(value).__name__}: {value}"
    for secret in sorted(
        {item for item in forbidden_values if isinstance(item, str) and item},
        key=len,
        reverse=True,
    ):
        cleaned = cleaned.replace(secret, "[REDACTED]")
    return " ".join(cleaned.split())[:2_000]


def run_canary(
    config: RootlessCanaryConfig,
    *,
    source_commit: str,
    output_root: str | Path,
    gate_runner: Callable[[str], Mapping[str, object]],
    forbidden_values: tuple[str, ...] = (),
    through_stage: str | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> tuple[CanaryStageResult, ...]:
    """Run ordered gates, resume passed identities, and stop at first failure."""

    commit = _require_commit(source_commit)
    if through_stage is not None and through_stage not in CANARY_STAGES:
        raise CanaryConfigError(f"unknown through_stage {through_stage!r}")
    boundary = (
        CANARY_STAGES.index(through_stage) + 1
        if through_stage is not None
        else len(CANARY_STAGES)
    )
    root = Path(output_root).expanduser().resolve()
    if root.is_symlink():
        raise CanaryConfigError("canary output root must not be a symlink")
    root.mkdir(parents=True, exist_ok=True)
    identity_path = root / "canary-run.json"
    identity = {
        "schema_version": 1,
        "run_id": config.run_id,
        "config_sha256": config.config_sha256,
        "source_commit": commit,
        "benchmark_commit": config.benchmark_commit,
        "stages": list(CANARY_STAGES),
        "formal_scoring_available": False,
    }
    if identity_path.is_file():
        try:
            existing = json.loads(identity_path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise CanaryConfigError("existing canary identity is malformed") from exc
        if existing != identity:
            raise CanaryConfigError("existing canary identity differs from requested run")
    else:
        _atomic_json(identity_path, identity)

    results: list[CanaryStageResult] = []
    failed = False
    failure_stage: str | None = None
    for sequence, stage in enumerate(CANARY_STAGES, start=1):
        result_path = _stage_path(root, sequence, stage)
        reusable = None
        if not failed:
            reusable = _load_reusable(
                result_path,
                sequence=sequence,
                stage=stage,
                config_sha256=config.config_sha256,
                source_commit=commit,
            )
        if reusable is not None:
            results.append(reusable)
            continue
        if sequence > boundary and not failed:
            now = clock()
            result = CanaryStageResult(
                schema_version=1,
                sequence=sequence,
                stage=stage,
                status="not_run",
                config_sha256=config.config_sha256,
                source_commit=commit,
                started_at=None,
                finished_at=_timestamp(now),
                duration_seconds=0.0,
                evidence={"deferred_after_stage": through_stage},
                failure=None,
            )
            _atomic_json(result_path, result.payload())
            results.append(result)
            continue
        if failed:
            now = clock()
            result = CanaryStageResult(
                schema_version=1,
                sequence=sequence,
                stage=stage,
                status="not_run",
                config_sha256=config.config_sha256,
                source_commit=commit,
                started_at=None,
                finished_at=_timestamp(now),
                duration_seconds=0.0,
                evidence={"blocked_by_stage": failure_stage},
                failure=None,
            )
        else:
            started = clock()
            try:
                evidence = gate_runner(stage)
                if not isinstance(evidence, Mapping):
                    raise CanaryGateError("gate evidence must be a mapping")
                safe_evidence = dict(evidence)
                json.dumps(safe_evidence, sort_keys=True)
                status: StageStatus = "pass"
                failure = None
            except Exception as exc:  # noqa: BLE001 - stage boundary must persist.
                safe_evidence = {}
                status = "fail"
                failure = _sanitize_failure(exc, forbidden_values)
                failed = True
                failure_stage = stage
            finished = clock()
            duration = max(0.0, (finished - started).total_seconds())
            result = CanaryStageResult(
                schema_version=1,
                sequence=sequence,
                stage=stage,
                status=status,
                config_sha256=config.config_sha256,
                source_commit=commit,
                started_at=_timestamp(started),
                finished_at=_timestamp(finished),
                duration_seconds=round(duration, 6),
                evidence=safe_evidence,
                failure=failure,
            )
        _atomic_json(result_path, result.payload())
        results.append(result)
    return tuple(results)


def _positive_int(value: object, *, label: str) -> int:
    if isinstance(value, bool):
        raise CanaryGateError(f"{label} must be an integer")
    try:
        result = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise CanaryGateError(f"{label} must be an integer") from exc
    if result < 0:
        raise CanaryGateError(f"{label} must be non-negative")
    return result


def validate_resource_evidence(
    evidence: Mapping[str, object],
    *,
    cpu_count: int,
    memory_mb: int,
    pids_limit: int,
) -> dict[str, object]:
    """Require exact cgroup-v2 CPU, memory, no-swap, and PID limits."""

    if any(type(value) is not int or value <= 0 for value in (cpu_count, memory_mb, pids_limit)):
        raise CanaryGateError("expected resources must be positive integers")
    raw_cpu = evidence.get("cpu.max")
    if not isinstance(raw_cpu, str) or len(raw_cpu.split()) != 2:
        raise CanaryGateError("cpu.max must contain quota and period")
    quota_text, period_text = raw_cpu.split()
    if quota_text == "max":
        raise CanaryGateError("CPU quota is unlimited")
    quota = _positive_int(quota_text, label="cpu quota")
    period = _positive_int(period_text, label="cpu period")
    if period == 0 or not math.isclose(quota / period, cpu_count, abs_tol=1e-9):
        raise CanaryGateError("CPU cgroup limit differs from declared contract")
    memory = _positive_int(evidence.get("memory.max"), label="memory.max")
    expected_memory = memory_mb * 1024 * 1024
    if memory != expected_memory:
        raise CanaryGateError("memory cgroup limit differs from declared contract")
    swap = _positive_int(evidence.get("memory.swap.max"), label="memory.swap.max")
    if swap != 0:
        raise CanaryGateError("swap must be disabled when memory-swap equals memory")
    pids = _positive_int(evidence.get("pids.max"), label="pids.max")
    if pids != pids_limit:
        raise CanaryGateError("PID cgroup limit differs from declared contract")
    return {
        "cpu_count": quota / period,
        "memory_bytes": memory,
        "swap_bytes": swap,
        "pids_limit": pids,
    }


def validate_daemon_host_evidence(
    evidence: Mapping[str, object],
    *,
    expected_uid: int,
) -> dict[str, object]:
    """Require subordinate IDs, user namespaces, and delegated cgroup v2."""

    if evidence.get("actual_uid") != expected_uid:
        raise CanaryGateError("coordinator UID differs from rootless socket owner")
    if _positive_int(
        evidence.get("max_user_namespaces"), label="max_user_namespaces"
    ) <= 0:
        raise CanaryGateError("unprivileged user namespaces are disabled")
    for name in ("subuid_range_size", "subgid_range_size"):
        if _positive_int(evidence.get(name), label=name) < 65_536:
            raise CanaryGateError(f"{name} is smaller than 65536 IDs")
    if evidence.get("cgroup_v2") is not True:
        raise CanaryGateError("unified cgroup v2 is unavailable")
    controllers = evidence.get("cgroup_controllers")
    if not isinstance(controllers, list) or not {"cpu", "memory", "pids"}.issubset(
        controllers
    ):
        raise CanaryGateError("required cgroup v2 controllers are unavailable")
    return {
        "host_ready": True,
        "actual_uid": expected_uid,
        "max_user_namespaces": int(evidence["max_user_namespaces"]),
        "subuid_range_size": int(evidence["subuid_range_size"]),
        "subgid_range_size": int(evidence["subgid_range_size"]),
        "cgroup_v2": True,
        "cgroup_controllers": sorted(set(controllers)),
    }


def _subordinate_id_range_size(path: Path, *, username: str, uid: int) -> int:
    try:
        lines = path.read_text().splitlines()
    except OSError as exc:
        raise CanaryGateError(f"cannot read {path}") from exc
    total = 0
    for line in lines:
        fields = line.split(":")
        if len(fields) != 3 or fields[0] not in {username, str(uid)}:
            continue
        try:
            start, size = int(fields[1]), int(fields[2])
        except ValueError as exc:
            raise CanaryGateError(f"malformed subordinate ID range in {path}") from exc
        if start <= 0 or size <= 0:
            raise CanaryGateError(f"invalid subordinate ID range in {path}")
        total += size
    return total


def validate_docker_inspect_contract(
    payload: object,
    *,
    native_id: str,
    image_ref: str,
    cpu_count: int,
    memory_mb: int,
    pids_limit: int,
    network_policy: str,
    writable_tmpfs_mb: Mapping[str, int] | None = None,
) -> dict[str, object]:
    """Require the live Docker control plane to match the declared spec."""

    if not isinstance(payload, list) or len(payload) != 1 or not isinstance(payload[0], dict):
        raise CanaryGateError("Docker inspect must contain exactly one object")
    item = payload[0]
    try:
        inspected_id = item["Id"]
        config = item["Config"]
        host = item["HostConfig"]
        mounts = item["Mounts"]
    except (KeyError, TypeError) as exc:
        raise CanaryGateError("Docker inspect object is incomplete") from exc
    if inspected_id != native_id or not isinstance(config, dict) or not isinstance(host, dict):
        raise CanaryGateError("Docker inspect identity is malformed")
    labels = config.get("Labels") or {}
    if (
        config.get("Image") != image_ref
        or not isinstance(labels, dict)
        or labels.get("qea.managed") != "true"
        or labels.get("qea.backend") != "rootless-docker"
    ):
        raise CanaryGateError("Docker inspect image or ownership labels differ")
    if host.get("ReadonlyRootfs") is not True or host.get("Privileged") is not False:
        raise CanaryGateError("Docker root is writable or container is privileged")
    if host.get("Binds") not in (None, []) or host.get("CapAdd") not in (None, []):
        raise CanaryGateError("Docker inspect contains host binds or added capabilities")
    cap_drop = host.get("CapDrop")
    if not isinstance(cap_drop, list) or {str(value).upper() for value in cap_drop} != {"ALL"}:
        raise CanaryGateError("Docker inspect does not drop all capabilities")
    security = host.get("SecurityOpt")
    if not isinstance(security, list) or not any(
        str(value).startswith("no-new-privileges") for value in security
    ):
        raise CanaryGateError("Docker inspect lacks no-new-privileges")
    if host.get("PidMode") not in (None, "") or host.get("IpcMode") not in (None, "", "private"):
        raise CanaryGateError("Docker inspect enables host PID or IPC mode")
    expected_network = {
        "none": lambda value: value == "none",
        "worker-proxy-only": lambda value: isinstance(value, str)
        and value.startswith("qea-")
        and value.endswith("-internal"),
        "proxy-outbound": lambda value: value in {"bridge", "default"},
    }
    predicate = expected_network.get(network_policy)
    if predicate is None or not predicate(host.get("NetworkMode")):
        raise CanaryGateError("Docker network mode differs from declared policy")
    memory_bytes = memory_mb * 1024 * 1024
    expected_values = {
        "NanoCpus": cpu_count * 1_000_000_000,
        "Memory": memory_bytes,
        "MemorySwap": memory_bytes,
        "PidsLimit": pids_limit,
    }
    for name, expected in expected_values.items():
        if host.get(name) != expected:
            raise CanaryGateError(f"Docker HostConfig {name} differs from contract")
    expected_tmpfs = dict(writable_tmpfs_mb or {})
    raw_tmpfs = host.get("Tmpfs") or {}
    if expected_tmpfs:
        if not isinstance(raw_tmpfs, dict) or set(raw_tmpfs) != set(expected_tmpfs):
            raise CanaryGateError("Docker tmpfs targets differ from contract")
        for path, size_mb in expected_tmpfs.items():
            options = str(raw_tmpfs[path]).split(",")
            required = {"rw", "nosuid", "nodev", "noexec", f"size={size_mb}m"}
            if not required.issubset(options):
                raise CanaryGateError(f"Docker tmpfs options differ for {path}")
    if not isinstance(mounts, list):
        raise CanaryGateError("Docker inspect mounts are malformed")
    for mount in mounts:
        if (
            not isinstance(mount, dict)
            or mount.get("Type") != "tmpfs"
            or mount.get("Destination") not in expected_tmpfs
        ):
            raise CanaryGateError("Docker inspect contains a non-tmpfs host mount")
    return {
        "control_plane_isolated": True,
        "native_id": native_id,
        "image_ref": image_ref,
        "network_mode": host.get("NetworkMode"),
        "tmpfs_targets": sorted(expected_tmpfs),
    }


def audit_worker_bundle(path: str | Path) -> list[str]:
    """Reject worker input archives containing verifier tests or solutions."""

    bundle = Path(path).expanduser().resolve()
    try:
        with tarfile.open(bundle, mode="r:*") as archive:
            members = archive.getmembers()
    except (OSError, tarfile.TarError) as exc:
        raise CanaryGateError("worker input bundle is unreadable") from exc
    forbidden: list[str] = []
    for member in members:
        parts = tuple(part.lower() for part in PurePosixPath(member.name).parts)
        if any(part == "tests" or part.startswith("solution") for part in parts):
            forbidden.append(member.name)
    if forbidden:
        raise CanaryGateError("worker input bundle contains verifier or solution data")
    return forbidden


def validate_force_kill_evidence(
    evidence: Mapping[str, object],
) -> dict[str, object]:
    """Require one killed coordinator, one exact container ID, and safe resume."""

    native_id = evidence.get("native_id")
    coordinator_pid = evidence.get("coordinator_pid")
    if not isinstance(native_id, str) or _IDENTIFIER.fullmatch(native_id) is None:
        raise CanaryGateError("force-kill evidence has an invalid native ID")
    if type(coordinator_pid) is not int or coordinator_pid <= 0:
        raise CanaryGateError("force-kill evidence has an invalid coordinator PID")
    for name in ("attempt_identity_sha256", "completed_operation_sha256"):
        value = evidence.get(name)
        if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
            raise CanaryGateError(f"force-kill evidence has an invalid {name}")
    if evidence.get("final_pending_ids") != []:
        raise CanaryGateError("force-kill evidence retains pending sandboxes")
    if (
        evidence.get("model_calls_duplicated") != 0
        or evidence.get("verifier_calls_duplicated") != 0
    ):
        raise CanaryGateError("force-kill resume duplicated a completed operation")
    reused = evidence.get("cleaned_lifecycle_reused")
    if type(reused) is not bool:
        raise CanaryGateError("force-kill cleanup reuse flag is invalid")
    expected_dry = [] if reused else [native_id]
    expected_killed = [] if reused else [native_id]
    if (
        evidence.get("dry_pending_ids") != expected_dry
        or evidence.get("killed_ids") != expected_killed
    ):
        raise CanaryGateError("force-kill reaper did not use one exact native ID")
    return {
        "exact_id_cleanup": True,
        "resume_reused_cleanup": reused,
        **dict(evidence),
    }


def validate_isolation_evidence(
    evidence: Mapping[str, object],
    *,
    expected_writable_paths: tuple[str, ...],
) -> dict[str, object]:
    """Validate read-only root, zero capabilities, and per-attempt isolation."""

    expected_bools = {
        "root_read_only": True,
        "no_new_privileges": True,
        "docker_socket_present": False,
        "host_mount_present": False,
        "metadata_reachable": False,
        "cross_attempt_marker_present": False,
    }
    for name, expected in expected_bools.items():
        if type(evidence.get(name)) is not bool or evidence[name] is not expected:
            raise CanaryGateError(f"isolation evidence mismatch for {name}")
    cap_eff = evidence.get("cap_eff")
    if not isinstance(cap_eff, str):
        raise CanaryGateError("CapEff evidence is missing")
    try:
        capabilities = int(cap_eff, 16)
    except ValueError as exc:
        raise CanaryGateError("CapEff is not hexadecimal") from exc
    if capabilities != 0:
        raise CanaryGateError("effective Linux capabilities are not empty")
    writable = evidence.get("writable_paths")
    if not isinstance(writable, list) or tuple(sorted(writable)) != tuple(
        sorted(expected_writable_paths)
    ):
        raise CanaryGateError("writable paths differ from declared tmpfs mounts")
    interfaces = evidence.get("network_interfaces")
    if not isinstance(interfaces, list) or tuple(sorted(interfaces)) != ("lo",):
        raise CanaryGateError("networkless canary has unexpected interfaces")
    uid = evidence.get("uid")
    gid = evidence.get("gid")
    if type(uid) is not int or uid < 0 or type(gid) is not int or gid < 0:
        raise CanaryGateError("effective UID/GID evidence is invalid")
    evidence_hashes = {}
    for name in (
        "status_sha256",
        "mountinfo_sha256",
        "route_sha256",
        "ipv6_route_sha256",
    ):
        value = evidence.get(name)
        if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
            raise CanaryGateError(f"isolation evidence is missing {name}")
        evidence_hashes[name] = value
    return {
        "isolated": True,
        "uid": uid,
        "gid": gid,
        "cap_eff": cap_eff,
        "writable_paths": writable,
        **evidence_hashes,
    }


def validate_network_evidence(
    evidence: Mapping[str, object],
    *,
    role: Literal["verifier", "worker"],
) -> dict[str, object]:
    """Require all direct probes blocked; worker additionally needs proxy success."""

    if role not in {"verifier", "worker"}:
        raise CanaryGateError(f"unknown network evidence role {role!r}")
    missing = sorted(_DIRECT_NETWORK_PROBES - set(evidence))
    if missing:
        raise CanaryGateError(f"network evidence is missing probes: {missing}")
    for name in sorted(_DIRECT_NETWORK_PROBES):
        if type(evidence[name]) is not bool or evidence[name]:
            raise CanaryGateError(f"direct network probe was not blocked: {name}")
    if role == "worker":
        if evidence.get("proxy_request") is not True:
            raise CanaryGateError("worker synthetic proxy request did not succeed")
        if evidence.get("secret_exposed") is not False:
            raise CanaryGateError("worker credential exposure scan did not pass")
    return {"isolated": True, "role": role, "direct_probe_count": len(_DIRECT_NETWORK_PROBES)}


def _bounded_reward(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CanaryGateError("reward must be numeric")
    result = float(value)
    if not 0.0 <= result <= 1.0:
        raise CanaryGateError("reward must be in [0, 1]")
    return result


def validate_replay_parity(
    reference: Mapping[str, object],
    observed: Mapping[str, object],
) -> dict[str, object]:
    """Compare only content identities, reward, and bounded test counts."""

    digest_keys = (
        "artifact_sha256",
        "executed_test_sha256",
        "dependency_lock_sha256",
    )
    for key in digest_keys:
        if not isinstance(reference.get(key), str) or _DIGEST.fullmatch(reference[key]) is None:
            raise CanaryGateError(f"reference {key} is invalid")
        if observed.get(key) != reference[key]:
            raise CanaryGateError(f"replay {key} differs from E2B reference")
    if _bounded_reward(reference.get("reward")) != _bounded_reward(observed.get("reward")):
        raise CanaryGateError("replay reward differs from E2B reference")
    for key in ("tests_passed", "tests_failed"):
        expected = _positive_int(reference.get(key), label=key)
        actual = _positive_int(observed.get(key), label=key)
        if actual != expected:
            raise CanaryGateError(f"replay {key} differs from E2B reference")
    return {
        "parity": True,
        "artifact_sha256": reference["artifact_sha256"],
        "reward": float(reference["reward"]),
        "tests_passed": int(reference["tests_passed"]),
        "tests_failed": int(reference["tests_failed"]),
        "executed_test_sha256": reference["executed_test_sha256"],
        "dependency_lock_sha256": reference["dependency_lock_sha256"],
    }


def validate_fresh_worker_evidence(evidence: Mapping[str, object]) -> dict[str, object]:
    """Require one artifact-only worker/verifier attempt with no oracle surface."""

    if evidence.get("task_id") != _EXPECTED_TASK:
        raise CanaryGateError("fresh canary task identity is wrong")
    worker_id = evidence.get("worker_sandbox_id")
    verifier_id = evidence.get("verifier_sandbox_id")
    if not isinstance(worker_id, str) or not worker_id:
        raise CanaryGateError("fresh worker sandbox ID is missing")
    if not isinstance(verifier_id, str) or not verifier_id or verifier_id == worker_id:
        raise CanaryGateError("fresh verifier must be an independent sandbox")
    digest = evidence.get("artifact_sha256")
    if not isinstance(digest, str) or _DIGEST.fullmatch(digest) is None:
        raise CanaryGateError("fresh artifact digest is invalid")
    _bounded_reward(evidence.get("reward"))
    for key in ("tests_passed", "tests_failed"):
        _positive_int(evidence.get(key), label=key)
    if evidence.get("worker_network_policy") != "worker-proxy-only":
        raise CanaryGateError("fresh worker network policy is wrong")
    if evidence.get("verifier_network_policy") != "none":
        raise CanaryGateError("fresh verifier network policy is wrong")
    if evidence.get("solution_members") != []:
        raise CanaryGateError("fresh worker/verifier flow contains solution members")
    if evidence.get("oracle_lifecycles") != []:
        raise CanaryGateError("fresh flow contains an oracle lifecycle")
    model_identity = evidence.get("model_identity")
    if not isinstance(model_identity, str) or not model_identity:
        raise CanaryGateError("fresh model identity is missing")
    for key in ("input_tokens", "output_tokens"):
        value = evidence.get(key)
        if value is not None:
            _positive_int(value, label=key)
    for key in ("model_cost_usd", "sandbox_cost_usd"):
        value = evidence.get(key)
        if value is not None and (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or float(value) < 0
        ):
            raise CanaryGateError(f"{key} must be non-negative or null")
    return {
        "oracle_free": True,
        "task_id": _EXPECTED_TASK,
        "artifact_sha256": digest,
        "reward": float(evidence["reward"]),
        "tests_passed": int(evidence["tests_passed"]),
        "tests_failed": int(evidence["tests_failed"]),
        "model_identity": model_identity,
        "input_tokens": evidence.get("input_tokens"),
        "output_tokens": evidence.get("output_tokens"),
        "model_cost_usd": evidence.get("model_cost_usd"),
        "sandbox_cost_usd": evidence.get("sandbox_cost_usd"),
    }


_CONTAINER_EVIDENCE_SCRIPT = r'''import json
import os
import socket
from pathlib import Path


def read(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


status = read('/proc/self/status') or ''
fields = {}
for line in status.splitlines():
    name, separator, value = line.partition(':')
    if separator:
        fields[name] = value.strip()

writable = []
for name in ('/tmp', '/qea'):
    probe = Path(name) / 'qea-write-probe'
    try:
        probe.write_text('bounded')
        probe.unlink()
        writable.append(name)
    except OSError:
        pass

root_probe = Path('/qea-root-read-only-probe')
root_read_only = False
try:
    root_probe.write_text('must-fail')
    root_probe.unlink()
except OSError:
    root_read_only = True

metadata_reachable = False
try:
    connection = socket.create_connection(('169.254.169.254', 80), timeout=0.25)
    connection.close()
    metadata_reachable = True
except OSError:
    pass

mountinfo = read('/proc/self/mountinfo') or ''
route = read('/proc/net/route') or ''
ipv6_route = read('/proc/net/ipv6_route') or ''
digest = __import__('hashlib').sha256
host_markers = ('/Users/kevinwu/', '/host/', '/workspace/', 'docker.sock')
payload = {
    'cpu.max': read('/sys/fs/cgroup/cpu.max'),
    'memory.max': read('/sys/fs/cgroup/memory.max'),
    'memory.swap.max': read('/sys/fs/cgroup/memory.swap.max'),
    'pids.max': read('/sys/fs/cgroup/pids.max'),
    'uid': os.getuid(),
    'gid': os.getgid(),
    'cap_eff': fields.get('CapEff'),
    'no_new_privileges': fields.get('NoNewPrivs') == '1',
    'root_read_only': root_read_only,
    'writable_paths': writable,
    'docker_socket_present': any(Path(path).exists() for path in (
        '/var/run/docker.sock', '/run/docker.sock', '/run/user/1013/docker.sock'
    )),
    'host_mount_present': any(marker in mountinfo for marker in host_markers),
    'metadata_reachable': metadata_reachable,
    'cross_attempt_marker_present': Path('/qea/cross-attempt-marker').exists(),
    'network_interfaces': sorted(path.name for path in Path('/sys/class/net').iterdir()),
    'status_sha256': digest(status.encode()).hexdigest(),
    'mountinfo_sha256': digest(mountinfo.encode()).hexdigest(),
    'route_sha256': digest(route.encode()).hexdigest(),
    'ipv6_route_sha256': digest(ipv6_route.encode()).hexdigest(),
}
Path('/qea/cross-attempt-marker').write_text('container-local')
print(json.dumps(payload, sort_keys=True, separators=(',', ':')))
'''

_NETWORK_PROBE_SCRIPT = r'''import json
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


role, model_host, proxy_url = sys.argv[1:4]


def dns(name):
    try:
        socket.getaddrinfo(name, 443)
        return True
    except OSError:
        return False


def tcp(host, port, family=0):
    try:
        if family:
            sock = socket.socket(family, socket.SOCK_STREAM)
            sock.settimeout(0.35)
            sock.connect((host, port, 0, 0) if family == socket.AF_INET6 else (host, port))
        else:
            sock = socket.create_connection((host, port), timeout=0.35)
        sock.close()
        return True
    except OSError:
        return False


def url(value):
    try:
        with urllib.request.urlopen(value, timeout=0.75) as response:
            response.read(1)
        return True
    except urllib.error.HTTPError:
        return True
    except (OSError, urllib.error.URLError, ValueError):
        return False


def retry_url(value, attempts=20, delay_seconds=0.5):
    for attempt in range(attempts):
        if url(value):
            return True
        if attempt + 1 < attempts:
            time.sleep(delay_seconds)
    return False


docker_socket = False
for candidate in ('/var/run/docker.sock', '/run/docker.sock', '/run/user/1013/docker.sock'):
    path = Path(candidate)
    if not path.exists():
        continue
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(0.25)
        sock.connect(candidate)
        sock.close()
        docker_socket = True
    except OSError:
        pass

payload = {
    'dns': dns('example.com'),
    'public_ipv4_tcp': tcp('1.1.1.1', 443),
    'public_ipv6_tcp': tcp('2606:4700:4700::1111', 443, socket.AF_INET6),
    'http': url('http://example.com/'),
    'https': url('https://example.com/'),
    'github': url('https://github.com/'),
    'pypi': url('https://pypi.org/simple/'),
    'model_host': tcp(model_host, 443),
    'metadata_ipv4': tcp('169.254.169.254', 80),
    'metadata_dns': dns('metadata.google.internal'),
    'docker_socket': docker_socket,
}
if role == 'worker':
    payload['proxy_request'] = retry_url(proxy_url)
print(json.dumps(payload, sort_keys=True, separators=(',', ':')))
'''


class RootlessCanaryLiveGates:
    """Live rootless gate driver; every stage returns bounded public evidence."""

    def __init__(
        self,
        config: RootlessCanaryConfig,
        *,
        source_commit: str,
        output_root: str | Path,
    ) -> None:
        from .backends.rootless_docker import (
            RootlessDockerBackend,
            SubprocessCommandRunner,
        )

        self.config = config
        self.source_commit = _require_commit(source_commit)
        self.output_root = Path(output_root).expanduser().resolve()
        self.runner = SubprocessCommandRunner()
        self.backend = RootlessDockerBackend(
            docker_host=config.docker_host,
            expected_uid=config.expected_uid,
            runner=self.runner,
        )
        self._images: dict[str, dict[str, object]] | None = None

    def __call__(self, stage: str) -> Mapping[str, object]:
        handlers = {
            "daemon": self._daemon,
            "immutable-images": self._immutable_images,
            "resources-2cpu-4gib": lambda: self._resource_gate(2, 4096),
            "resources-4cpu-8gib": lambda: self._resource_gate(4, 8192),
            "filesystem-and-capabilities": self._filesystem_gate,
            "verifier-no-egress": self._verifier_network_gate,
            "worker-proxy-synthetic": self._worker_proxy_gate,
            "nexau-no-model": self._nexau_no_model,
            "force-kill-reap-resume": self._reaper_resume_gate,
            "verifier-replay": self._verifier_replay,
            "historical-var-seed-worker": self._fresh_worker,
        }
        try:
            handler = handlers[stage]
        except KeyError as exc:
            raise CanaryGateError(f"unknown live canary stage {stage!r}") from exc
        return handler()

    def _host_command(self, argv: tuple[str, ...], *, label: str) -> bytes:
        result = self.runner.run(argv, timeout_seconds=60)
        if result.returncode != 0:
            detail = result.stderr[:8_192].decode("utf-8", errors="replace")
            raise CanaryGateError(f"{label} failed: {detail}")
        return result.stdout

    def _daemon(self) -> Mapping[str, object]:
        import stat

        from .rootless_images import _verify_role_root

        source = self.config.resolved_path("source_root")
        if not source.is_dir() or not (source / ".git").exists():
            raise CanaryGateError("source worktree is missing Git metadata")
        head = self._host_command(
            ("git", "-C", str(source), "rev-parse", "HEAD"), label="source HEAD"
        ).decode().strip()
        if head != self.source_commit:
            raise CanaryGateError("source HEAD differs from requested source commit")
        branch = self._host_command(
            ("git", "-C", str(source), "branch", "--show-current"),
            label="source branch",
        ).decode().strip()
        if branch != self.config.branch:
            raise CanaryGateError("source branch differs from canary branch")
        dirty = self._host_command(
            (
                "git",
                "-C",
                str(source),
                "status",
                "--porcelain",
                "--untracked-files=no",
            ),
            label="source status",
        ).decode().strip()
        if dirty:
            raise CanaryGateError("source worktree has tracked changes")
        public = _verify_role_root(self.config.resolved_path("public_root"), "public")
        trusted = _verify_role_root(
            self.config.resolved_path("trusted_root"), "trusted-verifier"
        )
        if public.commit != self.config.benchmark_commit or trusted.commit != public.commit:
            raise CanaryGateError("public/trusted benchmark commits differ")
        secret = self.config.resolved_path("secret_file")
        metadata = secret.lstat()
        if secret.is_symlink() or not secret.is_file() or stat.S_IMODE(metadata.st_mode) != 0o600:
            raise CanaryGateError("model token must be a regular mode-600 file")
        version = self._host_command(
            (
                "docker",
                "--host",
                self.config.docker_host,
                "version",
                "--format",
                "{{.Server.Version}}",
            ),
            label="rootless Docker version",
        ).decode().strip()
        security_raw = self._host_command(
            (
                "docker",
                "--host",
                self.config.docker_host,
                "info",
                "--format",
                "{{json .SecurityOptions}}",
            ),
            label="rootless Docker info",
        )
        try:
            security = json.loads(security_raw)
        except json.JSONDecodeError as exc:
            raise CanaryGateError("Docker security options are malformed") from exc
        if not isinstance(security, list) or "name=rootless" not in security:
            raise CanaryGateError("Docker daemon is not rootless")
        actual_uid = os.getuid()
        try:
            username = pwd.getpwuid(actual_uid).pw_name
        except KeyError as exc:
            raise CanaryGateError("coordinator UID has no passwd entry") from exc
        controller_path = Path("/sys/fs/cgroup/cgroup.controllers")
        namespace_path = Path("/proc/sys/user/max_user_namespaces")
        try:
            controllers = sorted(controller_path.read_text().split())
            max_namespaces = int(namespace_path.read_text().strip())
        except (OSError, ValueError) as exc:
            raise CanaryGateError("host namespace or cgroup evidence is unavailable") from exc
        host = validate_daemon_host_evidence(
            {
                "actual_uid": actual_uid,
                "max_user_namespaces": max_namespaces,
                "subuid_range_size": _subordinate_id_range_size(
                    Path("/etc/subuid"), username=username, uid=actual_uid
                ),
                "subgid_range_size": _subordinate_id_range_size(
                    Path("/etc/subgid"), username=username, uid=actual_uid
                ),
                "cgroup_v2": controller_path.is_file(),
                "cgroup_controllers": controllers,
            },
            expected_uid=self.config.expected_uid,
        )
        return {
            **host,
            "source_commit": head,
            "branch": branch,
            "benchmark_commit": public.commit,
            "public_manifest_sha256": public.manifest_sha256,
            "trusted_manifest_sha256": trusted.manifest_sha256,
            "docker_version": version,
            "docker_security_options": security,
            "docker_host": self.config.docker_host,
            "secret_mode": "0600",
        }

    def _load_images(self) -> dict[str, dict[str, object]]:
        if self._images is not None:
            return self._images
        root = self.config.resolved_path("image_manifest_root")
        if not root.is_dir() or root.is_symlink():
            raise CanaryGateError("image manifest root is missing")
        selected: dict[str, list[dict[str, object]]] = {
            "base": [],
            "worker": [],
            "verifier": [],
        }
        for path in sorted(root.rglob("MANIFEST.json")):
            if path.is_symlink():
                raise CanaryGateError("image manifest symlink is forbidden")
            try:
                payload = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError) as exc:
                raise CanaryGateError(f"invalid image manifest {path}") from exc
            role = payload.get("role")
            task_id = payload.get("task_id")
            if role == "base" and task_id is None:
                selected["base"].append({**payload, "manifest_path": str(path)})
            elif role in {"worker", "verifier"} and task_id == self.config.task["task_id"]:
                selected[role].append({**payload, "manifest_path": str(path)})
        images: dict[str, dict[str, object]] = {}
        for role, matches in selected.items():
            if len(matches) != 1:
                raise CanaryGateError(
                    f"expected exactly one {role} image manifest, found {len(matches)}"
                )
            manifest = matches[0]
            image_id = manifest.get("image_id")
            if (
                manifest.get("benchmark_commit") != self.config.benchmark_commit
                or not isinstance(image_id, str)
                or not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id)
            ):
                raise CanaryGateError(f"{role} image manifest identity is invalid")
            images[role] = manifest
        self._images = images
        return images

    def _immutable_images(self) -> Mapping[str, object]:
        images = self._load_images()
        evidence: dict[str, object] = {}
        for role, manifest in images.items():
            image_id = str(manifest["image_id"])
            raw = self._host_command(
                (
                    "docker",
                    "--host",
                    self.config.docker_host,
                    "image",
                    "inspect",
                    "--format",
                    "{{json .}}",
                    image_id,
                ),
                label=f"{role} image inspect",
            )
            try:
                inspected = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise CanaryGateError(f"{role} image inspect is malformed") from exc
            if inspected.get("Id") != image_id:
                raise CanaryGateError(f"{role} image inspect ID differs")
            evidence[role] = {
                "image_id": image_id,
                "identity_sha256": manifest.get("identity_sha256"),
                "dependency_lock_sha256": manifest.get("dependency_lock_sha256"),
                "docker_version": manifest.get("docker_version"),
            }
        return evidence

    def _sandbox_spec(
        self,
        *,
        stage: str,
        image_ref: str,
        cpu_count: int,
        memory_mb: int,
        network_policy: str = "none",
        role: str = "canary",
        environment: Mapping[str, str] | None = None,
        tmpfs: Mapping[str, int] | None = None,
    ):
        from .sandbox_backend import SandboxSpec

        return SandboxSpec(
            role=role,
            run_id=self.config.run_id,
            attempt_id=stage,
            task_id=self.config.task["task_id"],
            image_ref=image_ref,
            cpu_count=cpu_count,
            memory_mb=memory_mb,
            pids_limit=256,
            timeout_seconds=300,
            network_policy=network_policy,
            environment=environment or {},
            writable_tmpfs_mb=tmpfs or {"/tmp": 64, "/qea": 64},
        )

    def _run_json_sandbox(
        self,
        *,
        spec,
        script: str,
        argv: tuple[str, ...] = (),
    ) -> tuple[dict[str, object], str, Path, bytes]:
        from .sandbox_lifecycle import (
            create_lifecycle,
            mark_cleaned,
            mark_finished,
            mark_started,
        )

        lifecycle = (
            self.output_root
            / "lifecycles"
            / spec.attempt_id
            / "canary-sandbox-lifecycle-v2.json"
        )
        identity = hashlib.sha256(
            f"{spec.spec_sha256}:{hashlib.sha256(script.encode()).hexdigest()}".encode()
        ).hexdigest()
        handle = None
        finished = False
        primary: Exception | None = None
        payload: dict[str, object] = {}
        inspect_payload = b""
        try:
            handle = self.backend.create(spec)
            create_lifecycle(
                lifecycle,
                handle=handle,
                spec=spec,
                attempt_identity_sha256=identity,
            )
            self.backend.start(handle)
            mark_started(lifecycle)
            self.backend.put_bytes(handle, "/qea/canary.py", script.encode())
            result = self.backend.run(
                handle,
                ("python3", "/qea/canary.py", *argv),
                environment={},
                timeout_seconds=120,
            )
            if result.timed_out or result.exit_code != 0:
                raise CanaryGateError(
                    f"canary command failed exit={result.exit_code} timed_out={result.timed_out}"
                )
            try:
                parsed = json.loads(result.stdout)
            except json.JSONDecodeError as exc:
                raise CanaryGateError("canary command returned invalid JSON") from exc
            if not isinstance(parsed, dict):
                raise CanaryGateError("canary evidence must be an object")
            payload = parsed
            inspect_payload = self._docker_inspect_bytes(handle.native_id)
            try:
                inspect_object = json.loads(inspect_payload)
            except json.JSONDecodeError as exc:
                raise CanaryGateError("container inspect returned invalid JSON") from exc
            validate_docker_inspect_contract(
                inspect_object,
                native_id=handle.native_id,
                image_ref=spec.image_ref,
                cpu_count=spec.cpu_count,
                memory_mb=spec.memory_mb,
                pids_limit=spec.pids_limit,
                network_policy=spec.network_policy,
                writable_tmpfs_mb=spec.writable_tmpfs_mb,
            )
            mark_finished(lifecycle)
            finished = True
        except Exception as exc:  # noqa: BLE001
            primary = exc
        finally:
            if handle is not None:
                if not finished:
                    try:
                        mark_finished(lifecycle, failure=str(primary))
                    except Exception:
                        pass
                try:
                    killed = self.backend.kill(handle.native_id)
                    mark_cleaned(
                        lifecycle,
                        cleanup_method="exact-id",
                        cleanup_result=killed.outcome,
                    )
                except Exception as cleanup_exc:  # noqa: BLE001
                    raise CanaryGateError("canary exact-ID cleanup failed") from cleanup_exc
        if primary is not None:
            if isinstance(primary, CanaryGateError):
                raise primary
            raise CanaryGateError(
                f"canary sandbox failed: {type(primary).__name__}: {primary}"
            ) from primary
        assert handle is not None
        return payload, handle.native_id, lifecycle, inspect_payload

    def _resource_gate(self, cpu_count: int, memory_mb: int) -> Mapping[str, object]:
        image = str(self._load_images()["base"]["image_id"])
        stage = f"resource-{cpu_count}cpu-{memory_mb}mb"
        payload, native_id, lifecycle, _ = self._run_json_sandbox(
            spec=self._sandbox_spec(
                stage=stage,
                image_ref=image,
                cpu_count=cpu_count,
                memory_mb=memory_mb,
            ),
            script=_CONTAINER_EVIDENCE_SCRIPT,
        )
        validated = validate_resource_evidence(
            payload,
            cpu_count=cpu_count,
            memory_mb=memory_mb,
            pids_limit=256,
        )
        return {
            **validated,
            "sandbox_id": native_id,
            "lifecycle_sha256": hashlib.sha256(lifecycle.read_bytes()).hexdigest(),
            "mountinfo_sha256": payload.get("mountinfo_sha256"),
        }

    def _filesystem_gate(self) -> Mapping[str, object]:
        image = str(self._load_images()["base"]["image_id"])
        observations = []
        for suffix in ("a", "b"):
            payload, native_id, _, _ = self._run_json_sandbox(
                spec=self._sandbox_spec(
                    stage=f"filesystem-{suffix}",
                    image_ref=image,
                    cpu_count=2,
                    memory_mb=4096,
                ),
                script=_CONTAINER_EVIDENCE_SCRIPT,
            )
            validated = validate_isolation_evidence(
                payload, expected_writable_paths=("/tmp", "/qea")
            )
            observations.append({**validated, "sandbox_id": native_id})
        return {"isolated": True, "attempts": observations}

    def _network_probe(
        self,
        *,
        spec,
        role: Literal["verifier", "worker"],
        proxy_url: str = "http://qea-model-proxy:8080/v1",
    ) -> tuple[dict[str, object], str, Path, bytes]:
        model_host = urlsplit(self.config.task["proxy_upstream_base_url"]).hostname or ""
        payload, native_id, lifecycle, inspect_payload = self._run_json_sandbox(
            spec=spec,
            script=_NETWORK_PROBE_SCRIPT,
            argv=(role, model_host, proxy_url),
        )
        return payload, native_id, lifecycle, inspect_payload

    def _verifier_network_gate(self) -> Mapping[str, object]:
        image = str(self._load_images()["verifier"]["image_id"])
        payload, native_id, lifecycle, _ = self._network_probe(
            spec=self._sandbox_spec(
                stage="verifier-no-egress",
                image_ref=image,
                cpu_count=2,
                memory_mb=4096,
                role="verifier",
            ),
            role="verifier",
        )
        return {
            **validate_network_evidence(payload, role="verifier"),
            "sandbox_id": native_id,
            "lifecycle_sha256": hashlib.sha256(lifecycle.read_bytes()).hexdigest(),
        }

    def _docker_inspect_bytes(self, native_id: str) -> bytes:
        return self._host_command(
            (
                "docker",
                "--host",
                self.config.docker_host,
                "container",
                "inspect",
                native_id,
            ),
            label="container secret-scan inspect",
        )

    def _validate_inspect_bytes(self, payload: bytes, *, native_id: str, spec) -> None:
        try:
            inspected = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise CanaryGateError("container inspect returned invalid JSON") from exc
        validate_docker_inspect_contract(
            inspected,
            native_id=native_id,
            image_ref=spec.image_ref,
            cpu_count=spec.cpu_count,
            memory_mb=spec.memory_mb,
            pids_limit=spec.pids_limit,
            network_policy=spec.network_policy,
            writable_tmpfs_mb=spec.writable_tmpfs_mb,
        )

    def _worker_proxy_gate(self) -> Mapping[str, object]:
        from .model_proxy import (
            build_model_proxy_sandbox_plan,
            scan_secret_exposure,
            start_model_proxy_sandbox,
        )
        from .sandbox_lifecycle import mark_cleaned, mark_finished

        images = self._load_images()
        synthetic = b"qea-synthetic-canary-token"
        network_created = False
        proxy_handle = None
        proxy_lifecycle = self.output_root / "lifecycles/proxy-synthetic/proxy-sandbox-lifecycle-v2.json"
        worker_inspect = b""
        proxy_inspect = b""
        try:
            self.backend.create_internal_network(self.config.run_id)
            network_created = True
            plan = build_model_proxy_sandbox_plan(
                run_id=self.config.run_id,
                attempt_id="proxy-synthetic",
                image_ref=str(images["base"]["image_id"]),
                upstream_base_url=_SYNTHETIC_PROXY_UPSTREAM_BASE_URL,
                allowed_path_prefix="/v1",
                listen_port=8080,
                cpu_count=1,
                memory_mb=512,
                pids_limit=64,
                timeout_seconds=300,
            )
            proxy_handle = start_model_proxy_sandbox(
                backend=self.backend,
                plan=plan,
                token=synthetic,
                lifecycle_path=proxy_lifecycle,
            )
            proxy_inspect = self._docker_inspect_bytes(proxy_handle.native_id)
            self._validate_inspect_bytes(
                proxy_inspect,
                native_id=proxy_handle.native_id,
                spec=plan.spec,
            )
            spec = self._sandbox_spec(
                stage="worker-proxy-synthetic",
                image_ref=str(images["base"]["image_id"]),
                cpu_count=1,
                memory_mb=512,
                network_policy="worker-proxy-only",
                role="worker",
                environment={
                    "LLM_API_KEY": "qea-proxy-placeholder",
                    "LLM_BASE_URL": "http://qea-model-proxy:8080/v1",
                    "LLM_MODEL": "synthetic",
                },
            )
            payload, native_id, worker_lifecycle, worker_inspect = self._network_probe(
                spec=spec, role="worker"
            )
            report = scan_secret_exposure(
                synthetic,
                {
                    "worker-inspect": worker_inspect,
                    "worker-lifecycle": worker_lifecycle,
                    "worker-evidence": json.dumps(payload, sort_keys=True),
                    "proxy-inspect": proxy_inspect,
                    "proxy-lifecycle": proxy_lifecycle,
                },
            )
            payload["secret_exposed"] = False
            validated = validate_network_evidence(payload, role="worker")
            return {
                **validated,
                "worker_sandbox_id": native_id,
                "proxy_sandbox_id": proxy_handle.native_id,
                "secret_scan_surfaces": report.scanned_surfaces,
                "secret_scan_files": report.scanned_files,
            }
        finally:
            if proxy_handle is not None:
                try:
                    mark_finished(proxy_lifecycle)
                    result = self.backend.kill(proxy_handle.native_id)
                    mark_cleaned(
                        proxy_lifecycle,
                        cleanup_method="exact-id",
                        cleanup_result=result.outcome,
                    )
                except Exception as exc:  # noqa: BLE001
                    raise CanaryGateError("synthetic proxy cleanup failed") from exc
            if network_created:
                try:
                    self.backend.remove_internal_network(self.config.run_id)
                except Exception as exc:  # noqa: BLE001
                    raise CanaryGateError("synthetic network cleanup failed") from exc

    def _nexau_no_model(self) -> Mapping[str, object]:
        from .qfbench_images import NEXAU_REQUIREMENTS_LOCK, NEXAU_RUNTIME_PYTHON

        image = str(self._load_images()["worker"]["image_id"])
        script = r'''import hashlib, json
from pathlib import Path
import nexau
payload = b'no-model-canary\n'
Path('/qea/no-model-artifact').write_bytes(payload)
print(json.dumps({'artifact_sha256': hashlib.sha256(payload).hexdigest(), 'nexau_imported': True}))
'''
        spec = self._sandbox_spec(
            stage="nexau-no-model",
            image_ref=image,
            cpu_count=2,
            memory_mb=4096,
            role="worker",
        )
        from .sandbox_lifecycle import create_lifecycle, mark_cleaned, mark_finished, mark_started

        lifecycle = self.output_root / "lifecycles/nexau-no-model/worker-sandbox-lifecycle-v2.json"
        handle = self.backend.create(spec)
        create_lifecycle(
            lifecycle,
            handle=handle,
            spec=spec,
            attempt_identity_sha256=hashlib.sha256(script.encode()).hexdigest(),
        )
        try:
            self.backend.start(handle)
            mark_started(lifecycle)
            inspect_payload = self._docker_inspect_bytes(handle.native_id)
            try:
                inspect_object = json.loads(inspect_payload)
            except json.JSONDecodeError as exc:
                raise CanaryGateError("NexAU container inspect returned invalid JSON") from exc
            validate_docker_inspect_contract(
                inspect_object,
                native_id=handle.native_id,
                image_ref=spec.image_ref,
                cpu_count=spec.cpu_count,
                memory_mb=spec.memory_mb,
                pids_limit=spec.pids_limit,
                network_policy=spec.network_policy,
                writable_tmpfs_mb=spec.writable_tmpfs_mb,
            )
            self.backend.put_bytes(handle, "/qea/no-model.py", script.encode())
            result = self.backend.run(
                handle,
                (NEXAU_RUNTIME_PYTHON, "/qea/no-model.py"),
                environment={},
                timeout_seconds=60,
            )
            if result.timed_out or result.exit_code != 0:
                raise CanaryGateError("exact-image NexAU no-model command failed")
            payload = json.loads(result.stdout)
            lock = self.backend.read_bytes(handle, NEXAU_REQUIREMENTS_LOCK)
            artifact = self.backend.read_bytes(handle, "/qea/no-model-artifact")
            if hashlib.sha256(artifact).hexdigest() != payload.get("artifact_sha256"):
                raise CanaryGateError("no-model artifact digest mismatch")
            mark_finished(lifecycle)
        finally:
            killed = self.backend.kill(handle.native_id)
            mark_cleaned(
                lifecycle,
                cleanup_method="exact-id",
                cleanup_result=killed.outcome,
            )
        return {
            "sandbox_id": handle.native_id,
            "nexau_imported": payload.get("nexau_imported") is True,
            "artifact_sha256": payload["artifact_sha256"],
            "dependency_lock_sha256": hashlib.sha256(lock).hexdigest(),
            "model_calls": 0,
            "verifier_calls": 0,
        }

    def _reaper_resume_gate(self) -> Mapping[str, object]:
        from .sandbox_reaper import reap_sandboxes

        image = str(self._load_images()["base"]["image_id"])
        spec = self._sandbox_spec(
            stage="force-kill-reap-resume",
            image_ref=image,
            cpu_count=1,
            memory_mb=512,
        )
        root = self.output_root / "reaper-resume"
        lifecycle = root / "force-kill-sandbox-lifecycle-v2.json"
        identity = hashlib.sha256(spec.canonical_json().encode()).hexdigest()
        ready = root / "child-ready.json"
        error = root / "child-error.json"
        coordinator = None
        coordinator_exitcode: int | None = None
        if ready.is_file():
            try:
                marker = json.loads(ready.read_text())
            except (OSError, json.JSONDecodeError) as exc:
                raise CanaryGateError("existing child marker is malformed") from exc
            if (
                marker.get("attempt_identity_sha256") != identity
                or not isinstance(marker.get("native_id"), str)
                or type(marker.get("coordinator_pid")) is not int
            ):
                raise CanaryGateError("existing child marker identity differs")
            coordinator_pid = marker["coordinator_pid"]
            native_id = marker["native_id"]
            if Path(f"/proc/{coordinator_pid}").exists():
                raise CanaryGateError(
                    "previous coordinator PID is still live; refusing an ambiguous kill"
                )
            child_reused = True
        else:
            root.mkdir(parents=True, exist_ok=True)
            context = multiprocessing.get_context("spawn")
            coordinator = context.Process(
                target=_force_kill_child,
                kwargs={
                    "docker_host": self.config.docker_host,
                    "expected_uid": self.config.expected_uid,
                    "spec_payload": json.loads(spec.canonical_json()),
                    "lifecycle_path": str(lifecycle),
                    "ready_marker_path": str(ready),
                    "error_marker_path": str(error),
                },
                name="qea-force-kill-coordinator",
            )
            coordinator.start()
            deadline = time.monotonic() + 60
            while (
                not ready.is_file()
                and coordinator.is_alive()
                and time.monotonic() < deadline
            ):
                time.sleep(0.1)
            if not ready.is_file():
                if coordinator.is_alive():
                    coordinator.terminate()
                coordinator.join(timeout=10)
                cleanup = reap_sandboxes(root, backend=self.backend, apply=True)
                if cleanup.failed or cleanup.identity_mismatch_ids:
                    raise CanaryGateError(
                        "failed child left an ambiguous sandbox lifecycle"
                    )
                detail = "child exited before persisting its ready marker"
                if error.is_file():
                    try:
                        detail = str(json.loads(error.read_text()).get("error", detail))
                    except (OSError, json.JSONDecodeError):
                        pass
                raise CanaryGateError(f"force-kill coordinator failed: {detail}")
            try:
                marker = json.loads(ready.read_text())
            except (OSError, json.JSONDecodeError) as exc:
                coordinator.terminate()
                coordinator.join(timeout=10)
                raise CanaryGateError("child ready marker is malformed") from exc
            if (
                marker.get("attempt_identity_sha256") != identity
                or marker.get("coordinator_pid") != coordinator.pid
                or not isinstance(marker.get("native_id"), str)
            ):
                coordinator.terminate()
                coordinator.join(timeout=10)
                raise CanaryGateError("child ready marker identity differs")
            coordinator_pid = marker["coordinator_pid"]
            native_id = marker["native_id"]
            coordinator.terminate()
            coordinator.join(timeout=10)
            if coordinator.is_alive():
                coordinator.kill()
                coordinator.join(timeout=10)
            if coordinator.is_alive():
                raise CanaryGateError("force-kill coordinator did not terminate")
            coordinator_exitcode = coordinator.exitcode
            if coordinator_exitcode not in {-signal.SIGTERM, -signal.SIGKILL}:
                raise CanaryGateError(
                    "force-kill coordinator exited without the requested signal"
                )
            child_reused = False
        completed = root / "completed-operation.json"
        completed_payload = b'{"model_calls":0,"verifier_calls":0}\n'
        if completed.is_file():
            if completed.read_bytes() != completed_payload:
                raise CanaryGateError("completed operation identity differs on resume")
            completed_reused = True
        else:
            completed.write_bytes(completed_payload)
            completed_reused = False
        completed_sha = hashlib.sha256(completed_payload).hexdigest()
        dry = reap_sandboxes(root, backend=self.backend)
        if dry.apply or dry.failed or dry.identity_mismatch_ids:
            raise CanaryGateError("dry reaper returned an unsafe report")
        if dry.pending_ids == (native_id,):
            applied = reap_sandboxes(root, backend=self.backend, apply=True)
            if applied.killed_ids != (native_id,):
                raise CanaryGateError("applied reaper did not kill one exact native ID")
            cleaned_reused = False
        elif dry.pending_ids == () and child_reused:
            from .sandbox_lifecycle import load_lifecycle

            prior = load_lifecycle(lifecycle)
            if (
                prior.native_id != native_id
                or prior.attempt_identity_sha256 != identity
                or not prior.cleaned_up
                or prior.cleanup_method != "reaper"
                or prior.cleanup_result not in {"killed", "already_absent"}
            ):
                raise CanaryGateError("cleaned lifecycle cannot be safely resumed")
            applied = None
            cleaned_reused = True
        else:
            raise CanaryGateError("dry reaper did not identify one exact native ID")
        final = reap_sandboxes(root, backend=self.backend)
        if final.pending_ids or final.failed or final.identity_mismatch_ids:
            raise CanaryGateError("reaper left pending or ambiguous lifecycle state")
        if hashlib.sha256(completed.read_bytes()).hexdigest() != completed_sha:
            raise CanaryGateError("resume changed a completed operation hash")
        evidence = {
            "native_id": native_id,
            "coordinator_pid": coordinator_pid,
            "coordinator_exitcode": coordinator_exitcode,
            "child_marker_reused": child_reused,
            "completed_operation_reused": completed_reused,
            "dry_pending_ids": list(dry.pending_ids),
            "killed_ids": list(applied.killed_ids) if applied is not None else [],
            "cleaned_lifecycle_reused": cleaned_reused,
            "final_pending_ids": list(final.pending_ids),
            "attempt_identity_sha256": identity,
            "completed_operation_sha256": completed_sha,
            "model_calls_duplicated": 0,
            "verifier_calls_duplicated": 0,
        }
        return validate_force_kill_evidence(evidence)

    def _task_view(self):
        from types import SimpleNamespace

        from .benchmarks.qfbench import _task_resource_contract

        root = self.config.resolved_path("public_root") / "tasks" / self.config.task["task_id"]
        resources = _task_resource_contract(root, self.config.task["task_id"])
        return SimpleNamespace(
            task_id=self.config.task["task_id"],
            domain=self.config.task["domain"],
            **resources,
        )

    def _verifier_replay(self) -> Mapping[str, object]:
        from .evaluation import ArtifactRecord, TaskAttempt
        from .executors.e2b_nexau import E2BWorkerExecution
        from .executors.sandbox_nexau import (
            SandboxQFBenchVerifier,
            SandboxResourceContract,
        )

        manifest_path = self.config.resolved_path("historical_artifact_manifest")
        reference_path = self.config.resolved_path("historical_e2b_score")
        try:
            artifact_manifest = json.loads(manifest_path.read_text())
            reference = json.loads(reference_path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise CanaryGateError("historical replay inputs are unavailable") from exc
        artifact_dir = (self.config.runtime_root / artifact_manifest["artifact_dir"]).resolve()
        try:
            artifact_dir.relative_to(self.config.runtime_root)
        except ValueError as exc:
            raise CanaryGateError("historical artifact directory escapes runtime root") from exc
        records = tuple(ArtifactRecord(**item) for item in artifact_manifest["artifacts"])
        task = self._task_view()
        worker_digest = str(artifact_manifest.get("worker_digest", "a" * 64))
        attempt = TaskAttempt.create(
            run_id=self.config.run_id,
            benchmark_commit=self.config.benchmark_commit,
            task_id=task.task_id,
            split="canary-replay",
            checkpoint="historical-e2b-artifact",
            worker_digest=worker_digest,
        )
        execution = E2BWorkerExecution(
            attempt_id=attempt.attempt_id,
            artifact_dir=artifact_dir,
            artifacts=records,
            trace_uri=str(manifest_path),
            log_uri=str(manifest_path),
            final_text_uri=str(manifest_path),
            summary={},
            sandbox_id=str(artifact_manifest.get("source_sandbox_id", "historical")),
            cleaned_up=True,
        )
        image = str(self._load_images()["verifier"]["image_id"])
        verifier = SandboxQFBenchVerifier(
            backend=self.backend,
            lifecycle_root=self.output_root / "lifecycles",
            verifier_image_ref=image,
            trusted_task_root=self.config.resolved_path("trusted_root"),
            resource_contract=SandboxResourceContract(
                cpu_count=task.cpus,
                memory_mb=task.memory_mb,
                pids_limit=256,
                timeout_seconds=task.verifier_timeout_seconds,
                writable_tmpfs_mb={
                    "/tmp": 256,
                    "/qea": 512,
                    "/app": 1024,
                    "/tests": 128,
                    "/logs": 128,
                    "/opt/qea/uv-cache": 256,
                    "/opt/qea/uv-tools": 64,
                },
            ),
        )
        run_dir = self.output_root / "replay"
        score = verifier.verify(
            attempt=attempt, task=task, execution=execution, run_dir=run_dir
        )
        evidence_path = run_dir / "attempts" / attempt.attempt_id / "verifier/verifier-evidence.json"
        verifier_evidence = json.loads(evidence_path.read_text())
        observed = {
            "artifact_sha256": artifact_manifest["artifact_sha256"],
            "reward": score.reward,
            "tests_passed": score.tests_passed or 0,
            "tests_failed": score.tests_failed or 0,
            "executed_test_sha256": verifier_evidence["executed_test_sha256"],
            "dependency_lock_sha256": verifier_evidence["dependency_lock_sha256"],
        }
        return validate_replay_parity(reference, observed)

    @staticmethod
    def _records_digest(records) -> str:
        payload = [asdict(record) for record in sorted(records, key=lambda item: item.path)]
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def _fresh_worker(self) -> Mapping[str, object]:
        from .evaluation import TaskAttempt
        from .executors.sandbox_nexau import (
            SandboxNexAUExecutor,
            SandboxQFBenchVerifier,
            SandboxResourceContract,
        )
        from .loop_benchmark import hash_worker_directory
        from .model_proxy import (
            build_model_proxy_sandbox_plan,
            scan_secret_exposure,
            start_model_proxy_sandbox,
        )
        from .sandbox_lifecycle import mark_cleaned, mark_finished

        images = self._load_images()
        token_path = self.config.resolved_path("secret_file")
        token = token_path.read_bytes().rstrip(b"\r\n")
        worker_dir = self.config.resolved_path("source_root") / self.config.task["worker_dir"]
        task = self._task_view()
        attempt = TaskAttempt.create(
            run_id=self.config.run_id,
            benchmark_commit=self.config.benchmark_commit,
            task_id=task.task_id,
            split="canary-fresh",
            checkpoint="seed",
            worker_digest=hash_worker_directory(worker_dir),
        )
        network_created = False
        proxy_handle = None
        proxy_lifecycle = self.output_root / "lifecycles/proxy-paid/proxy-sandbox-lifecycle-v2.json"
        run_dir = self.output_root / "fresh"
        try:
            self.backend.create_internal_network(self.config.run_id)
            network_created = True
            plan = build_model_proxy_sandbox_plan(
                run_id=self.config.run_id,
                attempt_id="proxy-paid",
                image_ref=str(images["base"]["image_id"]),
                upstream_base_url=self.config.task["proxy_upstream_base_url"],
                allowed_path_prefix=self.config.task["proxy_allowed_path_prefix"],
                listen_port=8080,
                cpu_count=1,
                memory_mb=512,
                pids_limit=64,
                timeout_seconds=task.agent_timeout_seconds + 300,
            )
            proxy_handle = start_model_proxy_sandbox(
                backend=self.backend,
                plan=plan,
                token=token,
                lifecycle_path=proxy_lifecycle,
            )
            self._validate_inspect_bytes(
                self._docker_inspect_bytes(proxy_handle.native_id),
                native_id=proxy_handle.native_id,
                spec=plan.spec,
            )
            worker_resources = SandboxResourceContract(
                cpu_count=task.cpus,
                memory_mb=task.memory_mb,
                pids_limit=256,
                timeout_seconds=task.agent_timeout_seconds,
                writable_tmpfs_mb={"/tmp": 256, "/qea": 512, "/app": 2048},
            )
            executor = SandboxNexAUExecutor(
                backend=self.backend,
                lifecycle_root=self.output_root / "lifecycles",
                worker_image_ref=str(images["worker"]["image_id"]),
                public_task_root=self.config.resolved_path("public_root"),
                resource_contract=worker_resources,
                worker_network_name=f"qea-{self.config.run_id}-internal",
                proxy_base_url="http://qea-model-proxy:8080/v1",
                model_name=self.config.task["model_name"],
            )
            execution = executor.execute(
                attempt=attempt,
                task=task,
                worker_dir=worker_dir,
                run_dir=run_dir,
                model_env={},
            )
            verifier = SandboxQFBenchVerifier(
                backend=self.backend,
                lifecycle_root=self.output_root / "lifecycles",
                verifier_image_ref=str(images["verifier"]["image_id"]),
                trusted_task_root=self.config.resolved_path("trusted_root"),
                resource_contract=SandboxResourceContract(
                    cpu_count=task.cpus,
                    memory_mb=task.memory_mb,
                    pids_limit=256,
                    timeout_seconds=task.verifier_timeout_seconds,
                    writable_tmpfs_mb={
                        "/tmp": 256,
                        "/qea": 512,
                        "/app": 2048,
                        "/tests": 128,
                        "/logs": 128,
                        "/opt/qea/uv-cache": 256,
                        "/opt/qea/uv-tools": 64,
                    },
                ),
            )
            score = verifier.verify(
                attempt=attempt,
                task=task,
                execution=execution,
                run_dir=run_dir,
            )
            lifecycle_root = self.output_root / "lifecycles"
            oracle_lifecycles = [
                str(path.relative_to(lifecycle_root))
                for path in lifecycle_root.rglob("*.json")
                if "oracle" in path.name.lower()
                or any("oracle" in part.lower() for part in path.parts)
            ]
            solution_members = [
                record.path for record in execution.artifacts if "solution" in record.path.split("/")
            ]
            worker_bundle = (
                run_dir / "attempts" / attempt.attempt_id / "worker-input.tar"
            )
            solution_members.extend(audit_worker_bundle(worker_bundle))
            report = scan_secret_exposure(
                token,
                {
                    "fresh-run": run_dir,
                    "worker-lifecycles": self.output_root / "lifecycles",
                    "proxy-inspect": self._docker_inspect_bytes(proxy_handle.native_id),
                },
            )
            fresh = {
                "task_id": task.task_id,
                "worker_sandbox_id": execution.sandbox_id,
                "verifier_sandbox_id": json.loads(
                    (
                        run_dir
                        / "attempts"
                        / attempt.attempt_id
                        / "verifier/verifier-evidence.json"
                    ).read_text()
                )["sandbox_id"],
                "artifact_sha256": self._records_digest(execution.artifacts),
                "reward": score.reward,
                "tests_passed": score.tests_passed or 0,
                "tests_failed": score.tests_failed or 0,
                "worker_network_policy": "worker-proxy-only",
                "verifier_network_policy": "none",
                "solution_members": solution_members,
                "oracle_lifecycles": oracle_lifecycles,
                "model_identity": self.config.task["model_name"],
                "input_tokens": None,
                "output_tokens": None,
                "model_cost_usd": None,
                "sandbox_cost_usd": None,
            }
            return {
                **validate_fresh_worker_evidence(fresh),
                "secret_scan_surfaces": report.scanned_surfaces,
                "secret_scan_files": report.scanned_files,
            }
        finally:
            if proxy_handle is not None:
                try:
                    mark_finished(proxy_lifecycle)
                    killed = self.backend.kill(proxy_handle.native_id)
                    mark_cleaned(
                        proxy_lifecycle,
                        cleanup_method="exact-id",
                        cleanup_result=killed.outcome,
                    )
                except Exception as exc:  # noqa: BLE001
                    raise CanaryGateError("paid proxy cleanup failed") from exc
            if network_created:
                try:
                    self.backend.remove_internal_network(self.config.run_id)
                except Exception as exc:  # noqa: BLE001
                    raise CanaryGateError("paid network cleanup failed") from exc
