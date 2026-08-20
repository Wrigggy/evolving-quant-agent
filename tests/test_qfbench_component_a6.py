import json
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _identity_fixture(tmp_path: Path):
    import scripts.run_qfbench_component_pilot as pilot

    release = tmp_path / "release"
    protocol = release / "data/qfbench/MANIFEST_A6_EXPANDED_CANARY.json"
    seed_digest = "9" * 64
    task_ids = ("target-a", "protect-a", "sentinel-a")
    _write_json(
        protocol,
        {
            "stage": "A6",
            "benchmark_commit": "fixture-commit",
            "baseline": {"seed_worker_digest": seed_digest},
            "discovery_design": {"maximum_candidate_evaluations": 3},
            "prelaunch_identity_freeze": {
                "record_path": "../identity.json"
            },
            "panel": {
                "targets": [{"task_id": "target-a"}],
                "protections": [{"task_id": "protect-a"}],
                "coverage_sentinels": [{"task_id": "sentinel-a"}],
                "task_ids": list(task_ids),
            },
        },
    )
    identity = tmp_path / "identity.json"
    source_manifest = tmp_path / "source-manifest.json"
    rootless = tmp_path / "rootless.json"
    images = tmp_path / "images.json"
    for path in (identity, source_manifest, rootless, images):
        _write_json(path, {"schema_version": 1})
    args = SimpleNamespace(
        run_id="qfbench-a6-seed-fixture",
        checkpoint_prefix="a6-seed",
        a6_run_kind="seed",
        a6_manifest=protocol,
        a6_prelaunch_identity=identity,
        a6_source_release_root=release,
        a6_source_release_manifest=source_manifest,
        rootless_config=rootless,
        rootless_image_set_manifest=images,
    )
    config = SimpleNamespace(
        public_root=tmp_path / "public",
        trusted_root=tmp_path / "trusted",
        upstream_base_url="https://example.invalid/v1",
        allowed_path_prefix="/v1",
        allowed_model="provider/model",
        required_provider="provider",
        scheduler_epoch="a6-epoch",
    )
    arm_payloads = [
        {
            "label": "seed-evidence",
            "worker_digest": seed_digest,
        }
    ]
    return pilot, release, args, config, task_ids, seed_digest, arm_payloads


def test_a6_component_static_identity_binds_full_panel_seed_and_runtime_inputs(
    tmp_path, monkeypatch
):
    (
        pilot,
        release,
        args,
        config,
        task_ids,
        seed_digest,
        arm_payloads,
    ) = _identity_fixture(tmp_path)
    monkeypatch.setattr(
        pilot,
        "validate_a6_source_release",
        lambda root, manifest: {
            "manifest_sha256": "a" * 64,
            "tree_sha256": "b" * 64,
            "member_count": 42,
        },
    )
    role_digests = iter(("c" * 64, "d" * 64))
    monkeypatch.setattr(
        pilot,
        "verify_role_root",
        lambda root, role: SimpleNamespace(manifest_sha256=next(role_digests)),
    )
    monkeypatch.setattr(pilot, "rootless_model_route_identity", lambda **kwargs: "e" * 64)

    identity = pilot._a6_component_launch_identity(
        args=args,
        config=config,
        task_ids=task_ids,
        primary_task_ids=frozenset(task_ids),
        benchmark_commit="fixture-commit",
        seed_digest=seed_digest,
        arm_payloads=arm_payloads,
        execution_root=release,
    )

    assert identity["run_kind"] == "seed"
    assert identity["effective_identity"] == {
        "rootless_config_sha256": pilot._sha256(args.rootless_config),
        "image_set_manifest_sha256": pilot._sha256(
            args.rootless_image_set_manifest
        ),
        "public_task_role_manifest_sha256": "c" * 64,
        "trusted_task_role_manifest_sha256": "d" * 64,
        "scheduler_epoch": "a6-epoch",
        "provider_route_identity_sha256": "e" * 64,
        "a6_source_release_sha256": "b" * 64,
    }


def test_a6_component_identity_fails_closed_for_missing_args_or_panel_drift(
    tmp_path, monkeypatch
):
    (
        pilot,
        release,
        args,
        config,
        task_ids,
        seed_digest,
        arm_payloads,
    ) = _identity_fixture(tmp_path)
    args.a6_run_kind = None
    for name in (
        "a6_manifest",
        "a6_prelaunch_identity",
        "a6_source_release_root",
        "a6_source_release_manifest",
    ):
        setattr(args, name, None)
    with pytest.raises(ValueError, match="A6-named"):
        pilot._a6_component_launch_identity(
            args=args,
            config=config,
            task_ids=task_ids,
            primary_task_ids=frozenset(task_ids),
            benchmark_commit="fixture-commit",
            seed_digest=seed_digest,
            arm_payloads=arm_payloads,
            execution_root=release,
        )

    (
        pilot,
        release,
        args,
        config,
        task_ids,
        seed_digest,
        arm_payloads,
    ) = _identity_fixture(tmp_path / "again")
    monkeypatch.setattr(
        pilot,
        "validate_a6_source_release",
        lambda root, manifest: {
            "manifest_sha256": "a" * 64,
            "tree_sha256": "b" * 64,
            "member_count": 42,
        },
    )
    monkeypatch.setattr(
        pilot,
        "verify_role_root",
        lambda root, role: SimpleNamespace(manifest_sha256="c" * 64),
    )
    with pytest.raises(ValueError, match="differs from the frozen full panel"):
        pilot._a6_component_launch_identity(
            args=args,
            config=config,
            task_ids=task_ids[:-1],
            primary_task_ids=frozenset(task_ids),
            benchmark_commit="fixture-commit",
            seed_digest=seed_digest,
            arm_payloads=arm_payloads,
            execution_root=release,
        )


def test_a6_component_candidate_rejects_unbound_labels_and_duplicate_workers(
    tmp_path, monkeypatch
):
    (
        pilot,
        release,
        args,
        config,
        task_ids,
        seed_digest,
        arm_payloads,
    ) = _identity_fixture(tmp_path)
    args.a6_run_kind = "candidate"
    monkeypatch.setattr(
        pilot,
        "validate_a6_source_release",
        lambda root, manifest: {
            "manifest_sha256": "a" * 64,
            "tree_sha256": "b" * 64,
            "member_count": 42,
        },
    )
    monkeypatch.setattr(
        pilot,
        "verify_role_root",
        lambda root, role: SimpleNamespace(manifest_sha256="c" * 64),
    )

    with pytest.raises(ValueError, match="does not identify R, E, or EC"):
        pilot._a6_component_launch_identity(
            args=args,
            config=config,
            task_ids=task_ids,
            primary_task_ids=frozenset(task_ids),
            benchmark_commit="fixture-commit",
            seed_digest=seed_digest,
            arm_payloads=[{"label": "candidate", "worker_digest": "1" * 64}],
            execution_root=release,
        )
    with pytest.raises(ValueError, match="duplicate worker digests"):
        pilot._a6_component_launch_identity(
            args=args,
            config=config,
            task_ids=task_ids,
            primary_task_ids=frozenset(task_ids),
            benchmark_commit="fixture-commit",
            seed_digest=seed_digest,
            arm_payloads=[
                {"label": "a6-r", "worker_digest": "1" * 64},
                {"label": "a6-e", "worker_digest": "1" * 64},
            ],
            execution_root=release,
        )


@dataclass
class _Admission:
    admitted: bool = True
    files: tuple[dict[str, object], ...] = (
        {"path": "agent.yaml", "sha256": "8" * 64, "size_bytes": 1},
    )
    checks: tuple[str, ...] = ("file_manifest", "protected_config")


def test_component_plan_normalization_matches_persisted_json_types():
    import scripts.run_qfbench_component_pilot as pilot

    normalized = pilot._canonical_json_value(
        {"admission": asdict(_Admission())}
    )

    assert normalized == {
        "admission": {
            "admitted": True,
            "files": [
                {
                    "path": "agent.yaml",
                    "sha256": "8" * 64,
                    "size_bytes": 1,
                }
            ],
            "checks": ["file_manifest", "protected_config"],
        }
    }


def test_component_activation_follows_replacement_and_counts_tool_call(tmp_path):
    import scripts.run_qfbench_component_pilot as pilot

    logical = tmp_path / "attempts" / "logical"
    replacement = tmp_path / "attempts" / "replacement"
    _write_json(
        logical / "attempt.json",
        {
            "attempt_id": "logical",
            "task_id": "dupire-local-vol",
            "checkpoint": "localvol-candidate",
        },
    )
    _write_json(
        replacement / "attempt.json",
        {
            "attempt_id": "replacement",
            "task_id": "dupire-local-vol",
            "checkpoint": "localvol-candidate+infra-replacement-02",
        },
    )
    _write_json(
        replacement / "raw-trace.jsonl",
        {
            "role": "assistant",
            "content": (
                '<ToolUse>{"input": {}, '
                '"name": "validate_surface_artifacts"}</ToolUse>'
            ),
        },
    )

    activation = pilot._activation_payload(
        tmp_path,
        "localvol-candidate",
        "validate_surface_artifacts",
    )

    assert activation["activation_count"] == 1
    assert len(activation["attempts"]) == 2
    assert activation["attempts"][1]["activated"] is True


def test_component_preflight_validates_a6_identity_before_any_evaluator_call(
    tmp_path, monkeypatch
):
    import scripts.run_qfbench_component_pilot as pilot

    task = SimpleNamespace(task_id="task-a")
    snapshot = SimpleNamespace(
        commit="fixture-commit",
        primary=SimpleNamespace(tasks=(task,)),
        diagnostic=SimpleNamespace(tasks=()),
    )
    config = SimpleNamespace(
        allowed_model="provider/model",
        required_provider="provider",
        scheduler_epoch="a6-epoch",
        worker_concurrency=1,
        verifier_concurrency=1,
    )
    state = {"evaluate_calls": 0, "validate_calls": 0, "close_calls": 0}

    class _EvaluatorBoundary(RuntimeError):
        pass

    class _Evaluator:
        def evaluate(self, **kwargs):
            state["evaluate_calls"] += 1
            raise _EvaluatorBoundary("no-call evaluator boundary")

    class _Runtime:
        evaluator = _Evaluator()
        scheduler_identity_digest = "5" * 64
        runtime_identity_digest = "6" * 64

        def close(self):
            state["close_calls"] += 1

    protocol = tmp_path / "protocol.json"
    qfbench_manifest = tmp_path / "qfbench.json"
    rootless = tmp_path / "rootless.json"
    images = tmp_path / "images.json"
    identity_record = tmp_path / "identity.json"
    source_manifest = tmp_path / "source.json"
    for path in (
        protocol,
        qfbench_manifest,
        rootless,
        images,
        identity_record,
        source_manifest,
    ):
        _write_json(path, {"schema_version": 1})
    seed = tmp_path / "seed"
    arm = tmp_path / "arm"
    seed.mkdir()
    arm.mkdir()

    monkeypatch.setattr(pilot, "load_qfbench_baseline_snapshot", lambda *a, **k: snapshot)
    monkeypatch.setattr(pilot, "hash_worker_directory", lambda path: "9" * 64)
    monkeypatch.setattr(
        pilot.AdmissionPolicy,
        "qfbench_full",
        staticmethod(lambda: object()),
    )
    monkeypatch.setattr(pilot, "admit_candidate", lambda *a, **k: _Admission())
    monkeypatch.setattr(pilot, "load_rootless_full_harness_config", lambda path: config)
    monkeypatch.setattr(
        pilot,
        "_a6_component_launch_identity",
        lambda **kwargs: {
            "frozen": {},
            "freeze_record": {
                "protocol_manifest_sha256": "1" * 64,
                "materialized_launch_identity_sha256": "2" * 64,
            },
            "protocol_manifest_path": protocol,
            "identity_record_sha256": "3" * 64,
            "source_release_manifest_sha256": "4" * 64,
            "source_release_member_count": 12,
            "run_kind": "seed",
            "effective_identity": {
                "a6_source_release_sha256": "7" * 64,
            },
        },
    )
    monkeypatch.setattr(
        pilot,
        "build_rootless_full_harness_runtime",
        lambda **kwargs: _Runtime(),
    )

    def validate(**kwargs):
        state["validate_calls"] += 1
        assert kwargs["effective_identity"]["scheduler_identity_sha256"] == "5" * 64

    monkeypatch.setattr(pilot, "validate_a6_prelaunch_identity", validate)

    base_args = [
        "--qfbench-root",
        str(tmp_path / "qfbench"),
        "--qfbench-manifest",
        str(qfbench_manifest),
        "--rootless-config",
        str(rootless),
        "--rootless-image-set-manifest",
        str(images),
        "--run-id",
        "qfbench-a6-preflight-fixture",
        "--results-dir",
        str(tmp_path / "runs"),
        "--seed-worker",
        str(seed),
        "--arm",
        f"seed-evidence={arm}",
        "--task-id",
        "task-a",
        "--a6-run-kind",
        "seed",
        "--a6-manifest",
        str(protocol),
        "--a6-prelaunch-identity",
        str(identity_record),
        "--a6-source-release-root",
        str(tmp_path),
        "--a6-source-release-manifest",
        str(source_manifest),
    ]

    result = pilot.main([*base_args, "--preflight-only"])

    assert result == 0
    assert state == {"evaluate_calls": 0, "validate_calls": 1, "close_calls": 1}
    report = json.loads(
        (
            tmp_path
            / "runs/qfbench-a6-preflight-fixture/pilot-preflight.json"
        ).read_text()
    )
    assert report["model_request_count"] == 0
    assert report["a6_prelaunch_identity_validated"] is True
    marker = (
        tmp_path
        / "runs/qfbench-a6-preflight-fixture/pilot-model-boundary.json"
    )
    assert not marker.exists()

    with pytest.raises(_EvaluatorBoundary, match="no-call evaluator boundary"):
        pilot.main([*base_args, "--approve-external-run"])

    assert state == {"evaluate_calls": 1, "validate_calls": 2, "close_calls": 2}
    assert marker.is_file()
    assert marker.stat().st_mode & 0o777 == 0o600

    with pytest.raises(ValueError, match="already claimed"):
        pilot.main([*base_args, "--approve-external-run"])
    assert state == {"evaluate_calls": 1, "validate_calls": 2, "close_calls": 2}

    plan_path = (
        tmp_path / "runs/qfbench-a6-preflight-fixture/pilot-plan.json"
    )
    canonical_plan = plan_path.read_bytes()
    with pytest.raises(ValueError, match="existing pilot plan identity differs"):
        pilot.main(
            [
                *base_args,
                "--checkpoint-prefix",
                "drifted-checkpoint",
                "--approve-external-run",
            ]
        )

    assert state == {"evaluate_calls": 1, "validate_calls": 2, "close_calls": 2}
    assert plan_path.read_bytes() == canonical_plan


def test_component_cost_payload_uses_canonical_multi_checkpoint_lower_bound(
    tmp_path,
):
    import hashlib

    from qea.evaluation import OfficialTaskScore, TaskAttempt
    from scripts.run_qfbench_component_pilot import _cost_payload

    run_dir = tmp_path / "component-run"
    for index, checkpoint in enumerate(("component-a", "component-b")):
        attempt = TaskAttempt.create(
            run_id=run_dir.name,
            benchmark_commit="f" * 40,
            task_id=f"task-{index}",
            split="mechanism-pilot",
            checkpoint=checkpoint,
            worker_digest="e" * 64,
        )
        attempt_dir = run_dir / "attempts" / attempt.attempt_id
        _write_json(attempt_dir / "attempt.json", asdict(attempt))
        score = OfficialTaskScore(
            task_id=attempt.task_id,
            domain="derivatives",
            reward=0.0 if index else 1.0,
            diagnostic_tags=("timeout",) if index else (),
        )
        _write_json(attempt_dir / "completed-score.json", asdict(score))
        record = {
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
        payload = (json.dumps(record, sort_keys=True) + "\n").encode()
        if index == 0:
            (attempt_dir / "proxy-audit.jsonl").write_bytes(payload)
        else:
            (attempt_dir / "proxy-audit.unsealed.jsonl").write_bytes(payload)
            _write_json(
                attempt_dir / "proxy-audit.quarantined.json",
                {
                    "schema_version": 2,
                    "request_state": "quarantined",
                    "reason": "audit_download_or_validation_failed",
                    "accounting_complete": False,
                    "unsealed_audit_sha256": hashlib.sha256(payload).hexdigest(),
                    "unsealed_record_count": 1,
                },
            )

    cost = _cost_payload(
        run_dir,
        checkpoints=("component-a", "component-b"),
        expected_attempts=2,
    )

    assert cost["attempt_count"] == 2
    assert cost["request_count"] == 2
    assert cost["completed_request_count"] == 2
    assert cost["total_tokens"] == 30
    assert cost["provider_cost_usd"] == "0.002"
    assert cost["cost_complete"] is False
    assert cost["provider_cost_is_lower_bound"] is True
    assert cost["unreconciled_attempt_count"] == 1
    assert cost["checkpoints"] == ["component-a", "component-b"]
