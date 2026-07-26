"""Full NexAU-in-E2B worker execution and isolated QFBench verification."""

from __future__ import annotations

import io
import hashlib
import json
import os
import tarfile
from datetime import datetime, timezone
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Mapping
from urllib.parse import urlparse

from ..e2b_lease import E2BLeasePool
from ..evaluation import ArtifactRecord, OfficialTaskScore, TaskAttempt
from ..qfbench_images import NEXAU_REQUIREMENTS_LOCK, NEXAU_RUNTIME_PYTHON
from ..verifiers.qfbench import (
    parse_official_qfbench_score,
    prepare_offline_verifier_script,
)
from .bundles import build_oracle_bundle, build_verifier_bundle, build_worker_bundle
from .e2b_protocol import E2BSandboxFactory, SDKSandboxFactory


_MODEL_ENV_ALLOWLIST = frozenset({"LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"})
_SYSTEM_CA_BUNDLE = "/etc/ssl/certs/ca-certificates.crt"
_REMOTE_RUNNER = Path(__file__).with_name("remote_nexau_worker.py")
_RUNTIME_BRIDGE = Path(__file__).parents[1] / "runtime_bridge.py"


class E2BExecutionError(RuntimeError):
    """A worker/verifier sandbox failed or returned an unsafe artifact archive."""


class E2BWorkerTimeout(E2BExecutionError):
    """The worker command reached the task's declared agent timeout."""

    def __init__(self, message: str, *, log_uri: str | None = None) -> None:
        super().__init__(message)
        self.log_uri = log_uri


@dataclass(frozen=True)
class E2BNexAUConfig:
    worker_templates: Mapping[str, str]
    verifier_templates: Mapping[str, str]
    timeout_seconds: int = 3_600
    worker_allow_internet: bool = True
    verifier_allow_internet: bool = False
    max_output_files: int = 2_000
    max_output_bytes: int = 512 * 1024 * 1024
    lease_timeout_seconds: float = 120

    def __post_init__(self) -> None:
        if self.timeout_seconds < 1:
            raise E2BExecutionError("timeout_seconds must be positive")
        if self.max_output_files < 1 or self.max_output_bytes < 1:
            raise E2BExecutionError("output limits must be positive")

    def worker_template(self, task_id: str) -> str:
        try:
            return self.worker_templates[task_id]
        except KeyError as exc:
            raise E2BExecutionError(f"no E2B worker template for task {task_id!r}") from exc

    def verifier_template(self, task_id: str) -> str:
        try:
            return self.verifier_templates[task_id]
        except KeyError as exc:
            raise E2BExecutionError(f"no E2B verifier template for task {task_id!r}") from exc


@dataclass(frozen=True)
class E2BWorkerExecution:
    attempt_id: str
    artifact_dir: Path
    artifacts: tuple[ArtifactRecord, ...]
    trace_uri: str
    log_uri: str
    final_text_uri: str
    summary: dict
    sandbox_id: str
    cleaned_up: bool


def _persist_worker_execution(execution: E2BWorkerExecution, attempt_dir: Path) -> None:
    payload = {
        "attempt_id": execution.attempt_id,
        "artifact_dir": str(execution.artifact_dir.relative_to(attempt_dir)),
        "artifacts": [asdict(record) for record in execution.artifacts],
        "trace_uri": str(Path(execution.trace_uri).relative_to(attempt_dir)),
        "log_uri": str(Path(execution.log_uri).relative_to(attempt_dir)),
        "final_text_uri": str(Path(execution.final_text_uri).relative_to(attempt_dir)),
        "summary": execution.summary,
        "sandbox_id": execution.sandbox_id,
        "cleaned_up": execution.cleaned_up,
    }
    _write_json(attempt_dir / "worker-execution.json", payload)


def load_worker_execution(
    attempt: TaskAttempt,
    run_dir: str | Path,
) -> E2BWorkerExecution | None:
    """Restore a completed worker attempt and verify every artifact hash."""

    attempt_dir = Path(run_dir).resolve() / "attempts" / attempt.attempt_id
    manifest_path = attempt_dir / "worker-execution.json"
    if not manifest_path.is_file():
        return None
    try:
        payload = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise E2BExecutionError(f"invalid worker execution manifest: {exc}") from exc
    if payload.get("attempt_id") != attempt.attempt_id:
        raise E2BExecutionError("worker execution manifest attempt mismatch")
    artifact_dir = (attempt_dir / payload["artifact_dir"]).resolve()
    records = tuple(ArtifactRecord(**item) for item in payload.get("artifacts", ()))
    for record in records:
        current = ArtifactRecord.from_file(artifact_dir / record.path, root=artifact_dir)
        if current != record:
            raise E2BExecutionError(f"artifact integrity mismatch on resume: {record.path}")
    return E2BWorkerExecution(
        attempt_id=attempt.attempt_id,
        artifact_dir=artifact_dir,
        artifacts=records,
        trace_uri=str((attempt_dir / payload["trace_uri"]).resolve()),
        log_uri=str((attempt_dir / payload["log_uri"]).resolve()),
        final_text_uri=str((attempt_dir / payload["final_text_uri"]).resolve()),
        summary=dict(payload.get("summary", {})),
        sandbox_id=str(payload.get("sandbox_id", "")),
        cleaned_up=bool(payload.get("cleaned_up", False)),
    )


def sanitize_worker_env(environment: Mapping[str, str]) -> dict[str, str]:
    """Return non-secret NexAU config values; E2B injects the real auth header."""

    clean: dict[str, str] = {"SSL_CERT_FILE": _SYSTEM_CA_BUNDLE}
    for name in sorted(_MODEL_ENV_ALLOWLIST):
        value = environment.get(name)
        if value is not None and str(value):
            clean[name] = (
                "e2b-header-injected" if name == "LLM_API_KEY" else str(value)
            )
    return clean


def _deny_all_traffic(context) -> list[str]:
    """Use the E2B SDK selector context instead of a magic pseudo-CIDR."""

    return [context.all_traffic]


def build_worker_network(environment: Mapping[str, str]) -> dict:
    """Allow one model host and inject its credential outside the task process."""

    api_key = str(environment.get("LLM_API_KEY", ""))
    base_url = str(environment.get("LLM_BASE_URL", ""))
    parsed = urlparse(base_url)
    if not api_key or parsed.scheme != "https" or not parsed.hostname:
        raise E2BExecutionError(
            "internet-enabled workers require LLM_API_KEY and an https LLM_BASE_URL"
        )
    host = parsed.hostname
    return {
        "allow_out": [host],
        "deny_out": _deny_all_traffic,
        "rules": {
            host: [{
                "transform": {
                    "headers": {"Authorization": f"Bearer {api_key}"}
                }
            }]
        },
        "allow_public_traffic": False,
    }


def _scrub(value: str, secrets: Mapping[str, str]) -> str:
    scrubbed = value
    for secret in secrets.values():
        if secret:
            scrubbed = scrubbed.replace(secret, "[REDACTED]")
    return scrubbed


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")
    os.replace(temporary, path)


def _write_sandbox_lifecycle(
    path: Path,
    *,
    attempt: TaskAttempt,
    task_id: str,
    role: str,
    sandbox_id: str,
    cleaned_up: bool,
    cleanup_error: str | None = None,
) -> None:
    payload = {
        "schema_version": 1,
        "run_id": attempt.run_id,
        "attempt_id": attempt.attempt_id,
        "task_id": task_id,
        "role": role,
        "sandbox_id": sandbox_id,
        "cleaned_up": cleaned_up,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if cleanup_error:
        payload["cleanup_error"] = cleanup_error
    _write_json(path, payload)


def _read_optional_text(sandbox, path: str) -> str | None:
    try:
        return str(sandbox.files.read(path, format="text"))
    except Exception as exc:  # E2B is an optional dependency; avoid importing its exception here.
        if isinstance(exc, KeyError) or exc.__class__.__name__ in {
            "FileNotFoundException",
            "NotFoundException",
        }:
            return None
        raise


def _write_sandbox_file(sandbox, path: str, payload) -> None:
    """Retry one idempotent upload after a closed pooled HTTP/2 connection."""

    for attempt in range(2):
        try:
            sandbox.files.write(path, payload)
            return
        except Exception as exc:  # E2B/httpx are optional imports here.
            transient = (
                exc.__class__.__name__ == "LocalProtocolError"
                and "ConnectionState.CLOSED" in str(exc)
            )
            if attempt or not transient:
                raise


def _command_payload(result, secrets: Mapping[str, str]) -> dict:
    return {
        "exit_code": int(getattr(result, "exit_code", -1)),
        "stdout": _scrub(str(getattr(result, "stdout", "") or ""), secrets),
        "stderr": _scrub(str(getattr(result, "stderr", "") or ""), secrets),
        "error": _scrub(str(getattr(result, "error", "") or ""), secrets),
    }


def _run_command_result(sandbox, command: str, **kwargs):
    """Normalize E2B SDK versions that raise on a non-zero command exit."""

    try:
        return sandbox.commands.run(command, **kwargs)
    except Exception as exc:  # E2B remains an optional dependency at import time.
        if (
            exc.__class__.__name__ != "CommandExitException"
            or not isinstance(getattr(exc, "exit_code", None), int)
        ):
            raise
        return exc


def _run_checked(sandbox, command: str, *, label: str, timeout: int, envs=None):
    result = _run_command_result(
        sandbox, command, timeout=timeout, envs=envs or {}
    )
    if int(getattr(result, "exit_code", -1)) != 0:
        raise E2BExecutionError(f"{label} failed with exit {getattr(result, 'exit_code', -1)}")
    return result


def _task_command_timeout(task, attribute: str, global_cap: int) -> int:
    value = getattr(task, attribute, global_cap)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise E2BExecutionError(f"task {attribute} must be a positive integer")
    return min(value, global_cap)


def _sandbox_lifetime(command_timeout: int, global_cap: int) -> int:
    return min(global_cap, command_timeout + 180)


def _unsafe_output_name(name: str) -> bool:
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        return True
    lowered = path.name.lower()
    return (
        lowered == ".env"
        or lowered.startswith(".env.")
        or lowered.startswith("credentials")
        or lowered.startswith("secrets")
        or lowered in {"id_rsa", "id_ed25519"}
        or lowered.endswith((".pem", ".key"))
    )


def extract_output_archive(
    payload: bytes,
    destination: str | Path,
    *,
    max_files: int = 2_000,
    max_bytes: int = 512 * 1024 * 1024,
) -> tuple[Path, ...]:
    """Extract regular files only, without tar traversal, links, or secret files."""

    root = Path(destination).resolve()
    root.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []
    total_bytes = 0
    seen: set[str] = set()
    try:
        archive = tarfile.open(fileobj=io.BytesIO(payload), mode="r:*")
    except tarfile.TarError as exc:
        raise E2BExecutionError(f"invalid output archive: {exc}") from exc
    with archive:
        for member in archive.getmembers():
            if member.isdir():
                continue
            if not member.isfile() or _unsafe_output_name(member.name):
                raise E2BExecutionError(f"unsafe output member {member.name!r}")
            name = PurePosixPath(member.name).as_posix()
            if name in seen:
                raise E2BExecutionError(f"duplicate output member {name!r}")
            seen.add(name)
            if len(seen) > max_files:
                raise E2BExecutionError(f"output file limit exceeded: {len(seen)} > {max_files}")
            total_bytes += member.size
            if total_bytes > max_bytes:
                raise E2BExecutionError(f"output byte limit exceeded: {total_bytes} > {max_bytes}")
            target = (root / Path(*PurePosixPath(name).parts)).resolve()
            try:
                target.relative_to(root)
            except ValueError as exc:
                raise E2BExecutionError(f"unsafe output member {member.name!r}") from exc
            target.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                raise E2BExecutionError(f"cannot read output member {member.name!r}")
            with target.open("wb") as handle:
                handle.write(source.read())
            extracted.append(target)
    return tuple(sorted(extracted, key=lambda path: path.relative_to(root).as_posix()))


class E2BNexAUExecutor:
    def __init__(
        self,
        config: E2BNexAUConfig,
        *,
        sandbox_factory: E2BSandboxFactory | None = None,
        lease_pool: E2BLeasePool,
    ) -> None:
        self.config = config
        self.sandbox_factory = sandbox_factory or SDKSandboxFactory()
        self.lease_pool = lease_pool

    def execute(
        self,
        *,
        attempt: TaskAttempt,
        task,
        worker_dir: str | Path,
        run_dir: str | Path,
        model_env: Mapping[str, str],
    ) -> E2BWorkerExecution:
        attempt_dir = Path(run_dir).resolve() / "attempts" / attempt.attempt_id
        attempt_dir.mkdir(parents=True, exist_ok=True)
        bundle = build_worker_bundle(task, worker_dir, attempt_dir / "worker-input.tar")
        worker_env = sanitize_worker_env(model_env)
        worker_network = (
            build_worker_network(model_env) if self.config.worker_allow_internet else None
        )
        command_log = attempt_dir / "worker-command.json"
        trace_path = attempt_dir / "raw-trace.jsonl"
        final_text_path = attempt_dir / "final.txt"
        dependency_lock_path = attempt_dir / "nexau-requirements.lock"
        artifact_dir = attempt_dir / "artifacts"
        sandbox = None
        sandbox_id = ""
        cleanup_ok = False
        lifecycle_path = attempt_dir / "worker-sandbox-lifecycle.json"
        command_timeout = _task_command_timeout(
            task, "agent_timeout_seconds", self.config.timeout_seconds
        )
        sandbox_timeout = _sandbox_lifetime(command_timeout, self.config.timeout_seconds)

        with self.lease_pool.acquire(
            f"worker:{attempt.attempt_id}", timeout_seconds=self.config.lease_timeout_seconds
        ) as lease:
            try:
                create_args = {
                    "template": self.config.worker_template(task.task_id),
                    "timeout": sandbox_timeout,
                    "metadata": {
                        "qea_role": "worker",
                        "qea_run_id": attempt.run_id,
                        "qea_attempt_id": attempt.attempt_id,
                        "qea_task_id": task.task_id,
                    },
                    "envs": worker_env,
                    "secure": True,
                    "allow_internet_access": self.config.worker_allow_internet,
                }
                if worker_network is not None:
                    create_args["network"] = worker_network
                sandbox = self.sandbox_factory.create(**create_args)
                sandbox_id = str(sandbox.sandbox_id)
                _write_sandbox_lifecycle(
                    lifecycle_path,
                    attempt=attempt,
                    task_id=task.task_id,
                    role="worker",
                    sandbox_id=sandbox_id,
                    cleaned_up=False,
                )
                dependency_lock = _read_optional_text(
                    sandbox, NEXAU_REQUIREMENTS_LOCK
                )
                if dependency_lock is None or not dependency_lock.strip():
                    raise E2BExecutionError(
                        "worker template is missing its NexAU dependency lock"
                    )
                dependency_lock_path.write_text(dependency_lock)
                dependency_lock_sha256 = hashlib.sha256(
                    dependency_lock_path.read_bytes()
                ).hexdigest()
                lease.heartbeat()
                _write_sandbox_file(
                    sandbox, "/tmp/qea-worker.tar", bundle.path.read_bytes()
                )
                _write_sandbox_file(
                    sandbox,
                    "/qea/remote_nexau_worker.py",
                    _REMOTE_RUNNER.read_bytes(),
                )
                _write_sandbox_file(
                    sandbox,
                    "/qea/runtime_bridge.py",
                    _RUNTIME_BRIDGE.read_bytes(),
                )
                _run_checked(
                    sandbox,
                    "mkdir -p /qea/result /app/data /app/output && "
                    "tar -xf /tmp/qea-worker.tar -C /qea && "
                    "if [ -d /qea/task/environment/data ]; then "
                    "cp -R /qea/task/environment/data/. /app/data/; fi",
                    label="worker setup command",
                    timeout=min(120, sandbox_timeout),
                )
                try:
                    worker_result = _run_command_result(
                        sandbox,
                        f"{NEXAU_RUNTIME_PYTHON} /qea/remote_nexau_worker.py "
                        "--task-dir /qea/task --worker-dir /qea/worker "
                        "--work-dir /app --output-dir /app/output --result-dir /qea/result",
                        timeout=command_timeout,
                        envs=worker_env,
                    )
                except Exception as exc:  # E2B remains optional at import time.
                    if exc.__class__.__name__ != "TimeoutException":
                        raise
                    _write_json(command_log, {
                        "exit_code": None,
                        "stdout": "",
                        "stderr": "",
                        "error": _scrub(str(exc), model_env),
                        "timed_out": True,
                    })
                    raise E2BWorkerTimeout(
                        f"worker exceeded the official agent timeout ({command_timeout}s)",
                        log_uri=str(command_log.resolve()),
                    ) from exc
                _write_json(command_log, _command_payload(worker_result, model_env))
                if int(getattr(worker_result, "exit_code", -1)) != 0:
                    raise E2BExecutionError(
                        f"worker command failed with exit {getattr(worker_result, 'exit_code', -1)}"
                    )
                lease.heartbeat()
                _run_checked(
                    sandbox,
                    "tar -C /app/output -cf /tmp/qea-output.tar .",
                    label="worker artifact command",
                    timeout=min(120, sandbox_timeout),
                )
                output_payload = sandbox.files.read("/tmp/qea-output.tar", format="bytes")
                if not isinstance(output_payload, bytes):
                    output_payload = bytes(output_payload)
                extracted = extract_output_archive(
                    output_payload,
                    artifact_dir,
                    max_files=self.config.max_output_files,
                    max_bytes=self.config.max_output_bytes,
                )
                trace_text = sandbox.files.read("/qea/result/raw_trace.jsonl", format="text")
                final_text = sandbox.files.read("/qea/result/final.txt", format="text")
                summary_text = sandbox.files.read("/qea/result/summary.json", format="text")
                trace_path.write_text(_scrub(str(trace_text), model_env))
                final_text_path.write_text(_scrub(str(final_text), model_env))
                try:
                    summary = json.loads(_scrub(str(summary_text), model_env))
                except json.JSONDecodeError as exc:
                    raise E2BExecutionError(f"invalid remote worker summary: {exc}") from exc
                summary["dependency_lock_sha256"] = dependency_lock_sha256
                records = tuple(ArtifactRecord.from_file(path, root=artifact_dir) for path in extracted)
            finally:
                cleanup_error = None
                if sandbox is not None:
                    try:
                        sandbox.kill()
                        cleanup_ok = True
                    except Exception as exc:  # noqa: BLE001
                        cleanup_ok = False
                        cleanup_error = f"{type(exc).__name__}: {exc}"
                if sandbox_id:
                    _write_sandbox_lifecycle(
                        lifecycle_path,
                        attempt=attempt,
                        task_id=task.task_id,
                        role="worker",
                        sandbox_id=sandbox_id,
                        cleaned_up=cleanup_ok,
                        cleanup_error=cleanup_error,
                    )
                _write_json(attempt_dir / "worker-cleanup.json", {
                    "attempt_id": attempt.attempt_id,
                    "sandbox_id": sandbox_id,
                    "cleaned_up": cleanup_ok,
                })

        execution = E2BWorkerExecution(
            attempt_id=attempt.attempt_id,
            artifact_dir=artifact_dir,
            artifacts=records,
            trace_uri=str(trace_path),
            log_uri=str(command_log),
            final_text_uri=str(final_text_path),
            summary=summary,
            sandbox_id=sandbox_id,
            cleaned_up=cleanup_ok,
        )
        _persist_worker_execution(execution, attempt_dir)
        return execution


class E2BOracleRunner:
    """Trusted no-LLM oracle path used only to establish local/E2B parity."""

    def __init__(
        self,
        config: E2BNexAUConfig,
        *,
        sandbox_factory: E2BSandboxFactory | None = None,
        lease_pool: E2BLeasePool,
    ) -> None:
        self.config = config
        self.sandbox_factory = sandbox_factory or SDKSandboxFactory()
        self.lease_pool = lease_pool

    def execute(
        self,
        *,
        attempt: TaskAttempt,
        task,
        run_dir: str | Path,
    ) -> E2BWorkerExecution:
        if not (Path(task.root) / "solution" / "solve.sh").is_file():
            raise E2BExecutionError(f"task {task.task_id!r} has no solution/solve.sh")
        attempt_dir = Path(run_dir).resolve() / "attempts" / attempt.attempt_id
        attempt_dir.mkdir(parents=True, exist_ok=True)
        bundle = build_oracle_bundle(task, attempt_dir / "oracle-input.tar")
        command_log = attempt_dir / "oracle-command.json"
        trace_path = attempt_dir / "oracle-trace.jsonl"
        final_text_path = attempt_dir / "oracle-final.txt"
        artifact_dir = attempt_dir / "artifacts"
        sandbox = None
        sandbox_id = ""
        cleanup_ok = False
        lifecycle_path = attempt_dir / "oracle-sandbox-lifecycle.json"
        command_timeout = _task_command_timeout(
            task, "agent_timeout_seconds", self.config.timeout_seconds
        )
        sandbox_timeout = _sandbox_lifetime(command_timeout, self.config.timeout_seconds)

        with self.lease_pool.acquire(
            f"oracle:{attempt.attempt_id}", timeout_seconds=self.config.lease_timeout_seconds
        ) as lease:
            try:
                sandbox = self.sandbox_factory.create(
                    template=self.config.worker_template(task.task_id),
                    timeout=sandbox_timeout,
                    metadata={
                        "qea_role": "oracle",
                        "qea_run_id": attempt.run_id,
                        "qea_attempt_id": attempt.attempt_id,
                        "qea_task_id": task.task_id,
                    },
                    envs={},
                    secure=True,
                    allow_internet_access=False,
                )
                sandbox_id = str(sandbox.sandbox_id)
                _write_sandbox_lifecycle(
                    lifecycle_path,
                    attempt=attempt,
                    task_id=task.task_id,
                    role="oracle",
                    sandbox_id=sandbox_id,
                    cleaned_up=False,
                )
                lease.heartbeat()
                _write_sandbox_file(
                    sandbox, "/tmp/qea-oracle.tar", bundle.path.read_bytes()
                )
                _run_checked(
                    sandbox,
                    "mkdir -p /qea_oracle /solution /app/data /app/output && "
                    "tar -xf /tmp/qea-oracle.tar -C /qea_oracle && "
                    "cp -R /qea_oracle/task/environment/data/. /app/data/ && "
                    "cp -R /qea_oracle/solution/. /solution/",
                    label="oracle setup command",
                    timeout=min(120, sandbox_timeout),
                )
                oracle_result = _run_command_result(
                    sandbox,
                    "bash /solution/solve.sh",
                    timeout=command_timeout,
                    envs={},
                )
                _write_json(command_log, _command_payload(oracle_result, {}))
                if int(getattr(oracle_result, "exit_code", -1)) != 0:
                    raise E2BExecutionError(
                        f"oracle command failed with exit {getattr(oracle_result, 'exit_code', -1)}"
                    )
                lease.heartbeat()
                _run_checked(
                    sandbox,
                    "tar -C /app/output -cf /tmp/qea-output.tar .",
                    label="oracle artifact command",
                    timeout=min(120, sandbox_timeout),
                )
                output_payload = sandbox.files.read("/tmp/qea-output.tar", format="bytes")
                if not isinstance(output_payload, bytes):
                    output_payload = bytes(output_payload)
                extracted = extract_output_archive(
                    output_payload,
                    artifact_dir,
                    max_files=self.config.max_output_files,
                    max_bytes=self.config.max_output_bytes,
                )
                records = tuple(ArtifactRecord.from_file(path, root=artifact_dir) for path in extracted)
                summary = {"turns": 0, "tool_calls": 0, "tool_errors": 0, "files": len(records)}
                trace_path.write_text(json.dumps({"role": "oracle", "content": "official solve.sh"}) + "\n")
                final_text_path.write_text("official QFBench oracle completed\n")
            finally:
                cleanup_error = None
                if sandbox is not None:
                    try:
                        sandbox.kill()
                        cleanup_ok = True
                    except Exception as exc:  # noqa: BLE001
                        cleanup_ok = False
                        cleanup_error = f"{type(exc).__name__}: {exc}"
                if sandbox_id:
                    _write_sandbox_lifecycle(
                        lifecycle_path,
                        attempt=attempt,
                        task_id=task.task_id,
                        role="oracle",
                        sandbox_id=sandbox_id,
                        cleaned_up=cleanup_ok,
                        cleanup_error=cleanup_error,
                    )
                _write_json(attempt_dir / "oracle-cleanup.json", {
                    "attempt_id": attempt.attempt_id,
                    "sandbox_id": sandbox_id,
                    "cleaned_up": cleanup_ok,
                })
        execution = E2BWorkerExecution(
            attempt_id=attempt.attempt_id,
            artifact_dir=artifact_dir,
            artifacts=records,
            trace_uri=str(trace_path),
            log_uri=str(command_log),
            final_text_uri=str(final_text_path),
            summary=summary,
            sandbox_id=sandbox_id,
            cleaned_up=cleanup_ok,
        )
        _persist_worker_execution(execution, attempt_dir)
        return execution


class E2BQFBenchVerifier:
    def __init__(
        self,
        config: E2BNexAUConfig,
        *,
        sandbox_factory: E2BSandboxFactory | None = None,
        lease_pool: E2BLeasePool,
    ) -> None:
        self.config = config
        self.sandbox_factory = sandbox_factory or SDKSandboxFactory()
        self.lease_pool = lease_pool

    def verify(
        self,
        *,
        attempt: TaskAttempt,
        task,
        execution: E2BWorkerExecution,
        run_dir: str | Path,
    ) -> OfficialTaskScore:
        attempt_dir = Path(run_dir).resolve() / "attempts" / attempt.attempt_id
        verifier_dir = attempt_dir / "verifier"
        verifier_dir.mkdir(parents=True, exist_ok=True)
        bundle = build_verifier_bundle(
            task, execution.artifact_dir, verifier_dir / "verifier-input.tar"
        )
        command_log = verifier_dir / "verifier-command.trusted.json"
        sandbox = None
        sandbox_id = ""
        cleanup_ok = False
        lifecycle_path = verifier_dir / "verifier-sandbox-lifecycle.json"
        official_script = (Path(task.root) / "tests" / "test.sh").read_text()
        executed_script = official_script
        command = "bash /tests/test.sh"
        command_timeout = _task_command_timeout(
            task, "verifier_timeout_seconds", self.config.timeout_seconds
        )
        sandbox_timeout = _sandbox_lifetime(command_timeout, self.config.timeout_seconds)
        if not self.config.verifier_allow_internet:
            executed_script = prepare_offline_verifier_script(official_script)
            command = "bash /tmp/qea-offline-test.sh"
            (verifier_dir / "executed-test.sh").write_text(executed_script)
        harness_payload = {
            "official_sha256": hashlib.sha256(official_script.encode()).hexdigest(),
            "executed_sha256": hashlib.sha256(executed_script.encode()).hexdigest(),
            "offline_transformed": not self.config.verifier_allow_internet,
            "transformation": (
                "remove-known-pinned-uv-bootstrap-only"
                if not self.config.verifier_allow_internet
                else "none"
            ),
        }
        harness_path = verifier_dir / "verifier-harness.json"
        _write_json(harness_path, harness_payload)

        with self.lease_pool.acquire(
            f"verifier:{attempt.attempt_id}", timeout_seconds=self.config.lease_timeout_seconds
        ) as lease:
            try:
                sandbox = self.sandbox_factory.create(
                    template=self.config.verifier_template(task.task_id),
                    timeout=sandbox_timeout,
                    metadata={
                        "qea_role": "verifier",
                        "qea_run_id": attempt.run_id,
                        "qea_attempt_id": attempt.attempt_id,
                        "qea_task_id": task.task_id,
                    },
                    envs={},
                    secure=True,
                    allow_internet_access=self.config.verifier_allow_internet,
                )
                sandbox_id = str(sandbox.sandbox_id)
                _write_sandbox_lifecycle(
                    lifecycle_path,
                    attempt=attempt,
                    task_id=task.task_id,
                    role="verifier",
                    sandbox_id=sandbox_id,
                    cleaned_up=False,
                )
                dependency_lock = _read_optional_text(
                    sandbox, "/opt/qea/verifier-requirements.lock"
                )
                if dependency_lock is None or not dependency_lock.strip():
                    raise E2BExecutionError(
                        "verifier template dependency lock is missing or empty"
                    )
                dependency_lock_path = verifier_dir / "verifier-requirements.lock"
                dependency_lock_path.write_text(dependency_lock)
                harness_payload["dependency_lock_sha256"] = hashlib.sha256(
                    dependency_lock.encode()
                ).hexdigest()
                _write_json(harness_path, harness_payload)
                lease.heartbeat()
                _write_sandbox_file(
                    sandbox, "/tmp/qea-verifier.tar", bundle.path.read_bytes()
                )
                if not self.config.verifier_allow_internet:
                    _write_sandbox_file(
                        sandbox, "/tmp/qea-offline-test.sh", executed_script
                    )
                _run_checked(
                    sandbox,
                    "mkdir -p /qea_verify /tests /app/output /logs/verifier && "
                    "mkdir -p /qea_verify/artifacts && "
                    "tar -xf /tmp/qea-verifier.tar -C /qea_verify && "
                    "cp -R /qea_verify/tests/. /tests/ && "
                    "cp -R /qea_verify/artifacts/. /app/output/",
                    label="verifier setup command",
                    timeout=min(120, sandbox_timeout),
                )
                verifier_result = _run_command_result(
                    sandbox,
                    command,
                    timeout=command_timeout,
                    envs={
                        "UV_OFFLINE": "1",
                        "UV_CACHE_DIR": "/opt/qea/uv-cache",
                        "UV_TOOL_DIR": "/opt/qea/uv-tools",
                        "UV_TOOL_BIN_DIR": "/opt/qea/uv-bin",
                        "PATH": (
                            "/opt/qea/uv-bin:/root/.local/bin:/usr/local/bin:"
                            "/usr/bin:/bin"
                        ),
                    } if not self.config.verifier_allow_internet else {},
                )
                _write_json(command_log, _command_payload(verifier_result, {}))
                reward_text = sandbox.files.read("/logs/verifier/reward.txt", format="text")
                ctrf_text = _read_optional_text(sandbox, "/logs/verifier/ctrf.json")
                reward_path = verifier_dir / "reward.txt"
                ctrf_path = verifier_dir / "ctrf.json"
                reward_path.write_text(str(reward_text))
                if ctrf_text is not None:
                    ctrf_path.write_text(ctrf_text)
                score = parse_official_qfbench_score(
                    task_id=task.task_id,
                    domain=task.domain,
                    reward_path=reward_path,
                    ctrf_path=ctrf_path if ctrf_text is not None else None,
                    verifier_exit_code=int(getattr(verifier_result, "exit_code", -1)),
                    log_uri=str(command_log),
                    pytest_output=(
                        str(getattr(verifier_result, "stdout", "") or "")
                        + "\n"
                        + str(getattr(verifier_result, "stderr", "") or "")
                    ),
                )
                _write_json(verifier_dir / "official-score.json", asdict(score))
            finally:
                cleanup_error = None
                if sandbox is not None:
                    try:
                        sandbox.kill()
                        cleanup_ok = True
                    except Exception as exc:  # noqa: BLE001
                        cleanup_ok = False
                        cleanup_error = f"{type(exc).__name__}: {exc}"
                if sandbox_id:
                    _write_sandbox_lifecycle(
                        lifecycle_path,
                        attempt=attempt,
                        task_id=task.task_id,
                        role="verifier",
                        sandbox_id=sandbox_id,
                        cleaned_up=cleanup_ok,
                        cleanup_error=cleanup_error,
                    )
                _write_json(verifier_dir / "verifier-cleanup.json", {
                    "attempt_id": attempt.attempt_id,
                    "sandbox_id": sandbox_id,
                    "cleaned_up": cleanup_ok,
                })
        return score
