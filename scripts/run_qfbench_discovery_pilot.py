#!/usr/bin/env python3
"""Run one proposal-only quant evolver discovery canary on rootless Docker."""

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

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.benchmarks.qfbench import load_qfbench_baseline_snapshot  # noqa: E402
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
from qea.rootless_full_harness import (  # noqa: E402
    build_rootless_full_harness_runtime,
    load_rootless_full_harness_config,
    rootless_model_route_identity,
)


_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")


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
    noncompleted = []
    for path in sorted(run_dir.glob("attempts/*/proxy-audit.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("request_state") == "completed":
                completed.append(record)
            else:
                noncompleted.append(record)
    costs = [record.get("provider_cost_usd") for record in completed]
    tokens = [record.get("total_tokens") for record in completed]
    return {
        "completed_request_count": len(completed),
        "noncompleted_request_count": len(noncompleted),
        "provider_cost_usd": (
            sum(float(value) for value in costs)
            if completed and all(isinstance(value, (int, float)) for value in costs)
            else None
        ),
        "total_tokens": (
            sum(int(value) for value in tokens)
            if completed and all(isinstance(value, int) for value in tokens)
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
    parser.add_argument("--arm", choices=("raw", "indexed"), required=True)
    parser.add_argument(
        "--reasoning-effort",
        choices=("none", "minimal", "low", "medium", "high", "xhigh"),
        default="none",
        help="Deliberation request supported by the selected model route.",
    )
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--approve-external-run", action="store_true")
    return parser


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
    backbone = args.backbone.resolve()
    if not backbone.is_dir():
        raise ValueError("backbone directory is unavailable")
    evolver_source = args.evolver_dir.resolve()
    if not evolver_source.is_dir():
        raise ValueError("evolver directory is unavailable")
    if not config.required_provider:
        raise ValueError("discovery runs require an exact model provider route")

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
        "worker_evaluation_in_this_run": False,
    }
    plan_path = run_dir / "pilot-plan.json"
    if plan_path.is_file() and _json(plan_path) != plan:
        raise ValueError("persisted discovery-pilot plan differs")
    _atomic_json(plan_path, plan)

    runtime = build_rootless_full_harness_runtime(
        config=config,
        image_set_manifest=args.rootless_image_set_manifest.resolve(),
        benchmark_commit=snapshot.commit,
        tasks=full_panel,
        run_id=args.run_id,
        results_root=results_root,
        include_evolver=True,
    )
    if args.preflight_only:
        runtime.close()
        report = {
            "schema_version": 1,
            "run_id": args.run_id,
            "arm": args.arm,
            "status": "preflight_complete",
            "model_request_count": 0,
            "evidence_sha256": evidence.sha256,
            "runtime_identity_sha256": runtime.runtime_identity_digest,
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
    try:
        if runtime.proposer is None:
            raise RuntimeError("discovery pilot runtime has no evolver proposer")
        proposal = runtime.proposer.propose(
            candidate_dir=backbone,
            evidence_dir=staged_evidence,
            evolver_dir=evolver_dir,
            diagnosis={
                "stage": "DISCOVERY",
                "arm": args.arm,
                "instruction": (
                    "Discover and test one causal harness mechanism from the "
                    "authorized post-A3 public evidence. The coordinator prescribes "
                    "no component, file, root cause, or implementation."
                ),
            },
            iteration=1,
            run_id=args.run_id,
            run_dir=run_dir,
        )
        try:
            admission = asdict(
                admit_candidate(
                    backbone, proposal.candidate_dir, AdmissionPolicy.qfbench_full()
                )
            )
        except CandidateAdmissionError as exc:
            admission = {
                "admitted": False,
                "failure": f"{type(exc).__name__}: {exc}",
            }
        proposal_payload = {
            "candidate_dir": str(proposal.candidate_dir),
            "candidate_digest": proposal.candidate_digest,
            "admission": admission,
            "diff": dir_unified_diff(backbone, proposal.candidate_dir),
            "prediction": _json(proposal.prediction_uri),
            "access_summary": _json(proposal.access_summary_uri),
            "summary": _json(proposal.summary_uri),
        }
    finally:
        runtime.close()

    report = {
        "schema_version": 1,
        "run_id": args.run_id,
        "arm": args.arm,
        "status": "complete",
        "proposal": proposal_payload,
        "cost": _cost(run_dir),
        "worker_evaluation_in_this_run": False,
    }
    _atomic_json(run_dir / "proposal-report.json", proposal_payload)
    _atomic_json(run_dir / "pilot-report.json", report)
    _atomic_json(run_dir / "pilot-progress.json", report)
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
