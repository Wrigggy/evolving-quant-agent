"""Minimal five-round Property-Guided Bidirectional Harness Search core.

This module is deliberately free of model and sandbox construction.  It owns
only the answer-free ACT/ABSTAIN contract, completed-evaluation references,
official versus diagnostic selection, archive bookkeeping, and the fixed
five-iteration state transition.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Mapping

from .quantcodeeval_evidence import PropertyFamilyProgress


_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_TASK_ID = re.compile(r"T(?:0[1-9]|[12][0-9]|30)\Z")
_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_COMPONENTS = frozenset(
    {
        "middleware",
        "skills",
        "systemprompt",
        "tool_descriptions",
        "tools",
        "validator",
    }
)
_ROUTER = {
    "artifact_interface": frozenset(
        {"middleware", "systemprompt", "tool_descriptions", "tools", "validator"}
    ),
    "data_temporal_integrity": frozenset(
        {"middleware", "skills", "systemprompt", "tools", "validator"}
    ),
    "quant_definition_estimation": frozenset(
        {"skills", "systemprompt", "tools"}
    ),
    "portfolio_execution": frozenset(
        {"skills", "systemprompt", "tools", "validator"}
    ),
    "resource_termination": frozenset(
        {"middleware", "systemprompt", "tool_descriptions", "tools"}
    ),
}


class QuantPGBHSError(ValueError):
    """A decision, selection, or state transition is invalid."""


class FailureClass(str, Enum):
    ARTIFACT_INTERFACE = "artifact_interface"
    DATA_TEMPORAL_INTEGRITY = "data_temporal_integrity"
    QUANT_DEFINITION_ESTIMATION = "quant_definition_estimation"
    PORTFOLIO_EXECUTION = "portfolio_execution"
    RESOURCE_TERMINATION = "resource_termination"
    ISOLATED_TASK_SPECIFIC = "isolated_task_specific"
    UNKNOWN = "unknown"


class Decision(str, Enum):
    ACT = "ACT"
    ABSTAIN = "ABSTAIN"


class MutationOperator(str, Enum):
    ADD = "add"
    REPLACE = "replace"
    DELETE = "delete"
    ROLLBACK = "rollback"


class EvidenceBasis(str, Enum):
    CROSS_TASK_RECURRENCE = "cross_task_recurrence"
    DETERMINISTIC_INTERFACE = "deterministic_interface"
    TYPE_A_CLAUSE_ARTIFACT_TRACE = "type_a_clause_artifact_trace"


def _text(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise QuantPGBHSError(f"{label} must be non-empty text")
    return value.strip()


def _task_ids(values: object, *, label: str, minimum: int = 0) -> tuple[str, ...]:
    if not isinstance(values, list) or any(
        not isinstance(value, str) or _TASK_ID.fullmatch(value) is None
        for value in values
    ):
        raise QuantPGBHSError(f"{label} must be a list of QuantCodeEval task IDs")
    result = tuple(values)
    if len(result) < minimum or len(result) != len(set(result)):
        raise QuantPGBHSError(f"{label} has invalid size or duplicates")
    return result


@dataclass(frozen=True)
class TaskPanelResult:
    task_id: str
    official_reward: float
    type_a: PropertyFamilyProgress
    type_b: PropertyFamilyProgress

    def __post_init__(self) -> None:
        if _TASK_ID.fullmatch(self.task_id) is None:
            raise QuantPGBHSError("panel result has an invalid task ID")
        if isinstance(self.official_reward, bool) or self.official_reward not in {
            0.0,
            1.0,
        }:
            raise QuantPGBHSError("panel official reward must be binary")
        completed = (
            self.type_a.passed == self.type_a.total
            and self.type_b.passed == self.type_b.total
        )
        if self.official_reward != (1.0 if completed else 0.0):
            raise QuantPGBHSError(
                "panel official reward differs from property-family completion"
            )


@dataclass(frozen=True)
class EvaluationRef:
    """Reference to one already completed panel; it never requests resampling."""

    evaluation_id: str
    checkpoint: str
    worker_digest: str
    panel_digest: str
    sampling_identity_digest: str
    attempt_ids: Mapping[str, str]
    task_results: Mapping[str, TaskPanelResult]
    reused_from_evaluation_id: str | None = None
    resampled: bool = False

    def __post_init__(self) -> None:
        for name in ("worker_digest", "panel_digest", "sampling_identity_digest"):
            if _SHA256.fullmatch(str(getattr(self, name))) is None:
                raise QuantPGBHSError(f"{name} must be SHA-256")
        if (
            _SAFE_ID.fullmatch(self.evaluation_id) is None
            or _SAFE_ID.fullmatch(self.checkpoint) is None
        ):
            raise QuantPGBHSError("evaluation ID and checkpoint must be path-safe")
        if self.resampled is not False:
            raise QuantPGBHSError(
                "EvaluationRef must reference completed evidence with resampled=false"
            )
        task_ids = set(self.task_results)
        if task_ids != set(self.attempt_ids) or not task_ids:
            raise QuantPGBHSError("evaluation task and attempt panels differ")
        if any(
            task_id != result.task_id
            for task_id, result in self.task_results.items()
        ):
            raise QuantPGBHSError("evaluation task-result identity differs")
        if self.reused_from_evaluation_id is not None and not str(
            self.reused_from_evaluation_id
        ).strip():
            raise QuantPGBHSError("reused evaluation ID must be non-empty")

    def as_reuse(self) -> "EvaluationRef":
        """Return an explicit no-resample reference for the next iteration."""

        return replace(
            self,
            reused_from_evaluation_id=self.evaluation_id,
            resampled=False,
        )


@dataclass(frozen=True)
class PropertyPrediction:
    task_id: str
    family: str
    minimum_passed_delta: int
    protected_task_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if _TASK_ID.fullmatch(self.task_id) is None:
            raise QuantPGBHSError("prediction has an invalid task ID")
        if self.family not in {"type_a", "type_b"}:
            raise QuantPGBHSError("prediction family must be type_a or type_b")
        if (
            isinstance(self.minimum_passed_delta, bool)
            or not isinstance(self.minimum_passed_delta, int)
            or self.minimum_passed_delta < 1
        ):
            raise QuantPGBHSError("prediction minimum delta must be positive")
        if any(_TASK_ID.fullmatch(value) is None for value in self.protected_task_ids):
            raise QuantPGBHSError("prediction protection task is invalid")


@dataclass(frozen=True)
class QuantDecisionRecord:
    decision: Decision
    failure_class: FailureClass
    hypotheses: tuple[Mapping[str, str], ...]
    selected_hypothesis_id: str | None
    evidence_refs: tuple[str, ...]
    public_clause_ref: Mapping[str, object] | None
    artifact_fact_ref: str | None
    trace_fact_ref: str | None
    evidence_basis: EvidenceBasis | None
    component: str | None
    mutation_operator: MutationOperator | None
    prediction: PropertyPrediction | None
    risk_tasks: tuple[str, ...]
    counterevidence: str
    uncertainty: str
    abstain_reason: str | None

    def __post_init__(self) -> None:
        if len(self.hypotheses) < 2:
            raise QuantPGBHSError("decision requires at least two hypotheses")
        hypothesis_ids = [value.get("hypothesis_id") for value in self.hypotheses]
        if (
            any(not isinstance(value, str) or not value for value in hypothesis_ids)
            or len(hypothesis_ids) != len(set(hypothesis_ids))
        ):
            raise QuantPGBHSError("decision hypothesis IDs are invalid")
        if not self.counterevidence.strip() or not self.uncertainty.strip():
            raise QuantPGBHSError("decision requires counterevidence and uncertainty")
        if self.decision is Decision.ABSTAIN:
            if any(
                value is not None
                for value in (
                    self.selected_hypothesis_id,
                    self.public_clause_ref,
                    self.artifact_fact_ref,
                    self.trace_fact_ref,
                    self.evidence_basis,
                    self.component,
                    self.mutation_operator,
                    self.prediction,
                )
            ):
                raise QuantPGBHSError("ABSTAIN must not carry an ACT intervention")
            if not isinstance(self.abstain_reason, str) or not self.abstain_reason.strip():
                raise QuantPGBHSError("ABSTAIN requires a reason")
            return
        if self.failure_class in {
            FailureClass.ISOLATED_TASK_SPECIFIC,
            FailureClass.UNKNOWN,
        }:
            raise QuantPGBHSError("isolated or unknown failures cannot unlock ACT")
        if self.selected_hypothesis_id not in set(hypothesis_ids):
            raise QuantPGBHSError("ACT selected hypothesis is invalid")
        if len(self.evidence_refs) < 3 or len(self.evidence_refs) != len(
            set(self.evidence_refs)
        ):
            raise QuantPGBHSError("ACT requires three unique evidence refs")
        if any(
            value is None
            for value in (
                self.public_clause_ref,
                self.artifact_fact_ref,
                self.trace_fact_ref,
                self.evidence_basis,
                self.component,
                self.mutation_operator,
                self.prediction,
            )
        ):
            raise QuantPGBHSError("ACT intervention fields are incomplete")
        assert self.component is not None
        if self.component not in _COMPONENTS or self.component not in _ROUTER[
            self.failure_class.value
        ]:
            raise QuantPGBHSError("ACT component is not routed for the failure class")
        if self.abstain_reason is not None:
            raise QuantPGBHSError("ACT must not carry an abstain reason")

    @property
    def unlocked(self) -> bool:
        return self.decision is Decision.ACT


def _member_ref(
    value: object,
    *,
    label: str,
    members: set[str],
    accessed: set[str],
) -> str:
    ref = _text(value, label=label)
    if ref not in members:
        raise QuantPGBHSError(f"{label} is not an exact evidence member")
    if ref not in accessed:
        raise QuantPGBHSError(f"{label} was not accessed before decision")
    return ref


def _public_clause(
    value: object,
    *,
    evidence_root: Path,
    members: set[str],
    accessed: set[str],
) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != {
        "path",
        "start_line",
        "end_line",
        "text_sha256",
    }:
        raise QuantPGBHSError("public_clause_ref schema differs")
    path = _member_ref(
        value["path"], label="public clause path", members=members, accessed=accessed
    )
    if not path.endswith("/instruction.md"):
        raise QuantPGBHSError("public clause must refer to a task instruction")
    start = value["start_line"]
    end = value["end_line"]
    digest = value["text_sha256"]
    if (
        isinstance(start, bool)
        or isinstance(end, bool)
        or not isinstance(start, int)
        or not isinstance(end, int)
        or start < 1
        or end < start
        or _SHA256.fullmatch(str(digest)) is None
    ):
        raise QuantPGBHSError("public clause line range or digest is invalid")
    lines = (evidence_root / path).read_text(encoding="utf-8").splitlines()
    if end > len(lines):
        raise QuantPGBHSError("public clause line range exceeds instruction")
    selected = "\n".join(lines[start - 1 : end]) + "\n"
    if hashlib.sha256(selected.encode()).hexdigest() != digest:
        raise QuantPGBHSError("public clause digest differs from evidence")
    return {
        "path": path,
        "start_line": start,
        "end_line": end,
        "text_sha256": digest,
    }


def validate_quant_decision(
    payload: Mapping[str, object],
    *,
    evidence_root: str | Path,
    evidence_members: tuple[str, ...],
    accessed_evidence_paths: set[str] | frozenset[str],
    allowed_task_ids: tuple[str, ...],
) -> QuantDecisionRecord:
    """Validate one quant-specific terminal decision and ACT write gate."""

    if not isinstance(payload, Mapping):
        raise QuantPGBHSError("decision payload must be an object")
    root = Path(evidence_root).resolve()
    members = set(evidence_members)
    accessed = set(accessed_evidence_paths)
    allowed = set(allowed_task_ids)
    if not root.is_dir() or not members:
        raise QuantPGBHSError("authorized evidence is unavailable")
    try:
        decision = Decision(_text(payload.get("decision"), label="decision").upper())
        failure_class = FailureClass(
            _text(payload.get("failure_class"), label="failure_class").casefold()
        )
    except ValueError as exc:
        raise QuantPGBHSError("decision or failure_class is unsupported") from exc
    counterevidence = _text(payload.get("counterevidence"), label="counterevidence")
    uncertainty = _text(payload.get("uncertainty"), label="uncertainty")

    raw_hypotheses = payload.get("hypotheses_considered")
    if not isinstance(raw_hypotheses, list) or len(raw_hypotheses) < 2:
        raise QuantPGBHSError("at least two competing hypotheses are required")
    hypotheses: list[dict[str, str]] = []
    hypothesis_ids: set[str] = set()
    for index, raw in enumerate(raw_hypotheses):
        if not isinstance(raw, Mapping) or set(raw) != {
            "hypothesis_id",
            "mechanism",
        }:
            raise QuantPGBHSError(f"hypothesis {index} schema differs")
        hypothesis_id = _text(raw["hypothesis_id"], label="hypothesis ID")
        mechanism = _text(raw["mechanism"], label="hypothesis mechanism")
        if hypothesis_id in hypothesis_ids:
            raise QuantPGBHSError("hypothesis IDs must be unique")
        hypothesis_ids.add(hypothesis_id)
        hypotheses.append({"hypothesis_id": hypothesis_id, "mechanism": mechanism})

    raw_refs = payload.get("evidence_refs", [])
    if not isinstance(raw_refs, list) or any(not isinstance(ref, str) for ref in raw_refs):
        raise QuantPGBHSError("evidence_refs must be a text list")
    refs = tuple(
        _member_ref(ref, label="evidence ref", members=members, accessed=accessed)
        for ref in raw_refs
    )
    if len(refs) != len(set(refs)):
        raise QuantPGBHSError("evidence_refs must not contain duplicates")

    risk_tasks_raw = payload.get("risk_tasks", [])
    risk_tasks = _task_ids(risk_tasks_raw, label="risk_tasks")
    if not set(risk_tasks) <= allowed:
        raise QuantPGBHSError("risk_tasks contains a task outside the panel")

    if decision is Decision.ABSTAIN:
        if payload.get("component") is not None or payload.get("mutation_operator") is not None:
            raise QuantPGBHSError("ABSTAIN must not declare a mutation")
        if payload.get("prediction") is not None:
            raise QuantPGBHSError("ABSTAIN must not declare a prediction")
        if payload.get("selected_hypothesis_id") is not None:
            raise QuantPGBHSError("ABSTAIN must not select a hypothesis")
        return QuantDecisionRecord(
            decision=decision,
            failure_class=failure_class,
            hypotheses=tuple(hypotheses),
            selected_hypothesis_id=None,
            evidence_refs=refs,
            public_clause_ref=None,
            artifact_fact_ref=None,
            trace_fact_ref=None,
            evidence_basis=None,
            component=None,
            mutation_operator=None,
            prediction=None,
            risk_tasks=risk_tasks,
            counterevidence=counterevidence,
            uncertainty=uncertainty,
            abstain_reason=_text(payload.get("abstain_reason"), label="abstain_reason"),
        )

    if failure_class in {
        FailureClass.ISOLATED_TASK_SPECIFIC,
        FailureClass.UNKNOWN,
    }:
        raise QuantPGBHSError("isolated or unknown failures cannot unlock ACT")
    selected = _text(
        payload.get("selected_hypothesis_id"), label="selected_hypothesis_id"
    )
    if selected not in hypothesis_ids:
        raise QuantPGBHSError("selected hypothesis is unknown")
    if len(refs) < 3:
        raise QuantPGBHSError("ACT requires at least three exact evidence refs")
    clause = _public_clause(
        payload.get("public_clause_ref"),
        evidence_root=root,
        members=members,
        accessed=accessed,
    )
    artifact_ref = _member_ref(
        payload.get("artifact_fact_ref"),
        label="artifact_fact_ref",
        members=members,
        accessed=accessed,
    )
    if not artifact_ref.endswith(
        ("/strategy_ast_facts.json", "/artifact_manifest.json")
    ):
        raise QuantPGBHSError("artifact fact must be a coarse strategy fact")
    trace_ref = _member_ref(
        payload.get("trace_fact_ref"),
        label="trace_fact_ref",
        members=members,
        accessed=accessed,
    )
    if not trace_ref.endswith(("/trace_facts.json", "/process_facts.json")):
        raise QuantPGBHSError("trace fact must be a coarse process fact")
    try:
        basis = EvidenceBasis(_text(payload.get("evidence_basis"), label="evidence_basis"))
        operator = MutationOperator(
            _text(payload.get("mutation_operator"), label="mutation_operator")
        )
    except ValueError as exc:
        raise QuantPGBHSError("evidence basis or mutation operator is unsupported") from exc
    component = _text(payload.get("component"), label="component")
    if component not in _COMPONENTS or component not in _ROUTER[failure_class.value]:
        raise QuantPGBHSError("component is not routed for the selected failure class")
    prediction_raw = payload.get("prediction")
    if not isinstance(prediction_raw, Mapping) or set(prediction_raw) != {
        "task_id",
        "family",
        "minimum_passed_delta",
        "protected_task_ids",
    }:
        raise QuantPGBHSError("ACT prediction schema differs")
    prediction = PropertyPrediction(
        task_id=_text(prediction_raw["task_id"], label="prediction task"),
        family=_text(prediction_raw["family"], label="prediction family"),
        minimum_passed_delta=prediction_raw["minimum_passed_delta"],
        protected_task_ids=_task_ids(
            prediction_raw["protected_task_ids"], label="protected_task_ids"
        ),
    )
    if prediction.task_id not in allowed or not set(prediction.protected_task_ids) <= allowed:
        raise QuantPGBHSError("prediction contains a task outside the fixed panel")
    if basis is EvidenceBasis.TYPE_A_CLAUSE_ARTIFACT_TRACE and prediction.family != "type_a":
        raise QuantPGBHSError("Type-A evidence basis must predict Type-A progress")
    return QuantDecisionRecord(
        decision=decision,
        failure_class=failure_class,
        hypotheses=tuple(hypotheses),
        selected_hypothesis_id=selected,
        evidence_refs=refs,
        public_clause_ref=clause,
        artifact_fact_ref=artifact_ref,
        trace_fact_ref=trace_ref,
        evidence_basis=basis,
        component=component,
        mutation_operator=operator,
        prediction=prediction,
        risk_tasks=risk_tasks,
        counterevidence=counterevidence,
        uncertainty=uncertainty,
        abstain_reason=None,
    )


@dataclass(frozen=True)
class CandidateAdmissionSummary:
    admitted: bool
    nonempty_diff: bool
    declared_roles_match_actual: bool
    failure: str | None = None

    def __post_init__(self) -> None:
        if self.admitted and not (
            self.nonempty_diff and self.declared_roles_match_actual
        ):
            raise QuantPGBHSError(
                "admitted ACT requires a non-empty, role-aligned mutation"
            )
        if not self.admitted and not self.failure:
            raise QuantPGBHSError("rejected admission requires a failure reason")


@dataclass(frozen=True)
class SelectionResult:
    official_promoted: bool
    search_parent_promoted: bool
    prediction_consistent: bool
    official_reason: str
    search_reason: str
    family_passed_delta: int


def _same_panel(left: EvaluationRef, right: EvaluationRef) -> tuple[str, ...]:
    task_ids = tuple(sorted(left.task_results))
    if set(task_ids) != set(right.task_results):
        raise QuantPGBHSError("candidate evaluation changed the fixed task panel")
    if left.panel_digest != right.panel_digest:
        raise QuantPGBHSError("candidate evaluation changed the panel identity")
    for task_id in task_ids:
        before = left.task_results[task_id]
        after = right.task_results[task_id]
        if before.type_a.total != after.type_a.total or before.type_b.total != after.type_b.total:
            raise QuantPGBHSError("property-family totals changed across evaluations")
    return task_ids


def official_pareto_select(
    incumbent: EvaluationRef, candidate: EvaluationRef
) -> tuple[bool, str]:
    """Use only official binary task rewards for official promotion."""

    task_ids = _same_panel(incumbent, candidate)
    deltas = {
        task_id: candidate.task_results[task_id].official_reward
        - incumbent.task_results[task_id].official_reward
        for task_id in task_ids
    }
    regressed = [task_id for task_id, delta in deltas.items() if delta < 0]
    if regressed:
        return False, "official task regression: " + ", ".join(regressed)
    if not any(delta > 0 for delta in deltas.values()):
        return False, "official binary vector did not strictly improve"
    return True, "official binary vector Pareto-dominated the incumbent"


def diagnostic_search_parent_select(
    parent: EvaluationRef,
    candidate: EvaluationRef,
    prediction: PropertyPrediction,
) -> tuple[bool, bool, int, str]:
    """Select a diagnostic parent without relabeling it an official gain."""

    task_ids = _same_panel(parent, candidate)
    if prediction.task_id not in task_ids:
        raise QuantPGBHSError("prediction task is outside the candidate panel")
    official_regressions = [
        task_id
        for task_id in task_ids
        if candidate.task_results[task_id].official_reward
        < parent.task_results[task_id].official_reward
    ]
    if official_regressions:
        return False, False, 0, "official regression blocks diagnostic parent"
    for task_id in task_ids:
        before = parent.task_results[task_id]
        after = candidate.task_results[task_id]
        for family_name in ("type_a", "type_b"):
            left = getattr(before, family_name)
            right = getattr(after, family_name)
            if right.errors > left.errors or right.skipped > left.skipped:
                return False, False, 0, "errors or skips increased"
    before_family = getattr(parent.task_results[prediction.task_id], prediction.family)
    after_family = getattr(candidate.task_results[prediction.task_id], prediction.family)
    delta = after_family.passed - before_family.passed
    protected_regressions = [
        task_id
        for task_id in prediction.protected_task_ids
        if any(
            getattr(candidate.task_results[task_id], family).passed
            < getattr(parent.task_results[task_id], family).passed
            for family in ("type_a", "type_b")
        )
    ]
    if protected_regressions:
        return False, delta >= prediction.minimum_passed_delta, delta, (
            "protected property-family regression"
        )
    consistent = delta >= prediction.minimum_passed_delta
    if not consistent:
        return False, False, delta, "predicted property-family gain was not observed"
    return True, True, delta, "diagnostic prediction passed without official regression"


@dataclass(frozen=True)
class ArchiveEntry:
    worker_digest: str
    evaluation: EvaluationRef
    official_successes: int
    predicted_family_gain: int


@dataclass(frozen=True)
class QuantIterationRecord:
    iteration: int
    parent_worker_digest: str
    parent_evaluation: EvaluationRef
    evidence_digest: str
    decision: QuantDecisionRecord
    candidate_worker_digest: str | None
    admission: CandidateAdmissionSummary | None
    candidate_evaluation: EvaluationRef | None
    selection: SelectionResult | None
    rollback_reason: str | None
    official_incumbent_after: str
    search_parent_after: str


@dataclass(frozen=True)
class QuantPGBHSState:
    run_id: str
    task_ids: tuple[str, ...]
    h0_worker_digest: str
    h0_evaluation: EvaluationRef
    official_incumbent_worker_digest: str
    official_incumbent_evaluation: EvaluationRef
    search_parent_worker_digest: str
    search_parent_evaluation: EvaluationRef
    archive: tuple[ArchiveEntry, ...] = ()
    iterations: tuple[QuantIterationRecord, ...] = ()
    n_iters: int = 5

    def __post_init__(self) -> None:
        if _SAFE_ID.fullmatch(self.run_id) is None or self.n_iters != 5:
            raise QuantPGBHSError("PGBHS core requires one named five-iteration run")
        if len(self.task_ids) != 2 or len(set(self.task_ids)) != 2:
            raise QuantPGBHSError("PGBHS canary requires exactly two tasks")
        if set(self.task_ids) != set(self.h0_evaluation.task_results):
            raise QuantPGBHSError("H0 evaluation differs from the fixed task panel")
        if len(self.archive) > 2 or len(self.iterations) > self.n_iters:
            raise QuantPGBHSError("archive or iteration limit exceeded")

    @property
    def complete(self) -> bool:
        return len(self.iterations) == self.n_iters


def initialize_pgbs_state(
    *, run_id: str, h0_worker_digest: str, h0_evaluation: EvaluationRef
) -> QuantPGBHSState:
    """Initialize H0 once; every later parent reference is an explicit reuse."""

    if _SHA256.fullmatch(h0_worker_digest) is None:
        raise QuantPGBHSError("H0 worker digest must be SHA-256")
    if h0_evaluation.worker_digest != h0_worker_digest:
        raise QuantPGBHSError("H0 worker and evaluation digests differ")
    task_ids = tuple(sorted(h0_evaluation.task_results))
    return QuantPGBHSState(
        run_id=run_id,
        task_ids=task_ids,
        h0_worker_digest=h0_worker_digest,
        h0_evaluation=h0_evaluation,
        official_incumbent_worker_digest=h0_worker_digest,
        official_incumbent_evaluation=h0_evaluation,
        search_parent_worker_digest=h0_worker_digest,
        search_parent_evaluation=h0_evaluation,
    )


def _archive(
    existing: tuple[ArchiveEntry, ...],
    *,
    worker_digest: str,
    evaluation: EvaluationRef,
    family_gain: int,
) -> tuple[ArchiveEntry, ...]:
    entries = [item for item in existing if item.worker_digest != worker_digest]
    entries.append(
        ArchiveEntry(
            worker_digest=worker_digest,
            evaluation=evaluation,
            official_successes=sum(
                result.official_reward == 1.0
                for result in evaluation.task_results.values()
            ),
            predicted_family_gain=family_gain,
        )
    )
    entries.sort(
        key=lambda item: (
            -item.official_successes,
            -item.predicted_family_gain,
            item.worker_digest,
        )
    )
    return tuple(entries[:2])


def record_pgbs_iteration(
    state: QuantPGBHSState,
    *,
    evidence_digest: str,
    decision: QuantDecisionRecord,
    candidate_worker_digest: str | None = None,
    admission: CandidateAdmissionSummary | None = None,
    candidate_evaluation: EvaluationRef | None = None,
) -> QuantPGBHSState:
    """Append one iteration; ABSTAIN is non-terminal until round five."""

    if state.complete:
        raise QuantPGBHSError("five PGBHS iterations are already complete")
    if _SHA256.fullmatch(evidence_digest) is None:
        raise QuantPGBHSError("evidence digest must be SHA-256")
    iteration = len(state.iterations) + 1
    parent_worker = state.search_parent_worker_digest
    parent_evaluation = state.search_parent_evaluation
    official_worker = state.official_incumbent_worker_digest
    official_evaluation = state.official_incumbent_evaluation
    search_worker = parent_worker
    search_evaluation = parent_evaluation
    archive = state.archive
    selection: SelectionResult | None = None
    rollback_reason: str | None = None

    if decision.decision is Decision.ABSTAIN:
        if (
            candidate_worker_digest is not None
            or admission is not None
            or candidate_evaluation is not None
        ):
            raise QuantPGBHSError("ABSTAIN must not carry a candidate")
        rollback_reason = decision.abstain_reason
    else:
        if candidate_worker_digest is None or _SHA256.fullmatch(candidate_worker_digest) is None:
            raise QuantPGBHSError("ACT requires a candidate worker digest")
        if admission is None:
            raise QuantPGBHSError("ACT requires an admission record")
        if not admission.admitted:
            if candidate_evaluation is not None:
                raise QuantPGBHSError("rejected ACT must not be officially evaluated")
            rollback_reason = admission.failure
        else:
            if candidate_evaluation is None:
                raise QuantPGBHSError("admitted ACT requires a complete candidate panel")
            if candidate_evaluation.worker_digest != candidate_worker_digest:
                raise QuantPGBHSError("candidate worker and evaluation digests differ")
            if set(candidate_evaluation.task_results) != set(state.task_ids):
                raise QuantPGBHSError("candidate did not complete the fixed two-task panel")
            assert decision.prediction is not None
            official_promoted, official_reason = official_pareto_select(
                official_evaluation, candidate_evaluation
            )
            search_promoted, consistent, family_delta, search_reason = (
                diagnostic_search_parent_select(
                    parent_evaluation, candidate_evaluation, decision.prediction
                )
            )
            if official_promoted:
                official_worker = candidate_worker_digest
                official_evaluation = candidate_evaluation
            if official_promoted or search_promoted:
                search_worker = candidate_worker_digest
                search_evaluation = candidate_evaluation
                archive = _archive(
                    archive,
                    worker_digest=candidate_worker_digest,
                    evaluation=candidate_evaluation,
                    family_gain=family_delta,
                )
            else:
                rollback_reason = search_reason
            selection = SelectionResult(
                official_promoted=official_promoted,
                search_parent_promoted=official_promoted or search_promoted,
                prediction_consistent=consistent,
                official_reason=official_reason,
                search_reason=search_reason,
                family_passed_delta=family_delta,
            )

    record = QuantIterationRecord(
        iteration=iteration,
        parent_worker_digest=parent_worker,
        parent_evaluation=parent_evaluation.as_reuse(),
        evidence_digest=evidence_digest,
        decision=decision,
        candidate_worker_digest=candidate_worker_digest,
        admission=admission,
        candidate_evaluation=candidate_evaluation,
        selection=selection,
        rollback_reason=rollback_reason,
        official_incumbent_after=official_worker,
        search_parent_after=search_worker,
    )
    return replace(
        state,
        official_incumbent_worker_digest=official_worker,
        official_incumbent_evaluation=official_evaluation,
        search_parent_worker_digest=search_worker,
        search_parent_evaluation=search_evaluation,
        archive=archive,
        iterations=(*state.iterations, record),
    )


def state_payload(state: QuantPGBHSState) -> dict[str, object]:
    """Return a JSON-safe five-round ledger payload."""

    payload = asdict(state)
    payload["schema_version"] = 1
    payload["protocol"] = "quant_property_v1"
    payload["complete"] = state.complete
    return payload


def _progress_from_payload(value: object) -> PropertyFamilyProgress:
    if not isinstance(value, Mapping):
        raise QuantPGBHSError("property-family payload must be an object")
    try:
        return PropertyFamilyProgress(
            total=value["total"],
            passed=value["passed"],
            failed=value["failed"],
            skipped=value["skipped"],
            errors=value["errors"],
        )
    except (KeyError, TypeError) as exc:
        raise QuantPGBHSError("property-family payload schema differs") from exc


def _task_result_from_payload(value: object) -> TaskPanelResult:
    if not isinstance(value, Mapping):
        raise QuantPGBHSError("task-result payload must be an object")
    try:
        return TaskPanelResult(
            task_id=value["task_id"],
            official_reward=value["official_reward"],
            type_a=_progress_from_payload(value["type_a"]),
            type_b=_progress_from_payload(value["type_b"]),
        )
    except (KeyError, TypeError) as exc:
        raise QuantPGBHSError("task-result payload schema differs") from exc


def _evaluation_from_payload(value: object) -> EvaluationRef:
    if not isinstance(value, Mapping):
        raise QuantPGBHSError("evaluation payload must be an object")
    raw_results = value.get("task_results")
    raw_attempts = value.get("attempt_ids")
    if not isinstance(raw_results, Mapping) or not isinstance(raw_attempts, Mapping):
        raise QuantPGBHSError("evaluation task panel schema differs")
    try:
        return EvaluationRef(
            evaluation_id=value["evaluation_id"],
            checkpoint=value["checkpoint"],
            worker_digest=value["worker_digest"],
            panel_digest=value["panel_digest"],
            sampling_identity_digest=value["sampling_identity_digest"],
            attempt_ids={str(key): str(item) for key, item in raw_attempts.items()},
            task_results={
                str(key): _task_result_from_payload(item)
                for key, item in raw_results.items()
            },
            reused_from_evaluation_id=value.get("reused_from_evaluation_id"),
            resampled=value.get("resampled", False),
        )
    except (KeyError, TypeError) as exc:
        raise QuantPGBHSError("evaluation payload schema differs") from exc


def _prediction_from_payload(value: object) -> PropertyPrediction | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise QuantPGBHSError("prediction payload must be an object")
    try:
        return PropertyPrediction(
            task_id=value["task_id"],
            family=value["family"],
            minimum_passed_delta=value["minimum_passed_delta"],
            protected_task_ids=tuple(value.get("protected_task_ids", ())),
        )
    except (KeyError, TypeError) as exc:
        raise QuantPGBHSError("prediction payload schema differs") from exc


def _decision_from_payload(value: object) -> QuantDecisionRecord:
    if not isinstance(value, Mapping):
        raise QuantPGBHSError("decision payload must be an object")
    try:
        return QuantDecisionRecord(
            decision=Decision(value["decision"]),
            failure_class=FailureClass(value["failure_class"]),
            hypotheses=tuple(dict(item) for item in value["hypotheses"]),
            selected_hypothesis_id=value.get("selected_hypothesis_id"),
            evidence_refs=tuple(value.get("evidence_refs", ())),
            public_clause_ref=value.get("public_clause_ref"),
            artifact_fact_ref=value.get("artifact_fact_ref"),
            trace_fact_ref=value.get("trace_fact_ref"),
            evidence_basis=(
                EvidenceBasis(value["evidence_basis"])
                if value.get("evidence_basis") is not None
                else None
            ),
            component=value.get("component"),
            mutation_operator=(
                MutationOperator(value["mutation_operator"])
                if value.get("mutation_operator") is not None
                else None
            ),
            prediction=_prediction_from_payload(value.get("prediction")),
            risk_tasks=tuple(value.get("risk_tasks", ())),
            counterevidence=value["counterevidence"],
            uncertainty=value["uncertainty"],
            abstain_reason=value.get("abstain_reason"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise QuantPGBHSError("decision payload schema differs") from exc


def load_decision_payload(value: Mapping[str, object]) -> QuantDecisionRecord:
    """Load the canonical JSON form emitted by ``state_payload``/``asdict``."""

    return _decision_from_payload(value)


def _admission_from_payload(value: object) -> CandidateAdmissionSummary | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise QuantPGBHSError("admission payload must be an object")
    try:
        return CandidateAdmissionSummary(
            admitted=value["admitted"],
            nonempty_diff=value["nonempty_diff"],
            declared_roles_match_actual=value["declared_roles_match_actual"],
            failure=value.get("failure"),
        )
    except (KeyError, TypeError) as exc:
        raise QuantPGBHSError("admission payload schema differs") from exc


def _selection_from_payload(value: object) -> SelectionResult | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise QuantPGBHSError("selection payload must be an object")
    try:
        return SelectionResult(
            official_promoted=value["official_promoted"],
            search_parent_promoted=value["search_parent_promoted"],
            prediction_consistent=value["prediction_consistent"],
            official_reason=value["official_reason"],
            search_reason=value["search_reason"],
            family_passed_delta=value["family_passed_delta"],
        )
    except (KeyError, TypeError) as exc:
        raise QuantPGBHSError("selection payload schema differs") from exc


def load_state_payload(value: Mapping[str, object]) -> QuantPGBHSState:
    """Reconstruct and fully validate a JSON-round-tripped resume ledger."""

    if not isinstance(value, Mapping):
        raise QuantPGBHSError("state payload must be an object")
    if value.get("schema_version") != 1 or value.get("protocol") != "quant_property_v1":
        raise QuantPGBHSError("state payload identity differs")
    try:
        archive = tuple(
            ArchiveEntry(
                worker_digest=item["worker_digest"],
                evaluation=_evaluation_from_payload(item["evaluation"]),
                official_successes=item["official_successes"],
                predicted_family_gain=item["predicted_family_gain"],
            )
            for item in value.get("archive", ())
        )
        iterations = tuple(
            QuantIterationRecord(
                iteration=item["iteration"],
                parent_worker_digest=item["parent_worker_digest"],
                parent_evaluation=_evaluation_from_payload(
                    item["parent_evaluation"]
                ),
                evidence_digest=item["evidence_digest"],
                decision=_decision_from_payload(item["decision"]),
                candidate_worker_digest=item.get("candidate_worker_digest"),
                admission=_admission_from_payload(item.get("admission")),
                candidate_evaluation=(
                    _evaluation_from_payload(item["candidate_evaluation"])
                    if item.get("candidate_evaluation") is not None
                    else None
                ),
                selection=_selection_from_payload(item.get("selection")),
                rollback_reason=item.get("rollback_reason"),
                official_incumbent_after=item["official_incumbent_after"],
                search_parent_after=item["search_parent_after"],
            )
            for item in value.get("iterations", ())
        )
        state = QuantPGBHSState(
            run_id=value["run_id"],
            task_ids=tuple(value["task_ids"]),
            h0_worker_digest=value["h0_worker_digest"],
            h0_evaluation=_evaluation_from_payload(value["h0_evaluation"]),
            official_incumbent_worker_digest=value[
                "official_incumbent_worker_digest"
            ],
            official_incumbent_evaluation=_evaluation_from_payload(
                value["official_incumbent_evaluation"]
            ),
            search_parent_worker_digest=value["search_parent_worker_digest"],
            search_parent_evaluation=_evaluation_from_payload(
                value["search_parent_evaluation"]
            ),
            archive=archive,
            iterations=iterations,
            n_iters=value["n_iters"],
        )
    except (KeyError, TypeError) as exc:
        raise QuantPGBHSError("state payload schema differs") from exc
    if value.get("complete") is not state.complete:
        raise QuantPGBHSError("state completion marker differs")
    if json.dumps(
        state_payload(state), sort_keys=True, separators=(",", ":")
    ) != json.dumps(dict(value), sort_keys=True, separators=(",", ":")):
        raise QuantPGBHSError("state payload is non-canonical or inconsistent")
    return state


__all__ = [
    "ArchiveEntry",
    "CandidateAdmissionSummary",
    "Decision",
    "EvaluationRef",
    "EvidenceBasis",
    "FailureClass",
    "MutationOperator",
    "PropertyPrediction",
    "QuantDecisionRecord",
    "QuantIterationRecord",
    "QuantPGBHSError",
    "QuantPGBHSState",
    "SelectionResult",
    "TaskPanelResult",
    "diagnostic_search_parent_select",
    "initialize_pgbs_state",
    "load_decision_payload",
    "load_state_payload",
    "official_pareto_select",
    "record_pgbs_iteration",
    "state_payload",
    "validate_quant_decision",
]
