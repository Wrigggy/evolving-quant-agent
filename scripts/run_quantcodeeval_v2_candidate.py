#!/usr/bin/env python3
"""Evaluate one passed QuantCodeEval v2 activation candidate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qea.quantcodeeval_full_candidate import run_quantcodeeval_full_candidate


def _selected_mechanism(decision: dict[str, object]) -> str:
    selected = decision.get("selected_hypothesis_id")
    for value in decision.get("hypotheses_considered", []):
        if isinstance(value, dict) and value.get("hypothesis_id") == selected:
            mechanism = value.get("mechanism")
            if isinstance(mechanism, str) and mechanism.strip():
                return mechanism
    raise ValueError("activation decision has no selected mechanism")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--release", required=True, type=Path)
    parser.add_argument("--activation-run", required=True, type=Path)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--worker-image", required=True)
    parser.add_argument("--verifier-image", required=True)
    parser.add_argument("--proxy-image", required=True)
    parser.add_argument("--task", dest="task_ids", action="append")
    parser.add_argument(
        "--token-file",
        type=Path,
        help="Deprecated compatibility option; completed proxy evidence is used.",
    )
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args(argv)

    live = json.loads((args.activation_run / "LIVE-RESULT.json").read_text())
    if live.get("status") != "PASS" or live.get("candidate_benchmark_evaluated"):
        raise ValueError("activation run is not an unscored PASS")
    decision = live.get("decision")
    if not isinstance(decision, dict) or decision.get("decision") != "ACT":
        raise ValueError("activation run has no legal ACT decision")
    result = run_quantcodeeval_full_candidate(
        config_path=args.config,
        public_root=args.release / "public",
        trusted_root=args.release / "trusted",
        run_dir=args.run_dir,
        seed_worker_dir=args.release / "h0/workers/H0",
        parent_worker_dir=args.release / "h0/workers/H0",
        candidate_worker_dir=args.activation_run / "evolutions/iteration-0001/candidate",
        iteration=1,
        mechanism=_selected_mechanism(decision),
        primary_components=decision["primary_components"],
        declared_roles=decision["components"],
        component_tests=live["component_tests"],
        activation=live["activation"],
        worker_image_ref=args.worker_image,
        verifier_image_ref=args.verifier_image,
        proxy_image_ref=args.proxy_image,
        token_file=args.token_file,
        source_h0_evaluation_id=live["h0_evaluation_id"],
        task_ids=args.task_ids,
        preflight_only=args.preflight_only,
    )
    print(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False))
    if args.preflight_only:
        return 0
    return 0 if result.get("status") == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
