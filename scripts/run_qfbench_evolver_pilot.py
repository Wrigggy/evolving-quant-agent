#!/usr/bin/env python3
"""Run one A2/A3 evolver proposal and a small official activation panel."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from dataclasses import asdict, replace
from pathlib import Path

import yaml

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.benchmarks.qfbench import load_qfbench_baseline_snapshot  # noqa: E402
from qea.candidate_admission import (  # noqa: E402
    AdmissionPolicy,
    CandidateAdmissionError,
    admit_candidate,
)
from qea.evolution_evidence import authorize_evidence_tree  # noqa: E402
from qea.evolve_runtime import dir_unified_diff, snapshot_dir  # noqa: E402
from qea.loop_benchmark import hash_worker_directory  # noqa: E402
from qea.rootless_full_harness import (  # noqa: E402
    build_rootless_full_harness_runtime,
    load_rootless_full_harness_config,
)


def _atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")
    os.replace(temporary, path)


def _json(path: Path) -> object:
    return json.loads(path.read_text())


def _summary(summary) -> dict[str, object]:
    return {
        "scores": [asdict(score) for score in summary.scores],
        "task_rewards": dict(summary.task_rewards),
        "domain_scores": dict(summary.domain_scores),
        "task_mean": summary.task_mean,
        "overall": summary.overall,
    }


def _skill_names(candidate: Path) -> tuple[str, ...]:
    try:
        config = yaml.safe_load((candidate / "agent.yaml").read_text())
    except (OSError, yaml.YAMLError):
        return ()
    skills = config.get("skills", []) if isinstance(config, dict) else []
    names = []
    for raw in skills if isinstance(skills, list) else []:
        if not isinstance(raw, str):
            continue
        skill_path = candidate / raw.removeprefix("./") / "SKILL.md"
        try:
            lines = skill_path.read_text().splitlines()
            closing = next(
                index for index, line in enumerate(lines[1:], start=1)
                if line.strip() == "---"
            )
            metadata = yaml.safe_load("\n".join(lines[1:closing]))
        except (OSError, StopIteration, yaml.YAMLError):
            continue
        name = metadata.get("name") if isinstance(metadata, dict) else None
        if isinstance(name, str) and name:
            names.append(name)
    return tuple(sorted(set(names)))


def _activations(run_dir: Path, checkpoint: str, skills: tuple[str, ...]) -> dict:
    attempts = []
    for attempt_path in sorted(run_dir.glob("attempts/*/attempt.json")):
        attempt = _json(attempt_path)
        if attempt.get("checkpoint") != checkpoint:
            continue
        trace_path = attempt_path.with_name("raw-trace.jsonl")
        trace = trace_path.read_text(errors="replace") if trace_path.is_file() else ""
        activated = [
            name for name in skills
            if name in trace
            and ("<SkillDetails>" in trace or "Found the skill details" in trace)
        ]
        attempts.append({
            "attempt_id": attempt.get("attempt_id"),
            "task_id": attempt.get("task_id"),
            "activated_skills": activated,
            "trace_path": trace_path.relative_to(run_dir).as_posix(),
        })
    return {
        "declared_skills": list(skills),
        "attempts": attempts,
        "activation_count": sum(bool(item["activated_skills"]) for item in attempts),
    }


def _cost(run_dir: Path) -> dict[str, object]:
    records = []
    for path in sorted(run_dir.rglob("proxy-audit.jsonl")):
        for line in path.read_text().splitlines():
            if line.strip():
                records.append(json.loads(line))
    completed = [record for record in records if record.get("request_state") == "completed"]
    costs = [record.get("provider_cost_usd") for record in completed]
    tokens = [record.get("total_tokens") for record in completed]
    return {
        "completed_request_count": len(completed),
        "noncompleted_request_count": len(records) - len(completed),
        "provider_cost_usd": (
            sum(float(value) for value in costs)
            if completed and all(isinstance(value, (int, float)) for value in costs)
            else None
        ),
        "total_tokens": (
            sum(int(value) for value in tokens)
            if completed and all(isinstance(value, int) for value in tokens)
            else None
        ),
        "missing_cost_count": sum(value is None for value in costs),
        "missing_token_count": sum(value is None for value in tokens),
    }


def _selection_task_ids(selection: dict[str, object]) -> tuple[str, ...]:
    task_ids: list[str] = []
    for field in ("positive_task_cluster", "negative_task_cluster"):
        values = selection.get(field)
        if not isinstance(values, list) or not values:
            raise ValueError(f"evidence selection has no {field}")
        for value in values:
            if not isinstance(value, str) or not value or value in task_ids:
                raise ValueError(f"evidence selection has invalid {field}")
            task_ids.append(value)
    if len(task_ids) > 8:
        raise ValueError("autonomy pilot task panel is unexpectedly large")
    return tuple(task_ids)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("A2", "A3"), required=True)
    parser.add_argument("--qfbench-root", type=Path, required=True)
    parser.add_argument("--qfbench-manifest", type=Path, required=True)
    parser.add_argument("--rootless-config", type=Path, required=True)
    parser.add_argument("--rootless-image-set-manifest", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--evolver-dir", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--worker-concurrency", type=int, default=4)
    parser.add_argument("--verifier-concurrency", type=int, default=3)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--approve-external-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if (
        not args.preflight_only
        and not args.approve_external_run
        and os.environ.get("QEA_PAID_EVAL_AUTO_APPROVE") != "1"
    ):
        raise ValueError("external evolver/worker execution was not approved")
    source_evidence = authorize_evidence_tree(args.evidence_dir)
    selection = _json(source_evidence.root / "selection.json")
    if not isinstance(selection, dict):
        raise ValueError("evidence selection must be an object")
    if args.stage == "A3" and (
        selection.get("human_selected_parent") is not False
        or selection.get("human_selected_tasks") is not False
    ):
        raise ValueError("A3 evidence contains human parent or task selection")
    backbone_relative = selection.get("backbone_relative_path")
    if not isinstance(backbone_relative, str):
        raise ValueError("evidence selection has no backbone path")
    backbone_source = (source_evidence.root / backbone_relative).resolve()
    if (
        not backbone_source.is_relative_to(source_evidence.root)
        or not backbone_source.is_dir()
    ):
        raise ValueError("selected backbone path is unsafe")

    selected_task_ids = _selection_task_ids(selection)
    snapshot = load_qfbench_baseline_snapshot(
        args.qfbench_root, manifest_path=args.qfbench_manifest
    )
    full_panel = snapshot.primary.tasks + snapshot.diagnostic.tasks
    tasks_by_id = {task.task_id: task for task in full_panel}
    missing = sorted(set(selected_task_ids) - set(tasks_by_id))
    if missing:
        raise ValueError(f"unknown or excluded tasks: {missing}")
    selected_tasks = tuple(tasks_by_id[task_id] for task_id in selected_task_ids)

    results_root = args.results_dir.expanduser().resolve()
    run_dir = results_root / args.run_id
    evidence_root = run_dir / "authorized-evidence"
    if evidence_root.exists():
        evidence = authorize_evidence_tree(evidence_root)
        if (
            evidence.sha256 != source_evidence.sha256
            or evidence.members != source_evidence.members
        ):
            raise ValueError("persisted evidence identity differs")
    else:
        snapshot_dir(source_evidence.root, evidence_root)
        evidence = authorize_evidence_tree(evidence_root)
    backbone = run_dir / "workers" / "backbone"
    if backbone.exists():
        if hash_worker_directory(backbone) != hash_worker_directory(backbone_source):
            raise ValueError("persisted backbone identity differs")
    else:
        snapshot_dir(backbone_source, backbone)
    plan = {
        "schema_version": 1,
        "stage": args.stage,
        "run_id": args.run_id,
        "benchmark_commit": snapshot.commit,
        "task_ids": list(selected_task_ids),
        "evidence_sha256": evidence.sha256,
        "evidence_members": list(evidence.members),
        "selection": selection,
        "backbone_digest": hash_worker_directory(backbone),
        "evolver_dir": str(args.evolver_dir.resolve()),
    }
    plan_path = run_dir / "pilot-plan.json"
    if plan_path.is_file() and _json(plan_path) != plan:
        raise ValueError("persisted evolver-pilot plan differs")
    _atomic_json(plan_path, plan)
    if not args.preflight_only:
        _atomic_json(run_dir / "pilot-progress.json", {
            "schema_version": 1,
            "stage": args.stage,
            "run_id": args.run_id,
            "status": "starting",
            "task_ids": list(selected_task_ids),
            "evidence_sha256": evidence.sha256,
        })

    config = load_rootless_full_harness_config(args.rootless_config)
    config = replace(
        config,
        worker_concurrency=args.worker_concurrency,
        verifier_concurrency=args.verifier_concurrency,
    )
    runtime = build_rootless_full_harness_runtime(
        config=config,
        image_set_manifest=args.rootless_image_set_manifest,
        benchmark_commit=snapshot.commit,
        tasks=full_panel,
        run_id=args.run_id,
        results_root=results_root,
        include_evolver=True,
    )
    if args.preflight_only:
        runtime.close()
        report = {
            "schema_version": 1,
            "stage": args.stage,
            "run_id": args.run_id,
            "status": "preflight_complete",
            "selection": selection,
            "task_ids": list(selected_task_ids),
            "evidence_sha256": evidence.sha256,
            "model_request_count": 0,
        }
        _atomic_json(run_dir / "pilot-preflight.json", report)
        _atomic_json(run_dir / "pilot-progress.json", report)
        print(json.dumps(report, sort_keys=True, indent=2))
        return 0
    try:
        proposal = runtime.proposer.propose(
            candidate_dir=backbone,
            evidence_dir=evidence,
            evolver_dir=args.evolver_dir.resolve(),
            diagnosis={
                "stage": args.stage,
                "instruction": (
                    "Apply the generic recombination operator and selection contract "
                    "from authorized evidence. Infer the component from evidence; no "
                    "component, file, or implementation is prescribed by coordinator."
                ),
            },
            iteration=1,
            run_id=args.run_id,
            run_dir=run_dir,
        )
        candidate = proposal.candidate_dir
        try:
            admission = admit_candidate(
                backbone, candidate, AdmissionPolicy.qfbench_full()
            )
            admission_payload = asdict(admission)
        except CandidateAdmissionError as exc:
            admission_payload = {
                "admitted": False,
                "failure": f"{type(exc).__name__}: {exc}",
            }
        proposal_payload = {
            "candidate_dir": str(candidate),
            "candidate_digest": proposal.candidate_digest,
            "admission": admission_payload,
            "diff": dir_unified_diff(backbone, candidate),
            "prediction": _json(proposal.prediction_uri),
            "access_summary": _json(proposal.access_summary_uri),
            "summary": _json(proposal.summary_uri),
        }
        _atomic_json(run_dir / "proposal-report.json", proposal_payload)
        evaluation = None
        activation = None
        if admission_payload.get("admitted") is True:
            checkpoint = f"{args.stage.lower()}-candidate"
            evaluated = runtime.evaluator.evaluate(
                worker_dir=candidate,
                tasks=selected_tasks,
                split="mechanism-pilot",
                checkpoint=checkpoint,
                run_dir=run_dir,
            )
            evaluation = _summary(evaluated)
            activation = _activations(
                run_dir, checkpoint, _skill_names(candidate)
            )
    finally:
        runtime.close()

    report = {
        "schema_version": 1,
        "stage": args.stage,
        "run_id": args.run_id,
        "status": "complete",
        "proposal": proposal_payload,
        "evaluation": evaluation,
        "activation": activation,
        "cost": _cost(run_dir),
    }
    _atomic_json(run_dir / "pilot-report.json", report)
    _atomic_json(run_dir / "pilot-progress.json", report)
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
