import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import pytest

from qea.qfbench_a6 import materialized_a6_launch_identity_digest
from qea.evaluation import OfficialTaskScore, TaskAttempt
from qea.qfbench_baseline import audit_fixed_checkpoint_proxy_costs
from scripts.build_qfbench_a6_evidence import _a6_seed_identity


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _fixture(tmp_path: Path):
    required_fields = [
        "protocol_manifest_sha256",
        "rootless_config_sha256",
        "image_set_manifest_sha256",
        "public_task_role_manifest_sha256",
        "trusted_task_role_manifest_sha256",
        "scheduler_epoch",
        "scheduler_identity_sha256",
        "provider_route_identity_sha256",
        "a6_source_release_sha256",
        "materialized_launch_identity_sha256",
    ]
    manifest_path = tmp_path / "MANIFEST_A6_EXPANDED_CANARY.json"
    manifest = {
        "stage": "A6",
        "benchmark_commit": "fixture-commit",
        "frozen_runtime": {
            "model": "provider/model",
            "provider": "provider",
        },
        "panel": {"task_ids": ["task-a", "task-b"]},
        "prelaunch_identity_freeze": {
            "schema_version": 1,
            "required_before_any_a6_model_call": True,
            "required_record_fields": required_fields,
        },
    }
    _write_json(manifest_path, manifest)
    record = {
        "schema_version": 1,
        "stage": "A6",
        "status": "materialized",
        "protocol_manifest_sha256": hashlib.sha256(
            manifest_path.read_bytes()
        ).hexdigest(),
        "rootless_config_sha256": "1" * 64,
        "image_set_manifest_sha256": "2" * 64,
        "public_task_role_manifest_sha256": "3" * 64,
        "trusted_task_role_manifest_sha256": "4" * 64,
        "scheduler_epoch": "a6-epoch",
        "scheduler_identity_sha256": "5" * 64,
        "provider_route_identity_sha256": "6" * 64,
        "a6_source_release_sha256": "7" * 64,
    }
    record["materialized_launch_identity_sha256"] = (
        materialized_a6_launch_identity_digest(record)
    )
    identity_path = tmp_path / "A6_PRELAUNCH_IDENTITY.json"
    _write_json(identity_path, record)
    record_sha256 = hashlib.sha256(identity_path.read_bytes()).hexdigest()
    metadata = {
        "run_kind": "seed",
        "identity_record_sha256": record_sha256,
        "materialized_launch_identity_sha256": record[
            "materialized_launch_identity_sha256"
        ],
        "protocol_manifest_sha256": record["protocol_manifest_sha256"],
        "source_release_tree_sha256": record["a6_source_release_sha256"],
    }
    evidence_run = tmp_path / "seed-run"
    _write_json(
        evidence_run / "pilot-plan.json",
        {
            "benchmark_commit": "fixture-commit",
            "task_ids": ["task-a", "task-b"],
            "rootless_config_sha256": record["rootless_config_sha256"],
            "image_set_sha256": record["image_set_manifest_sha256"],
            "effective_runtime": {
                "allowed_model": "provider/model",
                "required_provider": "provider",
                "scheduler_epoch": "a6-epoch",
            },
            "a6_prelaunch_identity": metadata,
        },
    )
    checkpoint = "a6-seed-evidence"
    for index, task_id in enumerate(("task-a", "task-b")):
        attempt = TaskAttempt.create(
            run_id="seed-run",
            benchmark_commit="0" * 40,
            task_id=task_id,
            split="mechanism-pilot",
            checkpoint=checkpoint,
            worker_digest="f" * 64,
        )
        attempt_dir = evidence_run / "attempts" / attempt.attempt_id
        _write_json(attempt_dir / "attempt.json", asdict(attempt))
        _write_json(
            attempt_dir / "completed-score.json",
            asdict(
                OfficialTaskScore(
                    task_id=task_id,
                    domain="derivatives",
                    reward=1.0,
                )
            ),
        )
        audit = {
            "schema_version": 1,
            "request_identity_sha256": str(index + 1) * 64,
            "model": "provider/model",
            "started_at": "2026-08-09T00:00:00+00:00",
            "finished_at": "2026-08-09T00:00:01+00:00",
            "latency_ms": 1000,
            "request_state": "completed",
            "upstream_status_code": 200,
            "provider_request_id": f"provider-request-{index}",
            "input_tokens": 10,
            "output_tokens": 5,
            "total_tokens": 15,
            "provider_cost_usd": 0.001,
            "failure_class": None,
        }
        (attempt_dir / "proxy-audit.jsonl").write_text(
            json.dumps(audit, sort_keys=True) + "\n"
        )
    from scripts.run_qfbench_component_pilot import _cost_payload

    cost = _cost_payload(
        evidence_run,
        expected_attempts=2,
        checkpoints=(checkpoint,),
    )
    _write_json(
        evidence_run / "pilot-report.json",
        {
            "status": "complete",
            "task_ids": ["task-a", "task-b"],
            "activations": {
                "seed-evidence": {"checkpoint": checkpoint},
            },
            "cost": cost,
            "a6_prelaunch_identity": {
                **metadata,
                "scheduler_identity_sha256": record[
                    "scheduler_identity_sha256"
                ],
                "validated_before_first_evaluator_call": True,
            },
        },
    )
    return manifest_path, manifest, identity_path, evidence_run, record


def test_a6_seed_evidence_is_bound_to_completed_materialized_launch(tmp_path):
    manifest_path, manifest, identity_path, evidence_run, record = _fixture(
        tmp_path
    )

    binding = _a6_seed_identity(
        manifest_path=manifest_path,
        manifest=manifest,
        evidence_run=evidence_run,
        identity_path=identity_path,
    )

    assert binding == {
        "seed_launch_identity_sha256": record[
            "materialized_launch_identity_sha256"
        ],
        "seed_identity_record_sha256": hashlib.sha256(
            identity_path.read_bytes()
        ).hexdigest(),
    }


def test_a6_seed_evidence_rejects_scheduler_or_validation_drift(tmp_path):
    manifest_path, manifest, identity_path, evidence_run, _ = _fixture(tmp_path)
    report_path = evidence_run / "pilot-report.json"
    report = json.loads(report_path.read_text())
    report["a6_prelaunch_identity"]["scheduler_identity_sha256"] = "8" * 64
    _write_json(report_path, report)

    with pytest.raises(ValueError, match="scheduler_identity_sha256"):
        _a6_seed_identity(
            manifest_path=manifest_path,
            manifest=manifest,
            evidence_run=evidence_run,
            identity_path=identity_path,
        )

    manifest_path, manifest, identity_path, evidence_run, _ = _fixture(
        tmp_path / "unvalidated"
    )
    report_path = evidence_run / "pilot-report.json"
    report = json.loads(report_path.read_text())
    report["a6_prelaunch_identity"][
        "validated_before_first_evaluator_call"
    ] = False
    _write_json(report_path, report)
    with pytest.raises(ValueError, match="not validated before evaluation"):
        _a6_seed_identity(
            manifest_path=manifest_path,
            manifest=manifest,
            evidence_run=evidence_run,
            identity_path=identity_path,
        )


def test_a6_seed_evidence_rejects_canonical_timeout_cost_lower_bound(tmp_path):
    manifest_path, manifest, identity_path, evidence_run, _ = _fixture(tmp_path)
    timeout_dir = next(
        path.parent
        for path in (evidence_run / "attempts").glob("*/attempt.json")
        if json.loads(path.read_text())["task_id"] == "task-b"
    )
    (timeout_dir / "proxy-audit.jsonl").unlink()
    _write_json(
        timeout_dir / "completed-score.json",
        asdict(
            OfficialTaskScore(
                task_id="task-b",
                domain="derivatives",
                reward=0.0,
                diagnostic_tags=("timeout",),
            )
        ),
    )
    _write_json(
        timeout_dir / "proxy-audit.quarantined.json",
        {
            "schema_version": 1,
            "request_state": "quarantined",
            "reason": "audit_download_or_validation_failed",
        },
    )
    report_path = evidence_run / "pilot-report.json"
    report = json.loads(report_path.read_text())
    report["cost"] = audit_fixed_checkpoint_proxy_costs(
        evidence_run,
        expected_attempts=2,
        checkpoint="a6-seed-evidence",
        split="mechanism-pilot",
    )
    _write_json(report_path, report)

    with pytest.raises(ValueError, match="canonical request/token/cost ledger"):
        _a6_seed_identity(
            manifest_path=manifest_path,
            manifest=manifest,
            evidence_run=evidence_run,
            identity_path=identity_path,
        )


def test_a6_seed_evidence_rejects_canonical_not_accepted_request(tmp_path):
    manifest_path, manifest, identity_path, evidence_run, _ = _fixture(tmp_path)
    attempt_dir = next(
        path.parent
        for path in (evidence_run / "attempts").glob("*/attempt.json")
        if json.loads(path.read_text())["task_id"] == "task-b"
    )
    audit_path = attempt_dir / "proxy-audit.jsonl"
    record = json.loads(audit_path.read_text())
    record.update({
        "request_state": "not_accepted",
        "upstream_status_code": None,
        "provider_request_id": None,
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
        "provider_cost_usd": None,
        "failure_class": "pre_accept_transport",
    })
    audit_path.write_text(json.dumps(record, sort_keys=True) + "\n")
    report_path = evidence_run / "pilot-report.json"
    report = json.loads(report_path.read_text())
    report["cost"] = audit_fixed_checkpoint_proxy_costs(
        evidence_run,
        expected_attempts=2,
        checkpoint="a6-seed-evidence",
        split="mechanism-pilot",
    )
    assert report["cost"]["cost_complete"] is True
    assert report["cost"]["request_count"] == 2
    assert report["cost"]["completed_request_count"] == 1
    _write_json(report_path, report)

    with pytest.raises(ValueError, match="canonical request/token/cost ledger"):
        _a6_seed_identity(
            manifest_path=manifest_path,
            manifest=manifest,
            evidence_run=evidence_run,
            identity_path=identity_path,
        )
