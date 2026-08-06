#!/usr/bin/env python3
"""Build raw or debugger-indexed post-A3 evidence for a discovery canary."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.evolution_evidence import authorize_evidence_tree  # noqa: E402


_CREDENTIAL = re.compile(
    r"(?i)(?:Bearer\s+|\bsk-[A-Za-z0-9_-]*)([A-Za-z0-9._-]{12,})"
)
_PRIVATE_PARTS = frozenset(
    {
        "tests",
        "solution",
        "official-tests",
        "official_tests",
        "reference-data",
        "reference_data",
        "trusted-verifier",
        "trusted_verifier",
        "gold",
    }
)


def _json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"required regular JSON file is unavailable: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON file {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"JSON file must contain an object: {path}")
    return payload


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _sanitize_text(text: str) -> tuple[str, int]:
    redactions = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal redactions
        redactions += 1
        prefix = "Bearer " if match.group(0).casefold().startswith("bearer") else "sk-"
        return prefix + "[REDACTED]"

    return _CREDENTIAL.sub(replace, text), redactions


def _copy_text(source: Path, destination: Path) -> int:
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"evidence source must be regular: {source}")
    if any(part.casefold() in _PRIVATE_PARTS for part in source.parts):
        raise ValueError(f"private evaluator path is forbidden: {source}")
    try:
        text = source.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"evidence source is not UTF-8: {source}") from exc
    sanitized, redactions = _sanitize_text(text)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(sanitized, encoding="utf-8")
    return redactions


def _public_score(score: dict) -> dict[str, object]:
    return {
        "schema_version": 1,
        "task_id": str(score["task_id"]),
        "official_reward": float(score["reward"]),
        "diagnostic_tags": sorted(
            str(value) for value in score.get("diagnostic_tags", [])
        ),
        "tests_passed": score.get("tests_passed"),
        "tests_failed": score.get("tests_failed"),
        "provenance": "official scalar and answer-free public diagnostics",
    }


def _pilot_summary(run: Path) -> dict[str, object]:
    report = _json(run / "pilot-report.json")
    evaluation = report.get("evaluation")
    evaluation = dict(evaluation) if isinstance(evaluation, dict) else {}
    activation = report.get("activation")
    activation = dict(activation) if isinstance(activation, dict) else {}
    proposal = report.get("proposal")
    proposal = dict(proposal) if isinstance(proposal, dict) else {}
    prediction = proposal.get("prediction")
    prediction = dict(prediction) if isinstance(prediction, dict) else {}
    return {
        "run_id": report.get("run_id", run.name),
        "stage": report.get("stage"),
        "status": report.get("status"),
        "task_rewards": evaluation.get("task_rewards"),
        "task_mean": evaluation.get("task_mean"),
        "overall": evaluation.get("overall"),
        "activation_count": activation.get("activation_count"),
        "declared_skills": activation.get("declared_skills"),
        "component_changed": prediction.get("component_changed"),
        "failure_kind": prediction.get("failure_kind"),
        "cost": report.get("cost"),
    }


def _changed_components(diff: str) -> list[str]:
    result: set[str] = set()
    for line in diff.splitlines():
        if not line.startswith("+++ b/"):
            continue
        relative = line[len("+++ b/") :]
        if relative == "systemprompt.md":
            result.add("systemprompt")
        elif relative == "agent.yaml":
            result.add("agent_config")
        else:
            result.add(relative.split("/", 1)[0])
    return sorted(result)


def _candidate_tree(source: Path, destination: Path) -> int:
    redactions = 0
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"candidate symlink is forbidden: {path}")
        if path.is_file():
            redactions += _copy_text(path, destination / path.relative_to(source))
    return redactions


def build(
    *,
    a1_run: Path,
    a2_run: Path,
    a3_run: Path,
    destination: Path,
    mode: str,
) -> dict[str, object]:
    runs = {"A1": a1_run.resolve(), "A2": a2_run.resolve(), "A3": a3_run.resolve()}
    for label, run in runs.items():
        if run.is_symlink() or not run.is_dir():
            raise ValueError(f"{label} run is unavailable: {run}")
    if destination.exists():
        raise ValueError(f"destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = Path(
        tempfile.mkdtemp(prefix=destination.name + ".tmp-", dir=destination.parent)
    )
    redactions = 0
    try:
        (temporary / "access_log.jsonl").write_text("", encoding="utf-8")
        _write_json(
            temporary / "contract.json",
            {
                "schema_version": 1,
                "purpose": "exploratory post-A3 harness discovery canary",
                "mode": mode,
                "held_out_feedback": False,
                "private_evaluator_feedback": False,
                "official_solution": False,
                "candidate_goal": (
                    "Diagnose the A3 behavior from public outcomes and worker traces, "
                    "then test one generalizable harness mechanism."
                ),
            },
        )
        history = {label: _pilot_summary(run) for label, run in runs.items()}
        _write_json(temporary / "history" / "a1-a3.json", history)

        a3_report = _json(a3_run / "pilot-report.json")
        proposal = _json(a3_run / "proposal-report.json")
        diff = str(proposal.get("diff", ""))
        sanitized_diff, count = _sanitize_text(diff)
        redactions += count
        (temporary / "candidate" / "a3-change.patch").parent.mkdir(
            parents=True, exist_ok=True
        )
        (temporary / "candidate" / "a3-change.patch").write_text(
            sanitized_diff, encoding="utf-8"
        )
        _write_json(
            temporary / "prior" / "a3-proposal.json",
            {
                "prediction": proposal.get("prediction"),
                "access_summary": proposal.get("access_summary"),
                "summary": proposal.get("summary"),
                "admission_checks": (
                    proposal.get("admission", {}).get("checks")
                    if isinstance(proposal.get("admission"), dict)
                    else None
                ),
                "changed_components": _changed_components(diff),
            },
        )
        authorized = a3_run / "authorized-evidence"
        for name in ("task_vectors.json", "selection.json", "debugger_overview.json"):
            if (authorized / name).is_file():
                redactions += _copy_text(
                    authorized / name, temporary / "prior" / name
                )
        redactions += _candidate_tree(
            a3_run / "workers" / "backbone",
            temporary / "candidate" / "pre-a3",
        )
        redactions += _candidate_tree(
            a3_run / "evolutions" / "iteration-0001" / "candidate",
            temporary / "candidate" / "post-a3",
        )

        activation_by_task: dict[str, dict[str, object]] = {}
        activation = a3_report.get("activation")
        if isinstance(activation, dict):
            for item in activation.get("attempts", []):
                if isinstance(item, dict) and isinstance(item.get("task_id"), str):
                    activation_by_task[item["task_id"]] = {
                        "activated_skills": item.get("activated_skills", []),
                        "attempt_id": item.get("attempt_id"),
                    }

        task_rows: list[dict[str, object]] = []
        for attempt_path in sorted((a3_run / "attempts").glob("*/attempt.json")):
            attempt = _json(attempt_path)
            task_id = str(attempt.get("task_id", ""))
            if not task_id:
                raise ValueError(f"attempt has no task ID: {attempt_path}")
            attempt_dir = attempt_path.parent
            score = _public_score(_json(attempt_dir / "completed-score.json"))
            task_root = temporary / "tasks" / task_id
            _write_json(task_root / "public_evaluation.json", score)
            execution_path = attempt_dir / "worker-execution.json"
            process_summary = None
            if execution_path.is_file():
                execution = _json(execution_path)
                process_summary = execution.get("summary", {})
                _write_json(task_root / "process_summary.json", process_summary)
            redactions += _copy_text(
                attempt_dir / "raw-trace.jsonl", task_root / "worker_trace.jsonl"
            )
            if (attempt_dir / "final.txt").is_file():
                redactions += _copy_text(
                    attempt_dir / "final.txt", task_root / "worker_final.txt"
                )
            activation_item = activation_by_task.get(task_id, {})
            task_rows.append(
                {
                    "task_id": task_id,
                    "official_reward": score["official_reward"],
                    "diagnostic_tags": score["diagnostic_tags"],
                    "activated_skills": activation_item.get("activated_skills", []),
                    "paths": {
                        "evaluation": f"tasks/{task_id}/public_evaluation.json",
                        "trace": f"tasks/{task_id}/worker_trace.jsonl",
                        "process": (
                            f"tasks/{task_id}/process_summary.json"
                            if process_summary is not None
                            else None
                        ),
                    },
                }
            )

        if mode == "indexed":
            task_vectors = _json(authorized / "task_vectors.json")
            selection = _json(authorized / "selection.json")
            vectors = task_vectors.get("vectors", {})
            backbone_label = str(selection.get("backbone_parent", ""))
            backbone = vectors.get(backbone_label, {}) if isinstance(vectors, dict) else {}
            backbone_rewards = (
                backbone.get("task_rewards", {}) if isinstance(backbone, dict) else {}
            )
            deltas = {
                row["task_id"]: float(row["official_reward"])
                - float(backbone_rewards.get(row["task_id"], row["official_reward"]))
                for row in task_rows
            }
            activation_count = sum(bool(row["activated_skills"]) for row in task_rows)
            _write_json(
                temporary / "debugger" / "overview.json",
                {
                    "schema_version": 1,
                    "generator": "deterministic evidence librarian; not root-cause oracle",
                    "task_count": len(task_rows),
                    "activation_count": activation_count,
                    "activation_rate": activation_count / len(task_rows) if task_rows else 0,
                    "all_selected_tasks_activated": activation_count == len(task_rows),
                    "outcome_deltas_vs_pre_a3_backbone": deltas,
                    "positive_tasks": sorted(task for task, value in deltas.items() if value > 0),
                    "negative_tasks": sorted(task for task, value in deltas.items() if value < 0),
                    "unchanged_tasks": sorted(task for task, value in deltas.items() if value == 0),
                    "observed_anomalies": [
                        "the declared skill activated on every selected task",
                        "activation coincided with positive, negative, and unchanged outcomes",
                    ],
                    "unresolved_questions": [
                        "what trace condition caused broad activation",
                        "whether routing, skill description, global prompt, or another component should localize the behavior",
                    ],
                },
            )
            _write_json(temporary / "debugger" / "task_index.json", task_rows)
            _write_json(
                temporary / "debugger" / "change_outcome.json",
                {
                    "schema_version": 1,
                    "changed_components": _changed_components(diff),
                    "declared_skills": (
                        a3_report.get("activation", {}).get("declared_skills", [])
                        if isinstance(a3_report.get("activation"), dict)
                        else []
                    ),
                    "task_activation_and_delta": [
                        {
                            "task_id": row["task_id"],
                            "activated_skills": row["activated_skills"],
                            "reward_delta": deltas[row["task_id"]],
                        }
                        for row in task_rows
                    ],
                    "interpretation_boundary": (
                        "This graph records association and reachability. The evolver "
                        "must inspect traces before claiming a cause."
                    ),
                },
            )

        _write_json(
            temporary / "sanitization.json",
            {
                "schema_version": 1,
                "credential_redactions": redactions,
                "copied_private_evaluator_material": False,
                "copied_official_solutions": False,
                "copied_held_out_feedback": False,
            },
        )
        record = authorize_evidence_tree(temporary)
        os.replace(temporary, destination)
        temporary = None
        return {
            "schema_version": 1,
            "mode": mode,
            "destination": str(destination),
            "sha256": record.sha256,
            "member_count": len(record.members),
            "members": list(record.members),
            "credential_redactions": redactions,
        }
    finally:
        if temporary is not None and temporary.exists():
            shutil.rmtree(temporary)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--a1-run", type=Path, required=True)
    parser.add_argument("--a2-run", type=Path, required=True)
    parser.add_argument("--a3-run", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--mode", choices=("raw", "indexed"), required=True)
    args = parser.parse_args(argv)
    report = build(
        a1_run=args.a1_run,
        a2_run=args.a2_run,
        a3_run=args.a3_run,
        destination=args.destination.expanduser().resolve(),
        mode=args.mode,
    )
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
