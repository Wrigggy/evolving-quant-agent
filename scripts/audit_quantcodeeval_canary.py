#!/usr/bin/env python3
"""Run QuantCodeEval T16/T24 golden, failing, and oracle-isolation gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from dataclasses import asdict
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.backends.rootless_docker import RootlessDockerBackend
from qea.benchmarks.quantcodeeval import load_quantcodeeval_snapshot
from qea.evaluation import ArtifactRecord, TaskAttempt
from qea.executors.execution_record import WorkerExecution
from qea.executors.sandbox_runtime import SandboxResourceContract
from qea.verifiers.quantcodeeval_sandbox import IsolatedQuantCodeEvalVerifier


def _wrong_strategy(task_id: str) -> str:
    functions = (
        (
            "compute_realized_variance", "solve_normalization_constant",
            "compute_weight", "compute_managed_returns", "compute_alpha_appraisal",
            "main",
        )
        if task_id == "T16"
        else (
            "compute_demeaned_signal", "compute_regression_coefficient",
            "compute_portfolio_weight", "compute_strategy_returns",
        )
    )
    lines = [
        "import json",
        "from pathlib import Path",
        "probe = {",
        "    'tests_exists': Path('/tests').exists(),",
        "    'golden_exists': Path('/tests/golden_ref.py').exists(),",
        "    'expected_exists': any(Path('/tests').rglob('expected.json')) if Path('/tests').exists() else False,",
        "}",
        "Path('/candidate/qea-isolation-probe.json').write_text(json.dumps(probe))",
        "if probe['golden_exists']:",
        "    exec(Path('/tests/golden_ref.py').read_text(), globals())",
        "else:",
    ]
    for name in functions:
        lines.extend((f"    def {name}(*args, **kwargs):", "        return None"))
    return "\n".join(lines) + "\n"


def _execution(
    *,
    attempt: TaskAttempt,
    artifact_dir: Path,
    source: Path | None = None,
    generated: str | None = None,
) -> WorkerExecution:
    artifact_dir.mkdir(parents=True)
    target = artifact_dir / "strategy.py"
    if source is not None:
        shutil.copyfile(source, target)
    else:
        assert generated is not None
        target.write_text(generated)
    record = ArtifactRecord.from_file(target, root=artifact_dir)
    placeholder = artifact_dir.parent
    for name in ("trace.jsonl", "command.json", "final.txt"):
        (placeholder / name).write_text("\n")
    return WorkerExecution(
        attempt_id=attempt.attempt_id,
        artifact_dir=artifact_dir,
        artifacts=(record,),
        trace_uri=str(placeholder / "trace.jsonl"),
        log_uri=str(placeholder / "command.json"),
        final_text_uri=str(placeholder / "final.txt"),
        summary={"audit_fixture": True},
        sandbox_id="trusted-audit-fixture",
        cleaned_up=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("public_root", type=Path)
    parser.add_argument("trusted_root", type=Path)
    parser.add_argument("output_root", type=Path)
    parser.add_argument("--image", required=True)
    parser.add_argument("--docker-host", required=True)
    parser.add_argument("--expected-uid", required=True, type=int)
    args = parser.parse_args()
    output = args.output_root.resolve()
    if output.exists():
        raise SystemExit(f"refusing existing audit output {output}")
    output.mkdir(parents=True)
    snapshot = load_quantcodeeval_snapshot(args.public_root)
    backend = RootlessDockerBackend(
        docker_host=args.docker_host,
        expected_uid=args.expected_uid,
    )
    preflight = backend.preflight(
        expected_server_version="29.4.1",
        expected_security_options=(
            "name=seccomp,profile=builtin", "name=rootless", "name=cgroupns",
        ),
        image_ids=(args.image,),
    )
    resources = SandboxResourceContract(
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
    verifier = IsolatedQuantCodeEvalVerifier(
        backend=backend,
        lifecycle_root=output / "lifecycles",
        verifier_image_ref=args.image,
        public_task_root=args.public_root,
        trusted_task_root=args.trusted_root,
        resource_contract=resources,
    )
    rows = []
    for task in snapshot.optimize.tasks:
        for candidate_kind in ("golden", "oracle-probe-wrong"):
            candidate_payload = (
                (args.trusted_root / "tasks" / task.task_id / "tests" / "golden_ref.py").read_bytes()
                if candidate_kind == "golden"
                else _wrong_strategy(task.task_id).encode()
            )
            digest = hashlib.sha256(candidate_payload).hexdigest()
            attempt = TaskAttempt.create(
                run_id="qce-parity-20260812",
                benchmark_commit=snapshot.commit,
                task_id=task.task_id,
                split="audit",
                checkpoint=candidate_kind,
                worker_digest=digest,
            )
            artifact_dir = output / "fixtures" / attempt.attempt_id / "artifacts"
            execution = _execution(
                attempt=attempt,
                artifact_dir=artifact_dir,
                source=(
                    args.trusted_root / "tasks" / task.task_id / "tests" / "golden_ref.py"
                    if candidate_kind == "golden" else None
                ),
                generated=(
                    _wrong_strategy(task.task_id)
                    if candidate_kind != "golden" else None
                ),
            )
            score = verifier.verify(
                attempt=attempt,
                task=task,
                execution=execution,
                run_dir=output,
            )
            expected_reward = 1.0 if candidate_kind == "golden" else 0.0
            if score.reward != expected_reward:
                raise SystemExit(
                    f"{task.task_id} {candidate_kind}: expected {expected_reward}, got {score.reward}"
                )
            probe_path = (
                output / "attempts" / attempt.attempt_id / "verifier"
                / "strategy-isolation-probe.json"
            )
            probe = json.loads(probe_path.read_text()) if probe_path.is_file() else None
            if candidate_kind != "golden" and probe != {
                "tests_exists": False,
                "golden_exists": False,
                "expected_exists": False,
            }:
                raise SystemExit(f"unsafe strategy isolation probe: {probe}")
            rows.append({
                "task_id": task.task_id,
                "candidate_kind": candidate_kind,
                "attempt_id": attempt.attempt_id,
                "candidate_sha256": digest,
                "score": asdict(score),
                "isolation_probe": probe,
            })
    result = {
        "schema_version": 1,
        "protocol": "quantcodeeval-t16-t24-isolated-parity-v1",
        "benchmark_commit": snapshot.commit,
        "image_id": args.image,
        "rootless_preflight_identity_sha256": preflight.identity_sha256,
        "zero_model_requests": True,
        "gates": rows,
    }
    (output / "RESULT.json").write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n"
    )
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
