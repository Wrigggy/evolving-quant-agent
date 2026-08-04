import json
from pathlib import Path
from types import SimpleNamespace

import pytest


RUN_ID = (
    "qfbench-rootless-base-85x5-official-"
    "deepseek-v4-flash-0731-all12x3-20260804"
)


def test_calibration_uses_max_absolute_deviation_with_floor() -> None:
    from qea.qfbench_validation import calibrate_validation_tolerance

    calibration = calibrate_validation_tolerance(
        run_id="base-85x5",
        repetition_scores=(0.40, 0.42, 0.38, 0.41, 0.39),
        validation_task_ids=("v1", "v2"),
        source_result_sha256="a" * 64,
    )

    assert calibration.mean_score == pytest.approx(0.40)
    assert calibration.tolerance == pytest.approx(0.02)
    assert calibration.floor == pytest.approx(0.02)
    assert calibration.formula_version == "max-absolute-deviation-floor-v1"
    assert len(calibration.digest) == 64


def test_calibration_uses_observed_deviation_above_floor() -> None:
    from qea.qfbench_validation import calibrate_validation_tolerance

    calibration = calibrate_validation_tolerance(
        run_id="base-85x5",
        repetition_scores=(0.2, 0.2, 0.2, 0.2, 0.7),
        validation_task_ids=("v1",),
        source_result_sha256="b" * 64,
    )

    assert calibration.mean_score == pytest.approx(0.3)
    assert calibration.tolerance == pytest.approx(0.4)


def _write_baseline_result(run_dir: Path, *, repetitions: int = 5) -> None:
    values = (
        (0.2, 0.6),
        (0.3, 0.5),
        (0.4, 0.4),
        (0.5, 0.3),
        (0.6, 0.2),
    )
    payload = {
        "run_id": RUN_ID,
        "complete": repetitions == 5,
        "repetitions": [
            {
                "repetition": index,
                "primary": {
                    "scores": [],
                    "task_rewards": {
                        "validation-risk": risk,
                        "validation-rates": rates,
                        "unselected": 1.0,
                    },
                    "domain_scores": {},
                    "task_mean": 0.0,
                    "overall": 0.0,
                },
                "diagnostic": {
                    "scores": [],
                    "task_rewards": {"copy": 0.0},
                    "domain_scores": {"risk_credit": 0.0},
                    "task_mean": 0.0,
                    "overall": 0.0,
                },
            }
            for index, (risk, rates) in enumerate(values[:repetitions], start=1)
        ],
        "aggregate": {
            "expected_repetitions": 5,
            "completed_repetitions": repetitions,
            "complete": repetitions == 5,
        },
    }
    run_dir.mkdir(parents=True)
    (run_dir / "result.json").write_text(json.dumps(payload, indent=2) + "\n")


def _validation_tasks():
    return (
        SimpleNamespace(task_id="validation-risk", domain="risk_credit"),
        SimpleNamespace(task_id="validation-rates", domain="rates_fx_macro"),
    )


def test_calibration_recomputes_five_validation_domain_macros(
    tmp_path: Path,
) -> None:
    from qea.qfbench_validation import calibration_from_baseline_run

    run_dir = tmp_path / RUN_ID
    _write_baseline_result(run_dir)

    calibration = calibration_from_baseline_run(
        run_dir,
        validation_tasks=_validation_tasks(),
        expected_run_id=RUN_ID,
    )

    assert calibration.source_run_id == RUN_ID
    assert calibration.validation_task_ids == (
        "validation-risk",
        "validation-rates",
    )
    assert calibration.repetition_scores == pytest.approx(
        (0.4, 0.4, 0.4, 0.4, 0.4)
    )
    assert calibration.mean_score == pytest.approx(0.4)
    assert calibration.tolerance == pytest.approx(0.02)


def test_calibration_rejects_nonfive_or_incomplete_baseline(tmp_path: Path) -> None:
    from qea.qfbench_validation import (
        ValidationCalibrationError,
        calibration_from_baseline_run,
    )

    run_dir = tmp_path / RUN_ID
    _write_baseline_result(run_dir, repetitions=4)

    with pytest.raises(ValidationCalibrationError, match="exactly five"):
        calibration_from_baseline_run(
            run_dir,
            validation_tasks=_validation_tasks(),
            expected_run_id=RUN_ID,
        )


def test_calibration_artifact_rejects_identity_tampering(tmp_path: Path) -> None:
    from qea.qfbench_validation import (
        ValidationCalibrationError,
        calibration_from_baseline_run,
        load_validation_calibration,
        write_validation_calibration,
    )

    run_dir = tmp_path / RUN_ID
    _write_baseline_result(run_dir)
    calibration = calibration_from_baseline_run(
        run_dir,
        validation_tasks=_validation_tasks(),
        expected_run_id=RUN_ID,
    )
    artifact = tmp_path / "calibration.json"
    write_validation_calibration(artifact, calibration)
    payload = json.loads(artifact.read_text())
    payload["tolerance"] = 0.9
    artifact.write_text(json.dumps(payload))

    with pytest.raises(ValidationCalibrationError, match="digest mismatch"):
        load_validation_calibration(artifact)


def test_written_calibration_round_trips_tuple_fields_as_json_arrays(
    tmp_path: Path,
) -> None:
    from qea.qfbench_validation import (
        calibration_from_baseline_run,
        load_validation_calibration,
        write_validation_calibration,
    )

    run_dir = tmp_path / RUN_ID
    _write_baseline_result(run_dir)
    calibration = calibration_from_baseline_run(
        run_dir,
        validation_tasks=_validation_tasks(),
        expected_run_id=RUN_ID,
    )
    artifact = tmp_path / "calibration.json"
    write_validation_calibration(artifact, calibration)

    assert load_validation_calibration(artifact) == calibration


def test_calibration_cli_writes_artifact_from_manifest_panel(
    tmp_path: Path,
) -> None:
    from qea.qfbench_validation import load_validation_calibration
    from scripts.calibrate_qfbench_validation import main

    run_dir = tmp_path / RUN_ID
    _write_baseline_result(run_dir)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "schema_version": 2,
        "evolution": {
            "validation": [
                {"task_id": "validation-risk", "domain": "risk_credit"},
                {
                    "task_id": "validation-rates",
                    "domain": "rates_fx_macro",
                },
            ]
        },
    }))
    output = tmp_path / "calibration.json"

    assert main([
        "--run-dir", str(run_dir),
        "--manifest", str(manifest),
        "--output", str(output),
    ]) == 0
    calibration = load_validation_calibration(output)
    assert calibration.source_run_id == RUN_ID
    assert calibration.validation_task_ids == (
        "validation-risk",
        "validation-rates",
    )
