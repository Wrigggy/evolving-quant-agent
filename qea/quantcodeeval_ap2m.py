"""Minimum two-decision AP-2M autonomy canary for QuantCodeEval."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from .quantcodeeval_full_candidate import run_quantcodeeval_full_candidate
from .quantcodeeval_repair_probe import run_probe_arm
from .quantcodeeval_v2_live import run_quantcodeeval_v2_activation_canary


class QuantCodeEvalAP2MError(ValueError):
    """An AP-2M decision, experiment, or result is incomplete."""


@dataclass(frozen=True)
class AP2MExperimentSpec:
    mode: str
    seed_experience: str | None
    worker_instruction: str
    max_iterations: int
    prediction: str
    decision_changing_observation: str

    @classmethod
    def from_decision(cls, decision: Mapping[str, object]) -> "AP2MExperimentSpec":
        raw = decision.get("experiment_spec")
        if not isinstance(raw, Mapping):
            raise QuantCodeEvalAP2MError("round one ACT lacks experiment_spec")
        mode = str(raw.get("mode", "")).casefold()
        seed = raw.get("seed_experience")
        instruction = raw.get("worker_instruction")
        iterations = raw.get("max_iterations")
        prediction = raw.get("prediction")
        counter = raw.get("decision_changing_observation")
        if mode not in {"repair", "from_scratch"}:
            raise QuantCodeEvalAP2MError("experiment mode is unsupported")
        if seed is not None and (not isinstance(seed, str) or not seed.strip()):
            raise QuantCodeEvalAP2MError("seed experience is invalid")
        if mode == "repair" and seed is None:
            raise QuantCodeEvalAP2MError("repair experiment has no seed")
        if mode == "from_scratch" and seed is not None:
            raise QuantCodeEvalAP2MError("from-scratch experiment selected a seed")
        if type(iterations) is not int or not 1 <= iterations <= 12:
            raise QuantCodeEvalAP2MError("experiment iteration budget is invalid")
        for label, value in (
            ("worker_instruction", instruction),
            ("prediction", prediction),
            ("decision_changing_observation", counter),
        ):
            if not isinstance(value, str) or not value.strip():
                raise QuantCodeEvalAP2MError(f"experiment {label} is empty")
        return cls(
            mode=mode,
            seed_experience=seed.strip() if isinstance(seed, str) else None,
            worker_instruction=instruction.strip(),
            max_iterations=iterations,
            prediction=prediction.strip(),
            decision_changing_observation=counter.strip(),
        )


def _selected_mechanism(decision: Mapping[str, object]) -> str:
    selected = decision.get("selected_hypothesis_id")
    for value in decision.get("hypotheses_considered", ()):  # type: ignore[union-attr]
        if isinstance(value, Mapping) and value.get("hypothesis_id") == selected:
            mechanism = value.get("mechanism")
            if isinstance(mechanism, str) and mechanism.strip():
                return mechanism.strip()
    raise QuantCodeEvalAP2MError("round two ACT lacks a selected mechanism")


def _cost(value: Mapping[str, object] | None) -> float:
    if not isinstance(value, Mapping):
        return 0.0
    raw = value.get("provider_cost_usd")
    return (
        float(raw)
        if isinstance(raw, (int, float)) and not isinstance(raw, bool)
        else 0.0
    )


def _write_result(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(value), sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def run_quantcodeeval_ap2m(
    *,
    config_path: str | Path,
    release_dir: str | Path,
    run_dir: str | Path,
    evolver_image_ref: str,
    worker_image_ref: str,
    verifier_image_ref: str,
    proxy_image_ref: str,
    task_panel_path: str | Path,
    seed_experiences: Mapping[str, str | Path],
    warm_component_sources: Mapping[str, str | Path] | None = None,
    warm_observation_sources: Mapping[str, str | Path] | None = None,
    prior_scored_candidate_pairs: Iterable[tuple[str | Path, str | Path]] = (),
    component_ledger_path: str | Path | None = None,
    cost_cap_usd: float = 0.25,
    final_cost_reserve_usd: float = 0.10,
    preflight_only: bool = False,
) -> dict[str, object]:
    """Run two Evolver decisions around one self-authored Worker experiment."""

    if cost_cap_usd <= 0 or not 0 <= final_cost_reserve_usd < cost_cap_usd:
        raise QuantCodeEvalAP2MError("AP-2M cost cap is invalid")
    root = Path(run_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    release = Path(release_dir).expanduser().resolve()
    pairs = tuple(prior_scored_candidate_pairs)
    activations = tuple(value[0] for value in pairs)
    scored_runs = tuple(value[1] for value in pairs)
    normalized_seeds = {
        str(name): Path(path).expanduser().resolve()
        for name, path in seed_experiences.items()
    }
    if not normalized_seeds or any(not path.is_file() for path in normalized_seeds.values()):
        raise QuantCodeEvalAP2MError("AP-2M seed experience catalog is empty or missing")

    round_one = run_quantcodeeval_v2_activation_canary(
        config_path=config_path,
        release_dir=release,
        run_dir=root / "round-1",
        evolver_image_ref=evolver_image_ref,
        proxy_image_ref=proxy_image_ref,
        prior_scored_candidate_activation_dir=activations or None,
        prior_scored_candidate_run_dir=scored_runs or None,
        component_ledger_path=component_ledger_path,
        component_sources=warm_component_sources,
        worker_artifact_sources=normalized_seeds,
        experiment_observation_sources=warm_observation_sources,
        task_ids=("T26",),
        diagnosis_note=(
            "AP-2M round one. Choose one reusable harness intervention and author "
            "one bounded Worker experiment that can discriminate your selected "
            "mechanism from a competitor. The evidence contract requires "
            "experiment_spec. Select repair or from_scratch, choose an authorized "
            "worker_artifact seed name or none, write the answer-blind Worker "
            "instruction, predict the observation, and state what result would "
            "change round two. Do not assume the candidate will be promoted."
        ),
        validate_release=False,
        autonomous_probe_required=True,
        preflight_only=preflight_only,
    )
    if preflight_only:
        result = {
            "schema_version": 1,
            "protocol": "quantcodeeval-ap2m-v1",
            "status": "preflight_complete",
            "round_one": round_one,
        }
        _write_result(root / "AP2M-PREFLIGHT.json", result)
        return result

    if round_one.get("status") != "PASS":
        result = {
            "schema_version": 1,
            "protocol": "quantcodeeval-ap2m-v1",
            "status": "round_one_terminal",
            "autonomy_feasible": False,
            "feedback_driven": False,
            "round_one": round_one,
        }
        _write_result(root / "AP2M-RESULT.json", result)
        return result

    decision_one = round_one.get("decision")
    if not isinstance(decision_one, Mapping):
        raise QuantCodeEvalAP2MError("round one result lacks a decision")
    spec = AP2MExperimentSpec.from_decision(decision_one)
    seed_path = (
        normalized_seeds.get(spec.seed_experience)
        if spec.seed_experience is not None
        else None
    )
    if spec.seed_experience is not None and seed_path is None:
        raise QuantCodeEvalAP2MError(
            f"round one selected an unknown seed: {spec.seed_experience}"
        )
    round_one_candidate = root / "round-1/evolutions/iteration-0001/candidate"
    probe = run_probe_arm(
        label="evolver-selected",
        config_path=config_path,
        public_root=release / "public",
        trusted_root=release / "trusted",
        run_dir=root / "worker-probe",
        worker_dir=round_one_candidate,
        seed_strategy=seed_path,
        worker_instruction=spec.worker_instruction,
        worker_image_ref=worker_image_ref,
        verifier_image_ref=verifier_image_ref,
        proxy_image_ref=proxy_image_ref,
        task_panel_path=task_panel_path,
        task_id="T26",
        max_iterations=spec.max_iterations,
    )
    spent = _cost(round_one.get("proxy_audit")) + _cost(
        probe.get("cost") if isinstance(probe.get("cost"), Mapping) else None
    )
    if spent >= cost_cap_usd:
        result = {
            "schema_version": 1,
            "protocol": "quantcodeeval-ap2m-v1",
            "status": "budget_stop_after_probe",
            "autonomy_feasible": False,
            "feedback_driven": False,
            "round_one": round_one,
            "experiment_spec": spec.__dict__,
            "probe": probe,
            "cost_usd": spent,
        }
        _write_result(root / "AP2M-RESULT.json", result)
        return result

    round_two = run_quantcodeeval_v2_activation_canary(
        config_path=config_path,
        release_dir=release,
        run_dir=root / "round-2",
        evolver_image_ref=evolver_image_ref,
        proxy_image_ref=proxy_image_ref,
        component_ledger_path=component_ledger_path,
        component_sources={"round1_candidate": round_one_candidate},
        experiment_observation_sources={
            "round1_probe": root / "worker-probe/PROBE-RESULT.json"
        },
        worker_artifact_sources=normalized_seeds,
        task_ids=("T26",),
        diagnosis_note=(
            "AP-2M round two. Read guidance/experiment_observations/"
            "round1_probe.json and compare the actual observation with the prior "
            f"prediction: {spec.prediction} Counter-observation: "
            f"{spec.decision_changing_observation} The exact round-one harness is "
            "available as guidance/component_sources/round1_candidate. Decide from "
            "the observed result: REUSE/REFINE/COMPOSE it and ACT, or roll back with "
            "a grounded ABSTAIN. Cite the experiment observation in evidence_refs."
        ),
        validate_release=False,
        preflight_only=False,
    )
    spent += _cost(round_two.get("proxy_audit"))
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
        final_skipped_reason = "remaining AP-2M cost reserve is too small"
    else:
        assert isinstance(decision_two, Mapping)
        final = run_quantcodeeval_full_candidate(
            config_path=config_path,
            public_root=release / "public",
            trusted_root=release / "trusted",
            run_dir=root / "final-worker",
            seed_worker_dir=release / "h0/workers/H0",
            parent_worker_dir=release / "h0/workers/H0",
            candidate_worker_dir=(
                root / "round-2/evolutions/iteration-0001/candidate"
            ),
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
        spent += _cost(
            final.get("cost_audit")
            if isinstance(final.get("cost_audit"), Mapping)
            else None
        )

    final_reward = None
    final_tests_passed = None
    if isinstance(final, Mapping):
        summary = final.get("score_summary")
        if isinstance(summary, Mapping):
            rewards = summary.get("task_rewards")
            if isinstance(rewards, Mapping):
                final_reward = rewards.get("T26")
            scores = summary.get("scores")
            if isinstance(scores, list) and scores and isinstance(scores[0], Mapping):
                final_tests_passed = scores[0].get("tests_passed")
    result = {
        "schema_version": 1,
        "protocol": "quantcodeeval-ap2m-v1",
        "status": "complete" if final is not None else "complete_without_final",
        "autonomy_feasible": True,
        "feedback_driven": observation_used,
        "component_activated": (
            isinstance(round_two.get("activation"), Mapping)
            and round_two["activation"].get("status") == "passed"  # type: ignore[index]
        ),
        "benchmark_helpful": final_reward == 1,
        "binary_helpful": final_tests_passed == 17 and final_reward == 1,
        "experiment_spec": spec.__dict__,
        "round_one": round_one,
        "probe": probe,
        "round_two": round_two,
        "final": final,
        "final_skipped_reason": final_skipped_reason,
        "cost_cap_usd": cost_cap_usd,
        "cost_usd": spent,
    }
    _write_result(root / "AP2M-RESULT.json", result)
    return result


__all__ = [
    "AP2MExperimentSpec",
    "QuantCodeEvalAP2MError",
    "run_quantcodeeval_ap2m",
]
