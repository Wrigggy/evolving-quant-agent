#!/usr/bin/env python3
"""Run the phase-aware P-v2 QuantCodeEval causal component probe."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qea.quantcodeeval_causal_probe import run_quantcodeeval_causal_probe  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--source-run-dir", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--seed-strategy", type=Path, required=True)
    parser.add_argument("--worker-image", required=True)
    parser.add_argument("--verifier-image", required=True)
    parser.add_argument("--proxy-image", required=True)
    parser.add_argument("--task-panel", type=Path, required=True)
    parser.add_argument("--task", default="T26")
    parser.add_argument("--component-tool", default="check_quant_relations")
    parser.add_argument("--completed-request-budget", type=int, default=12)
    args = parser.parse_args()
    result = run_quantcodeeval_causal_probe(
        config_path=args.config,
        release_dir=args.release,
        source_run_dir=args.source_run_dir,
        run_dir=args.run_dir,
        seed_strategy=args.seed_strategy,
        worker_image_ref=args.worker_image,
        verifier_image_ref=args.verifier_image,
        proxy_image_ref=args.proxy_image,
        task_panel_path=args.task_panel,
        task_id=args.task,
        component_tool=args.component_tool,
        completed_request_budget=args.completed_request_budget,
    )
    print(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
