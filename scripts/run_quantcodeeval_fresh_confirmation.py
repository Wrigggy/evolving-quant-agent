#!/usr/bin/env python3
"""Run one fresh T26 Worker under the retained QDR-1 harness."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qea.quantcodeeval_fresh_confirmation import (  # noqa: E402
    run_quantcodeeval_fresh_confirmation,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--source-run-dir", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--worker-image", required=True)
    parser.add_argument("--verifier-image", required=True)
    parser.add_argument("--proxy-image", required=True)
    parser.add_argument("--task-panel", type=Path, required=True)
    parser.add_argument("--task", default="T26")
    parser.add_argument("--component-tool", default="check_quant_relations")
    parser.add_argument("--max-iterations", type=int, default=60)
    parser.add_argument("--initial-construction-turns", type=int, default=24)
    args = parser.parse_args()
    result = run_quantcodeeval_fresh_confirmation(
        config_path=args.config,
        release_dir=args.release,
        source_run_dir=args.source_run_dir,
        run_dir=args.run_dir,
        worker_image_ref=args.worker_image,
        verifier_image_ref=args.verifier_image,
        proxy_image_ref=args.proxy_image,
        task_panel_path=args.task_panel,
        task_id=args.task,
        component_tool=args.component_tool,
        max_iterations=args.max_iterations,
        initial_construction_turns=args.initial_construction_turns,
    )
    print(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
