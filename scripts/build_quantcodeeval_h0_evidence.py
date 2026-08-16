#!/usr/bin/env python3
"""Project one completed QuantCodeEval H0 run into answer-free task evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __name__ == "__main__":
    sys.dont_write_bytecode = True

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.quantcodeeval_evidence import build_quantcodeeval_evidence  # noqa: E402
from qea.quantcodeeval_experiment import (  # noqa: E402
    h0_evaluation_ref,
    materialize_h0_attempt_sources,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--h0-run", type=Path, required=True)
    parser.add_argument("--public-root", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()

    h0 = args.h0_run.expanduser().resolve()
    workspace = args.workspace.expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    evaluation = h0_evaluation_ref(h0)
    sources = materialize_h0_attempt_sources(
        master_root=workspace,
        h0_root=h0,
        evaluation=evaluation,
    )
    record = build_quantcodeeval_evidence(
        destination=args.destination,
        public_task_roots={
            task_id: args.public_root.expanduser().resolve() / "tasks" / task_id
            for task_id in evaluation.task_results
        },
        attempts=sources,
        current_evaluation_id=evaluation.evaluation_id,
    )
    print(
        json.dumps(
            {
                "destination": str(record.root),
                "task_ids": sorted(evaluation.task_results),
                "files": len(record.members),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
