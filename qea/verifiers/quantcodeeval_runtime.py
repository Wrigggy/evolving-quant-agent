#!/usr/bin/env python3
"""Trusted in-sandbox adapter from checker JSON to binary reward.

This file is copied into the verifier-only bundle.  It intentionally has no
dependency on the coordinator's installed QEA package.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _manifest_properties(path: Path) -> list[str]:
    payload = json.loads(path.read_text())
    rows = payload.get("checkers")
    if not isinstance(rows, list) or not rows:
        raise SystemExit("checker manifest has no checkers")
    properties = [row.get("property_id") for row in rows]
    if any(not isinstance(item, str) or not item for item in properties):
        raise SystemExit("checker manifest has invalid property IDs")
    if len(properties) != len(set(properties)):
        raise SystemExit("checker manifest has duplicate property IDs")
    return properties


def _missing_target(properties: list[str]) -> dict:
    return {
        "target": "strategy.py",
        "total": len(properties),
        "pass": 0,
        "fail": len(properties),
        "skip": 0,
        "results": [
            {
                "property_id": property_id,
                "verdict": "ERROR",
                "detail": "submitted strategy.py is missing",
            }
            for property_id in properties
        ],
    }


def _validate(payload: dict, properties: list[str]) -> bool:
    rows = payload.get("results")
    if not isinstance(rows, list) or len(rows) != len(properties):
        raise SystemExit("checker output does not cover the complete manifest")
    indexed = {row.get("property_id"): row.get("verdict") for row in rows}
    if set(indexed) != set(properties) or len(indexed) != len(rows):
        raise SystemExit("checker output property identity mismatch")
    allowed = {"PASS", "FAIL", "SKIP", "ERROR"}
    if any(verdict not in allowed for verdict in indexed.values()):
        raise SystemExit("checker output contains an invalid verdict")
    passed = sum(verdict == "PASS" for verdict in indexed.values())
    skipped = sum(verdict == "SKIP" for verdict in indexed.values())
    failed = len(properties) - passed - skipped
    expected = {
        "total": len(properties),
        "pass": passed,
        "fail": failed,
        "skip": skipped,
    }
    if any(payload.get(key) != value for key, value in expected.items()):
        raise SystemExit("checker output summary is inconsistent")
    return passed == len(properties)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--reward", type=Path)
    parser.add_argument("--task-id")
    parser.add_argument("--missing-target", action="store_true")
    args = parser.parse_args()
    properties = _manifest_properties(args.manifest)
    if args.missing_target:
        if args.output is None:
            raise SystemExit("--output is required with --missing-target")
        args.output.write_text(json.dumps(_missing_target(properties), indent=2) + "\n")
        return 0
    if args.input is None or args.reward is None or not args.task_id:
        raise SystemExit("--input, --reward, and --task-id are required")
    payload = json.loads(args.input.read_text())
    passed = _validate(payload, properties)
    args.reward.write_text("1\n" if passed else "0\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
