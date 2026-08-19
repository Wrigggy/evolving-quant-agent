"""Variable-length state machine for QuantCodeEval full-harness search v2.

The safety cap is configurable, but it is not the scientific definition of a
run.  Search stops on an achieved target, repeated evidence-free decisions,
repeated calibrated abstention, an explicit operator gap, or budget exhaustion.
Official promotion and diagnostic search-parent promotion remain separate.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Mapping


_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")


class QuantCodeEvalSearchError(ValueError):
    """A v2 search decision, transition, or persisted state is invalid."""


class SearchDecision(str, Enum):
    ACT = "ACT"
    ABSTAIN = "ABSTAIN"


class SearchSelection(str, Enum):
    REJECTED = "rejected"
    ARCHIVED = "archived"
    DIAGNOSTIC_PROMOTED = "diagnostic_promoted"
    RESEARCH_STATE_PROMOTED = "research_state_promoted"
    OFFICIAL_PROMOTED = "official_promoted"
    ABSTAINED = "abstained"


class SearchStopReason(str, Enum):
    TARGET_REACHED = "target_reached"
    BUDGET_EXHAUSTED = "budget_exhausted"
    NO_NEW_INFORMATION = "no_new_information"
    TERMINAL_ABSTAIN = "terminal_abstain"
    OPERATOR_GAP = "operator_gap"
    USER_STOP = "user_stop"
    INFRASTRUCTURE_FAILURE = "infrastructure_failure"


@dataclass(frozen=True)
class QuantSearchLimits:
    max_rounds: int = 20
    max_no_information_rounds: int = 3
    max_consecutive_abstain: int = 2
    max_archive_entries: int = 8
    max_model_requests: int | None = None
    max_cost_usd: float | None = None

    def __post_init__(self) -> None:
        for field in (
            "max_rounds",
            "max_no_information_rounds",
            "max_consecutive_abstain",
            "max_archive_entries",
        ):
            value = getattr(self, field)
            if type(value) is not int or value < 1:
                raise QuantCodeEvalSearchError(f"{field} must be a positive integer")
        if self.max_model_requests is not None and (
            type(self.max_model_requests) is not int or self.max_model_requests < 1
        ):
            raise QuantCodeEvalSearchError(
                "max_model_requests must be a positive integer or null"
            )
        if self.max_cost_usd is not None and (
            isinstance(self.max_cost_usd, bool)
            or not isinstance(self.max_cost_usd, (int, float))
            or self.max_cost_usd <= 0
        ):
            raise QuantCodeEvalSearchError(
                "max_cost_usd must be a positive number or null"
            )


@dataclass(frozen=True)
class SearchArchiveEntry:
    candidate_digest: str
    history_entry_id: str
    selection: SearchSelection
    official_rewards: Mapping[str, float]

    def __post_init__(self) -> None:
        if _SHA256.fullmatch(self.candidate_digest) is None:
            raise QuantCodeEvalSearchError("archive candidate digest is invalid")
        if _SHA256.fullmatch(self.history_entry_id) is None:
            raise QuantCodeEvalSearchError("archive history entry ID is invalid")
        _validate_rewards(self.official_rewards)


@dataclass(frozen=True)
class QuantSearchRound:
    iteration: int
    decision: SearchDecision
    parent_digest: str
    candidate_digest: str | None
    history_entry_id: str | None
    selection: SearchSelection
    mechanism: str | None
    primary_components: tuple[str, ...]
    declared_roles: tuple[str, ...]
    official_rewards: Mapping[str, float]
    new_information: bool
    model_requests: int
    cost_usd: float
    reason: str

    def __post_init__(self) -> None:
        if type(self.iteration) is not int or self.iteration < 1:
            raise QuantCodeEvalSearchError("round iteration is invalid")
        if _SHA256.fullmatch(self.parent_digest) is None:
            raise QuantCodeEvalSearchError("round parent digest is invalid")
        _validate_rewards(self.official_rewards)
        if type(self.model_requests) is not int or self.model_requests < 0:
            raise QuantCodeEvalSearchError("round model_requests is invalid")
        if isinstance(self.cost_usd, bool) or self.cost_usd < 0:
            raise QuantCodeEvalSearchError("round cost_usd is invalid")
        if not self.reason.strip():
            raise QuantCodeEvalSearchError("round reason is required")
        if self.decision is SearchDecision.ABSTAIN:
            if any(
                value
                for value in (
                    self.candidate_digest,
                    self.history_entry_id,
                    self.mechanism,
                    self.primary_components,
                    self.declared_roles,
                )
            ):
                raise QuantCodeEvalSearchError(
                    "ABSTAIN round must not carry candidate mutation fields"
                )
            if self.selection is not SearchSelection.ABSTAINED:
                raise QuantCodeEvalSearchError("ABSTAIN selection differs")
            return
        if self.candidate_digest is None or _SHA256.fullmatch(self.candidate_digest) is None:
            raise QuantCodeEvalSearchError("ACT requires candidate digest")
        if self.history_entry_id is None or _SHA256.fullmatch(self.history_entry_id) is None:
            raise QuantCodeEvalSearchError("ACT requires history entry ID")
        if not isinstance(self.mechanism, str) or not self.mechanism.strip():
            raise QuantCodeEvalSearchError("ACT requires a mechanism")
        if not self.primary_components or not set(self.primary_components) <= set(
            self.declared_roles
        ):
            raise QuantCodeEvalSearchError(
                "ACT primary components must be declared mutation roles"
            )
        if self.selection is SearchSelection.ABSTAINED:
            raise QuantCodeEvalSearchError("ACT cannot use abstained selection")


@dataclass(frozen=True)
class QuantCodeEvalSearchState:
    run_id: str
    task_ids: tuple[str, ...]
    h0_digest: str
    official_incumbent_digest: str
    search_parent_digest: str
    official_rewards: Mapping[str, float]
    search_parent_rewards: Mapping[str, float]
    limits: QuantSearchLimits
    archive: tuple[SearchArchiveEntry, ...] = ()
    rounds: tuple[QuantSearchRound, ...] = ()
    total_model_requests: int = 0
    total_cost_usd: float = 0.0
    consecutive_no_information: int = 0
    consecutive_abstain: int = 0
    stopped: bool = False
    stop_reason: SearchStopReason | None = None

    def __post_init__(self) -> None:
        if _SAFE_ID.fullmatch(self.run_id) is None:
            raise QuantCodeEvalSearchError("search run_id is invalid")
        if not self.task_ids or len(self.task_ids) != len(set(self.task_ids)):
            raise QuantCodeEvalSearchError("search task panel is empty or duplicated")
        for digest in (
            self.h0_digest,
            self.official_incumbent_digest,
            self.search_parent_digest,
        ):
            if _SHA256.fullmatch(digest) is None:
                raise QuantCodeEvalSearchError("search worker digest is invalid")
        if set(self.official_rewards) != set(self.task_ids) or set(
            self.search_parent_rewards
        ) != set(self.task_ids):
            raise QuantCodeEvalSearchError("search reward panel differs from task_ids")
        _validate_rewards(self.official_rewards)
        _validate_rewards(self.search_parent_rewards)
        if self.stopped != (self.stop_reason is not None):
            raise QuantCodeEvalSearchError("stopped state and stop reason differ")
        if len(self.archive) > self.limits.max_archive_entries:
            raise QuantCodeEvalSearchError("search archive exceeds configured limit")

    @property
    def next_iteration(self) -> int:
        return len(self.rounds) + 1


def _validate_rewards(rewards: Mapping[str, float]) -> None:
    if not isinstance(rewards, Mapping) or not rewards:
        raise QuantCodeEvalSearchError("official rewards must be a non-empty mapping")
    for task_id, reward in rewards.items():
        if not isinstance(task_id, str) or not task_id:
            raise QuantCodeEvalSearchError("reward task ID is invalid")
        if isinstance(reward, bool) or reward not in {0, 0.0, 1, 1.0}:
            raise QuantCodeEvalSearchError("QuantCodeEval official reward must be binary")


def initialize_quantcodeeval_search(
    *,
    run_id: str,
    h0_digest: str,
    h0_official_rewards: Mapping[str, float],
    limits: QuantSearchLimits | None = None,
) -> QuantCodeEvalSearchState:
    """Initialize a variable-length search from one already-measured H0."""

    normalized = {str(key): float(value) for key, value in h0_official_rewards.items()}
    _validate_rewards(normalized)
    return QuantCodeEvalSearchState(
        run_id=run_id,
        task_ids=tuple(sorted(normalized)),
        h0_digest=h0_digest,
        official_incumbent_digest=h0_digest,
        search_parent_digest=h0_digest,
        official_rewards=normalized,
        search_parent_rewards=normalized,
        limits=limits or QuantSearchLimits(),
    )


def _pareto_improves(
    before: Mapping[str, float], after: Mapping[str, float]
) -> bool:
    return all(after[key] >= before[key] for key in before) and any(
        after[key] > before[key] for key in before
    )


def _bounded_archive(
    state: QuantCodeEvalSearchState,
    entry: SearchArchiveEntry,
) -> tuple[SearchArchiveEntry, ...]:
    values = [item for item in state.archive if item.candidate_digest != entry.candidate_digest]
    values.append(entry)
    priority = {
        SearchSelection.OFFICIAL_PROMOTED: 0,
        SearchSelection.RESEARCH_STATE_PROMOTED: 1,
        SearchSelection.DIAGNOSTIC_PROMOTED: 2,
        SearchSelection.ARCHIVED: 3,
        SearchSelection.REJECTED: 4,
        SearchSelection.ABSTAINED: 5,
    }
    values.sort(
        key=lambda value: (
            priority[value.selection],
            -sum(value.official_rewards.values()),
            value.candidate_digest,
        )
    )
    return tuple(values[: state.limits.max_archive_entries])


def _automatic_stop(state: QuantCodeEvalSearchState) -> QuantCodeEvalSearchState:
    reason: SearchStopReason | None = None
    if all(value == 1.0 for value in state.official_rewards.values()):
        reason = SearchStopReason.TARGET_REACHED
    elif state.total_model_requests >= (state.limits.max_model_requests or 10**18):
        reason = SearchStopReason.BUDGET_EXHAUSTED
    elif state.total_cost_usd >= (state.limits.max_cost_usd or float("inf")):
        reason = SearchStopReason.BUDGET_EXHAUSTED
    elif len(state.rounds) >= state.limits.max_rounds:
        reason = SearchStopReason.BUDGET_EXHAUSTED
    elif state.consecutive_no_information >= state.limits.max_no_information_rounds:
        reason = SearchStopReason.NO_NEW_INFORMATION
    elif state.consecutive_abstain >= state.limits.max_consecutive_abstain:
        reason = SearchStopReason.TERMINAL_ABSTAIN
    return replace(state, stopped=True, stop_reason=reason) if reason else state


def record_quantcodeeval_search_round(
    state: QuantCodeEvalSearchState,
    *,
    decision: SearchDecision | str,
    official_rewards: Mapping[str, float],
    selection: SearchSelection | str,
    reason: str,
    new_information: bool,
    model_requests: int = 0,
    cost_usd: float = 0.0,
    candidate_digest: str | None = None,
    history_entry_id: str | None = None,
    mechanism: str | None = None,
    primary_components: tuple[str, ...] = (),
    declared_roles: tuple[str, ...] = (),
) -> QuantCodeEvalSearchState:
    """Append one ACT/ABSTAIN outcome and apply official/search-parent selection."""

    if state.stopped:
        raise QuantCodeEvalSearchError("cannot append to a stopped search")
    normalized_decision = SearchDecision(decision)
    normalized_selection = SearchSelection(selection)
    rewards = {str(key): float(value) for key, value in official_rewards.items()}
    if set(rewards) != set(state.task_ids):
        raise QuantCodeEvalSearchError("round reward panel differs from search panel")
    round_record = QuantSearchRound(
        iteration=state.next_iteration,
        decision=normalized_decision,
        parent_digest=state.search_parent_digest,
        candidate_digest=candidate_digest,
        history_entry_id=history_entry_id,
        selection=normalized_selection,
        mechanism=mechanism,
        primary_components=tuple(primary_components),
        declared_roles=tuple(declared_roles),
        official_rewards=rewards,
        new_information=bool(new_information),
        model_requests=model_requests,
        cost_usd=float(cost_usd),
        reason=reason,
    )
    official_digest = state.official_incumbent_digest
    official = dict(state.official_rewards)
    search_digest = state.search_parent_digest
    search_rewards = dict(state.search_parent_rewards)
    archive = state.archive
    if normalized_decision is SearchDecision.ACT:
        assert candidate_digest is not None and history_entry_id is not None
        if normalized_selection is SearchSelection.OFFICIAL_PROMOTED:
            if not _pareto_improves(official, rewards):
                raise QuantCodeEvalSearchError(
                    "official promotion must Pareto-improve the incumbent"
                )
            official_digest = candidate_digest
            official = rewards
            search_digest = candidate_digest
            search_rewards = rewards
        elif normalized_selection in {
            SearchSelection.DIAGNOSTIC_PROMOTED,
            SearchSelection.RESEARCH_STATE_PROMOTED,
        }:
            if any(rewards[key] < official[key] for key in rewards):
                raise QuantCodeEvalSearchError(
                    "diagnostic promotion cannot regress official incumbent tasks"
                )
            search_digest = candidate_digest
            search_rewards = rewards
        archive = _bounded_archive(
            state,
            SearchArchiveEntry(
                candidate_digest=candidate_digest,
                history_entry_id=history_entry_id,
                selection=normalized_selection,
                official_rewards=rewards,
            ),
        )
    updated = replace(
        state,
        official_incumbent_digest=official_digest,
        search_parent_digest=search_digest,
        official_rewards=official,
        search_parent_rewards=search_rewards,
        archive=archive,
        rounds=(*state.rounds, round_record),
        total_model_requests=state.total_model_requests + model_requests,
        total_cost_usd=state.total_cost_usd + float(cost_usd),
        consecutive_no_information=(
            0 if new_information else state.consecutive_no_information + 1
        ),
        consecutive_abstain=(
            state.consecutive_abstain + 1
            if normalized_decision is SearchDecision.ABSTAIN
            else 0
        ),
    )
    return _automatic_stop(updated)


def stop_quantcodeeval_search(
    state: QuantCodeEvalSearchState,
    reason: SearchStopReason | str,
) -> QuantCodeEvalSearchState:
    """Record an explicit operator, infrastructure, user, or budget stop."""

    if state.stopped:
        return state
    return replace(state, stopped=True, stop_reason=SearchStopReason(reason))


def quantcodeeval_search_payload(state: QuantCodeEvalSearchState) -> dict[str, object]:
    payload = asdict(state)
    payload["schema_version"] = 2
    payload["protocol"] = "quant_property_v2_full_harness"
    payload["state_sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return payload


def load_quantcodeeval_search_state(
    source: str | Path,
) -> QuantCodeEvalSearchState:
    """Load and revalidate one exact persisted v2 search checkpoint."""

    path = Path(source).expanduser().resolve()
    if path.is_symlink() or not path.is_file():
        raise QuantCodeEvalSearchError("search checkpoint must be a regular file")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise QuantCodeEvalSearchError("search checkpoint is invalid JSON") from exc
    if not isinstance(payload, dict):
        raise QuantCodeEvalSearchError("search checkpoint must be an object")
    digest = payload.pop("state_sha256", None)
    observed = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if (
        payload.pop("schema_version", None) != 2
        or payload.pop("protocol", None) != "quant_property_v2_full_harness"
        or not isinstance(digest, str)
    ):
        raise QuantCodeEvalSearchError("search checkpoint identity differs")
    if digest != observed:
        raise QuantCodeEvalSearchError("search checkpoint digest differs")
    try:
        limits = QuantSearchLimits(**payload["limits"])
        archive = tuple(
            SearchArchiveEntry(
                candidate_digest=value["candidate_digest"],
                history_entry_id=value["history_entry_id"],
                selection=SearchSelection(value["selection"]),
                official_rewards=value["official_rewards"],
            )
            for value in payload["archive"]
        )
        rounds = tuple(
            QuantSearchRound(
                iteration=value["iteration"],
                decision=SearchDecision(value["decision"]),
                parent_digest=value["parent_digest"],
                candidate_digest=value["candidate_digest"],
                history_entry_id=value["history_entry_id"],
                selection=SearchSelection(value["selection"]),
                mechanism=value["mechanism"],
                primary_components=tuple(value["primary_components"]),
                declared_roles=tuple(value["declared_roles"]),
                official_rewards=value["official_rewards"],
                new_information=value["new_information"],
                model_requests=value["model_requests"],
                cost_usd=value["cost_usd"],
                reason=value["reason"],
            )
            for value in payload["rounds"]
        )
        state = QuantCodeEvalSearchState(
            run_id=payload["run_id"],
            task_ids=tuple(payload["task_ids"]),
            h0_digest=payload["h0_digest"],
            official_incumbent_digest=payload["official_incumbent_digest"],
            search_parent_digest=payload["search_parent_digest"],
            official_rewards=payload["official_rewards"],
            search_parent_rewards=payload["search_parent_rewards"],
            limits=limits,
            archive=archive,
            rounds=rounds,
            total_model_requests=payload["total_model_requests"],
            total_cost_usd=payload["total_cost_usd"],
            consecutive_no_information=payload["consecutive_no_information"],
            consecutive_abstain=payload["consecutive_abstain"],
            stopped=payload["stopped"],
            stop_reason=(
                SearchStopReason(payload["stop_reason"])
                if payload["stop_reason"] is not None
                else None
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise QuantCodeEvalSearchError("search checkpoint schema differs") from exc
    if quantcodeeval_search_payload(state)["state_sha256"] != digest:
        raise QuantCodeEvalSearchError("reconstructed search checkpoint differs")
    return state


__all__ = [
    "QuantCodeEvalSearchError",
    "QuantCodeEvalSearchState",
    "QuantSearchLimits",
    "SearchDecision",
    "SearchSelection",
    "SearchStopReason",
    "initialize_quantcodeeval_search",
    "load_quantcodeeval_search_state",
    "quantcodeeval_search_payload",
    "record_quantcodeeval_search_round",
    "stop_quantcodeeval_search",
]
