#!/usr/bin/env python3
"""Run the no-model import or one-task paid Rich full-harness E2B canary."""

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

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import run as run_cli
from qea.candidate_admission import AdmissionPolicy, admit_candidate
from qea.e2b_lease import E2BLeasePool
from qea.e2b_reaper import reap_e2b_sandboxes
from qea.evaluation import TaskAttempt
from qea.executors.e2b_evolver import E2BEvolverConfig, E2BFullHarnessProposer
from qea.executors.e2b_nexau import (
    E2BNexAUConfig,
    E2BNexAUExecutor,
    E2BQFBenchVerifier,
    _command_payload,
    _read_optional_text,
    _run_checked,
    _write_json,
    _write_sandbox_file,
)
from qea.executors.e2b_protocol import E2BSandboxFactory, SDKSandboxFactory
from qea.evolution_feedback import PublicTaskRubric, load_feedback_manifest
from qea.evolve_runtime import snapshot_dir
from qea.loop_benchmark import hash_worker_directory
from qea.qfbench_images import NEXAU_REQUIREMENTS_LOCK, NEXAU_RUNTIME_PYTHON


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
    def kill(sandbox_id: str) -> bool:
        from e2b import Sandbox

        return bool(Sandbox.kill(sandbox_id))

    report = reap_e2b_sandboxes(run_dir, kill_sandbox=kill, apply=True)
    return asdict(report)


def run_paid_rich_canary(args, *, snapshot, task, run_dir: Path) -> dict:
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
    snapshot_dir(Path("qea/worker_gdpval_weak").resolve(), candidate)
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("import", "paid-rich"), required=True)
    parser.add_argument("--qfbench-root", type=Path, required=True)
    parser.add_argument(
        "--manifest", type=Path, default=Path("data/qfbench/MANIFEST_30.json")
    )
    parser.add_argument("--template-manifest-dir", type=Path, required=True)
    parser.add_argument("--evolver-template-manifest", type=Path)
    parser.add_argument(
        "--feedback-manifest",
        type=Path,
        default=Path("data/qfbench/FEEDBACK_30.json"),
    )
    parser.add_argument("--task", default="historical-var-data-prep")
    parser.add_argument("--run-id")
    parser.add_argument(
        "--results-dir", type=Path, default=Path("results/qfbench-full-harness-canary")
    )
    parser.add_argument("--global-e2b-cap", type=int, default=12)
    parser.add_argument("--approve-paid-e2b", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_cli._load_dotenv()
    from qea.benchmarks.qfbench import load_qfbench_snapshot

    snapshot = load_qfbench_snapshot(args.qfbench_root, manifest_path=args.manifest)
    task = snapshot.task(args.task)
    if args.mode == "paid-rich" and task.task_id not in snapshot.optimize.task_ids:
        raise ValueError("paid-rich canary task must be in the optimize split")
    if args.mode == "paid-rich" and args.evolver_template_manifest is None:
        raise ValueError("--evolver-template-manifest is required for paid-rich")
    approved = args.approve_paid_e2b or os.environ.get(
        "QEA_PAID_EVAL_AUTO_APPROVE"
    ) == "1"
    if not approved:
        print("NOT STARTED: pass --approve-paid-e2b or set standing auto-approval")
        return 2
    args.run_id = args.run_id or (
        "qfbench-full-harness-canary-"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )
    run_dir = args.results_dir.resolve() / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    status = None
    try:
        if args.mode == "import":
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
        reaper = _exact_reap(run_dir)
        _write_json(run_dir / "run_status.json", {
            "mode": args.mode,
            "run_id": args.run_id,
            "status": status,
            "exact_id_reaper": reaper,
        })
        print(run_dir)


if __name__ == "__main__":
    raise SystemExit(main())
