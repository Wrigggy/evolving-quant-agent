#!/usr/bin/env python3
"""Attach one scored Worker probe to a coordinated Evolver evidence view."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def _json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required: {path}")
    return payload


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _worker_attempt(source_run: Path) -> Path:
    matches = [
        path.parent
        for path in sorted((source_run / "attempts").glob("*/worker-execution.json"))
    ]
    if len(matches) != 1:
        raise ValueError("source run must contain exactly one scored Worker probe")
    return matches[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-view", type=Path, required=True)
    parser.add_argument("--source-run", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--round-label", default="round-1")
    args = parser.parse_args(argv)

    source_run = args.source_run.expanduser().resolve()
    destination = args.destination.expanduser().resolve()
    if destination.exists():
        raise ValueError(f"destination already exists: {destination}")
    shutil.copytree(args.base_view.expanduser().resolve(), destination)

    proposal = _json(source_run / "proposal-report.json")
    attempt = _worker_attempt(source_run)
    execution = _json(attempt / "worker-execution.json")
    score = _json(attempt / "completed-score.json")
    trace_path = attempt / str(execution.get("trace_uri", "raw-trace.jsonl"))
    final_path = attempt / str(execution.get("final_text_uri", "final.txt"))
    label = args.round_label
    archive = destination / "history/archive"
    objects = archive / "objects"
    objects.mkdir(parents=True, exist_ok=True)
    shutil.copy2(trace_path, objects / f"{label}-worker-trace.jsonl")
    shutil.copy2(final_path, objects / f"{label}-worker-final.txt")
    _write_json(objects / f"{label}-worker-score.json", score)
    _write_json(
        objects / f"{label}-worker-execution.json",
        {
            "summary": execution.get("summary", {}),
            "artifact_count": len(execution.get("artifacts", [])),
        },
    )

    prediction = proposal.get("prediction")
    if not isinstance(prediction, dict):
        raise ValueError("source run has no Evolver prediction")
    trace_text = trace_path.read_text(encoding="utf-8")
    entry = {
        "schema_version": 1,
        "protocol": "coordinated_worker_runtime_experience",
        "source_run": source_run.name,
        "decision": proposal.get("decision"),
        "prediction": prediction,
        "worker_observation": {
            "score": score,
            "execution_summary": execution.get("summary", {}),
            "artifact_count": len(execution.get("artifacts", [])),
            "candidate_component_call_count": trace_text.count(
                '"name": "validate_surface_artifacts"'
            ),
            "final_text": final_path.read_text(encoding="utf-8"),
        },
        "evidence_paths": {
            "trace": f"history/archive/objects/{label}-worker-trace.jsonl",
            "score": f"history/archive/objects/{label}-worker-score.json",
            "execution": f"history/archive/objects/{label}-worker-execution.json",
            "final": f"history/archive/objects/{label}-worker-final.txt",
        },
    }
    _write_json(archive / "entries" / f"{label}.json", entry)
    diff = proposal.get("diff")
    if not isinstance(diff, str) or not diff.strip():
        raise ValueError("source run has no candidate diff")
    diff_path = archive / "diffs" / f"{label}.patch"
    diff_path.parent.mkdir(parents=True, exist_ok=True)
    diff_path.write_text(diff, encoding="utf-8")

    contract_path = destination / "contract.json"
    contract = _json(contract_path)
    contract["history_required"] = True
    contract["runtime_feedback_round"] = 2
    contract["prior_runtime_experience"] = (
        f"history/archive/entries/{label}.json"
    )
    contract["evolver_instruction"] = str(contract.get("evolver_instruction", "")) + (
        " This is a feedback round. Read the exact prior candidate diff, its "
        "prediction, and the scored Worker trace. Compare predicted activation, "
        "artifact delivery, and official outcome with what happened. Decide "
        "REFINE, REUSE, REVERT, NEW_PROBE, or ABSTAIN from that observation. "
        "Do not repeat the same experiment unchanged. If the prior probe ended "
        "before the predicted component could activate, make the next bounded "
        "experiment distinguish component failure from insufficient causal "
        "distance; the Evolver still chooses the intervention and budget."
    )
    _write_json(contract_path, contract)
    _write_json(
        destination / "FEEDBACK-VIEW-RECORD.json",
        {
            "schema_version": 1,
            "source_run": source_run.name,
            "round": 2,
            "worker_model_requests": 0,
        },
    )
    print(json.dumps({"destination": str(destination), "round": 2}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
