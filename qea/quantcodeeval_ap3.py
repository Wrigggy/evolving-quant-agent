"""Minimum autonomous Quant-H0 bootstrap canary for QuantCodeEval."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Mapping

from .quantcodeeval_ap2m import (
    AP2MExperimentSpec,
    QuantCodeEvalAP2MError,
    _cost,
    _selected_mechanism,
    _write_result,
)
from .quantcodeeval_baseline import prepare_quantcodeeval_h0, run_quantcodeeval_h0
from .quantcodeeval_full_candidate import run_quantcodeeval_full_candidate
from .quantcodeeval_repair_probe import run_probe_arm
from .quantcodeeval_v2_live import run_quantcodeeval_v2_activation_canary


class QuantCodeEvalAP3Error(ValueError):
    """The AP-3 bootstrap setup or autonomous decision is incomplete."""


_RUN_LOCAL_H0_SEED = "run_local_h0"


def require_ap3_run_local_probe(
    decision: Mapping[str, object],
) -> AP2MExperimentSpec:
    """Require a short activation probe over this AP-3 run's H0 artifact."""

    try:
        spec = AP2MExperimentSpec.from_decision(decision)
    except QuantCodeEvalAP2MError as exc:
        raise QuantCodeEvalAP3Error(str(exc)) from exc
    if spec.mode != "repair" or spec.seed_experience != _RUN_LOCAL_H0_SEED:
        raise QuantCodeEvalAP3Error(
            "AP-3 activation probe must repair the run-local H0 artifact"
        )
    return spec


def find_ap3_run_local_h0_artifact(
    h0_root: str | Path, h0_result: Mapping[str, object]
) -> Path:
    """Locate the T26 artifact produced by this AP-3 run's fresh H0 Worker."""

    attempts = h0_result.get("attempts")
    if not isinstance(attempts, list):
        raise QuantCodeEvalAP3Error("AP-3 H0 result lacks attempt records")
    root = Path(h0_root).expanduser().resolve()
    for attempt in attempts:
        if not isinstance(attempt, Mapping) or attempt.get("task_id") != "T26":
            continue
        attempt_id = attempt.get("attempt_id")
        if not isinstance(attempt_id, str) or not attempt_id:
            continue
        artifact = root / "attempts" / attempt_id / "artifacts" / "strategy.py"
        if artifact.is_file():
            return artifact
    raise QuantCodeEvalAP3Error("AP-3 fresh H0 Worker produced no T26 artifact")


def ap3_round_one_prediction_record(
    decision: Mapping[str, object], spec: AP2MExperimentSpec
) -> dict[str, object]:
    """Persist the round-one prediction beside its later probe observation."""

    return {
        "schema_version": 1,
        "protocol": "quantcodeeval-ap3-round-one-prediction-v1",
        "selected_hypothesis_id": decision.get("selected_hypothesis_id"),
        "research_state_transition": decision.get("research_state_transition"),
        "prediction": spec.prediction,
        "decision_changing_observation": spec.decision_changing_observation,
    }


def _copy_public_evaluator_surface(source: Path, target: Path) -> None:
    if target.exists():
        raise QuantCodeEvalAP3Error("AP-3 engineering release already exists")
    target.mkdir(parents=True)
    for name in ("public", "trusted"):
        value = source / name
        if not value.is_dir():
            raise QuantCodeEvalAP3Error(f"AP-3 source release lacks {name}")
        shutil.copytree(value, target / name)


def _proxy_cost(result: Mapping[str, object]) -> float:
    return _cost(
        result.get("proxy_cost")
        if isinstance(result.get("proxy_cost"), Mapping)
        else result.get("proxy_audit")
        if isinstance(result.get("proxy_audit"), Mapping)
        else result.get("cost_audit")
        if isinstance(result.get("cost_audit"), Mapping)
        else None
    )


def run_quantcodeeval_ap3(
    *,
    config_path: str | Path,
    source_release_dir: str | Path,
    quant_h0_worker_dir: str | Path,
    run_dir: str | Path,
    evolver_image_ref: str,
    worker_image_ref: str,
    verifier_image_ref: str,
    proxy_image_ref: str,
    task_panel_path: str | Path,
    cost_cap_usd: float = 0.80,
    final_cost_reserve_usd: float = 0.12,
    preflight_only: bool = False,
) -> dict[str, object]:
    """Run H0 evidence, a seeded activation probe, two decisions, and one final."""

    if cost_cap_usd <= 0 or not 0 <= final_cost_reserve_usd < cost_cap_usd:
        raise QuantCodeEvalAP3Error("AP-3 cost cap is invalid")
    root = Path(run_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    source_release = Path(source_release_dir).expanduser().resolve()
    quant_h0 = Path(quant_h0_worker_dir).expanduser().resolve()
    if not quant_h0.is_dir():
        raise QuantCodeEvalAP3Error("Quant-H0 worker directory is missing")

    release = root / "engineering-release"
    _copy_public_evaluator_surface(source_release, release)
    h0_root = release / "h0"
    snapshot, evaluator, h0_plan, frozen_worker = prepare_quantcodeeval_h0(
        config_path=config_path,
        public_root=release / "public",
        trusted_root=release / "trusted",
        run_dir=h0_root,
        worker_dir=quant_h0,
        worker_image_ref=worker_image_ref,
        verifier_image_ref=verifier_image_ref,
        proxy_image_ref=proxy_image_ref,
        task_panel_path=task_panel_path,
        task_ids=("T26",),
    )
    if preflight_only:
        result = {
            "schema_version": 1,
            "protocol": "quantcodeeval-ap3-v2",
            "status": "preflight_complete",
            "h0_preflight": h0_plan,
            "certificate_path": "generic_research_state_evidence",
        }
        _write_result(root / "AP3-PREFLIGHT.json", result)
        return result

    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    h0 = run_quantcodeeval_h0(
        snapshot=snapshot,
        evaluator=evaluator,
        plan=h0_plan,
        frozen_worker=frozen_worker,
        run_dir=h0_root,
        token_file=config["token_file"],
    )
    spent = _proxy_cost(h0)
    h0_artifact = find_ap3_run_local_h0_artifact(h0_root, h0)

    round_one = run_quantcodeeval_v2_activation_canary(
        config_path=config_path,
        release_dir=release,
        run_dir=root / "round-1",
        evolver_image_ref=evolver_image_ref,
        proxy_image_ref=proxy_image_ref,
        worker_artifact_sources={_RUN_LOCAL_H0_SEED: h0_artifact},
        task_ids=("T26",),
        diagnosis_note=(
            "AP-3 round one. Start only from this run's fresh Quant-H0 T26 "
            "attempt. Choose one reusable full-harness intervention and one "
            "short activation/repair experiment that can discriminate the "
            "selected mechanism from a competitor. The only permitted seed is "
            "this run's fresh H0 artifact at guidance/worker_artifacts/"
            "run_local_h0.py. The experiment_spec must use mode=repair and "
            "seed_experience=run_local_h0. Prefer 4-8 Worker iterations and never "
            "exceed the external 12-iteration cap. Do not use or request any "
            "historical artifact, component, task-specific answer, or historical "
            "repair instruction. Use generic Research-State evidence; QEC-1 did "
            "not justify adding certificate guidance to this run."
        ),
        validate_release=False,
        autonomous_probe_required=True,
        preflight_only=False,
    )
    spent += _cost(
        round_one.get("proxy_audit")
        if isinstance(round_one.get("proxy_audit"), Mapping)
        else None
    )
    if round_one.get("status") != "PASS":
        result = {
            "schema_version": 1,
            "protocol": "quantcodeeval-ap3-v2",
            "status": "round_one_terminal",
            "bootstrap_loop_feasible": False,
            "certificate_path": "generic_research_state_evidence",
            "h0": h0,
            "round_one": round_one,
            "cost_usd": spent,
        }
        _write_result(root / "AP3-RESULT.json", result)
        return result
    decision_one = round_one.get("decision")
    if not isinstance(decision_one, Mapping):
        raise QuantCodeEvalAP3Error("AP-3 round one lacks a decision")
    spec = require_ap3_run_local_probe(decision_one)
    round_one_prediction = ap3_round_one_prediction_record(decision_one, spec)
    _write_result(root / "round-one-prediction.json", round_one_prediction)
    candidate_one = root / "round-1/evolutions/iteration-0001/candidate"
    probe = run_probe_arm(
        label="ap3-evolver-selected",
        config_path=config_path,
        public_root=release / "public",
        trusted_root=release / "trusted",
        run_dir=root / "worker-probe",
        worker_dir=candidate_one,
        seed_strategy=h0_artifact,
        worker_instruction=spec.worker_instruction,
        worker_image_ref=worker_image_ref,
        verifier_image_ref=verifier_image_ref,
        proxy_image_ref=proxy_image_ref,
        task_panel_path=task_panel_path,
        task_id="T26",
        max_iterations=spec.max_iterations,
    )
    spent += _cost(
        probe.get("cost") if isinstance(probe.get("cost"), Mapping) else None
    )
    if spent >= cost_cap_usd:
        result = {
            "schema_version": 1,
            "protocol": "quantcodeeval-ap3-v2",
            "status": "budget_stop_after_probe",
            "bootstrap_loop_feasible": False,
            "certificate_path": "generic_research_state_evidence",
            "h0": h0,
            "round_one": round_one,
            "experiment_spec": spec.__dict__,
            "probe": probe,
            "cost_usd": spent,
        }
        _write_result(root / "AP3-RESULT.json", result)
        return result

    round_two_worker_artifacts: dict[str, Path] = {
        _RUN_LOCAL_H0_SEED: h0_artifact
    }
    probe_attempt_id = probe.get("terminal_attempt_id")
    if isinstance(probe_attempt_id, str):
        probe_artifact = (
            root
            / "worker-probe"
            / "attempts"
            / probe_attempt_id
            / "artifacts"
            / "strategy.py"
        )
        if probe_artifact.is_file():
            round_two_worker_artifacts["round1_probe_output"] = probe_artifact

    round_two = run_quantcodeeval_v2_activation_canary(
        config_path=config_path,
        release_dir=release,
        run_dir=root / "round-2",
        evolver_image_ref=evolver_image_ref,
        proxy_image_ref=proxy_image_ref,
        component_sources={"round1_candidate": candidate_one},
        worker_artifact_sources=round_two_worker_artifacts,
        experiment_observation_sources={
            "round1_probe": root / "worker-probe/PROBE-RESULT.json",
            "round1_prediction": root / "round-one-prediction.json",
        },
        task_ids=("T26",),
        diagnosis_note=(
            "AP-3 round two. Read the run-local round1_probe observation and "
            "compare it with the persisted round1_prediction. Reuse, refine, "
            "compose, or roll back only from this AP-3 history. Cite both the "
            "prediction and observation. The original H0 artifact and, when "
            "delivered, the probe output are available under guidance/"
            "worker_artifacts for a before/after comparison. "
            "Do not import historical candidates or artifact answers."
        ),
        validate_release=False,
        preflight_only=False,
    )
    spent += _cost(
        round_two.get("proxy_audit")
        if isinstance(round_two.get("proxy_audit"), Mapping)
        else None
    )
    decision_two = round_two.get("decision")
    observation_used = False
    if isinstance(decision_two, Mapping):
        refs = decision_two.get("evidence_refs", ())
        observation_used = isinstance(refs, list) and any(
            "experiment_observations/round1_probe.json" in str(value)
            for value in refs
        )

    final: Mapping[str, object] | None = None
    final_skipped_reason = None
    if round_two.get("status") != "PASS":
        final_skipped_reason = "round two did not submit an admitted ACT candidate"
    elif spent > cost_cap_usd - final_cost_reserve_usd:
        final_skipped_reason = "remaining AP-3 cost reserve is too small"
    else:
        assert isinstance(decision_two, Mapping)
        final = run_quantcodeeval_full_candidate(
            config_path=config_path,
            public_root=release / "public",
            trusted_root=release / "trusted",
            run_dir=root / "final-worker",
            seed_worker_dir=release / "h0/workers/H0",
            parent_worker_dir=release / "h0/workers/H0",
            candidate_worker_dir=root / "round-2/evolutions/iteration-0001/candidate",
            iteration=2,
            mechanism=_selected_mechanism(decision_two),
            primary_components=decision_two.get("primary_components", ()),
            declared_roles=decision_two.get("components", ()),
            component_tests=round_two.get("component_tests", ()),
            activation=(
                round_two.get("activation")
                if isinstance(round_two.get("activation"), Mapping)
                else None
            ),
            worker_image_ref=worker_image_ref,
            verifier_image_ref=verifier_image_ref,
            proxy_image_ref=proxy_image_ref,
            source_h0_evaluation_id=str(round_two["h0_evaluation_id"]),
            task_ids=("T26",),
            task_panel_path=task_panel_path,
        )
        spent += _proxy_cost(final)

    h0_passed = None
    h0_reward = None
    h0_summary = h0.get("score_summary")
    if isinstance(h0_summary, Mapping):
        scores = h0_summary.get("scores")
        if isinstance(scores, list) and scores and isinstance(scores[0], Mapping):
            h0_passed = scores[0].get("tests_passed")
            h0_reward = scores[0].get("reward")
    final_passed = None
    final_reward = None
    if isinstance(final, Mapping):
        summary = final.get("score_summary")
        if isinstance(summary, Mapping):
            scores = summary.get("scores")
            if isinstance(scores, list) and scores and isinstance(scores[0], Mapping):
                final_passed = scores[0].get("tests_passed")
                final_reward = scores[0].get("reward")
    component_activated = (
        isinstance(round_two.get("activation"), Mapping)
        and round_two["activation"].get("status") == "passed"  # type: ignore[index]
    )
    result = {
        "schema_version": 1,
        "protocol": "quantcodeeval-ap3-v2",
        "status": "complete" if final is not None else "complete_without_final",
        "certificate_path": "generic_research_state_evidence",
        "bootstrap_loop_feasible": bool(observation_used),
        "component_activated": component_activated,
        "bootstrap_helpful": (
            final_passed is not None
            and h0_passed is not None
            and int(final_passed) > int(h0_passed)
        ),
        "binary_helpful": final_passed == 17 and final_reward == 1,
        "h0_tests_passed": h0_passed,
        "h0_reward": h0_reward,
        "final_tests_passed": final_passed,
        "final_reward": final_reward,
        "h0": h0,
        "round_one": round_one,
        "probe_kind": "run_local_h0_artifact_activation",
        "probe_seed": _RUN_LOCAL_H0_SEED,
        "experiment_spec": spec.__dict__,
        "probe": probe,
        "round_two": round_two,
        "final": final,
        "final_skipped_reason": final_skipped_reason,
        "cost_cap_usd": cost_cap_usd,
        "cost_usd": spent,
    }
    _write_result(root / "AP3-RESULT.json", result)
    return result


__all__ = [
    "QuantCodeEvalAP3Error",
    "ap3_round_one_prediction_record",
    "find_ap3_run_local_h0_artifact",
    "require_ap3_run_local_probe",
    "run_quantcodeeval_ap3",
]
