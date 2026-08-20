#!/usr/bin/env python3
"""Run one evidence-bound proposal-only quant discovery canary on rootless Docker."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Mapping

if __name__ == "__main__":
    # A6 releases are content-addressed and must not be mutated by imports.
    sys.dont_write_bytecode = True

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.benchmarks.qfbench import load_qfbench_baseline_snapshot  # noqa: E402
from qea.a6_model_boundary import (  # noqa: E402
    assert_a6_model_boundary_unclaimed,
    claim_a6_model_boundary,
)
from qea.a6_source_release import validate_a6_source_release  # noqa: E402
from qea.candidate_admission import (  # noqa: E402
    AdmissionPolicy,
    CandidateAdmissionError,
    admit_candidate,
)
from qea.evolve_runtime import dir_unified_diff  # noqa: E402
from qea.evolution_evidence import authorize_evidence_tree  # noqa: E402
from qea.evolver_profile import (  # noqa: E402
    materialize_evolver_profile,
    profile_as_dict,
)
from qea.mutation_metrics import measure_mutation  # noqa: E402
from qea.public_contract_evidence import (  # noqa: E402
    public_contract_source_identity,
    validate_public_contract_index,
)
from qea.qfbench_a6 import (  # noqa: E402
    validate_a6_evidence_contract,
    validate_a6_prelaunch_identity,
)
from qea.rootless_full_harness import (  # noqa: E402
    build_rootless_full_harness_runtime,
    load_rootless_full_harness_config,
    rootless_model_route_identity,
)
from qea.rootless_images import verify_role_root  # noqa: E402


_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_ARM = re.compile(r"[a-z0-9][a-z0-9_-]{0,47}\Z")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def _arm(value: str) -> str:
    if _ARM.fullmatch(value) is None:
        raise argparse.ArgumentTypeError("arm must be a safe lowercase label")
    return value


def _diagnosis(evidence_root: Path, arm: str) -> dict[str, object]:
    """Read the experiment instruction from the authorized evidence contract."""

    contract = _json(evidence_root / "contract.json")
    instruction = contract.get("evolver_instruction")
    if not isinstance(instruction, str) or not instruction.strip():
        candidate_goal = contract.get("candidate_goal")
        if isinstance(candidate_goal, str) and candidate_goal.strip():
            instruction = candidate_goal
        else:
            instruction = (
                "Discover and test one causal harness mechanism from the authorized "
                "public evidence. Verify indexed claims against raw evidence. The "
                "coordinator prescribes no component, file, root cause, or "
                "implementation."
            )
    if len(instruction.encode("utf-8")) > 8 * 1024:
        raise ValueError("evidence contract Evolver instruction is too large")
    stage = contract.get("stage", "DISCOVERY")
    if not isinstance(stage, str) or not stage.strip():
        raise ValueError("evidence contract stage is invalid")
    contract_arm = contract.get("contract_arm")
    if isinstance(contract_arm, str) and contract_arm:
        normalized_requested = "".join(
            character for character in arm.casefold() if character.isalnum()
        )
        normalized_contract = "".join(
            character for character in contract_arm.casefold() if character.isalnum()
        )
        if normalized_requested != normalized_contract:
            raise ValueError("requested arm differs from the evidence contract")
    return {
        "stage": stage,
        "arm": arm,
        "instruction": instruction.strip(),
    }


def _terminal_decision(
    discovery_state: Mapping[str, object],
    prediction: Mapping[str, object] | None = None,
) -> str | None:
    """Return an explicitly recorded decision from either terminal artifact."""

    for record in (discovery_state, prediction or {}):
        raw = record.get("decision")
        if isinstance(raw, str):
            decision = raw.strip().upper()
            if decision in {"ACT", "ABSTAIN"}:
                return decision
    return None


def _candidate_admission(
    *,
    decision: str | None,
    backbone: Path,
    candidate: Path,
) -> dict[str, object]:
    """Admit only an explicitly recorded ACT; all other states are fail-closed."""

    if decision == "ABSTAIN":
        return {
            "admitted": None,
            "not_applicable": True,
            "reason": "Evolver recorded ABSTAIN; candidate writes remained locked",
        }
    if decision != "ACT":
        return {
            "admitted": False,
            "not_applicable": True,
            "reason": (
                "Evolver did not record a valid ACT or ABSTAIN decision; "
                "candidate admission is fail-closed"
            ),
        }
    try:
        return asdict(
            admit_candidate(
                backbone,
                candidate,
                AdmissionPolicy.qfbench_full(),
            )
        )
    except CandidateAdmissionError as exc:
        return {
            "admitted": False,
            "failure": f"{type(exc).__name__}: {exc}",
        }


def _summary_payload(summary) -> dict[str, object]:
    return {
        "scores": [asdict(score) for score in summary.scores],
        "task_rewards": dict(summary.task_rewards),
        "domain_scores": dict(summary.domain_scores),
        "task_mean": summary.task_mean,
        "overall": summary.overall,
    }


def _coordinated_probe_task_key(
    *,
    contract: Mapping[str, object],
    decision: str | None,
    admission: Mapping[str, object],
    discovery_state: Mapping[str, object],
) -> str | None:
    """Return the Evolver-selected singleton target for an admitted ACT."""

    if contract.get("stage") != "COORDINATED_BREADTH":
        raise ValueError("selected-probe dispatch requires coordinated evidence")
    if contract.get("max_worker_probes_this_round") != 1:
        raise ValueError("coordinated evidence must permit exactly one Worker probe")
    if decision != "ACT" or admission.get("admitted") is not True:
        return None
    hypothesis = discovery_state.get("hypothesis")
    if not isinstance(hypothesis, Mapping):
        raise ValueError("admitted coordinated ACT has no structured hypothesis")
    probe_task_key = hypothesis.get("probe_task_key")
    if not isinstance(probe_task_key, str) or not probe_task_key:
        raise ValueError("admitted coordinated ACT has no probe_task_key")
    targets = contract.get("target_task_keys")
    if not isinstance(targets, list) or probe_task_key not in targets:
        raise ValueError("coordinated ACT selected a non-target probe task")
    if not probe_task_key.startswith("qfbench:"):
        raise ValueError("this runner only dispatches QFBench probe tasks")
    return probe_task_key


def _qfbench_task_for_key(probe_task_key: str, tasks: tuple):
    benchmark, separator, task_id = probe_task_key.partition(":")
    if benchmark != "qfbench" or not separator or not task_id:
        raise ValueError("probe_task_key is not a QFBench task key")
    matches = [task for task in tasks if task.task_id == task_id]
    if len(matches) != 1:
        raise ValueError("probe_task_key does not resolve to one QFBench task")
    return matches[0]


def _materialize_coordinated_probe_worker(
    *, candidate: Path, destination: Path, hypothesis: Mapping[str, object]
) -> tuple[Path, int]:
    """Apply only the Evolver-authored probe directive and bounded turn budget."""

    experiment = hypothesis.get("experiment_spec")
    if not isinstance(experiment, Mapping):
        raise ValueError("coordinated ACT has no experiment_spec")
    if experiment.get("mode") != "from_scratch" or experiment.get(
        "seed_experience"
    ) is not None:
        raise ValueError("coordinated probe must run from_scratch without a seed")
    max_iterations = experiment.get("max_iterations")
    if type(max_iterations) is not int or not 1 <= max_iterations <= 12:
        raise ValueError("coordinated probe max_iterations must be in [1, 12]")
    instruction = experiment.get("worker_instruction")
    if not isinstance(instruction, str) or not instruction.strip():
        raise ValueError("coordinated probe has no Worker instruction")
    if destination.exists():
        raise ValueError("coordinated probe worker already exists")
    shutil.copytree(
        candidate,
        destination,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    agent = destination / "agent.yaml"
    text = agent.read_text(encoding="utf-8")
    text, count = re.subn(
        r"(?m)^max_iterations:\s*\d+\s*$",
        f"max_iterations: {max_iterations}",
        text,
        count=1,
    )
    if count != 1:
        raise ValueError("coordinated candidate has no max_iterations setting")
    agent.write_text(text, encoding="utf-8")
    prompt = destination / "systemprompt.md"
    prompt.write_text(
        prompt.read_text(encoding="utf-8").rstrip()
        + "\n\n## Evolver-authored bounded experiment directive\n\n"
        + instruction.strip()
        + "\n",
        encoding="utf-8",
    )
    return destination, max_iterations


def _stage_evidence(record, run_dir: Path):
    """Copy authorized evidence under the exact run root before sandbox use."""

    destination = run_dir / "authorized-evidence"
    if destination.exists():
        staged = authorize_evidence_tree(destination)
        if staged.sha256 != record.sha256 or staged.members != record.members:
            raise ValueError("staged evidence differs from the authorized source")
        return staged

    temporary = run_dir / "authorized-evidence.tmp"
    if temporary.exists():
        raise ValueError("temporary staged evidence already exists")
    try:
        shutil.copytree(record.root, temporary, symlinks=False)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    staged = authorize_evidence_tree(destination)
    if staged.sha256 != record.sha256 or staged.members != record.members:
        raise ValueError("staged evidence differs from the authorized source")
    return staged


def _cost(run_dir: Path) -> dict[str, object]:
    completed = []
    downstream_deliveries = []
    noncompleted = []
    for path in sorted(run_dir.glob("attempts/*/proxy-audit.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("request_state") == "completed":
                completed.append(record)
            elif (
                record.get("request_state") == "quarantined"
                and record.get("failure_class") == "downstream_delivery"
            ):
                downstream_deliveries.append(record)
            else:
                noncompleted.append(record)
    billable = completed + downstream_deliveries
    costs = [record.get("provider_cost_usd") for record in billable]
    tokens = [record.get("total_tokens") for record in billable]
    return {
        "completed_request_count": len(completed),
        "downstream_delivery_request_count": len(downstream_deliveries),
        "noncompleted_request_count": len(noncompleted),
        "provider_cost_usd": (
            sum(float(value) for value in costs)
            if billable and all(isinstance(value, (int, float)) for value in costs)
            else None
        ),
        "total_tokens": (
            sum(int(value) for value in tokens)
            if billable and all(isinstance(value, int) for value in tokens)
            else None
        ),
        "missing_cost_count": sum(value is None for value in costs),
        "missing_token_count": sum(value is None for value in tokens),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qfbench-root", type=Path, required=True)
    parser.add_argument("--qfbench-manifest", type=Path, required=True)
    parser.add_argument("--rootless-config", type=Path, required=True)
    parser.add_argument("--rootless-image-set-manifest", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--backbone", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--evolver-dir", type=Path, required=True)
    parser.add_argument("--arm", type=_arm, required=True)
    parser.add_argument(
        "--a6-manifest",
        type=Path,
        help="Frozen A6 protocol manifest; mandatory for every A6 invocation.",
    )
    parser.add_argument(
        "--a6-prelaunch-identity",
        type=Path,
        help="Materialized external A6 launch-identity record.",
    )
    parser.add_argument(
        "--a6-source-release-root",
        type=Path,
        help="Exact clean source release from which this runner is executing.",
    )
    parser.add_argument(
        "--a6-source-release-manifest",
        type=Path,
        help="External deterministic member manifest for the A6 source release.",
    )
    parser.add_argument(
        "--reasoning-effort",
        choices=("none", "minimal", "low", "medium", "high", "xhigh"),
        default="none",
        help="Deliberation request supported by the selected model route.",
    )
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument(
        "--dispatch-selected-probe",
        action="store_true",
        help=(
            "After an admitted coordinated ACT, evaluate exactly the Evolver-"
            "selected probe task. Protection remains a separate conditional run."
        ),
    )
    parser.add_argument("--approve-external-run", action="store_true")
    return parser


def _a6_static_launch_identity(
    *,
    args: argparse.Namespace,
    stage: str,
    config: object,
    execution_root: Path | None = None,
) -> dict[str, object] | None:
    """Bind A6 inputs to the exact clean release before runtime construction."""

    argument_names = (
        "a6_manifest",
        "a6_prelaunch_identity",
        "a6_source_release_root",
        "a6_source_release_manifest",
    )
    values = {name: getattr(args, name, None) for name in argument_names}
    normalized_arm = str(args.arm).casefold().replace("_", "-")
    a6_arm = normalized_arm in {"a6-r", "a6-e", "a6-ec"}
    if (stage == "A6") is not a6_arm:
        raise ValueError("A6 arm and evidence-contract stage must agree")
    if stage != "A6":
        if any(value is not None for value in values.values()):
            raise ValueError("A6 identity arguments are invalid for a non-A6 run")
        return None
    missing = [name for name, value in values.items() if value is None]
    if missing:
        raise ValueError(
            "A6 invocation is missing fail-closed identity arguments: "
            + ", ".join(missing)
        )

    expected_root = (
        execution_root.resolve()
        if execution_root is not None
        else Path(__file__).resolve().parents[1]
    )
    release_root_raw = Path(values["a6_source_release_root"]).expanduser()
    if release_root_raw.is_symlink() or release_root_raw.resolve() != expected_root:
        raise ValueError(
            "A6 source release root differs from the executing runner source"
        )
    protocol_path = Path(values["a6_manifest"]).expanduser()
    expected_protocol_path = (
        expected_root / "data/qfbench/MANIFEST_A6_EXPANDED_CANARY.json"
    )
    if protocol_path.is_symlink() or protocol_path.resolve() != expected_protocol_path:
        raise ValueError("A6 protocol manifest is not the executing release manifest")
    identity_path = Path(values["a6_prelaunch_identity"]).expanduser()
    if identity_path.is_symlink() or not identity_path.is_file():
        raise ValueError("A6 prelaunch identity record is unavailable")

    frozen = _json(protocol_path)
    if frozen.get("stage") != "A6":
        raise ValueError("A6 protocol manifest has the wrong stage")
    freeze_spec = frozen.get("prelaunch_identity_freeze")
    record_path = (
        freeze_spec.get("record_path")
        if isinstance(freeze_spec, Mapping)
        else None
    )
    if not isinstance(record_path, str) or not record_path:
        raise ValueError("A6 prelaunch identity record path is not frozen")
    expected_identity_path = (expected_root / record_path).resolve()
    if identity_path.resolve() != expected_identity_path:
        raise ValueError(
            "A6 prelaunch identity path differs from the external frozen record"
        )
    try:
        expected_identity_path.relative_to(expected_root)
    except ValueError:
        pass
    else:
        raise ValueError("A6 prelaunch identity record must be outside source release")
    freeze_record = _json(identity_path)
    source_release = validate_a6_source_release(
        release_root_raw,
        Path(values["a6_source_release_manifest"]).expanduser(),
    )
    public_role = verify_role_root(config.public_root, "public")
    trusted_role = verify_role_root(config.trusted_root, "trusted-verifier")
    panel = frozen.get("panel")
    panel_task_ids = panel.get("task_ids") if isinstance(panel, Mapping) else None
    benchmark_commit = frozen.get("benchmark_commit")
    if not isinstance(panel_task_ids, list) or not isinstance(
        benchmark_commit, str
    ):
        raise ValueError("A6 frozen public-contract source panel is invalid")
    public_contract_source = public_contract_source_identity(
        public_task_root=config.public_root,
        task_ids=panel_task_ids,
        benchmark_commit=benchmark_commit,
    )
    if (
        public_contract_source["public_task_role_manifest_sha256"]
        != public_role.manifest_sha256
    ):
        raise ValueError("A6 public-contract source role identity is inconsistent")
    provider_route = rootless_model_route_identity(
        upstream_base_url=config.upstream_base_url,
        allowed_path_prefix=config.allowed_path_prefix,
        allowed_model=config.allowed_model,
        required_provider=config.required_provider,
    )
    return {
        "frozen": frozen,
        "freeze_record": freeze_record,
        "protocol_manifest_path": protocol_path,
        "identity_record_sha256": _sha256(identity_path),
        "source_release_manifest_sha256": source_release["manifest_sha256"],
        "source_release_member_count": source_release["member_count"],
        "public_contract_source": public_contract_source,
        "effective_identity": {
            "rootless_config_sha256": _sha256(args.rootless_config.resolve()),
            "image_set_manifest_sha256": _sha256(
                args.rootless_image_set_manifest.resolve()
            ),
            "public_task_role_manifest_sha256": public_role.manifest_sha256,
            "trusted_task_role_manifest_sha256": trusted_role.manifest_sha256,
            "scheduler_epoch": config.scheduler_epoch,
            "provider_route_identity_sha256": provider_route,
            "a6_source_release_sha256": source_release["tree_sha256"],
        },
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if _RUN_ID.fullmatch(args.run_id) is None:
        raise ValueError("run ID is unsafe")
    if (
        not args.preflight_only
        and not args.approve_external_run
        and os.environ.get("QEA_PAID_EVAL_AUTO_APPROVE") != "1"
    ):
        raise ValueError("external evolver/model execution was not approved")

    snapshot = load_qfbench_baseline_snapshot(
        args.qfbench_root.resolve(), manifest_path=args.qfbench_manifest.resolve()
    )
    full_panel = snapshot.primary.tasks + snapshot.diagnostic.tasks
    config = load_rootless_full_harness_config(args.rootless_config.resolve())
    evidence = authorize_evidence_tree(args.evidence.resolve())
    diagnosis = _diagnosis(evidence.root, args.arm)
    backbone = args.backbone.resolve()
    if not backbone.is_dir():
        raise ValueError("backbone directory is unavailable")
    evolver_source = args.evolver_dir.resolve()
    if not evolver_source.is_dir():
        raise ValueError("evolver directory is unavailable")
    if not config.required_provider:
        raise ValueError("discovery runs require an exact model provider route")
    a6_identity = _a6_static_launch_identity(
        args=args,
        stage=str(diagnosis["stage"]),
        config=config,
    )
    evidence_contract = _json(evidence.root / "contract.json")
    if args.dispatch_selected_probe and evidence_contract.get("stage") != (
        "COORDINATED_BREADTH"
    ):
        raise ValueError(
            "selected-probe dispatch is only valid for coordinated breadth"
        )
    if a6_identity is not None:
        validate_a6_evidence_contract(
            frozen=a6_identity["frozen"],
            contract=evidence_contract,
            arm=args.arm,
            prelaunch_identity=a6_identity["freeze_record"],
            identity_record_sha256=a6_identity["identity_record_sha256"],
            public_contract_source=a6_identity["public_contract_source"],
        )
        if evidence_contract["public_contract_evidence"] is True:
            validate_public_contract_index(
                evidence_root=evidence.root,
                public_task_root=config.public_root,
                task_ids=evidence_contract["train_task_ids"],
                benchmark_commit=snapshot.commit,
            )
        elif (evidence.root / "contracts").exists():
            raise ValueError("A6-R evidence unexpectedly exposes public contracts")

    results_root = args.results_dir.expanduser().resolve()
    run_dir = results_root / args.run_id
    evolver_profile = materialize_evolver_profile(
        evolver_source,
        run_dir / "inputs" / "evolver",
        model=config.allowed_model,
        provider=config.required_provider,
        reasoning_effort=args.reasoning_effort,
    )
    evolver_dir = Path(evolver_profile.materialized_dir)
    plan = {
        "schema_version": 1,
        "purpose": "self-hosted model-configurable quant discovery canary",
        "run_id": args.run_id,
        "arm": args.arm,
        "benchmark_commit": snapshot.commit,
        "backbone": str(backbone),
        "evidence": str(evidence.root),
        "evidence_sha256": evidence.sha256,
        "evidence_members": list(evidence.members),
        "evidence_contract": evidence_contract,
        "evolver_source_dir": str(evolver_source),
        "evolver_runtime_profile": profile_as_dict(evolver_profile),
        "qfbench_manifest_sha256": _sha256(args.qfbench_manifest.resolve()),
        "rootless_config_sha256": _sha256(args.rootless_config.resolve()),
        "image_set_sha256": _sha256(args.rootless_image_set_manifest.resolve()),
        "model_route": {
            "allowed_model": config.allowed_model,
            "required_provider": config.required_provider,
            "identity_sha256": rootless_model_route_identity(
                upstream_base_url=config.upstream_base_url,
                allowed_path_prefix=config.allowed_path_prefix,
                allowed_model=config.allowed_model,
                required_provider=config.required_provider,
            ),
        },
        "selected_worker_probe_dispatch_enabled": args.dispatch_selected_probe,
        "max_worker_probes_in_this_run": (
            1 if args.dispatch_selected_probe else 0
        ),
    }
    if a6_identity is not None:
        freeze_record = a6_identity["freeze_record"]
        plan["a6_prelaunch_identity"] = {
            "identity_record_sha256": a6_identity["identity_record_sha256"],
            "materialized_launch_identity_sha256": freeze_record.get(
                "materialized_launch_identity_sha256"
            ),
            "protocol_manifest_sha256": freeze_record.get(
                "protocol_manifest_sha256"
            ),
            "source_release_manifest_sha256": a6_identity[
                "source_release_manifest_sha256"
            ],
            "source_release_tree_sha256": a6_identity["effective_identity"][
                "a6_source_release_sha256"
            ],
            "source_release_member_count": a6_identity[
                "source_release_member_count"
            ],
            "public_task_role_manifest_sha256": a6_identity[
                "public_contract_source"
            ]["public_task_role_manifest_sha256"],
            "public_contract_source_members_sha256": a6_identity[
                "public_contract_source"
            ]["instruction_members_sha256"],
        }
    plan_path = run_dir / "pilot-plan.json"
    if plan_path.is_file() and _json(plan_path) != plan:
        raise ValueError("persisted discovery-pilot plan differs")
    _atomic_json(plan_path, plan)
    if a6_identity is not None and not args.preflight_only:
        assert_a6_model_boundary_unclaimed(run_dir)

    runtime = build_rootless_full_harness_runtime(
        config=config,
        image_set_manifest=args.rootless_image_set_manifest.resolve(),
        benchmark_commit=snapshot.commit,
        tasks=full_panel,
        run_id=args.run_id,
        results_root=results_root,
        include_evolver=True,
    )
    try:
        if a6_identity is not None:
            effective_identity = dict(a6_identity["effective_identity"])
            effective_identity["scheduler_identity_sha256"] = (
                runtime.scheduler_identity_digest
            )
            validate_a6_prelaunch_identity(
                frozen=a6_identity["frozen"],
                freeze_record=a6_identity["freeze_record"],
                protocol_manifest_path=a6_identity["protocol_manifest_path"],
                effective_identity=effective_identity,
            )
        if args.preflight_only:
            report = {
                "schema_version": 1,
                "run_id": args.run_id,
                "arm": args.arm,
                "status": "preflight_complete",
                "model_request_count": 0,
                "evidence_sha256": evidence.sha256,
                "runtime_identity_sha256": runtime.runtime_identity_digest,
                "scheduler_identity_sha256": runtime.scheduler_identity_digest,
                "a6_prelaunch_identity_validated": a6_identity is not None,
                "a6_prelaunch_identity": (
                    plan.get("a6_prelaunch_identity")
                    if a6_identity is not None
                    else None
                ),
                "selected_worker_probe_dispatch_enabled": (
                    args.dispatch_selected_probe
                ),
            }
            _atomic_json(run_dir / "pilot-preflight.json", report)
            _atomic_json(run_dir / "pilot-progress.json", report)
            print(json.dumps(report, sort_keys=True, indent=2))
            return 0

        _atomic_json(
            run_dir / "pilot-progress.json",
            {
                "schema_version": 1,
                "run_id": args.run_id,
                "arm": args.arm,
                "status": "proposing",
            },
        )
        staged_evidence = _stage_evidence(evidence, run_dir)
        if runtime.proposer is None:
            raise RuntimeError("discovery pilot runtime has no evolver proposer")
        if a6_identity is not None:
            claim_a6_model_boundary(
                run_dir,
                plan_path=plan_path,
                run_id=args.run_id,
                run_kind="discovery",
                arm_labels=(args.arm,),
                identity_record_sha256=str(
                    a6_identity["identity_record_sha256"]
                ),
                materialized_launch_identity_sha256=str(
                    a6_identity["freeze_record"].get(
                        "materialized_launch_identity_sha256"
                    )
                ),
            )
        proposal = runtime.proposer.propose(
            candidate_dir=backbone,
            evidence_dir=staged_evidence,
            evolver_dir=evolver_dir,
            diagnosis=diagnosis,
            iteration=1,
            run_id=args.run_id,
            run_dir=run_dir,
        )
        proposal_summary = _json(proposal.summary_uri)
        discovery_state = proposal_summary.get("discovery_hypothesis")
        discovery_state = (
            dict(discovery_state) if isinstance(discovery_state, Mapping) else {}
        )
        prediction = _json(proposal.prediction_uri)
        decision = _terminal_decision(discovery_state, prediction)
        hypothesis = discovery_state.get("hypothesis")
        hypothesis = dict(hypothesis) if isinstance(hypothesis, Mapping) else {}
        declared_roles = hypothesis.get("components")
        declared_roles = (
            [str(value) for value in declared_roles]
            if isinstance(declared_roles, list)
            else []
        )
        mutation_metrics = measure_mutation(
            before_root=backbone,
            after_root=proposal.candidate_dir,
            declared_roles=declared_roles,
        )
        admission = _candidate_admission(
            decision=decision,
            backbone=backbone,
            candidate=proposal.candidate_dir,
        )
        proposal_cost = _cost(run_dir)
        worker_probe: dict[str, object] = {
            "requested": args.dispatch_selected_probe,
            "dispatched": False,
            "probe_task_key": None,
            "reason": "selected-probe dispatch was not enabled",
        }
        if args.dispatch_selected_probe:
            probe_task_key = _coordinated_probe_task_key(
                contract=evidence_contract,
                decision=decision,
                admission=admission,
                discovery_state=discovery_state,
            )
            if probe_task_key is None:
                worker_probe["reason"] = (
                    "no admitted coordinated ACT selected a Worker probe"
                )
            else:
                selected_task = _qfbench_task_for_key(
                    probe_task_key, tuple(full_panel)
                )
                probe_worker, probe_max_iterations = (
                    _materialize_coordinated_probe_worker(
                        candidate=proposal.candidate_dir,
                        destination=run_dir / "inputs/coordinated-probe-worker",
                        hypothesis=hypothesis,
                    )
                )
                summary = runtime.evaluator.evaluate(
                    worker_dir=probe_worker,
                    tasks=(selected_task,),
                    split="coordinated-probe",
                    checkpoint="mt-selected-probe",
                    run_dir=run_dir,
                )
                worker_probe = {
                    "requested": True,
                    "dispatched": True,
                    "probe_task_key": probe_task_key,
                    "task_id": selected_task.task_id,
                    "task_count": 1,
                    "probe_worker_dir": str(probe_worker),
                    "max_iterations": probe_max_iterations,
                    "experiment_directive_applied": True,
                    "summary": _summary_payload(summary),
                }
        proposal_payload = {
            "decision": decision,
            "candidate_dir": str(proposal.candidate_dir),
            "candidate_digest": proposal.candidate_digest,
            "admission": admission,
            "diff": dir_unified_diff(backbone, proposal.candidate_dir),
            "prediction": prediction,
            "access_summary": _json(proposal.access_summary_uri),
            "summary": proposal_summary,
            "mutation_metrics": mutation_metrics,
            "worker_probe": worker_probe,
        }
    finally:
        runtime.close()

    run_cost = _cost(run_dir)
    wall_seconds = proposal_summary.get("secs")
    wall_seconds = (
        float(wall_seconds)
        if isinstance(wall_seconds, (int, float)) and not isinstance(wall_seconds, bool)
        else None
    )
    requests = int(proposal_cost["completed_request_count"]) + int(
        proposal_cost["downstream_delivery_request_count"]
    )
    proposal_payload["candidate_generation_throughput"] = {
        "wall_seconds": wall_seconds,
        "completed_request_count": proposal_cost["completed_request_count"],
        "downstream_delivery_request_count": proposal_cost[
            "downstream_delivery_request_count"
        ],
        "noncompleted_request_count": proposal_cost["noncompleted_request_count"],
        "billable_or_delivered_request_count": requests,
        "total_tokens": proposal_cost["total_tokens"],
        "provider_cost_usd": proposal_cost["provider_cost_usd"],
        "requests_per_second": (
            requests / wall_seconds if wall_seconds and wall_seconds > 0 else None
        ),
        "tokens_per_second": (
            int(proposal_cost["total_tokens"]) / wall_seconds
            if wall_seconds
            and wall_seconds > 0
            and isinstance(proposal_cost["total_tokens"], int)
            else None
        ),
        "measurement_only": True,
    }
    report = {
        "schema_version": 1,
        "run_id": args.run_id,
        "arm": args.arm,
        "status": "complete",
        "proposal": proposal_payload,
        "proposal_cost": proposal_cost,
        "cost": run_cost,
        "worker_evaluation_in_this_run": bool(
            proposal_payload["worker_probe"]["dispatched"]
        ),
    }
    if a6_identity is not None:
        report["a6_prelaunch_identity"] = {
            **plan["a6_prelaunch_identity"],
            "scheduler_identity_sha256": runtime.scheduler_identity_digest,
            "validated_before_first_model_call": True,
        }
    _atomic_json(run_dir / "proposal-report.json", proposal_payload)
    _atomic_json(run_dir / "pilot-report.json", report)
    _atomic_json(run_dir / "pilot-progress.json", report)
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
