#!/usr/bin/env python3
"""Preflight or run one bounded QuantCodeEval AP-2M canary."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qea.quantcodeeval_ap2m import run_quantcodeeval_ap2m  # noqa: E402


def _named_path(value: str) -> tuple[str, Path]:
    try:
        name, raw_path = value.split("=", 1)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("value must be NAME=PATH") from exc
    if not name or not raw_path:
        raise argparse.ArgumentTypeError("value must be NAME=PATH")
    return name, Path(raw_path)


def _pair(value: str) -> tuple[Path, Path]:
    try:
        activation, scored = value.split("=", 1)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "value must be ACTIVATION_DIR=SCORED_RUN_DIR"
        ) from exc
    return Path(activation), Path(scored)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--evolver-image", required=True)
    parser.add_argument("--worker-image", required=True)
    parser.add_argument("--verifier-image", required=True)
    parser.add_argument("--proxy-image", required=True)
    parser.add_argument("--task-panel", type=Path, required=True)
    parser.add_argument(
        "--seed-experience", type=_named_path, action="append", required=True
    )
    parser.add_argument(
        "--warm-component", type=_named_path, action="append", default=[]
    )
    parser.add_argument(
        "--warm-observation", type=_named_path, action="append", default=[]
    )
    parser.add_argument("--prior-scored-pair", type=_pair, action="append", default=[])
    parser.add_argument("--component-ledger", type=Path)
    parser.add_argument("--cost-cap-usd", type=float, default=0.25)
    parser.add_argument("--final-cost-reserve-usd", type=float, default=0.10)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args(argv)
    result = run_quantcodeeval_ap2m(
        config_path=args.config,
        release_dir=args.release,
        run_dir=args.run_dir,
        evolver_image_ref=args.evolver_image,
        worker_image_ref=args.worker_image,
        verifier_image_ref=args.verifier_image,
        proxy_image_ref=args.proxy_image,
        task_panel_path=args.task_panel,
        seed_experiences=dict(args.seed_experience),
        warm_component_sources=dict(args.warm_component),
        warm_observation_sources=dict(args.warm_observation),
        prior_scored_candidate_pairs=args.prior_scored_pair,
        component_ledger_path=args.component_ledger,
        cost_cap_usd=args.cost_cap_usd,
        final_cost_reserve_usd=args.final_cost_reserve_usd,
        preflight_only=args.preflight_only,
    )
    print(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False))
    if args.preflight_only:
        return 0
    return 0 if result.get("status") in {
        "complete",
        "complete_without_final",
        "round_one_terminal",
        "budget_stop_after_probe",
    } else 1


if __name__ == "__main__":
    raise SystemExit(main())
