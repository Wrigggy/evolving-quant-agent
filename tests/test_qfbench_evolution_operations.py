import copy
import hashlib
import json

import pytest


MODEL = "deepseek/deepseek-v4-flash-0731"
PROVIDER = "deepseek"
RUN_ID = "qfbench-tvt-complete"


def _tier_panel(
    workers: int,
    *,
    overlap: int | None = None,
    available_memory_mb: int = 20_000,
) -> dict:
    return {
        "schema_version": 1,
        "run_id": f"tier-{workers}w3v",
        "executor": "rootless-docker",
        "formal_scoring_eligible": True,
        "worker_concurrency": workers,
        "verifier_concurrency": 3,
        "worker_overlap": workers if overlap is None else overlap,
        "worker_launch_interval_seconds": 2,
        "lease_timeout_seconds": 6000,
        "model_route": {
            "upstream_base_url": "https://openrouter.ai/api/v1",
            "allowed_path_prefix": "/v1",
            "model": MODEL,
            "provider": PROVIDER,
            "fallbacks_allowed": False,
        },
        "scheduler_identity_digest": f"{workers % 10}" * 64,
        "failure_counts": {
            "resource_lease_timeout": 0,
            "provider": 0,
            "http_429": 0,
            "replay": 0,
            "coordinator_crash": 0,
        },
        "lifecycle_audit": {
            "cleaned_up": True,
            "verifier_networkless": True,
            "worker_proxy_only": True,
        },
        "host_samples": [
            {
                "load_1m": 31.0,
                "max_load_1m": 64.0,
                "available_memory_mb": available_memory_mb,
            }
        ],
        "residual_resource_count": 0,
    }


def test_tier_acceptance_selects_highest_observed_safe_tier() -> None:
    from scripts.accept_qfbench_evolution_tier import accept_tiers

    accepted = accept_tiers(
        (
            _tier_panel(20, overlap=18),
            _tier_panel(16, available_memory_mb=18_000),
            _tier_panel(12),
        )
    )

    assert accepted.worker_concurrency == 16
    assert accepted.verifier_concurrency == 3
    assert accepted.digest == accepted.to_dict()["digest"]


def test_tier_acceptance_roundtrip_rejects_digest_drift(tmp_path) -> None:
    from scripts.accept_qfbench_evolution_tier import (
        EvolutionTierError,
        accept_tiers,
        load_tier_acceptance,
        write_tier_acceptance,
    )

    accepted = accept_tiers((_tier_panel(12),))
    path = tmp_path / "tier-acceptance.json"
    write_tier_acceptance(path, accepted)
    assert load_tier_acceptance(path) == accepted

    payload = json.loads(path.read_text())
    payload["worker_concurrency"] = 16
    path.write_text(json.dumps(payload))
    with pytest.raises(EvolutionTierError, match="digest"):
        load_tier_acceptance(path)


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        (lambda panel: panel["model_route"].update({"provider": "other"}), "provider"),
        (lambda panel: panel.update({"residual_resource_count": 1}), "residual"),
        (
            lambda panel: panel["host_samples"][0].update(
                {"available_memory_mb": 16_383}
            ),
            "memory",
        ),
    ),
)
def test_tier_acceptance_fails_closed_without_any_safe_tier(
    mutation, message
) -> None:
    from scripts.accept_qfbench_evolution_tier import (
        EvolutionTierError,
        accept_tiers,
    )

    panels = [_tier_panel(workers) for workers in (20, 16, 12)]
    for panel in panels:
        mutation(panel)
    with pytest.raises(EvolutionTierError, match=message):
        accept_tiers(panels)


def _entries(prefix: str, count: int) -> list[dict]:
    return [
        {
            "task_id": f"{prefix}-{index:02d}",
            "domain": f"domain-{index % 3}",
            "lineage": f"{prefix}_lineage_{index:02d}",
        }
        for index in range(count)
    ]


def _summary(entries: list[dict], reward: float) -> dict:
    scores = [
        {
            "task_id": entry["task_id"],
            "domain": entry["domain"],
            "reward": reward,
            "diagnostic_tags": [],
            "verifier_exit_code": 0,
            "tests_passed": 1,
            "tests_failed": 0,
            "log_uri": None,
        }
        for entry in entries
    ]
    domains = sorted({entry["domain"] for entry in entries})
    return {
        "scores": scores,
        "task_rewards": {entry["task_id"]: reward for entry in entries},
        "domain_scores": {domain: reward for domain in domains},
        "task_mean": reward,
        "overall": reward,
    }


def _complete_payloads() -> tuple[dict, dict, dict, dict, dict, tuple[dict, ...]]:
    from types import SimpleNamespace

    from qea.loop_benchmark import _tvt_task_manifest_digest
    from qea.qfbench_validation import calibrate_validation_tolerance
    from qea.rootless_full_harness import rootless_model_route_identity
    from scripts.accept_qfbench_evolution_tier import accept_tiers

    train = _entries("train", 30)
    validation = _entries("validation", 15)
    test = _entries("test", 32)
    diagnostic = _entries("diagnostic", 8)
    manifest = {
        "schema_version": 2,
        "commit": "0" * 40,
        "copy_oracle_tasks": [entry["task_id"] for entry in diagnostic],
        "evolution": {
            "train": train,
            "validation": validation,
            "test": test,
            "diagnostic": diagnostic,
        },
    }
    calibration = calibrate_validation_tolerance(
        run_id="baseline-five",
        repetition_scores=(0.5, 0.5, 0.5, 0.5, 0.5),
        validation_task_ids=(entry["task_id"] for entry in validation),
        source_result_sha256="c" * 64,
    ).to_dict()
    tier = accept_tiers((_tier_panel(16),)).to_dict()
    panels = {
        name: tuple(SimpleNamespace(**entry) for entry in entries)
        for name, entries in (
            ("train", train),
            ("validation", validation),
            ("test", test),
            ("diagnostic", diagnostic),
        )
    }
    identity = {
        "protocol": "train-validation-test-v1",
        "benchmark_commit": manifest["commit"],
        "task_manifest_digest": _tvt_task_manifest_digest(
            manifest["commit"], **panels
        ),
        "model_identity": rootless_model_route_identity(
            upstream_base_url=tier["upstream_base_url"],
            allowed_path_prefix=tier["allowed_path_prefix"],
            allowed_model=tier["model"],
            required_provider=tier["provider"],
        ),
        "scheduler_identity_digest": tier["scheduler_identity_digest"],
        "worker_concurrency": 16,
        "verifier_concurrency": 3,
        "validation_noise_tolerance": 0.02,
        "validation_calibration_digest": calibration["digest"],
        "validation_calibration_source_run_id": calibration["source_run_id"],
    }
    records = [
        {
            "iteration": iteration,
            "kept": iteration in {2, 5, 9},
            "reason": "gain" if iteration in {2, 5, 9} else "confirm_failed",
        }
        for iteration in range(1, 11)
    ]
    validation_records = [
        {
            "iteration": iteration,
            "incumbent_before": _summary(validation, 0.5),
            "candidate": _summary(validation, 0.5),
            "margin": 0.0,
            "tolerance": 0.02,
            "confirmed": True,
        }
        for iteration in range(1, 11)
    ]
    result = {
        "schema_version": 3,
        "run_id": RUN_ID,
        "identity": identity,
        "records": records,
        "optimize_final": _summary(train, 0.6),
        "validation_seed": _summary(validation, 0.5),
        "validation_final": _summary(validation, 0.5),
        "validation_records": validation_records,
        "test_seed": _summary(test, 0.4),
        "test_final": _summary(test, 0.55),
        "diagnostic_seed": _summary(diagnostic, 0.2),
        "diagnostic_final": _summary(diagnostic, 0.3),
    }
    resume = {
        "schema_version": 3,
        "run_id": RUN_ID,
        "n_iters": 10,
        "benchmark_commit": manifest["commit"],
        "identity": identity,
        "phase": "complete",
        "records": records,
        "seed_optimize": _summary(train, 0.4),
        "validation_records": validation_records,
    }
    attempts = []

    def add(split: str, checkpoint: str, entries: list[dict]) -> None:
        for entry in entries:
            logical = f"{split}\0{checkpoint}\0{entry['task_id']}"
            attempts.append(
                {
                    "attempt_id": hashlib.sha256(logical.encode()).hexdigest(),
                    "run_id": RUN_ID,
                    "benchmark_commit": manifest["commit"],
                    "split": split,
                    "checkpoint": checkpoint,
                    "task_id": entry["task_id"],
                    "score": {
                        "task_id": entry["task_id"],
                        "domain": entry["domain"],
                        "reward": 0.5,
                        "diagnostic_tags": [],
                    },
                    "provider_ok": True,
                    "provider_request_identities": [
                        hashlib.sha256((logical + "request").encode()).hexdigest()
                    ],
                    "worker_cleaned": True,
                    "worker_proxy_only": True,
                    "verifier_cleaned": True,
                    "verifier_networkless": True,
                    "network_cleaned": True,
                }
            )

    add("optimize", "seed-optimize", train)
    add("validation", "seed-validation", validation)
    add("test", "seed-test", test)
    add("diagnostic", "seed-diagnostic", diagnostic)
    for iteration in range(1, 11):
        add("optimize", f"iteration-{iteration}-candidate", train)
        add("validation", f"iteration-{iteration}-validation", validation)
    add("test", "final-test", test)
    add("diagnostic", "final-diagnostic", diagnostic)
    return result, resume, manifest, calibration, tier, tuple(attempts)


def test_complete_audit_reconciles_575_and_separates_diagnostic() -> None:
    from scripts.audit_qfbench_tvt_evolution import audit_evolution_payloads

    result, resume, manifest, calibration, tier, attempts = _complete_payloads()
    audit = audit_evolution_payloads(
        result=result,
        resume=resume,
        manifest=manifest,
        calibration=calibration,
        tier_acceptance=tier,
        attempts=attempts,
        mirrored_attempt_ids={attempt["attempt_id"] for attempt in attempts},
    )

    assert audit["passed"] is True
    assert audit["attempts"]["total"] == 575
    assert audit["primary_test"]["task_count"] == 32
    assert audit["primary_test"]["overall_delta"] == pytest.approx(0.15)
    assert audit["diagnostic_test"]["task_count"] == 8
    assert audit["firewall"]["passed"] is True
    assert len(audit["selection"]["iterations"]) == 10


@pytest.mark.parametrize(
    ("corruption", "message"),
    (
        ("missing_attempt", "575"),
        ("diagnostic_in_primary", "test"),
        ("provider_replay", "replay"),
        ("verifier_network", "verifier"),
        ("mirror_missing", "mirror"),
        ("calibration_drift", "calibration"),
    ),
)
def test_evolution_audit_fails_closed(corruption: str, message: str) -> None:
    from scripts.audit_qfbench_tvt_evolution import (
        EvolutionAuditError,
        audit_evolution_payloads,
    )

    result, resume, manifest, calibration, tier, attempts = _complete_payloads()
    attempts = list(copy.deepcopy(attempts))
    mirrored = {attempt["attempt_id"] for attempt in attempts}
    if corruption == "missing_attempt":
        attempts.pop()
    elif corruption == "diagnostic_in_primary":
        result["test_final"]["scores"][0]["task_id"] = "diagnostic-00"
    elif corruption == "provider_replay":
        attempts[0]["provider_request_identities"] *= 2
    elif corruption == "verifier_network":
        attempts[0]["verifier_networkless"] = False
    elif corruption == "mirror_missing":
        mirrored.remove(attempts[0]["attempt_id"])
    elif corruption == "calibration_drift":
        calibration["digest"] = "f" * 64
    else:  # pragma: no cover
        raise AssertionError(corruption)

    with pytest.raises(EvolutionAuditError, match=message):
        audit_evolution_payloads(
            result=result,
            resume=resume,
            manifest=manifest,
            calibration=calibration,
            tier_acceptance=tier,
            attempts=attempts,
            mirrored_attempt_ids=mirrored,
        )
