#!/usr/bin/env python3
"""Run import, paid Rich, or paid baseline full-harness canaries."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import run as run_cli
from qea.evaluation import TaskAttempt
from qea.executors.sandbox_runtime import atomic_json as _write_json
from qea.loop_benchmark import hash_worker_directory
from qea.qfbench_baseline import audit_fixed_checkpoint_proxy_costs
from qea.qfbench_epoch_report import audit_paid_baseline_lifecycles
from qea.qfbench_images import NEXAU_REQUIREMENTS_LOCK, NEXAU_RUNTIME_PYTHON

if TYPE_CHECKING:
    from qea.evolution_feedback import PublicTaskRubric


PAID_BASELINE_BATCH_TASK_IDS = (
    "ohlc-realized-vol-estimators",
    "momentum-backtest",
    "evt-pot-var",
    "geometric-mean-reverting-jd",
    "option-put-call-parity-forward-audit",
    "sma-crossover-spy",
    "corporate-action-adjustment",
    "earnings-surprise-calculator",
    "fama-french-factor-model-new",
    "credit-migration-matrix",
    "zero-coupon-bootstrapping",
    "copula-sampling-rank-correlation",
)
_PAID_BASELINE_CHECKPOINT = "epoch-02-concurrency-canary"


def _snapshot_worker(source: Path, destination: Path) -> None:
    """Copy one worker snapshot without importing the evolution stack."""

    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


_IMPORT_AGENT = """\
type: agent
name: qea_import_canary
max_context_tokens: 200000
system_prompt: ./systemprompt.md
system_prompt_type: jinja
tool_call_mode: openai
max_iterations: 1
llm_config:
  model: ${env.LLM_MODEL}
  base_url: ${env.LLM_BASE_URL}
  api_key: ${env.LLM_API_KEY}
  max_tokens: 8
  temperature: 0
  stream: false
  api_type: openai_chat_completion
  timeout: 10
tools:
  - name: echo
    yaml_path: ./tool_descriptions/echo.tool.yaml
    binding: tools.fixture:echo
tracers:
  - import: nexau.archs.tracer.adapters.in_memory:InMemoryTracer
"""
_IMPORT_DESCRIPTION = """\
type: tool
name: echo
description: Return one value for import verification.
input_schema:
  type: object
  properties:
    value: {type: string}
  required: [value]
  additionalProperties: false
"""
_IMPORT_RUNNER = """\
import argparse
import os
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--worker-dir", type=Path, required=True)
args = parser.parse_args()
root = args.worker_dir.resolve()
sys.path.insert(0, str(root))
os.environ["LLM_MODEL"] = "import-only"
os.environ["LLM_BASE_URL"] = "https://invalid.local/v1"
os.environ["LLM_API_KEY"] = "not-a-real-key"
from nexau import AgentConfig
config = AgentConfig.from_yaml(config_path=root / "agent.yaml")
from tools.fixture import echo
assert echo("ok") == {"value": "ok"}
assert len(config.tools) == 1
print("IMPORT_OK")
"""


def build_synthetic_rich_evidence(
    *,
    task,
    rubric: PublicTaskRubric,
    destination: str | Path,
) -> Path:
    """Create public-only evidence for the one-task paid evolver canary."""

    root = Path(destination).resolve()
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    task_root = Path(task.root).resolve()
    public_root = root / "tasks" / task.task_id
    for source_value in task.worker_files:
        source = Path(source_value)
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"unsafe public canary file: {source}")
        relative = source.resolve().relative_to(task_root)
        if any(part in {"tests", "solution"} for part in relative.parts):
            raise ValueError(f"private file crossed canary firewall: {relative}")
        target = public_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    _write_json(root / "contract.json", {
        "schema_version": 1,
        "mode": "rich",
        "synthetic_canary": True,
        "optimize_task_ids": [task.task_id],
        "held_out_feedback": False,
    })
    _write_json(public_root / "public_rubric.json", {
        "schema_version": 1,
        "task_id": task.task_id,
        "provenance": "public_task",
        "criteria": [asdict(item) for item in rubric.criteria],
    })
    _write_json(root / "history" / "iterations.json", [])
    (root / "access_log.jsonl").write_text("")
    return root


def run_import_canary(
    *,
    template_id: str,
    run_id: str,
    run_dir: str | Path,
    sandbox_factory: E2BSandboxFactory | None = None,
    lease_pool: E2BLeasePool,
) -> dict:
    """Load a local tool binding in the pinned template without calling a model."""

    from qea.executors.e2b_nexau import (
        _command_payload,
        _read_optional_text,
        _run_checked,
        _write_sandbox_file,
    )
    from qea.executors.e2b_protocol import SDKSandboxFactory

    root = Path(run_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    factory = sandbox_factory or SDKSandboxFactory()
    lifecycle_path = root / "worker-import-sandbox-lifecycle.json"
    command_path = root / "import-command.json"
    sandbox = None
    sandbox_id = ""
    cleaned_up = False
    with lease_pool.acquire(
        f"import-canary:{run_id}", timeout_seconds=120
    ) as lease:
        try:
            sandbox = factory.create(
                template=template_id,
                timeout=300,
                metadata={
                    "qea_role": "worker-import-canary",
                    "qea_run_id": run_id,
                },
                envs={},
                secure=True,
                allow_internet_access=False,
            )
            sandbox_id = str(sandbox.sandbox_id)
            _write_json(lifecycle_path, {
                "schema_version": 1,
                "run_id": run_id,
                "role": "worker-import-canary",
                "sandbox_id": sandbox_id,
                "cleaned_up": False,
            })
            dependency_lock = _read_optional_text(
                sandbox, NEXAU_REQUIREMENTS_LOCK
            )
            if dependency_lock is None or not dependency_lock.strip():
                raise RuntimeError("worker template NexAU dependency lock is missing")
            lease.heartbeat()
            _run_checked(
                sandbox,
                "mkdir -p /qea/import-worker/tools /qea/import-worker/tool_descriptions",
                label="import canary setup",
                timeout=60,
            )
            files = {
                "/qea/import-worker/agent.yaml": _IMPORT_AGENT,
                "/qea/import-worker/systemprompt.md": "Import-only canary.\n",
                "/qea/import-worker/tools/__init__.py": "",
                "/qea/import-worker/tools/fixture.py": (
                    "def echo(value):\n    return {'value': value}\n"
                ),
                "/qea/import-worker/tool_descriptions/echo.tool.yaml": (
                    _IMPORT_DESCRIPTION
                ),
                "/qea/import_canary.py": _IMPORT_RUNNER,
            }
            for path, payload in files.items():
                _write_sandbox_file(sandbox, path, payload)
            result = sandbox.commands.run(
                f"{NEXAU_RUNTIME_PYTHON} /qea/import_canary.py "
                "--worker-dir /qea/import-worker",
                timeout=120,
                envs={},
            )
            _write_json(command_path, _command_payload(result, {}))
            if int(getattr(result, "exit_code", -1)) != 0 or "IMPORT_OK" not in str(
                getattr(result, "stdout", "")
            ):
                raise RuntimeError("local-tool import canary failed")
        finally:
            if sandbox is not None:
                try:
                    sandbox.kill()
                    cleaned_up = True
                except Exception:  # noqa: BLE001
                    cleaned_up = False
            if sandbox_id:
                _write_json(lifecycle_path, {
                    "schema_version": 1,
                    "run_id": run_id,
                    "role": "worker-import-canary",
                    "sandbox_id": sandbox_id,
                    "cleaned_up": cleaned_up,
                })
    output = {
        "run_id": run_id,
        "sandbox_id": sandbox_id,
        "import_ok": True,
        "model_calls": 0,
        "network_enabled": False,
        "cleaned_up": cleaned_up,
    }
    _write_json(root / "result.json", output)
    return output


def run_rootless_import_canary(
    *,
    runtime,
    task,
    run_id: str,
    run_dir: str | Path,
) -> dict:
    """Load NexAU and a local tool in one network-isolated rootless worker."""

    from qea.sandbox_backend import SandboxSpec
    from qea.sandbox_lifecycle import (
        create_lifecycle,
        mark_cleaned,
        mark_finished,
        mark_started,
    )

    root = Path(run_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    try:
        task_runtime = runtime.evaluator.executor.catalog.tasks[task.task_id]
    except (AttributeError, KeyError, TypeError) as exc:
        raise ValueError("rootless runtime has no selected worker for the task") from exc
    resources = task_runtime.worker_resources
    identity_seed = (
        f"{run_id}:{task.task_id}:{task_runtime.worker_image_ref}:"
        f"{hashlib.sha256(_IMPORT_RUNNER.encode()).hexdigest()}"
    )
    import_digest = hashlib.sha256(identity_seed.encode()).hexdigest()
    attempt_id = "import-" + import_digest[:24]
    spec = SandboxSpec(
        role="worker",
        run_id=run_id,
        attempt_id=attempt_id,
        task_id=task.task_id,
        image_ref=task_runtime.worker_image_ref,
        cpu_count=resources.cpu_count,
        memory_mb=resources.memory_mb,
        pids_limit=resources.pids_limit,
        timeout_seconds=resources.timeout_seconds,
        network_policy="worker-proxy-only",
        environment={},
        writable_tmpfs_mb=resources.writable_tmpfs_mb,
        network_scope=attempt_id,
    )
    attempt_identity = hashlib.sha256(
        f"{spec.spec_sha256}:{import_digest}".encode()
    ).hexdigest()
    backend = runtime.backend
    lifecycle_path = root / "worker-import-sandbox-lifecycle-v2.json"
    network = None
    handle = None
    primary_error: BaseException | None = None
    cleanup_result = None
    try:
        network = backend.create_internal_network(
            run_id,
            network_scope=attempt_id,
        )
        handle = backend.create(spec)
        create_lifecycle(
            lifecycle_path,
            handle=handle,
            spec=spec,
            attempt_identity_sha256=attempt_identity,
        )
        backend.start(handle)
        mark_started(lifecycle_path)
        setup = backend.run(
            handle,
            ("mkdir", "-p", "/qea/import-worker/tools", "/qea/import-worker/tool_descriptions"),
            environment={},
            timeout_seconds=min(60, resources.timeout_seconds),
        )
        if setup.timed_out or setup.exit_code != 0:
            raise RuntimeError("rootless import setup failed")
        files = {
            "/qea/import-worker/agent.yaml": _IMPORT_AGENT,
            "/qea/import-worker/systemprompt.md": "Import-only canary.\n",
            "/qea/import-worker/tools/__init__.py": "",
            "/qea/import-worker/tools/fixture.py": (
                "def echo(value):\n    return {'value': value}\n"
            ),
            "/qea/import-worker/tool_descriptions/echo.tool.yaml": _IMPORT_DESCRIPTION,
            "/qea/import_canary.py": _IMPORT_RUNNER,
        }
        for path, payload in files.items():
            backend.put_bytes(handle, path, payload.encode())
        command = backend.run(
            handle,
            (
                NEXAU_RUNTIME_PYTHON,
                "/qea/import_canary.py",
                "--worker-dir",
                "/qea/import-worker",
            ),
            environment={},
            timeout_seconds=min(120, resources.timeout_seconds),
        )
        if (
            command.timed_out
            or command.exit_code != 0
            or "IMPORT_OK" not in command.stdout
        ):
            raise RuntimeError("rootless NexAU/local-tool import failed")
        mark_finished(lifecycle_path)
    except BaseException as exc:  # noqa: BLE001 - preserve exact cleanup on interruption.
        primary_error = exc
        if lifecycle_path.is_file():
            mark_finished(lifecycle_path, failure=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        cleanup_error = None
        if handle is not None:
            try:
                cleanup_result = backend.kill(handle.native_id).outcome
                mark_cleaned(
                    lifecycle_path,
                    cleanup_method="exact-id",
                    cleanup_result=cleanup_result,
                )
            except BaseException as exc:  # noqa: BLE001
                cleanup_error = exc
        if network is not None:
            try:
                backend.remove_internal_network(network)
            except BaseException as exc:  # noqa: BLE001
                if cleanup_error is None:
                    cleanup_error = exc
        if primary_error is None and cleanup_error is not None:
            raise cleanup_error

    pending = backend.list(
        {"qea.managed": "true", "qea.run-id": run_id}
    )
    if pending:
        raise RuntimeError("rootless import canary left managed containers")
    output = {
        "run_id": run_id,
        "task_id": task.task_id,
        "sandbox_id": handle.native_id,
        "network_id": network.native_id,
        "import_ok": True,
        "model_calls": 0,
        "network_enabled": False,
        "cleaned_up": cleanup_result in {"killed", "already_absent"},
    }
    _write_json(root / "result.json", output)
    return output


def _model_env() -> dict[str, str]:
    key = os.environ.get("LLM_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise ValueError("LLM_API_KEY or OPENROUTER_API_KEY is required")
    return {
        "LLM_API_KEY": key,
        "LLM_BASE_URL": os.environ.get(
            "LLM_BASE_URL",
            os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        ),
        "LLM_MODEL": os.environ.get("LLM_MODEL", "deepseek/deepseek-v4-pro"),
    }


def _exact_reap(run_dir: Path) -> dict:
    from qea.e2b_reaper import reap_e2b_sandboxes

    def kill(sandbox_id: str) -> bool:
        from e2b import Sandbox

        return bool(Sandbox.kill(sandbox_id))

    report = reap_e2b_sandboxes(run_dir, kill_sandbox=kill, apply=True)
    return asdict(report)


def _exact_rootless_reap(run_dir: Path, config_path: Path) -> dict:
    from qea.backends.rootless_docker import RootlessDockerBackend
    from qea.rootless_full_harness import load_rootless_full_harness_config
    from qea.sandbox_reaper import reap_sandbox_networks, reap_sandboxes

    config = load_rootless_full_harness_config(config_path)
    backend = RootlessDockerBackend(
        docker_host=config.docker_host,
        expected_uid=config.expected_uid,
    )
    applied = reap_sandboxes(run_dir, backend=backend, apply=True)
    final = reap_sandboxes(run_dir, backend=backend)
    applied_networks = reap_sandbox_networks(
        run_dir, backend=backend, apply=True
    )
    final_networks = reap_sandbox_networks(run_dir, backend=backend)
    inventory = backend.list(
        {"qea.managed": "true", "qea.run-id": run_dir.name}
    )
    if (
        final.pending_ids
        or final.identity_mismatch_ids
        or final.failed
        or final_networks.pending_ids
        or final_networks.failed
        or inventory
    ):
        raise RuntimeError("rootless exact-ID cleanup left managed resources")
    return {
        **asdict(applied),
        "backend": backend.backend_name,
        "final_pending_ids": list(final.pending_ids),
        "final_inventory_ids": [state.native_id for state in inventory],
        "network_reaper": asdict(applied_networks),
        "final_pending_network_ids": list(final_networks.pending_ids),
    }


def select_paid_baseline_batch_tasks(snapshot, *, config, executor: str):
    """Validate the exact standard-task epoch-2 panel before any paid work."""

    if executor != "rootless-docker":
        raise ValueError("paid-baseline-batch requires rootless-docker")
    if len(PAID_BASELINE_BATCH_TASK_IDS) != len(
        set(PAID_BASELINE_BATCH_TASK_IDS)
    ):
        raise ValueError("paid baseline batch task panel contains duplicates")
    if (
        getattr(config, "scheduler_epoch", None)
        != "repetitions-02-through-05"
        or getattr(config, "worker_concurrency", None) != 12
        or getattr(config, "verifier_concurrency", None) != 3
    ):
        raise ValueError("paid baseline batch requires schema-3 epoch-2 12/3 config")
    if (
        getattr(config, "allowed_model", None)
        != "deepseek/deepseek-v4-flash"
        or getattr(config, "required_provider", None) != "deepseek"
    ):
        raise ValueError(
            "paid baseline batch requires DeepSeek V4 Flash official provider"
        )
    try:
        primary_tasks = tuple(snapshot.primary.tasks)
    except AttributeError as exc:
        raise ValueError(
            "paid baseline batch requires the baseline primary panel"
        ) from exc
    by_id = {task.task_id: task for task in primary_tasks}
    missing = [
        task_id for task_id in PAID_BASELINE_BATCH_TASK_IDS if task_id not in by_id
    ]
    if missing:
        raise ValueError(f"paid baseline batch tasks are not primary: {missing}")
    selected = tuple(by_id[task_id] for task_id in PAID_BASELINE_BATCH_TASK_IDS)
    invalid = [
        task.task_id
        for task in selected
        if getattr(task, "cpus", None) != 2
        or getattr(task, "memory_mb", None) != 4096
    ]
    if invalid:
        raise ValueError(
            "paid baseline batch tasks must have a 2 CPU/4096 MiB worker "
            f"contract: {invalid}"
        )
    return selected


def audit_paid_provider_records(
    run_dir: str | Path,
    *,
    attempt_ids,
    allowed_model: str,
) -> dict:
    """Verify safe proxy metadata for the paid batch and summarize latency."""

    root = Path(run_dir).resolve()
    identifiers = tuple(attempt_ids)
    latencies: list[float] = []
    request_count = 0
    for attempt_id in identifiers:
        audit_path = root / "attempts" / attempt_id / "proxy-audit.jsonl"
        if audit_path.is_symlink() or not audit_path.is_file():
            raise RuntimeError(f"paid batch proxy audit is missing: {attempt_id}")
        identities: set[str] = set()
        for line in audit_path.read_text().splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict):
                raise RuntimeError("paid batch proxy audit record is invalid")
            if record.get("model") != allowed_model:
                raise RuntimeError("paid batch proxy route model differs")
            identity = record.get("request_identity_sha256")
            if not isinstance(identity, str) or len(identity) != 64:
                raise RuntimeError("paid batch request identity is invalid")
            if identity in identities:
                raise RuntimeError("paid batch contains a within-attempt replay")
            identities.add(identity)
            if (
                record.get("request_state") != "completed"
                or record.get("upstream_status_code") != 200
                or record.get("failure_class") is not None
            ):
                raise RuntimeError("paid batch has a failed or ambiguous request")
            latency = record.get("latency_ms")
            if (
                isinstance(latency, bool)
                or not isinstance(latency, (int, float))
                or latency < 0
            ):
                raise RuntimeError("paid batch provider latency is invalid")
            latencies.append(float(latency))
            request_count += 1
    if request_count < len(identifiers):
        raise RuntimeError("paid batch has fewer model requests than task attempts")
    ordered = sorted(latencies)
    p90_index = max(0, (9 * len(ordered) + 9) // 10 - 1)
    return {
        "request_count": request_count,
        "latency_ms": {
            "mean": sum(ordered) / len(ordered),
            "p90": ordered[p90_index],
        },
        "model": allowed_model,
    }


def run_paid_baseline_batch(
    *,
    runtime,
    config,
    snapshot,
    run_dir: str | Path,
    seed_worker: str | Path = Path("qea/worker_gdpval_weak"),
) -> dict:
    """Evaluate the immutable base worker once on the twelve-task canary."""

    root = Path(run_dir).resolve()
    selected = select_paid_baseline_batch_tasks(
        snapshot, config=config, executor="rootless-docker"
    )
    worker = root / "workers" / "seed"
    _snapshot_worker(Path(seed_worker).resolve(), worker)
    worker_digest = hash_worker_directory(worker)
    attempts = tuple(
        TaskAttempt.create(
            run_id=root.name,
            benchmark_commit=snapshot.commit,
            task_id=task.task_id,
            split="baseline_primary",
            checkpoint=_PAID_BASELINE_CHECKPOINT,
            worker_digest=worker_digest,
        )
        for task in selected
    )
    summary = runtime.evaluator.evaluate(
        worker_dir=worker,
        tasks=selected,
        split="baseline_primary",
        checkpoint=_PAID_BASELINE_CHECKPOINT,
        run_dir=root,
    )
    cost = audit_fixed_checkpoint_proxy_costs(
        root,
        expected_attempts=12,
        checkpoint=_PAID_BASELINE_CHECKPOINT,
        split="baseline_primary",
    )
    if not cost.get("cost_complete") or cost.get(
        "provider_cost_is_lower_bound"
    ):
        raise RuntimeError("paid baseline batch accounting is incomplete")
    attempt_ids = tuple(attempt.attempt_id for attempt in attempts)
    route = audit_paid_provider_records(
        root,
        attempt_ids=attempt_ids,
        allowed_model=config.allowed_model,
    )
    lifecycles = audit_paid_baseline_lifecycles(
        root, attempt_ids=attempt_ids
    )
    residual = runtime.backend.list(
        {"qea.managed": "true", "qea.run-id": root.name}
    )
    if residual:
        raise RuntimeError("paid baseline batch left managed resources")
    output = {
        "run_id": root.name,
        "executor": "rootless-docker",
        "mode": "paid-baseline-batch",
        "checkpoint": _PAID_BASELINE_CHECKPOINT,
        "task_ids": list(PAID_BASELINE_BATCH_TASK_IDS),
        "task_count": 12,
        "worker_concurrency": config.worker_concurrency,
        "verifier_concurrency": config.verifier_concurrency,
        "scheduler_epoch": config.scheduler_epoch,
        "worker_overlap": lifecycles["worker_overlap"],
        "official_task_mean": float(summary.task_mean),
        "official_overall": float(summary.overall),
        "timeout_count": sum(
            "timeout" in tuple(score.diagnostic_tags)
            for score in summary.scores
        ),
        "provider": config.required_provider,
        "model": config.allowed_model,
        "fallbacks_allowed": False,
        "provider_audit": route,
        "cost_audit": cost,
        "lifecycle_audit": lifecycles,
        "residual_resource_count": 0,
        "feedback_used": False,
        "evolver_used": False,
        "image_identity_digest": runtime.image_identity_digest,
        "scheduler_identity_digest": runtime.scheduler_identity_digest,
        "runtime_identity_digest": runtime.runtime_identity_digest,
    }
    _write_json(root / "paid-baseline-batch.json", output)
    return output


def run_paid_rich_canary(args, *, snapshot, task, run_dir: Path) -> dict:
    from qea.candidate_admission import AdmissionPolicy, admit_candidate
    from qea.e2b_lease import E2BLeasePool
    from qea.executors.e2b_evolver import E2BEvolverConfig, E2BFullHarnessProposer
    from qea.executors.e2b_nexau import (
        E2BNexAUConfig,
        E2BNexAUExecutor,
        E2BQFBenchVerifier,
    )
    from qea.evolution_feedback import load_feedback_manifest

    worker_templates, verifier_templates = run_cli.load_template_ids(
        args.template_manifest_dir,
        (task,),
        benchmark_commit=snapshot.commit,
    )
    evolver_template, _ = run_cli.load_evolver_template(
        args.evolver_template_manifest,
        benchmark_commit=snapshot.commit,
    )
    rubrics = load_feedback_manifest(args.feedback_manifest)
    if task.task_id not in rubrics:
        raise ValueError(f"feedback manifest has no rubric for {task.task_id}")
    evidence = build_synthetic_rich_evidence(
        task=task,
        rubric=rubrics[task.task_id],
        destination=run_dir / "evidence",
    )
    candidate = run_dir / "seed-candidate"
    _snapshot_worker(Path("qea/worker_gdpval_weak").resolve(), candidate)
    leases = E2BLeasePool(run_dir / ".e2b-leases", max_leases=args.global_e2b_cap)
    model_env = _model_env()
    proposer = E2BFullHarnessProposer(
        E2BEvolverConfig(template=evolver_template),
        lease_pool=leases,
    )
    proposal = proposer.propose(
        candidate_dir=candidate,
        evidence_dir=evidence,
        evolver_dir=Path("qea/evolve_agent_full").resolve(),
        diagnosis="Paid Rich canary: inspect public evidence and improve general validation.",
        iteration=1,
        run_id=args.run_id,
        run_dir=run_dir,
        model_env=model_env,
    )
    admission = admit_candidate(
        candidate,
        proposal.candidate_dir,
        AdmissionPolicy.qfbench_full(
            forbidden_content=sorted(snapshot.held_out.task_ids)
        ),
    )
    _write_json(run_dir / "admission.json", asdict(admission))
    config = E2BNexAUConfig(
        worker_templates=worker_templates,
        verifier_templates=verifier_templates,
        worker_allow_internet=True,
        verifier_allow_internet=False,
    )
    attempt = TaskAttempt.create(
        run_id=args.run_id,
        benchmark_commit=snapshot.commit,
        task_id=task.task_id,
        split="optimize",
        checkpoint="paid-rich-canary",
        worker_digest=hash_worker_directory(proposal.candidate_dir),
    )
    _write_json(
        run_dir / "attempts" / attempt.attempt_id / "attempt.json",
        asdict(attempt),
    )
    execution = E2BNexAUExecutor(config, lease_pool=leases).execute(
        attempt=attempt,
        task=task,
        worker_dir=proposal.candidate_dir,
        run_dir=run_dir,
        model_env=model_env,
    )
    score = E2BQFBenchVerifier(config, lease_pool=leases).verify(
        attempt=attempt,
        task=task,
        execution=execution,
        run_dir=run_dir,
    )
    _write_json(
        run_dir / "attempts" / attempt.attempt_id / "completed-score.json",
        asdict(score),
    )
    return {
        "run_id": args.run_id,
        "task_id": task.task_id,
        "proposal_candidate_digest": proposal.candidate_digest,
        "admitted": admission.admitted,
        "official_reward": score.reward,
        "diagnostic_tags": list(score.diagnostic_tags),
        "evolver_sandbox_id": proposal.sandbox_id,
        "worker_sandbox_id": execution.sandbox_id,
    }


def run_rootless_canary(args, *, snapshot, task, run_dir: Path) -> dict:
    """Assemble the production rootless runtime and run its selected smoke."""

    if args.mode == "paid-rich":
        if args.verifier_criteria_map is None:
            raise ValueError(
                "--verifier-criteria-map is required for rootless paid-rich"
            )
        production_args = [
            "--benchmark",
            "qfbench",
            "--executor",
            "rootless-docker",
            "--qfbench-root",
            str(args.qfbench_root),
            "--qfbench-manifest",
            str(args.manifest),
            "--rootless-config",
            str(args.rootless_config),
            "--rootless-image-set-manifest",
            str(args.rootless_image_set_manifest),
            "--feedback-mode",
            "rich",
            "--feedback-manifest",
            str(args.feedback_manifest),
            "--verifier-criteria-map",
            str(args.verifier_criteria_map),
            "--run-id",
            args.run_id,
            "--iters",
            "1",
            "--results-dir",
            str(args.results_dir),
            "--approve-external-run",
        ]
        exit_code = run_cli.main(production_args)
        if exit_code != 0:
            raise RuntimeError(
                f"rootless production runner exited with status {exit_code}"
            )
        return {
            "run_id": args.run_id,
            "executor": "rootless-docker",
            "mode": "paid-rich",
            "iterations": 1,
            "production_runner_exit_code": exit_code,
        }

    from qea.rootless_full_harness import (
        build_rootless_full_harness_runtime,
        load_rootless_full_harness_config,
    )

    config = load_rootless_full_harness_config(args.rootless_config)
    if args.mode == "paid-baseline-batch":
        select_paid_baseline_batch_tasks(
            snapshot, config=config, executor=args.executor
        )
    runtime = build_rootless_full_harness_runtime(
        config=config,
        image_set_manifest=args.rootless_image_set_manifest,
        benchmark_commit=snapshot.commit,
        tasks=snapshot.tasks,
        run_id=args.run_id,
        results_root=args.results_dir,
        include_evolver=args.mode != "paid-baseline-batch",
    )
    try:
        if args.mode == "paid-baseline-batch":
            return run_paid_baseline_batch(
                runtime=runtime,
                config=config,
                snapshot=snapshot,
                run_dir=run_dir,
            )
        result = run_rootless_import_canary(
            runtime=runtime,
            task=task,
            run_id=args.run_id,
            run_dir=run_dir,
        )
        return {
            **result,
            "image_identity_digest": runtime.image_identity_digest,
            "scheduler_identity_digest": runtime.scheduler_identity_digest,
            "runtime_identity_digest": runtime.runtime_identity_digest,
        }
    finally:
        runtime.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--executor",
        choices=("rootless-docker", "e2b"),
        default="rootless-docker",
    )
    parser.add_argument(
        "--mode",
        choices=("import", "paid-rich", "paid-baseline-batch"),
        required=True,
    )
    parser.add_argument("--qfbench-root", type=Path, required=True)
    parser.add_argument(
        "--manifest", type=Path, default=Path("data/qfbench/MANIFEST_30.json")
    )
    parser.add_argument("--rootless-config", type=Path)
    parser.add_argument("--rootless-image-set-manifest", type=Path)
    parser.add_argument("--template-manifest-dir", type=Path)
    parser.add_argument("--evolver-template-manifest", type=Path)
    parser.add_argument(
        "--feedback-manifest",
        type=Path,
        default=Path("data/qfbench/FEEDBACK_30.json"),
    )
    parser.add_argument("--verifier-criteria-map", type=Path)
    parser.add_argument("--task", default="historical-var-data-prep")
    parser.add_argument("--run-id")
    parser.add_argument(
        "--results-dir", type=Path, default=Path("results/qfbench-full-harness-canary")
    )
    parser.add_argument("--global-e2b-cap", type=int, default=12)
    parser.add_argument("--approve-external-run", action="store_true")
    parser.add_argument("--approve-paid-e2b", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.mode == "paid-baseline-batch" and args.executor != "rootless-docker":
        raise ValueError("paid-baseline-batch requires rootless-docker")
    if args.executor == "rootless-docker" and args.rootless_config is None:
        raise ValueError("--rootless-config is required for rootless-docker")
    if (
        args.executor == "rootless-docker"
        and args.rootless_image_set_manifest is None
    ):
        raise ValueError(
            "--rootless-image-set-manifest is required for rootless-docker"
        )
    if args.executor == "e2b":
        run_cli._load_dotenv()
    if args.mode == "paid-baseline-batch":
        from qea.benchmarks.qfbench import load_qfbench_baseline_snapshot

        snapshot = load_qfbench_baseline_snapshot(
            args.qfbench_root, manifest_path=args.manifest
        )
    else:
        from qea.benchmarks.qfbench import load_qfbench_snapshot

        snapshot = load_qfbench_snapshot(
            args.qfbench_root, manifest_path=args.manifest
        )
    task = snapshot.task(args.task)
    if args.mode == "paid-rich" and task.task_id not in snapshot.optimize.task_ids:
        raise ValueError("paid-rich canary task must be in the optimize split")
    if (
        args.executor == "e2b"
        and args.mode == "paid-rich"
        and args.evolver_template_manifest is None
    ):
        raise ValueError("--evolver-template-manifest is required for paid-rich")
    approved = (
        args.approve_external_run
        or (args.executor == "e2b" and args.approve_paid_e2b)
        or os.environ.get("QEA_PAID_EVAL_AUTO_APPROVE") == "1"
    )
    if args.mode in {"paid-rich", "paid-baseline-batch"} and not approved:
        print(
            "NOT STARTED: pass --approve-external-run or set standing "
            "auto-approval"
        )
        return 2
    args.run_id = args.run_id or (
        "qfbench-full-harness-canary-"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )
    run_dir = args.results_dir.resolve() / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    status = None
    try:
        if args.executor == "rootless-docker":
            status = run_rootless_canary(
                args, snapshot=snapshot, task=task, run_dir=run_dir
            )
        elif args.mode == "import":
            from qea.e2b_lease import E2BLeasePool

            if args.template_manifest_dir is None:
                raise ValueError("--template-manifest-dir is required for E2B")
            workers, _ = run_cli.load_template_ids(
                args.template_manifest_dir,
                (task,),
                benchmark_commit=snapshot.commit,
            )
            status = run_import_canary(
                template_id=workers[task.task_id],
                run_id=args.run_id,
                run_dir=run_dir,
                lease_pool=E2BLeasePool(
                    run_dir / ".e2b-leases", max_leases=args.global_e2b_cap
                ),
            )
        else:
            status = run_paid_rich_canary(
                args, snapshot=snapshot, task=task, run_dir=run_dir
            )
        return 0
    finally:
        reaper = (
            _exact_reap(run_dir)
            if args.executor == "e2b"
            else _exact_rootless_reap(run_dir, args.rootless_config)
        )
        _write_json(run_dir / "run_status.json", {
            "executor": args.executor,
            "mode": args.mode,
            "run_id": args.run_id,
            "status": status,
            "exact_id_reaper": reaper,
        })
        print(run_dir)


if __name__ == "__main__":
    raise SystemExit(main())
