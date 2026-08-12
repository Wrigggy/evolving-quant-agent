#!/usr/bin/env python3
"""Build one arm of the A6 evidence-versus-contract discovery ladder."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Iterable, Mapping

if __name__ == "__main__":
    # A6 releases are content-addressed and must not be mutated by imports.
    sys.dont_write_bytecode = True

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_qfbench_a4_evidence import (  # noqa: E402
    _require_complete_component_cost,
    build,
)
from qea.qfbench_a6 import validate_a6_prelaunch_identity  # noqa: E402


_ARMS = ("A6-R", "A6-E", "A6-EC")


def _json(path: Path) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"required regular JSON file is unavailable: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _a6_seed_identity(
    *,
    manifest_path: Path,
    manifest: Mapping[str, object],
    evidence_run: Path,
    identity_path: Path,
) -> dict[str, object]:
    """Bind a completed shared seed run to the materialized A6 launch."""

    identity_path = identity_path.expanduser().resolve()
    record = _json(identity_path)
    effective_fields = (
        "rootless_config_sha256",
        "image_set_manifest_sha256",
        "public_task_role_manifest_sha256",
        "trusted_task_role_manifest_sha256",
        "scheduler_epoch",
        "scheduler_identity_sha256",
        "provider_route_identity_sha256",
        "a6_source_release_sha256",
    )
    validate_a6_prelaunch_identity(
        frozen=manifest,
        freeze_record=record,
        protocol_manifest_path=manifest_path,
        effective_identity={field: record.get(field) for field in effective_fields},
    )
    record_sha256 = _sha256(identity_path)
    plan = _json(evidence_run / "pilot-plan.json")
    report = _json(evidence_run / "pilot-report.json")
    if report.get("status") != "complete":
        raise ValueError("A6 fresh seed run is not complete")
    plan_identity = plan.get("a6_prelaunch_identity")
    report_identity = report.get("a6_prelaunch_identity")
    if not isinstance(plan_identity, Mapping) or not isinstance(
        report_identity, Mapping
    ):
        raise ValueError("A6 fresh seed run has no validated launch identity")
    expected_metadata = {
        "run_kind": "seed",
        "identity_record_sha256": record_sha256,
        "materialized_launch_identity_sha256": record.get(
            "materialized_launch_identity_sha256"
        ),
        "protocol_manifest_sha256": record.get("protocol_manifest_sha256"),
        "source_release_tree_sha256": record.get("a6_source_release_sha256"),
    }
    drifted_metadata = sorted(
        key
        for key, expected in expected_metadata.items()
        if plan_identity.get(key) != expected or report_identity.get(key) != expected
    )
    if drifted_metadata:
        raise ValueError(
            "A6 fresh seed launch identity differs from the freeze record: "
            + ", ".join(drifted_metadata)
        )
    if report_identity.get("validated_before_first_evaluator_call") is not True:
        raise ValueError(
            "A6 fresh seed launch identity was not validated before evaluation"
        )
    panel = manifest.get("panel")
    raw_task_ids = panel.get("task_ids") if isinstance(panel, Mapping) else None
    if (
        not isinstance(raw_task_ids, list)
        or not raw_task_ids
        or any(not isinstance(task_id, str) for task_id in raw_task_ids)
    ):
        raise ValueError("A6 manifest task panel is invalid")
    _require_complete_component_cost(
        evidence_run,
        report=report,
        arm="seed-evidence",
        expected_tasks=tuple(raw_task_ids),
    )
    input_checks = {
        "benchmark_commit": (
            plan.get("benchmark_commit"),
            manifest.get("benchmark_commit"),
        ),
        "task_ids": (
            plan.get("task_ids"),
            manifest.get("panel", {}).get("task_ids")
            if isinstance(manifest.get("panel"), Mapping)
            else None,
        ),
        "rootless_config_sha256": (
            plan.get("rootless_config_sha256"),
            record.get("rootless_config_sha256"),
        ),
        "image_set_manifest_sha256": (
            plan.get("image_set_sha256"),
            record.get("image_set_manifest_sha256"),
        ),
        "scheduler_epoch": (
            (
                plan.get("effective_runtime", {}).get("scheduler_epoch")
                if isinstance(plan.get("effective_runtime"), Mapping)
                else None
            ),
            record.get("scheduler_epoch"),
        ),
        "scheduler_identity_sha256": (
            report_identity.get("scheduler_identity_sha256"),
            record.get("scheduler_identity_sha256"),
        ),
    }
    runtime = manifest.get("frozen_runtime")
    runtime = runtime if isinstance(runtime, Mapping) else {}
    effective_runtime = plan.get("effective_runtime")
    effective_runtime = (
        effective_runtime if isinstance(effective_runtime, Mapping) else {}
    )
    input_checks.update(
        {
            "allowed_model": (
                effective_runtime.get("allowed_model"),
                runtime.get("model"),
            ),
            "required_provider": (
                effective_runtime.get("required_provider"),
                runtime.get("provider"),
            ),
        }
    )
    drifted_inputs = sorted(
        key for key, (observed, expected) in input_checks.items() if observed != expected
    )
    if drifted_inputs:
        raise ValueError(
            "A6 fresh seed effective inputs differ from the freeze record: "
            + ", ".join(drifted_inputs)
        )
    return {
        "seed_launch_identity_sha256": record[
            "materialized_launch_identity_sha256"
        ],
        "seed_identity_record_sha256": record_sha256,
    }


def _normalized_arm(value: str) -> str:
    normalized = value.strip().upper().replace("_", "-")
    if normalized not in _ARMS:
        raise argparse.ArgumentTypeError(f"A6 arm must be one of {_ARMS}")
    return normalized


def _contract_key(manifest: Mapping[str, object], arm: str) -> str:
    experiment = manifest.get("experiment")
    experiment = experiment if isinstance(experiment, Mapping) else {}
    contracts = experiment.get("contracts")
    if not isinstance(contracts, Mapping):
        design = manifest.get("discovery_design")
        design = design if isinstance(design, Mapping) else {}
        contracts = design.get("arms")
    if not isinstance(contracts, Mapping):
        raise ValueError("A6 manifest has no discovery arm contracts")

    target = "".join(character for character in arm.casefold() if character.isalnum())
    matches = [
        str(key)
        for key in contracts
        if "".join(
            character for character in str(key).casefold() if character.isalnum()
        )
        == target
    ]
    if len(matches) != 1:
        raise ValueError(f"A6 manifest has no unique contract for arm {arm!r}")
    return matches[0]


def _subset_digest(root: Path, members: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for relative in sorted(members):
        payload = (root / relative).read_bytes()
        encoded = relative.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def _add_ladder_digests(report: dict[str, object], destination: Path) -> None:
    members = [
        path.relative_to(destination).as_posix()
        for path in destination.rglob("*")
        if path.is_file()
        and not path.is_symlink()
        and path.name != "access_log.jsonl"
    ]
    shared = [
        relative
        for relative in members
        if relative != "contract.json" and not relative.startswith("contracts/")
    ]
    semantic = [relative for relative in members if relative.startswith("contracts/")]
    report["ladder_byte_audit"] = {
        "shared_core_member_count": len(shared),
        "shared_core_sha256": _subset_digest(destination, shared),
        "semantic_contract_member_count": len(semantic),
        "semantic_contract_sha256": (
            _subset_digest(destination, semantic) if semantic else None
        ),
        "excluded_from_shared_core": ["contract.json", "contracts/**"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-run", type=Path, required=True)
    parser.add_argument("--evolution-manifest", type=Path, required=True)
    parser.add_argument("--a6-manifest", type=Path, required=True)
    parser.add_argument("--evidence-run", type=Path, required=True)
    parser.add_argument(
        "--a6-prelaunch-identity",
        type=Path,
        required=True,
        help="Materialized identity record used by the completed A6 seed run.",
    )
    parser.add_argument("--seed-arm", default="seed-evidence")
    parser.add_argument("--a6-arm", type=_normalized_arm, required=True)
    parser.add_argument(
        "--qfbench-root",
        type=Path,
        help=(
            "Exact verified public role root with MANIFEST.json; required for "
            "A6-E and A6-EC only."
        ),
    )
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args(argv)

    manifest_path = args.a6_manifest.expanduser().resolve()
    execution_root = Path(__file__).resolve().parents[1]
    expected_manifest = (
        execution_root / "data/qfbench/MANIFEST_A6_EXPANDED_CANARY.json"
    )
    if manifest_path != expected_manifest:
        raise ValueError("A6 protocol manifest is not the executing release manifest")
    manifest = _json(manifest_path)
    if manifest.get("stage") != "A6":
        raise ValueError("A6 evidence builder requires an A6 manifest")
    identity_spec = manifest.get("prelaunch_identity_freeze")
    identity_spec = identity_spec if isinstance(identity_spec, Mapping) else {}
    record_path = identity_spec.get("record_path")
    if not isinstance(record_path, str) or not record_path:
        raise ValueError("A6 protocol has no external identity record path")
    expected_identity_path = (execution_root / record_path).resolve()
    if (
        expected_identity_path == execution_root
        or execution_root in expected_identity_path.parents
    ):
        raise ValueError("A6 prelaunch identity path is inside the source release")
    if args.a6_prelaunch_identity.expanduser().resolve() != expected_identity_path:
        raise ValueError("A6 prelaunch identity path differs from the protocol")
    evidence_run = args.evidence_run.expanduser().resolve()
    seed_identity = _a6_seed_identity(
        manifest_path=manifest_path,
        manifest=manifest,
        evidence_run=evidence_run,
        identity_path=args.a6_prelaunch_identity,
    )
    contract_key = _contract_key(manifest, args.a6_arm)
    experiment = manifest.get("experiment")
    experiment = experiment if isinstance(experiment, Mapping) else {}
    contracts = experiment.get("contracts")
    if not isinstance(contracts, Mapping):
        design = manifest.get("discovery_design")
        design = design if isinstance(design, Mapping) else {}
        contracts = design.get("arms")
    contract = contracts[contract_key]
    if not isinstance(contract, Mapping):
        raise ValueError(f"A6 contract {contract_key!r} is invalid")

    exposes_contracts = args.a6_arm in {"A6-E", "A6-EC"}
    expected_protocol = (
        "semantic_contract_v1" if args.a6_arm == "A6-EC" else "failure_type_v1"
    )
    if contract.get("decision_protocol") != expected_protocol:
        raise ValueError(
            f"{args.a6_arm} requires decision_protocol={expected_protocol}"
        )
    if args.a6_arm == "A6-EC" and contract.get(
        "semantic_comparison", "required_for_act"
    ) != "required_for_act":
        raise ValueError("A6-EC must require a grounded semantic comparison for ACT")
    if exposes_contracts and args.qfbench_root is None:
        raise ValueError(f"{args.a6_arm} requires --qfbench-root")
    if contract.get("public_contract_index") is not exposes_contracts:
        raise ValueError(
            f"{args.a6_arm} public_contract_index differs from its ladder role"
        )

    destination = args.destination.expanduser().resolve()
    report = build(
        baseline_run=args.baseline_run,
        evolution_manifest_path=args.evolution_manifest,
        a4_manifest_path=manifest_path,
        evidence_run=evidence_run,
        arm=args.seed_arm,
        destination=destination,
        contract_arm=contract_key,
        public_task_root=(
            args.qfbench_root.expanduser().resolve()
            if exposes_contracts and args.qfbench_root is not None
            else None
        ),
        a6_seed_identity=seed_identity,
    )
    report["a6_arm"] = args.a6_arm
    report["manifest_contract_key"] = contract_key
    _add_ladder_digests(report, destination)
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
