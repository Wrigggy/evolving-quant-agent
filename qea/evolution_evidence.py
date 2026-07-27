"""Build deterministic proposer evidence without crossing evaluator boundaries."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Mapping

from .evolution_feedback import (
    FeedbackMode,
    PublicTaskRubric,
    VerifierCriterionRule,
    sanitize_ctrf_feedback,
)


class EvidenceContractError(ValueError):
    """An evidence tree contains an unknown task, unsafe path, or private input."""


@dataclass(frozen=True)
class EvidenceRecord:
    root: Path
    sha256: str
    members: tuple[str, ...]


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")
    os.replace(temporary, path)


def _read_json(path: Path, label: str) -> dict:
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceContractError(f"invalid {label} {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise EvidenceContractError(f"{label} must be an object: {path}")
    return payload


def _safe_relative(path: Path, root: Path, label: str) -> Path:
    if path.is_symlink():
        raise EvidenceContractError(f"symlink is forbidden in {label}: {path}")
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise EvidenceContractError(f"{label} is outside its root: {path}") from exc
    if any(part in {"tests", "solution"} for part in relative.parts):
        raise EvidenceContractError(f"private evaluator path in {label}: {relative}")
    return relative


def _copy_file(source: Path, destination: Path) -> None:
    if source.is_symlink() or not source.is_file():
        raise EvidenceContractError(f"evidence source is not a regular file: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(source.read_bytes())


def _copy_public_task(task, destination: Path) -> None:
    task_root = Path(task.root).resolve()
    for source in sorted(
        (Path(path) for path in task.worker_files),
        key=lambda path: path.resolve().as_posix(),
    ):
        relative = _safe_relative(source, task_root, "public task file")
        _copy_file(source, destination / relative)


def _copy_artifacts(artifact_root: Path, destination: Path) -> None:
    if not artifact_root.is_dir():
        raise EvidenceContractError(f"worker artifact root does not exist: {artifact_root}")
    for source in sorted(
        artifact_root.rglob("*"),
        key=lambda path: path.relative_to(artifact_root).as_posix(),
    ):
        if source.is_symlink():
            raise EvidenceContractError(f"symlink is forbidden in worker artifacts: {source}")
        if source.is_file():
            _copy_file(source, destination / source.relative_to(artifact_root))


def _public_score(score: dict) -> dict:
    return {
        "task_id": str(score["task_id"]),
        "official_reward": float(score["reward"]),
        "diagnostic_tags": sorted(str(tag) for tag in score.get("diagnostic_tags", ())),
        "tests_passed": score.get("tests_passed"),
        "tests_failed": score.get("tests_failed"),
        "provenance": "official_scalar",
    }


def _attempts(run_dir: Path) -> tuple[tuple[Path, dict], ...]:
    result: list[tuple[Path, dict]] = []
    attempts_root = run_dir / "attempts"
    if not attempts_root.exists():
        return ()
    for path in sorted(attempts_root.glob("*/attempt.json")):
        result.append((path.parent, _read_json(path, "attempt identity")))
    return tuple(result)


def _rubric_payload(rubric: PublicTaskRubric) -> dict:
    return {
        "schema_version": 1,
        "task_id": rubric.task_id,
        "provenance": "public_task",
        "criteria": [asdict(item) for item in rubric.criteria],
    }


def _copy_rich_attempt(
    *,
    attempt_dir: Path,
    attempt: dict,
    destination: Path,
    rubric: PublicTaskRubric,
    verifier_rules: Iterable[VerifierCriterionRule],
) -> None:
    score = _read_json(attempt_dir / "completed-score.json", "completed score")
    if score.get("task_id") != attempt.get("task_id"):
        raise EvidenceContractError("completed score task identity mismatch")

    execution_path = attempt_dir / "worker-execution.json"
    if not execution_path.is_file():
        diagnostic_tags = {str(tag) for tag in score.get("diagnostic_tags", ())}
        if "timeout" not in diagnostic_tags or float(score["reward"]) != 0.0:
            _read_json(execution_path, "worker execution manifest")
        public_evaluation = _public_score(score)
        public_evaluation["criterion_results"] = []
        _write_json(destination / "public_evaluation.json", public_evaluation)
        return

    execution = _read_json(execution_path, "worker execution manifest")
    if execution.get("attempt_id") != attempt.get("attempt_id"):
        raise EvidenceContractError("worker execution attempt identity mismatch")
    trace_path = (attempt_dir / str(execution["trace_uri"])).resolve()
    final_path = (attempt_dir / str(execution["final_text_uri"])).resolve()
    artifact_root = (attempt_dir / str(execution["artifact_dir"])).resolve()
    for path, label in (
        (trace_path, "worker trace"),
        (final_path, "worker final text"),
        (artifact_root, "worker artifact root"),
    ):
        try:
            path.relative_to(attempt_dir.resolve())
        except ValueError as exc:
            raise EvidenceContractError(f"{label} escapes attempt directory") from exc

    _copy_file(trace_path, destination / "worker_trace.jsonl")
    _copy_file(final_path, destination / "worker_final.txt")
    _write_json(destination / "process_summary.json", dict(execution.get("summary", {})))
    _copy_artifacts(artifact_root, destination / "artifacts")

    criteria = {item.criterion_id: item for item in rubric.criteria}
    ctrf_path = attempt_dir / "verifier" / "ctrf.json"
    criterion_results = (
        sanitize_ctrf_feedback(ctrf_path, verifier_rules, criteria)
        if ctrf_path.is_file()
        else ()
    )
    public_evaluation = _public_score(score)
    public_evaluation["criterion_results"] = [
        asdict(item) for item in criterion_results
    ]
    _write_json(destination / "public_evaluation.json", public_evaluation)


def _digest_tree(root: Path) -> tuple[str, tuple[str, ...]]:
    digest = hashlib.sha256()
    files = sorted(
        (
            path for path in root.rglob("*")
            if path.is_file() and path.name != "access_log.jsonl"
        ),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    members: list[str] = []
    for path in files:
        relative = path.relative_to(root).as_posix()
        payload = path.read_bytes()
        encoded = relative.encode()
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
        members.append(relative)
    return digest.hexdigest(), tuple(members)


def build_evolution_evidence(
    *,
    mode: FeedbackMode,
    optimize_tasks: Iterable,
    held_out_task_ids: Iterable[str],
    run_dir: str | Path,
    destination: str | Path,
    feedback_manifest: Mapping[str, PublicTaskRubric],
    verifier_mapping: Mapping[str, Iterable[VerifierCriterionRule]],
    history: Iterable[dict],
) -> EvidenceRecord:
    """Build one immutable optimize-only corpus for the next proposal."""

    feedback_mode = FeedbackMode(mode)
    tasks = {str(task.task_id): task for task in optimize_tasks}
    if not tasks or set(tasks) != set(feedback_manifest):
        raise EvidenceContractError("optimize task and public feedback sets differ")
    if set(tasks) & set(held_out_task_ids):
        raise EvidenceContractError("optimize and held-out task sets overlap")
    if set(tasks) != set(verifier_mapping):
        raise EvidenceContractError("optimize task and verifier mapping sets differ")

    source_run = Path(run_dir).resolve()
    root = Path(destination).resolve()
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    (root / "access_log.jsonl").write_text("")
    _write_json(root / "contract.json", {
        "schema_version": 1,
        "mode": feedback_mode.value,
        "optimize_task_ids": sorted(tasks),
        "access_log": "access_log.jsonl",
        "held_out_feedback": False,
    })
    history_payload = tuple(dict(item) for item in history)
    encoded_history = json.dumps(history_payload, sort_keys=True)
    leaked_history_ids = [
        task_id for task_id in sorted(set(held_out_task_ids))
        if task_id and task_id in encoded_history
    ]
    if leaked_history_ids:
        raise EvidenceContractError(
            f"held-out identity in history: {leaked_history_ids}"
        )
    _write_json(root / "history" / "iterations.json", list(history_payload))

    task_scores: list[dict] = []
    for attempt_dir, attempt in _attempts(source_run):
        task_id = str(attempt.get("task_id", ""))
        split = str(attempt.get("split", ""))
        if split == "held_out":
            continue
        if split != "optimize":
            raise EvidenceContractError(f"unknown attempt split {split!r}")
        if task_id not in tasks:
            raise EvidenceContractError(f"unknown optimize task {task_id!r}")
        score_path = attempt_dir / "completed-score.json"
        if not score_path.is_file():
            continue
        score = _read_json(score_path, "completed score")
        task_scores.append({
            **_public_score(score),
            "checkpoint": str(attempt.get("checkpoint", "")),
        })
        if feedback_mode is not FeedbackMode.RICH:
            continue
        checkpoint = str(attempt.get("checkpoint", ""))
        if not checkpoint or "/" in checkpoint or ".." in checkpoint:
            raise EvidenceContractError(f"unsafe attempt checkpoint {checkpoint!r}")
        destination_attempt = (
            root / "tasks" / task_id / "attempts" / checkpoint
        )
        _copy_rich_attempt(
            attempt_dir=attempt_dir,
            attempt=attempt,
            destination=destination_attempt,
            rubric=feedback_manifest[task_id],
            verifier_rules=verifier_mapping[task_id],
        )

    _write_json(
        root / "feedback" / "task_scores.json",
        sorted(task_scores, key=lambda item: (item["checkpoint"], item["task_id"])),
    )
    if feedback_mode is FeedbackMode.RICH:
        for task_id, task in sorted(tasks.items()):
            task_root = root / "tasks" / task_id
            _copy_public_task(task, task_root)
            _write_json(
                task_root / "public_rubric.json",
                _rubric_payload(feedback_manifest[task_id]),
            )

    sha256, members = _digest_tree(root)
    return EvidenceRecord(root=root, sha256=sha256, members=members)
