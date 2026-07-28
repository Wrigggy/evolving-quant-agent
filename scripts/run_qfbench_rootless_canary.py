#!/usr/bin/env python3
"""Plan or execute the ordered rootless QFBench canary gates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.rootless_canary import (
    CANARY_STAGES,
    RootlessCanaryLiveGates,
    load_canary_config,
    plan_canary,
    run_canary,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--source-commit", required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan-only", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--through-stage", choices=CANARY_STAGES)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_canary_config(args.config, runtime_root=args.runtime_root)
    if args.apply:
        output_root = config.resolved_path("run_output_root")
        gate_runner = RootlessCanaryLiveGates(
            config,
            source_commit=args.source_commit,
            output_root=output_root,
        )
        try:
            token = config.resolved_path("secret_file").read_bytes().strip().decode("ascii")
        except (OSError, UnicodeDecodeError):
            token = ""
        results = run_canary(
            config,
            source_commit=args.source_commit,
            output_root=output_root,
            gate_runner=gate_runner,
            forbidden_values=(token,) if token else (),
            through_stage=args.through_stage,
        )
        boundary = (
            CANARY_STAGES.index(args.through_stage) + 1
            if args.through_stage
            else len(CANARY_STAGES)
        )
        accepted = all(
            result.status == "pass" for result in results[:boundary]
        ) and all(
            result.status in {"pass", "not_run"}
            for result in results[boundary:]
        )
        print(json.dumps({
            "schema_version": 1,
            "mode": "apply",
            "run_id": config.run_id,
            "config_sha256": config.config_sha256,
            "through_stage": args.through_stage,
            "accepted_through_boundary": accepted,
            "formal_scoring_available": False,
            "results": [result.payload() for result in results],
        }, sort_keys=True, indent=2))
        return 0 if accepted else 1
    payload = plan_canary(config, source_commit=args.source_commit)
    payload["through_stage"] = args.through_stage
    print(json.dumps(payload, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
