"""Run NexAU workers and QFBench verifiers through a neutral sandbox backend.

The coordinator remains trusted.  Public task material and a candidate worker are
sent to one network-restricted sandbox; official tests and the resulting artifact
archive are sent to a different, networkless sandbox.  This module deliberately
has no oracle or official-solution execution surface.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, Mapping, Sequence

from ..evaluation import ArtifactRecord, OfficialTaskScore, TaskAttempt
from ..qfbench_images import NEXAU_REQUIREMENTS_LOCK, NEXAU_RUNTIME_PYTHON
from ..sandbox_backend import (
    SandboxBackend,
    SandboxCommandResult,
    SandboxSpec,
    validate_sandbox_environment,
)
from ..sandbox_lifecycle import (
    create_lifecycle,
    mark_finished,
    mark_started,
)
from ..verifiers.qfbench import (
    parse_official_qfbench_score,
    prepare_offline_verifier_script,
)
from .bundles import build_verifier_bundle, build_worker_bundle
from .execution_record import (
    WorkerArtifactContractError,
    WorkerBehaviorTimeout,
    WorkerExecution,
    persist_worker_execution,
)
from .output_archive import extract_output_archive
from .sandbox_runtime import (
    PLACEHOLDER_API_KEY as _PLACEHOLDER_API_KEY,
    SandboxExecutionError,
    SandboxInfrastructureError,
    SandboxResourceContract,
    atomic_json as _atomic_json,
    backend_call as _backend_call,
    finish_and_cleanup as _finish_and_cleanup,
    public_model_environment,
    require_tmpfs as _require_tmpfs,
    run_required as _run_required,
    utc_now as _utc_now,
    validate_public_model_env,
    write_command_log as _write_command_log,
)


_REMOTE_RUNNER = Path(__file__).with_name("remote_nexau_worker.py")
_RUNTIME_BRIDGE = Path(__file__).parents[1] / "runtime_bridge.py"
_WORKER_REQUIRED_TMPFS = frozenset({"/tmp", "/qea", "/app"})
_VERIFIER_REQUIRED_TMPFS = frozenset(
    {
        "/tmp",
        "/qea",
        "/app",
        "/tests",
        "/logs",
        "/opt/qea/uv-cache",
        "/opt/qea/uv-tools",
    }
)
_VERIFIER_EXECUTABLE_TMPFS = frozenset(
    {"/opt/qea/uv-cache", "/opt/qea/uv-tools"}
)
_OFFLINE_VERIFIER_ENV = {
    "TMPDIR": "/opt/qea/uv-tools",
    "UV_OFFLINE": "1",
    "UV_CACHE_DIR": "/opt/qea/uv-cache",
    "UV_TOOL_DIR": "/opt/qea/uv-tools",
    "UV_TOOL_BIN_DIR": "/opt/qea/uv-bin",
    "PATH": "/opt/qea/uv-bin:/root/.local/bin:/usr/local/bin:/usr/bin:/bin",
}
# Keep uv metadata writable while reusing the image's immutable package archives.
_VERIFIER_CACHE_OVERLAY_CODE = """\
# QEA_WRITABLE_UV_CACHE_OVERLAY_V1
import os
import shutil
from pathlib import Path

source = Path("/opt/qea/uv-cache-seed")
destination = Path("/opt/qea/uv-cache")
ignored_top_level = {"archive-v0"}


def ignore_immutable_archives(directory, names):
    if Path(directory) != source:
        return set()
    return ignored_top_level.intersection(names)


shutil.copytree(
    source,
    destination,
    dirs_exist_ok=True,
    symlinks=True,
    ignore=ignore_immutable_archives,
)
(destination / "archive-v0").mkdir(exist_ok=True)
archive_source = source / "archive-v0"
if archive_source.is_dir():
    for entry in sorted(archive_source.iterdir(), key=lambda path: path.name):
        os.symlink(
            entry,
            destination / "archive-v0" / entry.name,
            target_is_directory=entry.is_dir(),
        )
"""
_ARTIFACT_INTEGRITY_CODE = """\
import hashlib, json
from pathlib import Path

root = Path('/app/output')
expected = json.loads(Path('/qea/expected-artifacts.json').read_text())
actual = {}
for path in sorted(root.rglob('*')):
    if path.is_symlink() or (not path.is_file() and not path.is_dir()):
        raise SystemExit(86)
    if path.is_file():
        payload = path.read_bytes()
        actual[path.relative_to(root).as_posix()] = {
            'sha256': hashlib.sha256(payload).hexdigest(),
            'size_bytes': len(payload),
        }
Path('/qea/artifact-integrity.json').write_text(
    json.dumps(actual, sort_keys=True, separators=(',', ':')) + '\\n'
)
raise SystemExit(0 if actual == expected else 87)
"""


class SandboxWorkerTimeout(WorkerBehaviorTimeout, SandboxExecutionError):
    """The worker's task command, and only that command, reached its timeout."""


class SandboxWorkerArtifactContractError(
    WorkerArtifactContractError, SandboxExecutionError
):
    """The completed worker returned the wrong artifact membership."""


def _task_timeout(task, attribute: str, cap: int, *, phase: str) -> int:
    value = getattr(task, attribute, cap)
    if type(value) is not int or value <= 0:
        raise SandboxInfrastructureError(
            phase, f"task {attribute} must be a positive integer"
        )
    return min(value, cap)


def _task_root(base: Path, task_id: str, *, phase: str) -> Path:
    root = (base / "tasks" / task_id).resolve()
    try:
        root.relative_to(base)
    except ValueError as exc:
        raise SandboxInfrastructureError(phase, "task root escapes role root") from exc
    if root.is_symlink() or not root.is_dir():
        raise SandboxInfrastructureError(phase, f"missing task root {root}")
    return root


def _regular_files(root: Path, *, phase: str) -> tuple[Path, ...]:
    if root.is_symlink() or not root.is_dir():
        raise SandboxInfrastructureError(phase, f"missing directory {root}")
    files: list[Path] = []
    for path in root.rglob("*"):
        if path.is_symlink():
            raise SandboxInfrastructureError(phase, f"symlink is forbidden: {path}")
        if path.is_file():
            files.append(path.resolve())
        elif not path.is_dir():
            raise SandboxInfrastructureError(phase, f"non-regular entry: {path}")
    return tuple(sorted(files, key=lambda item: item.relative_to(root).as_posix()))


def _worker_task_view(public_root: Path, task_id: str):
    root = _task_root(public_root, task_id, phase="worker.input")
    instruction = root / "instruction.md"
    if instruction.is_symlink() or not instruction.is_file():
        raise SandboxInfrastructureError(
            "worker.input", f"missing public instruction {instruction}"
        )
    data_root = root / "environment" / "data"
    if data_root.is_symlink():
        raise SandboxInfrastructureError(
            "worker.input", f"symlink is forbidden: {data_root}"
        )
    data_files = (
        _regular_files(data_root, phase="worker.input")
        if data_root.exists()
        else ()
    )
    return SimpleNamespace(
        task_id=task_id,
        root=root,
        worker_files=tuple(
            sorted(
                (*data_files, instruction.resolve()),
                key=lambda item: item.relative_to(root).as_posix(),
            )
        ),
    )


def _verifier_task_view(trusted_root: Path, task_id: str):
    root = _task_root(trusted_root, task_id, phase="verifier.input")
    tests_root = root / "tests"
    files = _regular_files(tests_root, phase="verifier.input")
    test_script = tests_root / "test.sh"
    if test_script.resolve() not in files:
        raise SandboxInfrastructureError(
            "verifier.input", f"missing official test script {test_script}"
        )
    return SimpleNamespace(task_id=task_id, root=root, verifier_files=files)


def _worker_environment(
    *,
    proxy_base_url: str,
    model_name: str,
    placeholder_api_key: str,
) -> dict[str, str]:
    return public_model_environment(
        proxy_base_url=proxy_base_url,
        model_name=model_name,
        placeholder_api_key=placeholder_api_key,
    )


def _validate_public_model_env(
    supplied: Mapping[str, str] | None,
    expected: Mapping[str, str],
) -> None:
    validate_public_model_env(supplied, expected, role="worker")


def _attempt_identity(
    *,
    role: str,
    attempt: TaskAttempt,
    spec: SandboxSpec,
    input_sha256: str,
) -> str:
    payload = {
        "attempt": asdict(attempt),
        "input_sha256": input_sha256,
        "role": role,
        "spec_sha256": spec.spec_sha256,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _artifact_records(execution: WorkerExecution) -> tuple[ArtifactRecord, ...]:
    artifact_root = Path(execution.artifact_dir).resolve()
    expected = tuple(sorted(execution.artifacts, key=lambda item: item.path))
    discovered = _regular_files(artifact_root, phase="verifier.artifacts")
    actual = tuple(
        sorted(
            (
                ArtifactRecord.from_file(path, root=artifact_root)
                for path in discovered
            ),
            key=lambda item: item.path,
        )
    )
    if actual != expected:
        raise SandboxInfrastructureError(
            "verifier.artifacts", "worker artifact records changed before upload"
        )
    return actual


def _artifact_map(records: Sequence[ArtifactRecord]) -> dict[str, dict[str, object]]:
    return {
        record.path: {
            "sha256": record.sha256,
            "size_bytes": record.size_bytes,
        }
        for record in sorted(records, key=lambda item: item.path)
    }


def _optional_read(backend: SandboxBackend, handle, path: str) -> bytes | None:
    try:
        return backend.read_bytes(handle, path)
    except Exception as exc:  # noqa: BLE001 - backend-specific not-found types.
        message = str(exc).lower()
        if isinstance(exc, (FileNotFoundError, KeyError)) or any(
            marker in message
            for marker in ("no such file", "not found", "could not find the file")
        ):
            return None
        raise


class SandboxNexAUExecutor:
    """Execute one public QFBench task in an isolated worker sandbox."""

    def __init__(
        self,
        *,
        backend: SandboxBackend,
        lifecycle_root: str | Path,
        worker_image_ref: str,
        public_task_root: str | Path,
        resource_contract: SandboxResourceContract,
        worker_network_name: str,
        network_scope: str | None = None,
        proxy_base_url: str,
        model_name: str,
        placeholder_api_key: str = _PLACEHOLDER_API_KEY,
        clock: Callable[[], datetime] = _utc_now,
        max_output_files: int = 2_000,
        max_output_bytes: int = 512 * 1024 * 1024,
        expected_output_paths: tuple[str, ...] | None = None,
        auxiliary_output_paths: tuple[str, ...] = (),
        retain_additional_outputs: bool = False,
    ) -> None:
        _require_tmpfs(resource_contract, _WORKER_REQUIRED_TMPFS, role="worker")
        if type(max_output_files) is not int or max_output_files <= 0:
            raise SandboxInfrastructureError(
                "worker.config", "max_output_files must be positive"
            )
        if type(max_output_bytes) is not int or max_output_bytes <= 0:
            raise SandboxInfrastructureError(
                "worker.config", "max_output_bytes must be positive"
            )
        self.backend = backend
        self.lifecycle_root = Path(lifecycle_root).expanduser().resolve()
        self.worker_image_ref = worker_image_ref
        self.public_task_root = Path(public_task_root).expanduser().resolve()
        self.resource_contract = resource_contract
        if not isinstance(worker_network_name, str) or not worker_network_name.strip():
            raise SandboxInfrastructureError(
                "worker.config", "worker network name must be non-empty"
            )
        if network_scope is not None and (
            not isinstance(network_scope, str) or not network_scope.strip()
        ):
            raise SandboxInfrastructureError(
                "worker.config", "network scope must be non-empty when supplied"
            )
        self.worker_network_name = worker_network_name
        self.network_scope = network_scope
        self.worker_environment = _worker_environment(
            proxy_base_url=proxy_base_url,
            model_name=model_name,
            placeholder_api_key=placeholder_api_key,
        )
        self.clock = clock
        self.max_output_files = max_output_files
        self.max_output_bytes = max_output_bytes
        if expected_output_paths is not None:
            normalized = tuple(sorted(set(expected_output_paths)))
            if (
                not normalized
                or len(normalized) != len(expected_output_paths)
                or any(
                    not isinstance(path, str)
                    or path.startswith("/")
                    or path in {"", "."}
                    or ".." in Path(path).parts
                    for path in normalized
                )
            ):
                raise SandboxInfrastructureError(
                    "worker.config", "expected output paths are invalid"
                )
            self.expected_output_paths = normalized
        else:
            self.expected_output_paths = None
        normalized_auxiliary = tuple(sorted(set(auxiliary_output_paths)))
        if (
            len(normalized_auxiliary) != len(auxiliary_output_paths)
            or any(
                not isinstance(path, str)
                or path.startswith("/")
                or path in {"", "."}
                or ".." in Path(path).parts
                for path in normalized_auxiliary
            )
            or (
                self.expected_output_paths is not None
                and set(normalized_auxiliary).intersection(
                    self.expected_output_paths
                )
            )
        ):
            raise SandboxInfrastructureError(
                "worker.config", "auxiliary output paths are invalid"
            )
        self.auxiliary_output_paths = normalized_auxiliary
        self.retain_additional_outputs = bool(retain_additional_outputs)

    def execute(
        self,
        *,
        attempt: TaskAttempt,
        task,
        worker_dir: str | Path,
        run_dir: str | Path,
        model_env: Mapping[str, str] | None = None,
    ) -> WorkerExecution:
        _validate_public_model_env(model_env, self.worker_environment)
        if self.network_scope is None:
            expected_network = f"qea-{attempt.run_id}-internal"
            if self.worker_network_name != expected_network:
                raise SandboxInfrastructureError(
                    "worker.proxy",
                    f"worker network must be the exact run network {expected_network!r}",
                )
        elif self.network_scope != attempt.attempt_id:
            raise SandboxInfrastructureError(
                "worker.proxy", "worker network scope must match the attempt identity"
            )
        attempt_dir = Path(run_dir).resolve() / "attempts" / attempt.attempt_id
        attempt_dir.mkdir(parents=True, exist_ok=True)
        task_view = _worker_task_view(self.public_task_root, task.task_id)
        try:
            bundle = build_worker_bundle(
                task_view, worker_dir, attempt_dir / "worker-input.tar"
            )
        except Exception as exc:  # noqa: BLE001 - bundle contract boundary.
            raise SandboxInfrastructureError(
                "worker.input", f"{type(exc).__name__}: {exc}"
            ) from exc
        timeout = _task_timeout(
            task,
            "agent_timeout_seconds",
            self.resource_contract.timeout_seconds,
            phase="worker.config",
        )
        spec = SandboxSpec(
            role="worker",
            run_id=attempt.run_id,
            attempt_id=attempt.attempt_id,
            task_id=task.task_id,
            image_ref=self.worker_image_ref,
            cpu_count=self.resource_contract.cpu_count,
            memory_mb=self.resource_contract.memory_mb,
            pids_limit=self.resource_contract.pids_limit,
            timeout_seconds=self.resource_contract.timeout_seconds,
            network_policy="worker-proxy-only",
            environment=self.worker_environment,
            writable_tmpfs_mb=self.resource_contract.writable_tmpfs_mb,
            network_scope=self.network_scope,
        )
        identity = _attempt_identity(
            role="worker",
            attempt=attempt,
            spec=spec,
            input_sha256=bundle.sha256,
        )
        lifecycle_path = (
            self.lifecycle_root
            / attempt.run_id
            / attempt.attempt_id
            / "worker-sandbox-lifecycle-v2.json"
        )
        command_log = attempt_dir / "worker-command.json"
        trace_path = attempt_dir / "raw-trace.jsonl"
        final_path = attempt_dir / "final.txt"
        dependency_path = attempt_dir / "nexau-requirements.lock"
        artifact_dir = attempt_dir / "artifacts"
        handle = None
        primary_error: BaseException | None = None
        finished = False
        records: tuple[ArtifactRecord, ...] = ()
        summary: dict[str, object] = {}

        try:
            handle = _backend_call("worker.create", lambda: self.backend.create(spec))
            _backend_call(
                "worker.lifecycle",
                lambda: create_lifecycle(
                    lifecycle_path,
                    handle=handle,
                    spec=spec,
                    attempt_identity_sha256=identity,
                    at=self.clock(),
                ),
            )
            _backend_call("worker.start", lambda: self.backend.start(handle))
            _backend_call(
                "worker.lifecycle",
                lambda: mark_started(lifecycle_path, at=self.clock()),
            )
            dependency_lock = _backend_call(
                "worker.dependency",
                lambda: self.backend.read_bytes(handle, NEXAU_REQUIREMENTS_LOCK),
            )
            if not isinstance(dependency_lock, bytes) or not dependency_lock.strip():
                raise SandboxInfrastructureError(
                    "worker.dependency", "NexAU dependency lock is missing or empty"
                )
            dependency_path.write_bytes(dependency_lock)

            uploads = (
                ("/qea/worker-input.tar", bundle.path.read_bytes()),
                ("/qea/remote_nexau_worker.py", _REMOTE_RUNNER.read_bytes()),
                ("/qea/runtime_bridge.py", _RUNTIME_BRIDGE.read_bytes()),
            )
            for path, payload in uploads:
                _backend_call(
                    "worker.upload",
                    lambda path=path, payload=payload: self.backend.put_bytes(
                        handle, path, payload
                    ),
                )
            setup_timeout = min(120, self.resource_contract.timeout_seconds)
            for argv in (
                ("mkdir", "-p", "/qea/result", "/app/data", "/app/output"),
                ("tar", "-xf", "/qea/worker-input.tar", "-C", "/qea"),
                (
                    "sh",
                    "-c",
                    "if [ -d /qea/task/environment/data ]; then "
                    "cp -R /qea/task/environment/data/. /app/data/; "
                    "cp -R /qea/task/environment/data/. /app/; fi",
                ),
            ):
                _run_required(
                    self.backend,
                    handle,
                    argv,
                    environment={},
                    timeout_seconds=setup_timeout,
                    phase="worker.setup",
                )
            result = _backend_call(
                "worker.command",
                lambda: self.backend.run(
                    handle,
                    (
                        NEXAU_RUNTIME_PYTHON,
                        "/qea/remote_nexau_worker.py",
                        "--task-dir",
                        "/qea/task",
                        "--worker-dir",
                        "/qea/worker",
                        "--work-dir",
                        "/app",
                        "--output-dir",
                        "/app/output",
                        "--result-dir",
                        "/qea/result",
                    ),
                    environment=self.worker_environment,
                    timeout_seconds=timeout,
                ),
            )
            assert isinstance(result, SandboxCommandResult)
            _write_command_log(command_log, result)
            if result.timed_out:
                raise SandboxWorkerTimeout(
                    f"worker exceeded the official agent timeout ({timeout}s)",
                    log_uri=str(command_log.resolve()),
                )
            if result.exit_code != 0:
                raise SandboxInfrastructureError(
                    "worker.command",
                    f"worker command exited {result.exit_code}: {result.stderr}",
                )
            _run_required(
                self.backend,
                handle,
                ("tar", "-C", "/app/output", "-cf", "/qea/output.tar", "."),
                environment={},
                timeout_seconds=setup_timeout,
                phase="worker.artifacts",
            )
            output_payload = _backend_call(
                "worker.download",
                lambda: self.backend.read_bytes(handle, "/qea/output.tar"),
            )
            if artifact_dir.exists() and any(artifact_dir.iterdir()):
                raise SandboxInfrastructureError(
                    "worker.artifacts", "artifact directory is not empty"
                )
            try:
                extracted = extract_output_archive(
                    output_payload,
                    artifact_dir,
                    max_files=self.max_output_files,
                    max_bytes=self.max_output_bytes,
                )
            except Exception as exc:  # noqa: BLE001 - archive firewall boundary.
                raise SandboxInfrastructureError(
                    "worker.artifacts", f"{type(exc).__name__}: {exc}"
                ) from exc
            trace = _backend_call(
                "worker.download",
                lambda: self.backend.read_bytes(handle, "/qea/result/raw_trace.jsonl"),
            )
            final = _backend_call(
                "worker.download",
                lambda: self.backend.read_bytes(handle, "/qea/result/final.txt"),
            )
            raw_summary = _backend_call(
                "worker.download",
                lambda: self.backend.read_bytes(handle, "/qea/result/summary.json"),
            )
            trace_path.write_bytes(trace)
            final_path.write_bytes(final)
            try:
                parsed = json.loads(raw_summary)
            except (TypeError, json.JSONDecodeError) as exc:
                raise SandboxInfrastructureError(
                    "worker.summary", f"invalid remote worker summary: {exc}"
                ) from exc
            if not isinstance(parsed, dict):
                raise SandboxInfrastructureError(
                    "worker.summary", "remote worker summary must be an object"
                )
            summary = dict(parsed)
            summary["dependency_lock_sha256"] = hashlib.sha256(
                dependency_lock
            ).hexdigest()
            records = tuple(
                ArtifactRecord.from_file(path, root=artifact_dir) for path in extracted
            )
            found_paths = tuple(sorted(record.path for record in records))
            allowed_paths = set(self.expected_output_paths or ()) | set(
                self.auxiliary_output_paths
            )
            if (
                self.expected_output_paths is not None
                and (
                    not set(self.expected_output_paths).issubset(found_paths)
                    or (
                        not self.retain_additional_outputs
                        and not set(found_paths).issubset(allowed_paths)
                    )
                )
            ):
                _atomic_json(
                    attempt_dir / "worker-artifact-contract.json",
                    {
                        "schema_version": 1,
                        "outcome": "official_worker_artifact_contract_zero",
                        "expected_paths": list(self.expected_output_paths),
                        "found_paths": list(found_paths),
                        "artifact_records": [asdict(record) for record in records],
                        "trace_uri": str(trace_path),
                        "final_text_uri": str(final_path),
                    },
                )
                raise SandboxWorkerArtifactContractError(
                    "worker output membership differs from the benchmark contract: "
                    f"expected={list(self.expected_output_paths)}, "
                    f"found={list(found_paths)}",
                    log_uri=str(trace_path.resolve()),
                )
            auxiliary_records = tuple(
                record
                for record in records
                if (
                    record.path in self.auxiliary_output_paths
                    or (
                        self.retain_additional_outputs
                        and record.path not in set(self.expected_output_paths or ())
                    )
                )
            )
            if auxiliary_records:
                auxiliary_root = attempt_dir / "worker-auxiliary-artifacts"
                for record in auxiliary_records:
                    source = artifact_dir / record.path
                    target = auxiliary_root / record.path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    source.replace(target)
                _atomic_json(
                    attempt_dir / "worker-auxiliary-artifacts.json",
                    {
                        "schema_version": 1,
                        "purpose": "worker_validation_side_effects_not_submitted",
                        "artifact_records": [
                            asdict(record) for record in auxiliary_records
                        ],
                    },
                )
                records = tuple(
                    record
                    for record in records
                    if record not in auxiliary_records
                )
            mark_finished(lifecycle_path, at=self.clock())
            finished = True
        except (
            SandboxInfrastructureError,
            SandboxWorkerArtifactContractError,
            SandboxWorkerTimeout,
        ) as exc:
            primary_error = exc
        except Exception as exc:  # noqa: BLE001 - final typed boundary.
            primary_error = SandboxInfrastructureError(
                "worker.coordinator", f"{type(exc).__name__}: {exc}"
            )
        finally:
            _finish_and_cleanup(
                backend=self.backend,
                handle=handle,
                lifecycle_path=lifecycle_path if handle is not None else None,
                clock=self.clock,
                role="worker",
                primary_error=primary_error,
                finished=finished,
            )
        if primary_error is not None:
            raise primary_error
        assert handle is not None
        execution = WorkerExecution(
            attempt_id=attempt.attempt_id,
            artifact_dir=artifact_dir,
            artifacts=records,
            trace_uri=str(trace_path),
            log_uri=str(command_log),
            final_text_uri=str(final_path),
            summary=summary,
            sandbox_id=handle.native_id,
            cleaned_up=True,
        )
        persist_worker_execution(execution, attempt_dir)
        return execution


class SandboxQFBenchVerifier:
    """Run official tests in an independent sandbox with no network stack."""

    def __init__(
        self,
        *,
        backend: SandboxBackend,
        lifecycle_root: str | Path,
        verifier_image_ref: str,
        trusted_task_root: str | Path,
        public_task_root: str | Path | None = None,
        resource_contract: SandboxResourceContract,
        clock: Callable[[], datetime] = _utc_now,
        score_parser: Callable[..., OfficialTaskScore] = parse_official_qfbench_score,
        answer_free_evidence_builder: Callable[[str | Path], dict[str, object]] | None = None,
        sandbox_role: str = "verifier",
        network_policy: str = "none",
        network_scope: str | None = None,
        verifier_environment: Mapping[str, str] | None = None,
    ) -> None:
        _require_tmpfs(resource_contract, _VERIFIER_REQUIRED_TMPFS, role="verifier")
        self.backend = backend
        self.lifecycle_root = Path(lifecycle_root).expanduser().resolve()
        self.verifier_image_ref = verifier_image_ref
        self.trusted_task_root = Path(trusted_task_root).expanduser().resolve()
        self.public_task_root = (
            Path(public_task_root).expanduser().resolve()
            if public_task_root is not None
            else None
        )
        self.resource_contract = resource_contract
        self.clock = clock
        if not callable(score_parser):
            raise SandboxInfrastructureError(
                "verifier.config", "score_parser must be callable"
            )
        self.score_parser = score_parser
        if answer_free_evidence_builder is not None and not callable(
            answer_free_evidence_builder
        ):
            raise SandboxInfrastructureError(
                "verifier.config", "answer-free evidence builder must be callable"
            )
        if sandbox_role not in {"verifier", "canary"}:
            raise SandboxInfrastructureError(
                "verifier.config", "verifier sandbox role is invalid"
            )
        if network_policy not in {"none", "worker-proxy-only"}:
            raise SandboxInfrastructureError(
                "verifier.config", "verifier network policy is invalid"
            )
        self.answer_free_evidence_builder = answer_free_evidence_builder
        self.sandbox_role = sandbox_role
        self.network_policy = network_policy
        self.network_scope = network_scope
        self.verifier_environment = validate_sandbox_environment(
            verifier_environment or {}
        )

    def verify(
        self,
        *,
        attempt: TaskAttempt,
        task,
        execution: WorkerExecution,
        run_dir: str | Path,
    ) -> OfficialTaskScore:
        attempt_dir = Path(run_dir).resolve() / "attempts" / attempt.attempt_id
        verifier_dir = attempt_dir / "verifier"
        verifier_dir.mkdir(parents=True, exist_ok=True)
        records = _artifact_records(execution)
        task_view = _verifier_task_view(self.trusted_task_root, task.task_id)
        public_task_view = (
            _worker_task_view(self.public_task_root, task.task_id)
            if self.public_task_root is not None
            else None
        )
        try:
            bundle = build_verifier_bundle(
                task_view,
                execution.artifact_dir,
                verifier_dir / "verifier-input.tar",
                public_task=public_task_view,
            )
            official_script = (Path(task_view.root) / "tests" / "test.sh").read_text()
            executed_script = prepare_offline_verifier_script(official_script)
        except Exception as exc:  # noqa: BLE001 - trusted input boundary.
            raise SandboxInfrastructureError(
                "verifier.input", f"{type(exc).__name__}: {exc}"
            ) from exc
        timeout = _task_timeout(
            task,
            "verifier_timeout_seconds",
            self.resource_contract.timeout_seconds,
            phase="verifier.config",
        )
        spec = SandboxSpec(
            role=self.sandbox_role,
            run_id=attempt.run_id,
            attempt_id=attempt.attempt_id,
            task_id=task.task_id,
            image_ref=self.verifier_image_ref,
            cpu_count=self.resource_contract.cpu_count,
            memory_mb=self.resource_contract.memory_mb,
            pids_limit=self.resource_contract.pids_limit,
            timeout_seconds=self.resource_contract.timeout_seconds,
            network_policy=self.network_policy,
            environment=self.verifier_environment,
            writable_tmpfs_mb=self.resource_contract.writable_tmpfs_mb,
            executable_tmpfs_paths=_VERIFIER_EXECUTABLE_TMPFS,
            network_scope=self.network_scope,
        )
        identity = _attempt_identity(
            role="verifier",
            attempt=attempt,
            spec=spec,
            input_sha256=bundle.sha256,
        )
        lifecycle_path = (
            self.lifecycle_root
            / attempt.run_id
            / attempt.attempt_id
            / "verifier-sandbox-lifecycle-v2.json"
        )
        command_log = verifier_dir / "verifier-command.trusted.json"
        reward_path = verifier_dir / "reward.txt"
        ctrf_path = verifier_dir / "ctrf.json"
        harness_path = verifier_dir / "verifier-harness.json"
        evidence_path = verifier_dir / "verifier-evidence.json"
        expected_artifacts = _artifact_map(records)
        expected_payload = (
            json.dumps(expected_artifacts, sort_keys=True, separators=(",", ":"))
            + "\n"
        ).encode()
        handle = None
        primary_error: BaseException | None = None
        finished = False
        score: OfficialTaskScore | None = None

        try:
            handle = _backend_call("verifier.create", lambda: self.backend.create(spec))
            _backend_call(
                "verifier.lifecycle",
                lambda: create_lifecycle(
                    lifecycle_path,
                    handle=handle,
                    spec=spec,
                    attempt_identity_sha256=identity,
                    at=self.clock(),
                ),
            )
            _backend_call("verifier.start", lambda: self.backend.start(handle))
            _backend_call(
                "verifier.lifecycle",
                lambda: mark_started(lifecycle_path, at=self.clock()),
            )
            dependency_lock = _backend_call(
                "verifier.dependency",
                lambda: self.backend.read_bytes(
                    handle, "/opt/qea/verifier-requirements.lock"
                ),
            )
            if not isinstance(dependency_lock, bytes) or not dependency_lock.strip():
                raise SandboxInfrastructureError(
                    "verifier.dependency",
                    "verifier dependency lock is missing or empty",
                )
            (verifier_dir / "verifier-requirements.lock").write_bytes(dependency_lock)
            uploads = (
                ("/qea/verifier-input.tar", bundle.path.read_bytes()),
                ("/tmp/qea-offline-test.sh", executed_script.encode()),
                ("/qea/expected-artifacts.json", expected_payload),
            )
            for path, payload in uploads:
                _backend_call(
                    "verifier.upload",
                    lambda path=path, payload=payload: self.backend.put_bytes(
                        handle, path, payload
                    ),
                )
            setup_timeout = min(120, self.resource_contract.timeout_seconds)
            for argv in (
                (
                    "mkdir",
                    "-p",
                    "/qea/tests",
                    "/qea/artifacts",
                    "/app/data",
                    "/tests",
                    "/app/output",
                    "/logs/verifier",
                ),
                ("tar", "-xf", "/qea/verifier-input.tar", "-C", "/qea"),
                ("cp", "-R", "/qea/tests/.", "/tests/"),
                ("cp", "-R", "/qea/artifacts/.", "/app/output/"),
                (
                    "sh",
                    "-c",
                    "if [ -d /qea/task/environment/data ]; then "
                    "cp -R /qea/task/environment/data/. /app/data/; "
                    "cp -R /qea/task/environment/data/. /app/; fi",
                ),
                ("python3", "-c", _VERIFIER_CACHE_OVERLAY_CODE),
            ):
                _run_required(
                    self.backend,
                    handle,
                    argv,
                    environment={},
                    timeout_seconds=setup_timeout,
                    phase="verifier.setup",
                )
            _run_required(
                self.backend,
                handle,
                ("python3", "-c", _ARTIFACT_INTEGRITY_CODE),
                environment={},
                timeout_seconds=setup_timeout,
                phase="verifier.artifact-integrity",
            )
            actual_integrity = _backend_call(
                "verifier.artifact-integrity",
                lambda: self.backend.read_bytes(
                    handle, "/qea/artifact-integrity.json"
                ),
            )
            try:
                actual_artifacts = json.loads(actual_integrity)
            except (TypeError, json.JSONDecodeError) as exc:
                raise SandboxInfrastructureError(
                    "verifier.artifact-integrity", f"invalid integrity output: {exc}"
                ) from exc
            if actual_artifacts != expected_artifacts:
                raise SandboxInfrastructureError(
                    "verifier.artifact-integrity",
                    "artifact hashes changed after verifier extraction",
                )
            result = _backend_call(
                "verifier.command",
                lambda: self.backend.run(
                    handle,
                    ("bash", "/tmp/qea-offline-test.sh"),
                    environment={
                        **_OFFLINE_VERIFIER_ENV,
                        **dict(self.verifier_environment),
                    },
                    timeout_seconds=timeout,
                ),
            )
            assert isinstance(result, SandboxCommandResult)
            _write_command_log(command_log, result)
            if result.timed_out:
                raise SandboxInfrastructureError(
                    "verifier.command", "official verifier command timed out"
                )
            reward = _backend_call(
                "verifier.output",
                lambda: self.backend.read_bytes(handle, "/logs/verifier/reward.txt"),
            )
            ctrf = _backend_call(
                "verifier.output",
                lambda: _optional_read(
                    self.backend, handle, "/logs/verifier/ctrf.json"
                ),
            )
            reward_path.write_bytes(reward)
            if ctrf is not None:
                ctrf_path.write_bytes(ctrf)
            try:
                score = self.score_parser(
                    task_id=task.task_id,
                    domain=task.domain,
                    reward_path=reward_path,
                    ctrf_path=ctrf_path if ctrf is not None else None,
                    verifier_exit_code=result.exit_code,
                    log_uri=str(command_log),
                    pytest_output=result.stdout + "\n" + result.stderr,
                )
            except Exception as exc:  # noqa: BLE001 - score parser is trusted infra.
                raise SandboxInfrastructureError(
                    "verifier.score", f"{type(exc).__name__}: {exc}"
                ) from exc
            official_sha256 = hashlib.sha256(official_script.encode()).hexdigest()
            executed_sha256 = hashlib.sha256(executed_script.encode()).hexdigest()
            dependency_sha256 = hashlib.sha256(dependency_lock).hexdigest()
            _atomic_json(
                harness_path,
                {
                    "official_sha256": official_sha256,
                    "executed_sha256": executed_sha256,
                    "offline_transformed": True,
                    "transformation": (
                        "remove-known-pinned-uv-bootstrap-and-set-output-dir"
                    ),
                    "dependency_lock_sha256": dependency_sha256,
                },
            )
            _atomic_json(
                evidence_path,
                {
                    "schema_version": 1,
                    "task_id": task.task_id,
                    "sandbox_id": handle.native_id,
                    "network_policy": self.network_policy,
                    "input_bundle_sha256": bundle.sha256,
                    "artifact_records": [asdict(record) for record in records],
                    "artifact_manifest_sha256": hashlib.sha256(
                        expected_payload
                    ).hexdigest(),
                    "artifact_integrity_verified": True,
                    "official_test_sha256": official_sha256,
                    "executed_test_sha256": executed_sha256,
                    "dependency_lock_sha256": dependency_sha256,
                    "reward": score.reward,
                    "tests_passed": score.tests_passed,
                    "tests_failed": score.tests_failed,
                    "diagnostic_tags": list(score.diagnostic_tags),
                },
            )
            if self.answer_free_evidence_builder is not None:
                if ctrf is None:
                    raise SandboxInfrastructureError(
                        "verifier.evidence", "answer-free evidence needs checker output"
                    )
                try:
                    answer_free = self.answer_free_evidence_builder(ctrf_path)
                except Exception as exc:  # noqa: BLE001 - trusted sanitizer boundary.
                    raise SandboxInfrastructureError(
                        "verifier.evidence", f"{type(exc).__name__}: {exc}"
                    ) from exc
                _atomic_json(
                    verifier_dir / "answer-free-evidence.json",
                    answer_free,
                )
            _atomic_json(verifier_dir / "official-score.json", asdict(score))
            mark_finished(lifecycle_path, at=self.clock())
            finished = True
        except SandboxInfrastructureError as exc:
            primary_error = exc
        except Exception as exc:  # noqa: BLE001 - final typed boundary.
            primary_error = SandboxInfrastructureError(
                "verifier.coordinator", f"{type(exc).__name__}: {exc}"
            )
        finally:
            _finish_and_cleanup(
                backend=self.backend,
                handle=handle,
                lifecycle_path=lifecycle_path if handle is not None else None,
                clock=self.clock,
                role="verifier",
                primary_error=primary_error,
                finished=finished,
            )
        if primary_error is not None:
            raise primary_error
        assert score is not None
        return score
