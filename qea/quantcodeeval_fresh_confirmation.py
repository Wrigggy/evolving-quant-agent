"""Fresh, answer-blind T26 confirmation for a retained quant harness."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from .candidate_admission import AdmissionPolicy, admit_candidate
from .quantcodeeval_ap2m import _write_result
from .quantcodeeval_repair_probe import run_probe_arm


class QuantCodeEvalFreshConfirmationError(ValueError):
    """The retained candidate or fresh confirmation setup is incomplete."""


def _json_object(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise QuantCodeEvalFreshConfirmationError(
            f"cannot read {label}: {path}"
        ) from exc
    if not isinstance(value, dict):
        raise QuantCodeEvalFreshConfirmationError(f"{label} must be an object")
    return value


def _number(value: object) -> float:
    if isinstance(value, bool):
        return 0.0
    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    return parsed if parsed >= 0 else 0.0


def run_quantcodeeval_fresh_confirmation(
    *,
    config_path: str | Path,
    release_dir: str | Path,
    source_run_dir: str | Path,
    run_dir: str | Path,
    worker_image_ref: str,
    verifier_image_ref: str,
    proxy_image_ref: str,
    task_panel_path: str | Path,
    task_id: str = "T26",
    component_tool: str = "check_quant_relations",
    max_iterations: int = 60,
    initial_construction_turns: int = 24,
    min_post_observation_turns: int = 3,
) -> dict[str, object]:
    """Run one no-seed Worker from the public task under the retained harness."""

    if type(max_iterations) is not int or not 12 <= max_iterations <= 60:
        raise QuantCodeEvalFreshConfirmationError(
            "max_iterations must be in [12, 60]"
        )
    if (
        type(initial_construction_turns) is not int
        or not 2 <= initial_construction_turns < max_iterations - 3
    ):
        raise QuantCodeEvalFreshConfirmationError(
            "initial construction turns leave no audit-and-repair budget"
        )
    source = Path(source_run_dir).expanduser().resolve()
    root = Path(run_dir).expanduser().resolve()
    release = Path(release_dir).expanduser().resolve()
    if root.exists():
        raise QuantCodeEvalFreshConfirmationError(
            "fresh confirmation run directory already exists"
        )
    candidate = source / "evolver/evolutions/iteration-0001/candidate"
    prior = _json_object(source / "COMPONENT-IMPACT-RESULT.json", "source result")
    evolution = _json_object(source / "evolver/LIVE-RESULT.json", "source evolution")
    decision = evolution.get("decision")
    if not isinstance(decision, Mapping) or decision.get("decision") != "ACT":
        raise QuantCodeEvalFreshConfirmationError("source run lacks an Evolver ACT")
    if not candidate.is_dir():
        raise QuantCodeEvalFreshConfirmationError("retained candidate is missing")
    admit_candidate(
        release / "h0/workers/H0", candidate, AdmissionPolicy.qfbench_full()
    )
    baseline_passed = prior.get("baseline_tests_passed")
    if type(baseline_passed) is not int:
        raise QuantCodeEvalFreshConfirmationError(
            "source result lacks a property baseline"
        )
    baseline_reward = _number(prior.get("baseline_reward"))
    instruction = (
        "Fresh confirmation run: start only from the public task and data; no "
        "strategy implementation is pre-staged. Produce /app/output/strategy.py "
        "from scratch. Progress from a bounded contract/data inventory to a "
        "parsable first draft before the declared-relations checkpoint. At the "
        "checkpoint, decide whether check_quant_relations applies to the current "
        "draft, author its relation declarations from the public instruction, "
        "and call it when applicable. Use supported findings to revise the "
        "artifact, run focused public-data smokes, re-audit, and deliver the best "
        "runnable strategy.py. Do not inspect checker, reference, property, "
        "verdict, expected-value, or credential files, and do not add "
        "task-ID branches or copied expected values."
    )
    fresh = run_probe_arm(
        label="qdr1-fresh-t26-confirmation-v1",
        config_path=config_path,
        public_root=release / "public",
        trusted_root=release / "trusted",
        run_dir=root / "fresh-worker",
        worker_dir=candidate,
        seed_strategy=None,
        worker_instruction=instruction,
        worker_image_ref=worker_image_ref,
        verifier_image_ref=verifier_image_ref,
        proxy_image_ref=proxy_image_ref,
        task_panel_path=task_panel_path,
        task_id=task_id,
        max_iterations=max_iterations,
        component_tool=component_tool,
        inventory_turns=initial_construction_turns,
        min_post_observation_turns=min_post_observation_turns,
    )
    score = fresh.get("score")
    if not isinstance(score, Mapping):
        raise QuantCodeEvalFreshConfirmationError(
            "fresh Worker lacks an official score record"
        )
    artifact = Path(str(fresh.get("artifact", ""))).expanduser().resolve()
    artifact_exists = artifact.is_file()
    passed_value = score.get("tests_passed")
    passed = int(passed_value) if type(passed_value) is int else 0
    reward = _number(score.get("reward"))
    usage = fresh.get("tool_usage")
    counts = usage.get("counts") if isinstance(usage, Mapping) else {}
    first_turns = (
        usage.get("first_assistant_turn") if isinstance(usage, Mapping) else {}
    )
    calls = int(counts.get(component_tool, 0)) if isinstance(counts, Mapping) else 0
    first_turn = (
        first_turns.get(component_tool) if isinstance(first_turns, Mapping) else None
    )
    if not artifact_exists:
        status = "missing_artifact"
    elif reward > baseline_reward:
        status = "binary_gain"
    elif passed > baseline_passed:
        status = "property_gain"
    elif passed == baseline_passed:
        status = "tied"
    else:
        status = "regressed"
    worker_summary = fresh.get("worker_summary")
    result = {
        "schema_version": 1,
        "protocol": "quantcodeeval-fresh-harness-confirmation-v1",
        "status": status,
        "task_id": task_id,
        "source_run": source.name,
        "seed_strategy_present": False,
        "max_iterations": max_iterations,
        "completed_requests": (
            worker_summary.get("turns")
            if isinstance(worker_summary, Mapping)
            else None
        ),
        "initial_construction_turns": initial_construction_turns,
        "min_post_observation_turns": min_post_observation_turns,
        "component_tool": component_tool,
        "component_calls": calls,
        "first_component_call_assistant_turn": first_turn,
        "component_reaudit_observed": calls >= 2,
        "artifact_delivered": artifact_exists,
        "baseline_tests_passed": baseline_passed,
        "fresh_tests_passed": passed,
        "property_delta": passed - baseline_passed,
        "baseline_reward": baseline_reward,
        "fresh_reward": reward,
        "fresh": fresh,
        "cost_usd": _number(
            fresh.get("cost", {}).get("provider_cost_usd")
            if isinstance(fresh.get("cost"), Mapping)
            else None
        ),
        "claim_boundary": (
            "single fresh answer-blind T26 Worker under a retained harness; "
            "not an independent repeat, transfer, sealed evaluation, or "
            "end-to-end H0 Evolver search"
        ),
    }
    root.mkdir(parents=True, exist_ok=True)
    _write_result(root / "FRESH-CONFIRMATION-RESULT.json", result)
    return result


__all__ = [
    "QuantCodeEvalFreshConfirmationError",
    "run_quantcodeeval_fresh_confirmation",
]
