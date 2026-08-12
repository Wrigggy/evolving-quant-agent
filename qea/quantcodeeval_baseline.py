"""Measured, resumable QuantCodeEval T16/T24 baseline runtime."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict
from pathlib import Path
from typing import Mapping

from .backends.rootless_docker import RootlessDockerBackend
from .benchmarks.quantcodeeval import (
    QuantCodeEvalSnapshot,
    QuantCodeEvalSplit,
    load_quantcodeeval_snapshot,
    verify_quantcodeeval_role_root,
)
from .evaluation import TaskAttempt
from .executors.execution_record import WorkerExecution
from .executors.sandbox_nexau import SandboxNexAUExecutor
from .executors.sandbox_proxy import (
    SandboxProxyConfig,
    SandboxProxyManager,
)
from .executors.sandbox_runtime import SandboxResourceContract
from .loop_benchmark import QFBenchSandboxEvaluator, hash_worker_directory
from .qfbench_baseline import audit_fixed_checkpoint_proxy_costs
from .verifiers.quantcodeeval_sandbox import IsolatedQuantCodeEvalVerifier


MODEL = "deepseek/deepseek-v4-flash-0731"
CANONICAL_MODEL = "deepseek/deepseek-v4-flash-20260731"
PROVIDER = "deepseek"
GENERATION_ENDPOINT = "https://openrouter.ai/api/v1/generation"
CHECKPOINT = "quantcodeeval-h0-shell-only"
SPLIT = "engineering_canary_optimize"


class QuantCodeEvalBaselineError(RuntimeError):
    """The baseline identity, runtime, or evidence is incomplete."""


def _canonical_sha256(payload: object) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _runtime_source_identity() -> dict[str, str]:
    root = Path(__file__).resolve().parent
    relative_paths = (
        "quantcodeeval_baseline.py",
        "executors/execution_record.py",
        "executors/sandbox_nexau.py",
        "verifiers/quantcodeeval.py",
        "verifiers/quantcodeeval_rpc.py",
        "verifiers/quantcodeeval_rpc_server.py",
        "verifiers/quantcodeeval_sandbox.py",
    )
    return {
        relative: hashlib.sha256((root / relative).read_bytes()).hexdigest()
        for relative in relative_paths
    }


def _atomic_private_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(payload, output, sort_keys=True, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        path.chmod(0o600)
    except BaseException:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise


def _read_config(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise QuantCodeEvalBaselineError(f"invalid runtime config: {exc}") from exc
    if not isinstance(payload, dict):
        raise QuantCodeEvalBaselineError("runtime config must be a JSON object")
    if payload.get("allowed_model") != MODEL:
        raise QuantCodeEvalBaselineError("runtime config has the wrong model")
    if str(payload.get("required_provider", "")).casefold() != PROVIDER:
        raise QuantCodeEvalBaselineError("runtime config must require DeepSeek")
    if payload.get("allowed_path_prefix") != "/v1":
        raise QuantCodeEvalBaselineError("runtime config must restrict /v1")
    if payload.get("worker_concurrency") != 1:
        raise QuantCodeEvalBaselineError("H0 requires worker concurrency 1")
    return payload


def _resource(
    raw: Mapping[str, object],
    *,
    default_cpu: int | None = None,
    default_memory: int | None = None,
) -> SandboxResourceContract:
    tmpfs = raw.get("writable_tmpfs_mb")
    if not isinstance(tmpfs, Mapping):
        raise QuantCodeEvalBaselineError("resource contract has no tmpfs map")
    return SandboxResourceContract(
        cpu_count=int(raw.get("cpu_count", default_cpu)),
        memory_mb=int(raw.get("memory_mb", default_memory)),
        pids_limit=int(raw["pids_limit"]),
        timeout_seconds=int(raw["timeout_seconds"]),
        writable_tmpfs_mb={str(key): int(value) for key, value in tmpfs.items()},
    )


class QuantCodeEvalWorkerRouter:
    """Open one model proxy and one exact-output NexAU worker per attempt."""

    def __init__(
        self,
        *,
        backend: RootlessDockerBackend,
        proxy_manager: SandboxProxyManager,
        lifecycle_root: Path,
        public_task_root: Path,
        worker_image_ref: str,
        worker_resources: SandboxResourceContract,
    ) -> None:
        self.backend = backend
        self.proxy_manager = proxy_manager
        self.lifecycle_root = lifecycle_root
        self.public_task_root = public_task_root
        self.worker_image_ref = worker_image_ref
        self.worker_resources = worker_resources

    def execute(
        self,
        *,
        attempt: TaskAttempt,
        task,
        worker_dir: str | Path,
        run_dir: str | Path,
        model_env: Mapping[str, str] | None = None,
    ) -> WorkerExecution:
        run_root = Path(run_dir).resolve()
        with self.proxy_manager.open(
            run_id=attempt.run_id,
            attempt_id=attempt.attempt_id,
            task_id=task.task_id,
            caller_role="worker",
            run_dir=run_root,
        ) as session:
            if (
                session.allowed_model != MODEL
                or session.required_provider != PROVIDER
                or session.immutable_image_ref
                != self.proxy_manager.config.image_ref
                or session.network_scope != attempt.attempt_id
            ):
                raise QuantCodeEvalBaselineError(
                    "proxy session differs from the H0 identity"
                )
            executor = SandboxNexAUExecutor(
                backend=self.backend,
                lifecycle_root=self.lifecycle_root,
                worker_image_ref=self.worker_image_ref,
                public_task_root=self.public_task_root,
                resource_contract=self.worker_resources,
                worker_network_name=session.network_name,
                network_scope=session.network_scope,
                proxy_base_url=session.base_url,
                model_name=MODEL,
                max_output_files=20,
                max_output_bytes=32 * 1024 * 1024,
                expected_output_paths=("strategy.py",),
                auxiliary_output_paths=(
                    "trade_log.json",
                    "output/metrics.json",
                    "__pycache__/strategy.cpython-311.pyc",
                ),
                retain_additional_outputs=True,
            )
            return executor.execute(
                attempt=attempt,
                task=task,
                worker_dir=worker_dir,
                run_dir=run_root,
                model_env=model_env,
            )


def _generation_metadata(generation_id: str, token: str) -> dict[str, object]:
    url = GENERATION_ENDPOINT + "?" + urllib.parse.urlencode({"id": generation_id})
    request = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        method="GET",
    )
    last_error = "not attempted"
    for delay in (0, 2, 4, 8, 12):
        if delay:
            time.sleep(delay)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read())
            data = payload.get("data")
            if not isinstance(data, dict):
                raise QuantCodeEvalBaselineError(
                    "generation metadata response lacks data"
                )
            provider = data.get("provider_name")
            resolved_model = data.get("model")
            if not isinstance(provider, str) or provider.casefold() != PROVIDER:
                raise QuantCodeEvalBaselineError(
                    f"generation used unexpected provider {provider!r}"
                )
            if resolved_model not in {MODEL, CANONICAL_MODEL}:
                raise QuantCodeEvalBaselineError(
                    f"generation used unexpected model {resolved_model!r}"
                )
            return {
                "generation_id": generation_id,
                "provider_name": provider,
                "resolved_model": resolved_model,
                "total_cost": data.get("total_cost"),
                "tokens_prompt": data.get("tokens_prompt"),
                "tokens_completion": data.get("tokens_completion"),
            }
        except urllib.error.HTTPError as exc:
            last_error = f"HTTP {exc.code}"
            if exc.code not in {404, 425, 429}:
                raise QuantCodeEvalBaselineError(last_error) from exc
        except urllib.error.URLError as exc:
            last_error = str(exc.reason)
    raise QuantCodeEvalBaselineError(
        f"generation metadata did not become available: {last_error}"
    )


def _route_evidence(run_dir: Path, token_file: Path) -> dict[str, object]:
    records: list[dict[str, object]] = []
    generation_ids: list[str] = []
    for audit in sorted((run_dir / "attempts").glob("*/proxy-audit.jsonl")):
        for line in audit.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if (
                row.get("model") != MODEL
                or row.get("request_state") != "completed"
                or row.get("upstream_status_code") != 200
                or row.get("failure_class") is not None
            ):
                raise QuantCodeEvalBaselineError(
                    f"failed or ambiguous model request in {audit}"
                )
            generation_id = row.get("provider_request_id")
            if not isinstance(generation_id, str) or not generation_id:
                raise QuantCodeEvalBaselineError("model request has no generation ID")
            generation_ids.append(generation_id)
            records.append(
                {
                    key: row.get(key)
                    for key in (
                        "request_identity_sha256",
                        "provider_request_id",
                        "model",
                        "input_tokens",
                        "output_tokens",
                        "total_tokens",
                        "provider_cost_usd",
                        "latency_ms",
                    )
                }
            )
    if not generation_ids or len(generation_ids) != len(set(generation_ids)):
        raise QuantCodeEvalBaselineError("generation IDs are empty or duplicated")
    token = token_file.read_text(encoding="utf-8").strip()
    if not token:
        raise QuantCodeEvalBaselineError("model token is empty")
    try:
        resolved = [_generation_metadata(item, token) for item in generation_ids]
    finally:
        token = ""
    return {
        "requested_model": MODEL,
        "required_provider": PROVIDER,
        "allow_fallbacks": False,
        "requests": records,
        "generation_metadata": resolved,
    }


def _snapshot_worker(source: Path, target: Path) -> str:
    expected = hash_worker_directory(source)
    if target.exists():
        if not target.is_dir() or hash_worker_directory(target) != expected:
            raise QuantCodeEvalBaselineError("persisted H0 worker differs")
        return expected
    shutil.copytree(source, target)
    if hash_worker_directory(target) != expected:
        raise QuantCodeEvalBaselineError("H0 worker changed while snapshotting")
    return expected


def prepare_quantcodeeval_h0(
    *,
    config_path: str | Path,
    public_root: str | Path,
    trusted_root: str | Path,
    run_dir: str | Path,
    worker_dir: str | Path,
    worker_image_ref: str,
    verifier_image_ref: str,
    proxy_image_ref: str,
    task_panel_path: str | Path | None = None,
    task_ids: tuple[str, ...] | None = None,
) -> tuple[
    QuantCodeEvalSnapshot,
    QFBenchSandboxEvaluator,
    dict[str, object],
    Path,
]:
    config_file = Path(config_path).resolve()
    config = _read_config(config_file)
    public = Path(public_root).resolve()
    trusted = Path(trusted_root).resolve()
    run_root = Path(run_dir).resolve()
    run_root.mkdir(parents=True, exist_ok=True)
    snapshot = load_quantcodeeval_snapshot(
        public,
        task_panel_path=task_panel_path,
    )
    if task_ids is not None:
        available = {task.task_id: task for task in snapshot.optimize.tasks}
        if (
            not task_ids
            or len(set(task_ids)) != len(task_ids)
            or any(task_id not in available for task_id in task_ids)
        ):
            raise QuantCodeEvalBaselineError(
                "requested tasks must be a unique non-empty optimize subset"
            )
        snapshot = QuantCodeEvalSnapshot(
            root=snapshot.root,
            repository_url=snapshot.repository_url,
            commit=snapshot.commit,
            optimize=QuantCodeEvalSplit(
                "optimize",
                tuple(available[task_id] for task_id in task_ids),
            ),
            held_out=snapshot.held_out,
        )
    public_role = verify_quantcodeeval_role_root(public, "public")
    trusted_role = verify_quantcodeeval_role_root(trusted, "trusted-verifier")
    if public_role.commit != trusted_role.commit:
        raise QuantCodeEvalBaselineError("public and trusted commits differ")

    backend = RootlessDockerBackend(
        docker_host=str(config["docker_host"]),
        expected_uid=int(config["expected_uid"]),
    )
    preflight = backend.preflight(
        expected_server_version="29.4.1",
        expected_security_options=(
            "name=seccomp,profile=builtin",
            "name=rootless",
            "name=cgroupns",
        ),
        image_ids=(worker_image_ref, verifier_image_ref, proxy_image_ref),
    )
    worker_limits = config.get("worker_limits")
    proxy_limits = config.get("proxy_resources")
    if not isinstance(worker_limits, Mapping) or not isinstance(proxy_limits, Mapping):
        raise QuantCodeEvalBaselineError("runtime resource limits are missing")
    worker_resources = _resource(
        worker_limits, default_cpu=2, default_memory=4096
    )
    proxy_resources = _resource(proxy_limits)
    verifier_resources = SandboxResourceContract(
        cpu_count=2,
        memory_mb=4096,
        pids_limit=256,
        timeout_seconds=3600,
        writable_tmpfs_mb={
            "/tmp": 256,
            "/qea": 512,
            "/app": 1024,
            "/tests": 128,
            "/logs": 64,
            "/opt/qea/uv-cache": 256,
            "/opt/qea/uv-tools": 64,
        },
    )
    token_file = Path(str(config["token_file"])).resolve()
    proxy_config = SandboxProxyConfig(
        image_ref=proxy_image_ref,
        resource_contract=proxy_resources,
        token_file=token_file,
        upstream_base_url=str(config["upstream_base_url"]),
        allowed_path_prefix="/v1",
        allowed_model=MODEL,
        required_provider=PROVIDER,
        timeout_seconds=120,
        finalize_timeout_seconds=360,
        expect_request=True,
    )
    proxy_manager = SandboxProxyManager(backend=backend, config=proxy_config)
    lifecycle_root = run_root / "lifecycles"
    executor = QuantCodeEvalWorkerRouter(
        backend=backend,
        proxy_manager=proxy_manager,
        lifecycle_root=lifecycle_root,
        public_task_root=public,
        worker_image_ref=worker_image_ref,
        worker_resources=worker_resources,
    )
    verifier = IsolatedQuantCodeEvalVerifier(
        backend=backend,
        lifecycle_root=lifecycle_root,
        verifier_image_ref=verifier_image_ref,
        public_task_root=public,
        trusted_task_root=trusted,
        resource_contract=verifier_resources,
    )
    evaluator = QFBenchSandboxEvaluator(
        benchmark_commit=snapshot.commit,
        run_id=run_root.name,
        executor=executor,
        verifier=verifier,
        model_env={},
        worker_concurrency=1,
        verifier_concurrency=1,
    )
    frozen_worker = run_root / "workers" / "H0"
    worker_digest = _snapshot_worker(Path(worker_dir).resolve(), frozen_worker)
    identity_material = {
        "schema_version": 1,
        "protocol": "quantcodeeval-h0-shell-only-v1",
        "benchmark_commit": snapshot.commit,
        "task_ids": list(snapshot.optimize.task_ids),
        "public_manifest_sha256": public_role.manifest_sha256,
        "trusted_manifest_sha256": trusted_role.manifest_sha256,
        "worker_digest": worker_digest,
        "worker_image_ref": worker_image_ref,
        "verifier_image_ref": verifier_image_ref,
        "proxy_image_ref": proxy_image_ref,
        "rootless_preflight_identity_sha256": preflight.identity_sha256,
        "model": MODEL,
        "required_provider": PROVIDER,
        "allow_fallbacks": False,
        "worker_concurrency": 1,
        "verifier_concurrency": 1,
        "checkpoint": CHECKPOINT,
        "split": SPLIT,
        "output_contract": {
            "submitted_paths": ["strategy.py"],
            "retained_not_submitted_paths": [
                "trade_log.json",
                "output/metrics.json",
                "__pycache__/strategy.cpython-311.pyc",
            ],
            "max_files": 20,
            "max_total_bytes": 32 * 1024 * 1024,
            "retain_additional_outputs": True,
        },
        "coordinator_source_sha256": _runtime_source_identity(),
        "resample_policy": "H0 sampled once; later iterations reuse exact scores",
    }
    plan = {
        **identity_material,
        "runtime_identity_sha256": _canonical_sha256(identity_material),
        "model_request_count": 0,
        "status": "preflight_complete",
    }
    plan_path = run_root / "H0-PREFLIGHT.json"
    if plan_path.is_file():
        existing = json.loads(plan_path.read_text(encoding="utf-8"))
        if existing != plan:
            raise QuantCodeEvalBaselineError("persisted H0 preflight differs")
    else:
        _atomic_private_json(plan_path, plan)
    return snapshot, evaluator, plan, frozen_worker


def run_quantcodeeval_h0(
    *,
    snapshot: QuantCodeEvalSnapshot,
    evaluator: QFBenchSandboxEvaluator,
    plan: Mapping[str, object],
    frozen_worker: Path,
    run_dir: str | Path,
    token_file: str | Path,
) -> dict[str, object]:
    run_root = Path(run_dir).resolve()
    summary = evaluator.evaluate(
        worker_dir=frozen_worker,
        tasks=snapshot.optimize.tasks,
        split=SPLIT,
        checkpoint=CHECKPOINT,
        run_dir=run_root,
    )
    cost = audit_fixed_checkpoint_proxy_costs(
        run_root,
        expected_attempts=len(snapshot.optimize.tasks),
        checkpoint=CHECKPOINT,
        split=SPLIT,
    )
    route = _route_evidence(run_root, Path(token_file).resolve())
    attempts = []
    worker_digest = str(plan["worker_digest"])
    for task in snapshot.optimize.tasks:
        attempt = TaskAttempt.create(
            run_id=run_root.name,
            benchmark_commit=snapshot.commit,
            task_id=task.task_id,
            split=SPLIT,
            checkpoint=CHECKPOINT,
            worker_digest=worker_digest,
        )
        answer_free = (
            run_root / "attempts" / attempt.attempt_id
            / "verifier" / "answer-free-evidence.json"
        )
        attempts.append(
            {
                "task_id": task.task_id,
                "attempt_id": attempt.attempt_id,
                "answer_free_evidence": (
                    json.loads(answer_free.read_text())
                    if answer_free.is_file()
                    else {
                        "schema_version": 1,
                        "task_id": task.task_id,
                        "evidence_status": "unavailable_before_verifier",
                    }
                ),
                "reused_by_evolution": True,
            }
        )
    result = {
        "schema_version": 1,
        "protocol": "quantcodeeval-h0-shell-only-v1",
        "status": "complete",
        "claim_boundary": (
            "two-task engineering baseline; not a formal benchmark estimate"
        ),
        "runtime_identity_sha256": plan["runtime_identity_sha256"],
        "evaluation_identity_sha256": _canonical_sha256(
            {
                "runtime_identity_sha256": plan["runtime_identity_sha256"],
                "attempt_ids": [row["attempt_id"] for row in attempts],
            }
        ),
        "resampled": True,
        "reuse_contract": {
            "future_iterations_resample_h0": False,
            "evidence_retention": "all five iteration records plus H0",
        },
        "score_summary": {
            "task_rewards": summary.task_rewards,
            "domain_scores": summary.domain_scores,
            "task_mean": summary.task_mean,
            "overall": summary.overall,
            "scores": [asdict(score) for score in summary.scores],
        },
        "attempts": attempts,
        "route_evidence": route,
        "cost_audit": cost,
    }
    result_path = run_root / "H0-RESULT.json"
    if result_path.is_file():
        existing = json.loads(result_path.read_text(encoding="utf-8"))
        if existing != result:
            raise QuantCodeEvalBaselineError("persisted H0 result differs")
    else:
        _atomic_private_json(result_path, result)
    return result
