#!/usr/bin/env python3
"""Audit A4 Evolver behavior separately from its directional task outcome."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Mapping

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


_COMPONENTS = frozenset(
    {
        "systemprompt",
        "agent_config",
        "tool_descriptions",
        "tools",
        "validator",
        "skills",
        "memory",
        "middleware",
        "routing",
    }
)


def _json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


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
            top = relative.split("/", 1)[0]
            if top in _COMPONENTS:
                result.add(top)
            else:
                result.add(f"other:{top}")
    return sorted(result)


def _summary(report: Mapping[str, object], arm: str) -> Mapping[str, object]:
    summaries = report.get("summaries")
    if not isinstance(summaries, Mapping) or arm not in summaries:
        raise ValueError(f"pilot report has no arm {arm!r}")
    summary = summaries[arm]
    if not isinstance(summary, Mapping):
        raise ValueError(f"pilot summary for arm {arm!r} is invalid")
    return summary


def _rewards(summary: Mapping[str, object]) -> dict[str, float]:
    values = summary.get("task_rewards")
    if not isinstance(values, Mapping):
        raise ValueError("pilot summary has no task reward vector")
    return {str(task_id): float(reward) for task_id, reward in values.items()}


def _accessed_task_ids(
    access_summary: Mapping[str, object],
    expected_tasks: set[str],
) -> list[str]:
    paths = access_summary.get("evidence_paths")
    if not isinstance(paths, list):
        return []
    accessed: set[str] = set()
    for value in paths:
        if not isinstance(value, str) or not value.startswith("tasks/"):
            continue
        parts = value.split("/", 2)
        if len(parts) >= 2 and parts[1] in expected_tasks:
            accessed.add(parts[1])
    return sorted(accessed)


def audit(
    *,
    a4_manifest: Mapping[str, object],
    proposal_report: Mapping[str, object],
    seed_report: Mapping[str, object],
    candidate_report: Mapping[str, object],
    seed_arm: str,
    candidate_arm: str,
) -> dict[str, object]:
    """Return fixed process checks plus secondary score deltas."""

    panel = a4_manifest.get("panel")
    if not isinstance(panel, Mapping):
        raise ValueError("A4 manifest has no panel")
    targets = [str(item["task_id"]) for item in panel.get("targets", [])]
    protections = [
        str(item["task_id"]) for item in panel.get("protections", [])
    ]
    expected_tasks = set(targets + protections)
    if len(expected_tasks) != len(targets) + len(protections):
        raise ValueError("A4 panel task membership is invalid")

    proposal = proposal_report.get("proposal")
    if not isinstance(proposal, Mapping):
        raise ValueError("proposal report has no proposal")
    admission = proposal.get("admission")
    admission = dict(admission) if isinstance(admission, Mapping) else {}
    diff = str(proposal.get("diff", ""))
    prediction = proposal.get("prediction")
    prediction = dict(prediction) if isinstance(prediction, Mapping) else {}
    access = proposal.get("access_summary")
    access = dict(access) if isinstance(access, Mapping) else {}
    evolver_summary = proposal.get("summary")
    evolver_summary = (
        dict(evolver_summary) if isinstance(evolver_summary, Mapping) else {}
    )
    discovery = evolver_summary.get("discovery")
    discovery = dict(discovery) if isinstance(discovery, Mapping) else {}
    checks = discovery.get("checks")
    checks = dict(checks) if isinstance(checks, Mapping) else {}
    changed_components = _changed_components(diff)
    declared_component = prediction.get("component_changed")
    accessed_tasks = _accessed_task_ids(access, expected_tasks)
    grounded_ratio = discovery.get("grounded_citation_ratio")
    trace_files = discovery.get("trace_files_accessed")

    process_checks = {
        "candidate_admitted": admission.get("admitted") is True,
        "nonempty_candidate_diff": bool(diff.strip()),
        "writes_unlocked": checks.get("writes_unlocked") is True,
        "multiple_hypotheses": checks.get("multiple_hypotheses") is True,
        "counterevidence_recorded": checks.get("counterevidence_recorded") is True,
        "falsifiable_prediction_recorded": checks.get(
            "falsifiable_prediction_recorded"
        )
        is True,
        "final_mechanism_consistent": checks.get("final_mechanism_consistent")
        is True,
        "final_component_consistent": checks.get("final_component_consistent")
        is True,
        "at_least_two_tasks_inspected": len(accessed_tasks) >= 2,
        "at_least_two_raw_traces_inspected": isinstance(trace_files, int)
        and trace_files >= 2,
        "grounded_citation_ratio_at_least_0_8": isinstance(
            grounded_ratio, (int, float)
        )
        and not isinstance(grounded_ratio, bool)
        and grounded_ratio >= 0.8,
        "declared_component_matches_diff": isinstance(declared_component, str)
        and declared_component in changed_components,
    }
    process_gate = all(process_checks.values())

    seed = _rewards(_summary(seed_report, seed_arm))
    candidate = _rewards(_summary(candidate_report, candidate_arm))
    if set(seed) != expected_tasks or set(candidate) != expected_tasks:
        raise ValueError("seed or candidate score vector differs from the A4 panel")
    deltas = {
        task_id: candidate[task_id] - seed[task_id]
        for task_id in sorted(expected_tasks)
    }
    target_gains = [task_id for task_id in targets if deltas[task_id] > 0]
    target_regressions = [task_id for task_id in targets if deltas[task_id] < 0]
    protection_regressions = [
        task_id for task_id in protections if deltas[task_id] < 0
    ]

    return {
        "schema_version": 1,
        "stage": "A4",
        "interpretation": {
            "primary": "observable Evolver discovery and intervention behavior",
            "secondary": "one-pass directional task and protection deltas",
            "not_measured": [
                "statistical significance",
                "multi-round stability",
                "semantic truth of the claimed causal mechanism",
            ],
        },
        "process": {
            "checks": process_checks,
            "gate_passed": process_gate,
            "contract_score": discovery.get("contract_score"),
            "accessed_task_ids": accessed_tasks,
            "changed_components": changed_components,
            "declared_component": declared_component,
            "hypotheses_considered_count": discovery.get(
                "hypotheses_considered_count"
            ),
            "exact_evidence_access_count": discovery.get(
                "exact_evidence_access_count"
            ),
            "evidence_access_ratio": discovery.get("evidence_access_ratio"),
            "grounded_citation_ratio": grounded_ratio,
            "trace_files_accessed": trace_files,
            "semantic_prediction_audit_required": True,
        },
        "outcome": {
            "seed_rewards": seed,
            "candidate_rewards": candidate,
            "task_deltas": deltas,
            "target_gains": target_gains,
            "target_regressions": target_regressions,
            "protection_regressions": protection_regressions,
            "target_gain_count": len(target_gains),
            "protection_regression_count": len(protection_regressions),
        },
        "multi_round_readiness": (
            "manual_causal_audit_required" if process_gate else "not_ready"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--a4-manifest", type=Path, required=True)
    parser.add_argument("--proposal-run", type=Path, required=True)
    parser.add_argument("--seed-run", type=Path, required=True)
    parser.add_argument("--candidate-run", type=Path, required=True)
    parser.add_argument("--seed-arm", default="seed-evidence")
    parser.add_argument("--candidate-arm", default="candidate")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = audit(
        a4_manifest=_json(args.a4_manifest.resolve()),
        proposal_report=_json(args.proposal_run.resolve() / "pilot-report.json"),
        seed_report=_json(args.seed_run.resolve() / "pilot-report.json"),
        candidate_report=_json(args.candidate_run.resolve() / "pilot-report.json"),
        seed_arm=args.seed_arm,
        candidate_arm=args.candidate_arm,
    )
    _atomic_json(args.output.expanduser().resolve(), report)
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
