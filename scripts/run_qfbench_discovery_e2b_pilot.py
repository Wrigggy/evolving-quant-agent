#!/usr/bin/env python3
"""Run one proposal-only quant discovery canary in an E2B evolver sandbox."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import asdict
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.candidate_admission import (  # noqa: E402
    AdmissionPolicy,
    CandidateAdmissionError,
    admit_candidate,
)
from qea.e2b_lease import E2BLeasePool  # noqa: E402
from qea.evolve_runtime import dir_unified_diff  # noqa: E402
from qea.evolution_evidence import authorize_evidence_tree  # noqa: E402
from qea.executors.e2b_evolver import (  # noqa: E402
    E2BEvolverConfig,
    E2BFullHarnessProposer,
)
from run import load_evolver_template  # noqa: E402


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


def _model_env() -> dict[str, str]:
    key = os.environ.get("LLM_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise ValueError("LLM_API_KEY or OPENROUTER_API_KEY is required")
    base_url = os.environ.get(
        "LLM_BASE_URL",
        os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
    )
    model = os.environ.get("LLM_MODEL", "openai/gpt-5.4")
    if base_url.rstrip("/") != "https://openrouter.ai/api/v1":
        raise ValueError("discovery E2B canary requires the exact OpenRouter base URL")
    if model != "openai/gpt-5.4":
        raise ValueError("discovery E2B canary requires openai/gpt-5.4")
    return {
        "LLM_API_KEY": key,
        "LLM_BASE_URL": "https://openrouter.ai/api/v1",
        "LLM_MODEL": model,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--backbone", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--evolver-dir", type=Path, required=True)
    parser.add_argument("--evolver-template-manifest", type=Path, required=True)
    parser.add_argument("--benchmark-commit", required=True)
    parser.add_argument("--arm", choices=("raw", "indexed"), required=True)
    parser.add_argument("--timeout-seconds", type=int, default=3_600)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--approve-external-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if _RUN_ID.fullmatch(args.run_id) is None:
        raise ValueError("run ID is unsafe")
    if args.timeout_seconds < 300 or args.timeout_seconds > 7_200:
        raise ValueError("timeout must be from 300 through 7200 seconds")
    if (
        not args.preflight_only
        and not args.approve_external_run
        and os.environ.get("QEA_PAID_EVAL_AUTO_APPROVE") != "1"
    ):
        raise ValueError("external evolver/model execution was not approved")

    evidence = authorize_evidence_tree(args.evidence.resolve())
    backbone = args.backbone.resolve()
    evolver_dir = args.evolver_dir.resolve()
    if not backbone.is_dir() or not evolver_dir.is_dir():
        raise ValueError("backbone or evolver directory is unavailable")
    template_manifest = args.evolver_template_manifest.resolve()
    template, template_identity = load_evolver_template(
        template_manifest, benchmark_commit=args.benchmark_commit
    )
    results_root = args.results_dir.expanduser().resolve()
    run_dir = results_root / args.run_id
    plan = {
        "schema_version": 1,
        "purpose": "exploratory E2B proposal-only discovery canary",
        "run_id": args.run_id,
        "arm": args.arm,
        "benchmark_commit": args.benchmark_commit,
        "backbone": str(backbone),
        "evidence": str(evidence.root),
        "evidence_sha256": evidence.sha256,
        "evidence_members": list(evidence.members),
        "evolver_dir": str(evolver_dir),
        "evolver_template": template,
        "evolver_template_identity_sha256": template_identity,
        "evolver_template_manifest_sha256": _sha256(template_manifest),
        "model_route": {
            "base_url": "https://openrouter.ai/api/v1",
            "model": "openai/gpt-5.4",
            "reasoning_effort": "xhigh",
            "provider_selection": "OpenRouter balanced with provider fallback",
        },
        "timeout_seconds": args.timeout_seconds,
        "worker_evaluation_in_this_run": False,
    }
    plan_path = run_dir / "pilot-plan.json"
    if plan_path.is_file() and _json(plan_path) != plan:
        raise ValueError("persisted E2B discovery-pilot plan differs")
    _atomic_json(plan_path, plan)
    if args.preflight_only:
        report = {
            "schema_version": 1,
            "run_id": args.run_id,
            "arm": args.arm,
            "status": "preflight_complete",
            "model_request_count": 0,
            "evidence_sha256": evidence.sha256,
            "evolver_template_identity_sha256": template_identity,
        }
        _atomic_json(run_dir / "pilot-preflight.json", report)
        _atomic_json(run_dir / "pilot-progress.json", report)
        print(json.dumps(report, sort_keys=True, indent=2))
        return 0

    model_env = _model_env()
    if not os.environ.get("E2B_API_KEY"):
        raise ValueError("E2B_API_KEY is required")
    _atomic_json(
        run_dir / "pilot-progress.json",
        {
            "schema_version": 1,
            "run_id": args.run_id,
            "arm": args.arm,
            "status": "proposing",
        },
    )
    leases = E2BLeasePool(run_dir / ".e2b-leases", max_leases=1)
    proposer = E2BFullHarnessProposer(
        E2BEvolverConfig(
            template=template,
            timeout_seconds=args.timeout_seconds,
            lease_timeout_seconds=120,
        ),
        lease_pool=leases,
    )
    proposal = proposer.propose(
        candidate_dir=backbone,
        evidence_dir=evidence.root,
        evolver_dir=evolver_dir,
        diagnosis=(
            "DISCOVERY arm="
            f"{args.arm}. Discover and test one causal harness mechanism from "
            "the authorized post-A3 public evidence. The coordinator prescribes "
            "no component, file, root cause, or implementation."
        ),
        iteration=1,
        run_id=args.run_id,
        run_dir=run_dir,
        model_env=model_env,
    )
    try:
        admission = asdict(
            admit_candidate(backbone, proposal.candidate_dir, AdmissionPolicy.qfbench_full())
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
        "sandbox_id": proposal.sandbox_id,
        "cleaned_up": proposal.cleaned_up,
    }
    report = {
        "schema_version": 1,
        "run_id": args.run_id,
        "arm": args.arm,
        "status": "complete",
        "proposal": proposal_payload,
        "cost": {
            "provider_cost_usd": None,
            "reason": "direct E2B route does not expose trusted proxy cost audit",
        },
        "worker_evaluation_in_this_run": False,
    }
    _atomic_json(run_dir / "proposal-report.json", proposal_payload)
    _atomic_json(run_dir / "pilot-report.json", report)
    _atomic_json(run_dir / "pilot-progress.json", report)
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
