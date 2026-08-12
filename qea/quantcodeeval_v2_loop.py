"""Variable-length QuantCodeEval v2 full-harness evolution controller."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Mapping, Protocol

from .candidate_admission import AdmissionPolicy, admit_candidate
from .evolution_evidence import EvidenceRecord
from .loop_benchmark import hash_worker_directory
from .mutation_metrics import measure_mutation
from .quantcodeeval_history import append_quantcodeeval_history
from .quantcodeeval_search import (
    QuantCodeEvalSearchState,
    SearchDecision,
    SearchSelection,
    quantcodeeval_search_payload,
    record_quantcodeeval_search_round,
)


class QuantCodeEvalV2LoopError(ValueError):
    """The Evolver output or an outer-loop transition is inconsistent."""


@dataclass(frozen=True)
class QuantCandidateEvaluation:
    """Closed result returned by the benchmark-specific candidate evaluator."""

    official_rewards: Mapping[str, float]
    answer_free_evaluation: Mapping[str, object]
    official_evaluated: bool
    new_information: bool
    reason: str
    model_requests: int = 0
    cost_usd: float = 0.0

    def __post_init__(self) -> None:
        if not self.official_rewards:
            raise QuantCodeEvalV2LoopError("candidate evaluation rewards are empty")
        if any(
            isinstance(value, bool) or value not in {0, 0.0, 1, 1.0}
            for value in self.official_rewards.values()
        ):
            raise QuantCodeEvalV2LoopError(
                "QuantCodeEval candidate rewards must be binary"
            )
        if type(self.model_requests) is not int or self.model_requests < 0:
            raise QuantCodeEvalV2LoopError("candidate model request count is invalid")
        if isinstance(self.cost_usd, bool) or self.cost_usd < 0:
            raise QuantCodeEvalV2LoopError("candidate cost is invalid")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise QuantCodeEvalV2LoopError("candidate evaluation reason is required")
        json.dumps(self.answer_free_evaluation, sort_keys=True)


class EvolverProposal(Protocol):
    candidate_dir: Path
    candidate_digest: str
    summary_uri: Path
    prediction_uri: Path


EvidenceBuilder = Callable[
    [QuantCodeEvalSearchState, int, Path | None], EvidenceRecord
]
ActivationRunner = Callable[
    [
        Path,
        Mapping[str, object],
        tuple[Mapping[str, object], ...],
        int,
    ],
    Mapping[str, object],
]
CandidateEvaluator = Callable[
    [Path, Path, Mapping[str, object], tuple[Mapping[str, object], ...], Mapping[str, object], int],
    QuantCandidateEvaluation,
]
DiagnosisBuilder = Callable[[QuantCodeEvalSearchState, int], str]


def _json_object(path: Path, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise QuantCodeEvalV2LoopError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise QuantCodeEvalV2LoopError(f"{label} must be a JSON object")
    return value


def _proposal_decision(proposal: EvolverProposal) -> dict[str, object]:
    summary = _json_object(Path(proposal.summary_uri), label="Evolver summary")
    state = summary.get("discovery_hypothesis")
    if not isinstance(state, Mapping):
        raise QuantCodeEvalV2LoopError(
            "Evolver summary has no persisted discovery decision"
        )
    if (
        state.get("schema_version") != 4
        or state.get("protocol") != "quant_property_v2"
    ):
        raise QuantCodeEvalV2LoopError("Evolver used a different decision protocol")
    hypothesis = state.get("hypothesis")
    if not isinstance(hypothesis, Mapping):
        raise QuantCodeEvalV2LoopError("Evolver decision hypothesis is missing")
    decision = str(state.get("decision", "")).upper()
    if decision not in {"ACT", "ABSTAIN"} or hypothesis.get("decision") != decision:
        raise QuantCodeEvalV2LoopError("Evolver decision state is inconsistent")
    return dict(hypothesis)


def _proposal_usage(proposal: EvolverProposal) -> tuple[int, float | None]:
    summary = _json_object(Path(proposal.summary_uri), label="Evolver summary")
    usage = summary.get("model_usage")
    if not isinstance(usage, list) or not usage:
        return 1, None
    costs: list[float] = []
    for item in usage:
        if not isinstance(item, Mapping):
            continue
        value = item.get("cost_usd")
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
            costs.append(float(value))
    return len(usage), sum(costs) if len(costs) == len(usage) else None


def _proposal_component_tests(
    proposal: EvolverProposal,
    *,
    primary_components: tuple[str, ...],
    candidate_digest: str,
) -> tuple[Mapping[str, object], ...]:
    summary = _json_object(Path(proposal.summary_uri), label="Evolver summary")
    raw = summary.get("component_tests", [])
    if not isinstance(raw, list) or any(not isinstance(value, Mapping) for value in raw):
        raise QuantCodeEvalV2LoopError("Evolver component test records are invalid")
    records = tuple(dict(value) for value in raw)
    if records and [value.get("test_index") for value in records] != list(
        range(1, len(records) + 1)
    ):
        raise QuantCodeEvalV2LoopError("Evolver component test order is invalid")
    latest: dict[str, Mapping[str, object]] = {}
    for value in records:
        component = value.get("component")
        if (
            value.get("schema_version") != 1
            or value.get("status") not in {"passed", "failed"}
            or not isinstance(component, str)
        ):
            raise QuantCodeEvalV2LoopError("Evolver component test schema differs")
        latest[component] = value
    executable = {
        "agent_config",
        "tools",
        "validator",
        "skills",
        "memory",
        "middleware",
        "routing",
    }
    missing = sorted(
        component
        for component in primary_components
        if component in executable
        and (
            latest.get(component, {}).get("status") != "passed"
            or latest.get(component, {}).get("candidate_digest")
            != candidate_digest
        )
    )
    if missing:
        raise QuantCodeEvalV2LoopError(
            "primary components lack a final digest-bound passed smoke: "
            + ", ".join(missing)
        )
    return records


def _selection(
    state: QuantCodeEvalSearchState,
    evaluation: QuantCandidateEvaluation,
) -> SearchSelection:
    rewards = evaluation.official_rewards
    official = state.official_rewards
    improves = all(rewards[key] >= official[key] for key in state.task_ids) and any(
        rewards[key] > official[key] for key in state.task_ids
    )
    if evaluation.official_evaluated and improves:
        return SearchSelection.OFFICIAL_PROMOTED
    non_regressing = all(rewards[key] >= official[key] for key in state.task_ids)
    if evaluation.official_evaluated and non_regressing and evaluation.new_information:
        return SearchSelection.DIAGNOSTIC_PROMOTED
    if evaluation.new_information:
        return SearchSelection.ARCHIVED
    return SearchSelection.REJECTED


def _atomic_json(path: Path, value: object, *, replace_existing: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    if path.exists():
        if path.is_symlink():
            raise QuantCodeEvalV2LoopError(f"persisted evidence is a symlink: {path}")
        if not replace_existing and path.read_text(encoding="utf-8") != payload:
            raise QuantCodeEvalV2LoopError(f"persisted evidence differs: {path}")
        if not replace_existing:
            return
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, path)


def _parent_path(
    state: QuantCodeEvalSearchState, *, seed_worker_dir: Path, history_root: Path
) -> Path:
    if state.search_parent_digest == state.h0_digest:
        parent = seed_worker_dir
    else:
        parent = history_root / "objects" / state.search_parent_digest
    if hash_worker_directory(parent) != state.search_parent_digest:
        raise QuantCodeEvalV2LoopError("search-parent snapshot identity differs")
    return parent


def _round_payload(
    *,
    iteration: int,
    decision: Mapping[str, object],
    candidate_digest: str | None,
    history_entry_id: str | None,
    component_tests: tuple[Mapping[str, object], ...],
    activation: Mapping[str, object],
    evaluation: QuantCandidateEvaluation | None,
    selection: SearchSelection,
    evidence: EvidenceRecord,
    prediction: Mapping[str, object],
) -> dict[str, object]:
    return {
        "schema_version": 2,
        "protocol": "quant_property_v2_full_harness",
        "iteration": iteration,
        "decision": dict(decision),
        "candidate_digest": candidate_digest,
        "history_entry_id": history_entry_id,
        "component_tests": [dict(value) for value in component_tests],
        "activation": dict(activation),
        "evaluation": asdict(evaluation) if evaluation is not None else None,
        "selection": selection.value,
        "evidence_sha256": evidence.sha256,
        "prediction": dict(prediction),
    }


def run_quantcodeeval_v2_loop(
    *,
    state: QuantCodeEvalSearchState,
    run_dir: str | Path,
    seed_worker_dir: str | Path,
    evolver_dir: str | Path,
    proposer: object,
    evidence_builder: EvidenceBuilder,
    activation_runner: ActivationRunner,
    candidate_evaluator: CandidateEvaluator,
    diagnosis_builder: DiagnosisBuilder,
) -> QuantCodeEvalSearchState:
    """Run until an evidence-based stop condition or the configured safety cap."""

    root = Path(run_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    seed = Path(seed_worker_dir).expanduser().resolve()
    evolver = Path(evolver_dir).expanduser().resolve()
    if hash_worker_directory(seed) != state.h0_digest:
        raise QuantCodeEvalV2LoopError("H0 worker identity differs from search state")
    history_root = root / "history"
    while not state.stopped:
        iteration = state.next_iteration
        parent = _parent_path(
            state, seed_worker_dir=seed, history_root=history_root
        )
        history_argument = history_root if (history_root / "INDEX.json").is_file() else None
        evidence = evidence_builder(state, iteration, history_argument)
        proposal = proposer.propose(
            candidate_dir=parent,
            evidence_dir=evidence,
            evolver_dir=evolver,
            diagnosis=diagnosis_builder(state, iteration),
            iteration=iteration,
            run_id=state.run_id,
            run_dir=root,
        )
        decision = _proposal_decision(proposal)
        proposal_requests, proposal_cost = _proposal_usage(proposal)
        prediction = _json_object(Path(proposal.prediction_uri), label="Evolver prediction")
        candidate = Path(proposal.candidate_dir).resolve()
        actual_digest = hash_worker_directory(candidate)
        if actual_digest != proposal.candidate_digest:
            raise QuantCodeEvalV2LoopError("Evolver candidate digest differs")

        if decision["decision"] == "ABSTAIN":
            if actual_digest != state.search_parent_digest:
                raise QuantCodeEvalV2LoopError("ABSTAIN candidate changed the harness")
            state = record_quantcodeeval_search_round(
                state,
                decision=SearchDecision.ABSTAIN,
                official_rewards=state.official_rewards,
                selection=SearchSelection.ABSTAINED,
                reason=str(decision.get("abstain_reason", "calibrated abstention")),
                new_information=False,
                model_requests=proposal_requests,
                cost_usd=proposal_cost or 0.0,
            )
            _atomic_json(
                root / "rounds" / f"iteration-{iteration:04d}.json",
                _round_payload(
                    iteration=iteration,
                    decision=decision,
                    candidate_digest=None,
                    history_entry_id=None,
                    component_tests=(),
                    activation={"status": "not_run"},
                    evaluation=None,
                    selection=SearchSelection.ABSTAINED,
                    evidence=evidence,
                    prediction=prediction,
                ),
            )
            _atomic_json(
                root / "SEARCH-STATE.json",
                quantcodeeval_search_payload(state),
                replace_existing=True,
            )
            continue

        components = tuple(str(value) for value in decision.get("components", ()))
        primary = tuple(
            str(value) for value in decision.get("primary_components", ())
        )
        admission = admit_candidate(seed, candidate, AdmissionPolicy.qfbench_full())
        metrics = measure_mutation(
            before_root=parent,
            after_root=candidate,
            declared_roles=components,
        )
        if (
            not admission.admitted
            or not primary
            or not set(primary) <= set(components)
            or metrics["changed_file_count"] == 0
            or metrics["declared_roles_match_actual"] is not True
        ):
            raise QuantCodeEvalV2LoopError(
                "ACT candidate failed independent admission or component attribution"
            )
        evolver_tests = _proposal_component_tests(
            proposal,
            primary_components=primary,
            candidate_digest=actual_digest,
        )
        component_tests: tuple[Mapping[str, object], ...] = (
            *evolver_tests,
            {
                "kind": "independent_full_harness_admission",
                "status": "passed",
                "candidate_digest": actual_digest,
                "checks": list(admission.checks),
            },
        )
        activation = dict(
            activation_runner(candidate, decision, component_tests, iteration)
        )
        if activation.get("status") not in {"passed", "failed"}:
            raise QuantCodeEvalV2LoopError("activation must return passed or failed")
        if activation["status"] == "passed":
            evaluation = candidate_evaluator(
                parent,
                candidate,
                decision,
                component_tests,
                activation,
                iteration,
            )
        else:
            evaluation = QuantCandidateEvaluation(
                official_rewards=dict(state.search_parent_rewards),
                answer_free_evaluation={"official_evaluated": False},
                official_evaluated=False,
                new_information=True,
                reason="component activation failed before official evaluation",
            )
        if set(evaluation.official_rewards) != set(state.task_ids):
            raise QuantCodeEvalV2LoopError("candidate reward panel differs")
        selection = _selection(state, evaluation)
        history_selection = {
            SearchSelection.OFFICIAL_PROMOTED: "accepted",
            SearchSelection.DIAGNOSTIC_PROMOTED: "accepted",
            SearchSelection.ARCHIVED: "archived",
            SearchSelection.REJECTED: "rejected",
        }[selection]
        mechanism = next(
            (
                str(value.get("mechanism"))
                for value in decision.get("hypotheses_considered", ())
                if isinstance(value, Mapping)
                and value.get("hypothesis_id") == decision.get("selected_hypothesis_id")
            ),
            str(decision.get("selected_hypothesis_id", "unknown mechanism")),
        )
        history = append_quantcodeeval_history(
            history_root=history_root,
            run_id=state.run_id,
            iteration=iteration,
            parent_worker_dir=parent,
            candidate_worker_dir=candidate,
            decision=decision,
            mechanism=mechanism,
            primary_components=primary,
            declared_roles=components,
            component_tests=component_tests,
            activation=activation,
            evaluation={
                "official_evaluated": evaluation.official_evaluated,
                "official_rewards": dict(evaluation.official_rewards),
                "answer_free": dict(evaluation.answer_free_evaluation),
                "new_information": evaluation.new_information,
                "reason": evaluation.reason,
            },
            selection=history_selection,
            rollback_reason=(evaluation.reason if history_selection == "rejected" else None),
        )
        state = record_quantcodeeval_search_round(
            state,
            decision=SearchDecision.ACT,
            official_rewards=evaluation.official_rewards,
            selection=selection,
            reason=evaluation.reason,
            new_information=evaluation.new_information,
            model_requests=proposal_requests + evaluation.model_requests,
            cost_usd=(proposal_cost or 0.0) + evaluation.cost_usd,
            candidate_digest=actual_digest,
            history_entry_id=history.entry_id,
            mechanism=mechanism,
            primary_components=primary,
            declared_roles=components,
        )
        _atomic_json(
            root / "rounds" / f"iteration-{iteration:04d}.json",
            _round_payload(
                iteration=iteration,
                decision=decision,
                candidate_digest=actual_digest,
                history_entry_id=history.entry_id,
                component_tests=component_tests,
                activation=activation,
                evaluation=evaluation,
                selection=selection,
                evidence=evidence,
                prediction=prediction,
            ),
        )
        _atomic_json(
            root / "SEARCH-STATE.json",
            quantcodeeval_search_payload(state),
            replace_existing=True,
        )
    return state


__all__ = [
    "QuantCandidateEvaluation",
    "QuantCodeEvalV2LoopError",
    "run_quantcodeeval_v2_loop",
]
