#!/usr/bin/env python3
"""Build a public-only QFBench trajectory view from one fresh Quant-H0 run."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path
from typing import Mapping


class PublicTrajectoryEvidenceError(ValueError):
    """The requested sources cannot form an answer-free trajectory view."""


_INSTRUCTION = (
    "Use only the supplied public task contracts and the fresh Quant-H0 Worker "
    "trajectory. No official score, property verdict, checker output, expected "
    "value, optimize diagnostic, or prior candidate episode is present. "
    "Reconstruct a task-conditioned Quant Research State Card for the target, "
    "compare at least two plausible explanations, and use the protection public "
    "contract only to scope the proposed relation and likely non-activation. "
    "A protection failure is not required before ACT. If the evidence supports a "
    "bounded reusable intervention, use decide_candidate with a from_scratch "
    "experiment_spec and select only the predeclared target as probe_task_key; "
    "otherwise record calibrated ABSTAIN. Before ACT, enumerate every "
    "decision-changing Worker-visible predicate or instruction in "
    "worker_visible_claims. Each claim must cite an exact supplied public "
    "contract location or other predeclared public reference. The answer-free "
    "trajectory may localize uncertainty, but it is not itself public support "
    "for a new normative rule. Do not infer a failed official property or an "
    "expected answer from the absence of evaluator feedback."
)


def _json(path: Path, *, label: str) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise PublicTrajectoryEvidenceError(f"{label} is unavailable: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PublicTrajectoryEvidenceError(f"cannot read {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise PublicTrajectoryEvidenceError(f"{label} must be a JSON object")
    return payload


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _without_hash_fields(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): _without_hash_fields(child)
            for key, child in value.items()
            if "sha" not in str(key).casefold()
            and "digest" not in str(key).casefold()
            and str(key).casefold() != "attempt_id"
        }
    if isinstance(value, list):
        return [_without_hash_fields(child) for child in value]
    return value


def _copy_regular_file(source: Path, destination: Path) -> None:
    if source.is_symlink() or not source.is_file():
        raise PublicTrajectoryEvidenceError(
            f"evidence member must be a regular file: {source}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _copy_artifacts(source: Path, destination: Path) -> list[str]:
    if source.is_symlink() or not source.is_dir():
        raise PublicTrajectoryEvidenceError(
            f"fresh H0 artifact directory is unavailable: {source}"
        )
    copied: list[str] = []
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise PublicTrajectoryEvidenceError(
                f"artifact symlink is unsupported: {path}"
            )
        if not path.is_file():
            continue
        relative = path.relative_to(source)
        _copy_regular_file(path, destination / relative)
        copied.append(relative.as_posix())
    if not copied:
        raise PublicTrajectoryEvidenceError(
            "fresh H0 attempt must contain at least one public artifact"
        )
    return copied


def _contract_sources(root: Path, task_id: str) -> tuple[Path, Path]:
    task = root / task_id
    instruction = task / "instruction.md"
    clauses = task / "clauses.json"
    if not clauses.is_file():
        clauses = task / "public_clauses.json"
    if not instruction.is_file() or not clauses.is_file():
        raise PublicTrajectoryEvidenceError(
            f"public instruction/clauses are incomplete for {task_id}"
        )
    return instruction, clauses


def _attempt_members(
    attempt: Path,
) -> tuple[dict[str, object], Path, Path, Path | None]:
    execution = _json(attempt / "worker-execution.json", label="Worker execution")
    summary = execution.get("summary")
    if not isinstance(summary, Mapping) or summary.get("outcome") != "completed":
        raise PublicTrajectoryEvidenceError(
            "fresh H0 Worker execution must have completed outcome"
        )
    trace_name = execution.get("trace_uri", "raw-trace.jsonl")
    final_name = execution.get("final_text_uri", "final.txt")
    if not isinstance(trace_name, str) or Path(trace_name).name != trace_name:
        raise PublicTrajectoryEvidenceError("Worker trace URI must be a local file")
    if not isinstance(final_name, str) or Path(final_name).name != final_name:
        raise PublicTrajectoryEvidenceError("Worker final URI must be a local file")
    state_trace = attempt / "research-state-trace.json"
    return (
        dict(summary),
        attempt / trace_name,
        attempt / final_name,
        (
            state_trace
            if state_trace.is_file() and not state_trace.is_symlink()
            else None
        ),
    )


def build(
    *,
    public_contracts_root: Path,
    h0_run: Path,
    h0_attempt: Path,
    quant_h0_worker: Path,
    target_task_id: str,
    protection_task_ids: list[str],
    destination: Path,
) -> dict[str, object]:
    """Create one discovery-compatible view with no evaluator or candidate history."""

    contracts = public_contracts_root.expanduser().resolve()
    run = h0_run.expanduser().resolve()
    attempt = h0_attempt.expanduser().resolve()
    backbone = quant_h0_worker.expanduser().resolve()
    target = destination.expanduser().resolve()
    task_ids = [target_task_id, *protection_task_ids]
    if not target_task_id or not protection_task_ids:
        raise PublicTrajectoryEvidenceError(
            "one target and at least one protection task are required"
        )
    if len(task_ids) != len(set(task_ids)):
        raise PublicTrajectoryEvidenceError("target/protection task IDs must be unique")
    if not run.is_dir() or attempt.parent != run / "attempts" or not attempt.is_dir():
        raise PublicTrajectoryEvidenceError(
            "fresh H0 attempt must be a direct child of the supplied run/attempts"
        )
    if not (backbone / "agent.yaml").is_file() or not (
        backbone / "systemprompt.md"
    ).is_file():
        raise PublicTrajectoryEvidenceError(
            "Quant-H0 worker must contain agent.yaml and systemprompt.md"
        )
    attempt_record = _json(attempt / "attempt.json", label="fresh H0 attempt")
    if attempt_record.get("task_id") != target_task_id:
        raise PublicTrajectoryEvidenceError(
            "fresh H0 attempt task does not match the target task"
        )
    summary, trace, final, research_state_trace = _attempt_members(attempt)
    parent_name = (
        "Quant-H0-S6"
        if (
            backbone
            / "skills"
            / "quant-research-six-stage-workflow"
            / "SKILL.md"
        ).is_file()
        else "Quant-H0"
    )
    if target.exists():
        raise PublicTrajectoryEvidenceError(f"destination already exists: {target}")
    staging = target.with_name(target.name + ".partial")
    if staging.exists():
        raise PublicTrajectoryEvidenceError(
            f"staging destination already exists: {staging}"
        )

    staging.mkdir(parents=True)
    try:
        (staging / "access_log.jsonl").write_text("", encoding="utf-8")
        cards: list[dict[str, object]] = []
        for task_id in task_ids:
            role = "target" if task_id == target_task_id else "protection"
            instruction, clauses = _contract_sources(contracts, task_id)
            task_root = staging / "benchmarks/qfbench/tasks" / task_id
            _copy_regular_file(instruction, task_root / "instruction.md")
            public_clauses = _without_hash_fields(
                _json(clauses, label=f"{task_id} public clauses")
            )
            _write_json(task_root / "public_clauses.json", public_clauses)
            evidence_paths: dict[str, str] = {
                "instruction": (
                    f"benchmarks/qfbench/tasks/{task_id}/instruction.md"
                ),
                "public_clauses": (
                    f"benchmarks/qfbench/tasks/{task_id}/public_clauses.json"
                ),
            }
            card: dict[str, object] = {
                "schema_version": 1,
                "task_key": f"qfbench:{task_id}",
                "benchmark": "qfbench",
                "task_id": task_id,
                "role": role,
                "feedback_mode": "answer_free",
                "execution_status": (
                    "complete" if role == "target" else "not_run_public_contract_only"
                ),
                "evidence_completeness": (
                    "fresh_h0_public_trajectory"
                    if role == "target"
                    else "public_contract_only"
                ),
                "evidence_paths": evidence_paths,
            }
            if role == "target":
                _copy_regular_file(trace, task_root / "worker_trace.jsonl")
                _copy_regular_file(final, task_root / "worker_final.txt")
                if research_state_trace is not None:
                    _copy_regular_file(
                        research_state_trace,
                        task_root / "research_state_trace.json",
                    )
                artifacts = _copy_artifacts(
                    attempt / "artifacts", task_root / "artifacts"
                )
                clean_summary = _without_hash_fields(summary)
                _write_json(task_root / "process_summary.json", clean_summary)
                evidence_paths.update(
                    {
                        "trace": (
                            f"benchmarks/qfbench/tasks/{task_id}/worker_trace.jsonl"
                        ),
                        "final": (
                            f"benchmarks/qfbench/tasks/{task_id}/worker_final.txt"
                        ),
                        "process": (
                            f"benchmarks/qfbench/tasks/{task_id}/process_summary.json"
                        ),
                        "artifacts": (
                            f"benchmarks/qfbench/tasks/{task_id}/artifacts"
                        ),
                    }
                )
                if research_state_trace is not None:
                    evidence_paths["research_state_trace"] = (
                        f"benchmarks/qfbench/tasks/{task_id}/"
                        "research_state_trace.json"
                    )
                card["runtime_summary"] = clean_summary
                card["artifact_paths"] = artifacts
            cards.append(card)
            _write_json(
                staging / "tasks/cards" / f"qfbench--{task_id}.json", card
            )

        task_keys = [f"qfbench:{task_id}" for task_id in task_ids]
        _write_json(
            staging / "tasks/CATALOG.json",
            {"schema_version": 1, "task_count": len(cards), "tasks": cards},
        )
        _write_json(
            staging / "tasks/RELEVANT_COMPONENTS.json",
            {
                "schema_version": 1,
                "history_enabled": False,
                "task_keys": task_keys,
                "tasks": [],
            },
        )
        _write_json(
            staging / "components/CATALOG.json",
            {
                "schema_version": 1,
                "catalog_policy": "no_candidate_history",
                "component_count": 0,
                "components": [],
            },
        )
        _write_json(
            staging / "contract.json",
            {
                "schema_version": 1,
                "stage": "COORDINATED_BREADTH",
                "contract_arm": "quant-state",
                "candidate_parent": parent_name,
                "candidate_history_exposed": False,
                "component_history_enabled": False,
                "history_required": False,
                "answer_free": True,
                "feedback_tier": "answer_free_property_family_v2",
                "optimization_answers_exposed_to_evolver": False,
                "optimization_answers_exposed_to_worker": False,
                "worker_visible_claim_provenance_required_for_act": True,
                "quant_research_state_card_required_for_act": True,
                "research_state_transition_required_for_act": True,
                "decision_protocol": "quant_property_v2",
                "task_keys": task_keys,
                "target_task_keys": [f"qfbench:{target_task_id}"],
                "protection_task_keys": [
                    f"qfbench:{task_id}" for task_id in protection_task_ids
                ],
                "task_ids": task_ids,
                "target_task_ids": [target_task_id],
                "protection_task_ids": protection_task_ids,
                "task_evidence_prefixes": {
                    f"qfbench:{task_id}": [
                        f"benchmarks/qfbench/tasks/{task_id}/",
                        f"tasks/cards/qfbench--{task_id}.json",
                    ]
                    for task_id in task_ids
                },
                "autonomous_probe_required": True,
                "coordinated_evidence_required_for_act": True,
                "shared_mechanism_required_for_act": False,
                "shared_mechanism_assessment_required": False,
                "probe_task_selection_required_for_act": True,
                "probe_seed_policy": "none",
                "max_primary_components": 2,
                "max_declared_components": 9,
                "max_worker_probes_this_round": 1,
                "positive_target_before_contrast_evaluation": True,
                "evolver_worker_evaluation_in_this_stage": False,
                "coordinator_selected_probe_evaluation_allowed": True,
                "worker_evaluation_in_this_stage": (
                    "conditional_singleton_dispatch"
                ),
                "evolver_instruction": _INSTRUCTION,
            },
        )
        _write_json(
            staging / "PUBLIC-TRAJECTORY-RECORD.json",
            {
                "schema_version": 1,
                "source_run": run.name,
                "parent": parent_name,
                "target_task_id": target_task_id,
                "protection_task_ids": protection_task_ids,
                "copied_evidence": (
                    "public contracts plus one fresh H0 trace, final, artifacts, "
                    "process summary, and the trusted research-state marker "
                    "index when present"
                ),
                "excluded_evidence": [
                    "official scores and public evaluation",
                    "CTRF and verifier files",
                    "optimize diagnostics",
                    "failed properties, checker outputs, and expected values",
                    "prior candidate episodes",
                ],
            },
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging, target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return {
        "schema_version": 1,
        "destination": str(target),
        "target_task_id": target_task_id,
        "protection_task_ids": protection_task_ids,
        "artifact_count": len(
            cards[0].get("artifact_paths", [])
            if isinstance(cards[0].get("artifact_paths"), list)
            else []
        ),
        "answer_free": True,
        "candidate_history_exposed": False,
        "parent": parent_name,
        "research_state_trace_included": research_state_trace is not None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-contracts-root", type=Path, required=True)
    parser.add_argument("--h0-run", type=Path, required=True)
    parser.add_argument("--h0-attempt", type=Path, required=True)
    parser.add_argument("--quant-h0-worker", type=Path, required=True)
    parser.add_argument("--target-task-id", required=True)
    parser.add_argument(
        "--protection-task-id", action="append", required=True,
    )
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args(argv)
    report = build(
        public_contracts_root=args.public_contracts_root,
        h0_run=args.h0_run,
        h0_attempt=args.h0_attempt,
        quant_h0_worker=args.quant_h0_worker,
        target_task_id=args.target_task_id,
        protection_task_ids=args.protection_task_id,
        destination=args.destination,
    )
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
