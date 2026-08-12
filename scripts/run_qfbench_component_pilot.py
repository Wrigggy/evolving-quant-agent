#!/usr/bin/env python3
"""Evaluate a few worker harness arms on an exact QFBench task subset.

The rootless runtime is still assembled against the immutable full 85-task image
and material panel. Only the requested public tasks are executed. This keeps the
official verifier firewall and image identities unchanged while making an A1-A3
mechanism canary affordable and resumable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Mapping

if __name__ == "__main__":
    # A6 releases are content-addressed and must not be mutated by imports.
    sys.dont_write_bytecode = True

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.a6_source_release import validate_a6_source_release  # noqa: E402
from qea.a6_model_boundary import (  # noqa: E402
    assert_a6_model_boundary_unclaimed,
    claim_a6_model_boundary,
)
from qea.benchmarks.qfbench import load_qfbench_baseline_snapshot  # noqa: E402
from qea.candidate_admission import AdmissionPolicy, admit_candidate  # noqa: E402
from qea.loop_benchmark import hash_worker_directory  # noqa: E402
from qea.qfbench_a6 import validate_a6_prelaunch_identity  # noqa: E402
from qea.qfbench_baseline import (  # noqa: E402
    audit_fixed_checkpoint_proxy_costs,
    audit_fixed_checkpoints_proxy_costs,
)
from qea.rootless_full_harness import (  # noqa: E402
    build_rootless_full_harness_runtime,
    load_rootless_full_harness_config,
    rootless_model_route_identity,
)
from qea.rootless_images import verify_role_root  # noqa: E402


_LABEL = re.compile(r"[a-z0-9][a-z0-9_-]{0,47}\Z")
_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_A6_TOKEN = re.compile(r"(?:^|[._-])a6(?:[._-]|$)", re.IGNORECASE)
_A6_IDENTITY_ARGUMENTS = (
    "a6_manifest",
    "a6_prelaunch_identity",
    "a6_source_release_root",
    "a6_source_release_manifest",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")
    os.replace(temporary, path)


def _canonical_json_value(payload: object) -> object:
    """Return the exact JSON value that ``_atomic_json`` will persist."""

    return json.loads(json.dumps(payload, sort_keys=True))


def _json(path: Path) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"required regular JSON file is unavailable: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _arm(value: str) -> tuple[str, Path]:
    label, separator, raw_path = value.partition("=")
    if not separator or _LABEL.fullmatch(label) is None:
        raise argparse.ArgumentTypeError("arm must be LABEL=PATH with a safe label")
    path = Path(raw_path).expanduser().resolve()
    if not path.is_dir():
        raise argparse.ArgumentTypeError(f"worker arm is unavailable: {path}")
    return label, path


def _summary_payload(summary) -> dict[str, object]:
    return {
        "scores": [asdict(score) for score in summary.scores],
        "task_rewards": dict(summary.task_rewards),
        "domain_scores": dict(summary.domain_scores),
        "task_mean": summary.task_mean,
        "overall": summary.overall,
    }


def _activation_payload(run_dir: Path, checkpoint: str, token: str | None) -> dict:
    attempts: list[dict[str, object]] = []
    for attempt_path in sorted(run_dir.glob("attempts/*/attempt.json")):
        attempt = json.loads(attempt_path.read_text())
        if attempt.get("checkpoint") != checkpoint:
            continue
        trace_path = attempt_path.with_name("raw-trace.jsonl")
        trace = trace_path.read_text(errors="replace") if trace_path.is_file() else ""
        marker = (
            token is not None
            and token in trace
            and ("<SkillDetails>" in trace or "Found the skill details" in trace)
        )
        attempts.append({
            "attempt_id": attempt.get("attempt_id"),
            "task_id": attempt.get("task_id"),
            "trace_path": trace_path.relative_to(run_dir).as_posix(),
            "activation_token": token,
            "activated": marker,
            "trace_sha256": _sha256(trace_path) if trace_path.is_file() else None,
        })
    return {
        "checkpoint": checkpoint,
        "attempts": attempts,
        "activation_count": sum(bool(item["activated"]) for item in attempts),
    }


def _cost_payload(
    run_dir: Path,
    *,
    checkpoints: tuple[str, ...],
    expected_attempts: int,
) -> dict[str, object]:
    """Return the canonical fixed-panel request/token/cost audit."""

    if len(checkpoints) == 1:
        return audit_fixed_checkpoint_proxy_costs(
            run_dir,
            expected_attempts=expected_attempts,
            checkpoint=checkpoints[0],
            split="mechanism-pilot",
        )
    return audit_fixed_checkpoints_proxy_costs(
        run_dir,
        expected_attempts=expected_attempts,
        checkpoints=checkpoints,
        split="mechanism-pilot",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qfbench-root", type=Path, required=True)
    parser.add_argument("--qfbench-manifest", type=Path, required=True)
    parser.add_argument("--rootless-config", type=Path, required=True)
    parser.add_argument("--rootless-image-set-manifest", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--seed-worker", type=Path, required=True)
    parser.add_argument("--arm", action="append", type=_arm, required=True)
    parser.add_argument("--task-id", action="append", required=True)
    parser.add_argument("--checkpoint-prefix", default="component-pilot")
    parser.add_argument("--activation-token")
    parser.add_argument("--worker-concurrency", type=int)
    parser.add_argument("--verifier-concurrency", type=int)
    parser.add_argument(
        "--a6-run-kind",
        choices=("seed", "candidate"),
        help="A6 full-panel seed or candidate evaluation; enables fail-closed identity checks.",
    )
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
        "--preflight-only",
        action="store_true",
        help="Validate and materialize no-model runtime identity, then exit.",
    )
    parser.add_argument("--approve-external-run", action="store_true")
    return parser


def _panel_task_ids(frozen: Mapping[str, object]) -> tuple[str, ...]:
    panel = frozen.get("panel")
    if not isinstance(panel, Mapping):
        raise ValueError("A6 protocol manifest has no panel")
    raw_task_ids = panel.get("task_ids")
    if not isinstance(raw_task_ids, list) or not raw_task_ids:
        raise ValueError("A6 protocol panel task_ids must be a non-empty array")
    task_ids = tuple(raw_task_ids)
    if any(not isinstance(task_id, str) or not task_id for task_id in task_ids):
        raise ValueError("A6 protocol panel contains an invalid task ID")
    if len(task_ids) != len(set(task_ids)):
        raise ValueError("A6 protocol panel task IDs are not unique")

    sentinel_items = panel.get("sentinels")
    if sentinel_items is None:
        sentinel_items = panel.get("coverage_sentinels", [])
    role_items = (
        panel.get("targets", []),
        panel.get("protections", []),
        sentinel_items,
    )
    derived: list[str] = []
    for items in role_items:
        if not isinstance(items, list):
            raise ValueError("A6 protocol panel role is not an array")
        for item in items:
            if not isinstance(item, Mapping):
                raise ValueError("A6 protocol panel role item is invalid")
            task_id = item.get("task_id")
            if not isinstance(task_id, str) or not task_id:
                raise ValueError("A6 protocol panel role item has no task ID")
            derived.append(task_id)
    if tuple(derived) != task_ids:
        raise ValueError("A6 protocol role order differs from panel task_ids")
    return task_ids


def _a6_component_launch_identity(
    *,
    args: argparse.Namespace,
    config: object,
    task_ids: tuple[str, ...],
    primary_task_ids: frozenset[str],
    benchmark_commit: str,
    seed_digest: str,
    arm_payloads: list[dict[str, object]],
    execution_root: Path | None = None,
) -> dict[str, object] | None:
    """Bind an A6 worker call to the frozen panel, seed, and clean release."""

    identity_values = {
        name: getattr(args, name, None) for name in _A6_IDENTITY_ARGUMENTS
    }
    run_kind = getattr(args, "a6_run_kind", None)
    labels = [str(item.get("label", "")) for item in arm_payloads]
    a6_named = any(
        _A6_TOKEN.search(value) is not None
        for value in (str(args.run_id), str(args.checkpoint_prefix), *labels)
    )
    a6_requested = run_kind is not None or any(
        value is not None for value in identity_values.values()
    )
    if not a6_requested:
        if a6_named:
            raise ValueError(
                "A6-named component run is missing fail-closed A6 identity arguments"
            )
        return None
    if run_kind not in {"seed", "candidate"}:
        raise ValueError("A6 invocation requires --a6-run-kind")
    missing = [name for name, value in identity_values.items() if value is None]
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
    release_root = Path(identity_values["a6_source_release_root"]).expanduser()
    if release_root.is_symlink() or release_root.resolve() != expected_root:
        raise ValueError(
            "A6 source release root differs from the executing runner source"
        )
    protocol_path = Path(identity_values["a6_manifest"]).expanduser()
    expected_protocol_path = (
        expected_root / "data/qfbench/MANIFEST_A6_EXPANDED_CANARY.json"
    )
    if protocol_path.is_symlink() or protocol_path.resolve() != expected_protocol_path:
        raise ValueError("A6 protocol manifest is not the executing release manifest")
    identity_path = Path(identity_values["a6_prelaunch_identity"]).expanduser()
    if identity_path.is_symlink() or not identity_path.is_file():
        raise ValueError("A6 prelaunch identity record is unavailable")

    frozen = _json(protocol_path)
    if frozen.get("stage") != "A6":
        raise ValueError("A6 protocol manifest has the wrong stage")
    identity_spec = frozen.get("prelaunch_identity_freeze")
    identity_spec = identity_spec if isinstance(identity_spec, Mapping) else {}
    record_path = identity_spec.get("record_path")
    if not isinstance(record_path, str) or not record_path:
        raise ValueError("A6 protocol has no external identity record path")
    expected_identity_path = (expected_root / record_path).resolve()
    if (
        expected_identity_path == expected_root
        or expected_root in expected_identity_path.parents
    ):
        raise ValueError("A6 prelaunch identity path is inside the source release")
    if identity_path.resolve() != expected_identity_path:
        raise ValueError("A6 prelaunch identity path differs from the protocol")
    if frozen.get("benchmark_commit") != benchmark_commit:
        raise ValueError("A6 protocol benchmark differs from the loaded snapshot")
    expected_tasks = _panel_task_ids(frozen)
    if task_ids != expected_tasks:
        raise ValueError("A6 component task list differs from the frozen full panel")
    if not set(task_ids).issubset(primary_task_ids):
        raise ValueError("A6 component panel contains a diagnostic or excluded task")
    baseline = frozen.get("baseline")
    if not isinstance(baseline, Mapping):
        raise ValueError("A6 protocol baseline contract is invalid")
    expected_seed_digest = baseline.get("seed_worker_digest")
    if seed_digest != expected_seed_digest:
        raise ValueError("A6 component seed worker differs from the frozen baseline")

    arm_digests = [str(item.get("worker_digest", "")) for item in arm_payloads]
    if run_kind == "seed":
        if (
            labels != ["seed-evidence"]
            or len(arm_payloads) != 1
            or arm_digests != [seed_digest]
        ):
            raise ValueError("A6 seed run requires exactly one frozen seed arm")
    else:
        design = frozen.get("discovery_design")
        design = design if isinstance(design, Mapping) else {}
        maximum = design.get("maximum_candidate_evaluations", 3)
        if isinstance(maximum, bool) or not isinstance(maximum, int) or maximum < 1:
            raise ValueError("A6 maximum candidate-evaluation count is invalid")
        if not 1 <= len(arm_payloads) <= maximum:
            raise ValueError("A6 candidate run exceeds its frozen portfolio cap")
        if len(arm_digests) != len(set(arm_digests)):
            raise ValueError("A6 candidate run contains duplicate worker digests")
        valid_labels = {"a6-r", "a6-e", "a6-ec"}
        if any(
            label.casefold().replace("_", "-") not in valid_labels
            for label in labels
        ):
            raise ValueError("A6 candidate arm label does not identify R, E, or EC")

    freeze_record = _json(identity_path)
    source_release = validate_a6_source_release(
        release_root,
        Path(identity_values["a6_source_release_manifest"]).expanduser(),
    )
    public_role = verify_role_root(config.public_root, "public")
    trusted_role = verify_role_root(config.trusted_root, "trusted-verifier")
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
        "run_kind": run_kind,
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
        raise ValueError("external worker/model execution was not approved")
    arms = tuple(args.arm)
    if len({label for label, _ in arms}) != len(arms):
        raise ValueError("worker arm labels must be unique")
    task_ids = tuple(args.task_id)
    if len(set(task_ids)) != len(task_ids):
        raise ValueError("task IDs must be unique")

    snapshot = load_qfbench_baseline_snapshot(
        args.qfbench_root,
        manifest_path=args.qfbench_manifest,
    )
    full_panel = snapshot.primary.tasks + snapshot.diagnostic.tasks
    tasks_by_id = {task.task_id: task for task in full_panel}
    missing = sorted(set(task_ids) - set(tasks_by_id))
    if missing:
        raise ValueError(f"unknown or excluded QFBench tasks: {missing}")
    selected_tasks = tuple(tasks_by_id[task_id] for task_id in task_ids)
    primary_task_ids = frozenset(task.task_id for task in snapshot.primary.tasks)

    seed = args.seed_worker.resolve()
    seed_digest = hash_worker_directory(seed)
    policy = AdmissionPolicy.qfbench_full()
    arm_payloads = []
    for label, worker in arms:
        admission = admit_candidate(seed, worker, policy)
        arm_payloads.append({
            "label": label,
            "worker_dir": str(worker),
            "worker_digest": hash_worker_directory(worker),
            "admission": asdict(admission),
        })

    config = load_rootless_full_harness_config(args.rootless_config)
    overrides = {}
    if args.worker_concurrency is not None:
        overrides["worker_concurrency"] = args.worker_concurrency
    if args.verifier_concurrency is not None:
        overrides["verifier_concurrency"] = args.verifier_concurrency
    if overrides:
        config = replace(config, **overrides)

    a6_identity = _a6_component_launch_identity(
        args=args,
        config=config,
        task_ids=task_ids,
        primary_task_ids=primary_task_ids,
        benchmark_commit=snapshot.commit,
        seed_digest=seed_digest,
        arm_payloads=arm_payloads,
    )

    results_root = args.results_dir.expanduser().resolve()
    run_dir = results_root / args.run_id
    plan = {
        "schema_version": 1,
        "run_id": args.run_id,
        "benchmark_commit": snapshot.commit,
        "task_ids": list(task_ids),
        "checkpoint_prefix": args.checkpoint_prefix,
        "activation_token": args.activation_token,
        "arms": arm_payloads,
        "qfbench_manifest_sha256": _sha256(args.qfbench_manifest.resolve()),
        "rootless_config_sha256": _sha256(args.rootless_config.resolve()),
        "image_set_sha256": _sha256(args.rootless_image_set_manifest.resolve()),
        "effective_runtime": {
            "allowed_model": config.allowed_model,
            "required_provider": config.required_provider,
            "scheduler_epoch": config.scheduler_epoch,
            "worker_concurrency": config.worker_concurrency,
            "verifier_concurrency": config.verifier_concurrency,
        },
    }
    if a6_identity is not None:
        freeze_record = a6_identity["freeze_record"]
        plan["a6_prelaunch_identity"] = {
            "run_kind": a6_identity["run_kind"],
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
        }
    plan = _canonical_json_value(plan)
    plan_path = run_dir / "pilot-plan.json"
    if plan_path.is_file() and json.loads(plan_path.read_text()) != plan:
        raise ValueError("existing pilot plan identity differs")
    _atomic_json(plan_path, plan)
    if a6_identity is not None and not args.preflight_only:
        assert_a6_model_boundary_unclaimed(run_dir)

    runtime = build_rootless_full_harness_runtime(
        config=config,
        image_set_manifest=args.rootless_image_set_manifest,
        benchmark_commit=snapshot.commit,
        tasks=full_panel,
        run_id=args.run_id,
        results_root=results_root,
        include_evolver=False,
    )
    summaries: dict[str, object] = {}
    activations: dict[str, object] = {}
    validated_a6_identity: dict[str, object] | None = None
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
            validated_a6_identity = {
                **dict(plan["a6_prelaunch_identity"]),
                "scheduler_identity_sha256": runtime.scheduler_identity_digest,
                "validated_before_first_evaluator_call": True,
            }
        if args.preflight_only:
            report = {
                "schema_version": 1,
                "run_id": args.run_id,
                "status": "preflight_complete",
                "model_request_count": 0,
                "runtime_identity_sha256": runtime.runtime_identity_digest,
                "scheduler_identity_sha256": runtime.scheduler_identity_digest,
                "a6_prelaunch_identity_validated": a6_identity is not None,
                "a6_prelaunch_identity": validated_a6_identity,
            }
            _atomic_json(run_dir / "pilot-preflight.json", report)
            _atomic_json(run_dir / "pilot-progress.json", report)
            print(json.dumps(report, sort_keys=True, indent=2))
            return 0
        if a6_identity is not None:
            boundary = claim_a6_model_boundary(
                run_dir,
                plan_path=plan_path,
                run_id=args.run_id,
                run_kind=str(a6_identity["run_kind"]),
                arm_labels=tuple(label for label, _ in arms),
                identity_record_sha256=str(
                    a6_identity["identity_record_sha256"]
                ),
                materialized_launch_identity_sha256=str(
                    a6_identity["freeze_record"].get(
                        "materialized_launch_identity_sha256"
                    )
                ),
            )
            if validated_a6_identity is not None:
                validated_a6_identity["model_boundary_marker_sha256"] = (
                    boundary["marker_sha256"]
                )
        for label, worker in arms:
            checkpoint = f"{args.checkpoint_prefix}-{label}"
            summary = runtime.evaluator.evaluate(
                worker_dir=worker,
                tasks=selected_tasks,
                split="mechanism-pilot",
                checkpoint=checkpoint,
                run_dir=run_dir,
            )
            summaries[label] = _summary_payload(summary)
            activations[label] = _activation_payload(
                run_dir, checkpoint, args.activation_token
            )
            _atomic_json(run_dir / "pilot-progress.json", {
                "schema_version": 1,
                "run_id": args.run_id,
                "completed_arms": list(summaries),
                "summaries": summaries,
                "activations": activations,
                "status": "running",
            })
    finally:
        runtime.close()

    report = {
        "schema_version": 1,
        "run_id": args.run_id,
        "status": "complete",
        "task_ids": list(task_ids),
        "summaries": summaries,
        "activations": activations,
        "cost": _cost_payload(
            run_dir,
            checkpoints=tuple(
                f"{args.checkpoint_prefix}-{label}" for label, _ in arms
            ),
            expected_attempts=len(task_ids) * len(arms),
        ),
    }
    if validated_a6_identity is not None:
        report["a6_prelaunch_identity"] = validated_a6_identity
    _atomic_json(run_dir / "pilot-report.json", report)
    _atomic_json(run_dir / "pilot-progress.json", report)
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
