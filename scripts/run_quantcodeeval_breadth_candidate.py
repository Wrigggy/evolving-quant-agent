#!/usr/bin/env python3
"""Evaluate an admitted breadth-discovery candidate on one QuantCodeEval task."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.loop_benchmark import hash_worker_directory  # noqa: E402
from qea.quantcodeeval_experiment import h0_evaluation_ref  # noqa: E402
from qea.quantcodeeval_full_candidate import (  # noqa: E402
    run_quantcodeeval_full_candidate,
)


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--public-root", type=Path, required=True)
    parser.add_argument("--trusted-root", type=Path, required=True)
    parser.add_argument("--h0-run", type=Path, required=True)
    parser.add_argument("--discovery-run", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--worker-image", required=True)
    parser.add_argument("--verifier-image", required=True)
    parser.add_argument("--proxy-image", required=True)
    parser.add_argument("--task-panel", type=Path, required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--smoke-module", required=True)
    parser.add_argument("--smoke-function", required=True)
    parser.add_argument("--smoke-args-json", required=True)
    parser.add_argument("--expect-truthy-field", required=True)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()

    discovery = args.discovery_run.expanduser().resolve()
    report = _json(discovery / "pilot-report.json")
    proposal = report.get("proposal")
    if not isinstance(proposal, dict) or proposal.get("decision") != "ACT":
        raise ValueError("breadth discovery has no legal ACT")
    admission = proposal.get("admission")
    if not isinstance(admission, dict) or admission.get("admitted") is not True:
        raise ValueError("breadth discovery candidate was not admitted")
    candidate = Path(str(proposal["candidate_dir"])).resolve()
    summary = proposal.get("summary")
    state = summary.get("discovery_hypothesis") if isinstance(summary, dict) else None
    hypothesis = state.get("hypothesis") if isinstance(state, dict) else None
    if not isinstance(hypothesis, dict):
        raise ValueError("breadth discovery hypothesis is missing")
    mechanism = hypothesis.get("selected_mechanism")
    if not isinstance(mechanism, str) or not mechanism.strip():
        mechanism = hypothesis.get("search_operator")
    primary = hypothesis.get("component")
    if not isinstance(primary, str) or not primary.strip():
        primary_components = hypothesis.get("primary_components")
        if isinstance(primary_components, list) and primary_components:
            primary = primary_components[0]
    if not isinstance(mechanism, str) or not isinstance(primary, str):
        raise ValueError("breadth discovery component mechanism is missing")
    metrics = proposal.get("mutation_metrics")
    declared = metrics.get("component_roles") if isinstance(metrics, dict) else None
    if not isinstance(declared, list) or not declared:
        raise ValueError("breadth discovery changed component roles are missing")

    smoke_arguments = json.loads(args.smoke_args_json)
    if not isinstance(smoke_arguments, dict):
        raise ValueError("smoke args must be a JSON object")
    sys.path.insert(0, str(candidate))
    try:
        module = importlib.import_module(args.smoke_module)
        function = getattr(module, args.smoke_function)
        smoke_output = function(**smoke_arguments)
    finally:
        sys.path.pop(0)
    if not isinstance(smoke_output, dict) or not smoke_output.get(
        args.expect_truthy_field
    ):
        raise ValueError("candidate component smoke did not meet its expectation")
    component_tests = ({
        "status": "passed",
        "component": primary,
        "operation": "call",
        "target": f"{args.smoke_module}:{args.smoke_function}",
        "candidate_digest": hash_worker_directory(candidate),
        "observed_summary": smoke_output.get("summary"),
    },)

    result = run_quantcodeeval_full_candidate(
        config_path=args.config,
        public_root=args.public_root,
        trusted_root=args.trusted_root,
        run_dir=args.run_dir,
        seed_worker_dir=args.h0_run / "workers/H0",
        parent_worker_dir=args.h0_run / "workers/H0",
        candidate_worker_dir=candidate,
        iteration=1,
        mechanism=mechanism,
        primary_components=(primary,),
        declared_roles=declared,
        component_tests=component_tests,
        activation={"status": "not_run"},
        worker_image_ref=args.worker_image,
        verifier_image_ref=args.verifier_image,
        proxy_image_ref=args.proxy_image,
        source_h0_evaluation_id=h0_evaluation_ref(args.h0_run).evaluation_id,
        task_ids=(args.task,),
        task_panel_path=args.task_panel,
        require_activation=False,
        preflight_only=args.preflight_only,
    )
    print(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False))
    return 0 if args.preflight_only or result.get("status") == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
