"""Secure E2B execution for the full-harness NexAU evolver."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from ..e2b_lease import E2BLeasePool
from ..qfbench_images import NEXAU_REQUIREMENTS_LOCK, NEXAU_RUNTIME_PYTHON
from .bundles import build_evolver_input_bundle, extract_candidate_archive
from .e2b_nexau import (
    _command_payload,
    _read_optional_text,
    _run_checked,
    _run_command_result,
    _scrub,
    _write_json,
    _write_sandbox_file,
    build_worker_network,
    sanitize_worker_env,
)
from .e2b_protocol import E2BSandboxFactory, SDKSandboxFactory


_REMOTE_RUNNER = Path(__file__).with_name("remote_evolver.py")
_RUNTIME_BRIDGE = Path(__file__).parents[1] / "runtime_bridge.py"
_DISCOVERY_METRICS = Path(__file__).parents[1] / "evolver_discovery.py"
_PUBLIC_CONTRACT_EVIDENCE = (
    Path(__file__).parents[1] / "public_contract_evidence.py"
)


class E2BEvolverError(RuntimeError):
    """The isolated evolver failed or returned an unsafe candidate."""


@dataclass(frozen=True)
class E2BEvolverConfig:
    template: str
    timeout_seconds: int = 1_800
    max_candidate_files: int = 2_000
    max_candidate_bytes: int = 64 * 1024 * 1024
    lease_timeout_seconds: float = 120

    def __post_init__(self) -> None:
        if not self.template.strip():
            raise E2BEvolverError("evolver template must not be empty")
        if self.timeout_seconds < 1:
            raise E2BEvolverError("evolver timeout must be positive")
        if self.max_candidate_files < 1 or self.max_candidate_bytes < 1:
            raise E2BEvolverError("candidate output limits must be positive")


@dataclass(frozen=True)
class E2BEvolverResult:
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
    cleaned_up: bool


def _digest_tree(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(
        (item for item in root.rglob("*") if item.is_file()),
        key=lambda item: item.relative_to(root).as_posix(),
    ):
        relative = path.relative_to(root).as_posix().encode()
        payload = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def _lifecycle(
    path: Path,
    *,
    run_id: str,
    iteration: int,
    sandbox_id: str,
    cleaned_up: bool,
    cleanup_error: str | None = None,
) -> None:
    payload = {
        "schema_version": 1,
        "run_id": run_id,
        "iteration": iteration,
        "role": "evolver",
        "sandbox_id": sandbox_id,
        "cleaned_up": cleaned_up,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if cleanup_error:
        payload["cleanup_error"] = cleanup_error
    _write_json(path, payload)


def _load_completed(
    evolution_dir: Path,
    *,
    iteration: int,
    input_bundle_sha256: str,
) -> E2BEvolverResult | None:
    manifest_path = evolution_dir / "result.json"
    if not manifest_path.is_file():
        return None
    try:
        payload = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise E2BEvolverError(f"invalid completed evolver result: {exc}") from exc
    expected = (iteration, input_bundle_sha256, "candidate", True)
    actual = (
        payload.get("iteration"),
        payload.get("input_bundle_sha256"),
        payload.get("candidate_dir"),
        payload.get("cleaned_up"),
    )
    if actual != expected:
        raise E2BEvolverError(
            f"completed evolver result identity mismatch: expected {expected}, found {actual}"
        )
    candidate_dir = evolution_dir / "candidate"
    candidate_digest = _digest_tree(candidate_dir)
    if candidate_digest != payload.get("candidate_digest"):
        raise E2BEvolverError("completed evolver candidate digest mismatch")
    lifecycle_name = payload.get("lifecycle_file")
    if not isinstance(lifecycle_name, str) or Path(lifecycle_name).name != lifecycle_name:
        raise E2BEvolverError("completed evolver lifecycle identity is unsafe")
    paths = {
        "trace_uri": evolution_dir / "raw_trace.jsonl",
        "final_uri": evolution_dir / "final.txt",
        "prediction_uri": evolution_dir / "prediction.json",
        "access_summary_uri": evolution_dir / "access-summary.json",
        "summary_uri": evolution_dir / "summary.json",
        "command_log_uri": evolution_dir / "command.json",
        "lifecycle_uri": evolution_dir / lifecycle_name,
        "dependency_lock_uri": evolution_dir / "nexau-requirements.lock",
    }
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise E2BEvolverError(f"completed evolver result files are missing: {missing}")
    lifecycle = json.loads(paths["lifecycle_uri"].read_text())
    if lifecycle.get("cleaned_up") is not True:
        raise E2BEvolverError("completed evolver sandbox was not cleaned up")
    return E2BEvolverResult(
        iteration=iteration,
        candidate_dir=candidate_dir,
        candidate_digest=candidate_digest,
        input_bundle_sha256=input_bundle_sha256,
        sandbox_id=str(payload.get("sandbox_id", "")),
        cleaned_up=True,
        **paths,
    )


class E2BFullHarnessProposer:
    """Run exactly one evidence-driven candidate edit in a secure sandbox."""

    def __init__(
        self,
        config: E2BEvolverConfig,
        *,
        sandbox_factory: E2BSandboxFactory | None = None,
        lease_pool: E2BLeasePool,
    ) -> None:
        self.config = config
        self.sandbox_factory = sandbox_factory or SDKSandboxFactory()
        self.lease_pool = lease_pool

    def propose(
        self,
        *,
        candidate_dir: str | Path,
        evidence_dir: str | Path,
        evolver_dir: str | Path,
        diagnosis: str,
        iteration: int,
        run_id: str,
        run_dir: str | Path,
        model_env: Mapping[str, str],
    ) -> E2BEvolverResult:
        if iteration < 1:
            raise E2BEvolverError("iteration must be positive")
        evolution_dir = (
            Path(run_dir).resolve() / "evolutions" / f"iteration-{iteration:04d}"
        )
        evolution_dir.mkdir(parents=True, exist_ok=True)
        input_bundle = build_evolver_input_bundle(
            candidate_dir,
            evidence_dir,
            evolver_dir,
            evolution_dir / "input.tar",
            forbidden_values=(str(model_env.get("LLM_API_KEY", "")),),
        )
        safe_diagnosis = _scrub(diagnosis, model_env)
        diagnosis_path = evolution_dir / "diagnosis.txt"
        diagnosis_path.write_text(safe_diagnosis, encoding="utf-8")
        env = sanitize_worker_env(model_env)
        network = build_worker_network(model_env)
        command_log = evolution_dir / "command.json"
        lifecycle_path = evolution_dir / "lifecycle.json"
        dependency_lock_path = evolution_dir / "nexau-requirements.lock"
        trace_path = evolution_dir / "raw_trace.jsonl"
        final_path = evolution_dir / "final.txt"
        prediction_path = evolution_dir / "prediction.json"
        access_summary_path = evolution_dir / "access-summary.json"
        summary_path = evolution_dir / "summary.json"
        output_dir = evolution_dir / "candidate"
        completed = _load_completed(
            evolution_dir,
            iteration=iteration,
            input_bundle_sha256=input_bundle.sha256,
        )
        if completed is not None:
            return completed
        for lifecycle in sorted(
            evolution_dir.glob("*-sandbox-lifecycle.json")
        ):
            try:
                lifecycle_payload = json.loads(lifecycle.read_text())
            except (OSError, json.JSONDecodeError) as exc:
                raise E2BEvolverError(
                    f"invalid prior evolver lifecycle {lifecycle}: {exc}"
                ) from exc
            if lifecycle_payload.get("cleaned_up") is not True:
                raise E2BEvolverError(
                    "unfinished evolver sandbox requires exact-ID reaper before resume: "
                    f"{lifecycle_payload.get('sandbox_id')}"
                )
        if output_dir.exists():
            shutil.rmtree(output_dir)
        sandbox = None
        sandbox_id = ""
        cleanup_ok = False
        lifecycle_path: Path | None = None
        sandbox_timeout = self.config.timeout_seconds + 180

        with self.lease_pool.acquire(
            f"evolver:{run_id}:{iteration}",
            timeout_seconds=self.config.lease_timeout_seconds,
        ) as lease:
            try:
                sandbox = self.sandbox_factory.create(
                    template=self.config.template,
                    timeout=sandbox_timeout,
                    metadata={
                        "qea_role": "evolver",
                        "qea_run_id": run_id,
                        "qea_iteration": str(iteration),
                    },
                    envs=env,
                    secure=True,
                    allow_internet_access=True,
                    network=network,
                )
                sandbox_id = str(sandbox.sandbox_id)
                lifecycle_token = hashlib.sha256(sandbox_id.encode()).hexdigest()[:12]
                lifecycle_path = (
                    evolution_dir
                    / f"evolver-{lifecycle_token}-sandbox-lifecycle.json"
                )
                _lifecycle(
                    lifecycle_path,
                    run_id=run_id,
                    iteration=iteration,
                    sandbox_id=sandbox_id,
                    cleaned_up=False,
                )
                dependency_lock = _read_optional_text(
                    sandbox, NEXAU_REQUIREMENTS_LOCK
                )
                if dependency_lock is None or not dependency_lock.strip():
                    raise E2BEvolverError(
                        "evolver template NexAU dependency lock is missing or empty"
                    )
                dependency_lock_path.write_text(dependency_lock, encoding="utf-8")
                lease.heartbeat()
                _write_sandbox_file(
                    sandbox, "/tmp/qea-evolver.tar", input_bundle.path.read_bytes()
                )
                _write_sandbox_file(
                    sandbox, "/qea/remote_evolver.py", _REMOTE_RUNNER.read_bytes()
                )
                _write_sandbox_file(
                    sandbox, "/qea/runtime_bridge.py", _RUNTIME_BRIDGE.read_bytes()
                )
                _write_sandbox_file(
                    sandbox,
                    "/qea/evolver_discovery.py",
                    _DISCOVERY_METRICS.read_bytes(),
                )
                _write_sandbox_file(
                    sandbox,
                    "/qea/public_contract_evidence.py",
                    _PUBLIC_CONTRACT_EVIDENCE.read_bytes(),
                )
                _write_sandbox_file(
                    sandbox, "/qea/diagnosis.txt", diagnosis_path.read_bytes()
                )
                _run_checked(
                    sandbox,
                    "mkdir -p /qea/input /qea/result && "
                    "tar -xf /tmp/qea-evolver.tar -C /qea/input && "
                    "chmod -R a-w /qea/input/evidence /qea/input/evolve_agent && "
                    "chmod -R u+w /qea/input/candidate /qea/result",
                    label="evolver setup command",
                    timeout=min(120, sandbox_timeout),
                )
                command = (
                    f"{NEXAU_RUNTIME_PYTHON} /qea/remote_evolver.py "
                    "--candidate-dir /qea/input/candidate "
                    "--evidence-dir /qea/input/evidence "
                    "--evolver-dir /qea/input/evolve_agent "
                    "--result-dir /qea/result "
                    "--diagnosis-file /qea/diagnosis.txt "
                    f"--iteration {iteration}"
                )
                command_result = _run_command_result(
                    sandbox,
                    command,
                    timeout=self.config.timeout_seconds,
                    envs=env,
                )
                _write_json(command_log, _command_payload(command_result, model_env))
                if int(getattr(command_result, "exit_code", -1)) != 0:
                    raise E2BEvolverError(
                        "evolver command failed with exit "
                        f"{getattr(command_result, 'exit_code', -1)}"
                    )
                lease.heartbeat()
                archive = sandbox.files.read(
                    "/qea/result/candidate.tar", format="bytes"
                )
                if not isinstance(archive, bytes):
                    archive = bytes(archive)
                extract_candidate_archive(
                    archive,
                    output_dir,
                    max_files=self.config.max_candidate_files,
                    max_bytes=self.config.max_candidate_bytes,
                )
                for remote, local in (
                    ("/qea/result/raw_trace.jsonl", trace_path),
                    ("/qea/result/final.txt", final_path),
                    ("/qea/result/prediction.json", prediction_path),
                    ("/qea/result/access-summary.json", access_summary_path),
                    ("/qea/result/summary.json", summary_path),
                ):
                    text = sandbox.files.read(remote, format="text")
                    local.write_text(_scrub(str(text), model_env), encoding="utf-8")
            finally:
                cleanup_error = None
                if sandbox is not None:
                    try:
                        sandbox.kill()
                        cleanup_ok = True
                    except Exception as exc:  # noqa: BLE001
                        cleanup_error = f"{type(exc).__name__}: {_scrub(str(exc), model_env)}"
                if sandbox_id and lifecycle_path is not None:
                    _lifecycle(
                        lifecycle_path,
                        run_id=run_id,
                        iteration=iteration,
                        sandbox_id=sandbox_id,
                        cleaned_up=cleanup_ok,
                        cleanup_error=cleanup_error,
                    )
                _write_json(
                    evolution_dir / "cleanup.json",
                    {
                        "run_id": run_id,
                        "iteration": iteration,
                        "sandbox_id": sandbox_id,
                        "cleaned_up": cleanup_ok,
                    },
                )

        result = E2BEvolverResult(
            iteration=iteration,
            candidate_dir=output_dir,
            candidate_digest=_digest_tree(output_dir),
            input_bundle_sha256=input_bundle.sha256,
            trace_uri=trace_path,
            final_uri=final_path,
            prediction_uri=prediction_path,
            access_summary_uri=access_summary_path,
            summary_uri=summary_path,
            command_log_uri=command_log,
            lifecycle_uri=lifecycle_path,
            dependency_lock_uri=dependency_lock_path,
            sandbox_id=sandbox_id,
            cleaned_up=cleanup_ok,
        )
        _write_json(
            evolution_dir / "result.json",
            {
                "iteration": result.iteration,
                "candidate_dir": result.candidate_dir.name,
                "candidate_digest": result.candidate_digest,
                "input_bundle_sha256": result.input_bundle_sha256,
                "sandbox_id": result.sandbox_id,
                "cleaned_up": result.cleaned_up,
                "lifecycle_file": result.lifecycle_uri.name,
            },
        )
        return result
