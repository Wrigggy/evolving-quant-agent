"""Blind-validation noise calibration from a completed QFBench baseline."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Mapping

from .evaluation import OfficialTaskScore, aggregate_domain_macro


_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_FORMULA_VERSION = "max-absolute-deviation-floor-v1"


class ValidationCalibrationError(ValueError):
    """The validation calibration is incomplete or identity-incompatible."""


@dataclass(frozen=True)
class ValidationCalibration:
    source_run_id: str
    source_result_sha256: str
    validation_task_ids: tuple[str, ...]
    repetition_scores: tuple[float, ...]
    mean_score: float
    floor: float
    tolerance: float
    formula_version: str
    digest: str

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["validation_task_ids"] = list(self.validation_task_ids)
        payload["repetition_scores"] = list(self.repetition_scores)
        payload["schema_version"] = 1
        return payload


def _identity_payload(
    *,
    source_run_id: str,
    source_result_sha256: str,
    validation_task_ids: tuple[str, ...],
    repetition_scores: tuple[float, ...],
    mean_score: float,
    floor: float,
    tolerance: float,
    formula_version: str,
) -> dict:
    return {
        "schema_version": 1,
        "source_run_id": source_run_id,
        "source_result_sha256": source_result_sha256,
        "validation_task_ids": list(validation_task_ids),
        "repetition_scores": list(repetition_scores),
        "mean_score": mean_score,
        "floor": floor,
        "tolerance": tolerance,
        "formula_version": formula_version,
    }


def _digest(payload: Mapping) -> str:
    return hashlib.sha256(
        json.dumps(
            dict(payload), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def calibrate_validation_tolerance(
    *,
    run_id: str,
    repetition_scores: Iterable[float],
    validation_task_ids: Iterable[str],
    source_result_sha256: str,
    floor: float = 0.02,
) -> ValidationCalibration:
    """Apply the preregistered max-deviation formula to five repetitions."""

    if not isinstance(run_id, str) or not _RUN_ID_RE.fullmatch(run_id):
        raise ValidationCalibrationError("source run ID is invalid")
    if not isinstance(source_result_sha256, str) or not _SHA256_RE.fullmatch(
        source_result_sha256
    ):
        raise ValidationCalibrationError("source result SHA-256 is invalid")
    task_ids = tuple(validation_task_ids)
    if (
        not task_ids
        or len(task_ids) != len(set(task_ids))
        or any(not isinstance(task_id, str) or not task_id for task_id in task_ids)
    ):
        raise ValidationCalibrationError(
            "validation task IDs must be non-empty and unique"
        )
    scores = tuple(float(value) for value in repetition_scores)
    if len(scores) != 5:
        raise ValidationCalibrationError(
            "validation calibration requires exactly five repetitions"
        )
    if any(not math.isfinite(value) or not 0.0 <= value <= 1.0 for value in scores):
        raise ValidationCalibrationError(
            "validation repetition scores must be finite and between zero and one"
        )
    if isinstance(floor, bool) or not isinstance(floor, (int, float)):
        raise ValidationCalibrationError("validation tolerance floor is invalid")
    floor_value = float(floor)
    if not math.isfinite(floor_value) or floor_value < 0.0:
        raise ValidationCalibrationError("validation tolerance floor is invalid")

    mean_score = statistics.fmean(scores)
    max_deviation = max(abs(value - mean_score) for value in scores)
    tolerance = max(floor_value, max_deviation)
    identity = _identity_payload(
        source_run_id=run_id,
        source_result_sha256=source_result_sha256,
        validation_task_ids=task_ids,
        repetition_scores=scores,
        mean_score=mean_score,
        floor=floor_value,
        tolerance=tolerance,
        formula_version=_FORMULA_VERSION,
    )
    return ValidationCalibration(
        source_run_id=run_id,
        source_result_sha256=source_result_sha256,
        validation_task_ids=task_ids,
        repetition_scores=scores,
        mean_score=mean_score,
        floor=floor_value,
        tolerance=tolerance,
        formula_version=_FORMULA_VERSION,
        digest=_digest(identity),
    )


def calibration_from_baseline_run(
    run_dir: str | Path,
    *,
    validation_tasks: Iterable,
    expected_run_id: str,
    floor: float = 0.02,
) -> ValidationCalibration:
    """Recompute the validation domain macro for every baseline repetition."""

    root = Path(run_dir).expanduser().resolve()
    result_path = root / "result.json"
    try:
        raw_result = result_path.read_bytes()
        result = json.loads(raw_result)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationCalibrationError(
            f"cannot load completed baseline result: {exc}"
        ) from exc
    if not isinstance(result, dict):
        raise ValidationCalibrationError("baseline result must be an object")
    if result.get("run_id") != expected_run_id or root.name != expected_run_id:
        raise ValidationCalibrationError("baseline run identity mismatch")
    aggregate = result.get("aggregate")
    repetitions = result.get("repetitions")
    if (
        result.get("complete") is not True
        or not isinstance(aggregate, dict)
        or aggregate.get("complete") is not True
        or aggregate.get("expected_repetitions") != 5
        or aggregate.get("completed_repetitions") != 5
        or not isinstance(repetitions, list)
        or len(repetitions) != 5
    ):
        raise ValidationCalibrationError(
            "validation calibration requires exactly five complete repetitions"
        )

    tasks = tuple(validation_tasks)
    task_ids = tuple(task.task_id for task in tasks)
    if (
        not tasks
        or len(task_ids) != len(set(task_ids))
        or any(
            not isinstance(task_id, str)
            or not task_id
            or not isinstance(getattr(task, "domain", None), str)
            or not task.domain
            for task_id, task in zip(task_ids, tasks)
        )
    ):
        raise ValidationCalibrationError(
            "validation tasks must have unique IDs and non-empty domains"
        )
    tasks_by_id = {task.task_id: task for task in tasks}
    repetition_scores = []
    for expected_number, repetition in enumerate(repetitions, start=1):
        if (
            not isinstance(repetition, dict)
            or repetition.get("repetition") != expected_number
        ):
            raise ValidationCalibrationError(
                "baseline repetition numbering is incomplete or unordered"
            )
        primary = repetition.get("primary")
        task_rewards = primary.get("task_rewards") if isinstance(primary, dict) else None
        if not isinstance(task_rewards, dict) or any(
            task_id not in task_rewards for task_id in task_ids
        ):
            raise ValidationCalibrationError(
                "baseline repetition is missing a validation task score"
            )
        scores = []
        for task_id in task_ids:
            reward = task_rewards[task_id]
            if (
                isinstance(reward, bool)
                or not isinstance(reward, (int, float))
                or not math.isfinite(float(reward))
                or not 0.0 <= float(reward) <= 1.0
            ):
                raise ValidationCalibrationError(
                    f"invalid validation reward for task {task_id!r}"
                )
            scores.append(
                OfficialTaskScore(
                    task_id=task_id,
                    domain=tasks_by_id[task_id].domain,
                    reward=float(reward),
                )
            )
        summary = aggregate_domain_macro(
            scores, expected_domains={task.domain for task in tasks}
        )
        repetition_scores.append(summary.overall)

    return calibrate_validation_tolerance(
        run_id=expected_run_id,
        repetition_scores=repetition_scores,
        validation_task_ids=task_ids,
        source_result_sha256=hashlib.sha256(raw_result).hexdigest(),
        floor=floor,
    )


def write_validation_calibration(
    path: str | Path,
    calibration: ValidationCalibration,
) -> None:
    """Persist one canonical calibration artifact atomically."""

    if not isinstance(calibration, ValidationCalibration):
        raise ValidationCalibrationError("invalid validation calibration object")
    destination = Path(path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(calibration.to_dict(), sort_keys=True, indent=2) + "\n"
    )
    os.replace(temporary, destination)


def load_validation_calibration(path: str | Path) -> ValidationCalibration:
    """Load a calibration artifact and verify its canonical digest."""

    source = Path(path).expanduser().resolve()
    try:
        payload = json.loads(source.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationCalibrationError(
            f"cannot load validation calibration: {exc}"
        ) from exc
    expected_keys = {
        "schema_version",
        "source_run_id",
        "source_result_sha256",
        "validation_task_ids",
        "repetition_scores",
        "mean_score",
        "floor",
        "tolerance",
        "formula_version",
        "digest",
    }
    if not isinstance(payload, dict) or set(payload) != expected_keys:
        raise ValidationCalibrationError(
            "validation calibration has unknown or missing fields"
        )
    if payload.get("schema_version") != 1:
        raise ValidationCalibrationError("unsupported validation calibration schema")
    digest = payload["digest"]
    identity = {key: value for key, value in payload.items() if key != "digest"}
    if not isinstance(digest, str) or digest != _digest(identity):
        raise ValidationCalibrationError("validation calibration digest mismatch")
    calibration = calibrate_validation_tolerance(
        run_id=payload["source_run_id"],
        repetition_scores=payload["repetition_scores"],
        validation_task_ids=payload["validation_task_ids"],
        source_result_sha256=payload["source_result_sha256"],
        floor=payload["floor"],
    )
    if calibration.to_dict() != payload:
        raise ValidationCalibrationError(
            "validation calibration formula output mismatch"
        )
    return calibration


__all__ = [
    "ValidationCalibration",
    "ValidationCalibrationError",
    "calibrate_validation_tolerance",
    "calibration_from_baseline_run",
    "load_validation_calibration",
    "write_validation_calibration",
]
