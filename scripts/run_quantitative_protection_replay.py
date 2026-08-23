#!/usr/bin/env python3
"""Replay the deterministic QPR-0 triage over frozen evidence cards."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qea.quantitative_protection_review import (  # noqa: E402
    triage_quantitative_protection,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("data/breadth/QPR1_REVIEW_CASES.json"),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    source = json.loads(args.cases.read_text(encoding="utf-8"))
    records = []
    for case in source["cases"]:
        triage_input = case["triage_input"]
        result = triage_quantitative_protection(
            parent=case["parent"],
            candidate=case["candidate"],
            provisional_margin=int(case["provisional_margin"]),
            public_critical_relations=triage_input[
                "public_critical_relations"
            ],
            same_harness=bool(triage_input["same_harness"]),
            property_family_deltas=triage_input["property_family_deltas"],
            trace_attribution_hints=triage_input["trace_attribution_hints"],
        )
        expected = case["expected_triage"]
        matched = all(result.get(key) == value for key, value in expected.items())
        records.append(
            {
                "case_id": case["case_id"],
                "result": result,
                "expected": expected,
                "expected_matched": matched,
            }
        )

    payload = {
        "schema_version": 1,
        "protocol": "qpr-0",
        "status": "pass"
        if records and all(record["expected_matched"] for record in records)
        else "not_positive",
        "case_count": len(records),
        "model_requests": 0,
        "worker_sessions": 0,
        "official_verifier_executions": 0,
        "records": records,
        "claim_boundary": (
            "deterministic rule replay only; no Reviewer, Worker, controller "
            "mutation, official evaluation, or promotion was run"
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
