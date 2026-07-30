"""Run one full-harness evolver through a provider-neutral sandbox backend."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Callable, Mapping

from ..qfbench_images import NEXAU_REQUIREMENTS_LOCK, NEXAU_RUNTIME_PYTHON
from ..resource_lease import HostResourceLeasePool, ResourceRequest
from ..sandbox_backend import SandboxBackend, SandboxCommandResult, SandboxSpec
from ..sandbox_lifecycle import (
    create_lifecycle,
    load_lifecycle,
    mark_finished,
    mark_started,
)
from .bundles import (
    BundleError,
    build_evolver_input_bundle,
    extract_candidate_archive,
)
from .sandbox_proxy import SandboxProxyManager
from .sandbox_runtime import (
    SandboxInfrastructureError,
    SandboxResourceContract,
    atomic_json,
    backend_call,
    finish_and_cleanup,
    public_model_environment,
    require_tmpfs,
    run_required,
    utc_now,
    validate_public_model_env,
    write_command_log,
)


_REMOTE_RUNNER = Path(__file__).with_name("remote_evolver.py")
_REQUIRED_TMPFS = frozenset({"/tmp", "/qea"})
_TASK_ID = "full-harness-evolver"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_CREDENTIAL_ASSIGNMENT = re.compile(
    r"(?i)\b(api[_-]?key|token|secret|password)\b\s*[:=]\s*([^\s,;]+)"
)
_DOWNLOAD_LIMITS = {
    "raw_trace.jsonl": 4 * 1024 * 1024,
    "final.txt": 512 * 1024,
    "prediction.json": 2 * 1024 * 1024,
    "access-summary.json": 2 * 1024 * 1024,
    "summary.json": 2 * 1024 * 1024,
}
_JSON_EVIDENCE = frozenset(
    {"prediction.json", "access-summary.json", "summary.json"}
)


@dataclass(frozen=True)
class SandboxEvolverConfig:
    image_ref: str
    resource_contract: SandboxResourceContract
    command_timeout_seconds: int = 1800
    max_input_files: int = 2000
    max_input_bytes: int = 512 * 1024 * 1024
    max_candidate_files: int = 2000
    max_candidate_bytes: int = 64 * 1024 * 1024
    lease_timeout_seconds: float = 120.0

    def __post_init__(self) -> None:
        if not isinstance(self.image_ref, str) or not self.image_ref:
            raise SandboxInfrastructureError(
                "evolver.config", "image_ref must be non-empty"
            )
        if not isinstance(self.resource_contract, SandboxResourceContract):
            raise SandboxInfrastructureError(
                "evolver.config",
                "resource_contract must be a SandboxResourceContract",
            )
        require_tmpfs(self.resource_contract, _REQUIRED_TMPFS, role="evolver")
        for name in (
            "command_timeout_seconds",
            "max_input_files",
            "max_input_bytes",
            "max_candidate_files",
            "max_candidate_bytes",
        ):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise SandboxInfrastructureError(
                    "evolver.config", f"{name} must be a positive integer"
                )
        if self.resource_contract.timeout_seconds < self.command_timeout_seconds:
            raise SandboxInfrastructureError(
                "evolver.config",
                "sandbox lifetime must be at least the command timeout",
            )
        if (
            isinstance(self.lease_timeout_seconds, bool)
            or not isinstance(self.lease_timeout_seconds, (int, float))
            or not math.isfinite(self.lease_timeout_seconds)
            or self.lease_timeout_seconds < 0
        ):
            raise SandboxInfrastructureError(
                "evolver.config",
                "lease_timeout_seconds must be non-negative and finite",
            )


@dataclass(frozen=True)
class SandboxEvolverResult:
    iteration: int
    candidate_dir: Path
    candidate_digest: str
    input_bundle_sha256: str
    trace_uri: Path
    final_uri: Path
    prediction_uri: Path
    access_summary_uri: Path
    summary_uri: Path
    command_log_uri: Path
    lifecycle_uri: Path
    dependency_lock_uri: Path
    sandbox_id: str
    proxy_sandbox_id: str
    network_id: str
    cleaned_up: bool
    backend: str
    spec_sha256: str


def _digest_tree(root: Path) -> str:
    if root.is_symlink() or not root.is_dir():
        raise SandboxInfrastructureError(
            "evolver.candidate", f"candidate directory is unavailable: {root}"
        )
    digest = hashlib.sha256()
    for path in sorted(
        root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()
    ):
        relative_path = path.relative_to(root)
        if path.is_symlink():
            raise SandboxInfrastructureError(
                "evolver.candidate", f"candidate symlink is forbidden: {relative_path}"
            )
        if path.is_dir():
            continue
        if not path.is_file():
            raise SandboxInfrastructureError(
                "evolver.candidate", f"candidate entry is not regular: {relative_path}"
            )
        relative = relative_path.as_posix().encode()
        payload = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _safe_diagnosis(value: object) -> bytes:
    if isinstance(value, str):
        text = value
    elif isinstance(value, Mapping):
        text = json.dumps(value, sort_keys=True, separators=(",", ":"))
    else:
        raise SandboxInfrastructureError(
            "evolver.diagnosis", "diagnosis must be text or a JSON object"
        )
    encoded = text.encode("utf-8")
    if len(encoded) > 2 * 1024 * 1024:
        raise SandboxInfrastructureError(
            "evolver.diagnosis", "diagnosis exceeds its bounded contract"
        )
    scrubbed = _CREDENTIAL_ASSIGNMENT.sub(r"\1=[REDACTED]", text)
    return scrubbed.encode("utf-8")


def _attempt_identity(
    *,
    run_id: str,
    iteration: int,
    input_bundle_sha256: str,
    diagnosis_sha256: str,
    model_name: str,
    image_ref: str,
    spec_sha256: str,
    backend: str,
) -> str:
    payload = {
        "backend": backend,
        "diagnosis_sha256": diagnosis_sha256,
        "image_ref": image_ref,
        "input_bundle_sha256": input_bundle_sha256,
        "iteration": iteration,
        "model_name": model_name,
        "run_id": run_id,
        "spec_sha256": spec_sha256,
    }
    return _sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    )


def _combined_request(
    evolver: SandboxResourceContract,
    proxy: SandboxResourceContract,
) -> ResourceRequest:
    return ResourceRequest(
        cpu_count=evolver.cpu_count + proxy.cpu_count,
        memory_mb=evolver.memory_mb + proxy.memory_mb,
        pids_limit=evolver.pids_limit + proxy.pids_limit,
        tmpfs_mb=sum(evolver.writable_tmpfs_mb.values())
        + sum(proxy.writable_tmpfs_mb.values()),
        sandboxes=2,
    )


def _validate_evidence(name: str, payload: object) -> bytes:
    if not isinstance(payload, bytes):
        raise SandboxInfrastructureError(
            "evolver.download", f"{name} download is not bytes"
        )
    if len(payload) > _DOWNLOAD_LIMITS[name]:
        raise SandboxInfrastructureError(
            "evolver.download", f"{name} exceeds its bounded contract"
        )
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SandboxInfrastructureError(
            "evolver.download", f"{name} is not UTF-8"
        ) from exc
    if name in _JSON_EVIDENCE:
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SandboxInfrastructureError(
                "evolver.download", f"{name} is invalid JSON"
            ) from exc
        if not isinstance(value, dict):
            raise SandboxInfrastructureError(
                "evolver.download", f"{name} must contain a JSON object"
            )
    elif name == "raw_trace.jsonl":
        for line_number, line in enumerate(text.splitlines(), start=1):
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SandboxInfrastructureError(
                    "evolver.download",
                    f"raw_trace.jsonl line {line_number} is invalid JSON",
                ) from exc
            if not isinstance(value, dict):
                raise SandboxInfrastructureError(
                    "evolver.download",
                    f"raw_trace.jsonl line {line_number} is not an object",
                )
    return payload


def _result_paths(evolution_dir: Path, lifecycle_path: Path) -> dict[str, Path]:
    return {
        "trace_uri": evolution_dir / "raw_trace.jsonl",
        "final_uri": evolution_dir / "final.txt",
        "prediction_uri": evolution_dir / "prediction.json",
        "access_summary_uri": evolution_dir / "access-summary.json",
        "summary_uri": evolution_dir / "summary.json",
        "command_log_uri": evolution_dir / "command.json",
        "lifecycle_uri": lifecycle_path,
        "dependency_lock_uri": evolution_dir / "nexau-requirements.lock",
    }


def _load_completed(
    evolution_dir: Path,
    *,
    expected_identity: Mapping[str, object],
    paths: Mapping[str, Path],
) -> SandboxEvolverResult | None:
    manifest_path = evolution_dir / "result.json"
    if not manifest_path.is_file():
        return None
    try:
        payload = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise SandboxInfrastructureError(
            "evolver.resume", f"invalid completed result: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise SandboxInfrastructureError(
            "evolver.resume", "completed result must be an object"
        )
    actual_identity = {name: payload.get(name) for name in expected_identity}
    if actual_identity != dict(expected_identity):
        raise SandboxInfrastructureError(
            "evolver.resume",
            f"completed result identity mismatch: expected {dict(expected_identity)}, "
            f"found {actual_identity}",
        )
    if payload.get("cleaned_up") is not True:
        raise SandboxInfrastructureError(
            "evolver.resume", "completed result was not exactly cleaned"
        )
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise SandboxInfrastructureError(
            "evolver.resume", f"completed result files are missing: {missing}"
        )
    candidate_dir = evolution_dir / "candidate"
    candidate_digest = _digest_tree(candidate_dir)
    if candidate_digest != payload.get("candidate_digest"):
        raise SandboxInfrastructureError(
            "evolver.resume", "completed candidate digest mismatch"
        )
    lifecycle = load_lifecycle(paths["lifecycle_uri"])
    if (
        lifecycle.cleaned_up is not True
        or lifecycle.native_id != payload.get("sandbox_id")
        or lifecycle.spec_sha256 != payload.get("spec_sha256")
        or lifecycle.attempt_identity_sha256
        != payload.get("attempt_identity_sha256")
    ):
        raise SandboxInfrastructureError(
            "evolver.resume", "completed lifecycle identity mismatch"
        )
    file_digests = payload.get("file_sha256")
    if not isinstance(file_digests, dict) or any(
        _SHA256.fullmatch(str(file_digests.get(name, ""))) is None
        or _sha256(path.read_bytes()) != file_digests.get(name)
        for name, path in paths.items()
    ):
        raise SandboxInfrastructureError(
            "evolver.resume", "completed result evidence digest mismatch"
        )
    return SandboxEvolverResult(
        iteration=int(payload["iteration"]),
        candidate_dir=candidate_dir,
        candidate_digest=candidate_digest,
        input_bundle_sha256=str(payload["input_bundle_sha256"]),
        sandbox_id=str(payload["sandbox_id"]),
        proxy_sandbox_id=str(payload["proxy_sandbox_id"]),
        network_id=str(payload["network_id"]),
        cleaned_up=True,
        backend=str(payload["backend"]),
        spec_sha256=str(payload["spec_sha256"]),
        **paths,
    )


class SandboxFullHarnessProposer:
    """Run exactly one evidence-driven edit behind a per-attempt model proxy."""

    def __init__(
        self,
        *,
        config: SandboxEvolverConfig,
        backend: SandboxBackend,
        lifecycle_root: str | Path,
        proxy_manager: SandboxProxyManager,
        resource_pool: HostResourceLeasePool,
        model_name: str,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        if not isinstance(config, SandboxEvolverConfig):
            raise SandboxInfrastructureError(
                "evolver.config", "config must be a SandboxEvolverConfig"
            )
        if getattr(proxy_manager, "backend", None) is not backend:
            raise SandboxInfrastructureError(
                "evolver.config", "evolver and proxy must use the same backend"
            )
        proxy_resources = getattr(
            getattr(proxy_manager, "config", None), "resource_contract", None
        )
        if not isinstance(proxy_resources, SandboxResourceContract):
            raise SandboxInfrastructureError(
                "evolver.config", "proxy resource contract is unavailable"
            )
        if (
            not isinstance(model_name, str)
            or not model_name.strip()
            or getattr(proxy_manager.config, "allowed_model", None) != model_name
        ):
            raise SandboxInfrastructureError(
                "evolver.config", "proxy and evolver model identity differ"
            )
        self.config = config
        self.backend = backend
        self.lifecycle_root = Path(lifecycle_root).expanduser().resolve()
        self.proxy_manager = proxy_manager
        self.resource_pool = resource_pool
        self.model_name = model_name
        self.clock = clock
        self.proxy_resources = proxy_resources

    def propose(
        self,
        *,
        candidate_dir: str | Path,
        evidence_dir: str | Path,
        evolver_dir: str | Path,
        diagnosis: object,
        iteration: int,
        run_id: str,
        run_dir: str | Path,
        model_env: Mapping[str, str] | None = None,
    ) -> SandboxEvolverResult:
        if type(iteration) is not int or iteration < 1:
            raise SandboxInfrastructureError(
                "evolver.config", "iteration must be a positive integer"
            )
        run_root = Path(run_dir).expanduser().resolve()
        evolution_dir = run_root / "evolutions" / f"iteration-{iteration:04d}"
        evolution_dir.mkdir(parents=True, exist_ok=True)
        attempt_id = f"evolver-iteration-{iteration}"
        proxy_url = (
            f"http://qea-model-proxy:{self.proxy_manager.config.listen_port}"
            f"{self.proxy_manager.config.allowed_path_prefix}"
        )
        environment = public_model_environment(
            proxy_base_url=proxy_url, model_name=self.model_name
        )
        validate_public_model_env(model_env, environment, role="evolver")
        pending_input_path = evolution_dir / "input.pending.tar"
        try:
            input_bundle = build_evolver_input_bundle(
                candidate_dir,
                evidence_dir,
                evolver_dir,
                pending_input_path,
                max_files=self.config.max_input_files,
                max_bytes=self.config.max_input_bytes,
            )
        except BundleError as exc:
            if pending_input_path.exists():
                pending_input_path.unlink()
            raise SandboxInfrastructureError(
                "evolver.input", f"{type(exc).__name__}: {exc}"
            ) from exc
        diagnosis_payload = _safe_diagnosis(diagnosis)
        diagnosis_sha256 = _sha256(diagnosis_payload)
        spec = SandboxSpec(
            role="evolver",
            run_id=run_id,
            attempt_id=attempt_id,
            task_id=_TASK_ID,
            image_ref=self.config.image_ref,
            cpu_count=self.config.resource_contract.cpu_count,
            memory_mb=self.config.resource_contract.memory_mb,
            pids_limit=self.config.resource_contract.pids_limit,
            timeout_seconds=self.config.resource_contract.timeout_seconds,
            network_policy="worker-proxy-only",
            environment=environment,
            writable_tmpfs_mb=self.config.resource_contract.writable_tmpfs_mb,
            network_scope=attempt_id,
        )
        backend_name = str(getattr(self.backend, "backend_name", ""))
        if not backend_name:
            raise SandboxInfrastructureError(
                "evolver.config", "sandbox backend has no stable name"
            )
        attempt_identity = _attempt_identity(
            run_id=run_id,
            iteration=iteration,
            input_bundle_sha256=input_bundle.sha256,
            diagnosis_sha256=diagnosis_sha256,
            model_name=self.model_name,
            image_ref=self.config.image_ref,
            spec_sha256=spec.spec_sha256,
            backend=backend_name,
        )
        lifecycle_path = (
            self.lifecycle_root
            / run_id
            / attempt_id
            / "evolver-sandbox-lifecycle-v2.json"
        )
        paths = _result_paths(evolution_dir, lifecycle_path)
        expected_identity = {
            "run_id": run_id,
            "iteration": iteration,
            "input_bundle_sha256": input_bundle.sha256,
            "diagnosis_sha256": diagnosis_sha256,
            "model_name": self.model_name,
            "image_ref": self.config.image_ref,
            "spec_sha256": spec.spec_sha256,
            "backend": backend_name,
            "attempt_identity_sha256": attempt_identity,
        }
        try:
            completed = _load_completed(
                evolution_dir, expected_identity=expected_identity, paths=paths
            )
        except BaseException:
            if pending_input_path.exists():
                pending_input_path.unlink()
            raise
        if completed is not None:
            pending_input_path.unlink()
            return completed

        quarantine_path = (
            run_root
            / "attempts"
            / attempt_id
            / "proxy-audit.quarantined.json"
        )
        if quarantine_path.exists() or quarantine_path.is_symlink():
            pending_input_path.unlink()
            raise SandboxInfrastructureError(
                "evolver.resume",
                "quarantined model request identity must not reopen a sandbox",
            )
        if lifecycle_path.exists() or lifecycle_path.is_symlink():
            try:
                lifecycle = load_lifecycle(lifecycle_path)
            except BaseException:
                pending_input_path.unlink()
                raise
            if not lifecycle.cleaned_up:
                pending_input_path.unlink()
                raise SandboxInfrastructureError(
                    "evolver.resume",
                    "unfinished evolver sandbox requires exact-ID cleanup",
                )

        output_dir = evolution_dir / "candidate"
        if output_dir.exists():
            if output_dir.is_symlink() or any(output_dir.iterdir()):
                pending_input_path.unlink()
                raise SandboxInfrastructureError(
                    "evolver.resume",
                    "uncommitted candidate output makes the request identity ambiguous",
                )
            output_dir.rmdir()

        committed_input_path = evolution_dir / "input.tar"
        os.replace(pending_input_path, committed_input_path)
        input_bundle = replace(input_bundle, path=committed_input_path)
        dependency_lock = b""
        session = None
        handle = None
        primary_error: BaseException | None = None
        finished = False

        request = _combined_request(
            self.config.resource_contract, self.proxy_resources
        )
        lease = self.resource_pool.acquire(
            f"evolver:{run_id}:{iteration}",
            request,
            timeout_seconds=self.config.lease_timeout_seconds,
        )
        with lease:
            with self.proxy_manager.open(
                run_id=run_id,
                attempt_id=attempt_id,
                task_id=_TASK_ID,
                caller_role="evolver",
                run_dir=run_root,
            ) as opened_session:
                session = opened_session
                if (
                    session.network_scope != attempt_id
                    or session.base_url != environment["LLM_BASE_URL"]
                    or session.allowed_model != self.model_name
                ):
                    raise SandboxInfrastructureError(
                        "evolver.proxy", "proxy session identity differs from evolver spec"
                    )
                try:
                    handle = backend_call(
                        "evolver.create", lambda: self.backend.create(spec)
                    )
                    backend_call(
                        "evolver.lifecycle",
                        lambda: create_lifecycle(
                            lifecycle_path,
                            handle=handle,
                            spec=spec,
                            attempt_identity_sha256=attempt_identity,
                            at=self.clock(),
                        ),
                    )
                    backend_call(
                        "evolver.start", lambda: self.backend.start(handle)
                    )
                    backend_call(
                        "evolver.lifecycle",
                        lambda: mark_started(lifecycle_path, at=self.clock()),
                    )
                    dependency_lock = backend_call(
                        "evolver.dependency",
                        lambda: self.backend.read_bytes(
                            handle, NEXAU_REQUIREMENTS_LOCK
                        ),
                    )
                    if (
                        not isinstance(dependency_lock, bytes)
                        or not dependency_lock.strip()
                    ):
                        raise SandboxInfrastructureError(
                            "evolver.dependency",
                            "NexAU dependency lock is missing or empty",
                        )
                    paths["dependency_lock_uri"].write_bytes(dependency_lock)
                    for remote_path, payload in (
                        ("/qea/evolver-input.tar", input_bundle.path.read_bytes()),
                        ("/qea/remote_evolver.py", _REMOTE_RUNNER.read_bytes()),
                        ("/qea/diagnosis.txt", diagnosis_payload),
                    ):
                        backend_call(
                            "evolver.upload",
                            lambda remote_path=remote_path, payload=payload: (
                                self.backend.put_bytes(handle, remote_path, payload)
                            ),
                        )
                    setup_timeout = min(
                        120, self.config.resource_contract.timeout_seconds
                    )
                    for argv in (
                        ("mkdir", "-p", "/qea/input", "/qea/result"),
                        (
                            "tar",
                            "-xf",
                            "/qea/evolver-input.tar",
                            "-C",
                            "/qea/input",
                        ),
                        (
                            "chmod",
                            "-R",
                            "a-w",
                            "/qea/input/evidence",
                            "/qea/input/evolve_agent",
                        ),
                        (
                            "chmod",
                            "-R",
                            "u+w",
                            "/qea/input/candidate",
                            "/qea/result",
                        ),
                    ):
                        run_required(
                            self.backend,
                            handle,
                            argv,
                            environment={},
                            timeout_seconds=setup_timeout,
                            phase="evolver.setup",
                        )
                    command = (
                        NEXAU_RUNTIME_PYTHON,
                        "/qea/remote_evolver.py",
                        "--candidate-dir",
                        "/qea/input/candidate",
                        "--evidence-dir",
                        "/qea/input/evidence",
                        "--evolver-dir",
                        "/qea/input/evolve_agent",
                        "--result-dir",
                        "/qea/result",
                        "--diagnosis-file",
                        "/qea/diagnosis.txt",
                        "--iteration",
                        str(iteration),
                    )
                    command_result = backend_call(
                        "evolver.command",
                        lambda: self.backend.run(
                            handle,
                            command,
                            environment=environment,
                            timeout_seconds=self.config.command_timeout_seconds,
                        ),
                    )
                    if not isinstance(command_result, SandboxCommandResult):
                        raise SandboxInfrastructureError(
                            "evolver.command", "backend returned an invalid result"
                        )
                    write_command_log(paths["command_log_uri"], command_result)
                    if command_result.timed_out:
                        raise SandboxInfrastructureError(
                            "evolver.command", "evolver command timed out"
                        )
                    if command_result.exit_code != 0:
                        raise SandboxInfrastructureError(
                            "evolver.command",
                            f"evolver command exited {command_result.exit_code}: "
                            f"{command_result.stderr or command_result.stdout}",
                        )
                    archive = backend_call(
                        "evolver.download",
                        lambda: self.backend.read_bytes(
                            handle, "/qea/result/candidate.tar"
                        ),
                    )
                    if not isinstance(archive, bytes):
                        raise SandboxInfrastructureError(
                            "evolver.download", "candidate archive is not bytes"
                        )
                    try:
                        extract_candidate_archive(
                            archive,
                            output_dir,
                            max_files=self.config.max_candidate_files,
                            max_bytes=self.config.max_candidate_bytes,
                        )
                    except BundleError as exc:
                        raise SandboxInfrastructureError(
                            "evolver.candidate", f"{type(exc).__name__}: {exc}"
                        ) from exc
                    for remote_name, path_key in (
                        ("raw_trace.jsonl", "trace_uri"),
                        ("final.txt", "final_uri"),
                        ("prediction.json", "prediction_uri"),
                        ("access-summary.json", "access_summary_uri"),
                        ("summary.json", "summary_uri"),
                    ):
                        payload = backend_call(
                            "evolver.download",
                            lambda remote_name=remote_name: self.backend.read_bytes(
                                handle, f"/qea/result/{remote_name}"
                            ),
                        )
                        paths[path_key].write_bytes(
                            _validate_evidence(remote_name, payload)
                        )
                    mark_finished(lifecycle_path, at=self.clock())
                    finished = True
                except SandboxInfrastructureError as exc:
                    primary_error = exc
                except Exception as exc:  # noqa: BLE001 - typed final boundary.
                    primary_error = SandboxInfrastructureError(
                        "evolver.coordinator", f"{type(exc).__name__}: {exc}"
                    )
                finally:
                    finish_and_cleanup(
                        backend=self.backend,
                        handle=handle,
                        lifecycle_path=lifecycle_path if handle is not None else None,
                        clock=self.clock,
                        role="evolver",
                        primary_error=primary_error,
                        finished=finished,
                    )
                if primary_error is not None:
                    raise primary_error

            if session is None or handle is None:
                raise SandboxInfrastructureError(
                    "evolver.coordinator", "sandbox identities were not recorded"
                )
            lifecycle = load_lifecycle(lifecycle_path)
            if not lifecycle.cleaned_up:
                raise SandboxInfrastructureError(
                    "evolver.cleanup", "evolver lifecycle is not exactly cleaned"
                )
            candidate_digest = _digest_tree(output_dir)
            result = SandboxEvolverResult(
                iteration=iteration,
                candidate_dir=output_dir,
                candidate_digest=candidate_digest,
                input_bundle_sha256=input_bundle.sha256,
                trace_uri=paths["trace_uri"],
                final_uri=paths["final_uri"],
                prediction_uri=paths["prediction_uri"],
                access_summary_uri=paths["access_summary_uri"],
                summary_uri=paths["summary_uri"],
                command_log_uri=paths["command_log_uri"],
                lifecycle_uri=lifecycle_path,
                dependency_lock_uri=paths["dependency_lock_uri"],
                sandbox_id=handle.native_id,
                proxy_sandbox_id=session.native_id,
                network_id=session.network_id,
                cleaned_up=True,
                backend=handle.backend,
                spec_sha256=handle.spec_sha256,
            )
            file_digests = {
                name: _sha256(path.read_bytes()) for name, path in paths.items()
            }
            atomic_json(
                evolution_dir / "result.json",
                {
                    "schema_version": 1,
                    **expected_identity,
                    "attempt_id": attempt_id,
                    "candidate_dir": "candidate",
                    "candidate_digest": candidate_digest,
                    "sandbox_id": result.sandbox_id,
                    "proxy_sandbox_id": result.proxy_sandbox_id,
                    "network_id": result.network_id,
                    "cleaned_up": True,
                    "file_sha256": file_digests,
                },
            )
            return result


__all__ = [
    "SandboxEvolverConfig",
    "SandboxEvolverResult",
    "SandboxFullHarnessProposer",
]
