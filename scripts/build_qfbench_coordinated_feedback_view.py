#!/usr/bin/env python3
"""Attach one scored Worker run to a coordinated Evolver evidence view."""

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


def _without_hashes(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: _without_hashes(child)
            for key, child in value.items()
            if "sha256" not in key.casefold() and key.casefold() != "attempt_id"
        }
    if isinstance(value, list):
        return [_without_hashes(child) for child in value]
    return value


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
    parser.add_argument(
        "--source-run",
        type=Path,
        required=True,
        help="Run containing the Evolver proposal and candidate diff.",
    )
    parser.add_argument(
        "--worker-run",
        type=Path,
        help="Optional separate run containing the scored Worker attempt.",
    )
    parser.add_argument(
        "--component-token",
        default="validate_surface_artifacts",
        help="Trace token used to count observed component activation.",
    )
    parser.add_argument(
        "--optimization-diagnostic",
        type=Path,
        help="Optional Evolver-only diagnostic for the scored optimize run.",
    )
    parser.add_argument(
        "--parent-candidate",
        type=Path,
        help="Optional parent candidate snapshot that produced the Worker run.",
    )
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--round-label", default="round-1")
    args = parser.parse_args(argv)

    source_run = args.source_run.expanduser().resolve()
    worker_run = (
        args.worker_run.expanduser().resolve()
        if args.worker_run is not None
        else source_run
    )
    destination = args.destination.expanduser().resolve()
    if destination.exists():
        raise ValueError(f"destination already exists: {destination}")
    shutil.copytree(args.base_view.expanduser().resolve(), destination)

    proposal = _json(source_run / "proposal-report.json")
    attempt = _worker_attempt(worker_run)
    execution = _json(attempt / "worker-execution.json")
    score = _json(attempt / "completed-score.json")
    public_score = {
        key: score.get(key)
        for key in (
            "task_id",
            "domain",
            "reward",
            "diagnostic_tags",
            "tests_passed",
            "tests_failed",
            "verifier_exit_code",
        )
    }
    trace_path = attempt / str(execution.get("trace_uri", "raw-trace.jsonl"))
    final_path = attempt / str(execution.get("final_text_uri", "final.txt"))
    label = args.round_label
    archive = destination / "history/archive"
    objects = archive / "objects"
    objects.mkdir(parents=True, exist_ok=True)
    shutil.copy2(trace_path, objects / f"{label}-worker-trace.jsonl")
    shutil.copy2(final_path, objects / f"{label}-worker-final.txt")
    _write_json(objects / f"{label}-worker-score.json", public_score)
    _write_json(
        objects / f"{label}-worker-execution.json",
        {
            "summary": _without_hashes(execution.get("summary", {})),
            "artifact_count": len(execution.get("artifacts", [])),
        },
    )
    diagnostic_evidence_path = None
    if args.optimization_diagnostic is not None:
        diagnostic = _json(args.optimization_diagnostic.expanduser().resolve())
        if diagnostic.get("feedback_mode") != "answer_rich_evolver":
            raise ValueError("optimization diagnostic must be Evolver-only")
        if diagnostic.get("worker_visible") is not False:
            raise ValueError("optimization diagnostic must not be Worker-visible")
        diagnostic_name = f"{label}-optimization-diagnostic.json"
        _write_json(objects / diagnostic_name, diagnostic)
        diagnostic_evidence_path = f"history/archive/objects/{diagnostic_name}"
    parent_candidate_evidence_path = None
    if args.parent_candidate is not None:
        parent_candidate = args.parent_candidate.expanduser().resolve()
        if not parent_candidate.is_dir():
            raise ValueError("parent candidate must be a directory")
        parent_snapshot = archive / "parent-candidates" / label
        shutil.copytree(parent_candidate, parent_snapshot)
        parent_candidate_evidence_path = (
            f"history/archive/parent-candidates/{label}"
        )

    prediction = proposal.get("prediction")
    if not isinstance(prediction, dict):
        raise ValueError("source run has no Evolver prediction")
    trace_text = trace_path.read_text(encoding="utf-8")
    entry = {
        "schema_version": 1,
        "protocol": "coordinated_worker_runtime_experience",
        "source_run": source_run.name,
        "worker_run": worker_run.name,
        "decision": proposal.get("decision"),
        "prediction": prediction,
        "worker_observation": {
            "score": public_score,
            "execution_summary": _without_hashes(execution.get("summary", {})),
            "artifact_count": len(execution.get("artifacts", [])),
            "component_trace_token": args.component_token,
            "candidate_component_call_count": trace_text.count(
                args.component_token
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
    if diagnostic_evidence_path is not None:
        entry["evolver_only_optimization_diagnostic"] = diagnostic_evidence_path
    if parent_candidate_evidence_path is not None:
        entry["parent_candidate_snapshot"] = parent_candidate_evidence_path
    _write_json(archive / "entries" / f"{label}.json", entry)
    diff = proposal.get("diff")
    if not isinstance(diff, str) or not diff.strip():
        raise ValueError("source run has no candidate diff")
    diff_path = archive / "diffs" / f"{label}.patch"
    diff_path.parent.mkdir(parents=True, exist_ok=True)
    diff_path.write_text(diff, encoding="utf-8")

    contract_path = destination / "contract.json"
    contract = _json(contract_path)
    contract["stage"] = "LINEAGE_REFINEMENT"
    contract["history_required"] = True
    contract["runtime_feedback_round"] = 2
    contract["coordinated_evidence_required_for_act"] = False
    contract["shared_mechanism_assessment_required"] = False
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
        "distance; the Evolver still chooses the intervention and budget. "
        "When a parent candidate snapshot is listed in the runtime-experience "
        "entry, inspect that snapshot before attributing an observed behavior "
        "to or away from the tested component. This round refines one existing "
        "lineage; do not require a new cross-task shared-mechanism discovery."
    )
    _write_json(contract_path, contract)
    _write_json(
        destination / "FEEDBACK-VIEW-RECORD.json",
        {
            "schema_version": 1,
            "source_run": source_run.name,
            "worker_run": worker_run.name,
            "round": 2,
            "worker_model_requests": 0,
        },
    )
    print(json.dumps({"destination": str(destination), "round": 2}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
