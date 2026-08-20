"""One-round quant diagnostic refinement followed by one blind Worker probe."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from .quantcodeeval_ap2m import _write_result
from .quantcodeeval_ap3 import require_ap3_run_local_probe
from .quantcodeeval_repair_probe import run_probe_arm
from .quantcodeeval_v2_live import run_quantcodeeval_v2_activation_canary


class QuantDiagnosticRefinementError(ValueError):
    """The diagnostic-refinement canary setup or decision is incomplete."""


def _cost(value: Mapping[str, object] | None) -> float:
    if not isinstance(value, Mapping):
        return 0.0
    raw = value.get("provider_cost_usd")
    if isinstance(raw, bool):
        return 0.0
    try:
        parsed = float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    return parsed if parsed >= 0 else 0.0


def _json_object(path: str | Path, *, label: str) -> dict[str, object]:
    source = Path(path).expanduser().resolve()
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise QuantDiagnosticRefinementError(f"cannot read {label}: {source}") from exc
    if not isinstance(value, dict):
        raise QuantDiagnosticRefinementError(f"{label} must contain a JSON object")
    return value


def _tests_passed(result: Mapping[str, object], *, label: str) -> int:
    score = result.get("score")
    value = score.get("tests_passed") if isinstance(score, Mapping) else None
    if type(value) is not int or value < 0:
        raise QuantDiagnosticRefinementError(f"{label} lacks tests_passed")
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
        raise QuantDiagnosticRefinementError("Worker probe did not record its artifact")
    artifact = Path(raw).expanduser().resolve()
    if not artifact.is_file():
        raise QuantDiagnosticRefinementError("Worker probe artifact is missing")
    return seed.read_bytes() != artifact.read_bytes()


def run_quantcodeeval_diagnostic_refinement(
    *,
    config_path: str | Path,
    release_dir: str | Path,
    run_dir: str | Path,
    component_source: str | Path,
    seed_strategy: str | Path,
    prior_probe_result_path: str | Path,
    optimization_diagnostic_path: str | Path,
    evolver_image_ref: str,
    worker_image_ref: str,
    verifier_image_ref: str,
    proxy_image_ref: str,
    task_panel_path: str | Path,
    task_id: str = "T26",
    preflight_only: bool = False,
) -> dict[str, object]:
    """Test whether an Evolver can refine a weak quant diagnostic from evidence."""

    root = Path(run_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    component = Path(component_source).expanduser().resolve()
    seed = Path(seed_strategy).expanduser().resolve()
    if not component.is_dir() or not seed.is_file():
        raise QuantDiagnosticRefinementError("component source or seed strategy is missing")
    prior_probe_path = Path(prior_probe_result_path).expanduser().resolve()
    prior_probe = _json_object(prior_probe_path, label="prior probe result")
    baseline_passed = _tests_passed(prior_probe, label="prior probe result")

    evolution = run_quantcodeeval_v2_activation_canary(
        config_path=config_path,
        release_dir=release_dir,
        run_dir=root / "evolver",
        evolver_image_ref=evolver_image_ref,
        proxy_image_ref=proxy_image_ref,
        component_sources={"current_quant_diagnostic": component},
        worker_artifact_sources={"run_local_h0": seed},
        experiment_observation_sources={"prior_blind_probe": prior_probe_path},
        optimization_diagnostic_path=optimization_diagnostic_path,
        autonomous_probe_required=True,
        task_ids=(task_id,),
        diagnosis_note=(
            "Diagnostic-refinement canary. The current executable quant diagnostic "
            "activated in the prior blind Worker run but did not localize the official "
            "mismatches and the Worker left the seed artifact unchanged. Read the "
            "Evolver-only optimization diagnostic and prior blind probe. Compare at "
            "least two causal explanations, then REFINE, REPLACE, COMPOSE, or ABSTAIN. "
            "If ACT, implement one reusable quantitative consistency relation: for "
            "example an information-time, estimator-geometry, residual, or artifact-"
            "observability relation. Its final component smoke must discriminate a "
            "correct synthetic fixture from the same fixture with one controlled "
            "perturbation. Do not encode task IDs, expected values, or fixed task-only "
            "assertions. Author a repair experiment over seed_experience=run_local_h0 "
            "with 4-8 Worker iterations."
        ),
        validate_release=False,
        preflight_only=preflight_only,
    )
    if preflight_only:
        result = {
            "schema_version": 1,
            "protocol": "quantcodeeval-diagnostic-refinement-v1",
            "status": "preflight_complete",
            "baseline_tests_passed": baseline_passed,
            "evolution": evolution,
        }
        _write_result(root / "QDR-PREFLIGHT.json", result)
        return result

    if evolution.get("status") != "PASS":
        status = (
            "calibrated_abstain"
            if evolution.get("status") == "CALIBRATED_ABSTAIN"
            else "evolver_not_admitted"
        )
        result = {
            "schema_version": 1,
            "protocol": "quantcodeeval-diagnostic-refinement-v1",
            "status": status,
            "evolver_admitted": False,
            "worker_probe_run": False,
            "baseline_tests_passed": baseline_passed,
            "evolution": evolution,
            "cost_usd": _cost(
                evolution.get("proxy_audit")
                if isinstance(evolution.get("proxy_audit"), Mapping)
                else None
            ),
        }
        _write_result(root / "QDR-RESULT.json", result)
        return result

    decision = evolution.get("decision")
    if not isinstance(decision, Mapping):
        raise QuantDiagnosticRefinementError("admitted evolution lacks a decision")
    spec = require_ap3_run_local_probe(decision)
    candidate = root / "evolver/evolutions/iteration-0001/candidate"
    probe = run_probe_arm(
        label="quant-diagnostic-refinement",
        config_path=config_path,
        public_root=Path(release_dir).expanduser().resolve() / "public",
        trusted_root=Path(release_dir).expanduser().resolve() / "trusted",
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
    passed = _tests_passed(probe, label="refinement probe result")
    reward = _reward(probe)
    changed = _artifact_changed(seed, probe)
    if reward > _reward(prior_probe):
        status = "binary_gain"
    elif passed > baseline_passed:
        status = "property_gain"
    elif changed:
        status = "artifact_changed_no_score_gain"
    else:
        status = "component_refined_no_artifact_change"
    result = {
        "schema_version": 1,
        "protocol": "quantcodeeval-diagnostic-refinement-v1",
        "status": status,
        "evolver_admitted": True,
        "worker_probe_run": True,
        "artifact_changed": changed,
        "baseline_tests_passed": baseline_passed,
        "candidate_tests_passed": passed,
        "property_delta": passed - baseline_passed,
        "baseline_reward": _reward(prior_probe),
        "candidate_reward": reward,
        "experiment_spec": spec.__dict__,
        "evolution": evolution,
        "probe": probe,
        "cost_usd": _cost(
            evolution.get("proxy_audit")
            if isinstance(evolution.get("proxy_audit"), Mapping)
            else None
        )
        + _cost(probe.get("cost") if isinstance(probe.get("cost"), Mapping) else None),
        "claim_boundary": (
            "one answer-rich Evolver refinement and one blind seeded Worker probe; "
            "not a fresh-H0 or held-out benchmark result"
        ),
    }
    _write_result(root / "QDR-RESULT.json", result)
    return result


__all__ = [
    "QuantDiagnosticRefinementError",
    "run_quantcodeeval_diagnostic_refinement",
]
