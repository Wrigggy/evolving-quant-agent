"""Phase-aware bounded causal probe for one retained QuantCodeEval component."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from .candidate_admission import AdmissionPolicy, admit_candidate
from .quantcodeeval_ap2m import _write_result
from .quantcodeeval_ap3 import require_ap3_run_local_probe
from .quantcodeeval_repair_probe import run_probe_arm


class QuantCodeEvalCausalProbeError(ValueError):
    """The retained candidate or causal-probe setup is incomplete."""


def _json_object(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise QuantCodeEvalCausalProbeError(f"cannot read {label}: {path}") from exc
    if not isinstance(value, dict):
        raise QuantCodeEvalCausalProbeError(f"{label} must be an object")
    return value


def _number(value: object) -> float:
    if isinstance(value, bool):
        return 0.0
    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    return parsed if parsed >= 0 else 0.0


def run_quantcodeeval_causal_probe(
    *,
    config_path: str | Path,
    release_dir: str | Path,
    source_run_dir: str | Path,
    run_dir: str | Path,
    seed_strategy: str | Path,
    worker_image_ref: str,
    verifier_image_ref: str,
    proxy_image_ref: str,
    task_panel_path: str | Path,
    task_id: str = "T26",
    component_tool: str = "check_quant_relations",
    completed_request_budget: int = 12,
    inventory_turns: int = 2,
    min_post_observation_turns: int = 3,
) -> dict[str, object]:
    """Run one seeded probe with a fixed inventory and post-observation envelope."""

    if type(completed_request_budget) is not int or not 6 <= completed_request_budget <= 20:
        raise QuantCodeEvalCausalProbeError("completed request budget must be in [6, 20]")
    source = Path(source_run_dir).expanduser().resolve()
    root = Path(run_dir).expanduser().resolve()
    if root.exists():
        raise QuantCodeEvalCausalProbeError("causal probe run directory already exists")
    release = Path(release_dir).expanduser().resolve()
    seed = Path(seed_strategy).expanduser().resolve()
    candidate = source / "evolver/evolutions/iteration-0001/candidate"
    prior = _json_object(source / "COMPONENT-IMPACT-RESULT.json", "source result")
    evolution = _json_object(source / "evolver/LIVE-RESULT.json", "source evolution")
    decision = evolution.get("decision")
    if not isinstance(decision, Mapping) or decision.get("decision") != "ACT":
        raise QuantCodeEvalCausalProbeError("source run lacks an Evolver ACT")
    spec = require_ap3_run_local_probe(decision)
    if not seed.is_file() or not candidate.is_dir():
        raise QuantCodeEvalCausalProbeError("seed or retained candidate is missing")
    admit_candidate(
        release / "h0/workers/H0", candidate, AdmissionPolicy.qfbench_full()
    )
    baseline_passed = prior.get("baseline_tests_passed")
    if type(baseline_passed) is not int:
        raise QuantCodeEvalCausalProbeError("source result lacks a property baseline")
    baseline_reward = _number(prior.get("baseline_reward"))
    instruction = (
        spec.worker_instruction.rstrip()
        + "\n\nBounded causal-probe envelope: use only the first two assistant "
        "turns for public-contract and artifact inventory. At the phase checkpoint, "
        "call the applicable candidate component or state an evidence-grounded "
        "SKIP. After an actionable observation, prioritize edit, focused smoke, "
        "re-audit, and final artifact delivery over any broad research."
    )
    configured_max_iterations = completed_request_budget + 1
    probe = run_probe_arm(
        label="qdr1-bounded-causal-probe-v2",
        config_path=config_path,
        public_root=release / "public",
        trusted_root=release / "trusted",
        run_dir=root / "worker-probe",
        worker_dir=candidate,
        seed_strategy=seed,
        worker_instruction=instruction,
        worker_image_ref=worker_image_ref,
        verifier_image_ref=verifier_image_ref,
        proxy_image_ref=proxy_image_ref,
        task_panel_path=task_panel_path,
        task_id=task_id,
        max_iterations=configured_max_iterations,
        component_tool=component_tool,
        inventory_turns=inventory_turns,
        min_post_observation_turns=min_post_observation_turns,
    )
    score = probe.get("score")
    if not isinstance(score, Mapping) or type(score.get("tests_passed")) is not int:
        raise QuantCodeEvalCausalProbeError("probe lacks an official property score")
    artifact_value = probe.get("artifact")
    artifact = Path(str(artifact_value)).expanduser().resolve()
    if not artifact.is_file():
        raise QuantCodeEvalCausalProbeError("probe artifact is missing")
    usage = probe.get("tool_usage")
    counts = usage.get("counts") if isinstance(usage, Mapping) else {}
    first_turns = usage.get("first_assistant_turn") if isinstance(usage, Mapping) else {}
    calls = int(counts.get(component_tool, 0)) if isinstance(counts, Mapping) else 0
    first_turn = (
        first_turns.get(component_tool) if isinstance(first_turns, Mapping) else None
    )
    observations = probe.get("component_observations")
    rows = observations.get("observations") if isinstance(observations, Mapping) else []
    first_observation = rows[0] if isinstance(rows, list) and rows else {}
    summary = (
        first_observation.get("summary")
        if isinstance(first_observation, Mapping)
        else None
    )
    actionable_errors = (
        int(summary.get("errors", 0))
        if isinstance(summary, Mapping) and type(summary.get("errors", 0)) is int
        else 0
    )
    passed = int(score["tests_passed"])
    reward = _number(score.get("reward"))
    changed = seed.read_bytes() != artifact.read_bytes()
    if reward > baseline_reward:
        status = "binary_gain"
    elif passed > baseline_passed:
        status = "property_gain"
    elif calls == 0:
        status = "not_activated"
    elif actionable_errors == 0:
        status = "activated_no_actionable_finding"
    elif not changed:
        status = "actionable_finding_no_edit"
    elif calls < 2:
        status = "artifact_changed_no_reaudit"
    else:
        status = "artifact_changed_no_property_gain"
    worker_summary = probe.get("worker_summary")
    completed_requests = (
        worker_summary.get("turns") if isinstance(worker_summary, Mapping) else None
    )
    result = {
        "schema_version": 1,
        "protocol": "quantcodeeval-bounded-causal-probe-v2",
        "status": status,
        "task_id": task_id,
        "source_run": source.name,
        "completed_request_budget": completed_request_budget,
        "configured_max_iterations": configured_max_iterations,
        "completed_requests": completed_requests,
        "inventory_turns": inventory_turns,
        "min_post_observation_turns": min_post_observation_turns,
        "component_tool": component_tool,
        "component_calls": calls,
        "first_component_call_assistant_turn": first_turn,
        "actionable_errors": actionable_errors,
        "re_audit_observed": calls >= 2,
        "artifact_changed": changed,
        "baseline_tests_passed": baseline_passed,
        "candidate_tests_passed": passed,
        "property_delta": passed - baseline_passed,
        "baseline_reward": baseline_reward,
        "candidate_reward": reward,
        "probe": probe,
        "cost_usd": _number(
            probe.get("cost", {}).get("provider_cost_usd")
            if isinstance(probe.get("cost"), Mapping)
            else None
        ),
        "claim_boundary": (
            "phase-aware seeded causal probe; not a fresh Worker or sealed "
            "benchmark result"
        ),
    }
    root.mkdir(parents=True, exist_ok=True)
    _write_result(root / "CAUSAL-PROBE-RESULT.json", result)
    return result


__all__ = ["QuantCodeEvalCausalProbeError", "run_quantcodeeval_causal_probe"]
