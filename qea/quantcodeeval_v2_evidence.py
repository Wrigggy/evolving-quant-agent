"""QuantCodeEval v2 evidence with exact, answer-free mutation experience."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Iterable, Mapping

from .evolution_evidence import EvidenceRecord
from .quantcodeeval_evidence import (
    QuantCodeEvalEvidenceError,
    QuantEvidenceAttemptSource,
    build_quantcodeeval_evidence,
)
from .quantcodeeval_history import (
    QuantCodeEvalHistoryError,
    materialize_quantcodeeval_history_evidence,
)


class QuantCodeEvalV2EvidenceError(ValueError):
    """A v2 evidence corpus or its history projection is inconsistent."""


_PREFERRED_PRIMARY_COMPONENTS = {
    "artifact_interface": ["validator", "tools", "tool_descriptions"],
    "data_temporal_integrity": ["tools", "validator", "skills"],
    "quant_definition_estimation": ["tools", "skills", "memory"],
    "portfolio_execution": ["tools", "validator", "routing"],
    "resource_termination": ["middleware", "routing", "agent_config"],
    "isolated_task_specific": [],
    "unknown": [],
}


def _write_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _digest_tree(root: Path) -> tuple[str, tuple[str, ...]]:
    digest = hashlib.sha256()
    members: list[str] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            raise QuantCodeEvalV2EvidenceError("v2 evidence contains a symlink")
        if not path.is_file() or path.name == "access_log.jsonl":
            continue
        relative = path.relative_to(root).as_posix()
        payload = path.read_bytes()
        encoded = relative.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
        members.append(relative)
    return digest.hexdigest(), tuple(members)


def build_quantcodeeval_v2_evidence(
    *,
    destination: str | Path,
    public_task_roots: Mapping[str, str | Path],
    attempts: Iterable[QuantEvidenceAttemptSource],
    current_evaluation_id: str,
    history_root: str | Path | None,
    iteration_summaries: Iterable[Mapping[str, object]] = (),
    max_primary_components: int = 2,
    max_declared_components: int = 6,
) -> EvidenceRecord:
    """Build v1-safe evidence plus immutable prior candidate snapshots and diffs."""

    if type(max_primary_components) is not int or not 1 <= max_primary_components <= 2:
        raise QuantCodeEvalV2EvidenceError(
            "max_primary_components must be one or two"
        )
    if (
        type(max_declared_components) is not int
        or not max_primary_components <= max_declared_components <= 9
    ):
        raise QuantCodeEvalV2EvidenceError(
            "max_declared_components must cover primary roles and be at most nine"
        )
    sources = tuple(attempts)
    current = [
        source
        for source in sources
        if source.record.evaluation_id == current_evaluation_id
    ]
    current_rewards = {
        source.record.task_id: float(source.record.official_reward)
        for source in current
    }
    if set(current_rewards) != {str(task_id) for task_id in public_task_roots}:
        raise QuantCodeEvalV2EvidenceError(
            "current v2 evidence must cover the complete fixed task panel"
        )

    target = Path(destination).expanduser().resolve()
    if target.exists() or target.is_symlink():
        raise QuantCodeEvalV2EvidenceError(
            "v2 evidence destination must not already exist"
        )
    staging = target.with_name(target.name + ".partial")
    base = target.with_name(target.name + ".base-partial")
    for path in (staging, base):
        if path.exists() or path.is_symlink():
            raise QuantCodeEvalV2EvidenceError(
                f"v2 evidence staging path already exists: {path.name}"
            )
    try:
        build_quantcodeeval_evidence(
            destination=base,
            public_task_roots=public_task_roots,
            attempts=sources,
            current_evaluation_id=current_evaluation_id,
            history=iteration_summaries,
        )
        shutil.copytree(base, staging, copy_function=shutil.copy2)
        history_summary: dict[str, object] = {
            "schema_version": 1,
            "entry_count": 0,
            "entry_ids": [],
            "object_count": 0,
            "diff_count": 0,
        }
        if history_root is not None:
            try:
                projected = materialize_quantcodeeval_history_evidence(
                    history_root=history_root,
                    destination=staging / "history" / "archive",
                )
            except QuantCodeEvalHistoryError as exc:
                raise QuantCodeEvalV2EvidenceError(
                    f"cannot project QuantCodeEval history: {exc}"
                ) from exc
            history_summary = {
                key: projected[key]
                for key in (
                    "schema_version",
                    "entry_count",
                    "entry_ids",
                    "object_count",
                    "diff_count",
                )
            }
        _write_json(staging / "history" / "SUMMARY.json", history_summary)
        _write_json(
            staging / "contract.json",
            {
                "schema_version": 2,
                "stage": "PGBHS_V2",
                "benchmark": "quantcodeeval",
                "decision_protocol": "quant_property_v2",
                "feedback_tier": "answer_free_property_family_v2",
                "task_ids": sorted(current_rewards),
                "target_task_ids": sorted(
                    task_id
                    for task_id, reward in current_rewards.items()
                    if reward == 0.0
                ),
                "protection_task_ids": sorted(
                    task_id
                    for task_id, reward in current_rewards.items()
                    if reward == 1.0
                ),
                "current_evaluation_id": current_evaluation_id,
                "history_required": history_summary["entry_count"] != 0,
                "history_entry_ids": history_summary["entry_ids"],
                "max_primary_components": max_primary_components,
                "max_declared_components": max_declared_components,
                "preferred_primary_components": _PREFERRED_PRIMARY_COMPONENTS,
                "component_priors_are_advisory": True,
                "exact_history_content_exposed": history_summary["entry_count"] != 0,
                "oracle_fields_exposed": False,
            },
        )
        sha256, members = _digest_tree(staging)
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging, target)
        return EvidenceRecord(root=target, sha256=sha256, members=members)
    except (QuantCodeEvalEvidenceError, OSError, ValueError) as exc:
        if isinstance(exc, QuantCodeEvalV2EvidenceError):
            raise
        raise QuantCodeEvalV2EvidenceError(f"cannot build v2 evidence: {exc}") from exc
    finally:
        shutil.rmtree(base, ignore_errors=True)
        shutil.rmtree(staging, ignore_errors=True)


__all__ = [
    "QuantCodeEvalV2EvidenceError",
    "build_quantcodeeval_v2_evidence",
]
