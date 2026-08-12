"""Answer-free process metrics for QFBench worker harness comparisons."""

from __future__ import annotations

import json
import re
import statistics
from pathlib import Path
from typing import Mapping, Sequence


_INVENTORY = re.compile(r"\b(?:ls|find|tree)\b|/app/data", re.IGNORECASE)
_VALIDATION = re.compile(
    r"\b(?:pytest|assert|validate|verification|cross[- ]?check|sanity check)\b",
    re.IGNORECASE,
)
_INDEPENDENT = re.compile(
    r"\b(?:independent|re-derive|rederive|second (?:path|implementation))\b",
    re.IGNORECASE,
)
_OUTPUT_INSPECTION = re.compile(
    r"(?:cat|head|tail|ls)[^\n]*(?:/app/output|output/)|"
    r"(?:json\.load|read_csv|DictReader)[^\n]*(?:output|artifact)",
    re.IGNORECASE,
)


def _json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _trace_assistant_text(path: Path) -> list[str]:
    messages: list[str] = []
    if not path.is_file():
        return messages
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, Mapping) and str(payload.get("role")) == "assistant":
            messages.append(str(payload.get("content", "")))
    return messages


def _proxy_usage(attempt_dir: Path) -> dict[str, int]:
    completed = 0
    noncompleted = 0
    total_tokens = 0
    path = attempt_dir / "proxy-audit.jsonl"
    if not path.is_file():
        return {
            "completed_model_requests": 0,
            "noncompleted_model_requests": 0,
            "observed_total_tokens": 0,
        }
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"invalid proxy audit line {path}:{line_number}"
            ) from exc
        if not isinstance(record, Mapping):
            raise ValueError(f"proxy audit line is not an object {path}:{line_number}")
        if record.get("request_state") == "completed":
            completed += 1
        else:
            noncompleted += 1
        tokens = record.get("total_tokens")
        if isinstance(tokens, int):
            total_tokens += tokens
    return {
        "completed_model_requests": completed,
        "noncompleted_model_requests": noncompleted,
        "observed_total_tokens": total_tokens,
    }


def measure_attempt_capability(attempt_dir: Path) -> dict[str, object]:
    """Measure observable worker behavior without reading verifier internals."""

    attempt = _json(attempt_dir / "attempt.json")
    usage = _proxy_usage(attempt_dir)
    execution_path = attempt_dir / "worker-execution.json"
    if not execution_path.is_file():
        score = _json(attempt_dir / "completed-score.json")
        tags = {str(value) for value in score.get("diagnostic_tags", [])}
        if "timeout" not in tags:
            raise ValueError(
                "worker execution is missing without an explicit timeout: "
                f"{attempt_dir}"
            )
        return {
            "task_id": str(attempt.get("task_id", "")),
            "attempt_id": str(attempt.get("attempt_id", attempt_dir.name)),
            "execution_status": "worker_timeout",
            "trace_available": False,
            "turns": None,
            "tool_calls": None,
            "tool_errors": None,
            "tool_error_rate": None,
            "wall_seconds": None,
            "artifact_files": None,
            "first_turn_workspace_inventory": None,
            "validation_behavior_observed": None,
            "independent_crosscheck_observed": None,
            "output_inspection_observed": None,
            "assistant_turns_observed": None,
            **usage,
        }
    execution = _json(execution_path)
    summary = execution.get("summary")
    summary = dict(summary) if isinstance(summary, Mapping) else {}
    trace_name = str(execution.get("trace_uri", "raw-trace.jsonl"))
    assistant_messages = _trace_assistant_text(attempt_dir / trace_name)
    first = assistant_messages[0] if assistant_messages else ""
    all_assistant = "\n".join(assistant_messages)
    tool_calls = int(summary.get("tool_calls", 0) or 0)
    tool_errors = int(summary.get("tool_errors", 0) or 0)
    return {
        "task_id": str(attempt.get("task_id", "")),
        "attempt_id": str(attempt.get("attempt_id", attempt_dir.name)),
        "execution_status": "complete",
        "trace_available": True,
        "turns": int(summary.get("turns", 0) or 0),
        "tool_calls": tool_calls,
        "tool_errors": tool_errors,
        "tool_error_rate": tool_errors / tool_calls if tool_calls else 0.0,
        "wall_seconds": float(summary.get("secs", 0.0) or 0.0),
        "artifact_files": int(summary.get("files", 0) or 0),
        "first_turn_workspace_inventory": bool(_INVENTORY.search(first)),
        "validation_behavior_observed": bool(_VALIDATION.search(all_assistant)),
        "independent_crosscheck_observed": bool(_INDEPENDENT.search(all_assistant)),
        "output_inspection_observed": bool(_OUTPUT_INSPECTION.search(all_assistant)),
        "assistant_turns_observed": len(assistant_messages),
        **usage,
    }


def _aggregate_vectors(ordered: Sequence[Mapping[str, object]]) -> dict[str, object]:
    observed = [item for item in ordered if item.get("trace_available") is True]
    if not observed:
        raise ValueError("capability panel has no trace-observable attempts")
    total_calls = sum(int(item["tool_calls"]) for item in observed)
    total_errors = sum(int(item["tool_errors"]) for item in observed)

    def rate(field: str) -> float:
        return sum(bool(item[field]) for item in observed) / len(observed)

    return {
        "totals": {
            "turns": sum(int(item["turns"]) for item in observed),
            "tool_calls": total_calls,
            "tool_errors": total_errors,
            "wall_seconds": sum(float(item["wall_seconds"]) for item in observed),
            "artifact_files": sum(int(item["artifact_files"]) for item in observed),
        },
        "rates": {
            "tool_error_rate": total_errors / total_calls if total_calls else 0.0,
            "first_turn_workspace_inventory": rate(
                "first_turn_workspace_inventory"
            ),
            "validation_behavior": rate("validation_behavior_observed"),
            "independent_crosscheck": rate("independent_crosscheck_observed"),
            "output_inspection": rate("output_inspection_observed"),
        },
        "means": {
            "turns": statistics.fmean(float(item["turns"]) for item in observed),
            "tool_calls": statistics.fmean(
                float(item["tool_calls"]) for item in observed
            ),
            "wall_seconds": statistics.fmean(
                float(item["wall_seconds"]) for item in observed
            ),
            "artifact_files": statistics.fmean(
                float(item["artifact_files"]) for item in observed
            ),
        },
    }


def measure_checkpoint_capability(
    *,
    run_dir: Path,
    checkpoint: str,
    task_ids: Sequence[str],
) -> dict[str, object]:
    """Aggregate a fixed checkpoint's process behavior over exact tasks."""

    expected = set(task_ids)
    attempts: dict[str, dict[str, object]] = {}
    for attempt_path in sorted(run_dir.glob("attempts/*/attempt.json")):
        attempt = _json(attempt_path)
        if attempt.get("checkpoint") != checkpoint:
            continue
        task_id = str(attempt.get("task_id", ""))
        if task_id not in expected:
            continue
        if task_id in attempts:
            raise ValueError(f"duplicate attempt for checkpoint/task: {task_id}")
        attempts[task_id] = measure_attempt_capability(attempt_path.parent)
    missing = sorted(expected - set(attempts))
    if missing:
        raise ValueError(f"checkpoint is missing capability attempts: {missing}")
    ordered = [attempts[task_id] for task_id in task_ids]
    task_count = len(ordered)
    observed = [item for item in ordered if item.get("trace_available") is True]
    aggregate = _aggregate_vectors(ordered)
    return {
        "schema_version": 1,
        "scope": (
            "answer-free observable worker process; missing timeout traces remain "
            "explicit and are excluded from trace-derived rates"
        ),
        "checkpoint": checkpoint,
        "task_count": task_count,
        "task_vectors": ordered,
        "coverage": {
            "trace_available_count": len(observed),
            "trace_availability_rate": len(observed) / task_count,
            "normal_completion_count": sum(
                item.get("execution_status") == "complete" for item in ordered
            ),
            "worker_timeout_count": sum(
                item.get("execution_status") == "worker_timeout"
                for item in ordered
            ),
        },
        **aggregate,
    }


def capability_delta(
    before: Mapping[str, object], after: Mapping[str, object]
) -> dict[str, object]:
    """Return signed after-minus-before deltas for comparable aggregates."""

    if before.get("task_count") != after.get("task_count"):
        raise ValueError("capability panels differ")
    left_vectors = before.get("task_vectors")
    right_vectors = after.get("task_vectors")
    if not isinstance(left_vectors, list) or not isinstance(right_vectors, list):
        raise ValueError("capability report lacks task vectors")
    left_by_task = {
        str(item.get("task_id")): item
        for item in left_vectors
        if isinstance(item, Mapping)
    }
    right_by_task = {
        str(item.get("task_id")): item
        for item in right_vectors
        if isinstance(item, Mapping)
    }
    if set(left_by_task) != set(right_by_task):
        raise ValueError("capability task identities differ")
    paired_ids = sorted(
        task_id
        for task_id in left_by_task
        if left_by_task[task_id].get("trace_available") is True
        and right_by_task[task_id].get("trace_available") is True
    )
    left_paired = _aggregate_vectors([left_by_task[value] for value in paired_ids])
    right_paired = _aggregate_vectors([right_by_task[value] for value in paired_ids])
    transitions: dict[str, int] = {}
    for task_id in sorted(left_by_task):
        key = (
            f"{left_by_task[task_id].get('execution_status')}->"
            f"{right_by_task[task_id].get('execution_status')}"
        )
        transitions[key] = transitions.get(key, 0) + 1
    result: dict[str, object] = {
        "schema_version": 1,
        "scope": "paired trace-observable tasks plus explicit status transitions",
        "paired_task_ids": paired_ids,
        "paired_task_count": len(paired_ids),
        "status_transitions": transitions,
    }
    for section in ("totals", "rates", "means"):
        left = left_paired.get(section)
        right = right_paired.get(section)
        if not isinstance(left, Mapping) or not isinstance(right, Mapping):
            raise ValueError(f"capability report lacks {section}")
        if set(left) != set(right):
            raise ValueError(f"capability {section} keys differ")
        result[section] = {
            key: float(right[key]) - float(left[key]) for key in sorted(left)
        }
    left_coverage = before.get("coverage")
    right_coverage = after.get("coverage")
    if not isinstance(left_coverage, Mapping) or not isinstance(
        right_coverage, Mapping
    ):
        raise ValueError("capability report lacks coverage")
    result["coverage"] = {
        key: float(right_coverage[key]) - float(left_coverage[key])
        for key in sorted(left_coverage)
    }
    return result


__all__ = [
    "capability_delta",
    "measure_attempt_capability",
    "measure_checkpoint_capability",
]
