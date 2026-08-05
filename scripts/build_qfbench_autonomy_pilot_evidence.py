#!/usr/bin/env python3
"""Build answer-free A2 or A3 recombination evidence from a prior run archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.evolution_evidence import authorize_evidence_tree  # noqa: E402
from qea.worker_identity import hash_worker_directory  # noqa: E402


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")


def _evaluation(path: Path) -> dict:
    payload = json.loads(path.read_text())
    summary = payload.get("summary")
    rewards = summary.get("task_rewards") if isinstance(summary, dict) else None
    if not isinstance(rewards, dict):
        raise ValueError(f"evaluation has no task reward vector: {path}")
    return {
        "overall": float(summary["overall"]),
        "task_rewards": {str(key): float(value) for key, value in rewards.items()},
        "worker_digest": str(payload["worker_digest"]),
    }


def _archive(run: Path) -> dict[str, dict]:
    evaluations = run / "evaluations"
    workers = run / "workers"
    seed_eval = next(iter(sorted(evaluations.glob("seed-optimize-*.json"))), None)
    if seed_eval is None:
        raise ValueError("archive has no seed optimize evaluation")
    result = {"seed": {
        "worker": workers / "seed",
        "evaluation": _evaluation(seed_eval),
    }}
    for path in sorted(evaluations.glob("iteration-*-candidate-*.json")):
        iteration = int(path.name.split("-", 2)[1])
        label = f"iteration-{iteration:02d}-candidate"
        worker = workers / label
        if worker.is_dir():
            result[label] = {"worker": worker, "evaluation": _evaluation(path)}
    if len(result) < 2:
        raise ValueError("archive has no evaluated candidate parents")
    return result


def _vectors(archive: dict[str, dict]) -> dict[str, dict]:
    seed = archive["seed"]["evaluation"]["task_rewards"]
    vectors = {}
    for label, item in archive.items():
        rewards = item["evaluation"]["task_rewards"]
        if set(rewards) != set(seed):
            raise ValueError(f"task vector membership differs for {label}")
        positive = sorted(task for task in seed if rewards[task] > seed[task])
        negative = sorted(task for task in seed if rewards[task] < seed[task])
        unchanged = sorted(task for task in seed if rewards[task] == seed[task])
        vectors[label] = {
            "overall": item["evaluation"]["overall"],
            "positive_flips": positive,
            "negative_flips": negative,
            "unchanged_count": len(unchanged),
            "task_rewards": rewards,
            "worker_digest": item["evaluation"]["worker_digest"],
        }
    return vectors


def _automated_selection(vectors: dict[str, dict]) -> dict[str, object]:
    candidates = [
        label for label in vectors
        if label != "seed" and vectors[label]["positive_flips"]
    ]
    if not candidates:
        raise ValueError("archive has no candidate with a positive flip")
    source = max(
        candidates,
        key=lambda label: (
            len(vectors[label]["positive_flips"]),
            -len(vectors[label]["negative_flips"]),
            vectors[label]["overall"],
            label,
        ),
    )
    backbone = max(
        vectors,
        key=lambda label: (
            vectors[label]["overall"],
            -len(vectors[label]["negative_flips"]),
            label == "seed",
            label,
        ),
    )
    return {
        "selection_method": "max positive flips, then min negative flips, then overall",
        "source_parent": source,
        "backbone_parent": backbone,
        "positive_task_cluster": vectors[source]["positive_flips"],
        "negative_task_cluster": vectors[source]["negative_flips"],
        "human_selected_parent": False,
        "human_selected_tasks": False,
    }


def _build(
    root: Path,
    *,
    stage: str,
    archive: dict[str, dict],
    vectors: dict[str, dict],
    source_parent: str | None,
    backbone_parent: str | None,
) -> None:
    (root / "access_log.jsonl").write_text("")
    _write_json(root / "operator.json", {
        "operator": "translocation",
        "definition": (
            "Identify a reusable behavior associated with a source parent's positive "
            "task flips, then move or re-express that behavior in the backbone with a "
            "smaller and explicitly validated blast radius. The operator does not "
            "prescribe a component, file, or implementation."
        ),
        "forbidden_shortcut": "Do not copy task answers, task-specific constants, or replace the backbone wholesale.",
    })
    _write_json(root / "task_vectors.json", {
        "provenance": "official scalar rewards from the archived train panel",
        "vectors": vectors,
    })
    if stage == "A2":
        if source_parent not in archive or backbone_parent not in archive:
            raise ValueError("A2 parent label is unavailable")
        selection = {
            "source_parent": source_parent,
            "backbone_parent": backbone_parent,
            "positive_task_cluster": vectors[source_parent]["positive_flips"],
            "negative_task_cluster": vectors[source_parent]["negative_flips"],
            "human_selected_parent": True,
            "human_selected_tasks": True,
        }
        shutil.copytree(archive[backbone_parent]["worker"], root / "parents/backbone")
        shutil.copytree(archive[source_parent]["worker"], root / "parents/source")
        backbone_relative = "parents/backbone"
    else:
        selection = _automated_selection(vectors)
        for label, item in archive.items():
            shutil.copytree(item["worker"], root / "archive" / label)
        backbone_relative = f"archive/{selection['backbone_parent']}"
        positive_support = Counter()
        negative_support = Counter()
        for label, vector in vectors.items():
            if label == "seed":
                continue
            positive_support.update(vector["positive_flips"])
            negative_support.update(vector["negative_flips"])
        _write_json(root / "debugger_overview.json", {
            "generator": "deterministic archive task-vector debugger",
            "positive_support": dict(sorted(positive_support.items())),
            "negative_support": dict(sorted(negative_support.items())),
            "selection": selection,
            "rejected_buffer": sorted(label for label in vectors if label != "seed"),
        })
    _write_json(root / "selection.json", {
        **selection,
        "backbone_relative_path": backbone_relative,
    })
    _write_json(root / "contract.json", {
        "schema_version": 1,
        "stage": stage,
        "goal": "operator-guided reusable harness recombination",
        "component_hint": None,
        "file_hint": None,
        "implementation_hint": None,
        "private_evaluator_feedback": False,
        "held_out_feedback": False,
        "required_outcome": (
            "Choose the component from evidence, wire it into the candidate, and "
            "validate that it is behaviorally reachable."
        ),
    })
    _write_json(root / "archive_manifest.json", {
        "parents": {
            label: {
                "worker_digest": hash_worker_directory(item["worker"]),
                "overall": item["evaluation"]["overall"],
            }
            for label, item in sorted(archive.items())
        }
    })


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-run", type=Path, required=True)
    parser.add_argument("--stage", choices=("A2", "A3"), required=True)
    parser.add_argument("--source-parent")
    parser.add_argument("--backbone-parent")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.stage == "A2" and not (args.source_parent and args.backbone_parent):
        parser.error("A2 requires explicit source and backbone parents")
    if args.stage == "A3" and (args.source_parent or args.backbone_parent):
        parser.error("A3 forbids human parent selection")
    archive_run = args.archive_run.expanduser().resolve()
    archive = _archive(archive_run)
    vectors = _vectors(archive)
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=output.name + ".", dir=output.parent) as temp:
        staged = Path(temp) / "evidence"
        staged.mkdir()
        _build(
            staged,
            stage=args.stage,
            archive=archive,
            vectors=vectors,
            source_parent=args.source_parent,
            backbone_parent=args.backbone_parent,
        )
        record = authorize_evidence_tree(staged)
        if output.exists():
            existing = authorize_evidence_tree(output)
            if existing.sha256 != record.sha256 or existing.members != record.members:
                raise ValueError("refusing to replace a different evidence identity")
        else:
            os.replace(staged, output)
    record = authorize_evidence_tree(output)
    print(json.dumps({
        "stage": args.stage,
        "root": str(record.root),
        "sha256": record.sha256,
        "members": list(record.members),
    }, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
