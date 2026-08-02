#!/usr/bin/env python3
"""Operate the remote QFBench incident store through a narrow validated CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.repair_supervisor import (  # noqa: E402
    IncidentState,
    IncidentStore,
    RepairBudgetError,
    SupervisorPolicyError,
)


def _snapshot_payload(snapshot) -> dict[str, object]:
    return {
        "incident_id": snapshot.incident_id,
        "state": snapshot.state.value,
        "repair_count": snapshot.repair_count,
        "history": list(snapshot.history),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, required=True)
    subparsers = parser.add_subparsers(dest="action", required=True)
    subparsers.add_parser("show-active")
    show = subparsers.add_parser("show")
    show.add_argument("--incident-id", required=True)
    transition = subparsers.add_parser("transition")
    transition.add_argument("--incident-id", required=True)
    transition.add_argument("--state", choices=[state.value for state in IncidentState], required=True)
    repair = subparsers.add_parser("record-repair")
    repair.add_argument("--incident-id", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        store = IncidentStore(args.state_dir)
        if args.action == "show-active":
            active = json.loads((store.root / "active.json").read_text())
            incident_id = active.get("incident_id")
            if not incident_id:
                print(json.dumps({"incident": None, "snapshot": None}, sort_keys=True))
                return 0
            incident = store.load_incident(incident_id)
            snapshot = store.load(incident_id)
            payload = {
                "incident": incident.to_dict(),
                "snapshot": _snapshot_payload(snapshot),
            }
        elif args.action == "show":
            incident = store.load_incident(args.incident_id)
            snapshot = store.load(args.incident_id)
            payload = {
                "incident": incident.to_dict(),
                "snapshot": _snapshot_payload(snapshot),
            }
        elif args.action == "transition":
            snapshot = store.transition(
                args.incident_id, IncidentState(args.state)
            )
            payload = {"snapshot": _snapshot_payload(snapshot)}
        else:
            snapshot = store.record_repair(args.incident_id)
            payload = {"snapshot": _snapshot_payload(snapshot)}
        print(json.dumps(payload, sort_keys=True))
        return 0
    except RepairBudgetError as exc:
        print(json.dumps({"error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 30
    except (OSError, json.JSONDecodeError, SupervisorPolicyError) as exc:
        print(json.dumps({"error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 20


if __name__ == "__main__":
    raise SystemExit(main())
