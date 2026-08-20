"""One Evolver-directed component-impact experiment and official outcome."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping, Sequence

from .quantcodeeval_ap2m import _cost, _write_result
from .quantcodeeval_ap3 import require_ap3_run_local_probe
from .quantcodeeval_repair_probe import run_probe_arm
from .quantcodeeval_v2_live import run_quantcodeeval_v2_activation_canary


class QuantCodeEvalComponentImpactError(ValueError):
    """The component-impact experiment is incomplete or inconsistent."""


def _json_object(path: str | Path, *, label: str) -> dict[str, object]:
    source = Path(path).expanduser().resolve()
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise QuantCodeEvalComponentImpactError(f"cannot read {label}: {source}") from exc
    if not isinstance(value, dict):
        raise QuantCodeEvalComponentImpactError(f"{label} must contain a JSON object")
    return value


def _tests_passed(result: Mapping[str, object], *, label: str) -> int:
    score = result.get("score")
    value = score.get("tests_passed") if isinstance(score, Mapping) else None
    if type(value) is not int or value < 0:
        raise QuantCodeEvalComponentImpactError(f"{label} lacks tests_passed")
    return value


def _reward(result: Mapping[str, object]) -> float:
    score = result.get("score")
    value = score.get("reward") if isinstance(score, Mapping) else None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    return float(value)


def _artifact_changed(seed: Path, probe: Mapping[str, object]) -> bool:
    raw = probe.get("artifact")
    if not isinstance(raw, str):
        raise QuantCodeEvalComponentImpactError("probe did not record its artifact")
    artifact = Path(raw).expanduser().resolve()
    if not artifact.is_file():
        raise QuantCodeEvalComponentImpactError("probe artifact is missing")
    return seed.read_bytes() != artifact.read_bytes()


def _non_shell_calls(probe: Mapping[str, object]) -> dict[str, int]:
    usage = probe.get("tool_usage")
    counts = usage.get("counts") if isinstance(usage, Mapping) else None
    if not isinstance(counts, Mapping):
        return {}
    return {
        str(name): int(count)
        for name, count in counts.items()
        if name != "run_shell_command" and type(count) is int and count > 0
    }


def run_quantcodeeval_component_impact(
    *,
    config_path: str | Path,
    release_dir: str | Path,
    run_dir: str | Path,
    component_source: str | Path,
    seed_strategy: str | Path,
    prior_evolution_result_path: str | Path,
    prior_probe_result_paths: Sequence[str | Path],
    evolver_image_ref: str,
    worker_image_ref: str,
    verifier_image_ref: str,
    proxy_image_ref: str,
    task_panel_path: str | Path,
    task_id: str = "T26",
    preflight_only: bool = False,
) -> dict[str, object]:
    """Let the Evolver design one directed test of a candidate component."""

    root = Path(run_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    release = Path(release_dir).expanduser().resolve()
    component = Path(component_source).expanduser().resolve()
    seed = Path(seed_strategy).expanduser().resolve()
    if not component.is_dir() or not seed.is_file():
        raise QuantCodeEvalComponentImpactError("component source or seed is missing")
    prior_paths = tuple(Path(path).expanduser().resolve() for path in prior_probe_result_paths)
    if len(prior_paths) < 2 or any(not path.is_file() for path in prior_paths):
        raise QuantCodeEvalComponentImpactError("two prior probe results are required")
    prior_results = [
        _json_object(path, label=f"prior probe {index}")
        for index, path in enumerate(prior_paths, start=1)
    ]
    baseline_passed = _tests_passed(prior_results[0], label="baseline probe")
    baseline_reward = _reward(prior_results[0])
    for result in prior_results[1:]:
        if _tests_passed(result, label="prior probe") != baseline_passed:
            raise QuantCodeEvalComponentImpactError("prior probe baselines disagree")
    prior_evolution = Path(prior_evolution_result_path).expanduser().resolve()
    if not prior_evolution.is_file():
        raise QuantCodeEvalComponentImpactError("prior evolution result is missing")

    observations = {"prior_component_design": prior_evolution}
    observations.update(
        {
            f"zero_activation_probe_{index}": path
            for index, path in enumerate(prior_paths, start=1)
        }
    )
    evolution = run_quantcodeeval_v2_activation_canary(
        config_path=config_path,
        release_dir=release,
        run_dir=root / "evolver",
        evolver_image_ref=evolver_image_ref,
        proxy_image_ref=proxy_image_ref,
        component_sources={"current_quant_component": component},
        worker_artifact_sources={"run_local_h0": seed},
        experiment_observation_sources=observations,
        autonomous_probe_required=True,
        task_ids=(task_id,),
        diagnosis_note=(
            "Evolver-directed component-impact follow-up. The current quant component "
            "passed its local discriminating smoke, but two blind seeded Workers with "
            "different iteration caps made zero component calls, left the artifact "
            "unchanged, and retained the same official result. Compare at least "
            "activation timing and call complexity as explanations. If ACT, design one "
            "coherent harness revision and a directed repair experiment over "
            "seed_experience=run_local_h0. The Worker instruction must explicitly frame "
            "the run as a component-impact experiment rather than a full research "
            "reconnaissance: after a bounded public-contract and artifact inventory, "
            "decide applicability, invoke the component early when applicable, revise "
            "the artifact from its observation, re-check, and save the final artifact. "
            "Use 6-10 Worker iterations. Predict the first component call, the next "
            "Worker action, and the official artifact outcome. The Worker remains "
            "answer-blind; do not encode checker answers, expected values, task-only "
            "constants, or a fixed relation payload. An evidence-grounded ABSTAIN is "
            "valid if the retained observations do not support a bounded intervention."
        ),
        validate_release=False,
        preflight_only=preflight_only,
    )
    if preflight_only:
        result = {
            "schema_version": 1,
            "protocol": "quantcodeeval-component-impact-v1",
            "status": "preflight_complete",
            "baseline_tests_passed": baseline_passed,
            "evolution": evolution,
        }
        _write_result(root / "COMPONENT-IMPACT-PREFLIGHT.json", result)
        return result

    evolver_cost = _cost(
        evolution.get("proxy_audit")
        if isinstance(evolution.get("proxy_audit"), Mapping)
        else None
    )
    if evolution.get("status") != "PASS":
        status = (
            "calibrated_abstain"
            if evolution.get("status") == "CALIBRATED_ABSTAIN"
            else "evolver_not_admitted"
        )
        result = {
            "schema_version": 1,
            "protocol": "quantcodeeval-component-impact-v1",
            "status": status,
            "worker_probe_run": False,
            "baseline_tests_passed": baseline_passed,
            "evolution": evolution,
            "cost_usd": evolver_cost,
        }
        _write_result(root / "COMPONENT-IMPACT-RESULT.json", result)
        return result

    decision = evolution.get("decision")
    if not isinstance(decision, Mapping):
        raise QuantCodeEvalComponentImpactError("admitted evolution lacks a decision")
    spec = require_ap3_run_local_probe(decision)
    candidate = root / "evolver/evolutions/iteration-0001/candidate"
    probe = run_probe_arm(
        label="evolver-directed-component-impact",
        config_path=config_path,
        public_root=release / "public",
        trusted_root=release / "trusted",
        run_dir=root / "worker-probe",
        worker_dir=candidate,
        seed_strategy=seed,
        worker_instruction=spec.worker_instruction,
        worker_image_ref=worker_image_ref,
        verifier_image_ref=verifier_image_ref,
        proxy_image_ref=proxy_image_ref,
        task_panel_path=task_panel_path,
        task_id=task_id,
        max_iterations=spec.max_iterations,
    )
    passed = _tests_passed(probe, label="component-impact probe")
    reward = _reward(probe)
    changed = _artifact_changed(seed, probe)
    component_calls = _non_shell_calls(probe)
    if reward > baseline_reward:
        status = "binary_gain"
    elif passed > baseline_passed:
        status = "property_gain"
    elif changed:
        status = "artifact_changed_no_score_gain"
    elif component_calls:
        status = "component_called_no_artifact_change"
    else:
        status = "component_not_called"
    result = {
        "schema_version": 1,
        "protocol": "quantcodeeval-component-impact-v1",
        "status": status,
        "worker_probe_run": True,
        "component_calls": component_calls,
        "component_called": bool(component_calls),
        "artifact_changed": changed,
        "baseline_tests_passed": baseline_passed,
        "candidate_tests_passed": passed,
        "property_delta": passed - baseline_passed,
        "baseline_reward": baseline_reward,
        "candidate_reward": reward,
        "experiment_spec": spec.__dict__,
        "evolution": evolution,
        "probe": probe,
        "cost_usd": evolver_cost
        + _cost(probe.get("cost") if isinstance(probe.get("cost"), Mapping) else None),
        "claim_boundary": (
            "Evolver-directed seeded component-impact experiment; not a fresh "
            "from-public-task Worker or sealed benchmark result"
        ),
    }
    _write_result(root / "COMPONENT-IMPACT-RESULT.json", result)
    return result


__all__ = [
    "QuantCodeEvalComponentImpactError",
    "run_quantcodeeval_component_impact",
]
