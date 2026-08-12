#!/usr/bin/env python3
"""Preflight or run one real QuantCodeEval v2 Evolver activation round."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qea.quantcodeeval_v2_live import run_quantcodeeval_v2_activation_canary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--release", required=True, type=Path)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--evolver-image", required=True)
    parser.add_argument("--proxy-image", required=True)
    parser.add_argument("--prior-rejected-attempt", type=Path, action="append")
    parser.add_argument("--prior-failed-candidate-activation", type=Path)
    parser.add_argument("--prior-failed-candidate-run", type=Path)
    parser.add_argument("--prior-scored-candidate-activation", type=Path)
    parser.add_argument("--prior-scored-candidate-run", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args(argv)
    result = run_quantcodeeval_v2_activation_canary(
        config_path=args.config,
        release_dir=args.release,
        run_dir=args.run_dir,
        evolver_image_ref=args.evolver_image,
        proxy_image_ref=args.proxy_image,
        prior_rejected_attempt_dir=args.prior_rejected_attempt,
        prior_failed_candidate_activation_dir=(
            args.prior_failed_candidate_activation
        ),
        prior_failed_candidate_run_dir=args.prior_failed_candidate_run,
        prior_scored_candidate_activation_dir=(
            args.prior_scored_candidate_activation
        ),
        prior_scored_candidate_run_dir=args.prior_scored_candidate_run,
        preflight_only=args.preflight_only,
    )
    print(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False))
    if args.preflight_only:
        return 0
    return 0 if result["status"] in {"PASS", "CALIBRATED_ABSTAIN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
