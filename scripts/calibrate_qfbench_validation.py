#!/usr/bin/env python3
"""Create an immutable blind-validation calibration from a base run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from qea.qfbench_validation import (
    ValidationCalibrationError,
    calibration_from_baseline_run,
    write_validation_calibration,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Calibrate QFBench blind-validation sampling tolerance"
    )
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--floor", type=float, default=0.02)
    return parser


def _validation_tasks(manifest_path: Path) -> tuple[SimpleNamespace, ...]:
    try:
        payload = json.loads(manifest_path.expanduser().resolve().read_text())
        entries = payload["evolution"]["validation"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValidationCalibrationError(
            f"cannot load validation panel from manifest: {exc}"
        ) from exc
    if payload.get("schema_version") != 2 or not isinstance(entries, list):
        raise ValidationCalibrationError(
            "validation calibration requires a schema-v2 evolution manifest"
        )
    tasks = []
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) < {"task_id", "domain"}:
            raise ValidationCalibrationError(
                "validation manifest entries need task_id and domain"
            )
        task_id = entry["task_id"]
        domain = entry["domain"]
        if not isinstance(task_id, str) or not isinstance(domain, str):
            raise ValidationCalibrationError(
                "validation manifest task identity must be textual"
            )
        tasks.append(SimpleNamespace(task_id=task_id, domain=domain))
    if not tasks:
        raise ValidationCalibrationError("validation panel must not be empty")
    return tuple(tasks)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    run_dir = args.run_dir.expanduser().resolve()
    calibration = calibration_from_baseline_run(
        run_dir,
        validation_tasks=_validation_tasks(args.manifest),
        expected_run_id=run_dir.name,
        floor=args.floor,
    )
    write_validation_calibration(args.output, calibration)
    print(json.dumps({
        "source_run_id": calibration.source_run_id,
        "validation_task_count": len(calibration.validation_task_ids),
        "repetition_scores": calibration.repetition_scores,
        "mean_score": calibration.mean_score,
        "tolerance": calibration.tolerance,
        "formula_version": calibration.formula_version,
        "digest": calibration.digest,
        "output": str(args.output.expanduser().resolve()),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
