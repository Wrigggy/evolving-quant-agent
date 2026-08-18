#!/usr/bin/env python3
"""Run parent and candidate harnesses on the same failed T26 artifact."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.quantcodeeval_baseline import _atomic_private_json  # noqa: E402
from qea.quantcodeeval_repair_probe import (  # noqa: E402
    compare_probe_arms,
    run_probe_arm,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--public-root", type=Path, required=True)
    parser.add_argument("--trusted-root", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--parent-worker", type=Path, required=True)
    parser.add_argument("--candidate-worker", type=Path, required=True)
    parser.add_argument("--seed-strategy", type=Path, required=True)
    parser.add_argument("--worker-image", required=True)
    parser.add_argument("--verifier-image", required=True)
    parser.add_argument("--proxy-image", required=True)
    parser.add_argument("--task-panel", type=Path, required=True)
    parser.add_argument("--task", default="T26")
    parser.add_argument("--max-iterations", type=int, default=12)
    args = parser.parse_args()

    common = {
        "config_path": args.config,
        "public_root": args.public_root,
        "trusted_root": args.trusted_root,
        "seed_strategy": args.seed_strategy,
        "worker_image_ref": args.worker_image,
        "verifier_image_ref": args.verifier_image,
        "proxy_image_ref": args.proxy_image,
        "task_panel_path": args.task_panel,
        "task_id": args.task,
        "max_iterations": args.max_iterations,
    }
    root = args.run_dir.resolve()
    parent = run_probe_arm(
        label="parent",
        run_dir=root / "parent",
        worker_dir=args.parent_worker,
        **common,
    )
    candidate = run_probe_arm(
        label="candidate",
        run_dir=root / "candidate",
        worker_dir=args.candidate_worker,
        **common,
    )
    comparison = compare_probe_arms(parent, candidate)
    result = {"parent": parent, "candidate": candidate, "comparison": comparison}
    _atomic_private_json(root / "PAIRED-PROBE-RESULT.json", result)
    print(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
