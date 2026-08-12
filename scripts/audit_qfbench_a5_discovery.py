#!/usr/bin/env python3
"""Audit A5 discovery behavior, task outcomes, and harness capabilities."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Mapping

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.harness_capability import (  # noqa: E402
    capability_delta,
    measure_checkpoint_capability,
)


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


def _label_path(value: str) -> tuple[str, Path]:
    label, separator, raw_path = value.partition("=")
    if not separator or not label:
        raise argparse.ArgumentTypeError("value must be LABEL=PATH")
    path = Path(raw_path).expanduser().resolve()
    if not path.is_dir():
        raise argparse.ArgumentTypeError(f"run directory is unavailable: {path}")
    return label, path


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
            result.add(top if top in _COMPONENTS else f"other:{top}")
    return sorted(result)


def _summary(report: Mapping[str, object], arm: str) -> Mapping[str, object]:
    summaries = report.get("summaries")
    if not isinstance(summaries, Mapping) or arm not in summaries:
        raise ValueError(f"component report has no arm {arm!r}")
    summary = summaries[arm]
    if not isinstance(summary, Mapping):
        raise ValueError(f"component summary for {arm!r} is invalid")
    return summary


def _checkpoint(report: Mapping[str, object], arm: str) -> str:
    activations = report.get("activations")
    if not isinstance(activations, Mapping) or arm not in activations:
        raise ValueError(f"component report has no activation arm {arm!r}")
    activation = activations[arm]
    if not isinstance(activation, Mapping):
        raise ValueError(f"activation for {arm!r} is invalid")
    checkpoint = activation.get("checkpoint")
    if not isinstance(checkpoint, str) or not checkpoint:
        raise ValueError(f"activation for {arm!r} has no checkpoint")
    return checkpoint


def _task_outcomes(
    summary: Mapping[str, object],
) -> dict[str, dict[str, float | None]]:
    scores = summary.get("scores")
    if not isinstance(scores, list):
        raise ValueError("component summary has no score vector")
    result: dict[str, dict[str, float]] = {}
    for score in scores:
        if not isinstance(score, Mapping):
            continue
        task_id = str(score.get("task_id", ""))
        passed = score.get("tests_passed")
        failed = score.get("tests_failed")
        if isinstance(passed, int) and isinstance(failed, int) and passed + failed:
            pass_fraction = passed / (passed + failed)
        else:
            pass_fraction = None
        result[task_id] = {
            "reward": float(score.get("reward", 0.0)),
            "pass_fraction": pass_fraction,
        }
    return result


def _outcome_delta(
    before: Mapping[str, Mapping[str, float | None]],
    after: Mapping[str, Mapping[str, float | None]],
) -> dict[str, object]:
    if set(before) != set(after):
        raise ValueError("candidate and seed task panels differ")
    vectors: dict[str, dict[str, float | None]] = {}
    for task_id in sorted(before):
        before_reward = before[task_id]["reward"]
        after_reward = after[task_id]["reward"]
        if not isinstance(before_reward, float) or not isinstance(after_reward, float):
            raise ValueError(f"task reward is unavailable: {task_id}")
        before_pass = before[task_id]["pass_fraction"]
        after_pass = after[task_id]["pass_fraction"]
        pass_delta = (
            after_pass - before_pass
            if isinstance(before_pass, float) and isinstance(after_pass, float)
            else None
        )
        vectors[task_id] = {
            "reward": after_reward - before_reward,
            "pass_fraction": pass_delta,
        }
    comparable_pass_deltas = [
        value["pass_fraction"]
        for value in vectors.values()
        if isinstance(value["pass_fraction"], float)
    ]
    return {
        "task_vectors": vectors,
        "reward_gain_count": sum(value["reward"] > 0 for value in vectors.values()),
        "reward_regression_count": sum(
            value["reward"] < 0 for value in vectors.values()
        ),
        "mean_reward_delta": sum(value["reward"] for value in vectors.values())
        / len(vectors),
        "pass_fraction_comparable_count": len(comparable_pass_deltas),
        "mean_pass_fraction_delta": (
            sum(comparable_pass_deltas) / len(comparable_pass_deltas)
            if comparable_pass_deltas
            else None
        ),
    }


def audit(
    *,
    manifest: Mapping[str, object],
    seed_run: Path,
    seed_arm: str,
    proposal_runs: Mapping[str, Path],
    candidate_run: Path | None,
) -> dict[str, object]:
    panel = manifest.get("panel")
    if not isinstance(panel, Mapping):
        raise ValueError("A5 manifest has no panel")
    task_ids = [str(value) for value in panel.get("task_ids", [])]
    targets = {str(item["task_id"]) for item in panel.get("targets", [])}
    protections = {
        str(item["task_id"]) for item in panel.get("protections", [])
    }
    sentinel_items = panel.get("sentinels")
    if sentinel_items is None:
        sentinel_items = panel.get("coverage_sentinels", [])
    sentinels = {str(item["task_id"]) for item in sentinel_items}
    if set(task_ids) != targets | protections | sentinels:
        raise ValueError("discovery panel roles do not match task_ids")
    if (targets & protections) or (targets & sentinels) or (protections & sentinels):
        raise ValueError("discovery panel roles overlap")

    seed_report = _json(seed_run / "pilot-report.json")
    seed_summary = _summary(seed_report, seed_arm)
    seed_checkpoint = _checkpoint(seed_report, seed_arm)
    seed_outcomes = _task_outcomes(seed_summary)
    seed_capability = measure_checkpoint_capability(
        run_dir=seed_run,
        checkpoint=seed_checkpoint,
        task_ids=task_ids,
    )
    candidate_report = (
        _json(candidate_run / "pilot-report.json")
        if candidate_run is not None
        else None
    )

    arms: dict[str, object] = {}
    for label, run_dir in sorted(proposal_runs.items()):
        report = _json(run_dir / "pilot-report.json")
        proposal = report.get("proposal")
        if not isinstance(proposal, Mapping):
            raise ValueError(f"proposal report for {label!r} has no proposal")
        prediction = proposal.get("prediction")
        prediction = dict(prediction) if isinstance(prediction, Mapping) else {}
        summary = proposal.get("summary")
        summary = dict(summary) if isinstance(summary, Mapping) else {}
        discovery = summary.get("discovery")
        discovery = dict(discovery) if isinstance(discovery, Mapping) else {}
        decision = str(proposal.get("decision", discovery.get("decision", ""))).upper()
        diff = str(proposal.get("diff", ""))
        changed_components = _changed_components(diff)
        declared = discovery.get("components_selected")
        declared_components = (
            sorted(str(value) for value in declared)
            if isinstance(declared, list)
            else []
        )
        arm_payload: dict[str, object] = {
            "run_id": report.get("run_id"),
            "decision": decision,
            "discovery": discovery,
            "changed_components": changed_components,
            "declared_components": declared_components,
            "declared_components_match_diff": (
                changed_components == declared_components
            ),
            "admission": proposal.get("admission"),
            "cost": report.get("cost"),
            "prediction": prediction,
        }
        if decision == "ACT":
            if candidate_report is None or candidate_run is None:
                arm_payload["candidate_evaluation"] = "missing"
            else:
                candidate_summary = _summary(candidate_report, label)
                candidate_outcomes = _task_outcomes(candidate_summary)
                candidate_checkpoint = _checkpoint(candidate_report, label)
                candidate_capability = measure_checkpoint_capability(
                    run_dir=candidate_run,
                    checkpoint=candidate_checkpoint,
                    task_ids=task_ids,
                )
                outcome = _outcome_delta(seed_outcomes, candidate_outcomes)
                outcome["target_reward_gain_count"] = sum(
                    outcome["task_vectors"][task_id]["reward"] > 0
                    for task_id in targets
                )
                outcome["protection_reward_regression_count"] = sum(
                    outcome["task_vectors"][task_id]["reward"] < 0
                    for task_id in protections
                )
                outcome["sentinel_reward_change_count"] = sum(
                    outcome["task_vectors"][task_id]["reward"] != 0
                    for task_id in sentinels
                )
                target_regressions = [
                    task_id
                    for task_id in sorted(targets)
                    if outcome["task_vectors"][task_id]["reward"] < 0
                ]
                protection_regressions = [
                    task_id
                    for task_id in sorted(protections)
                    if outcome["task_vectors"][task_id]["reward"] < 0
                ]
                sentinel_changes = {
                    task_id: outcome["task_vectors"][task_id]
                    for task_id in sorted(sentinels)
                }
                arm_payload["candidate_evaluation"] = {
                    "outcome": outcome,
                    "target_regressions": target_regressions,
                    "protection_regressions": protection_regressions,
                    "sentinel_changes": sentinel_changes,
                    "harness_capability": candidate_capability,
                    "harness_capability_delta": capability_delta(
                        seed_capability, candidate_capability
                    ),
                }
        elif decision == "ABSTAIN":
            arm_payload["candidate_evaluation"] = "not_applicable_abstained"
        else:
            arm_payload["candidate_evaluation"] = "invalid_missing_decision"
        arms[label] = arm_payload

    comparison: dict[str, object] | None = None
    if {"failure_only", "contrastive"} <= set(arms):
        left = arms["failure_only"]
        right = arms["contrastive"]
        left_d = left["discovery"]
        right_d = right["discovery"]
        comparison = {
            "scope": "effect of requiring minimal success counterfactuals; descriptive engineering comparison",
            "failure_only_decision": left["decision"],
            "contrastive_decision": right["decision"],
            "metric_deltas_contrastive_minus_failure_only": {
                key: float(right_d.get(key, 0) or 0)
                - float(left_d.get(key, 0) or 0)
                for key in (
                    "contract_score",
                    "recurrent_failure_type_count",
                    "typed_failure_task_count",
                    "hypotheses_eliminated_count",
                    "probe_count",
                    "success_counterfactual_count",
                    "insufficient_contrast_count",
                    "grounded_citation_ratio",
                )
            },
            "interpretation_required": (
                "A positive counterfactual count is useful only if hypothesis "
                "elimination, decision calibration, component localization, or "
                "candidate behavior also improves. Token volume alone is not uplift."
            ),
        }
    return {
        "schema_version": 1,
        "stage": "A5",
        "panel": {
            "task_ids": task_ids,
            "target_count": len(targets),
            "protection_count": len(protections),
            "sentinel_count": len(sentinels),
        },
        "seed_harness_capability": seed_capability,
        "arms": arms,
        "success_counterfactual_comparison": comparison,
        "claim_boundary": [
            "more tasks improve cross-task coverage but do not establish statistical significance without independent repetitions",
            "this matched canary tests Evolver behavior and one-pass harness direction, not multi-round evolution gain",
            "free versus constrained probe remains a separate ablation",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--a5-manifest", type=Path, required=True)
    parser.add_argument("--seed-run", type=Path, required=True)
    parser.add_argument("--seed-arm", default="seed-evidence")
    parser.add_argument(
        "--proposal", action="append", type=_label_path, required=True
    )
    parser.add_argument("--candidate-run", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    proposal_runs = dict(args.proposal)
    if len(proposal_runs) != len(args.proposal):
        raise ValueError("proposal labels must be unique")
    report = audit(
        manifest=_json(args.a5_manifest.resolve()),
        seed_run=args.seed_run.resolve(),
        seed_arm=args.seed_arm,
        proposal_runs=proposal_runs,
        candidate_run=(args.candidate_run.resolve() if args.candidate_run else None),
    )
    _atomic_json(args.output.expanduser().resolve(), report)
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
