#!/usr/bin/env python3
"""Preflight or run the measured shell-only QuantCodeEval H0 panel."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.quantcodeeval_baseline import (
    prepare_quantcodeeval_h0,
    run_quantcodeeval_h0,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--public-root", type=Path, required=True)
    parser.add_argument("--trusted-root", type=Path, required=True)
    parser.add_argument("--results-root", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--worker-dir", type=Path, required=True)
    parser.add_argument("--worker-image", required=True)
    parser.add_argument("--verifier-image", required=True)
    parser.add_argument("--proxy-image", required=True)
    parser.add_argument("--task-panel", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    run_dir = args.results_root.resolve() / args.run_id
    snapshot, evaluator, plan, frozen_worker = prepare_quantcodeeval_h0(
        config_path=args.config,
        public_root=args.public_root,
        trusted_root=args.trusted_root,
        run_dir=run_dir,
        worker_dir=args.worker_dir,
        worker_image_ref=args.worker_image,
        verifier_image_ref=args.verifier_image,
        proxy_image_ref=args.proxy_image,
        task_panel_path=args.task_panel,
    )
    if args.preflight_only:
        print(json.dumps(plan, sort_keys=True, indent=2))
        return 0
    config = json.loads(args.config.read_text(encoding="utf-8"))
    result = run_quantcodeeval_h0(
        snapshot=snapshot,
        evaluator=evaluator,
        plan=plan,
        frozen_worker=frozen_worker,
        run_dir=run_dir,
        token_file=config["token_file"],
    )
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
