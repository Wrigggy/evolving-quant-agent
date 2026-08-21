#!/usr/bin/env python3
"""Publish a sanitized health record for one component-pilot systemd unit."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path


_PROPERTIES = (
    "ActiveState",
    "SubState",
    "Result",
    "ExecMainStatus",
    "NRestarts",
)

_DEFAULT_STALL_SECONDS = 3600


def _atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(path.suffix + ".tmp")
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    with os.fdopen(descriptor, "w") as output:
        os.fchmod(output.fileno(), 0o600)
        json.dump(payload, output, sort_keys=True, indent=2)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)


def _unit_state(unit: str) -> dict[str, str]:
    completed = subprocess.run(
        [
            "systemctl",
            "--user",
            "show",
            unit,
            *(f"--property={name}" for name in _PROPERTIES),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    values = {name: "" for name in _PROPERTIES}
    for line in completed.stdout.splitlines():
        name, separator, value = line.partition("=")
        if separator and name in values:
            values[name] = value
    if completed.returncode != 0 or not values["ActiveState"]:
        values["ActiveState"] = "unknown"
        values["SubState"] = "unknown"
        values["Result"] = "unit-query-failed"
    return values


def _latest_progress(run_dir: Path) -> tuple[int, int, int, float | None]:
    scores = list(run_dir.glob("attempts/*/completed-score.json"))
    workers = list(run_dir.glob("attempts/*/worker-execution.json"))
    replacements = list(run_dir.glob("attempts/*/replacement.json"))
    progress = scores + workers + replacements
    progress.extend(run_dir.glob("attempts/*/proxy-audit.jsonl"))
    progress.extend(run_dir.glob("lifecycles/**/*.json"))
    for name in (
        "pilot-plan.json",
        "pilot-progress.json",
        "pilot-report.json",
        "H0-PREFLIGHT.json",
        "H0-RESULT.json",
        "FULL-CANDIDATE-PREFLIGHT.json",
        "FULL-CANDIDATE-RESULT.json",
    ):
        path = run_dir / name
        if path.is_file():
            progress.append(path)
    latest = max((path.stat().st_mtime for path in progress), default=None)
    age = None if latest is None else max(0.0, time.time() - latest)
    return len(scores), len(workers), len(replacements), age


def _complete(run_dir: Path) -> bool:
    for name in (
        "pilot-report.json",
        "H0-RESULT.json",
        "FULL-CANDIDATE-RESULT.json",
    ):
        report = run_dir / name
        if not report.is_file():
            continue
        try:
            payload = json.loads(report.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if payload.get("status") == "complete":
            return True
    return False


def build_health(
    *,
    run_id: str,
    unit: str,
    run_dir: Path,
    stalled_after_seconds: int = _DEFAULT_STALL_SECONDS,
) -> dict[str, object]:
    state = _unit_state(unit)
    scores, workers, replacements, age = _latest_progress(run_dir)
    active = state["ActiveState"]
    restarts = int(state["NRestarts"] or 0)
    complete = _complete(run_dir)
    if complete:
        category = "complete"
        needs_codex = False
    elif active in {"active", "activating"} and (
        age is None or age <= stalled_after_seconds
    ):
        category = "healthy"
        needs_codex = False
    elif active in {"active", "activating"}:
        category = "stalled"
        needs_codex = True
    elif active == "failed" and restarts >= 3:
        category = "restart_budget_exhausted"
        needs_codex = True
    elif active in {"failed", "inactive", "unknown"}:
        category = "coordinator_not_running"
        needs_codex = True
    else:
        category = "healthy"
        needs_codex = False
    fingerprint_payload = {
        "run_id": run_id,
        "unit": unit,
        "category": category,
        "result": state["Result"],
        "exec_main_status": state["ExecMainStatus"],
        "n_restarts": restarts,
        "score_count": scores,
        "worker_count": workers,
    }
    fingerprint = hashlib.sha256(
        json.dumps(
            fingerprint_payload, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    return {
        "schema_version": 1,
        "run_id": run_id,
        "unit": unit,
        "category": category,
        "active_state": active,
        "sub_state": state["SubState"],
        "result": state["Result"],
        "exec_main_status": int(state["ExecMainStatus"] or 0),
        "n_restarts": restarts,
        "score_count": scores,
        "worker_count": workers,
        "replacement_count": replacements,
        "progress_age_seconds": None if age is None else round(age, 3),
        "stalled_after_seconds": stalled_after_seconds,
        "needs_codex": needs_codex,
        "fingerprint": fingerprint,
        "observed_unix": int(time.time()),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--unit", required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--stalled-after-seconds",
        type=int,
        default=_DEFAULT_STALL_SECONDS,
        help="Alert after this many seconds without host-side result progress.",
    )
    args = parser.parse_args(argv)
    health = build_health(
        run_id=args.run_id,
        unit=args.unit,
        run_dir=args.run_dir.expanduser().resolve(),
        stalled_after_seconds=args.stalled_after_seconds,
    )
    _atomic_json(args.output.expanduser().resolve(), health)
    print(json.dumps(health, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
