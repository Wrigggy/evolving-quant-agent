#!/usr/bin/env python3
"""Build an Evolver-only QuantCodeEval optimization diagnostic."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.quantcodeeval_optimization import (  # noqa: E402
    build_quantcodeeval_optimization_diagnostic,
    extend_quantcodeeval_optimization_diagnostic,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    base = plan.get("base_diagnostic_path")
    if base is not None:
        result = extend_quantcodeeval_optimization_diagnostic(
            destination=args.destination,
            base_diagnostic_path=base,
            attempts=plan["attempts"],
            candidate_changes=plan.get("candidate_changes", []),
            failure_signatures=plan.get("failure_signatures", []),
        )
    else:
        result = build_quantcodeeval_optimization_diagnostic(
            destination=args.destination,
            task_id=plan["task_id"],
            attempts=plan["attempts"],
            rubric_manifest_path=plan["rubric_manifest_path"],
            rubric_overrides=plan.get("rubric_overrides", {}),
            candidate_changes=plan.get("candidate_changes", []),
            failure_signatures=plan.get("failure_signatures", []),
        )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
