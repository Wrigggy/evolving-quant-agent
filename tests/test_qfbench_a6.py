import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import pytest

from qea.benchmarks.qfbench import git_blob_oid
from qea.evaluation import OfficialTaskScore, TaskAttempt
from qea.public_contract_evidence import (
    PublicContractEvidenceError,
    build_public_contract_index,
    load_public_contract_clause,
    public_contract_source_identity,
    split_public_contract,
    validate_public_contract_index,
)
from qea.qfbench_a6 import (
    A6PanelError,
    materialized_a6_launch_identity_digest,
    validate_a6_evidence_contract,
    validate_a6_prelaunch_identity,
    validate_frozen_a6_panel,
)
from qea.qfbench_baseline import audit_fixed_checkpoint_proxy_costs
from qea.worker_identity import hash_worker_directory


_FIXTURE_COMMIT = "f" * 40


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")


def _write_public_role_manifest(root, *, commit=_FIXTURE_COMMIT):
    task_ids = sorted(
        path.name for path in (root / "tasks").iterdir() if path.is_dir()
    )
    records = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if not path.is_file() or relative in {
            "MANIFEST.json",
            ".qfbench-revision",
            ".qfbench-sparse-tasks.json",
            ".qfbench-cache",
        }:
            continue
        payload = path.read_bytes()
        records.append(
            {
                "path": relative,
                "git_blob_oid": git_blob_oid(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size_bytes": len(payload),
            }
        )
    _write_json(
        root / "MANIFEST.json",
        {
            "schema_version": 1,
            "role": "public",
            "repository_url": "https://example.invalid/qfbench.git",
            "commit": commit,
            "task_ids": task_ids,
            "files": records,
        },
    )
    (root / ".qfbench-revision").write_text(commit + "\n")


def _baseline_and_evolution():
    task_domains = {
        "target-a": "rates",
        "target-b": "data",
        "protect-a": "risk",
        "protect-b": "derivatives",
        "sentinel-a": "crypto",
        "sentinel-b": "macro",
    }
    repetitions = []
    sentinel_rewards = {
        "sentinel-a": [1, 1, 1, 1, 0],
        "sentinel-b": [1, 0, 1, 0, 1],
    }
    for index in range(5):
        scores = []
        for task_id in task_domains:
            if task_id.startswith("target"):
                reward = 0.0
                passed, failed = 1, 1
            elif task_id.startswith("protect"):
                reward = 1.0
                passed, failed = 2, 0
            else:
                reward = float(sentinel_rewards[task_id][index])
                passed, failed = ((2, 0) if reward else (1, 1))
            scores.append(
                {
                    "task_id": task_id,
                    "reward": reward,
                    "tests_passed": passed,
                    "tests_failed": failed,
                    "verifier_exit_code": 0,
                    "diagnostic_tags": [] if reward else ["tests_failed"],
                }
            )
        repetitions.append({"repetition": index + 1, "primary": {"scores": scores}})
    baseline = {
        "run_id": "baseline-fixture",
        "complete": True,
        "repetitions": repetitions,
    }
    evolution = {
        "commit": _FIXTURE_COMMIT,
        "evolution": {
            "train": [
                {"task_id": task_id, "domain": domain}
                for task_id, domain in task_domains.items()
            ],
            "validation": [{"task_id": "held-out", "domain": "risk"}],
            "test": [],
        },
    }
    panel = {
        "targets": [
            {"task_id": "target-a", "domain": task_domains["target-a"]},
            {"task_id": "target-b", "domain": task_domains["target-b"]},
        ],
        "protections": [
            {"task_id": "protect-a", "domain": task_domains["protect-a"]},
            {"task_id": "protect-b", "domain": task_domains["protect-b"]},
        ],
        "sentinels": [
            {"task_id": "sentinel-a", "domain": task_domains["sentinel-a"]},
            {"task_id": "sentinel-b", "domain": task_domains["sentinel-b"]},
        ],
        "task_ids": list(task_domains),
    }
    return baseline, evolution, panel


def _candidate_advancement_thresholds():
    return {
        "false_act_allowed": False,
        "unsupported_semantic_leap_in_selected_act_allowed": False,
        "arm_specific_act_gate_must_hold": True,
        "minimum_interpretable_stable_five_domain_macro_delta": 0.1,
        "minimum_positive_target_tasks": 2,
        "maximum_strict_protection_regressions": 0,
        "component_specific_prediction_must_hold": True,
        "volatile_sentinels_count_toward_protection_gate": False,
        "volatile_sentinels_count_toward_stable_domain_gate": False,
    }


def test_public_contract_split_is_deterministic_and_covers_every_nonblank_line():
    instruction = (
        "# Outputs\n\n"
        "Create the requested artifacts.\n"
        "Continue the same paragraph.\n\n"
        "- result.json must contain `value`.\n"
        "  Use a number.\n"
        "- summary.csv must have two columns.\n\n"
        "```json\n"
        '{"value": 1}\n'
        "\n"
        "```\n"
    )

    first = split_public_contract(task_id="task-a", instruction=instruction)
    second = split_public_contract(task_id="task-a", instruction=instruction)

    assert first == second
    assert [value.kind for value in first] == [
        "heading",
        "paragraph",
        "list_item",
        "list_item",
        "code_block",
    ]
    assert first[2].heading_path == ("Outputs",)
    assert first[2].clause_id == "task-a#c0003"
    covered = {
        line
        for clause in first
        for line in range(clause.start_line, clause.end_line + 1)
        if instruction.splitlines()[line - 1].strip()
    }
    expected = {
        line
        for line, text in enumerate(instruction.splitlines(), start=1)
        if text.strip()
    }
    assert covered == expected


def test_public_contract_index_copies_only_named_exact_public_instructions(tmp_path):
    source = tmp_path / "qfbench"
    source.mkdir()
    for task_id in ("task-a", "task-b", "held-out"):
        task = source / "tasks" / task_id
        task.mkdir(parents=True)
        (task / "instruction.md").write_bytes(
            f"# {task_id}\n\nWrite result.json.\n".encode()
        )
        (task / "public-data.txt").write_text("PUBLIC INPUT\n")
    _write_public_role_manifest(source)
    destination = tmp_path / "evidence/contracts"

    report = build_public_contract_index(
        qfbench_root=source,
        task_ids=("task-a", "task-b"),
        destination=destination,
        benchmark_commit=_FIXTURE_COMMIT,
    )

    assert report["task_ids"] == ["task-a", "task-b"]
    assert not (destination / "held-out").exists()
    assert not any(path.name == "public-data.txt" for path in destination.rglob("*"))
    assert report["source_identity"][
        "public_task_role_manifest_sha256"
    ] == hashlib.sha256((source / "MANIFEST.json").read_bytes()).hexdigest()
    assert (destination / "task-a/instruction.md").read_bytes() == (
        source / "tasks/task-a/instruction.md"
    ).read_bytes()
    clause, paths = load_public_contract_clause(
        evidence_root=tmp_path / "evidence",
        task_id="task-a",
        clause_id="task-a#c0002",
    )
    assert clause["text"] == "Write result.json."
    assert paths == (
        "contracts/task-a/clauses.json",
        "contracts/task-a/instruction.md",
    )
    validated = validate_public_contract_index(
        evidence_root=tmp_path / "evidence",
        public_task_root=source,
        task_ids=("task-a", "task-b"),
        benchmark_commit=_FIXTURE_COMMIT,
    )
    assert validated["task_ids"] == ["task-a", "task-b"]
    with pytest.raises(PublicContractEvidenceError, match="unsafe task ID"):
        load_public_contract_clause(
            evidence_root=tmp_path / "evidence",
            task_id="../task-a",
            clause_id="../task-a#c0002",
        )

    pinned_instruction = source / "tasks/task-a/instruction.md"
    pinned_instruction_bytes = pinned_instruction.read_bytes()
    pinned_instruction.write_bytes(b"# forged\n\nSelf-consistent substitute.\n")
    with pytest.raises(PublicContractEvidenceError, match="role root is invalid"):
        validate_public_contract_index(
            evidence_root=tmp_path / "evidence",
            public_task_root=source,
            task_ids=("task-a", "task-b"),
            benchmark_commit=_FIXTURE_COMMIT,
        )
    pinned_instruction.write_bytes(pinned_instruction_bytes)

    manifest_path = source / "MANIFEST.json"
    pinned_manifest_bytes = manifest_path.read_bytes()
    replaced_manifest = json.loads(pinned_manifest_bytes)
    replaced_manifest["repository_url"] = "https://example.invalid/replaced.git"
    _write_json(manifest_path, replaced_manifest)
    with pytest.raises(PublicContractEvidenceError, match="source identity differs"):
        validate_public_contract_index(
            evidence_root=tmp_path / "evidence",
            public_task_root=source,
            task_ids=("task-a", "task-b"),
            benchmark_commit=_FIXTURE_COMMIT,
        )
    manifest_path.write_bytes(pinned_manifest_bytes)

    substitute = tmp_path / "substitute-qfbench"
    for task_id in ("task-a", "task-b", "held-out"):
        task = substitute / "tasks" / task_id
        task.mkdir(parents=True)
        instruction = (
            "# substituted\n\nWrite a different result.\n"
            if task_id == "task-a"
            else f"# {task_id}\n\nWrite result.json.\n"
        )
        (task / "instruction.md").write_text(instruction)
        (task / "public-data.txt").write_text("PUBLIC INPUT\n")
    _write_public_role_manifest(substitute)
    substitute_evidence = tmp_path / "substitute-evidence"
    build_public_contract_index(
        qfbench_root=substitute,
        task_ids=("task-a", "task-b"),
        destination=substitute_evidence / "contracts",
        benchmark_commit=_FIXTURE_COMMIT,
    )
    with pytest.raises(PublicContractEvidenceError, match="source identity differs"):
        validate_public_contract_index(
            evidence_root=substitute_evidence,
            public_task_root=source,
            task_ids=("task-a", "task-b"),
            benchmark_commit=_FIXTURE_COMMIT,
        )

    index_path = tmp_path / "evidence/contracts/index.json"
    drifted_index = json.loads(index_path.read_text())
    drifted_index["task_ids"] = ["task-b", "task-a"]
    _write_json(index_path, drifted_index)
    with pytest.raises(PublicContractEvidenceError, match="identity differs"):
        validate_public_contract_index(
            evidence_root=tmp_path / "evidence",
            public_task_root=source,
            task_ids=("task-a", "task-b"),
            benchmark_commit=_FIXTURE_COMMIT,
        )

    (source / ".qfbench-revision").write_text("0" * 40 + "\n")
    with pytest.raises(PublicContractEvidenceError, match="revision differs"):
        build_public_contract_index(
            qfbench_root=source,
            task_ids=("task-a",),
            destination=tmp_path / "different",
            benchmark_commit=_FIXTURE_COMMIT,
        )


def test_a6_panel_keeps_volatile_sentinels_out_of_strict_protections():
    baseline, evolution, frozen = _baseline_and_evolution()

    panel = validate_frozen_a6_panel(
        frozen=frozen,
        baseline_result=baseline,
        evolution_manifest=evolution,
    )

    assert [item.task_id for item in panel.targets] == ["target-a", "target-b"]
    assert [item.task_id for item in panel.protections] == [
        "protect-a",
        "protect-b",
    ]
    assert [item.task_id for item in panel.sentinels] == [
        "sentinel-a",
        "sentinel-b",
    ]
    assert set(item.task_id for item in panel.sentinels).isdisjoint(
        item.task_id for item in panel.protections
    )

    invalid = json.loads(json.dumps(frozen))
    invalid["protections"].append(invalid["sentinels"].pop())
    invalid["task_ids"] = [
        item["task_id"]
        for role in ("targets", "protections", "sentinels")
        for item in invalid[role]
    ]
    with pytest.raises(A6PanelError, match="strict 5/5"):
        validate_frozen_a6_panel(
            frozen=invalid,
            baseline_result=baseline,
            evolution_manifest=evolution,
        )

    invalid_count = json.loads(json.dumps(frozen))
    invalid_count["task_count"] = len(frozen["task_ids"]) + 1
    with pytest.raises(A6PanelError, match="task_count"):
        validate_frozen_a6_panel(
            frozen=invalid_count,
            baseline_result=baseline,
            evolution_manifest=evolution,
        )


def test_a6_prelaunch_identity_is_fail_closed_and_bound_to_effective_inputs(
    tmp_path,
):
    protocol = tmp_path / "a6-protocol.json"
    protocol.write_text('{"stage":"A6"}\n')
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
    frozen = {
        "stage": "A6",
        "prelaunch_identity_freeze": {
            "schema_version": 1,
            "required_before_any_a6_model_call": True,
            "required_record_fields": required_fields,
        }
    }
    record = {
        "schema_version": 1,
        "stage": "A6",
        "status": "materialized",
        "protocol_manifest_sha256": hashlib.sha256(protocol.read_bytes()).hexdigest(),
        "rootless_config_sha256": "1" * 64,
        "image_set_manifest_sha256": "2" * 64,
        "public_task_role_manifest_sha256": "3" * 64,
        "trusted_task_role_manifest_sha256": "4" * 64,
        "scheduler_epoch": "a6-canary-epoch",
        "scheduler_identity_sha256": "5" * 64,
        "provider_route_identity_sha256": "6" * 64,
        "a6_source_release_sha256": "7" * 64,
    }
    record["materialized_launch_identity_sha256"] = (
        materialized_a6_launch_identity_digest(record)
    )
    effective = {
        field: record[field]
        for field in required_fields
        if field
        not in {
            "protocol_manifest_sha256",
            "materialized_launch_identity_sha256",
        }
    }

    assert validate_a6_prelaunch_identity(
        frozen=frozen,
        freeze_record=record,
        protocol_manifest_path=protocol,
        effective_identity=effective,
    )["materialized_launch_identity_sha256"] == record[
        "materialized_launch_identity_sha256"
    ]

    with pytest.raises(A6PanelError, match="not materialized"):
        validate_a6_prelaunch_identity(
            frozen=frozen,
            freeze_record=None,
            protocol_manifest_path=protocol,
            effective_identity=effective,
        )
    drifted = dict(effective)
    drifted["scheduler_identity_sha256"] = "8" * 64
    with pytest.raises(A6PanelError, match="effective launch identity differs"):
        validate_a6_prelaunch_identity(
            frozen=frozen,
            freeze_record=record,
            protocol_manifest_path=protocol,
            effective_identity=drifted,
        )
    protocol.write_text('{"stage":"A6","drift":true}\n')
    with pytest.raises(A6PanelError, match="protocol manifest digest differs"):
        validate_a6_prelaunch_identity(
            frozen=frozen,
            freeze_record=record,
            protocol_manifest_path=protocol,
            effective_identity=effective,
        )


def test_a6_model_visible_evidence_contract_is_exactly_manifest_bound():
    _, _, panel = _baseline_and_evolution()
    instruction = "Use only the frozen answer-free evidence."
    frozen = {
        "stage": "A6",
        "benchmark_commit": _FIXTURE_COMMIT,
        "panel": panel,
        "discovery_design": {
            "max_components": 3,
            "evolver_instruction": instruction,
            "evaluator_feedback_tier": "answer_free_public_process",
            "feedback_manifest_digest": None,
            "arms": {
                "A6-R": {
                    "decision_protocol": "failure_type_v1",
                    "success_counterfactual": "required_or_insufficient",
                    "probe_policy": "constrained_evidence_profile_v1",
                    "public_contract_index": False,
                    "semantic_comparison": "not_required",
                },
                "A6-E": {
                    "decision_protocol": "failure_type_v1",
                    "success_counterfactual": "required_or_insufficient",
                    "probe_policy": "constrained_evidence_profile_v1",
                    "public_contract_index": True,
                    "semantic_comparison": "available_not_required",
                }
            },
        },
    }
    targets = [item["task_id"] for item in panel["targets"]]
    protections = [item["task_id"] for item in panel["protections"]]
    sentinels = [item["task_id"] for item in panel["sentinels"]]
    prelaunch_identity = {
        "schema_version": 1,
        "stage": "A6",
        "status": "materialized",
        "materialized_launch_identity_sha256": "a" * 64,
    }
    identity_record_sha256 = "b" * 64
    public_contract_source = {
        "schema_version": 1,
        "protocol": "pinned_public_role_instructions_v1",
        "benchmark_commit": _FIXTURE_COMMIT,
        "task_ids": panel["task_ids"],
        "public_task_role_manifest_sha256": "c" * 64,
        "instruction_member_count": len(panel["task_ids"]),
        "instruction_members_sha256": "d" * 64,
        "members": [
            {
                "task_id": task_id,
                "source_path": f"tasks/{task_id}/instruction.md",
                "sha256": "e" * 64,
                "size_bytes": 10,
            }
            for task_id in panel["task_ids"]
        ],
    }
    contract = {
        "schema_version": 1,
        "stage": "A6",
        "purpose": "failure-type induction, probe, and decision canary",
        "mode": "indexed_full_trace",
        "train_task_ids": panel["task_ids"],
        "target_task_ids": targets,
        "protection_task_ids": protections,
        "sentinel_task_ids": sentinels,
        "held_out_feedback": False,
        "private_evaluator_feedback": False,
        "official_solution": False,
        "component_hint": None,
        "root_cause_hint": None,
        "evolver_instruction": instruction,
        "contract_arm": "A6-R",
        "decision_protocol": "failure_type_v1",
        "success_counterfactual": "required_or_insufficient",
        "probe_policy": "constrained_evidence_profile_v1",
        "max_components": 3,
        "public_contract_evidence": False,
        "public_contract_index": None,
        "public_task_role_manifest_sha256": None,
        "public_contract_source_members_sha256": None,
        "semantic_comparison": "not_required",
        "evaluator_feedback_tier": "answer_free_public_process",
        "feedback_manifest_digest": None,
        "seed_launch_identity_sha256": "a" * 64,
        "seed_identity_record_sha256": identity_record_sha256,
    }

    assert validate_a6_evidence_contract(
        frozen=frozen,
        contract=contract,
        arm="a6-r",
        prelaunch_identity=prelaunch_identity,
        identity_record_sha256=identity_record_sha256,
        public_contract_source=public_contract_source,
    )["train_task_ids"] == panel["task_ids"]

    semantic_contract = dict(contract)
    semantic_contract.update(
        {
            "contract_arm": "A6-E",
            "public_contract_evidence": True,
            "public_contract_index": "contracts/index.json",
            "public_task_role_manifest_sha256": "c" * 64,
            "public_contract_source_members_sha256": "d" * 64,
            "semantic_comparison": "available_not_required",
        }
    )
    assert validate_a6_evidence_contract(
        frozen=frozen,
        contract=semantic_contract,
        arm="A6-E",
        prelaunch_identity=prelaunch_identity,
        identity_record_sha256=identity_record_sha256,
        public_contract_source=public_contract_source,
    )["public_task_role_manifest_sha256"] == "c" * 64
    replaced_source = dict(public_contract_source)
    replaced_source["public_task_role_manifest_sha256"] = "e" * 64
    with pytest.raises(A6PanelError, match="model-visible evidence contract differs"):
        validate_a6_evidence_contract(
            frozen=frozen,
            contract=semantic_contract,
            arm="A6-E",
            prelaunch_identity=prelaunch_identity,
            identity_record_sha256=identity_record_sha256,
            public_contract_source=replaced_source,
        )

    drifted = dict(contract)
    drifted["sentinel_task_ids"] = []
    with pytest.raises(A6PanelError, match="model-visible evidence contract differs"):
        validate_a6_evidence_contract(
            frozen=frozen,
            contract=drifted,
            arm="A6-R",
            prelaunch_identity=prelaunch_identity,
            identity_record_sha256=identity_record_sha256,
            public_contract_source=public_contract_source,
        )
    unexpected_field = dict(contract)
    unexpected_field["coordinator_hint"] = "do not expose this"
    with pytest.raises(A6PanelError, match="unexpected=coordinator_hint"):
        validate_a6_evidence_contract(
            frozen=frozen,
            contract=unexpected_field,
            arm="A6-R",
            prelaunch_identity=prelaunch_identity,
            identity_record_sha256=identity_record_sha256,
            public_contract_source=public_contract_source,
        )
    missing_feedback_field = dict(contract)
    missing_feedback_field.pop("feedback_manifest_digest")
    with pytest.raises(A6PanelError, match="model-visible evidence contract differs"):
        validate_a6_evidence_contract(
            frozen=frozen,
            contract=missing_feedback_field,
            arm="A6-R",
            prelaunch_identity=prelaunch_identity,
            identity_record_sha256=identity_record_sha256,
            public_contract_source=public_contract_source,
        )


def test_discovery_runner_requires_and_binds_all_a6_static_identity_inputs(
    tmp_path, monkeypatch
):
    import scripts.run_qfbench_discovery_pilot as pilot

    release = tmp_path / "release"
    protocol = release / "data/qfbench/MANIFEST_A6_EXPANDED_CANARY.json"
    _write_json(
        protocol,
        {
            "stage": "A6",
            "benchmark_commit": _FIXTURE_COMMIT,
            "panel": {"task_ids": ["task-a"]},
            "prelaunch_identity_freeze": {
                "record_path": "../a6-identity.json"
            },
        },
    )
    freeze_record = tmp_path / "a6-identity.json"
    _write_json(freeze_record, {"stage": "A6", "status": "materialized"})
    source_manifest = tmp_path / "source-manifest.json"
    _write_json(source_manifest, {"stage": "A6"})
    rootless_config = tmp_path / "rootless.json"
    image_set = tmp_path / "images.json"
    _write_json(rootless_config, {"schema_version": 1})
    _write_json(image_set, {"schema_version": 1})

    monkeypatch.setattr(
        pilot,
        "validate_a6_source_release",
        lambda root, manifest: {
            "manifest_sha256": "a" * 64,
            "tree_sha256": "b" * 64,
            "member_count": 12,
        },
    )
    role_digests = iter(("c" * 64, "d" * 64))
    monkeypatch.setattr(
        pilot,
        "verify_role_root",
        lambda root, role: SimpleNamespace(manifest_sha256=next(role_digests)),
    )
    monkeypatch.setattr(
        pilot,
        "public_contract_source_identity",
        lambda **kwargs: {
            "schema_version": 1,
            "protocol": "pinned_public_role_instructions_v1",
            "benchmark_commit": _FIXTURE_COMMIT,
            "task_ids": ["task-a"],
            "public_task_role_manifest_sha256": "c" * 64,
            "instruction_members_sha256": "e" * 64,
        },
    )
    args = SimpleNamespace(
        arm="a6-r",
        a6_manifest=protocol,
        a6_prelaunch_identity=freeze_record,
        a6_source_release_root=release,
        a6_source_release_manifest=source_manifest,
        rootless_config=rootless_config,
        rootless_image_set_manifest=image_set,
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

    identity = pilot._a6_static_launch_identity(
        args=args,
        stage="A6",
        config=config,
        execution_root=release,
    )

    assert identity["effective_identity"]["a6_source_release_sha256"] == "b" * 64


    assert identity["effective_identity"][
        "public_task_role_manifest_sha256"
    ] == "c" * 64
    assert identity["effective_identity"][
        "trusted_task_role_manifest_sha256"
    ] == "d" * 64
    assert identity["effective_identity"]["scheduler_epoch"] == "a6-epoch"

    args.a6_prelaunch_identity = None
    with pytest.raises(ValueError, match="missing fail-closed identity arguments"):
        pilot._a6_static_launch_identity(
            args=args,
            stage="A6",
            config=config,
            execution_root=release,
        )

    internal_identity = release / "a6-identity.json"
    _write_json(internal_identity, {"stage": "A6", "status": "materialized"})
    protocol_payload = json.loads(protocol.read_text())
    protocol_payload["prelaunch_identity_freeze"]["record_path"] = (
        "a6-identity.json"
    )
    _write_json(protocol, protocol_payload)
    args.a6_prelaunch_identity = internal_identity
    with pytest.raises(ValueError, match="must be outside source release"):
        pilot._a6_static_launch_identity(
            args=args,
            stage="A6",
            config=config,
            execution_root=release,
        )


def test_discovery_preflight_then_actual_claim_blocks_same_id_restart(
    tmp_path, monkeypatch
):
    import scripts.run_qfbench_discovery_pilot as pilot

    task = SimpleNamespace(task_id="task-a")
    snapshot = SimpleNamespace(
        commit=_FIXTURE_COMMIT,
        primary=SimpleNamespace(tasks=(task,)),
        diagnostic=SimpleNamespace(tasks=()),
    )
    config = SimpleNamespace(
        allowed_model="provider/model",
        required_provider="provider",
        scheduler_epoch="a6-epoch",
        public_root=tmp_path / "public",
        upstream_base_url="https://openrouter.ai/api/v1",
        allowed_path_prefix="/v1",
    )
    evidence_root = tmp_path / "evidence"
    _write_json(
        evidence_root / "contract.json",
        {
            "stage": "A6",
            "contract_arm": "A6-R",
            "evolver_instruction": "Use authorized evidence.",
            "public_contract_evidence": False,
            "train_task_ids": ["task-a"],
        },
    )
    evidence = SimpleNamespace(
        root=evidence_root, sha256="8" * 64, members=("contract.json",)
    )
    backbone = tmp_path / "backbone"
    evolver = tmp_path / "evolver"
    backbone.mkdir()
    evolver.mkdir()
    materialized = tmp_path / "materialized-evolver"
    materialized.mkdir()
    for name in ("qfbench.json", "rootless.json", "images.json"):
        _write_json(tmp_path / name, {"schema_version": 1})
    state = {"propose_calls": 0, "validate_calls": 0, "close_calls": 0}

    class _ProposerBoundary(RuntimeError):
        pass

    class _Proposer:
        def propose(self, **kwargs):
            state["propose_calls"] += 1
            raise _ProposerBoundary("provider boundary")

    class _Runtime:
        proposer = _Proposer()
        scheduler_identity_digest = "5" * 64
        runtime_identity_digest = "6" * 64

        def close(self):
            state["close_calls"] += 1

    monkeypatch.setattr(
        pilot, "load_qfbench_baseline_snapshot", lambda *a, **k: snapshot
    )
    monkeypatch.setattr(
        pilot, "load_rootless_full_harness_config", lambda path: config
    )
    monkeypatch.setattr(pilot, "authorize_evidence_tree", lambda path: evidence)
    monkeypatch.setattr(
        pilot,
        "materialize_evolver_profile",
        lambda *a, **k: SimpleNamespace(materialized_dir=str(materialized)),
    )
    monkeypatch.setattr(pilot, "profile_as_dict", lambda profile: {"mode": "high"})
    monkeypatch.setattr(
        pilot,
        "_a6_static_launch_identity",
        lambda **kwargs: {
            "frozen": {},
            "freeze_record": {
                "protocol_manifest_sha256": "1" * 64,
                "materialized_launch_identity_sha256": "2" * 64,
            },
            "protocol_manifest_path": tmp_path / "protocol.json",
            "identity_record_sha256": "3" * 64,
            "source_release_manifest_sha256": "4" * 64,
            "source_release_member_count": 12,
            "public_contract_source": {
                "public_task_role_manifest_sha256": "7" * 64,
                "instruction_members_sha256": "9" * 64,
            },
            "effective_identity": {"a6_source_release_sha256": "a" * 64},
        },
    )
    monkeypatch.setattr(pilot, "validate_a6_evidence_contract", lambda **k: None)
    monkeypatch.setattr(
        pilot,
        "build_rootless_full_harness_runtime",
        lambda **kwargs: _Runtime(),
    )
    monkeypatch.setattr(pilot, "_stage_evidence", lambda record, run_dir: record)

    def validate(**kwargs):
        state["validate_calls"] += 1

    monkeypatch.setattr(pilot, "validate_a6_prelaunch_identity", validate)
    base_args = [
        "--qfbench-root",
        str(tmp_path / "qfbench"),
        "--qfbench-manifest",
        str(tmp_path / "qfbench.json"),
        "--rootless-config",
        str(tmp_path / "rootless.json"),
        "--rootless-image-set-manifest",
        str(tmp_path / "images.json"),
        "--run-id",
        "qfbench-a6-discovery-boundary-r9",
        "--results-dir",
        str(tmp_path / "runs"),
        "--backbone",
        str(backbone),
        "--evidence",
        str(evidence_root),
        "--evolver-dir",
        str(evolver),
        "--arm",
        "a6-r",
        "--a6-manifest",
        str(tmp_path / "protocol.json"),
        "--a6-prelaunch-identity",
        str(tmp_path / "identity.json"),
        "--a6-source-release-root",
        str(tmp_path),
        "--a6-source-release-manifest",
        str(tmp_path / "source.json"),
    ]

    assert pilot.main([*base_args, "--preflight-only"]) == 0
    marker = (
        tmp_path
        / "runs/qfbench-a6-discovery-boundary-r9/pilot-model-boundary.json"
    )
    assert not marker.exists()
    with pytest.raises(_ProposerBoundary, match="provider boundary"):
        pilot.main([*base_args, "--approve-external-run"])
    assert marker.is_file()
    assert marker.stat().st_mode & 0o777 == 0o600
    assert state["propose_calls"] == 1
    with pytest.raises(ValueError, match="already claimed"):
        pilot.main([*base_args, "--approve-external-run"])
    assert state["propose_calls"] == 1


def test_repository_a6_manifest_validates_three_roles_and_three_arm_contracts():
    from scripts.build_qfbench_a6_evidence import _contract_key

    repository = Path(__file__).resolve().parents[1]
    manifest_path = repository / "data/qfbench/MANIFEST_A6_EXPANDED_CANARY.json"
    if not manifest_path.is_file():
        pytest.skip("the protocol agent has not materialized the A6 manifest")
    baseline_root = repository / (
        "results/bc-mirror/"
        "qfbench-rootless-base-85x5-official-deepseek-v4-flash-0731-"
        "all12x3-20260804"
    )
    if not baseline_root.is_dir():
        pytest.skip("the mirrored five-repeat baseline is not present")
    manifest = json.loads(manifest_path.read_text())
    baseline = json.loads((baseline_root / "result.json").read_text())
    evolution = json.loads(
        (
            repository / "data/qfbench/MANIFEST_30_15_40_EVOLUTION.json"
        ).read_text()
    )

    panel = validate_frozen_a6_panel(
        frozen=manifest["panel"],
        baseline_result=baseline,
        evolution_manifest=evolution,
    )

    assert len(panel.targets) == 6
    assert len(panel.protections) == 8
    assert len(panel.sentinels) == 2
    assert manifest["prelaunch_identity_freeze"]["status"] == (
        "required_not_materialized"
    )
    assert manifest["prelaunch_identity_freeze"][
        "required_before_any_a6_model_call"
    ] is True
    assert [_contract_key(manifest, arm) for arm in ("A6-R", "A6-E", "A6-EC")] == [
        "A6-R",
        "A6-E",
        "A6-EC",
    ]


def _a6_builder_fixture(tmp_path):
    baseline_payload, evolution, panel = _baseline_and_evolution()
    baseline = tmp_path / "baseline"
    _write_json(baseline / "result.json", baseline_payload)
    seed = baseline / "workers/seed"
    seed.mkdir(parents=True)
    (seed / "agent.yaml").write_text("type: agent\n")
    (seed / "systemprompt.md").write_text("fixture\n")
    seed_digest = hash_worker_directory(seed)
    evolution_path = tmp_path / "evolution.json"
    _write_json(evolution_path, evolution)
    shared_evolver_instruction = (
        "Use only the frozen answer-free evidence for the A6 comparison."
    )
    a6 = {
        "schema_version": 1,
        "stage": "A6",
        "benchmark_commit": _FIXTURE_COMMIT,
        "baseline": {
            "run_id": "baseline-fixture",
            "result_sha256": hashlib.sha256(
                (baseline / "result.json").read_bytes()
            ).hexdigest(),
            "seed_worker_digest": seed_digest,
        },
        "selection": {
            "target_count": 2,
            "protection_count": 2,
            "sentinel_count": 2,
            "tvt_manifest_sha256": hashlib.sha256(
                evolution_path.read_bytes()
            ).hexdigest(),
        },
        "panel": panel,
        "experiment": {
            "contracts": {
                "A6-R": {
                    "decision_protocol": "failure_type_v1",
                    "success_counterfactual": "required_or_insufficient",
                    "probe_policy": "constrained_evidence_profile_v1",
                    "max_components": 3,
                    "instruction": shared_evolver_instruction,
                },
                "A6-E": {
                    "decision_protocol": "failure_type_v1",
                    "success_counterfactual": "required_or_insufficient",
                    "probe_policy": "constrained_evidence_profile_v1",
                    "max_components": 3,
                    "instruction": shared_evolver_instruction,
                },
                "A6-EC": {
                    "decision_protocol": "semantic_contract_v1",
                    "success_counterfactual": "required_or_insufficient",
                    "probe_policy": "typed_contract_artifact_trace_v1",
                    "semantic_comparison": "required_for_act",
                    "max_components": 3,
                    "instruction": shared_evolver_instruction,
                },
            }
        },
    }
    manifest = tmp_path / "a6.json"
    _write_json(manifest, a6)
    evidence_run = tmp_path / "fresh"
    _write_json(
        evidence_run / "pilot-plan.json",
        {
            "benchmark_commit": _FIXTURE_COMMIT,
            "arms": [{"label": "seed-evidence", "worker_digest": seed_digest}],
        },
    )
    _write_json(
        evidence_run / "pilot-report.json",
        {
            "status": "complete",
            "task_ids": panel["task_ids"],
            "activations": {"seed-evidence": {"checkpoint": "a6-seed"}},
        },
    )
    role_by_task = {
        item["task_id"]: role[:-1] if role.endswith("s") else role
        for role in ("targets", "protections", "sentinels")
        for item in panel[role]
    }
    for index, task_id in enumerate(panel["task_ids"]):
        attempt_identity = TaskAttempt.create(
            run_id=evidence_run.name,
            benchmark_commit=_FIXTURE_COMMIT,
            task_id=task_id,
            split="mechanism-pilot",
            checkpoint="a6-seed",
            worker_digest=seed_digest,
        )
        attempt = evidence_run / "attempts" / attempt_identity.attempt_id
        _write_json(
            attempt / "attempt.json",
            asdict(attempt_identity),
        )
        role = role_by_task[task_id]
        reward = 0.0 if role == "target" else 1.0
        _write_json(
            attempt / "completed-score.json",
            asdict(
                OfficialTaskScore(
                    task_id=task_id,
                    domain="derivatives",
                    reward=reward,
                    tests_passed=1 if reward == 0 else 2,
                    tests_failed=1 if reward == 0 else 0,
                    verifier_exit_code=0,
                    diagnostic_tags=() if reward else ("tests_failed",),
                )
            ),
        )
        audit_record = {
            "schema_version": 1,
            "request_identity_sha256": f"{index:x}" * 64,
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
        (attempt / "proxy-audit.jsonl").write_text(
            json.dumps(audit_record, sort_keys=True) + "\n"
        )
        _write_json(
            attempt / "worker-execution.json",
            {
                "trace_uri": "raw-trace.jsonl",
                "final_text_uri": "final.txt",
                "artifact_dir": "artifacts",
                "summary": {"tool_calls": 1, "tool_errors": 0},
            },
        )
        (attempt / "raw-trace.jsonl").write_text(
            json.dumps({"role": "assistant", "content": "validate output"}) + "\n"
        )
        (attempt / "final.txt").write_text("done\n")
        artifacts = attempt / "artifacts"
        artifacts.mkdir()
        (artifacts / "result.json").write_text('{"value": 1}\n')
    report_path = evidence_run / "pilot-report.json"
    report = json.loads(report_path.read_text())
    report["cost"] = audit_fixed_checkpoint_proxy_costs(
        evidence_run,
        expected_attempts=len(panel["task_ids"]),
        checkpoint="a6-seed",
        split="mechanism-pilot",
    )
    _write_json(report_path, report)
    qfbench = tmp_path / "qfbench"
    qfbench.mkdir()
    for task_id in panel["task_ids"]:
        task = qfbench / "tasks" / task_id
        task.mkdir(parents=True)
        (task / "instruction.md").write_text(
            f"# {task_id}\n\nWrite result.json with value.\n"
        )
    _write_public_role_manifest(qfbench)
    return baseline, evolution_path, manifest, evidence_run, qfbench


def test_a6_builder_produces_raw_evidence_and_semantic_contract_ladder(tmp_path):
    from scripts.build_qfbench_a4_evidence import build

    baseline, evolution, manifest, evidence_run, qfbench = _a6_builder_fixture(
        tmp_path
    )
    roots = {}
    reports = {}
    for arm in ("A6-R", "A6-E", "A6-EC"):
        destination = tmp_path / arm
        roots[arm] = destination
        reports[arm] = build(
            baseline_run=baseline,
            evolution_manifest_path=evolution,
            a4_manifest_path=manifest,
            evidence_run=evidence_run,
            arm="seed-evidence",
            destination=destination,
            contract_arm=arm,
            public_task_root=(qfbench if arm != "A6-R" else None),
        )

    assert reports["A6-R"]["role_counts"] == {
        "target": 2,
        "protection": 2,
        "sentinel": 2,
    }
    assert not (roots["A6-R"] / "contracts").exists()
    assert (roots["A6-E"] / "contracts/index.json").is_file()
    assert (roots["A6-EC"] / "contracts/index.json").is_file()
    assert (roots["A6-E"] / "contracts/index.json").read_bytes() == (
        roots["A6-EC"] / "contracts/index.json"
    ).read_bytes()
    assert json.loads((roots["A6-E"] / "contract.json").read_text())[
        "semantic_comparison"
    ] == "available_not_required"
    assert json.loads((roots["A6-EC"] / "contract.json").read_text())[
        "semantic_comparison"
    ] == "required_for_act"
    contracts = {
        arm: json.loads((root / "contract.json").read_text())
        for arm, root in roots.items()
    }
    assert len(
        {contract["evolver_instruction"] for contract in contracts.values()}
    ) == 1
    assert contracts["A6-R"]["public_task_role_manifest_sha256"] is None
    assert contracts["A6-R"]["public_contract_source_members_sha256"] is None
    assert {
        contracts[arm]["public_task_role_manifest_sha256"]
        for arm in ("A6-E", "A6-EC")
    } == {hashlib.sha256((qfbench / "MANIFEST.json").read_bytes()).hexdigest()}
    assert len(
        {
            contracts[arm]["public_contract_source_members_sha256"]
            for arm in ("A6-E", "A6-EC")
        }
    ) == 1
    shared_members = {
        arm: sorted(
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_file()
            and path.name != "access_log.jsonl"
            and path.name != "contract.json"
            and "contracts" not in path.relative_to(root).parts
        )
        for arm, root in roots.items()
    }
    assert shared_members["A6-R"] == shared_members["A6-E"]
    assert shared_members["A6-R"] == shared_members["A6-EC"]
    for relative in shared_members["A6-R"]:
        assert (roots["A6-R"] / relative).read_bytes() == (
            roots["A6-E"] / relative
        ).read_bytes()
        assert (roots["A6-R"] / relative).read_bytes() == (
            roots["A6-EC"] / relative
        ).read_bytes()
    task_index = json.loads(
        (roots["A6-R"] / "debugger/task_index.json").read_text()
    )
    assert all(
        "public_instruction" not in task["paths"]
        and "public_clauses" not in task["paths"]
        for task in task_index["tasks"]
    )
    for root in roots.values():
        contract = json.loads((root / "contract.json").read_text())
        assert contract["sentinel_task_ids"] == ["sentinel-a", "sentinel-b"]
        assert contract["evaluator_feedback_tier"] == "answer_free_public_process"
        assert contract["feedback_manifest_digest"] is None


def test_a6_builder_rejects_timeout_with_unreconciled_proxy_ledger(tmp_path):
    from scripts.build_qfbench_a4_evidence import build

    baseline, evolution, manifest, evidence_run, _ = _a6_builder_fixture(
        tmp_path
    )
    timeout_dir = next(
        path.parent
        for path in (evidence_run / "attempts").glob("*/attempt.json")
        if json.loads(path.read_text())["task_id"] == "target-a"
    )
    (timeout_dir / "proxy-audit.jsonl").unlink()
    _write_json(
        timeout_dir / "completed-score.json",
        asdict(
            OfficialTaskScore(
                task_id="target-a",
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
        expected_attempts=6,
        checkpoint="a6-seed",
        split="mechanism-pilot",
    )
    _write_json(report_path, report)

    with pytest.raises(ValueError, match="canonical request/token/cost ledger"):
        build(
            baseline_run=baseline,
            evolution_manifest_path=evolution,
            a4_manifest_path=manifest,
            evidence_run=evidence_run,
            arm="seed-evidence",
            destination=tmp_path / "blocked-cost",
            contract_arm="A6-R",
        )


def test_a6_builder_accepts_safe_rate_limit_retry_with_complete_logical_ledger(
    tmp_path,
):
    from qea.model_proxy import model_proxy_wire_request_identity
    from scripts.build_qfbench_a4_evidence import build

    baseline, evolution, manifest, evidence_run, _ = _a6_builder_fixture(
        tmp_path
    )
    attempt_dir = next(
        path.parent for path in (evidence_run / "attempts").glob("*/attempt.json")
    )
    logical = "e" * 64
    rows = []
    for retry_index, rate_limited in ((0, True), (1, False)):
        rows.append(
            {
                "schema_version": 2,
                "request_identity_sha256": model_proxy_wire_request_identity(
                    logical, retry_index
                ),
                "logical_request_identity_sha256": logical,
                "retry_index": retry_index,
                "model": "provider/model",
                "started_at": "2026-08-09T00:00:00+00:00",
                "finished_at": "2026-08-09T00:00:01+00:00",
                "latency_ms": 1000,
                "request_state": (
                    "not_accepted" if rate_limited else "completed"
                ),
                "upstream_status_code": 429 if rate_limited else 200,
                "provider_request_id": (
                    None if rate_limited else "provider-request-retry"
                ),
                "input_tokens": None if rate_limited else 10,
                "output_tokens": None if rate_limited else 5,
                "total_tokens": None if rate_limited else 15,
                "provider_cost_usd": None if rate_limited else 0.001,
                "failure_class": "rate_limited" if rate_limited else None,
            }
        )
    with (attempt_dir / "proxy-audit.jsonl").open("a") as stream:
        stream.write("".join(json.dumps(row) + "\n" for row in rows))
    report_path = evidence_run / "pilot-report.json"
    report = json.loads(report_path.read_text())
    report["cost"] = audit_fixed_checkpoint_proxy_costs(
        evidence_run,
        expected_attempts=6,
        checkpoint="a6-seed",
        split="mechanism-pilot",
    )
    _write_json(report_path, report)

    built = build(
        baseline_run=baseline,
        evolution_manifest_path=evolution,
        a4_manifest_path=manifest,
        evidence_run=evidence_run,
        arm="seed-evidence",
        destination=tmp_path / "rate-limit-corpus",
        contract_arm="A6-R",
    )

    cost = report["cost"]
    assert cost["request_count"] == 8
    assert cost["completed_request_count"] == 7
    assert cost["logical_request_count"] == 7
    assert cost["rate_limited_retry_count"] == 1
    assert cost["other_nonaccepted_request_count"] == 0
    assert built["task_ids"]


def test_a6_builder_fails_closed_for_unapproved_feedback_tier(tmp_path):
    from scripts.build_qfbench_a4_evidence import build

    baseline, evolution, manifest, evidence_run, qfbench = _a6_builder_fixture(
        tmp_path
    )
    payload = json.loads(manifest.read_text())
    payload["experiment"]["contracts"]["A6-EC"][
        "evaluator_feedback_tier"
    ] = "raw_verifier_feedback"
    _write_json(manifest, payload)

    with pytest.raises(ValueError, match="feedback tier"):
        build(
            baseline_run=baseline,
            evolution_manifest_path=evolution,
            a4_manifest_path=manifest,
            evidence_run=evidence_run,
            arm="seed-evidence",
            destination=tmp_path / "blocked",
            contract_arm="A6-EC",
            public_task_root=qfbench,
        )


def test_a6_auditor_checks_ladder_bytes_grounded_triples_and_false_act_signals(
    tmp_path, monkeypatch
):
    import scripts.audit_qfbench_a6_discovery as auditor

    manifest = {
        "stage": "A6",
        "panel": {
            "targets": [{"task_id": "target-a", "domain": "rates"}],
            "protections": [{"task_id": "protect-a", "domain": "risk"}],
            "sentinels": [{"task_id": "sentinel-a", "domain": "crypto"}],
            "task_ids": ["target-a", "protect-a", "sentinel-a"],
        },
        "analysis_plan": {
            "candidate_advancement_thresholds": (
                _candidate_advancement_thresholds()
            )
        },
    }
    public_root = tmp_path / "public-qfbench"
    (public_root / "tasks/target-a").mkdir(parents=True)
    (public_root / "tasks/target-a/instruction.md").write_text(
        "# Output\nReturn the required field.\n"
    )
    _write_public_role_manifest(public_root)
    public_source = public_contract_source_identity(
        public_task_root=public_root,
        task_ids=["target-a"],
        benchmark_commit=_FIXTURE_COMMIT,
    )
    proposal_runs = {}
    decisions = {"A6-R": "ACT", "A6-E": "ABSTAIN", "A6-EC": "ACT"}
    for arm, protocol, expose in (
        ("A6-R", "failure_type_v1", False),
        ("A6-E", "failure_type_v1", True),
        ("A6-EC", "semantic_contract_v1", True),
    ):
        run = tmp_path / arm
        evidence = run / "authorized-evidence"
        evidence.mkdir(parents=True)
        (evidence / "access_log.jsonl").write_text("")
        (evidence / "debugger.json").write_text('{"same": true}\n')
        artifact = evidence / "tasks/target-a/artifacts/result.json"
        artifact.parent.mkdir(parents=True)
        artifact.write_text("{}\n")
        (evidence / "tasks/target-a/worker_trace.jsonl").write_text(
            '{"role":"assistant","content":"validation"}\n'
        )
        _write_json(
            evidence / "contract.json",
            {
                "contract_arm": arm,
                "decision_protocol": protocol,
                "probe_policy": (
                    "typed_contract_artifact_trace_v1"
                    if arm == "A6-EC"
                    else "constrained_evidence_profile_v1"
                ),
                "public_contract_evidence": expose,
                "public_contract_index": (
                    "contracts/index.json" if expose else None
                ),
                "semantic_comparison": (
                    "required_for_act"
                    if arm == "A6-EC"
                    else "available_not_required"
                    if arm == "A6-E"
                    else "not_required"
                ),
                "evaluator_feedback_tier": "answer_free_public_process",
                "evolver_instruction": (
                    "Use only the frozen answer-free evidence for the A6 "
                    "comparison."
                ),
                "seed_launch_identity_sha256": "a" * 64,
                "seed_identity_record_sha256": "b" * 64,
                "public_task_role_manifest_sha256": (
                    public_source["public_task_role_manifest_sha256"]
                    if expose
                    else None
                ),
                "public_contract_source_members_sha256": (
                    public_source["instruction_members_sha256"]
                    if expose
                    else None
                ),
            },
        )
        if expose:
            build_public_contract_index(
                qfbench_root=public_root,
                task_ids=["target-a"],
                destination=evidence / "contracts",
                benchmark_commit=_FIXTURE_COMMIT,
            )
        state = {
            "protocol": protocol,
            "decision": decisions[arm],
            "unlocked": decisions[arm] == "ACT",
            "hypothesis": (
                {
                    "selected_hypothesis_id": "h1",
                    "hypotheses_eliminated": ["h2"],
                    "components": ["validator"],
                    "prediction": {"observable": "required field appears"},
                }
                if decisions[arm] == "ACT"
                else {
                    "hypotheses_considered": [
                        {"hypothesis_id": "h1", "insufficient_contrast": True}
                    ],
                    "selected_hypothesis_id": None,
                    "hypotheses_eliminated": [],
                    "probe_records_used": [
                        {
                            "probe_id": "inconclusive",
                            "hypothesis_expectations": {"h1": "unresolved"},
                        }
                    ],
                    "components": [],
                    "uncertainty": "the matched comparison was inconclusive",
                    "abstain_reason": "no competing hypothesis was eliminated",
                }
            ),
        }
        if arm == "A6-EC":
            state["hypothesis"]["selected_hypothesis_id"] = "h1"
            state["hypothesis"]["grounded_semantic_comparisons"] = [
                {
                    "probe_id": "typed",
                    "task_id": "target-a",
                    "clause": {
                        "clause_id": "target-a#c0002",
                        "text_sha256": hashlib.sha256(
                            b"Return the required field."
                        ).hexdigest(),
                    },
                    "artifact": {
                        "path": "tasks/target-a/artifacts/result.json",
                        "selector": {"kind": "json_pointer", "value": "/x"},
                        "value_type": "missing",
                        "shape": {},
                    },
                    "trace": {
                        "path": "tasks/target-a/worker_trace.jsonl",
                        "phase": "validation",
                        "phase_present": False,
                    },
                    "semantic_relation": "contradicts",
                    "selected_hypothesis_id": "h1",
                    "contradicted_hypothesis_ids": ["h2"],
                }
            ]
        _write_json(
            run / "pilot-report.json",
            {
                "proposal": {
                    "prediction": {
                        "component": "validator",
                        "observable": f"{arm} required field appears",
                    },
                    "summary": {"discovery_hypothesis": state},
                    "diff": (
                        ""
                        if decisions[arm] == "ABSTAIN"
                        else "--- before\n+++ after\n+validator\n"
                    ),
                    "mutation_metrics": {
                        "changed_file_count": (
                            0 if decisions[arm] == "ABSTAIN" else 1
                        ),
                        "measurement_only": True,
                    },
                    "candidate_generation_throughput": {
                        "wall_seconds": 1.0,
                        "total_tokens": 10,
                    },
                }
            },
        )
        proposal_runs[arm] = run

    def fake_a5(*, proposal_runs, **kwargs):
        label = next(iter(proposal_runs))
        decision = decisions[label]
        candidate = (
            {
                "outcome": {
                    "reward_gain_count": 0 if label == "A6-R" else 1,
                    "target_reward_gain_count": (
                        0 if label == "A6-R" else 1
                    ),
                    "task_vectors": {
                        "target-a": {
                            "reward": 0.0 if label == "A6-R" else 0.2
                        },
                        "protect-a": {"reward": 0.0},
                        "sentinel-a": {
                            "reward": 0.0 if label == "A6-R" else -1.0
                        },
                    },
                },
                "protection_regressions": [],
            }
            if decision == "ACT"
            else "not_applicable_abstained"
        )
        return {
            "seed_harness_capability": {"task_count": 3},
            "arms": {
                label: {
                    "decision": decision,
                    "discovery": {"checks": {"fixture_contract": True}},
                    "candidate_evaluation": candidate,
                }
            },
        }

    monkeypatch.setattr(auditor, "audit_a5", fake_a5)
    r_prediction = {
        "component": "validator",
        "observable": "A6-R required field appears",
    }
    r_prediction_audit = tmp_path / "a6-r-prediction-audit.json"
    _write_json(
        r_prediction_audit,
        {
            "schema_version": 1,
            "arm": "A6-R",
            "adjudication_scope": (
                "primary_component_specific_observable_prediction"
            ),
            "prediction_sha256": auditor._json_digest(r_prediction),
            "status": "falsified",
            "evidence_refs": ["pilot-report.json"],
            "rationale": "The preregistered field remained absent.",
            "causal_truth_judged": False,
        },
    )

    report = auditor.audit(
        manifest=manifest,
        seed_run=tmp_path,
        seed_arm="seed",
        proposal_runs=proposal_runs,
        candidate_runs={"A6-R": proposal_runs["A6-R"]},
        prediction_audits={"A6-R": r_prediction_audit},
    )

    assert report["ladder_byte_audit"]["passed"] is True
    assert "evolver_instruction" not in report["ladder_byte_audit"][
        "observed_contract_difference_fields"
    ]
    assert report["panel"]["sentinels_are_not_protection_gate"] is True
    assert report["arms"]["A6-R"]["semantic_audit"][
        "unsupported_semantic_leap"
    ] is None
    assert report["arms"]["A6-R"]["semantic_audit"][
        "unsupported_semantic_leap_applicable"
    ] is False
    assert report["arms"]["A6-R"]["semantic_audit"][
        "clause_link_availability"
    ] == "structurally_unavailable"
    assert report["arms"]["A6-R"]["false_act_audit"]["false_act"] is True
    assert report["arms"]["A6-R"]["candidate_evaluation"][
        "prediction_audit"
    ]["verified_prediction_binding"] is True
    assert report["arms"]["A6-E"]["false_act_audit"]["false_act"] is None
    assert report["arms"]["A6-E"]["abstain_calibration"][
        "calibrated_abstain"
    ] is True
    assert report["arms"]["A6-EC"]["semantic_audit"][
        "semantic_act_gate_passed"
    ] is True
    assert report["arms"]["A6-EC"]["semantic_audit"][
        "grounded_triple_attempted_count"
    ] == 1
    assert report["arms"]["A6-EC"]["semantic_audit"][
        "grounded_triple_valid_count"
    ] == 1
    assert report["arms"]["A6-EC"]["semantic_audit"][
        "selected_hypothesis_grounded_coverage"
    ] == 1.0
    assert report["arms"]["A6-EC"]["semantic_audit"][
        "causal_truth_judged"
    ] is False
    assert report["arms"]["A6-EC"]["mutation_metrics"][
        "changed_file_count"
    ] == 1
    reward = report["arms"]["A6-EC"]["reward_audit"]
    assert reward["all_16_descriptive_six_domain"]["domain_count"] == 3
    assert reward["all_16_descriptive_six_domain"]["macro_reward_delta"] < 0
    assert reward["stable_14_task_five_domain"]["domain_count"] == 2
    assert reward["stable_14_task_five_domain"]["macro_reward_delta"] == pytest.approx(
        0.1
    )
    assert reward["volatile_sentinels_excluded_from_stable_gate"] is True
    assert report["arms"]["A6-EC"]["candidate_advancement"][
        "volatile_sentinels_used_for_gate"
    ] is False

    bad_prediction_audit = tmp_path / "bad-prediction-audit.json"
    bad_payload = json.loads(r_prediction_audit.read_text())
    bad_payload["prediction_sha256"] = "0" * 64
    _write_json(bad_prediction_audit, bad_payload)
    with pytest.raises(ValueError, match="not bound to the proposal"):
        auditor.audit(
            manifest=manifest,
            seed_run=tmp_path,
            seed_arm="seed",
            proposal_runs=proposal_runs,
            candidate_runs={"A6-R": proposal_runs["A6-R"]},
            prediction_audits={"A6-R": bad_prediction_audit},
        )

    e_contract_path = (
        proposal_runs["A6-E"] / "authorized-evidence/contract.json"
    )
    e_contract = json.loads(e_contract_path.read_text())
    e_contract["unexpected_arm_only_setting"] = True
    _write_json(e_contract_path, e_contract)

    drifted = auditor.audit(
        manifest=manifest,
        seed_run=tmp_path,
        seed_arm="seed",
        proposal_runs=proposal_runs,
    )

    assert drifted["ladder_byte_audit"]["passed"] is False
    assert drifted["ladder_byte_audit"][
        "unexpected_contract_difference_fields"
    ] == ["unexpected_arm_only_setting"]
