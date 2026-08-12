#!/usr/bin/env python3
"""Run one deterministic QuantCodeEval PGBHS candidate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.quantcodeeval_candidate import run_quantcodeeval_candidate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--public-root", type=Path, required=True)
    parser.add_argument("--trusted-root", type=Path, required=True)
    parser.add_argument("--results-root", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--seed-worker-dir", type=Path, required=True)
    parser.add_argument("--parent-worker-dir", type=Path, required=True)
    parser.add_argument("--failure-class", required=True)
    parser.add_argument("--iteration", type=int, required=True)
    parser.add_argument("--worker-image", required=True)
    parser.add_argument("--verifier-image", required=True)
    parser.add_argument("--proxy-image", required=True)
    parser.add_argument("--source-h0-evaluation-id", required=True)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    result = run_quantcodeeval_candidate(
        config_path=args.config,
        public_root=args.public_root,
        trusted_root=args.trusted_root,
        run_dir=args.results_root.resolve() / args.run_id,
        seed_worker_dir=args.seed_worker_dir,
        parent_worker_dir=args.parent_worker_dir,
        failure_class=args.failure_class,
        iteration=args.iteration,
        worker_image_ref=args.worker_image,
        verifier_image_ref=args.verifier_image,
        proxy_image_ref=args.proxy_image,
        token_file=config["token_file"],
        source_h0_evaluation_id=args.source_h0_evaluation_id,
        preflight_only=args.preflight_only,
    )
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
