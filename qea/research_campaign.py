"""Cumulative, whole-harness research campaign controller.

The controller deliberately owns only campaign semantics: exact stage identity,
bounded comparison windows, whole-package selection, independent research-memory
retention, accounting, and resumable state.  Benchmark execution is supplied by
an adapter with a small fixed contract.  The concrete QuantCodeEval adapter below
uses the existing Worker-panel, verifier-only replay, and behavior-revision
primitives; it does not inspect trusted evaluator contents.

Scores remain namespaced by benchmark.  A round can select a research parent only
on its explicitly declared development window.  It is not evidence that the
candidate improved on any task outside that window.  The terminal freeze evaluates
one unchanged whole harness on every development and evaluation task declared for
each benchmark.
"""

from __future__ import annotations

import codecs
import json
import os
import shutil
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Protocol

from .quantcodeeval_behavior_revision import run_quantcodeeval_behavior_revision
from .quantcodeeval_panel_observation import run_quantcodeeval_panel_observation
from .quantcodeeval_v2_evidence import EARLY_INTERVENTION_FULL_HARNESS_PROFILE
from .research_operation_memory import (
    ResearchOperationMemoryError,
    load_research_operation_memory,
)


PROTOCOL = "research-campaign-v1"
STATE_FILE = "CAMPAIGN-STATE.json"
EPISODE_FILE = "EPISODE-EVIDENCE.json"
EVALUATION_FILE = "OFFICIAL-EVALUATION.json"
EVIDENCE_RECORD_PROTOCOL = "research-campaign-evidence-record-v1"
_QCE_REPLAY_FAILURE_FILE = "REPLAY-FAILURE.json"
_QCE_REPLAY_FAILURE_PROTOCOL = "quantcodeeval-verifier-only-replay-failure-v1"
_QUALIFIED_REVISION_EMPTY_RESPONSE = "empty_model_response_after_fallback"
_QUALIFIED_REVISION_TERMINAL_VALIDATION_EXHAUSTION = (
    "terminal action model-call budget exhausted"
)
_QCE_PARTIAL_EVALUATOR_PHASES = frozenset(
    {
        "quantcodeeval.network",
        "quantcodeeval.network.cleanup",
        "quantcodeeval.strategy.create",
        "quantcodeeval.strategy.service",
        "quantcodeeval.strategy.start",
        "quantcodeeval.strategy.upload",
        "strategy.cleanup",
        "strategy.lifecycle",
        "verifier.cleanup",
        "verifier.command",
        "verifier.coordinator",
        "verifier.create",
        "verifier.evidence",
        "verifier.lifecycle",
        "verifier.output",
        "verifier.score",
        "verifier.setup",
        "verifier.start",
        "verifier.upload",
    }
)
_EVIDENCE_MEMBER_ROLES = (
    "attempt_identity",
    "artifact_root",
    "artifact_manifest",
    "public_data",
    "worker_trace",
    "worker_final",
    "process_summary",
)


class ResearchCampaignError(ValueError):
    """A plan, retained state, or backend result violates campaign semantics."""


@dataclass(frozen=True)
class HarnessRef:
    harness_id: str
    artifact_uri: str
    revision_uri: str | None = None
    worker_role: str = "candidate"


@dataclass(frozen=True)
class MemoryRef:
    artifact_uri: str
    source_stage_id: str


@dataclass(frozen=True)
class EpisodeRequest:
    campaign_id: str
    stage_id: str
    backend_id: str
    harness: HarnessRef
    task_ids: tuple[str, ...]
    purpose: str
    frozen: bool = False


@dataclass(frozen=True)
class EpisodeEvidence:
    stage_id: str
    backend_id: str
    harness: HarnessRef
    task_ids: tuple[str, ...]
    condition_id: str
    status: str
    cells: Mapping[str, Mapping[str, object]]
    accounting: Mapping[str, object]
    result_uri: str
    failure: Mapping[str, object] | None = None


@dataclass(frozen=True)
class EvaluationRequest:
    campaign_id: str
    stage_id: str
    backend_id: str
    episode: EpisodeEvidence


@dataclass(frozen=True)
class TaskMetric:
    task_id: str
    binary_reward: int
    passed: int
    failed: int
    errors: int
    skipped: int
    total: int
    contract_adjusted: bool
    zero_model_requests: bool
    result_uri: str
    families: Mapping[str, Mapping[str, int]]


@dataclass(frozen=True)
class OfficialEvaluation:
    stage_id: str
    backend_id: str
    harness: HarnessRef
    episode_stage_id: str
    task_ids: tuple[str, ...]
    condition_id: str
    status: str
    metrics: Mapping[str, Mapping[str, object]]
    selection_policy: str
    selection_key: tuple[tuple[int, int], ...]
    selection_summary: Mapping[str, object]
    accounting: Mapping[str, object]
    result_uri: str
    failure: Mapping[str, object] | None = None


@dataclass(frozen=True)
class RevisionRequest:
    campaign_id: str
    stage_id: str
    backend_id: str
    parent_harness: HarnessRef
    parent_episode: EpisodeEvidence
    parent_evaluation: OfficialEvaluation
    active_task_id: str
    research_memory: MemoryRef | None
    options: Mapping[str, object]
    evidence_by_backend: Mapping[str, EpisodeEvidence]
    evaluations_by_backend: Mapping[str, OfficialEvaluation]
    investigate_partial_windows: bool = False
    related_completed_round: RelatedCompletedRound | None = None
    seed_related_completed_rounds: tuple[RelatedCompletedRound, ...] = ()


@dataclass(frozen=True)
class RelatedCompletedRound:
    round_id: str
    parent_harness: HarnessRef
    candidate_harness: HarnessRef
    revision_result_uri: str
    parent_evidence_by_backend: Mapping[str, EpisodeEvidence]
    parent_evaluations_by_backend: Mapping[str, OfficialEvaluation]
    evidence_by_backend: Mapping[str, EpisodeEvidence]
    evaluations_by_backend: Mapping[str, OfficialEvaluation]


@dataclass(frozen=True)
class RevisionOutcome:
    stage_id: str
    backend_id: str
    parent_harness: HarnessRef
    status: str
    decision: str | None
    candidate_harness: HarnessRef | None
    retained_memory: MemoryRef | None
    accounting: Mapping[str, object]
    result_uri: str
    component_checks: tuple[Mapping[str, object], ...] = ()
    public_probe_refs: tuple[str, ...] = ()
    failure: Mapping[str, object] | None = None


class CampaignBackend(Protocol):
    """Fixed benchmark adapter boundary used by the campaign controller."""

    backend_id: str

    def run_episode(self, request: EpisodeRequest) -> EpisodeEvidence: ...

    def run_evaluation(self, request: EvaluationRequest) -> OfficialEvaluation: ...

    def active_revision_source_available(
        self,
        *,
        episode: EpisodeEvidence,
        evaluation: OfficialEvaluation,
        task_id: str,
        parent_harness: HarnessRef,
    ) -> bool: ...

    def run_revision(self, request: RevisionRequest) -> RevisionOutcome: ...


def qualified_revision_failure_selection(
    outcome: RevisionOutcome | Mapping[str, object],
    *,
    retained_memory_valid: bool,
) -> dict[str, object] | None:
    """Return a narrow non-promotion disposition for a retained Evolver failure.

    This helper is intentionally pure so an explicitly registered, zero-model
    recovery can apply the same decision to an already retained ``RevisionOutcome``.
    The caller must first validate the referenced research-memory snapshot with
    :func:`load_research_operation_memory`; this function never treats the mere
    presence of a path as proof that R is usable.
    """

    if isinstance(outcome, RevisionOutcome):
        status = outcome.status
        decision = outcome.decision
        candidate = outcome.candidate_harness
        retained_memory: object = outcome.retained_memory
        stage_id = outcome.stage_id
        failure: object = outcome.failure
    elif isinstance(outcome, Mapping):
        status = outcome.get("status")
        decision = outcome.get("decision")
        candidate = outcome.get("candidate_harness")
        retained_memory = outcome.get("retained_memory")
        stage_id = outcome.get("stage_id")
        failure = outcome.get("failure")
    else:
        return None

    if (
        retained_memory_valid is not True
        or status != "failed"
        or decision is not None
        or candidate is not None
        or not isinstance(stage_id, str)
        or not stage_id
        or retained_memory is None
        or not isinstance(failure, Mapping)
    ):
        return None

    if isinstance(retained_memory, MemoryRef):
        memory_source_stage = retained_memory.source_stage_id
    elif isinstance(retained_memory, Mapping):
        memory_source_stage = retained_memory.get("source_stage_id")
    else:
        return None
    if memory_source_stage != stage_id:
        return None

    error_text = " ".join(
        value
        for value in (failure.get("message"), failure.get("detail"))
        if isinstance(value, str)
    )
    if not (
        failure.get("exception_type") == "SandboxInfrastructureError"
        and failure.get("phase") == "evolver.command"
        and failure.get("stage") == "evolver_proposal"
    ):
        return None

    if _QUALIFIED_REVISION_EMPTY_RESPONSE in error_text:
        reason = "qualified_revision_provider_empty_response"
    elif (
        _QUALIFIED_REVISION_TERMINAL_VALIDATION_EXHAUSTION in error_text
        and "TerminalReserveError" in error_text
    ):
        # This is not a generic budget/error escape hatch.  It is the exact
        # retained terminal-reserve shape in which the Evolver exhausted its
        # final decision call without producing a decision or candidate.  The
        # guards above still require a same-stage, loader-validated R snapshot.
        reason = "qualified_revision_terminal_validation_exhaustion"
    else:
        return None

    return {
        "selected": "parent",
        "reason": reason,
        "round_status": "interrupted",
        "comparison_run": False,
        "candidate_observed": False,
        "candidate_promotable": False,
        "candidate_evaluation_run": False,
        "revision_failed": True,
        "revision_failure_retained": True,
        "automatic_retry": False,
        "research_parent_unchanged": True,
        "research_memory_retention_independent": True,
        "claim_outside_window": False,
    }


def _json_copy(value: object, *, label: str) -> object:
    try:
        return json.loads(
            json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
        )
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ResearchCampaignError(f"{label} must contain finite JSON values") from exc


def _read_object(path: Path, *, label: str) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise ResearchCampaignError(f"{label} is missing or unsafe: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ResearchCampaignError(f"{label} is invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise ResearchCampaignError(f"{label} must be a JSON object")
    return value


def _atomic_json(path: Path, value: Mapping[str, object]) -> None:
    payload = json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".partial")
    if temporary.exists() or temporary.is_symlink():
        raise ResearchCampaignError(f"stale partial state exists: {temporary}")
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, path)


def _write_or_reuse(path: Path, value: Mapping[str, object], *, label: str) -> None:
    normalized = _json_copy(value, label=label)
    assert isinstance(normalized, dict)
    if path.exists() or path.is_symlink():
        if _read_object(path, label=label) != normalized:
            raise ResearchCampaignError(f"retained {label} differs: {path}")
        return
    _atomic_json(path, normalized)


def _write_text_or_reuse(path: Path, value: str, *, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file():
            raise ResearchCampaignError(f"retained {label} is unsafe: {path}")
        if path.read_text(encoding="utf-8") != value:
            raise ResearchCampaignError(f"retained {label} differs: {path}")
        return
    temporary = path.with_name(path.name + ".partial")
    if temporary.exists() or temporary.is_symlink():
        raise ResearchCampaignError(f"stale {label} partial exists: {temporary}")
    temporary.write_text(value, encoding="utf-8")
    os.replace(temporary, path)


def _text(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ResearchCampaignError(f"{label} is required")
    return value.strip()


def _task_ids(
    value: object, *, label: str, allow_empty: bool = False
) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ResearchCampaignError(f"{label} must be a list")
    tasks = tuple(_text(item, label=f"{label} task") for item in value)
    if (not tasks and not allow_empty) or len(tasks) != len(set(tasks)):
        raise ResearchCampaignError(f"{label} must contain distinct tasks")
    return tasks


def _harness(value: object, *, label: str) -> HarnessRef:
    if not isinstance(value, Mapping):
        raise ResearchCampaignError(f"{label} must be an object")
    worker_role = value.get("worker_role", "candidate")
    if worker_role not in {"initial", "candidate"}:
        raise ResearchCampaignError(f"{label} worker_role is invalid")
    revision = value.get("revision_uri")
    if revision is not None:
        revision = _text(revision, label=f"{label} revision_uri")
    return HarnessRef(
        harness_id=_text(value.get("harness_id"), label=f"{label} harness_id"),
        artifact_uri=_text(
            value.get("artifact_uri"), label=f"{label} artifact_uri"
        ),
        revision_uri=revision,
        worker_role=str(worker_role),
    )


def _memory(value: object, *, label: str) -> MemoryRef | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ResearchCampaignError(f"{label} must be an object or null")
    return MemoryRef(
        artifact_uri=_text(
            value.get("artifact_uri"), label=f"{label} artifact_uri"
        ),
        source_stage_id=_text(
            value.get("source_stage_id"), label=f"{label} source_stage_id"
        ),
    )


def validate_campaign_plan(value: object) -> dict[str, object]:
    """Validate and normalize an immutable campaign plan."""

    if not isinstance(value, Mapping) or value.get("schema_version") != 1:
        raise ResearchCampaignError("campaign plan schema_version must be 1")
    campaign_id = _text(value.get("campaign_id"), label="campaign_id")
    investigate_partial_windows = value.get(
        "investigate_partial_windows", False
    )
    if type(investigate_partial_windows) is not bool:
        raise ResearchCampaignError(
            "investigate_partial_windows must be a boolean"
        )
    observe_partial_candidates = value.get(
        "observe_partial_candidates", False
    )
    if type(observe_partial_candidates) is not bool:
        raise ResearchCampaignError(
            "observe_partial_candidates must be a boolean"
        )
    if observe_partial_candidates and not investigate_partial_windows:
        raise ResearchCampaignError(
            "observe_partial_candidates requires investigate_partial_windows"
        )
    return_candidate_feedback = value.get("return_candidate_feedback", False)
    if type(return_candidate_feedback) is not bool:
        raise ResearchCampaignError(
            "return_candidate_feedback must be a boolean"
        )
    raw_benchmarks = value.get("benchmarks")
    if not isinstance(raw_benchmarks, Mapping) or not raw_benchmarks:
        raise ResearchCampaignError("campaign plan requires benchmark definitions")
    benchmarks: dict[str, object] = {}
    for raw_backend_id, raw_definition in raw_benchmarks.items():
        backend_id = _text(raw_backend_id, label="benchmark backend ID")
        if not isinstance(raw_definition, Mapping):
            raise ResearchCampaignError(f"benchmark {backend_id} must be an object")
        development = _task_ids(
            raw_definition.get("development_task_ids"),
            label=f"{backend_id} development_task_ids",
        )
        evaluation = _task_ids(
            raw_definition.get("evaluation_task_ids"),
            label=f"{backend_id} evaluation_task_ids",
            allow_empty=True,
        )
        if set(development) & set(evaluation):
            raise ResearchCampaignError(
                f"{backend_id} development and evaluation tasks overlap"
            )
        benchmarks[backend_id] = {
            "development_task_ids": list(development),
            "evaluation_task_ids": list(evaluation),
        }

    raw_baselines = value.get("baselines")
    if raw_baselines is None and isinstance(value.get("baseline"), Mapping):
        raw_baselines = [value["baseline"]]
    if not isinstance(raw_baselines, list) or len(raw_baselines) != len(benchmarks):
        raise ResearchCampaignError("baselines must contain one stage per benchmark")
    baselines: list[dict[str, object]] = []
    seen_baseline_backends: set[str] = set()
    baseline_harness_ref: HarnessRef | None = None
    all_stage_ids: set[str] = set()
    for raw_baseline in raw_baselines:
        if not isinstance(raw_baseline, Mapping):
            raise ResearchCampaignError("baseline stage must be an object")
        backend_id = _text(
            raw_baseline.get("backend_id"), label="baseline backend_id"
        )
        if backend_id not in benchmarks or backend_id in seen_baseline_backends:
            raise ResearchCampaignError(
                "baseline backend is missing, unknown, or repeated"
            )
        seen_baseline_backends.add(backend_id)
        tasks = _task_ids(
            raw_baseline.get("task_ids"), label=f"{backend_id} baseline task_ids"
        )
        expected = tuple(
            benchmarks[backend_id]["development_task_ids"]
            + benchmarks[backend_id]["evaluation_task_ids"]
        )
        if set(tasks) != set(expected) or len(tasks) != len(expected):
            raise ResearchCampaignError(
                f"{backend_id} baseline must cover its complete declared task set"
            )
        harness = _harness(
            raw_baseline.get("harness"), label=f"{backend_id} baseline harness"
        )
        if harness.worker_role != "initial":
            raise ResearchCampaignError("baseline harness must use the initial role")
        if baseline_harness_ref is None:
            baseline_harness_ref = harness
        elif harness != baseline_harness_ref:
            raise ResearchCampaignError(
                "all benchmark baselines must use the same whole harness"
            )
        episode_id = _text(
            raw_baseline.get("episode_stage_id"),
            label=f"{backend_id} baseline episode_stage_id",
        )
        evaluation_id = _text(
            raw_baseline.get("evaluation_stage_id"),
            label=f"{backend_id} baseline evaluation_stage_id",
        )
        if all_stage_ids & {episode_id, evaluation_id}:
            raise ResearchCampaignError("baseline stage IDs must be globally unique")
        all_stage_ids.update((episode_id, evaluation_id))
        baselines.append(
            {
                "backend_id": backend_id,
                "harness": asdict(harness),
                "task_ids": list(tasks),
                "episode_stage_id": episode_id,
                "evaluation_stage_id": evaluation_id,
            }
        )
    if seen_baseline_backends != set(benchmarks):
        raise ResearchCampaignError("baselines do not cover every benchmark")

    parent = _harness(
        value.get("initial_research_parent"), label="initial_research_parent"
    )
    if parent.worker_role != "candidate":
        raise ResearchCampaignError(
            "initial research parent must use the candidate role"
        )
    memory = _memory(value.get("initial_research_memory"), label="initial memory")
    raw_rounds = value.get("rounds")
    if not isinstance(raw_rounds, list) or not raw_rounds:
        raise ResearchCampaignError("campaign plan requires at least one round")
    rounds: list[dict[str, object]] = []
    round_ids: set[str] = set()
    for index, raw_round in enumerate(raw_rounds, start=1):
        if not isinstance(raw_round, Mapping):
            raise ResearchCampaignError(f"round {index} must be an object")
        round_id = _text(raw_round.get("round_id"), label=f"round {index} ID")
        if round_id in round_ids:
            raise ResearchCampaignError(f"duplicate round ID: {round_id}")
        round_ids.add(round_id)
        raw_windows = raw_round.get("comparison_windows")
        if raw_windows is None and isinstance(raw_round.get("backend_id"), str):
            raw_windows = {
                raw_round["backend_id"]: raw_round.get("comparison_task_ids")
            }
        if not isinstance(raw_windows, Mapping) or not raw_windows:
            raise ResearchCampaignError(
                f"round {round_id} requires nonempty comparison_windows"
            )
        windows: dict[str, list[str]] = {}
        for raw_backend_id, raw_tasks in raw_windows.items():
            backend_id = _text(
                raw_backend_id, label=f"round {round_id} window backend"
            )
            if backend_id not in benchmarks:
                raise ResearchCampaignError(
                    f"round {round_id} window backend is undeclared"
                )
            window = _task_ids(
                raw_tasks,
                label=f"round {round_id} {backend_id} comparison window",
            )
            development = set(benchmarks[backend_id]["development_task_ids"])
            if not set(window) <= development:
                raise ResearchCampaignError(
                    f"round {round_id} {backend_id} window is not development-only"
                )
            windows[backend_id] = list(window)
        active_backend = _text(
            raw_round.get("active_backend_id", raw_round.get("backend_id")),
            label=f"round {round_id} active_backend_id",
        )
        if active_backend not in windows:
            raise ResearchCampaignError(
                f"round {round_id} active backend has no comparison window"
            )
        active_task = _text(
            raw_round.get("active_task_id"),
            label=f"round {round_id} active_task_id",
        )
        if active_task not in windows[active_backend]:
            raise ResearchCampaignError(
                f"round {round_id} active task is outside its comparison window"
            )
        raw_stage_ids = raw_round.get("stage_ids")
        if not isinstance(raw_stage_ids, Mapping):
            raise ResearchCampaignError(f"round {round_id} stage_ids must be an object")
        legacy_keys = {
            "parent_episode",
            "parent_evaluation",
            "revision",
            "candidate_episode",
            "candidate_evaluation",
        }
        if set(raw_stage_ids) == legacy_keys and len(windows) == 1:
            only_backend = next(iter(windows))
            stage_ids = {
                "parent_episodes": {
                    only_backend: _text(
                        raw_stage_ids["parent_episode"],
                        label=f"round {round_id} parent_episode",
                    )
                },
                "parent_evaluations": {
                    only_backend: _text(
                        raw_stage_ids["parent_evaluation"],
                        label=f"round {round_id} parent_evaluation",
                    )
                },
                "revision": _text(
                    raw_stage_ids["revision"], label=f"round {round_id} revision"
                ),
                "candidate_episodes": {
                    only_backend: _text(
                        raw_stage_ids["candidate_episode"],
                        label=f"round {round_id} candidate_episode",
                    )
                },
                "candidate_evaluations": {
                    only_backend: _text(
                        raw_stage_ids["candidate_evaluation"],
                        label=f"round {round_id} candidate_evaluation",
                    )
                },
            }
        else:
            required_stage_keys = {
                "parent_episodes",
                "parent_evaluations",
                "revision",
                "candidate_episodes",
                "candidate_evaluations",
            }
            if set(raw_stage_ids) != required_stage_keys:
                raise ResearchCampaignError(
                    f"round {round_id} stage_ids fields differ"
                )
            stage_ids = {
                "revision": _text(
                    raw_stage_ids["revision"], label=f"round {round_id} revision"
                )
            }
            for key in (
                "parent_episodes",
                "parent_evaluations",
                "candidate_episodes",
                "candidate_evaluations",
            ):
                raw_mapping = raw_stage_ids[key]
                if not isinstance(raw_mapping, Mapping) or set(raw_mapping) != set(
                    windows
                ):
                    raise ResearchCampaignError(
                        f"round {round_id} {key} must match comparison backends"
                    )
                stage_ids[key] = {
                    backend_id: _text(
                        raw_mapping[backend_id],
                        label=f"round {round_id} {key} {backend_id}",
                    )
                    for backend_id in windows
                }
        flat_stage_ids = {
            str(stage_ids["revision"]),
            *(
                stage_id
                for key in (
                    "parent_episodes",
                    "parent_evaluations",
                    "candidate_episodes",
                    "candidate_evaluations",
                )
                for stage_id in stage_ids[key].values()
            ),
        }
        expected_stage_count = 1 + 4 * len(windows)
        if len(flat_stage_ids) != expected_stage_count:
            raise ResearchCampaignError(
                f"round {round_id} stage IDs must be distinct"
            )
        overlap = all_stage_ids & flat_stage_ids
        if overlap:
            raise ResearchCampaignError(
                "stage IDs must be globally unique: " + ", ".join(sorted(overlap))
            )
        all_stage_ids.update(flat_stage_ids)
        options = raw_round.get("revision_options", {})
        if not isinstance(options, Mapping):
            raise ResearchCampaignError(
                f"round {round_id} revision_options must be an object"
            )
        iteration = options.get("iteration")
        if type(iteration) is not int or iteration < 1:
            raise ResearchCampaignError(
                f"round {round_id} revision_options.iteration must be positive"
            )
        rounds.append(
            {
                "round_id": round_id,
                "active_backend_id": active_backend,
                "active_task_id": active_task,
                "comparison_windows": windows,
                "stage_ids": stage_ids,
                "revision_options": _json_copy(
                    dict(options), label=f"round {round_id} revision_options"
                ),
            }
        )

    raw_freeze = value.get("freeze")
    if not isinstance(raw_freeze, list) or len(raw_freeze) != len(benchmarks):
        raise ResearchCampaignError("freeze must contain one stage per benchmark")
    freezes: list[dict[str, object]] = []
    seen_freeze_backends: set[str] = set()
    for raw_stage in raw_freeze:
        if not isinstance(raw_stage, Mapping):
            raise ResearchCampaignError("freeze stage must be an object")
        backend_id = _text(
            raw_stage.get("backend_id"), label="freeze backend_id"
        )
        if backend_id not in benchmarks or backend_id in seen_freeze_backends:
            raise ResearchCampaignError("freeze backend is missing, unknown, or repeated")
        seen_freeze_backends.add(backend_id)
        tasks = _task_ids(raw_stage.get("task_ids"), label=f"{backend_id} freeze tasks")
        expected = tuple(
            benchmarks[backend_id]["development_task_ids"]
            + benchmarks[backend_id]["evaluation_task_ids"]
        )
        if set(tasks) != set(expected) or len(tasks) != len(expected):
            raise ResearchCampaignError(
                f"{backend_id} freeze must cover its complete declared task set"
            )
        episode_id = _text(
            raw_stage.get("episode_stage_id"),
            label=f"{backend_id} freeze episode_stage_id",
        )
        evaluation_id = _text(
            raw_stage.get("evaluation_stage_id"),
            label=f"{backend_id} freeze evaluation_stage_id",
        )
        overlap = all_stage_ids & {episode_id, evaluation_id}
        if overlap:
            raise ResearchCampaignError(
                "stage IDs must be globally unique: " + ", ".join(sorted(overlap))
            )
        all_stage_ids.update((episode_id, evaluation_id))
        freezes.append(
            {
                "backend_id": backend_id,
                "task_ids": list(tasks),
                "episode_stage_id": episode_id,
                "evaluation_stage_id": evaluation_id,
            }
        )
    if seen_freeze_backends != set(benchmarks):
        raise ResearchCampaignError("freeze stages do not cover every benchmark")

    normalized = {
        "schema_version": 1,
        "campaign_id": campaign_id,
        "benchmarks": benchmarks,
        "baselines": baselines,
        "initial_research_parent": asdict(parent),
        "initial_research_memory": None if memory is None else asdict(memory),
        "rounds": rounds,
        "freeze": freezes,
    }
    # Preserve byte-for-byte normalized-plan compatibility for registrations
    # created before this opt-in existed.  Absence means false; an explicitly
    # supplied value remains part of a new immutable plan identity.
    if "investigate_partial_windows" in value:
        normalized["investigate_partial_windows"] = investigate_partial_windows
    if "observe_partial_candidates" in value:
        normalized["observe_partial_candidates"] = observe_partial_candidates
    if "return_candidate_feedback" in value:
        normalized["return_candidate_feedback"] = return_candidate_feedback
    copied = _json_copy(normalized, label="campaign plan")
    assert isinstance(copied, dict)
    return copied


def initialize_campaign(*, plan: Mapping[str, object], state_path: str | Path) -> dict[str, object]:
    """Create or verify the immutable campaign state without executing a stage."""

    normalized_plan = validate_campaign_plan(plan)
    path = Path(state_path).expanduser().resolve()
    if path.exists() or path.is_symlink():
        retained = _read_object(path, label="campaign state")
        if retained.get("protocol") != PROTOCOL or retained.get("plan") != normalized_plan:
            raise ResearchCampaignError("retained campaign state belongs to another plan")
        return retained
    state: dict[str, object] = {
        "schema_version": 1,
        "protocol": PROTOCOL,
        "campaign_id": normalized_plan["campaign_id"],
        "plan": normalized_plan,
        "status": "running",
        "phase": "baseline_episode",
        "research_parent": normalized_plan["initial_research_parent"],
        "research_memory": normalized_plan["initial_research_memory"],
        "baseline_index": 0,
        "baseline_results": [],
        "round_index": 0,
        "current_round": None,
        "completed_rounds": [],
        "freeze_index": 0,
        "freeze_results": [],
        "terminal_comparison": None,
        "stage_ledger": [],
        "failure_ledger": [],
        "accounting": _accounting_totals([]),
    }
    if normalized_plan.get("return_candidate_feedback") is True:
        state["latest_candidate_observation_round_index"] = None
    _atomic_json(path, state)
    return state


def _episode(value: Mapping[str, object]) -> EpisodeEvidence:
    cells = value.get("cells")
    if not isinstance(cells, Mapping):
        raise ResearchCampaignError("episode cells must be an object")
    return EpisodeEvidence(
        stage_id=_text(value.get("stage_id"), label="episode stage_id"),
        backend_id=_text(value.get("backend_id"), label="episode backend_id"),
        harness=_harness(value.get("harness"), label="episode harness"),
        task_ids=_task_ids(value.get("task_ids"), label="episode task_ids"),
        condition_id=_text(value.get("condition_id"), label="episode condition_id"),
        status=_text(value.get("status"), label="episode status"),
        cells=dict(cells),
        accounting=dict(value.get("accounting", {})),
        result_uri=_text(value.get("result_uri"), label="episode result_uri"),
        failure=value.get("failure") if isinstance(value.get("failure"), Mapping) else None,
    )


def _evaluation(value: Mapping[str, object]) -> OfficialEvaluation:
    raw_metrics = value.get("metrics")
    if not isinstance(raw_metrics, Mapping):
        raise ResearchCampaignError("evaluation metrics must be an object")
    metrics: dict[str, Mapping[str, object]] = {}
    for task_id, raw_metric in raw_metrics.items():
        if not isinstance(task_id, str) or not isinstance(raw_metric, Mapping):
            raise ResearchCampaignError("evaluation contains an invalid metric")
        normalized = _json_copy(dict(raw_metric), label=f"{task_id} metric")
        assert isinstance(normalized, dict)
        if normalized.get("task_id") != task_id:
            raise ResearchCampaignError("evaluation metric task identity differs")
        metrics[task_id] = normalized
    if len(metrics) != len(raw_metrics):
        raise ResearchCampaignError("evaluation contains an invalid metric")
    status = _text(value.get("status"), label="evaluation status")
    task_ids = _task_ids(value.get("task_ids"), label="evaluation task_ids")
    raw_key = value.get("selection_key")
    if not isinstance(raw_key, (list, tuple)):
        raise ResearchCampaignError("evaluation selection_key must be a sequence")
    if status == "partial" and raw_key:
        raise ResearchCampaignError(
            "partial evaluation selection_key must be empty and nonselectable"
        )
    if status != "partial" and not raw_key:
        raise ResearchCampaignError("complete evaluation selection_key must be nonempty")
    if not set(metrics) <= set(task_ids):
        raise ResearchCampaignError(
            "evaluation metrics fall outside the declared task window"
        )
    selection_key: list[tuple[int, int]] = []
    for component in raw_key:
        if (
            not isinstance(component, (list, tuple))
            or len(component) != 2
            or type(component[0]) is not int
            or type(component[1]) is not int
            or component[1] <= 0
        ):
            raise ResearchCampaignError(
                "evaluation selection_key components must be integer rationals"
            )
        rational = Fraction(component[0], component[1])
        selection_key.append((rational.numerator, rational.denominator))
    raw_summary = value.get("selection_summary")
    if not isinstance(raw_summary, Mapping):
        raise ResearchCampaignError("evaluation selection_summary must be an object")
    if status == "partial":
        missing = [task_id for task_id in task_ids if task_id not in metrics]
        if not missing or not (
            raw_summary.get("selectable") is False
            and raw_summary.get("full_window_measurement_complete") is False
            and raw_summary.get("declared_task_ids") == list(task_ids)
            and raw_summary.get("scored_task_ids")
            == [task_id for task_id in task_ids if task_id in metrics]
            and raw_summary.get("missing_task_ids") == missing
            and raw_summary.get("missing_official_metrics")
            == {task_id: None for task_id in missing}
        ):
            raise ResearchCampaignError(
                "partial evaluation coverage or nonselectable declaration differs"
            )
    return OfficialEvaluation(
        stage_id=_text(value.get("stage_id"), label="evaluation stage_id"),
        backend_id=_text(value.get("backend_id"), label="evaluation backend_id"),
        harness=_harness(value.get("harness"), label="evaluation harness"),
        episode_stage_id=_text(value.get("episode_stage_id"), label="episode_stage_id"),
        task_ids=task_ids,
        condition_id=_text(value.get("condition_id"), label="evaluation condition_id"),
        status=status,
        metrics=metrics,
        selection_policy=_text(
            value.get("selection_policy"), label="evaluation selection_policy"
        ),
        selection_key=tuple(selection_key),
        selection_summary=dict(raw_summary),
        accounting=dict(value.get("accounting", {})),
        result_uri=_text(value.get("result_uri"), label="evaluation result_uri"),
        failure=value.get("failure") if isinstance(value.get("failure"), Mapping) else None,
    )


def _validated_evidence_record(
    *, episode: EpisodeEvidence, task_id: str
) -> dict[str, object]:
    """Validate the small cross-backend record without inventing file identity.

    Backends retain their native cell payloads, while this record gives every
    proposer the same role names.  Paths and lower-runtime receipts are the
    identity boundary; the campaign does not add a digest or content hash.
    """

    cell = episode.cells.get(task_id)
    if not isinstance(cell, Mapping):
        raise ResearchCampaignError(
            f"{episode.backend_id} episode lacks cell {task_id}"
        )
    raw = cell.get("evidence_record")
    if not isinstance(raw, Mapping):
        raise ResearchCampaignError(
            f"{episode.backend_id}/{task_id} lacks a standard evidence record"
        )
    if (
        raw.get("schema_version") != 1
        or raw.get("protocol") != EVIDENCE_RECORD_PROTOCOL
        or raw.get("backend_id") != episode.backend_id
        or raw.get("task_id") != task_id
        or raw.get("stage_id") != episode.stage_id
        or raw.get("official_evaluation_included") is not False
    ):
        raise ResearchCampaignError(
            f"{episode.backend_id}/{task_id} evidence identity differs"
        )
    _text(raw.get("root_uri"), label=f"{episode.backend_id}/{task_id} root_uri")
    members = raw.get("members")
    if not isinstance(members, Mapping):
        raise ResearchCampaignError(
            f"{episode.backend_id}/{task_id} evidence members are missing"
        )
    for role in _EVIDENCE_MEMBER_ROLES:
        _text(
            members.get(role),
            label=f"{episode.backend_id}/{task_id} evidence member {role}",
        )
    raw_probe_refs = raw.get("public_probe_refs")
    if not isinstance(raw_probe_refs, list) or not raw_probe_refs:
        raise ResearchCampaignError(
            f"{episode.backend_id}/{task_id} has no public probe references"
        )
    probe_refs = tuple(
        _text(
            value,
            label=f"{episode.backend_id}/{task_id} public probe reference",
        )
        for value in raw_probe_refs
    )
    if len(probe_refs) != len(set(probe_refs)) or not set(probe_refs) <= set(
        members
    ):
        raise ResearchCampaignError(
            f"{episode.backend_id}/{task_id} public probes do not name members"
        )
    normalized = _json_copy(dict(raw), label="standard evidence record")
    assert isinstance(normalized, dict)
    return normalized


def _delivered_evidence_record(
    *, episode: EpisodeEvidence, task_id: str
) -> dict[str, object] | None:
    """Return a delivered Worker record, excluding retained failure remnants."""

    cell = episode.cells.get(task_id)
    if not isinstance(cell, Mapping):
        raise ResearchCampaignError(
            f"{episode.backend_id} episode lacks cell {task_id}"
        )
    native = cell.get("native")
    if isinstance(native, Mapping):
        state = native.get("state")
        if isinstance(state, str) and state != "complete":
            return None
        if isinstance(native.get("failure"), Mapping):
            return None
    if cell.get("evidence_record") is None:
        return None
    return _validated_evidence_record(episode=episode, task_id=task_id)


def _window_coverage(
    *, episode: EpisodeEvidence, evaluation: OfficialEvaluation
) -> dict[str, object]:
    delivered = [
        task_id
        for task_id in episode.task_ids
        if _delivered_evidence_record(episode=episode, task_id=task_id)
        is not None
    ]
    scored = [
        task_id for task_id in episode.task_ids if task_id in evaluation.metrics
    ]
    missing_evidence = [
        task_id for task_id in episode.task_ids if task_id not in delivered
    ]
    missing_metrics = [
        task_id for task_id in episode.task_ids if task_id not in evaluation.metrics
    ]
    return {
        "episode_status": episode.status,
        "evaluation_status": evaluation.status,
        "declared_task_ids": list(episode.task_ids),
        "delivered_evidence_task_ids": delivered,
        "missing_evidence_task_ids": missing_evidence,
        "scored_task_ids": scored,
        "missing_official_metric_task_ids": missing_metrics,
        "missing_official_metrics": {
            task_id: None for task_id in missing_metrics
        },
        "full_window_measurement_complete": evaluation.status == "complete",
        "selectable": evaluation.status == "complete",
    }


def _validate_measured_episode_evaluation(
    *, episode: EpisodeEvidence, evaluation: OfficialEvaluation
) -> None:
    if not (
        _measured_stage(episode.status)
        and _measured_stage(evaluation.status)
        and not (
            episode.status == "partial" and evaluation.status == "complete"
        )
        and episode.backend_id == evaluation.backend_id
        and episode.harness == evaluation.harness
        and evaluation.episode_stage_id == episode.stage_id
        and evaluation.task_ids == episode.task_ids
        and evaluation.condition_id == episode.condition_id
        and set(evaluation.metrics) <= set(episode.task_ids)
    ):
        raise ResearchCampaignError(
            "measured episode and official evaluation identities differ"
        )
    if evaluation.status == "complete" and (
        set(evaluation.metrics) != set(episode.task_ids)
        or not evaluation.selection_key
    ):
        raise ResearchCampaignError(
            "complete official evaluation lacks its full selectable window"
        )
    if evaluation.status == "partial" and (
        set(evaluation.metrics) == set(episode.task_ids)
        or evaluation.selection_key
    ):
        raise ResearchCampaignError(
            "partial official evaluation must be sparse and nonselectable"
        )
    if evaluation.status == "partial":
        scored = [
            task_id
            for task_id in episode.task_ids
            if task_id in evaluation.metrics
        ]
        missing = [
            task_id
            for task_id in episode.task_ids
            if task_id not in evaluation.metrics
        ]
        summary = evaluation.selection_summary
        if not (
            summary.get("selectable") is False
            and summary.get("full_window_measurement_complete") is False
            and summary.get("declared_task_ids") == list(episode.task_ids)
            and summary.get("scored_task_ids") == scored
            and summary.get("missing_task_ids") == missing
            and summary.get("missing_official_metrics")
            == {task_id: None for task_id in missing}
        ):
            raise ResearchCampaignError(
                "partial official evaluation coverage declaration differs"
            )
    for metric in evaluation.metrics.values():
        if metric.get("zero_model_requests") is not True:
            raise ResearchCampaignError(
                "official evaluation metric is not zero-model"
            )


def _validate_revision_windows(
    *,
    parent_harness: HarnessRef,
    evidence_by_backend: Mapping[str, EpisodeEvidence],
    evaluations_by_backend: Mapping[str, OfficialEvaluation],
    investigate_partial_windows: bool = False,
) -> None:
    if set(evidence_by_backend) != set(evaluations_by_backend) or not evidence_by_backend:
        raise ResearchCampaignError(
            "revision evidence and evaluations must cover identical backends"
        )
    for backend_id, episode in evidence_by_backend.items():
        evaluation = evaluations_by_backend[backend_id]
        if not (
            episode.backend_id == backend_id
            and evaluation.backend_id == backend_id
            and episode.harness == parent_harness
            and evaluation.harness == parent_harness
            and evaluation.episode_stage_id == episode.stage_id
            and evaluation.task_ids == episode.task_ids
            and evaluation.condition_id == episode.condition_id
            and set(episode.cells) == set(episode.task_ids)
        ):
            raise ResearchCampaignError(
                f"{backend_id} revision window is not one matched parent package"
            )
        if not investigate_partial_windows and not (
            episode.status == "complete"
            and evaluation.status == "complete"
            and set(evaluation.metrics) == set(episode.task_ids)
        ):
            raise ResearchCampaignError(
                f"{backend_id} revision window is not one matched parent package"
            )
        if investigate_partial_windows:
            _validate_measured_episode_evaluation(
                episode=episode, evaluation=evaluation
            )
        for task_id in episode.task_ids:
            record = _delivered_evidence_record(
                episode=episode, task_id=task_id
            )
            if task_id in evaluation.metrics and record is None:
                raise ResearchCampaignError(
                    f"{backend_id}/{task_id} scored revision evidence is missing"
                )


def compare_whole_harness_evaluations(
    *,
    parent: OfficialEvaluation,
    candidate: OfficialEvaluation,
    expected_task_ids: Sequence[str],
    require_task_order: bool = True,
) -> dict[str, object]:
    """Apply the declared window rule without taskwise package splicing."""

    expected = tuple(expected_task_ids)
    if (
        parent.status != "complete"
        or candidate.status != "complete"
        or parent.backend_id != candidate.backend_id
        or (
            require_task_order
            and (parent.task_ids != expected or candidate.task_ids != expected)
        )
        or (
            not require_task_order
            and (
                set(parent.task_ids) != set(expected)
                or set(candidate.task_ids) != set(expected)
                or len(parent.task_ids) != len(expected)
                or len(candidate.task_ids) != len(expected)
            )
        )
        or set(parent.metrics) != set(expected)
        or set(candidate.metrics) != set(expected)
        or parent.condition_id != candidate.condition_id
        or parent.harness.harness_id == candidate.harness.harness_id
    ):
        raise ResearchCampaignError(
            "parent and candidate require distinct whole packages with the exact "
            "same completed comparison window and condition"
        )
    if (
        parent.selection_policy != candidate.selection_policy
        or len(parent.selection_key) != len(candidate.selection_key)
    ):
        raise ResearchCampaignError(
            "parent and candidate declared different benchmark selection metrics"
        )
    for evaluation in (parent, candidate):
        for task_id in expected:
            metric = evaluation.metrics[task_id]
            if metric.get("task_id") != task_id or metric.get(
                "zero_model_requests"
            ) is not True:
                raise ResearchCampaignError(
                    "comparison requires exact zero-model official task metrics"
                )
            if metric.get("contract_adjusted") is True:
                raise ResearchCampaignError(
                    "contract-adjusted replay is outside the default campaign rule"
                )
    parent_key = tuple(Fraction(*component) for component in parent.selection_key)
    candidate_key = tuple(
        Fraction(*component) for component in candidate.selection_key
    )
    selected = "candidate" if candidate_key > parent_key else "parent"
    return {
        "scope": "declared_development_comparison_window_only",
        "backend_id": parent.backend_id,
        "task_ids": list(expected),
        "rule": parent.selection_policy,
        "parent": dict(parent.selection_summary),
        "candidate": dict(candidate.selection_summary),
        "parent_key": [list(component) for component in parent.selection_key],
        "candidate_key": [list(component) for component in candidate.selection_key],
        "selected": selected,
        "exact_tie": candidate_key == parent_key,
        "taskwise_splicing": False,
        "claim_outside_window": False,
    }


def compare_benchmark_windows(
    *,
    parents: Mapping[str, OfficialEvaluation],
    candidates: Mapping[str, OfficialEvaluation],
    expected_windows: Mapping[str, Sequence[str]],
    require_task_order: bool = True,
    promotion_net_gains_required: int | None = None,
) -> dict[str, object]:
    """Pareto-select one whole harness across separately scored benchmarks.

    When ``promotion_net_gains_required`` is a positive integer N, an
    additional gate enforces that the candidate must show at least N net task
    gains (candidate wins minus parent wins) summed across the declared
    windows.  This is the net-gains threshold from the power analysis: a
    zero-threshold gate promotes a neutral mechanism ~13% of the time per
    round, while net>=2 reduces spurious promotions 3x at identical cost.
    When the parameter is ``None`` the original zero-threshold Pareto rule
    applies, preserving backward compatibility.
    """

    if set(parents) != set(expected_windows) or set(candidates) != set(
        expected_windows
    ):
        raise ResearchCampaignError(
            "multi-benchmark comparison lacks an exact backend window"
        )
    parent_harnesses = {evaluation.harness for evaluation in parents.values()}
    candidate_harnesses = {
        evaluation.harness for evaluation in candidates.values()
    }
    if len(parent_harnesses) != 1 or len(candidate_harnesses) != 1:
        raise ResearchCampaignError(
            "multi-benchmark comparison cannot splice backend-specific packages"
        )
    comparisons = {
        backend_id: compare_whole_harness_evaluations(
            parent=parents[backend_id],
            candidate=candidates[backend_id],
            expected_task_ids=expected_windows[backend_id],
            require_task_order=require_task_order,
        )
        for backend_id in expected_windows
    }
    candidate_strict = any(
        comparison["selected"] == "candidate"
        for comparison in comparisons.values()
    )
    candidate_nonregressing = all(
        tuple(
            Fraction(*component) for component in comparison["candidate_key"]
        )
        >= tuple(
            Fraction(*component) for component in comparison["parent_key"]
        )
        for comparison in comparisons.values()
    )
    mixed_regression = candidate_strict and not candidate_nonregressing

    # Net-gains threshold gate (power-analysis calibrated).
    net_gains_required_met = True
    net_task_gains = 0
    net_task_regressions = 0
    per_task_deltas: dict[str, dict[str, int]] = {}
    if promotion_net_gains_required is not None:
        if (
            not isinstance(promotion_net_gains_required, int)
            or promotion_net_gains_required < 0
        ):
            raise ResearchCampaignError(
                "promotion_net_gains_required must be a non-negative integer"
            )
        net_task_gains = 0
        net_task_regressions = 0
        for backend_id, comparison in comparisons.items():
            parent_eval = parents[backend_id]
            candidate_eval = candidates[backend_id]
            backend_deltas: dict[str, int] = {}
            for task_id in expected_windows[backend_id]:
                parent_reward = int(
                    parent_eval.metrics[task_id].get("binary_reward", 0)
                )
                candidate_reward = int(
                    candidate_eval.metrics[task_id].get("binary_reward", 0)
                )
                delta = candidate_reward - parent_reward
                backend_deltas[task_id] = delta
                if delta > 0:
                    net_task_gains += 1
                elif delta < 0:
                    net_task_regressions += 1
            per_task_deltas[backend_id] = backend_deltas
        net_gain = net_task_gains - net_task_regressions
        net_gains_required_met = net_gain >= promotion_net_gains_required

    pareto_promote = candidate_nonregressing and candidate_strict
    selected = (
        "candidate"
        if (pareto_promote and net_gains_required_met)
        else "parent"
    )
    return {
        "scope": "declared_multi_benchmark_development_windows_only",
        "rule": "per_benchmark_declared_metric_pareto_then_earlier"
        + (
            f"_net_gains_ge_{promotion_net_gains_required}"
            if promotion_net_gains_required is not None
            else ""
        ),
        "comparisons": comparisons,
        "selected": selected,
        "candidate_nonregressing_in_every_window": candidate_nonregressing,
        "candidate_strictly_improved_any_window": candidate_strict,
        "mixed_gain_regression": mixed_regression,
        "exact_tie": not candidate_strict and candidate_nonregressing,
        "taskwise_splicing": False,
        "cross_benchmark_score_pooling": False,
        "claim_outside_windows": False,
        "promotion_net_gains_required": promotion_net_gains_required,
        "net_task_gains": net_task_gains if promotion_net_gains_required is not None else None,
        "net_task_regressions": (
            net_task_regressions if promotion_net_gains_required is not None else None
        ),
        "net_gains_threshold_met": (
            net_gains_required_met
            if promotion_net_gains_required is not None
            else None
        ),
        "per_task_reward_deltas": per_task_deltas if promotion_net_gains_required is not None else None,
    }


_ACCOUNTING_FIELDS = (
    "provider_requests",
    "completed_requests",
    "logical_requests",
    "provider_retries",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "turns",
    "tool_calls",
    "tool_errors",
    "component_checks",
    "wall_time_seconds",
)


def _known_accounted_cost(accounting: Mapping[str, object]) -> Decimal | None:
    """Return one retained cost component without certifying completeness."""
    preferred = (
        ("provider_cost_usd", "accounted_provider_cost_usd")
        if accounting.get("cost_complete") is True
        else ("accounted_provider_cost_usd", "provider_cost_usd")
    )
    for field in preferred:
        value = accounting.get(field)
        if (
            not isinstance(value, bool)
            and isinstance(value, (int, float))
            and value >= 0
        ):
            return Decimal(str(value))
    return None


def _accounting_totals(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    totals: dict[str, object] = {field: 0 for field in _ACCOUNTING_FIELDS}
    completeness = {field: True for field in _ACCOUNTING_FIELDS}
    cost = Decimal("0")
    cost_complete = True
    for row in rows:
        accounting = row.get("accounting")
        if not isinstance(accounting, Mapping):
            accounting = {}
        row_completeness = accounting.get("field_complete")
        detail_incomplete = accounting.get("detail_complete") is False
        for field in _ACCOUNTING_FIELDS:
            value = accounting.get(field)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                completeness[field] = False
                continue
            totals[field] = float(totals[field]) + float(value)
            has_explicit_completeness = (
                isinstance(row_completeness, Mapping)
                and field in row_completeness
            )
            if (
                has_explicit_completeness
                and row_completeness.get(field) is not True
            ) or (
                not has_explicit_completeness
                and detail_incomplete
                and field not in {"component_checks", "wall_time_seconds"}
            ):
                completeness[field] = False
        raw_cost = accounting.get("provider_cost_usd")
        if accounting.get("cost_complete") is not True or isinstance(raw_cost, bool) or not isinstance(raw_cost, (int, float)) or raw_cost < 0:
            cost_complete = False
        known_cost = _known_accounted_cost(accounting)
        if known_cost is not None:
            cost += known_cost
    for field in _ACCOUNTING_FIELDS:
        if field != "wall_time_seconds" and float(totals[field]).is_integer():
            totals[field] = int(totals[field])
    totals.update(
        {
            "provider_cost_usd": float(cost) if cost_complete else None,
            "accounted_provider_cost_usd": float(cost),
            "cost_complete": cost_complete,
            "field_complete": completeness,
            "stage_count": len(rows),
        }
    )
    return totals


def _ledger_row(*, kind: str, stage_id: str, backend_id: str, status: str, accounting: Mapping[str, object], result_uri: str) -> dict[str, object]:
    return {
        "kind": kind,
        "stage_id": stage_id,
        "backend_id": backend_id,
        "status": status,
        "accounting": _json_copy(dict(accounting), label="stage accounting"),
        "result_uri": result_uri,
    }


def _backend(backends: Mapping[str, CampaignBackend], backend_id: str) -> CampaignBackend:
    try:
        backend = backends[backend_id]
    except KeyError as exc:
        raise ResearchCampaignError(f"no backend registered for {backend_id}") from exc
    if backend.backend_id != backend_id:
        raise ResearchCampaignError("backend registry key differs from backend_id")
    return backend


def _stop_for_failure(state: dict[str, object], *, stage_id: str, backend_id: str, failure: Mapping[str, object] | None, result_uri: str | None = None) -> None:
    record = {
        "stage_id": stage_id,
        "backend_id": backend_id,
        "failure": dict(failure or {"kind": "terminal_stage_failure"}),
        "result_uri": result_uri,
        "automatic_retry": False,
    }
    state["failure_ledger"].append(record)
    state["status"] = "stopped"
    state["phase"] = "failed"


def _record_continued_revision_failure(
    state: dict[str, object], *, result: RevisionOutcome
) -> None:
    """Retain a qualified failure without duplicating its stage accounting."""

    state["failure_ledger"].append(
        {
            "stage_id": result.stage_id,
            "backend_id": result.backend_id,
            "failure": dict(result.failure or {}),
            "result_uri": result.result_uri,
            "automatic_retry": False,
            "campaign_continued": True,
            "disposition": "retain_parent_and_research_memory",
            "candidate_evaluation_run": False,
        }
    )


def _failed_revision_memory_is_valid(result: RevisionOutcome) -> bool:
    memory = result.retained_memory
    if memory is None or memory.source_stage_id != result.stage_id:
        return False
    try:
        load_research_operation_memory(
            Path(memory.artifact_uri).expanduser().resolve()
        )
    except ResearchOperationMemoryError:
        return False
    return True


def _validate_revision_outcome_identity(
    result: RevisionOutcome,
    *,
    stage_id: str,
    backend_id: str,
    parent_harness: HarnessRef,
) -> None:
    if result.stage_id != stage_id:
        raise ResearchCampaignError("revision outcome stage identity differs")
    if result.backend_id != backend_id:
        raise ResearchCampaignError("revision outcome backend identity differs")
    if result.parent_harness != parent_harness:
        raise ResearchCampaignError("revision outcome parent harness differs")


def _persist_state(path: Path, state: dict[str, object]) -> dict[str, object]:
    state["accounting"] = _accounting_totals(state["stage_ledger"])
    normalized = _json_copy(state, label="campaign state")
    assert isinstance(normalized, dict)
    _atomic_json(path, normalized)
    return normalized


def _start_round(state: dict[str, object]) -> bool:
    plan = state["plan"]
    index = int(state["round_index"])
    rounds = plan["rounds"]
    if index >= len(rounds):
        state["phase"] = "freeze_episode"
        return False
    round_plan = rounds[index]
    state["current_round"] = {
        "round_id": round_plan["round_id"],
        "active_backend_id": round_plan["active_backend_id"],
        "active_task_id": round_plan["active_task_id"],
        "comparison_windows": round_plan["comparison_windows"],
        "backend_order": list(round_plan["comparison_windows"]),
        "stage_backend_index": 0,
        "stage_ids": round_plan["stage_ids"],
        "revision_options": round_plan["revision_options"],
        "parent_harness": state["research_parent"],
        "input_research_memory": state["research_memory"],
        "parent_episodes": {},
        "parent_evaluations": {},
        "revision": None,
        "candidate_episodes": {},
        "candidate_evaluations": {},
        "selection": None,
    }
    state["phase"] = "parent_episode"
    return True


def _related_completed_round(
    value: Mapping[str, object],
) -> RelatedCompletedRound | None:
    """Project one actually observed candidate round without its selection."""

    windows = value.get("comparison_windows")
    revision = value.get("revision")
    parent_episodes = value.get("parent_episodes")
    parent_evaluations = value.get("parent_evaluations")
    candidate_episodes = value.get("candidate_episodes")
    candidate_evaluations = value.get("candidate_evaluations")
    if not candidate_episodes and not candidate_evaluations:
        return None
    if not (
        isinstance(windows, Mapping)
        and windows
        and isinstance(revision, Mapping)
        and isinstance(parent_episodes, Mapping)
        and isinstance(parent_evaluations, Mapping)
        and isinstance(candidate_episodes, Mapping)
        and isinstance(candidate_evaluations, Mapping)
        and set(parent_episodes) == set(windows)
        and set(parent_evaluations) == set(windows)
        and set(candidate_episodes) == set(windows)
        and set(candidate_evaluations) == set(windows)
    ):
        raise ResearchCampaignError(
            "observed candidate round lacks an exact backend window"
        )
    parent_harness = _harness(
        value.get("parent_harness"), label="related round parent harness"
    )
    candidate_harness = _harness(
        revision.get("candidate_harness"),
        label="related round candidate harness",
    )
    parent_evidence_by_backend: dict[str, EpisodeEvidence] = {}
    parent_evaluations_by_backend: dict[str, OfficialEvaluation] = {}
    evidence_by_backend: dict[str, EpisodeEvidence] = {}
    evaluations_by_backend: dict[str, OfficialEvaluation] = {}
    for backend_id, raw_tasks in windows.items():
        tasks = _task_ids(
            raw_tasks,
            label=f"related round {backend_id} comparison window",
        )
        parent_episode = _episode(parent_episodes[backend_id])
        parent_evaluation = _evaluation(parent_evaluations[backend_id])
        candidate_episode = _episode(candidate_episodes[backend_id])
        candidate_evaluation = _evaluation(candidate_evaluations[backend_id])
        for side, harness, episode, evaluation in (
            (
                "parent",
                parent_harness,
                parent_episode,
                parent_evaluation,
            ),
            (
                "candidate",
                candidate_harness,
                candidate_episode,
                candidate_evaluation,
            ),
        ):
            if (
                episode.backend_id != backend_id
                or evaluation.backend_id != backend_id
                or episode.harness != harness
                or evaluation.harness != harness
                or episode.task_ids != tasks
            ):
                raise ResearchCampaignError(
                    f"related round {side} {backend_id} identity differs"
                )
            _validate_measured_episode_evaluation(
                episode=episode, evaluation=evaluation
            )
        parent_evidence_by_backend[backend_id] = parent_episode
        parent_evaluations_by_backend[backend_id] = parent_evaluation
        evidence_by_backend[backend_id] = candidate_episode
        evaluations_by_backend[backend_id] = candidate_evaluation
    return RelatedCompletedRound(
        round_id=_text(value.get("round_id"), label="related round ID"),
        parent_harness=parent_harness,
        candidate_harness=candidate_harness,
        revision_result_uri=_text(
            revision.get("result_uri"),
            label="related round revision result_uri",
        ),
        parent_evidence_by_backend=parent_evidence_by_backend,
        parent_evaluations_by_backend=parent_evaluations_by_backend,
        evidence_by_backend=evidence_by_backend,
        evaluations_by_backend=evaluations_by_backend,
    )


def _latest_related_completed_round(
    state: Mapping[str, object],
) -> RelatedCompletedRound | None:
    if state.get("plan", {}).get("return_candidate_feedback") is not True:
        return None
    completed = state.get("completed_rounds")
    if not isinstance(completed, list):
        raise ResearchCampaignError("completed rounds must be a list")
    raw_index = state.get("latest_candidate_observation_round_index")
    if raw_index is None:
        indexed = range(len(completed) - 1, -1, -1)
    elif type(raw_index) is int and 0 <= raw_index < len(completed):
        indexed = (raw_index,)
    else:
        raise ResearchCampaignError(
            "latest candidate observation round pointer is invalid"
        )
    for index in indexed:
        raw = completed[index]
        if not isinstance(raw, Mapping):
            raise ResearchCampaignError("completed round must be an object")
        related = _related_completed_round(raw)
        if related is not None:
            return related
    return None


def _seed_related_completed_rounds(
    options: Mapping[str, object],
) -> tuple[RelatedCompletedRound, ...]:
    """Resolve at most three explicitly registered old completed rounds.

    These are historical evidence, never current parent feedback or new H0
    scores. Each source is identified by campaign, round and revision stage.
    """

    raw = options.get("outcome_review_seed_round_refs")
    if raw is None:
        return ()
    if options.get("outcome_linked_experience_review") is not True:
        raise ResearchCampaignError("seed outcome rounds require opt-in review")
    if not isinstance(raw, list) or not 1 <= len(raw) <= 3:
        raise ResearchCampaignError("seed outcome rounds must contain one to three refs")
    resolved: list[RelatedCompletedRound] = []
    identities: set[tuple[str, str]] = set()
    for ref in raw:
        if not isinstance(ref, Mapping):
            raise ResearchCampaignError("seed outcome round ref must be an object")
        campaign_id = _text(ref.get("campaign_id"), label="seed campaign ID")
        round_id = _text(ref.get("round_id"), label="seed round ID")
        revision_stage_id = _text(
            ref.get("revision_stage_id"), label="seed revision stage ID"
        )
        identity = (campaign_id, round_id)
        if identity in identities:
            raise ResearchCampaignError("seed outcome round is duplicated")
        identities.add(identity)
        state_uri = _text(ref.get("state_uri"), label="seed campaign state URI")
        source_state = _read_object(Path(state_uri), label="seed campaign state")
        completed = source_state.get("completed_rounds")
        if not (
            source_state.get("protocol") == "research-campaign-v1"
            and source_state.get("campaign_id") == campaign_id
            and isinstance(completed, list)
        ):
            raise ResearchCampaignError("seed campaign state identity differs")
        rows = [
            row for row in completed
            if isinstance(row, Mapping) and row.get("round_id") == round_id
        ]
        if len(rows) != 1 or not isinstance(rows[0].get("revision"), Mapping):
            raise ResearchCampaignError("seed completed round is unavailable")
        if rows[0]["revision"].get("stage_id") != revision_stage_id:
            raise ResearchCampaignError("seed revision stage identity differs")
        related = _related_completed_round(rows[0])
        if related is None:
            raise ResearchCampaignError("seed round has no completed candidate pair")
        resolved.append(related)
    return tuple(resolved)


def _finish_round(state: dict[str, object], *, selection: Mapping[str, object]) -> None:
    current = state["current_round"]
    current["selection"] = dict(selection)
    if state["plan"].get("return_candidate_feedback") is True:
        related = _related_completed_round(current)
        if related is not None:
            state["latest_candidate_observation_round_index"] = len(
                state["completed_rounds"]
            )
    state["completed_rounds"].append(current)
    state["round_index"] = int(state["round_index"]) + 1
    state["current_round"] = None
    state["phase"] = "round_start"


def _measured_stage(status: str) -> bool:
    return status in {"complete", "partial"}


def _incomplete_window_selection(
    *,
    evaluations: Mapping[str, object],
    candidate: bool,
) -> dict[str, object]:
    coverage: dict[str, object] = {}
    partial_backends: list[str] = []
    for backend_id, raw in evaluations.items():
        if not isinstance(raw, Mapping):
            raise ResearchCampaignError(
                "incomplete comparison window lacks a backend evaluation"
            )
        evaluation = _evaluation(raw)
        scored = [
            task_id for task_id in evaluation.task_ids if task_id in evaluation.metrics
        ]
        missing = [
            task_id for task_id in evaluation.task_ids if task_id not in evaluation.metrics
        ]
        if evaluation.status == "partial":
            partial_backends.append(backend_id)
        coverage[backend_id] = {
            "status": evaluation.status,
            "declared_task_ids": list(evaluation.task_ids),
            "scored_task_ids": scored,
            "missing_task_ids": missing,
            "missing_official_metrics": {task_id: None for task_id in missing},
        }
    if not partial_backends:
        raise ResearchCampaignError(
            "incomplete comparison selection requires a partial backend"
        )
    return {
        "selected": "parent",
        "reason": "incomplete_comparison_window",
        "comparison_run": False,
        "candidate_observed": candidate,
        "candidate_promotable": False,
        "partial_backends": partial_backends,
        "coverage_by_backend": coverage,
        "research_parent_unchanged": True,
        "research_memory_retention_independent": True,
        "taskwise_splicing": False,
        "claim_outside_window": False,
    }


def _incomplete_candidate_comparison_selection(
    *,
    parents: Mapping[str, object],
    candidates: Mapping[str, object],
) -> dict[str, object]:
    """Retain the parent when either observed comparison side is partial."""

    parent_partial = [
        backend_id
        for backend_id, value in parents.items()
        if _evaluation(value).status == "partial"
    ]
    candidate_partial = [
        backend_id
        for backend_id, value in candidates.items()
        if _evaluation(value).status == "partial"
    ]
    if not parent_partial and not candidate_partial:
        raise ResearchCampaignError(
            "incomplete candidate comparison requires a partial side"
        )
    selection = _incomplete_window_selection(
        evaluations=candidates if candidate_partial else parents,
        candidate=True,
    )
    selection.update(
        {
            "parent_window_partial": bool(parent_partial),
            "candidate_window_partial": bool(candidate_partial),
            "parent_partial_backends": parent_partial,
            "candidate_partial_backends": candidate_partial,
        }
    )
    return selection


def _partial_terminal_comparison(
    *,
    baselines: Mapping[str, OfficialEvaluation],
    frozen: Mapping[str, OfficialEvaluation],
    windows: Mapping[str, tuple[str, ...]],
) -> dict[str, object]:
    if set(baselines) != set(windows) or set(frozen) != set(windows):
        raise ResearchCampaignError(
            "partial terminal measurement lacks a registered backend"
        )
    by_backend: dict[str, object] = {}

    def metric_delta(
        baseline_metric: Mapping[str, object],
        frozen_metric: Mapping[str, object],
    ) -> dict[str, object]:
        def reward(metric: Mapping[str, object]) -> Fraction | None:
            raw = metric.get("official_reward_rational")
            if (
                isinstance(raw, list)
                and len(raw) == 2
                and type(raw[0]) is int
                and type(raw[1]) is int
                and raw[1] > 0
            ):
                return Fraction(raw[0], raw[1])
            binary = metric.get("binary_reward")
            if type(binary) is int and binary in {0, 1}:
                return Fraction(binary, 1)
            return None

        def test_fraction(metric: Mapping[str, object]) -> Fraction | None:
            passed = metric.get("passed")
            total = metric.get("total")
            if type(passed) is int and type(total) is int and total > 0:
                return Fraction(passed, total)
            return None

        result: dict[str, object] = {}
        for label, getter in (
            ("official_reward_delta", reward),
            ("test_fraction_delta", test_fraction),
        ):
            before = getter(baseline_metric)
            after = getter(frozen_metric)
            if before is None or after is None:
                result[label] = None
            else:
                delta = after - before
                result[label] = {
                    "numerator": delta.numerator,
                    "denominator": delta.denominator,
                    "decimal": float(delta),
                }
        return result

    for backend_id, declared in windows.items():
        baseline = baselines[backend_id]
        candidate = frozen[backend_id]
        if not (
            _measured_stage(baseline.status)
            and _measured_stage(candidate.status)
            and baseline.backend_id == backend_id
            and candidate.backend_id == backend_id
            and set(baseline.task_ids) == set(declared)
            and set(candidate.task_ids) == set(declared)
            and baseline.condition_id == candidate.condition_id
            and set(baseline.metrics) <= set(declared)
            and set(candidate.metrics) <= set(declared)
        ):
            raise ResearchCampaignError(
                f"{backend_id} partial terminal measurement identity differs"
            )
        for evaluation in (baseline, candidate):
            for metric in evaluation.metrics.values():
                if (
                    metric.get("zero_model_requests") is not True
                    or metric.get("contract_adjusted") is True
                ):
                    raise ResearchCampaignError(
                        f"{backend_id} partial terminal metric is not an unchanged zero-model result"
                    )
        baseline_scored = [task for task in declared if task in baseline.metrics]
        candidate_scored = [task for task in declared if task in candidate.metrics]
        paired = [
            task
            for task in declared
            if task in baseline.metrics and task in candidate.metrics
        ]
        by_backend[backend_id] = {
            "declared_task_ids": list(declared),
            "baseline_status": baseline.status,
            "frozen_status": candidate.status,
            "baseline_scored_task_ids": baseline_scored,
            "baseline_missing_task_ids": [
                task for task in declared if task not in baseline.metrics
            ],
            "baseline_missing_official_metrics": {
                task: None for task in declared if task not in baseline.metrics
            },
            "frozen_scored_task_ids": candidate_scored,
            "frozen_missing_task_ids": [
                task for task in declared if task not in candidate.metrics
            ],
            "frozen_missing_official_metrics": {
                task: None for task in declared if task not in candidate.metrics
            },
            "paired_intersection_task_ids": paired,
            "paired_metrics": {
                task: {
                    "baseline": dict(baseline.metrics[task]),
                    "frozen": dict(candidate.metrics[task]),
                    "delta": metric_delta(
                        baseline.metrics[task], candidate.metrics[task]
                    ),
                }
                for task in paired
            },
            "paired_deltas_are_intersection_conditional": True,
            "backend_full_panel_comparison_available": (
                baseline.status == "complete" and candidate.status == "complete"
            ),
            "backend_full_panel_win_claim": False,
        }
    return {
        "scope": "terminal_registered_panels_partial_measurement",
        "protocol_complete": True,
        "full_panel_measurement_complete": False,
        "full_panel_comparison_available": False,
        "full_panel_win_claim": False,
        "selected": None,
        "taskwise_splicing": False,
        "cross_benchmark_score_pooling": False,
        "terminal_result_returned_to_revision": False,
        "selection_already_frozen": True,
        "benchmarks_reported_separately": True,
        "by_backend": by_backend,
    }


def _same_harness_terminal_comparison(
    *,
    baselines: Mapping[str, OfficialEvaluation],
    frozen: Mapping[str, OfficialEvaluation],
    windows: Mapping[str, tuple[str, ...]],
) -> dict[str, object]:
    """Describe two full observations of one package; never select it as a gain.

    The baseline/frozen worker_role labels describe their run purpose, not a
    package mutation. All other harness identity fields must agree exactly.
    """
    if set(baselines) != set(windows) or set(frozen) != set(windows):
        raise ResearchCampaignError("same-harness terminal panels lack a backend")
    identities = {
        (
            evaluation.harness.harness_id,
            evaluation.harness.artifact_uri,
            evaluation.harness.revision_uri,
        )
        for evaluation in (*baselines.values(), *frozen.values())
    }
    if len(identities) != 1:
        raise ResearchCampaignError(
            "same-harness terminal repeat requires exact id, artifact, and revision"
        )
    for backend_id, declared in windows.items():
        before, after = baselines[backend_id], frozen[backend_id]
        if not (
            before.status == after.status == "complete"
            and before.backend_id == after.backend_id == backend_id
            and set(before.task_ids) == set(after.task_ids) == set(declared)
            and len(before.task_ids) == len(after.task_ids) == len(declared)
            and set(before.metrics) == set(after.metrics) == set(declared)
            and before.condition_id == after.condition_id
            and before.selection_policy == after.selection_policy
            and len(before.selection_key) == len(after.selection_key)
        ):
            raise ResearchCampaignError(
                f"{backend_id} same-harness terminal full-panel identity differs"
            )
    # This existing path retains exact per-task official metric pairs and
    # rational deltas. Its partial-coverage flags are replaced below only after
    # the complete-panel checks above have succeeded.
    result = _partial_terminal_comparison(
        baselines=baselines, frozen=frozen, windows=windows
    )
    for backend_id in windows:
        before, after = baselines[backend_id], frozen[backend_id]
        entry = result["by_backend"][backend_id]
        entry["paired_deltas_are_intersection_conditional"] = False
        entry["selection_policy"] = before.selection_policy
        entry["baseline_selection_key"] = [list(part) for part in before.selection_key]
        entry["frozen_selection_key"] = [list(part) for part in after.selection_key]
        entry["baseline_selection_summary"] = dict(before.selection_summary)
        entry["frozen_selection_summary"] = dict(after.selection_summary)
        entry["same_harness_repeat_observation"] = True
    result.update(
        {
            "scope": "terminal_registered_full_panels_same_harness_repeat_observation",
            "full_panel_measurement_complete": True,
            "full_panel_comparison_available": True,
            "full_panel_win_claim_available": False,
            "full_panel_win_claim": False,
            "selected": None,
            "evolution_gain": False,
            "same_harness_repeat_observation": True,
            "same_harness_identity": {
                "harness_id": next(iter(identities))[0],
                "artifact_uri": next(iter(identities))[1],
                "revision_uri": next(iter(identities))[2],
            },
            "development_feedback_complete_before_terminal_evaluation": True,
        }
    )
    return result


def _finish_terminal_comparison(state: dict[str, object]) -> None:
    baselines = {
        str(row["backend_id"]): _evaluation(row["evaluation"])
        for row in state["baseline_results"]
    }
    frozen = {
        str(row["backend_id"]): _evaluation(row["evaluation"])
        for row in state["freeze_results"]
    }
    windows = {
        str(row["backend_id"]): tuple(row["task_ids"])
        for row in state["plan"]["freeze"]
    }
    if all(
        evaluation.status == "complete"
        for evaluation in (*baselines.values(), *frozen.values())
    ):
        baseline_ids = {item.harness.harness_id for item in baselines.values()}
        frozen_ids = {item.harness.harness_id for item in frozen.values()}
        if len(baseline_ids) == len(frozen_ids) == 1 and baseline_ids == frozen_ids:
            comparison = _same_harness_terminal_comparison(
                baselines=baselines, frozen=frozen, windows=windows
            )
        else:
            comparison = compare_benchmark_windows(
                parents=baselines,
                candidates=frozen,
                expected_windows=windows,
                require_task_order=False,
            )
            comparison["scope"] = "terminal_registered_full_panels_h0_vs_frozen"
            comparison["protocol_complete"] = True
            comparison["full_panel_measurement_complete"] = True
            comparison["full_panel_comparison_available"] = True
            comparison["full_panel_win_claim_available"] = True
            comparison["full_panel_win_claim"] = (
                comparison.get("selected") == "candidate"
            )
            comparison["development_feedback_complete_before_terminal_evaluation"] = True
            comparison["terminal_result_returned_to_revision"] = False
            comparison["selection_already_frozen"] = True
            comparison["benchmarks_reported_separately"] = True
            for backend_comparison in comparison["comparisons"].values():
                backend_comparison["scope"] = "terminal_registered_backend_panel_h0_vs_frozen"
                backend_comparison["claim_outside_window"] = False
    else:
        comparison = _partial_terminal_comparison(
            baselines=baselines,
            frozen=frozen,
            windows=windows,
        )
    state["terminal_comparison"] = comparison
    state["status"] = "complete"
    state["phase"] = "complete"


def advance_campaign(*, state_path: str | Path, backends: Mapping[str, CampaignBackend]) -> dict[str, object]:
    """Execute at most one external stage and durably advance the campaign."""

    path = Path(state_path).expanduser().resolve()
    state = _read_object(path, label="campaign state")
    if state.get("protocol") != PROTOCOL:
        raise ResearchCampaignError("campaign state protocol differs")
    if state.get("status") != "running":
        return state

    # Internal transitions do not require a separate user invocation.
    try:
        while state["phase"] in {
            "round_start",
            "selection",
            "terminal_comparison",
        }:
            if state["phase"] == "round_start":
                _start_round(state)
                continue
            if state["phase"] == "terminal_comparison":
                _finish_terminal_comparison(state)
                return _persist_state(path, state)
            current = state["current_round"]
            parents = {
                backend_id: _evaluation(value)
                for backend_id, value in current["parent_evaluations"].items()
            }
            candidates = {
                backend_id: _evaluation(value)
                for backend_id, value in current["candidate_evaluations"].items()
            }
            if any(
                evaluation.status == "partial"
                for evaluation in (*parents.values(), *candidates.values())
            ):
                selection = _incomplete_candidate_comparison_selection(
                    parents=current["parent_evaluations"],
                    candidates=current["candidate_evaluations"],
                )
            else:
                selection = compare_benchmark_windows(
                    parents=parents,
                    candidates=candidates,
                    expected_windows=current["comparison_windows"],
                )
            if selection["selected"] == "candidate":
                state["research_parent"] = current["revision"]["candidate_harness"]
            _finish_round(state, selection=selection)
    except Exception as exc:
        failure = {
            "kind": "campaign_internal_transition_error",
            "exception_type": type(exc).__name__,
            "message": str(exc),
        }
        _stop_for_failure(
            state,
            stage_id=str(state.get("phase", "campaign-transition")),
            backend_id="campaign",
            failure=failure,
        )
        return _persist_state(path, state)

    phase = str(state["phase"])
    try:
        if phase == "baseline_episode":
            index = int(state["baseline_index"])
            baseline = state["plan"]["baselines"][index]
            backend = _backend(backends, str(baseline["backend_id"]))
            result = backend.run_episode(
                EpisodeRequest(
                    campaign_id=str(state["campaign_id"]),
                    stage_id=str(baseline["episode_stage_id"]),
                    backend_id=backend.backend_id,
                    harness=_harness(baseline["harness"], label="baseline harness"),
                    task_ids=tuple(baseline["task_ids"]),
                    purpose="official_baseline",
                    frozen=True,
                )
            )
            state["stage_ledger"].append(_ledger_row(kind="episode", stage_id=result.stage_id, backend_id=result.backend_id, status=result.status, accounting=result.accounting, result_uri=result.result_uri))
            state["baseline_results"].append(
                {
                    "backend_id": backend.backend_id,
                    "episode": asdict(result),
                    "evaluation": None,
                }
            )
            if not _measured_stage(result.status):
                _stop_for_failure(state, stage_id=result.stage_id, backend_id=result.backend_id, failure=result.failure, result_uri=result.result_uri)
            else:
                state["phase"] = "baseline_evaluation"

        elif phase == "baseline_evaluation":
            index = int(state["baseline_index"])
            baseline = state["plan"]["baselines"][index]
            backend = _backend(backends, str(baseline["backend_id"]))
            episode = _episode(state["baseline_results"][index]["episode"])
            result = backend.run_evaluation(
                EvaluationRequest(
                    campaign_id=str(state["campaign_id"]),
                    stage_id=str(baseline["evaluation_stage_id"]),
                    backend_id=backend.backend_id,
                    episode=episode,
                )
            )
            state["stage_ledger"].append(_ledger_row(kind="official_evaluation", stage_id=result.stage_id, backend_id=result.backend_id, status=result.status, accounting=result.accounting, result_uri=result.result_uri))
            state["baseline_results"][index]["evaluation"] = asdict(result)
            if _measured_stage(result.status):
                _validate_measured_episode_evaluation(
                    episode=episode, evaluation=result
                )
            if not _measured_stage(result.status):
                _stop_for_failure(state, stage_id=result.stage_id, backend_id=result.backend_id, failure=result.failure, result_uri=result.result_uri)
            else:
                state["baseline_index"] = index + 1
                state["phase"] = (
                    "baseline_episode"
                    if index + 1 < len(state["plan"]["baselines"])
                    else "round_start"
                )

        elif phase in {"parent_episode", "candidate_episode"}:
            current = state["current_round"]
            index = int(current["stage_backend_index"])
            backend_id = str(current["backend_order"][index])
            backend = _backend(backends, backend_id)
            is_candidate = phase == "candidate_episode"
            harness_value = current["revision"]["candidate_harness"] if is_candidate else current["parent_harness"]
            stage_key = "candidate_episodes" if is_candidate else "parent_episodes"
            result = backend.run_episode(
                EpisodeRequest(
                    campaign_id=str(state["campaign_id"]),
                    stage_id=str(current["stage_ids"][stage_key][backend_id]),
                    backend_id=backend.backend_id,
                    harness=_harness(harness_value, label=f"{stage_key} harness"),
                    task_ids=tuple(current["comparison_windows"][backend_id]),
                    purpose="development_comparison",
                    frozen=False,
                )
            )
            state["stage_ledger"].append(_ledger_row(kind="episode", stage_id=result.stage_id, backend_id=result.backend_id, status=result.status, accounting=result.accounting, result_uri=result.result_uri))
            current[stage_key][backend_id] = asdict(result)
            if not _measured_stage(result.status):
                _stop_for_failure(state, stage_id=result.stage_id, backend_id=result.backend_id, failure=result.failure, result_uri=result.result_uri)
            else:
                index += 1
                if index < len(current["backend_order"]):
                    current["stage_backend_index"] = index
                else:
                    current["stage_backend_index"] = 0
                    state["phase"] = (
                        "candidate_evaluation"
                        if is_candidate
                        else "parent_evaluation"
                    )

        elif phase in {"parent_evaluation", "candidate_evaluation"}:
            current = state["current_round"]
            index = int(current["stage_backend_index"])
            backend_id = str(current["backend_order"][index])
            backend = _backend(backends, backend_id)
            is_candidate = phase == "candidate_evaluation"
            prefix = "candidate" if is_candidate else "parent"
            episode_key = f"{prefix}_episodes"
            evaluation_key = f"{prefix}_evaluations"
            stage_key = f"{prefix}_evaluations"
            episode = _episode(current[episode_key][backend_id])
            result = backend.run_evaluation(
                EvaluationRequest(
                    campaign_id=str(state["campaign_id"]),
                    stage_id=str(current["stage_ids"][stage_key][backend_id]),
                    backend_id=backend.backend_id,
                    episode=episode,
                )
            )
            state["stage_ledger"].append(_ledger_row(kind="official_evaluation", stage_id=result.stage_id, backend_id=result.backend_id, status=result.status, accounting=result.accounting, result_uri=result.result_uri))
            current[evaluation_key][backend_id] = asdict(result)
            if _measured_stage(result.status):
                _validate_measured_episode_evaluation(
                    episode=episode, evaluation=result
                )
            if not _measured_stage(result.status):
                _stop_for_failure(state, stage_id=result.stage_id, backend_id=result.backend_id, failure=result.failure, result_uri=result.result_uri)
            else:
                index += 1
                if index < len(current["backend_order"]):
                    current["stage_backend_index"] = index
                else:
                    current["stage_backend_index"] = 0
                    evaluations = current[evaluation_key]
                    partial_window = any(
                        _evaluation(value).status == "partial"
                        for value in evaluations.values()
                    )
                    investigate_partial = bool(
                        state["plan"].get(
                            "investigate_partial_windows", False
                        )
                    )
                    parent_partial_window = is_candidate and any(
                        _evaluation(value).status == "partial"
                        for value in current["parent_evaluations"].values()
                    )
                    if is_candidate and (
                        partial_window or parent_partial_window
                    ):
                        _finish_round(
                            state,
                            selection=_incomplete_candidate_comparison_selection(
                                parents=current["parent_evaluations"],
                                candidates=current["candidate_evaluations"],
                            ),
                        )
                    elif partial_window and not investigate_partial:
                        _finish_round(
                            state,
                            selection=_incomplete_window_selection(
                                evaluations=evaluations,
                                candidate=False,
                            ),
                        )
                    elif partial_window:
                        evidence_by_backend = {
                            name: _episode(value)
                            for name, value in current[
                                "parent_episodes"
                            ].items()
                        }
                        evaluations_by_backend = {
                            name: _evaluation(value)
                            for name, value in current[
                                "parent_evaluations"
                            ].items()
                        }
                        parent_harness = _harness(
                            current["parent_harness"],
                            label="round parent",
                        )
                        _validate_revision_windows(
                            parent_harness=parent_harness,
                            evidence_by_backend=evidence_by_backend,
                            evaluations_by_backend=evaluations_by_backend,
                            investigate_partial_windows=True,
                        )
                        active_backend_id = str(
                            current["active_backend_id"]
                        )
                        active_backend = _backend(
                            backends, active_backend_id
                        )
                        active_task_id = str(current["active_task_id"])
                        active_available = (
                            active_backend.active_revision_source_available(
                                episode=evidence_by_backend[
                                    active_backend_id
                                ],
                                evaluation=evaluations_by_backend[
                                    active_backend_id
                                ],
                                task_id=active_task_id,
                                parent_harness=parent_harness,
                            )
                        )
                        if type(active_available) is not bool:
                            raise ResearchCampaignError(
                                "active revision source admission must return a boolean"
                            )
                        if not active_available:
                            selection = _incomplete_window_selection(
                                evaluations=evaluations,
                                candidate=False,
                            )
                            selection.update(
                                {
                                    "reason": "partial_window_active_task_unavailable",
                                    "revision_eligible": False,
                                    "active_backend_id": active_backend_id,
                                    "active_task_id": active_task_id,
                                }
                            )
                            _finish_round(state, selection=selection)
                        else:
                            state["phase"] = "revision"
                    else:
                        state["phase"] = "selection" if is_candidate else "revision"

        elif phase == "revision":
            current = state["current_round"]
            active_backend_id = str(current["active_backend_id"])
            backend = _backend(backends, active_backend_id)
            evidence_by_backend = {
                backend_id: _episode(value)
                for backend_id, value in current["parent_episodes"].items()
            }
            evaluations_by_backend = {
                backend_id: _evaluation(value)
                for backend_id, value in current["parent_evaluations"].items()
            }
            parent_harness = _harness(
                current["parent_harness"], label="round parent"
            )
            _validate_revision_windows(
                parent_harness=parent_harness,
                evidence_by_backend=evidence_by_backend,
                evaluations_by_backend=evaluations_by_backend,
                investigate_partial_windows=bool(
                    state["plan"].get(
                        "investigate_partial_windows", False
                    )
                ),
            )
            investigate_partial = bool(
                state["plan"].get("investigate_partial_windows", False)
            )
            observe_partial_candidates = bool(
                state["plan"].get("observe_partial_candidates", False)
            )
            partial_parent = any(
                evaluation.status == "partial"
                for evaluation in evaluations_by_backend.values()
            )
            if partial_parent and not backend.active_revision_source_available(
                episode=evidence_by_backend[active_backend_id],
                evaluation=evaluations_by_backend[active_backend_id],
                task_id=str(current["active_task_id"]),
                parent_harness=parent_harness,
            ):
                raise ResearchCampaignError(
                    "partial revision phase lost its active Worker evidence"
                )
            revision_stage_id = str(current["stage_ids"]["revision"])
            result = backend.run_revision(
                RevisionRequest(
                    campaign_id=str(state["campaign_id"]),
                    stage_id=revision_stage_id,
                    backend_id=backend.backend_id,
                    parent_harness=parent_harness,
                    parent_episode=evidence_by_backend[active_backend_id],
                    parent_evaluation=evaluations_by_backend[active_backend_id],
                    active_task_id=str(current["active_task_id"]),
                    research_memory=_memory(state.get("research_memory"), label="research memory"),
                    options=dict(current["revision_options"]),
                    evidence_by_backend=evidence_by_backend,
                    evaluations_by_backend=evaluations_by_backend,
                    investigate_partial_windows=(
                        investigate_partial and partial_parent
                    ),
                    related_completed_round=_latest_related_completed_round(
                        state
                    ),
                    seed_related_completed_rounds=_seed_related_completed_rounds(
                        current["revision_options"]
                    ),
                )
            )
            _validate_revision_outcome_identity(
                result,
                stage_id=revision_stage_id,
                backend_id=backend.backend_id,
                parent_harness=parent_harness,
            )
            state["stage_ledger"].append(_ledger_row(kind="revision", stage_id=result.stage_id, backend_id=result.backend_id, status=result.status, accounting=result.accounting, result_uri=result.result_uri))
            current["revision"] = asdict(result)
            failed_memory_valid = (
                _failed_revision_memory_is_valid(result)
                if result.status == "failed"
                else False
            )
            if result.status == "failed" and result.retained_memory is not None and not failed_memory_valid:
                _stop_for_failure(
                    state,
                    stage_id=result.stage_id,
                    backend_id=result.backend_id,
                    failure={
                        "kind": "invalid_failed_revision_research_memory",
                        "revision_failure": dict(result.failure or {}),
                    },
                    result_uri=result.result_uri,
                )
            elif result.retained_memory is not None:
                state["research_memory"] = asdict(result.retained_memory)
            elif state.get("research_memory") is not None:
                _stop_for_failure(state, stage_id=result.stage_id, backend_id=result.backend_id, failure={"kind": "declared_research_memory_not_retained"}, result_uri=result.result_uri)
            qualified_failure_selection = qualified_revision_failure_selection(
                result,
                retained_memory_valid=failed_memory_valid,
            )
            if state["status"] == "stopped":
                pass
            elif result.status == "abstained" and result.decision == "ABSTAIN":
                _finish_round(state, selection={"selected": "parent", "reason": "ABSTAIN", "comparison_run": False, "claim_outside_window": False})
            elif result.status == "revised_unscored" and result.decision == "ACT" and result.candidate_harness is not None:
                if partial_parent and not observe_partial_candidates:
                    selection = _incomplete_window_selection(
                        evaluations=current["parent_evaluations"],
                        candidate=False,
                    )
                    selection.update(
                        {
                            "reason": "partial_parent_revision_act_archived",
                            "revision_run": True,
                            "revision_decision": "ACT",
                            "candidate_admitted": True,
                            "candidate_archived": True,
                            "candidate_observed": False,
                            "candidate_promotable": False,
                        }
                    )
                    _finish_round(state, selection=selection)
                else:
                    state["phase"] = "candidate_episode"
            elif qualified_failure_selection is not None:
                _record_continued_revision_failure(state, result=result)
                _finish_round(state, selection=qualified_failure_selection)
            else:
                _stop_for_failure(state, stage_id=result.stage_id, backend_id=result.backend_id, failure=result.failure or {"kind": "revision_not_admitted"}, result_uri=result.result_uri)

        elif phase == "freeze_episode":
            index = int(state["freeze_index"])
            freezes = state["plan"]["freeze"]
            if index >= len(freezes):
                state["phase"] = "terminal_comparison"
            else:
                freeze = freezes[index]
                backend = _backend(backends, str(freeze["backend_id"]))
                result = backend.run_episode(EpisodeRequest(campaign_id=str(state["campaign_id"]), stage_id=str(freeze["episode_stage_id"]), backend_id=backend.backend_id, harness=_harness(state["research_parent"], label="frozen research parent"), task_ids=tuple(freeze["task_ids"]), purpose="terminal_freeze", frozen=True))
                state["stage_ledger"].append(_ledger_row(kind="episode", stage_id=result.stage_id, backend_id=result.backend_id, status=result.status, accounting=result.accounting, result_uri=result.result_uri))
                state["freeze_results"].append({"backend_id": backend.backend_id, "episode": asdict(result), "evaluation": None})
                if not _measured_stage(result.status):
                    _stop_for_failure(state, stage_id=result.stage_id, backend_id=result.backend_id, failure=result.failure, result_uri=result.result_uri)
                else:
                    state["phase"] = "freeze_evaluation"

        elif phase == "freeze_evaluation":
            index = int(state["freeze_index"])
            freeze = state["plan"]["freeze"][index]
            backend = _backend(backends, str(freeze["backend_id"]))
            episode = _episode(state["freeze_results"][index]["episode"])
            result = backend.run_evaluation(EvaluationRequest(campaign_id=str(state["campaign_id"]), stage_id=str(freeze["evaluation_stage_id"]), backend_id=backend.backend_id, episode=episode))
            state["stage_ledger"].append(_ledger_row(kind="official_evaluation", stage_id=result.stage_id, backend_id=result.backend_id, status=result.status, accounting=result.accounting, result_uri=result.result_uri))
            state["freeze_results"][index]["evaluation"] = asdict(result)
            if _measured_stage(result.status):
                _validate_measured_episode_evaluation(
                    episode=episode, evaluation=result
                )
            if not _measured_stage(result.status):
                _stop_for_failure(state, stage_id=result.stage_id, backend_id=result.backend_id, failure=result.failure, result_uri=result.result_uri)
            else:
                state["freeze_index"] = index + 1
                state["phase"] = (
                    "terminal_comparison"
                    if index + 1 == len(state["plan"]["freeze"])
                    else "freeze_episode"
                )
        else:
            raise ResearchCampaignError(f"unsupported campaign phase: {phase}")
    except Exception as exc:  # stage boundary retains failure; never retries.
        if isinstance(exc, ResearchCampaignError):
            failure = {"kind": "campaign_stage_error", "message": str(exc)}
        else:
            failure = {"kind": "backend_exception", "exception_type": type(exc).__name__, "message": str(exc)}
        current = state.get("current_round")
        if isinstance(current, Mapping):
            if phase == "revision":
                backend_id = str(current.get("active_backend_id"))
            else:
                order = current.get("backend_order")
                index = current.get("stage_backend_index", 0)
                backend_id = (
                    str(order[index])
                    if isinstance(order, list)
                    and type(index) is int
                    and 0 <= index < len(order)
                    else "unknown"
                )
            stage_id = phase
            if isinstance(current.get("stage_ids"), Mapping):
                if phase == "revision":
                    stage_id = str(current["stage_ids"]["revision"])
                else:
                    key = {
                        "parent_episode": "parent_episodes",
                        "parent_evaluation": "parent_evaluations",
                        "candidate_episode": "candidate_episodes",
                        "candidate_evaluation": "candidate_evaluations",
                    }.get(phase)
                    if key is not None:
                        stage_id = str(
                            current["stage_ids"][key].get(backend_id, phase)
                        )
        elif phase.startswith("baseline_"):
            baseline_index = int(state.get("baseline_index", 0))
            baselines = state["plan"]["baselines"]
            if baseline_index < len(baselines):
                baseline = baselines[baseline_index]
                backend_id = str(baseline["backend_id"])
                stage_id = str(
                    baseline[
                        "episode_stage_id"
                        if phase == "baseline_episode"
                        else "evaluation_stage_id"
                    ]
                )
            else:
                backend_id = "unknown"
                stage_id = phase
        elif phase.startswith("freeze_"):
            freeze_index = int(state.get("freeze_index", 0))
            freezes = state["plan"]["freeze"]
            if freeze_index < len(freezes):
                freeze = freezes[freeze_index]
                backend_id = str(freeze["backend_id"])
                stage_id = str(
                    freeze[
                        "episode_stage_id"
                        if phase == "freeze_episode"
                        else "evaluation_stage_id"
                    ]
                )
            else:
                backend_id = "unknown"
                stage_id = phase
        else:
            backend_id = "campaign"
            stage_id = phase
        _stop_for_failure(state, stage_id=stage_id, backend_id=backend_id, failure=failure)
    return _persist_state(path, state)


def run_campaign(*, state_path: str | Path, backends: Mapping[str, CampaignBackend], max_stages: int | None = None) -> dict[str, object]:
    """Advance synchronously until terminal state or an optional stage limit."""

    if max_stages is not None and (type(max_stages) is not int or max_stages < 1):
        raise ResearchCampaignError("max_stages must be a positive integer")
    completed = 0
    while True:
        state = _read_object(Path(state_path).expanduser().resolve(), label="campaign state")
        if state.get("status") != "running" or (max_stages is not None and completed >= max_stages):
            return state
        state = advance_campaign(state_path=state_path, backends=backends)
        completed += 1


class QuantCodeEvalBackend:
    """Concrete adapter over the retained QuantCodeEval execution primitives."""

    backend_id = "quantcodeeval"

    def __init__(self, config: Mapping[str, object], *, command_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run) -> None:
        self.config = dict(config)
        self.command_runner = command_runner
        configured = self.config.get("backend_id", self.backend_id)
        if configured != self.backend_id:
            raise ResearchCampaignError("QuantCodeEval backend_id differs")
        self.run_root = Path(_text(self.config.get("run_root"), label="QCE run_root")).expanduser().resolve()
        self.panel_path = Path(_text(self.config.get("panel_path"), label="QCE panel_path")).expanduser().resolve()
        panel = _read_object(self.panel_path, label="QCE campaign panel")
        roles = panel.get("research_roles")
        if not isinstance(roles, Mapping):
            raise ResearchCampaignError("QCE panel has no research_roles")
        self.development_tasks = _task_ids(roles.get("development"), label="QCE development tasks")
        self.evaluation_tasks = _task_ids(
            roles.get("evaluation_only_this_cycle"),
            label="QCE evaluation tasks",
            allow_empty=True,
        )
        self.all_tasks = tuple(row["task_id"] for key in ("optimize", "held_out") for row in panel.get(key, []) if isinstance(row, Mapping) and isinstance(row.get("task_id"), str))
        if set(self.all_tasks) != set(self.development_tasks) | set(self.evaluation_tasks):
            raise ResearchCampaignError("QCE panel roles do not partition its tasks")
        raw_routes = self.config.get("replay_routes")
        if not isinstance(raw_routes, Mapping):
            raise ResearchCampaignError("QCE backend requires replay_routes")
        self.replay_routes = dict(raw_routes)
        self.condition_id = _text(
            self.config.get("condition_id"), label="QCE declared condition_id"
        )
        self.condition_projection = {
            key: self.config.get(key)
            for key in (
                "config_path",
                "panel_path",
                "deployment_root",
                "worker_image_ref",
                "proxy_image_ref",
                "verifier_image_ref",
                "development_max_iterations",
                "candidate_development_max_iterations_ceiling",
                "concurrency",
            )
        }
        if "replay_config_path" in self.config:
            # The verifier-only replay may need a condition-specific config
            # key that the strict Worker/Evolver loader must never receive.
            self.condition_projection["replay_config_path"] = self._path(
                "replay_config_path"
            ).as_posix()

    def _path(self, key: str) -> Path:
        return Path(_text(self.config.get(key), label=f"QCE {key}")).expanduser().resolve()

    def _replay_config_path(self) -> Path:
        return self._path(
            "replay_config_path" if "replay_config_path" in self.config else "config_path"
        )

    def _verify_harness(self, harness: HarnessRef) -> Path:
        path = Path(harness.artifact_uri).expanduser().resolve()
        if path.is_symlink() or not path.is_dir():
            raise ResearchCampaignError(f"QCE harness is missing or unsafe: {path}")
        return path

    def _validated_supplemental_accounting(
        self,
        *,
        manifests: Sequence[Mapping[str, object]],
        cells: Mapping[str, Mapping[str, object]],
    ) -> tuple[Mapping[str, object], ...]:
        rows: list[Mapping[str, object]] = []
        seen_tasks: set[str] = set()
        source_panels: set[str] = set()
        for manifest in manifests:
            raw = manifest.get("supplemental_accounting")
            if raw is None:
                continue
            if not isinstance(raw, Mapping) or not (
                raw.get("protocol")
                == "quantcodeeval-panel-supplemental-accounting-v1"
                and raw.get("reason") == "retained_replaced_failed_attempts"
                and raw.get("excluded_from_selected_cells") is True
            ):
                raise ResearchCampaignError(
                    "QCE panel supplemental accounting contract differs"
                )
            source_panel = _text(
                raw.get("source_panel_run_id"),
                label="QCE supplemental source panel run ID",
            )
            raw_rows = raw.get("cells")
            if not isinstance(raw_rows, list) or not raw_rows:
                raise ResearchCampaignError(
                    "QCE panel supplemental accounting requires retained cells"
                )
            source_panels.add(source_panel)
            for raw_row in raw_rows:
                if not isinstance(raw_row, Mapping):
                    raise ResearchCampaignError(
                        "QCE supplemental accounting cell must be an object"
                    )
                task_id = _text(
                    raw_row.get("task_id"),
                    label="QCE supplemental accounting task ID",
                )
                source_child = _text(
                    raw_row.get("source_child_run_id"),
                    label=f"{task_id} supplemental source child run ID",
                )
                accounting = raw_row.get("actual_accounting")
                selected = cells.get(task_id)
                recovery = (
                    selected.get("recovery_provenance")
                    if isinstance(selected, Mapping)
                    else None
                )
                if (
                    task_id in seen_tasks
                    or not isinstance(accounting, Mapping)
                    or not isinstance(selected, Mapping)
                    or not isinstance(recovery, Mapping)
                    or recovery.get("source_panel_run_id") != source_panel
                    or recovery.get("source_child_run_id") != source_child
                    or recovery.get("replacement_run_id")
                    != selected.get("child_run_id")
                    or recovery.get("reason")
                    != "empty_model_response_after_fallback"
                    or recovery.get("single_replacement") is not True
                    or selected.get("child_run_id") == source_child
                ):
                    raise ResearchCampaignError(
                        f"QCE supplemental accounting provenance differs for {task_id}"
                    )
                seen_tasks.add(task_id)
                rows.append(
                    {
                        "task_id": task_id,
                        "source_panel_run_id": source_panel,
                        "source_child_run_id": source_child,
                        "actual_accounting": dict(accounting),
                    }
                )
        recovered_tasks = {
            task_id
            for task_id, cell in cells.items()
            if isinstance(cell, Mapping)
            and isinstance(cell.get("recovery_provenance"), Mapping)
        }
        if recovered_tasks != seen_tasks:
            raise ResearchCampaignError(
                "QCE recovered cells and supplemental accounting tasks differ"
            )
        if rows and not source_panels:
            raise ResearchCampaignError("QCE supplemental source panel is missing")
        return tuple(rows)

    def _episode_accounting(
        self,
        cells: Mapping[str, Mapping[str, object]],
        wall_time: float,
        *,
        supplemental_rows: Sequence[Mapping[str, object]] = (),
    ) -> dict[str, object]:
        detail_fields = (
            "provider_requests",
            "completed_requests",
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "turns",
            "tool_calls",
            "tool_errors",
        )
        total = {field: 0 for field in detail_fields}
        field_complete = {field: True for field in detail_fields}
        field_complete["logical_requests"] = False
        cost = Decimal("0")
        cost_complete = True
        complete = True
        for cell in cells.values():
            native = cell.get("native")
            if isinstance(native, Mapping):
                cell = native
            accounting = cell.get("actual_accounting")
            observation = cell.get("observation")
            if not isinstance(accounting, Mapping) or not isinstance(observation, Mapping):
                complete = False
                cost_complete = False
                for field in detail_fields:
                    field_complete[field] = False
                continue
            mappings = {"provider_requests": "request_count", "completed_requests": "completed_request_count", "input_tokens": "input_tokens", "output_tokens": "output_tokens", "total_tokens": "total_tokens"}
            for target, source in mappings.items():
                value = accounting.get(source)
                if type(value) is not int or value < 0:
                    complete = False
                    field_complete[target] = False
                else:
                    total[target] += value
            execution = observation.get("worker_execution")
            summary = execution.get("summary") if isinstance(execution, Mapping) else None
            for field in ("turns", "tool_calls", "tool_errors"):
                value = summary.get(field) if isinstance(summary, Mapping) else None
                if type(value) is not int or value < 0:
                    complete = False
                    field_complete[field] = False
                else:
                    total[field] += value
            raw_cost = accounting.get("provider_cost_usd")
            if accounting.get("cost_complete") is not True or isinstance(raw_cost, bool) or not isinstance(raw_cost, (int, float)) or raw_cost < 0:
                cost_complete = False
            known_cost = _known_accounted_cost(accounting)
            if known_cost is not None:
                cost += known_cost
        supplemental_totals = {
            field: 0
            for field in (
                "provider_requests",
                "completed_requests",
                "input_tokens",
                "output_tokens",
                "total_tokens",
            )
        }
        supplemental_cost = Decimal("0")
        supplemental_cost_complete = True
        supplemental_counts_complete = True
        source_panel_ids: list[str] = []
        for row in supplemental_rows:
            accounting = row.get("actual_accounting")
            if not isinstance(accounting, Mapping):
                raise ResearchCampaignError(
                    "validated QCE supplemental accounting row lost accounting"
                )
            source_panel = _text(
                row.get("source_panel_run_id"),
                label="validated QCE supplemental source panel run ID",
            )
            if source_panel not in source_panel_ids:
                source_panel_ids.append(source_panel)
            mappings = {
                "provider_requests": "request_count",
                "completed_requests": "completed_request_count",
                "input_tokens": "input_tokens",
                "output_tokens": "output_tokens",
                "total_tokens": "total_tokens",
            }
            for target, source in mappings.items():
                value = accounting.get(source)
                if type(value) is not int or value < 0:
                    supplemental_counts_complete = False
                    field_complete[target] = False
                else:
                    supplemental_totals[target] += value
                    total[target] += value
            known_cost = _known_accounted_cost(accounting)
            if known_cost is None:
                supplemental_cost_complete = False
            else:
                supplemental_cost += known_cost
                cost += known_cost
            if accounting.get("cost_complete") is not True:
                supplemental_cost_complete = False
        if supplemental_rows:
            complete = False
            for field in ("turns", "tool_calls", "tool_errors"):
                field_complete[field] = False
        cost_complete = cost_complete and supplemental_cost_complete
        supplemental = {
            **supplemental_totals,
            "included_once": bool(supplemental_rows),
            "reason": (
                "retained_replaced_failed_attempts"
                if supplemental_rows
                else None
            ),
            "source_panel_run_ids": source_panel_ids,
            "task_count": len(supplemental_rows),
            "provider_cost_usd": (
                float(supplemental_cost)
                if supplemental_cost_complete
                else None
            ),
            "accounted_provider_cost_usd": float(supplemental_cost),
            "cost_complete": supplemental_cost_complete,
            "count_and_token_detail_complete": supplemental_counts_complete,
            "worker_execution_detail_included": False,
            "detail_complete": not supplemental_rows,
        }
        return {
            **total,
            "logical_requests": None,
            "provider_retries": None,
            "component_checks": 0,
            "wall_time_seconds": wall_time,
            "provider_cost_usd": float(cost) if cost_complete else None,
            "accounted_provider_cost_usd": float(cost),
            "cost_complete": cost_complete,
            "detail_complete": complete,
            "field_complete": field_complete,
            "supplemental_accounting": supplemental,
        }

    def _copy_evidence_member(
        self, *, source: Path, destination: Path, label: str
    ) -> None:
        supplied = source.expanduser()
        if supplied.is_symlink() or not supplied.exists():
            raise ResearchCampaignError(f"{label} is missing or unsafe: {supplied}")
        resolved = supplied.resolve()
        members = [resolved, *resolved.rglob("*")] if resolved.is_dir() else [resolved]
        for member in members:
            if member.is_symlink() or (not member.is_file() and not member.is_dir()):
                raise ResearchCampaignError(f"{label} contains an unsafe member: {member}")
            if member.is_file():
                try:
                    member.read_text(encoding="utf-8")
                except UnicodeDecodeError as exc:
                    raise ResearchCampaignError(
                        f"{label} contains non-text public evidence: {member}"
                    ) from exc
        if destination.exists() or destination.is_symlink():
            raise ResearchCampaignError(
                f"new {label} destination already exists: {destination}"
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        if resolved.is_dir():
            shutil.copytree(resolved, destination, copy_function=shutil.copy2)
        else:
            shutil.copy2(resolved, destination)

    def _copy_public_task_contract(
        self, *, source: Path, destination: Path, label: str
    ) -> bool:
        """Copy public task definition/source without duplicating its data tree."""

        supplied = source.expanduser()
        if supplied.is_symlink() or not supplied.is_dir():
            raise ResearchCampaignError(f"{label} is missing or unsafe: {supplied}")
        if destination.exists() or destination.is_symlink():
            raise ResearchCampaignError(
                f"new {label} destination already exists: {destination}"
            )
        resolved = supplied.resolve()
        copied_files = 0
        destination.mkdir(parents=True)
        for member in sorted(resolved.rglob("*")):
            relative = member.relative_to(resolved)
            if relative.parts[:2] == ("environment", "data"):
                continue
            if member.is_symlink() or (
                not member.is_file() and not member.is_dir()
            ):
                raise ResearchCampaignError(
                    f"{label} contains an unsafe member: {member}"
                )
            target = destination / relative
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            try:
                member.read_text(encoding="utf-8")
            except UnicodeDecodeError as exc:
                raise ResearchCampaignError(
                    f"{label} contains non-text public evidence: {member}"
                ) from exc
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(member, target)
            copied_files += 1
        if copied_files == 0:
            shutil.rmtree(destination)
            return False
        return True

    def _evidence_record(
        self,
        *,
        stage_id: str,
        task_id: str,
        native: Mapping[str, object],
        snapshot_root: Path,
    ) -> dict[str, object]:
        root = Path(
            _text(native.get("child_run_dir"), label=f"{task_id} evidence root")
        )
        observation = native.get("observation")
        worker_evidence = (
            observation.get("worker_evidence")
            if isinstance(observation, Mapping)
            else None
        )
        execution_source = native.get("execution_source")
        if not isinstance(worker_evidence, Mapping) or not isinstance(
            execution_source, Mapping
        ):
            raise ResearchCampaignError(
                f"{task_id} completed QCE cell lacks Worker evidence/source"
            )
        attempt_id = _text(
            observation.get("attempt_id"), label=f"{task_id} attempt ID"
        )

        def source_member(name: str) -> Path:
            return root / _text(
                worker_evidence.get(name),
                label=f"{task_id} Worker evidence {name}",
            )

        if snapshot_root.exists() or snapshot_root.is_symlink():
            raise ResearchCampaignError(
                f"new QCE evidence snapshot already exists: {snapshot_root}"
            )
        _text(
            execution_source.get("public_root"),
            label=f"{task_id} declared public data root",
        )
        worker_execution_path = source_member("worker_execution_uri")
        worker_execution = _read_object(
            worker_execution_path,
            label=f"{task_id} Worker execution",
        )
        observed_execution = observation.get("worker_execution")
        execution_summary = worker_execution.get("summary")
        if not (
            worker_execution.get("attempt_id") == attempt_id
            and isinstance(observed_execution, Mapping)
            and observed_execution.get("attempt_id") == attempt_id
            and isinstance(execution_summary, Mapping)
            and observed_execution.get("summary") == execution_summary
        ):
            raise ResearchCampaignError(
                f"{task_id} Worker execution identity or inline summary differs"
            )
        normalized_summary = _json_copy(
            dict(execution_summary),
            label=f"{task_id} Worker execution summary",
        )
        assert isinstance(normalized_summary, dict)
        summary_uri = worker_evidence.get("summary_uri")
        derive_process_summary = summary_uri is None
        public_task = root / "public-observation" / "tasks" / task_id
        public_data = public_task / "environment" / "data"
        has_dedicated_public_data = public_data.is_dir()
        if not has_dedicated_public_data:
            public_data = public_task
        sources = {
            "attempt_identity": root / "attempts" / attempt_id / "attempt.json",
            "artifact_root": source_member("artifact_dir"),
            "artifact_manifest": worker_execution_path,
            "public_data": public_data,
            "worker_trace": source_member("raw_trace_uri"),
            "worker_final": source_member("final_text_uri"),
            "observation_result": Path(
                _text(
                    native.get("observation_result_path"),
                    label=f"{task_id} observation result",
                )
            ),
        }
        if not derive_process_summary:
            sources["process_summary"] = source_member("summary_uri")
        destinations = {
            "attempt_identity": snapshot_root / "episode" / "attempt.json",
            "artifact_root": snapshot_root / "observation" / "artifacts",
            "artifact_manifest": snapshot_root
            / "observation"
            / "artifact-manifest.json",
            "public_data": snapshot_root / "public" / "data",
            "worker_trace": snapshot_root / "observation" / "worker-trace.jsonl",
            "worker_final": snapshot_root / "observation" / "worker-final.txt",
            "process_summary": snapshot_root
            / "observation"
            / "process-summary.json",
            "observation_result": snapshot_root
            / "observation"
            / "worker-observation-result.json",
        }
        if has_dedicated_public_data:
            destinations["public_task"] = snapshot_root / "public" / "task"
        for role, source in sources.items():
            self._copy_evidence_member(
                source=source,
                destination=destinations[role],
                label=f"{task_id} {role}",
            )
        if has_dedicated_public_data:
            copied_public_task = self._copy_public_task_contract(
                source=public_task,
                destination=destinations["public_task"],
                label=f"{task_id} public_task",
            )
            if not copied_public_task:
                destinations.pop("public_task")
        if derive_process_summary:
            _atomic_json(
                destinations["process_summary"],
                {
                    "schema_version": 1,
                    "source": "worker_execution.summary",
                    "source_worker_execution_uri": _text(
                        worker_evidence.get("worker_execution_uri"),
                        label=f"{task_id} Worker execution URI",
                    ),
                    "attempt_id": attempt_id,
                    "summary": normalized_summary,
                },
            )
        artifact_root = destinations["artifact_root"]
        current_strategy = artifact_root / "strategy.py"
        if not current_strategy.is_file() or current_strategy.is_symlink():
            raise ResearchCampaignError(
                f"{task_id} QCE evidence has no regular strategy.py"
            )
        members = {
            **{role: path.resolve().as_posix() for role, path in destinations.items()},
            "current_strategy": current_strategy.resolve().as_posix(),
        }
        return {
            "schema_version": 1,
            "protocol": "research-campaign-evidence-record-v1",
            "backend_id": self.backend_id,
            "task_id": task_id,
            "stage_id": stage_id,
            "root_uri": snapshot_root.resolve().as_posix(),
            "members": members,
            "public_probe_refs": [
                "artifact_root",
                "public_data",
                "current_strategy",
            ],
            "official_evaluation_included": False,
        }

    @staticmethod
    def _missing_artifact_cell(cell: Mapping[str, object]) -> bool:
        """Recognize retained no-delivery outcomes, never a successful Worker."""
        observation = cell.get("observation")
        failure = (
            observation.get("failure")
            if isinstance(observation, Mapping)
            else None
        )
        evidence = (
            observation.get("worker_evidence")
            if isinstance(observation, Mapping)
            else None
        )
        official = (
            observation.get("official_evaluation")
            if isinstance(observation, Mapping)
            else None
        )
        missing_membership = bool(
            isinstance(failure, Mapping)
            and failure.get("exception_type")
            == "SandboxWorkerArtifactContractError"
            and failure.get("message")
            == "worker output membership differs from the benchmark contract: expected=['strategy.py'], found=[]"
        )
        provider_tool_cutoff = bool(
            isinstance(failure, Mapping)
            and failure.get("exception_type") == "SandboxInfrastructureError"
            and failure.get("phase") == "worker.command"
            and "Upstream error from BaseTen: HttpError: HTTP 400: Tool calls cutoff by max_tokens."
            in str(failure.get("message", ""))
            and isinstance(evidence, Mapping)
            and evidence.get("summary_uri")
            and evidence.get("raw_trace_uri")
            and isinstance(cell.get("actual_accounting"), Mapping)
            and cell["actual_accounting"].get("audit_complete") is True
            and cell["actual_accounting"].get("cost_complete") is True
        )
        official_worker_timeout = bool(
            isinstance(failure, Mapping)
            and failure.get("exception_type") == "SandboxWorkerTimeout"
            and failure.get("message")
            == "worker exceeded the official agent timeout (3600s)"
            and isinstance(evidence, Mapping)
            and evidence.get("command_uri")
            and evidence.get("proxy_audit_uri")
            and evidence.get("raw_trace_uri") is None
            and evidence.get("summary_uri") is None
            and isinstance(cell.get("actual_accounting"), Mapping)
            and cell["actual_accounting"].get("audit_complete") is True
            and cell["actual_accounting"].get("cost_complete") is True
            and isinstance(official, Mapping)
            and official.get("status") == "not_run"
            and official.get("reward") is None
            and official.get("score") is None
        )
        accounting = cell.get("actual_accounting")
        quarantined_proxy_finalize_timeout = bool(
            isinstance(failure, Mapping)
            and failure.get("exception_type") == "SandboxProxyError"
            and failure.get("message")
            == "proxy audit was incomplete: proxy audit finalize failed: exit 124"
            and isinstance(evidence, Mapping)
            and evidence.get("summary_uri")
            and evidence.get("raw_trace_uri")
            and evidence.get("final_text_uri")
            and evidence.get("command_uri")
            and evidence.get("proxy_audit_uri") is None
            and evidence.get("proxy_quarantine_uri")
            and evidence.get("proxy_unsealed_audit_uri")
            and isinstance(accounting, Mapping)
            and accounting.get("audit_present") is False
            and accounting.get("audit_complete") is False
            and accounting.get("cost_complete") is False
            and accounting.get("canonical_audit_uri") is None
            and accounting.get("provider_cost_usd") is None
            and accounting.get("request_count") is None
            and accounting.get("completed_request_count") is None
            and accounting.get("input_tokens") is None
            and accounting.get("output_tokens") is None
            and accounting.get("total_tokens") is None
            and accounting.get("quarantine_evidence_uri")
            == evidence.get("proxy_quarantine_uri")
            and accounting.get("unsealed_audit_uri")
            == evidence.get("proxy_unsealed_audit_uri")
            and isinstance(official, Mapping)
            and official.get("status") == "not_run"
            and official.get("reward") is None
            and official.get("score") is None
        )
        return bool(
            cell.get("state") == "worker_failed"
            and cell.get("exception") is None
            and isinstance(cell.get("actual_accounting"), Mapping)
            and isinstance(observation, Mapping)
            and observation.get("protocol")
            == "quantcodeeval-worker-observation-v1"
            and observation.get("status") == "worker_failed"
            and observation.get("worker_execution") is None
            and observation.get("parent_artifact_seed") is None
            and (
                missing_membership
                or provider_tool_cutoff
                or official_worker_timeout
                or quarantined_proxy_finalize_timeout
            )
            and isinstance(evidence, Mapping)
            and (
                evidence.get("artifact_paths") == []
                or (
                    official_worker_timeout
                    and isinstance(evidence.get("artifact_paths"), list)
                    and all(
                        isinstance(path, str) and path
                        for path in evidence["artifact_paths"]
                    )
                    and evidence.get("artifact_contract_uri") is None
                    and evidence.get("worker_execution_uri") is None
                )
            )
            and isinstance(official, Mapping)
            and official.get("status") == "not_run"
            and observation.get("benchmark_score_claimed") is False
        )

    def run_episode(self, request: EpisodeRequest) -> EpisodeEvidence:
        if request.backend_id != self.backend_id:
            raise ResearchCampaignError("QCE episode backend differs")
        worker = self._verify_harness(request.harness)
        root = self.run_root / "episodes" / request.stage_id
        result_path = root / EPISODE_FILE
        request_payload = _json_copy(
            asdict(request), label="QCE episode request"
        )
        assert isinstance(request_payload, dict)
        if result_path.is_file() and not result_path.is_symlink():
            retained = _read_object(result_path, label="QCE episode evidence")
            if retained.get("request") != request_payload:
                raise ResearchCampaignError("retained QCE episode request differs")
            return _episode(retained["episode"])
        requested = tuple(request.task_ids)
        if len(requested) != len(set(requested)) or not requested:
            raise ResearchCampaignError("QCE episode requires distinct tasks")
        groups: list[tuple[str, tuple[str, ...], bool]] = []
        if request.harness.worker_role == "initial":
            if set(requested) != set(self.all_tasks) or len(requested) != len(self.all_tasks):
                raise ResearchCampaignError("initial QCE baseline must run the complete panel")
            groups.append(("all", self.all_tasks, False))
        else:
            development = tuple(task for task in requested if task in self.development_tasks)
            evaluation = tuple(task for task in requested if task in self.evaluation_tasks)
            if len(development) + len(evaluation) != len(requested):
                raise ResearchCampaignError("QCE episode includes undeclared tasks")
            if development:
                groups.append(("development", development, False))
            if evaluation:
                if not request.frozen:
                    raise ResearchCampaignError("evaluation-only QCE tasks require a frozen harness")
                groups.append(("evaluation_only_this_cycle", evaluation, True))
        started = time.perf_counter()
        native_cells: dict[str, Mapping[str, object]] = {}
        native_manifests: list[Mapping[str, object]] = []
        failures: list[Mapping[str, object]] = []
        manifest_records: list[Mapping[str, object]] = []
        for split, task_ids, frozen in groups:
            configured_roots = self.config.get("episode_run_roots", {})
            configured_stage = (
                configured_roots.get(request.stage_id)
                if isinstance(configured_roots, Mapping)
                else None
            )
            configured_part = (
                configured_stage.get(split)
                if isinstance(configured_stage, Mapping)
                else None
            )
            part_root = (
                Path(str(configured_part)).expanduser().resolve()
                if configured_part is not None
                else root / "parts" / split
            )
            manifest = run_quantcodeeval_panel_observation(
                config_path=self._path("config_path"),
                worker_dir=worker,
                worker_role=request.harness.worker_role,
                panel_path=self.panel_path,
                deployment_root=self._path("deployment_root"),
                run_root=part_root,
                development_max_iterations=int(self.config["development_max_iterations"]),
                candidate_development_max_iterations_ceiling=int(self.config["candidate_development_max_iterations_ceiling"]),
                worker_image_ref=_text(self.config.get("worker_image_ref"), label="QCE worker image"),
                proxy_image_ref=_text(self.config.get("proxy_image_ref"), label="QCE proxy image"),
                research_split=split,
                concurrency=min(int(self.config.get("concurrency", 6)), len(task_ids)),
                candidate_frozen_for_evaluation=frozen,
                selected_task_ids=task_ids,
            )
            native_manifests.append(manifest)
            for cell in manifest.get("cells", []):
                if isinstance(cell, Mapping) and isinstance(cell.get("task_id"), str):
                    native_cells[str(cell["task_id"])] = dict(cell)
            manifest_status = manifest.get("status")
            manifest_record = {
                "split": split,
                "status": manifest_status,
                "manifest_uri": (part_root / "PANEL-OBSERVATION.json").as_posix(),
            }
            manifest_records.append(manifest_record)
            if manifest_status not in {"complete", "failed"}:
                failures.append(
                    {"kind": "qce_panel_not_terminal", **manifest_record}
                )
        if set(native_cells) != set(requested):
            failures.append({"kind": "episode_cell_set_mismatch", "expected": list(requested), "actual": sorted(native_cells)})
        for task_id, native in native_cells.items():
            observation = native.get("observation")
            development_worker = (
                observation.get("development_worker")
                if isinstance(observation, Mapping)
                else None
            )
            observed_source = (
                development_worker.get("source_worker_dir")
                if isinstance(development_worker, Mapping)
                else None
            )
            if (
                not isinstance(observation, Mapping)
                or observation.get("worker_role", "candidate")
                != request.harness.worker_role
                or not isinstance(observed_source, str)
                or Path(observed_source).expanduser().resolve() != worker
            ):
                failures.append(
                    {
                        "kind": "qce_observed_worker_package_mismatch",
                        "task_id": task_id,
                        "expected_worker_dir": worker.as_posix(),
                        "observed_worker_dir": observed_source,
                    }
                )
        supplemental_rows = self._validated_supplemental_accounting(
            manifests=native_manifests,
            cells=native_cells,
        )
        missing_tasks = [
            task_id
            for task_id in requested
            if task_id in native_cells
            and native_cells[task_id].get("state") != "complete"
        ]
        for task_id in missing_tasks:
            if not self._missing_artifact_cell(native_cells[task_id]):
                failures.append(
                    {
                        "kind": "qce_unqualified_missing_delivery",
                        "task_id": task_id,
                        "state": native_cells[task_id].get("state"),
                    }
                )
        if missing_tasks and all(
            record.get("status") == "complete" for record in manifest_records
        ):
            failures.append(
                {"kind": "qce_complete_manifest_contains_missing_delivery"}
            )
        if not missing_tasks and any(
            record.get("status") != "complete" for record in manifest_records
        ):
            failures.append(
                {"kind": "qce_failed_manifest_has_no_missing_delivery"}
            )
        cells: dict[str, Mapping[str, object]] = {}
        for task_id, native in native_cells.items():
            evidence_record = None
            if native.get("state") == "complete":
                try:
                    evidence_record = self._evidence_record(
                        stage_id=request.stage_id,
                        task_id=task_id,
                        native=native,
                        snapshot_root=root / "evidence" / task_id,
                    )
                except ResearchCampaignError as exc:
                    failures.append(
                        {
                            "kind": "qce_evidence_record_unavailable",
                            "task_id": task_id,
                            "message": str(exc),
                        }
                    )
            cells[task_id] = {
                "task_id": task_id,
                "evidence_record": evidence_record,
                "native": dict(native),
            }
        status = (
            "failed"
            if failures
            else "partial"
            if missing_tasks
            else "complete"
        )
        accounting = self._episode_accounting(
            cells,
            round(time.perf_counter() - started, 6),
            supplemental_rows=supplemental_rows,
        )
        failure = None
        if status == "partial":
            failure = {
                "kind": "qce_episode_partial_missing_artifacts",
                "declared_task_ids": list(requested),
                "scored_eligible_task_ids": [
                    task_id for task_id in requested if task_id not in missing_tasks
                ],
                "missing_task_ids": missing_tasks,
                "missing_official_metrics": {
                    task_id: None for task_id in missing_tasks
                },
                "manifest_records": manifest_records,
                "promotable": False,
            }
        elif status == "failed":
            failure = {"kind": "qce_episode_failed", "parts": failures}
        episode = EpisodeEvidence(stage_id=request.stage_id, backend_id=self.backend_id, harness=request.harness, task_ids=requested, condition_id=self.condition_id, status=status, cells=cells, accounting=accounting, result_uri=result_path.as_posix(), failure=failure)
        _write_or_reuse(result_path, {"schema_version": 1, "protocol": "research-campaign-qce-episode-v1", "request": request_payload, "condition": {"condition_id": self.condition_id, "settings": self.condition_projection}, "episode": asdict(episode)}, label="QCE episode evidence")
        return episode

    @staticmethod
    def _qualified_replay_failure(
        *, output: Path, task_id: str, attempt_id: str
    ) -> dict[str, object] | None:
        path = output / _QCE_REPLAY_FAILURE_FILE
        if not path.exists() and not path.is_symlink():
            return None
        failure = _read_object(path, label=f"{task_id} QCE replay failure")
        phase = failure.get("phase")
        if not (
            failure.get("schema_version") == 1
            and failure.get("protocol") == _QCE_REPLAY_FAILURE_PROTOCOL
            and failure.get("status") == "failed"
            and failure.get("task_id") == task_id
            and failure.get("attempt_id") == attempt_id
            and failure.get("failure_class") == "sandbox_infrastructure_error"
            and isinstance(phase, str)
            and phase in _QCE_PARTIAL_EVALUATOR_PHASES
            and failure.get("official_metric") is None
            and failure.get("verifier_method_invoked") is True
            and failure.get("zero_model_requests") is True
        ):
            raise ResearchCampaignError(
                f"{task_id} QCE replay failure is not a qualified evaluator runtime failure"
            )
        return {
            "kind": "qce_official_evaluation_failed",
            "stage": "verifier",
            "outcome": "failed",
            "task_id": task_id,
            "reason": "qualified_verifier_runtime_failure",
            "runtime_phase": phase,
            "official_metric": None,
            "output_uri": output.as_posix(),
            "automatic_retry": False,
        }

    def _task_metric(self, *, task_id: str, replay_path: Path) -> TaskMetric:
        replay = _read_object(replay_path, label=f"{task_id} QCE replay")
        rows = replay.get("results")
        if replay.get("zero_model_requests") is not True or not isinstance(rows, list):
            raise ResearchCampaignError("QCE replay is not zero-model aggregate")
        matches = [row for row in rows if isinstance(row, Mapping) and row.get("task_id") == task_id]
        if len(matches) != 1:
            raise ResearchCampaignError(f"QCE replay has no unique {task_id} row")
        row = matches[0]
        evidence = row.get("answer_free_evidence")
        score = row.get("score")
        families = evidence.get("property_families") if isinstance(evidence, Mapping) else None
        if not isinstance(score, Mapping) or not isinstance(families, Mapping) or not families:
            raise ResearchCampaignError("QCE replay lacks answer-free family totals")
        totals = {key: 0 for key in ("passed", "failed", "errors", "skipped", "total")}
        normalized_families: dict[str, Mapping[str, int]] = {}
        for family, raw in families.items():
            if not isinstance(raw, Mapping):
                raise ResearchCampaignError("QCE property family is invalid")
            normalized: dict[str, int] = {}
            for key in totals:
                value = raw.get(key)
                if type(value) is not int or value < 0:
                    raise ResearchCampaignError("QCE property-family count is invalid")
                normalized[key] = value
                totals[key] += value
            if sum(normalized[key] for key in ("passed", "failed", "errors", "skipped")) != normalized["total"]:
                raise ResearchCampaignError("QCE family outcomes do not equal total")
            normalized_families[str(family)] = normalized
        reward = score.get("reward")
        if reward not in {0, 0.0, 1, 1.0}:
            raise ResearchCampaignError("QCE replay reward is not binary")
        return TaskMetric(task_id=task_id, binary_reward=int(reward), passed=totals["passed"], failed=totals["failed"], errors=totals["errors"], skipped=totals["skipped"], total=totals["total"], contract_adjusted=row.get("contract_adjusted") is True, zero_model_requests=True, result_uri=replay_path.as_posix(), families=normalized_families)

    def _selection_projection(
        self, metrics: Mapping[str, TaskMetric], task_ids: Sequence[str]
    ) -> tuple[str, tuple[tuple[int, int], ...], dict[str, object]]:
        selected = tuple(metrics[task_id] for task_id in task_ids)
        equal_mean = sum(
            (Fraction(metric.passed, metric.total) for metric in selected),
            Fraction(),
        ) / len(selected)
        binary_successes = sum(metric.binary_reward for metric in selected)
        summary = {
            "binary_successes": binary_successes,
            "task_count": len(selected),
            "equal_task_mean": {
                "numerator": equal_mean.numerator,
                "denominator": equal_mean.denominator,
                "decimal": float(equal_mean),
            },
            "pooled_passed": sum(metric.passed for metric in selected),
            "pooled_total": sum(metric.total for metric in selected),
            "per_task": {
                metric.task_id: {
                    "binary_reward": metric.binary_reward,
                    "passed": metric.passed,
                    "total": metric.total,
                }
                for metric in selected
            },
        }
        return (
            "quantcodeeval_binary_successes_then_equal_task_test_fraction_then_earlier",
            ((binary_successes, len(selected)), (equal_mean.numerator, equal_mean.denominator)),
            summary,
        )

    def run_evaluation(self, request: EvaluationRequest) -> OfficialEvaluation:
        if (
            request.backend_id != self.backend_id
            or request.episode.status not in {"complete", "partial"}
        ):
            raise ResearchCampaignError(
                "QCE evaluation requires a measured QCE episode"
            )
        root = self.run_root / "evaluations" / request.stage_id
        result_path = root / EVALUATION_FILE
        request_payload = {"campaign_id": request.campaign_id, "stage_id": request.stage_id, "backend_id": request.backend_id, "episode_stage_id": request.episode.stage_id, "harness_id": request.episode.harness.harness_id, "task_ids": list(request.episode.task_ids), "condition_id": request.episode.condition_id}
        if result_path.exists() or result_path.is_symlink():
            if result_path.is_symlink() or not result_path.is_file():
                raise ResearchCampaignError(
                    f"retained QCE official evaluation is unsafe: {result_path}"
                )
            retained = _read_object(result_path, label="QCE official evaluation")
            if retained.get("request") != request_payload:
                raise ResearchCampaignError("retained QCE evaluation request differs")
            return _evaluation(retained["evaluation"])
        started = time.perf_counter()
        metrics: dict[str, TaskMetric] = {}
        missing_delivery_tasks: list[str] = []
        evaluation_failures: list[dict[str, object]] = []
        for task_id in request.episode.task_ids:
            route = self.replay_routes.get(task_id)
            cell = request.episode.cells.get(task_id)
            if not isinstance(route, Mapping) or not isinstance(cell, Mapping):
                raise ResearchCampaignError(f"QCE replay route/cell missing for {task_id}")
            native_cell = cell.get("native")
            if not isinstance(native_cell, Mapping):
                raise ResearchCampaignError(
                    f"QCE episode cell lacks native evidence for {task_id}"
                )
            if native_cell.get("state") != "complete":
                if (
                    request.episode.status != "partial"
                    or not self._missing_artifact_cell(native_cell)
                    or cell.get("evidence_record") is not None
                ):
                    raise ResearchCampaignError(
                        f"QCE missing cell is not a qualified partial measurement: {task_id}"
                    )
                missing_delivery_tasks.append(task_id)
                continue
            if not isinstance(cell.get("evidence_record"), Mapping):
                raise ResearchCampaignError(
                    f"QCE completed cell lacks evidence record for {task_id}"
                )
            observation = native_cell.get("observation")
            if not isinstance(observation, Mapping):
                raise ResearchCampaignError(
                    f"QCE completed cell lacks its observation for {task_id}"
                )
            attempt_id = _text(
                observation.get("attempt_id"),
                label=f"{task_id} QCE attempt_id",
            )
            output = root / "tasks" / task_id
            replay_path = output / "REPLAY-RESULT.json"
            if output.is_symlink() or (output.exists() and not output.is_dir()):
                raise ResearchCampaignError(
                    f"QCE replay output identity is unsafe: {output}"
                )
            if replay_path.is_symlink():
                raise ResearchCampaignError(
                    f"QCE replay result identity is unsafe: {replay_path}"
                )
            qualified_failure = self._qualified_replay_failure(
                output=output,
                task_id=task_id,
                attempt_id=attempt_id,
            )
            if replay_path.is_file() and qualified_failure is not None:
                raise ResearchCampaignError(
                    f"QCE replay {task_id} retained both result and failure"
                )
            if not replay_path.is_file():
                if output.exists():
                    if qualified_failure is None:
                        raise ResearchCampaignError(
                            f"QCE replay {task_id} retained output without a qualified evaluator runtime failure"
                        )
                    evaluation_failures.append(
                        {**qualified_failure, "exit_code": None}
                    )
                    continue
                argv = [
                    _text(self.config.get("python_executable"), label="QCE python_executable"),
                    str(self._path("source_root") / "scripts/replay_quantcodeeval_verifier.py"),
                    "--config", str(self._replay_config_path()),
                    "--public-root", _text(route.get("public_root"), label=f"{task_id} public_root"),
                    "--trusted-root", _text(route.get("trusted_root"), label=f"{task_id} trusted_root"),
                    "--task-panel", _text(route.get("task_panel_path"), label=f"{task_id} task_panel_path"),
                    "--source-run", _text(native_cell.get("child_run_dir"), label=f"{task_id} source run"),
                    "--output-run", str(output),
                    "--verifier-image", _text(self.config.get("verifier_image_ref"), label="QCE verifier image"),
                    "--task", task_id,
                ]
                completed = self.command_runner(argv, check=False, text=True, capture_output=True)
                if output.is_symlink() or (output.exists() and not output.is_dir()):
                    raise ResearchCampaignError(
                        f"QCE replay output identity became unsafe: {output}"
                    )
                if replay_path.is_symlink():
                    raise ResearchCampaignError(
                        f"QCE replay result identity became unsafe: {replay_path}"
                    )
                qualified_failure = self._qualified_replay_failure(
                    output=output,
                    task_id=task_id,
                    attempt_id=attempt_id,
                )
                if completed.returncode != 0:
                    if replay_path.is_file() or qualified_failure is None:
                        raise ResearchCampaignError(
                            f"QCE replay {task_id} nonzero exit is not a qualified evaluator runtime failure"
                        )
                    evaluation_failures.append(
                        {**qualified_failure, "exit_code": completed.returncode}
                    )
                    continue
                if qualified_failure is not None or not replay_path.is_file():
                    raise ResearchCampaignError(
                        f"QCE replay {task_id} successful exit has no unique aggregate"
                    )
            metrics[task_id] = self._task_metric(task_id=task_id, replay_path=replay_path)
        if request.episode.status == "complete" and missing_delivery_tasks:
            raise ResearchCampaignError(
                "complete QCE episode unexpectedly contains missing cells"
            )
        if request.episode.status == "partial" and not missing_delivery_tasks:
            raise ResearchCampaignError(
                "partial QCE episode has no declared missing cells"
            )
        failed_evaluation_tasks = {
            str(failure["task_id"]) for failure in evaluation_failures
        }
        task_failures = [
            {
                "kind": "qce_official_metric_missing_worker_delivery",
                "stage": "worker",
                "outcome": "missing",
                "task_id": task_id,
                "reason": "missing_worker_artifact",
                "official_metric": None,
            }
            for task_id in missing_delivery_tasks
        ] + evaluation_failures
        missing_tasks = [
            task_id
            for task_id in request.episode.task_ids
            if task_id in missing_delivery_tasks
            or task_id in failed_evaluation_tasks
        ]
        policy = (
            "quantcodeeval_binary_successes_then_equal_task_test_fraction_then_earlier"
        )
        if missing_tasks:
            scored_tasks = [
                task_id
                for task_id in request.episode.task_ids
                if task_id in metrics
            ]
            selection_key: tuple[tuple[int, int], ...] = ()
            selection_summary = {
                "selectable": False,
                "full_window_measurement_complete": False,
                "declared_task_ids": list(request.episode.task_ids),
                "scored_task_ids": scored_tasks,
                "missing_task_ids": missing_tasks,
                "missing_official_metrics": {
                    task_id: None for task_id in missing_tasks
                },
                "per_task": {
                    task_id: {
                        "binary_reward": metrics[task_id].binary_reward,
                        "passed": metrics[task_id].passed,
                        "total": metrics[task_id].total,
                    }
                    for task_id in scored_tasks
                },
                "cross_benchmark_pooling": False,
            }
            status = "partial"
            failure = {
                "kind": "qce_official_evaluation_partial_coverage",
                "declared_task_ids": list(request.episode.task_ids),
                "scored_task_ids": scored_tasks,
                "missing_task_ids": missing_tasks,
                "missing_official_metrics": {
                    task_id: None for task_id in missing_tasks
                },
                "selectable": False,
                "promotable": False,
                "task_failures": task_failures,
            }
        else:
            policy, selection_key, selection_summary = self._selection_projection(
                metrics, request.episode.task_ids
            )
            selection_summary = {
                **selection_summary,
                "selectable": True,
                "full_window_measurement_complete": True,
                "declared_task_ids": list(request.episode.task_ids),
                "scored_task_ids": list(request.episode.task_ids),
                "missing_task_ids": [],
                "missing_official_metrics": {},
                "cross_benchmark_pooling": False,
            }
            status = "complete"
            failure = None
        evaluation = OfficialEvaluation(stage_id=request.stage_id, backend_id=self.backend_id, harness=request.episode.harness, episode_stage_id=request.episode.stage_id, task_ids=request.episode.task_ids, condition_id=request.episode.condition_id, status=status, metrics={task_id: asdict(metric) for task_id, metric in metrics.items()}, selection_policy=policy, selection_key=selection_key, selection_summary=selection_summary, accounting={"provider_requests": 0, "completed_requests": 0, "logical_requests": 0, "provider_retries": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "turns": 0, "tool_calls": 0, "tool_errors": 0, "component_checks": 0, "wall_time_seconds": round(time.perf_counter() - started, 6), "provider_cost_usd": 0.0, "cost_complete": True, "zero_model_requests": True}, result_uri=result_path.as_posix(), failure=failure)
        _write_or_reuse(result_path, {"schema_version": 1, "protocol": "research-campaign-qce-evaluation-v1", "request": request_payload, "evaluation": asdict(evaluation)}, label="QCE official evaluation")
        return evaluation

    def active_revision_source_available(
        self,
        *,
        episode: EpisodeEvidence,
        evaluation: OfficialEvaluation,
        task_id: str,
        parent_harness: HarnessRef,
    ) -> bool:
        """Admit only an original, delivered QCE Worker observation."""

        if not (
            episode.backend_id == self.backend_id
            and evaluation.backend_id == self.backend_id
            and episode.harness == parent_harness
            and evaluation.harness == parent_harness
            and evaluation.episode_stage_id == episode.stage_id
            and evaluation.task_ids == episode.task_ids
            and evaluation.condition_id == episode.condition_id
            and task_id in episode.task_ids
        ):
            raise ResearchCampaignError(
                "active QCE revision source identity differs"
            )
        cell = episode.cells.get(task_id)
        native = cell.get("native") if isinstance(cell, Mapping) else None
        if not isinstance(native, Mapping):
            raise ResearchCampaignError(
                "active QCE evidence lacks its native cell"
            )
        if native.get("state") != "complete":
            if (
                episode.status == "partial"
                and task_id not in evaluation.metrics
                and self._missing_artifact_cell(native)
                and _delivered_evidence_record(
                    episode=episode, task_id=task_id
                )
                is None
            ):
                return False
            raise ResearchCampaignError(
                "active QCE evidence is not a qualified delivered observation"
            )
        record = _delivered_evidence_record(
            episode=episode, task_id=task_id
        )
        if record is None:
            raise ResearchCampaignError(
                "active QCE delivered observation lacks standard evidence"
            )
        observation = native.get("observation")
        execution = (
            observation.get("worker_execution")
            if isinstance(observation, Mapping)
            else None
        )
        development_worker = (
            observation.get("development_worker")
            if isinstance(observation, Mapping)
            else None
        )
        attempt_id = (
            observation.get("attempt_id")
            if isinstance(observation, Mapping)
            else None
        )
        child_run_id = native.get("child_run_id")
        if not (
            native.get("task_id") == task_id
            and isinstance(observation, Mapping)
            and observation.get("protocol")
            == "quantcodeeval-worker-observation-v1"
            and observation.get("status") == "complete"
            and observation.get("task_id") == task_id
            and observation.get("run_id") == child_run_id
            and isinstance(attempt_id, str)
            and attempt_id
            and isinstance(execution, Mapping)
            and execution.get("attempt_id") == attempt_id
            and isinstance(development_worker, Mapping)
            and isinstance(
                development_worker.get("source_worker_dir"), str
            )
            and Path(
                str(development_worker["source_worker_dir"])
            ).expanduser().resolve()
            == Path(parent_harness.artifact_uri).expanduser().resolve()
        ):
            raise ResearchCampaignError(
                "active QCE native Worker identity differs"
            )
        root = Path(str(record["root_uri"])).expanduser()
        if root.is_symlink() or not root.is_dir():
            raise ResearchCampaignError(
                "active QCE standard evidence root is unavailable"
            )
        root = root.resolve()
        members = record["members"]
        assert isinstance(members, Mapping)
        for role in _EVIDENCE_MEMBER_ROLES:
            member = Path(str(members[role])).expanduser()
            if not member.is_absolute():
                member = root / member
            if member.is_symlink():
                raise ResearchCampaignError(
                    f"active QCE evidence member {role} is a symlink"
                )
            member = member.resolve()
            try:
                member.relative_to(root)
            except ValueError as exc:
                raise ResearchCampaignError(
                    f"active QCE evidence member {role} escapes its root"
                ) from exc
            self._member_preview(uri=member.as_posix(), role=role)
        identity = _read_object(
            Path(str(members["attempt_identity"])),
            label="active QCE attempt identity",
        )
        if not (
            identity.get("task_id") == task_id
            and identity.get("run_id") == child_run_id
            and identity.get("attempt_id") == attempt_id
            and identity.get("benchmark_commit")
            == observation.get("benchmark_commit")
        ):
            raise ResearchCampaignError(
                "active QCE original attempt identity differs"
            )
        return True

    def _revision_accounting(self, result: Mapping[str, object], root: Path, iteration: int, wall_time: float) -> dict[str, object]:
        cost = result.get("proxy_cost")
        cost = cost if isinstance(cost, Mapping) else {}
        summary_path = root / "attempts" / f"evolver-iteration-{iteration}" / "summary.json"
        summary = _read_object(summary_path, label="QCE Evolver summary") if summary_path.is_file() and not summary_path.is_symlink() else {}
        checks = result.get("component_tests")
        return {"provider_requests": cost.get("request_count"), "completed_requests": cost.get("completed_request_count"), "logical_requests": summary.get("logical_requests"), "provider_retries": summary.get("provider_retries"), "input_tokens": cost.get("input_tokens"), "output_tokens": cost.get("output_tokens"), "total_tokens": cost.get("total_tokens"), "turns": summary.get("turns"), "tool_calls": summary.get("tool_calls"), "tool_errors": summary.get("tool_errors"), "component_checks": len(checks) if isinstance(checks, list) else 0, "wall_time_seconds": wall_time, "provider_cost_usd": cost.get("provider_cost_usd") if cost.get("cost_complete") is True else None, "cost_complete": cost.get("cost_complete") is True, "trace_bytes": summary.get("trace_bytes"), "final_truncated": summary.get("final_truncated"), "terminal_reserve": summary.get("terminal_reserve"), "prepared_input_accounting": result.get("preparation_accounting")}

    def _member_preview(self, *, uri: str, role: str) -> dict[str, object]:
        supplied = Path(uri).expanduser()
        if not supplied.is_absolute():
            raise ResearchCampaignError(
                f"cross-backend evidence member {role} must use an absolute path"
            )
        if supplied.is_symlink():
            raise ResearchCampaignError(
                f"cross-backend evidence member {role} is a symlink: {supplied}"
            )
        path = supplied.resolve()
        if not path.exists():
            raise ResearchCampaignError(
                f"cross-backend evidence member {role} is missing or unsafe: {path}"
            )
        if path.is_dir():
            entries: list[dict[str, object]] = []
            for child in sorted(path.iterdir(), key=lambda item: item.name):
                if child.is_symlink():
                    raise ResearchCampaignError(
                        f"cross-backend evidence directory contains a symlink: {child}"
                    )
                entries.append(
                    {
                        "name": child.name,
                        "kind": "directory" if child.is_dir() else "file",
                        "bytes": child.stat().st_size if child.is_file() else None,
                    }
                )
                if len(entries) == 128:
                    break
            return {
                "path": path.as_posix(),
                "kind": "directory",
                "immediate_entries": entries,
                "entry_listing_truncated": len(list(path.iterdir())) > len(entries),
            }
        if not path.is_file():
            raise ResearchCampaignError(
                f"cross-backend evidence member {role} is not regular: {path}"
            )
        max_bytes = 4 * 1024
        total_bytes = path.stat().st_size
        with path.open("rb") as handle:
            if total_bytes <= max_bytes:
                payload = handle.read()
                mode = "complete"
            else:
                half = max_bytes // 2
                # At most three overlapping bytes complete a UTF-8 code point
                # at either cut. Middle bytes remain outside preview validation.
                head = handle.read(half + 3)
                handle.seek(total_bytes - half - 3)
                tail = handle.read(half + 3)
                mode = "head_and_tail"
        try:
            if mode == "complete":
                text = payload.decode("utf-8")
            else:
                # Strictly validate the retained spans and boundary overlap.
                # Only an unfinished suffix beyond the head limit is deferred.
                codecs.getincrementaldecoder("utf-8")().decode(head, final=False)
                head_end = half
                while head_end and head[head_end] & 0xC0 == 0x80:
                    head_end -= 1
                tail_prefix = 0
                while tail_prefix < 3 and tail[tail_prefix] & 0xC0 == 0x80:
                    tail_prefix += 1
                tail[tail_prefix:].decode("utf-8")
                tail_start = 3
                while tail_start < len(tail) and tail[tail_start] & 0xC0 == 0x80:
                    tail_start += 1
                text = (
                    head[:head_end].decode("utf-8")
                    + "\n... campaign preview omitted middle bytes ...\n"
                    + tail[tail_start:].decode("utf-8")
                )
        except UnicodeDecodeError as exc:
            raise ResearchCampaignError(
                f"cross-backend evidence member {role} is not UTF-8 text: {path}"
            ) from exc
        return {
            "path": path.as_posix(),
            "kind": "file",
            "bytes": total_bytes,
            "preview_mode": mode,
            "preview_bytes_limit": max_bytes,
            "text": text,
        }

    def _cross_backend_investigator_note(
        self, *, request: RevisionRequest, root: Path
    ) -> Path:
        _validate_revision_windows(
            parent_harness=request.parent_harness,
            evidence_by_backend=request.evidence_by_backend,
            evaluations_by_backend=request.evaluations_by_backend,
            investigate_partial_windows=request.investigate_partial_windows,
        )
        projection: dict[str, object] = {
            "schema_version": 1,
            "protocol": "research-campaign-proposer-evidence-projection-v1",
            "campaign_id": request.campaign_id,
            "revision_stage_id": request.stage_id,
            "active_backend_id": request.backend_id,
            "active_task_id": request.active_task_id,
            "parent_harness": asdict(request.parent_harness),
            "scope": "registered_current_development_comparison_windows_only",
            "official_evaluation_returned_by_zero_model_adapter": True,
            "official_failure_attribution": False,
            "cross_benchmark_score_pooling": False,
            "member_preview_bytes": 4 * 1024,
            "backends": {},
        }
        if request.investigate_partial_windows:
            projection["investigate_partial_windows"] = True
        if request.related_completed_round is not None:
            projection["related_completed_round"] = {
                "round_id": request.related_completed_round.round_id,
                "parent_harness_id": (
                    request.related_completed_round.parent_harness.harness_id
                ),
                "candidate_harness_id": (
                    request.related_completed_round.candidate_harness.harness_id
                ),
                "catalog": "related-completed-round/catalog.json",
                "separate_historical_namespace": True,
                "selection_included": False,
                "current_parent_override": False,
                "public_probe_aliases_created": False,
            }
        if request.seed_related_completed_rounds:
            projection["seed_completed_rounds"] = [
                {
                    "round_id": seed.round_id,
                    "source_revision_stage_id": Path(seed.revision_result_uri).parent.name,
                    "historical_outcome_only": True,
                    "current_parent_override": False,
                }
                for seed in request.seed_related_completed_rounds
            ]
        projected_backends = projection["backends"]
        assert isinstance(projected_backends, dict)
        for backend_id, episode in request.evidence_by_backend.items():
            evaluation = request.evaluations_by_backend[backend_id]
            tasks: dict[str, object] = {}
            for task_id in episode.task_ids:
                record = _delivered_evidence_record(
                    episode=episode, task_id=task_id
                )
                metric = evaluation.metrics.get(task_id)
                if record is None:
                    if metric is not None:
                        raise ResearchCampaignError(
                            f"{backend_id}/{task_id} metric lacks delivered evidence"
                        )
                    tasks[task_id] = {
                        "availability": "missing_worker_delivery",
                        "evidence_record": None,
                        "official_metric": None,
                        "member_previews": {},
                    }
                    continue
                members = record["members"]
                assert isinstance(members, dict)
                task_projection: dict[str, object] = {
                    "evidence_record": record,
                    "official_metric": (
                        dict(metric)
                        if isinstance(metric, Mapping)
                        else None
                    ),
                    "member_previews": {
                        role: self._member_preview(uri=str(uri), role=role)
                        for role, uri in members.items()
                    },
                }
                if request.investigate_partial_windows:
                    task_projection["availability"] = (
                        "observed_scored"
                        if isinstance(metric, Mapping)
                        else "observed_unscored"
                    )
                tasks[task_id] = task_projection
            backend_projection: dict[str, object] = {
                "episode_stage_id": episode.stage_id,
                "evaluation_stage_id": evaluation.stage_id,
                "condition_id": episode.condition_id,
                "selection_policy": evaluation.selection_policy,
                "selection_key": [list(value) for value in evaluation.selection_key],
                "selection_summary": dict(evaluation.selection_summary),
                "tasks": tasks,
            }
            if request.investigate_partial_windows:
                backend_projection["coverage"] = _window_coverage(
                    episode=episode, evaluation=evaluation
                )
            projected_backends[backend_id] = backend_projection
        registered_note = request.options.get("investigator_note_path")
        registered_text = ""
        registered_path: str | None = None
        if registered_note is not None:
            note = Path(
                _text(registered_note, label="registered investigator note")
            ).expanduser().resolve()
            if note.is_symlink() or not note.is_file() or note.suffix != ".md":
                raise ResearchCampaignError(
                    "registered investigator note must be a regular Markdown file"
                )
            registered_text = note.read_text(encoding="utf-8")
            if not registered_text.strip():
                raise ResearchCampaignError("registered investigator note is empty")
            registered_path = note.as_posix()
        projection["registered_investigator_note_path"] = registered_path
        serialized = json.dumps(
            projection, sort_keys=True, indent=2, ensure_ascii=False
        )
        note_text = (
            "# Registered investigator context\n\n"
            + (registered_text.rstrip() if registered_text else "No separate note was declared.")
            + "\n\n# Current campaign evidence projection\n\n"
            "The JSON below contains actual current-window Worker/evaluation evidence "
            "and, when declared, a pointer to one separately staged completed-round "
            "candidate evidence catalog. "
            "It is not hidden-test attribution, a claim of transfer, or pooled scoring. "
            "Large text members use a recorded head-and-tail preview; their exact retained "
            "paths and public-probe member roles remain in each evidence record.\n\n"
            "```json\n"
            + serialized
            + "\n```\n"
        )
        if len(note_text.encode("utf-8")) > 512 * 1024:
            raise ResearchCampaignError(
                "cross-backend proposer evidence projection exceeds 512 KiB"
            )
        note_path = root / "campaign-inputs" / "current-window-evidence.md"
        _write_text_or_reuse(
            note_path, note_text, label="cross-backend investigator note"
        )
        return note_path

    def run_revision(self, request: RevisionRequest) -> RevisionOutcome:
        if request.backend_id != self.backend_id or request.active_task_id not in request.parent_episode.task_ids or request.parent_episode.task_ids != request.parent_evaluation.task_ids:
            raise ResearchCampaignError("QCE revision inputs do not share the active window")
        if not self.active_revision_source_available(
            episode=request.parent_episode,
            evaluation=request.parent_evaluation,
            task_id=request.active_task_id,
            parent_harness=request.parent_harness,
        ):
            raise ResearchCampaignError(
                "active QCE revision source has no delivered Worker evidence"
            )
        parent_cell = request.parent_episode.cells[request.active_task_id]
        native_parent_cell = parent_cell.get("native")
        if not isinstance(native_parent_cell, Mapping):
            raise ResearchCampaignError("active QCE evidence lacks its native cell")
        parent_metric = request.parent_evaluation.metrics.get(
            request.active_task_id
        )
        if parent_metric is not None and not isinstance(parent_metric, Mapping):
            raise ResearchCampaignError("active QCE official metric is invalid")
        iteration = request.options.get("iteration")
        if type(iteration) is not int or iteration < 1:
            raise ResearchCampaignError("QCE revision iteration must be positive")
        root = self.run_root / "revisions" / request.stage_id
        projected_note = self._cross_backend_investigator_note(
            request=request, root=root
        )
        kwargs: dict[str, object] = {
            "observation_run_dir": _text(native_parent_cell.get("child_run_dir"), label="active parent observation"),
            "run_dir": root,
            "iteration": iteration,
            "config_path": self._path("config_path"),
            "evolver_image_ref": _text(self.config.get("evolver_image_ref"), label="QCE Evolver image"),
            "proxy_image_ref": _text(self.config.get("proxy_image_ref"), label="QCE proxy image"),
            "evolver_profile": _text(self.config.get("evolver_profile"), label="QCE Evolver profile"),
            "investigator_note_path": projected_note,
        }
        if "evolver_config_path" in self.config:
            kwargs["evolver_config_path"] = self._path("evolver_config_path")
        if kwargs["evolver_profile"] == EARLY_INTERVENTION_FULL_HARNESS_PROFILE:
            kwargs["current_comparison_windows"] = {
                backend_id: (episode, request.evaluations_by_backend[backend_id])
                for backend_id, episode in request.evidence_by_backend.items()
            }
            kwargs["allow_partial_comparison"] = request.investigate_partial_windows
        if parent_metric is not None:
            kwargs["official_replay_result_path"] = _text(
                parent_metric.get("result_uri"), label="active parent replay"
            )
        if request.research_memory is not None:
            memory_path = Path(request.research_memory.artifact_uri).expanduser().resolve()
            try:
                load_research_operation_memory(memory_path)
            except ResearchOperationMemoryError as exc:
                raise ResearchCampaignError(f"input research memory is invalid: {exc}") from exc
            kwargs["research_memory_path"] = memory_path
        if request.related_completed_round is not None:
            kwargs["related_completed_round"] = asdict(
                request.related_completed_round
            )
        if request.seed_related_completed_rounds:
            kwargs["seed_related_completed_rounds"] = [
                asdict(seed) for seed in request.seed_related_completed_rounds
            ]
        option_map = {
            "history_root": "history_root",
            "selected_history_entry_ids": "selected_history_entry_ids",
            "max_selected_history_entries": "max_selected_history_entries",
            "prior_decision_path": "prior_decision_path",
            "last_scored_parent_result_path": "last_scored_parent_result_path",
            "outcome_linked_experience_review": (
                "outcome_linked_experience_review"
            ),
        }
        for option, argument in option_map.items():
            if option in request.options and request.options[option] is not None:
                kwargs[argument] = request.options[option]
        started = time.perf_counter()
        result = run_quantcodeeval_behavior_revision(**kwargs)
        status = str(result.get("status"))
        raw_decision = result.get("decision")
        decision = raw_decision.get("decision") if isinstance(raw_decision, Mapping) else raw_decision if isinstance(raw_decision, str) else None
        candidate: HarnessRef | None = None
        if status == "revised_unscored" and decision == "ACT":
            candidate_uri = _text(result.get("candidate_dir"), label="QCE candidate_dir")
            candidate_path = (root / candidate_uri).resolve()
            candidate = HarnessRef(harness_id=f"{request.stage_id}-candidate", artifact_uri=candidate_path.as_posix(), revision_uri=root.as_posix(), worker_role="candidate")
        retained_memory: MemoryRef | None = None
        memory_uri = result.get("research_memory_uri")
        if memory_uri is not None:
            memory_path = (root / _text(memory_uri, label="QCE retained research memory")).resolve()
            try:
                load_research_operation_memory(memory_path)
            except ResearchOperationMemoryError as exc:
                raise ResearchCampaignError(f"retained research memory is invalid: {exc}") from exc
            retained_memory = MemoryRef(artifact_uri=memory_path.as_posix(), source_stage_id=request.stage_id)
        checks = tuple(dict(item) for item in result.get("component_tests", []) if isinstance(item, Mapping))
        decision_payload = result.get("decision")
        probes = decision_payload.get("public_artifact_probe_ids", []) if isinstance(decision_payload, Mapping) else []
        failure = result.get("failure") if isinstance(result.get("failure"), Mapping) else None
        projected_ref = f"campaign-evidence:{projected_note.as_posix()}"
        accounting = self._revision_accounting(
            result, root, iteration, round(time.perf_counter() - started, 6)
        )
        accounting["campaign_evidence_projection_bytes"] = projected_note.stat().st_size
        return RevisionOutcome(stage_id=request.stage_id, backend_id=self.backend_id, parent_harness=request.parent_harness, status=status, decision=str(decision) if decision is not None else None, candidate_harness=candidate, retained_memory=retained_memory, accounting=accounting, result_uri=(root / "BEHAVIOR-REVISION-RESULT.json").as_posix(), component_checks=checks, public_probe_refs=tuple(str(item) for item in probes) + (projected_ref,), failure=failure)


__all__ = [
    "CampaignBackend",
    "EVIDENCE_RECORD_PROTOCOL",
    "EpisodeEvidence",
    "EpisodeRequest",
    "EvaluationRequest",
    "HarnessRef",
    "MemoryRef",
    "OfficialEvaluation",
    "PROTOCOL",
    "QuantCodeEvalBackend",
    "RelatedCompletedRound",
    "ResearchCampaignError",
    "RevisionOutcome",
    "RevisionRequest",
    "STATE_FILE",
    "TaskMetric",
    "advance_campaign",
    "compare_benchmark_windows",
    "compare_whole_harness_evaluations",
    "initialize_campaign",
    "qualified_revision_failure_selection",
    "run_campaign",
    "validate_campaign_plan",
]
