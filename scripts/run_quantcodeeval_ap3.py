#!/usr/bin/env python3
"""Preflight or run one bounded QuantCodeEval AP-3 bootstrap canary."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qea.quantcodeeval_ap3 import run_quantcodeeval_ap3  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--source-release", type=Path, required=True)
    parser.add_argument("--quant-h0-worker", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--evolver-image", required=True)
    parser.add_argument("--worker-image", required=True)
    parser.add_argument("--verifier-image", required=True)
    parser.add_argument("--proxy-image", required=True)
    parser.add_argument("--task-panel", type=Path, required=True)
    parser.add_argument("--cost-cap-usd", type=float, default=0.80)
    parser.add_argument("--final-cost-reserve-usd", type=float, default=0.12)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args(argv)
    result = run_quantcodeeval_ap3(
        config_path=args.config,
        source_release_dir=args.source_release,
        quant_h0_worker_dir=args.quant_h0_worker,
        run_dir=args.run_dir,
        evolver_image_ref=args.evolver_image,
        worker_image_ref=args.worker_image,
        verifier_image_ref=args.verifier_image,
        proxy_image_ref=args.proxy_image,
        task_panel_path=args.task_panel,
        cost_cap_usd=args.cost_cap_usd,
        final_cost_reserve_usd=args.final_cost_reserve_usd,
        preflight_only=args.preflight_only,
    )
    print(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
