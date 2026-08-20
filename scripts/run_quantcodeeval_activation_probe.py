#!/usr/bin/env python3
"""Run one bounded QuantCodeEval component-activation Worker probe."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qea.quantcodeeval_repair_probe import run_probe_arm  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--public-root", type=Path, required=True)
    parser.add_argument("--trusted-root", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--seed-strategy", type=Path, required=True)
    parser.add_argument("--worker-instruction", type=Path, required=True)
    parser.add_argument("--worker-image", required=True)
    parser.add_argument("--verifier-image", required=True)
    parser.add_argument("--proxy-image", required=True)
    parser.add_argument("--task-panel", type=Path, required=True)
    parser.add_argument("--task", default="T26")
    parser.add_argument("--max-iterations", type=int, default=8)
    parser.add_argument("--label", default="component-activation")
    args = parser.parse_args(argv)

    instruction = args.worker_instruction.read_text(encoding="utf-8").strip()
    result = run_probe_arm(
        label=args.label,
        config_path=args.config,
        public_root=args.public_root,
        trusted_root=args.trusted_root,
        run_dir=args.run_dir,
        worker_dir=args.worker,
        seed_strategy=args.seed_strategy,
        worker_instruction=instruction,
        worker_image_ref=args.worker_image,
        verifier_image_ref=args.verifier_image,
        proxy_image_ref=args.proxy_image,
        task_panel_path=args.task_panel,
        task_id=args.task,
        max_iterations=args.max_iterations,
    )
    print(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
