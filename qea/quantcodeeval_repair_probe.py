"""Paired, answer-free Worker repair probe for QuantCodeEval components."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Mapping

from .evaluation import TaskAttempt
from .loop_benchmark import hash_worker_directory
from .qfbench_baseline import audit_fixed_checkpoint_proxy_costs
from .quantcodeeval_baseline import (
    _atomic_private_json,
    prepare_quantcodeeval_h0,
)


PROBE_SPLIT = "engineering_repair_probe"
PROBE_CHECKPOINT = "quantcodeeval-paired-repair"


class QuantCodeEvalRepairProbeError(ValueError):
    """The paired repair probe cannot be reconstructed or compared."""


_PROBE_INSTRUCTION = """\
You are repairing an existing QuantCodeEval strategy implementation, not
starting from an empty solution.  The current implementation is pre-staged at
`/app/output/strategy.py`; a read-only backup is available at
`/app/data/probe_seed_strategy.py`, and the ordinary public task inputs are in
`/app/data`.

Preserve work that is already correct and reproduce the observed runtime
failure before changing it.  The
answer-free symptom is a matrix/row-shape mismatch in the estimator pipeline
after monthly-mean and daily-second-moment semantics were introduced.  Trace
the shape and indexing assumptions through the estimator and cross-validation
helpers, repair the underlying cause, and run focused smoke tests plus an
end-to-end public-data smoke.  Save the best runnable implementation at
`/app/output/strategy.py` even if some uncertainty remains.

Do not search for tests, checker code, expected values, reference solutions, or
credentials.  Do not replace a working quantitative definition merely to make
the program run.
"""


def materialize_probe_public_root(
    public_root: str | Path,
    destination: str | Path,
    *,
    task_id: str,
    seed_strategy: str | Path | None,
    worker_instruction: str | None = None,
) -> Path:
    """Create a public-only task overlay for a bounded Worker experiment."""

    source = Path(public_root).resolve() / "tasks" / task_id
    target_root = Path(destination).resolve()
    target = target_root / "tasks" / task_id
    seed = Path(seed_strategy).resolve() if seed_strategy is not None else None
    if target_root.exists():
        raise QuantCodeEvalRepairProbeError("probe public overlay already exists")
    if not source.is_dir() or (
        seed is not None and (not seed.is_file() or seed.is_symlink())
    ):
        raise QuantCodeEvalRepairProbeError("probe public inputs are missing")
    data_source = source / "environment" / "data"
    data_target = target / "environment" / "data"
    data_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(data_source, data_target)
    if seed is not None:
        shutil.copy2(seed, data_target / "probe_seed_strategy.py")
    instruction = worker_instruction if worker_instruction is not None else _PROBE_INSTRUCTION
    if not isinstance(instruction, str) or not instruction.strip():
        raise QuantCodeEvalRepairProbeError("probe Worker instruction is empty")
    (target / "instruction.md").write_text(instruction.strip() + "\n", encoding="utf-8")
    return target_root


def materialize_probe_worker(
    worker_dir: str | Path,
    destination: str | Path,
    *,
    max_iterations: int,
) -> Path:
    """Copy a harness and apply the same small test-time budget to both arms."""

    if isinstance(max_iterations, bool) or not 1 <= max_iterations <= 60:
        raise QuantCodeEvalRepairProbeError("max_iterations must be in [1, 60]")
    source = Path(worker_dir).resolve()
    target = Path(destination).resolve()
    if target.exists() or not source.is_dir():
        raise QuantCodeEvalRepairProbeError("invalid probe worker destination")
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    config = target / "agent.yaml"
    text = config.read_text(encoding="utf-8")
    replaced, count = re.subn(
        r"(?m)^max_iterations:\s*\d+\s*$",
        f"max_iterations: {max_iterations}",
        text,
        count=1,
    )
    if count != 1:
        raise QuantCodeEvalRepairProbeError("worker agent.yaml has no max_iterations")
    config.write_text(replaced, encoding="utf-8")
    return target


def _read_answer_free(attempt_dir: Path) -> dict[str, object]:
    for path in (
        attempt_dir / "verifier" / "answer-free-evidence.json",
        attempt_dir / "completed-score.json",
    ):
        if path.is_file():
            value = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                return value
    return {"evidence_status": "missing"}


def run_probe_arm(
    *,
    label: str,
    config_path: str | Path,
    public_root: str | Path,
    trusted_root: str | Path,
    run_dir: str | Path,
    worker_dir: str | Path,
    seed_strategy: str | Path | None,
    worker_instruction: str | None = None,
    worker_image_ref: str,
    verifier_image_ref: str,
    proxy_image_ref: str,
    task_panel_path: str | Path,
    task_id: str = "T26",
    max_iterations: int = 12,
) -> dict[str, object]:
    """Run one short repair Worker and then score its artifact independently."""

    root = Path(run_dir).resolve()
    probe_worker = materialize_probe_worker(
        worker_dir,
        root / "probe-worker-input",
        max_iterations=max_iterations,
    )
    snapshot, evaluator, _, frozen_worker = prepare_quantcodeeval_h0(
        config_path=config_path,
        public_root=public_root,
        trusted_root=trusted_root,
        run_dir=root,
        worker_dir=probe_worker,
        worker_image_ref=worker_image_ref,
        verifier_image_ref=verifier_image_ref,
        proxy_image_ref=proxy_image_ref,
        task_panel_path=task_panel_path,
        task_ids=(task_id,),
    )
    overlay = materialize_probe_public_root(
        public_root,
        root / "probe-public",
        task_id=task_id,
        seed_strategy=seed_strategy,
        worker_instruction=worker_instruction,
    )
    evaluator.executor.public_task_root = overlay
    task = snapshot.task(task_id)
    summary = evaluator.evaluate(
        worker_dir=frozen_worker,
        tasks=(task,),
        split=PROBE_SPLIT,
        checkpoint=PROBE_CHECKPOINT,
        run_dir=root,
    )
    worker_digest = hash_worker_directory(frozen_worker)
    logical = TaskAttempt.create(
        run_id=root.name,
        benchmark_commit=snapshot.commit,
        task_id=task_id,
        split=PROBE_SPLIT,
        checkpoint=PROBE_CHECKPOINT,
        worker_digest=worker_digest,
    )
    attempt_dirs = [
        path.parent
        for path in (root / "attempts").glob("*/attempt.json")
        if json.loads(path.read_text(encoding="utf-8")).get("task_id") == task_id
    ]
    if not attempt_dirs:
        raise QuantCodeEvalRepairProbeError("probe produced no attempt evidence")
    attempt_dir = max(attempt_dirs, key=lambda path: path.stat().st_mtime_ns)
    worker_summary_path = attempt_dir / "worker-execution.json"
    worker_summary: Mapping[str, object] = {}
    if worker_summary_path.is_file():
        raw = json.loads(worker_summary_path.read_text(encoding="utf-8"))
        worker_summary = raw.get("summary", {}) if isinstance(raw, dict) else {}
    cost = audit_fixed_checkpoint_proxy_costs(
        root,
        expected_attempts=1,
        checkpoint=PROBE_CHECKPOINT,
        split=PROBE_SPLIT,
    )
    score = summary.scores[0]
    result = {
        "schema_version": 1,
        "protocol": "quantcodeeval-paired-runtime-repair-probe-v1",
        "label": label,
        "task_id": task_id,
        "max_iterations": max_iterations,
        "logical_attempt_id": logical.attempt_id,
        "terminal_attempt_id": attempt_dir.name,
        "score": asdict(score),
        "worker_summary": dict(worker_summary),
        "answer_free_evidence": _read_answer_free(attempt_dir),
        "cost": cost,
        "artifact": str(attempt_dir / "artifacts" / "strategy.py"),
    }
    _atomic_private_json(root / "PROBE-RESULT.json", result)
    return result


def compare_probe_arms(
    parent: Mapping[str, object], candidate: Mapping[str, object]
) -> dict[str, object]:
    """Classify component usefulness separately from an official score claim."""

    def score(row: Mapping[str, object]) -> tuple[int, int, float]:
        official = row.get("score", {})
        if not isinstance(official, Mapping):
            return (0, 0, 0.0)
        return (
            int(official.get("tests_passed") or 0),
            -int(official.get("tests_failed") or 0),
            float(official.get("reward") or 0.0),
        )

    parent_score = score(parent)
    candidate_score = score(candidate)
    if candidate_score[2] > parent_score[2]:
        status = "binary-helpful"
    elif candidate_score[0] > parent_score[0]:
        status = "score-helpful"
    elif candidate_score[0] == parent_score[0] and candidate_score[0] > 3:
        status = "repair-helpful-tie"
    else:
        status = "not-demonstrated"
    return {
        "schema_version": 1,
        "protocol": "quantcodeeval-paired-runtime-repair-probe-v1",
        "status": status,
        "parent_tests_passed": parent_score[0],
        "candidate_tests_passed": candidate_score[0],
        "property_delta": candidate_score[0] - parent_score[0],
        "parent_reward": parent_score[2],
        "candidate_reward": candidate_score[2],
        "advance_to_blind_t26": status in {"binary-helpful", "score-helpful"},
        "claim_boundary": "seeded repair probe; not a from-scratch benchmark result",
    }
