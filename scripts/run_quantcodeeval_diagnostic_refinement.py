#!/usr/bin/env python3
"""Run one answer-rich Evolver refinement and one blind seeded Worker probe."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qea.quantcodeeval_diagnostic_refinement import (  # noqa: E402
    run_quantcodeeval_diagnostic_refinement,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--component-source", type=Path, required=True)
    parser.add_argument("--seed-strategy", type=Path, required=True)
    parser.add_argument("--prior-probe-result", type=Path, required=True)
    parser.add_argument("--optimization-diagnostic", type=Path, required=True)
    parser.add_argument("--evolver-image", required=True)
    parser.add_argument("--worker-image", required=True)
    parser.add_argument("--verifier-image", required=True)
    parser.add_argument("--proxy-image", required=True)
    parser.add_argument("--task-panel", type=Path, required=True)
    parser.add_argument("--task", default="T26")
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args(argv)
    result = run_quantcodeeval_diagnostic_refinement(
        config_path=args.config,
        release_dir=args.release,
        run_dir=args.run_dir,
        component_source=args.component_source,
        seed_strategy=args.seed_strategy,
        prior_probe_result_path=args.prior_probe_result,
        optimization_diagnostic_path=args.optimization_diagnostic,
        evolver_image_ref=args.evolver_image,
        worker_image_ref=args.worker_image,
        verifier_image_ref=args.verifier_image,
        proxy_image_ref=args.proxy_image,
        task_panel_path=args.task_panel,
        task_id=args.task,
        preflight_only=args.preflight_only,
    )
    print(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
