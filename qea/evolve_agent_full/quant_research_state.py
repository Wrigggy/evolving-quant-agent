"""Compact normalization and validation for Quant Research State Cards."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any


class QuantResearchStateCardError(ValueError):
    """A State Card is missing information needed for bounded search."""


_UNSUPPORTED_TEXT = {"", "N-A", "UNKNOWN"}
_OUTCOME_CLASSES = {"positive", "negative", "inactive", "unstable"}
_RELATION_SUPPORT_FIELDS = (
    "support",
    "applicability",
    "observed_evidence",
    "evidence_refs",
)


def _normalize_value(value: object) -> Any:
    """Copy mappings and sequences into mutable, serialization-friendly forms."""

    if isinstance(value, Mapping):
        return {str(key): _normalize_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        return [_normalize_value(item) for item in value]
    return value


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _has_support(value: object) -> bool:
    """Return whether an open support field contains non-placeholder evidence."""

    if isinstance(value, str):
        return value.strip().upper() not in _UNSUPPORTED_TEXT
    if isinstance(value, Mapping):
        return any(_has_support(item) for item in value.values())
    if isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        return any(_has_support(item) for item in value)
    return value is not None


def _relation_id(relation: Mapping[str, object]) -> str | None:
    return _text(relation.get("relation_id"))


def _selected_relation_id(
    card: Mapping[str, object], explicit_relation_id: str | None
) -> str | None:
    if explicit_relation_id is not None:
        return _text(explicit_relation_id)

    intervention = card.get("selected_intervention")
    if isinstance(intervention, Mapping):
        selected = _text(intervention.get("relation_id"))
        if selected is not None:
            return selected

    selected_relation = card.get("selected_relation")
    if isinstance(selected_relation, Mapping):
        return _text(selected_relation.get("relation_id"))
    return _text(selected_relation)


def _component_locus(card: Mapping[str, object]) -> str | None:
    intervention = card.get("selected_intervention")
    if isinstance(intervention, Mapping):
        locus = _text(intervention.get("component_locus"))
        if locus is not None:
            return locus

    routing = card.get("component_routing")
    if isinstance(routing, Mapping):
        return _text(routing.get("selected_locus"))
    return None


def _residual_relation_id(card: Mapping[str, object]) -> str | None:
    intervention = card.get("selected_intervention")
    if isinstance(intervention, Mapping):
        return _text(intervention.get("residual_relation_id"))
    return None


def normalize_quant_research_state_card(
    value: Mapping[str, object],
    *,
    action: str | None = None,
    selected_relation_id: str | None = None,
) -> dict[str, object]:
    """Normalize one open State Card and enforce only search-blocking fields.

    Extra top-level and nested fields are retained. ``N-A`` and ``UNKNOWN``
    remain valid values; an ``ACT`` simply cannot select a relation whose only
    applicability/support evidence is one of those placeholders.
    """

    if not isinstance(value, Mapping):
        raise QuantResearchStateCardError("State Card must be a mapping")
    card: dict[str, object] = _normalize_value(value)
    card.setdefault("schema_version", 1)

    task_key = _text(card.get("task_key"))
    if task_key is None or task_key.upper() in _UNSUPPORTED_TEXT:
        raise QuantResearchStateCardError("State Card requires a task_key")
    card["task_key"] = task_key

    raw_relations = card.get("candidate_relations")
    if not isinstance(raw_relations, list) or not raw_relations:
        raise QuantResearchStateCardError(
            "State Card requires at least one candidate relation"
        )

    relations: list[dict[str, object]] = []
    for raw_relation in raw_relations:
        if not isinstance(raw_relation, Mapping):
            raise QuantResearchStateCardError(
                "each candidate relation must be a mapping"
            )
        relation = dict(raw_relation)
        relation_id = _relation_id(relation)
        if relation_id is None:
            raise QuantResearchStateCardError(
                "each candidate relation requires a relation_id"
            )
        relation["relation_id"] = relation_id
        status = _text(relation.get("status"))
        if status is not None:
            relation["status"] = status.upper()
        relations.append(relation)
    card["candidate_relations"] = relations

    normalized_action = _text(action)
    if normalized_action is None:
        normalized_action = _text(card.get("action"))
    if normalized_action is None or normalized_action.upper() != "ACT":
        return card

    relation_id = _selected_relation_id(card, selected_relation_id)
    if relation_id is None:
        raise QuantResearchStateCardError("ACT requires a selected relation")
    selected = next(
        (relation for relation in relations if _relation_id(relation) == relation_id),
        None,
    )
    if selected is None:
        raise QuantResearchStateCardError(
            "ACT selected relation is not present in candidate_relations"
        )
    if not any(
        _has_support(selected.get(field))
        for field in _RELATION_SUPPORT_FIELDS
    ):
        raise QuantResearchStateCardError(
            "ACT selected relation has no support; provide applicability, "
            "observed_evidence, evidence_refs, or support"
        )
    residual_relation_id = _residual_relation_id(card)
    if residual_relation_id is not None:
        if residual_relation_id == relation_id:
            raise QuantResearchStateCardError(
                "residual-risk relation must differ from the selected relation"
            )
        residual = next(
            (
                relation
                for relation in relations
                if _relation_id(relation) == residual_relation_id
            ),
            None,
        )
        if residual is None:
            raise QuantResearchStateCardError(
                "residual-risk relation is not present in candidate_relations"
            )
        if not any(
            _has_support(residual.get(field))
            for field in _RELATION_SUPPORT_FIELDS
        ):
            raise QuantResearchStateCardError(
                "residual-risk relation has no support; provide applicability, "
                "observed_evidence, evidence_refs, or support"
            )
    if _component_locus(card) is None:
        raise QuantResearchStateCardError("ACT requires a component locus")
    return card


def validate_quant_research_state_card(
    value: Mapping[str, object],
    *,
    action: str | None = None,
    selected_relation_id: str | None = None,
) -> dict[str, object]:
    """Validate and return the normalized State Card."""

    return normalize_quant_research_state_card(
        value,
        action=action,
        selected_relation_id=selected_relation_id,
    )


def _strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        return [text for child in value.values() for text in _strings(child)]
    if isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        return [text for child in value for text in _strings(child)]
    return []


def _tokens(value: object) -> set[str]:
    return {
        token
        for text in _strings(value)
        for token in re.split(r"[^a-z0-9]+", text.casefold())
        if len(token) > 2
    }


def _selected_relation(
    card: Mapping[str, object], relation_id: str
) -> Mapping[str, object]:
    relations = card.get("candidate_relations")
    assert isinstance(relations, list)
    return next(
        relation
        for relation in relations
        if isinstance(relation, Mapping)
        and _relation_id(relation) == relation_id
    )


def _outcome_class(
    trial: Mapping[str, object], *, component_is_unstable: bool
) -> str | None:
    explicit = _text(trial.get("outcome_class"))
    if explicit is not None and explicit.casefold() in _OUTCOME_CLASSES:
        return explicit.casefold()
    if trial.get("activated") is False:
        return "inactive"
    if component_is_unstable:
        return "unstable"
    reward = trial.get("official_reward")
    if isinstance(reward, (int, float)) and not isinstance(reward, bool):
        return "positive" if float(reward) >= 1.0 else "negative"
    return None


def _retrieve_relation_episodes(
    *,
    card: Mapping[str, object],
    relation_id: str,
    raw_components: Sequence[object],
    max_per_outcome: int,
) -> dict[str, object]:
    relation = _selected_relation(card, relation_id)
    intervention = card.get("selected_intervention")
    intervention_map = intervention if isinstance(intervention, Mapping) else {}
    query = {
        "task_key": card["task_key"],
        "state_locus": intervention_map.get("state_locus"),
        "relation_family": relation.get("relation_family", relation_id),
        "component_locus": _component_locus(card),
        "task_mechanism": relation.get(
            "task_mechanism", relation.get("applicability")
        ),
        "desired_observation": relation.get(
            "discriminating_observation",
            relation.get(
                "expected_relation",
                intervention_map.get(
                    "discriminating_observation",
                    intervention_map.get("predicted_transition"),
                ),
            ),
        ),
    }
    query_tokens = _tokens(query)
    ranked: dict[str, list[tuple[int, str, dict[str, object]]]] = {
        label: [] for label in sorted(_OUTCOME_CLASSES)
    }
    for component in raw_components:
        if not isinstance(component, Mapping):
            continue
        component_id = _text(component.get("component_id"))
        if component_id is None:
            continue
        query_relation_family = _text(query.get("relation_family"))
        component_relation_family = _text(component.get("relation_family"))
        if (
            query_relation_family is not None
            and component_relation_family is not None
            and query_relation_family.casefold()
            != component_relation_family.casefold()
        ):
            continue
        trials = component.get("observed_trials")
        trial_rows = [row for row in trials or [] if isinstance(row, Mapping)]
        measured_rewards = {
            float(row["official_reward"])
            for row in trial_rows
            if isinstance(row.get("official_reward"), (int, float))
            and not isinstance(row.get("official_reward"), bool)
            and row.get("activated") is True
        }
        component_is_unstable = len(measured_rewards) > 1
        if not trial_rows and _text(component.get("outcome_class")) is not None:
            trial_rows = [component]
        for trial in trial_rows:
            outcome = _outcome_class(
                trial, component_is_unstable=component_is_unstable
            )
            if outcome is None:
                continue
            searchable = {
                "component_id": component_id,
                "description": component.get("description"),
                "capabilities": component.get("capabilities"),
                "state_locus": component.get("state_locus"),
                "relation_family": component.get("relation_family"),
                "component_locus": component.get("component_locus"),
                "task_mechanism": component.get("task_mechanism"),
                "task_id": trial.get("task_id"),
                "observation": trial.get("observation"),
            }
            matched = sorted(query_tokens & _tokens(searchable))
            score = len(matched)
            for coordinate in (
                "state_locus",
                "relation_family",
                "component_locus",
                "task_mechanism",
            ):
                query_value = _text(query.get(coordinate))
                component_value = _text(component.get(coordinate))
                if (
                    query_value is not None
                    and component_value is not None
                    and query_value.casefold() == component_value.casefold()
                ):
                    score += 3
            if score == 0:
                continue
            episode = {
                "component_id": component_id,
                "task_id": trial.get("task_id"),
                "outcome_class": outcome,
                "matched_terms": matched,
                "observation": trial.get("observation"),
                "source_path": component.get("source_path"),
            }
            ranked[outcome].append((score, component_id, episode))

    selected: list[dict[str, object]] = []
    for outcome in ("positive", "negative", "inactive", "unstable"):
        rows = sorted(ranked[outcome], key=lambda row: (-row[0], row[1]))
        selected.extend(row[2] for row in rows[:max_per_outcome])
    return {
        "relation_id": relation_id,
        "query": query,
        "episodes": selected,
    }


def retrieve_quant_research_episodes(
    state_card: Mapping[str, object],
    component_catalog: Mapping[str, object],
    *,
    max_per_outcome: int = 1,
) -> dict[str, object]:
    """Select compact primary and optional residual relation experience.

    This is deliberately lexical and transparent. It is a navigation aid over
    the same catalog available to the generic arm, not a second memory system or
    a learned ranking model.
    """

    if type(max_per_outcome) is not int or not 1 <= max_per_outcome <= 3:
        raise QuantResearchStateCardError("max_per_outcome must be between 1 and 3")
    card = validate_quant_research_state_card(state_card, action="ACT")
    relation_id = _selected_relation_id(card, None)
    assert relation_id is not None
    raw_components = component_catalog.get("components")
    if not isinstance(raw_components, list):
        raise QuantResearchStateCardError("component catalog requires components")
    primary = _retrieve_relation_episodes(
        card=card,
        relation_id=relation_id,
        raw_components=raw_components,
        max_per_outcome=max_per_outcome,
    )
    result = {
        "relation_id": primary["relation_id"],
        "query": primary["query"],
        "selection_policy": (
            "separate primary and residual-risk relation queries over state, "
            "component, mechanism, and desired-observation coordinates; at "
            "most one episode per outcome by default"
        ),
        "episodes": primary["episodes"],
    }
    residual_relation_id = _residual_relation_id(card)
    if residual_relation_id is not None:
        result["residual_risk"] = _retrieve_relation_episodes(
            card=card,
            relation_id=residual_relation_id,
            raw_components=raw_components,
            max_per_outcome=max_per_outcome,
        )
    return result


def quant_research_intervention_verdict(
    *,
    activated: bool,
    predicted_relation_changed: bool,
    official_target_improved: bool,
    repeated_gain: bool = False,
    protection_safe: bool = False,
    matched_transfer: bool = False,
) -> str:
    """Keep mechanism, task gain, and stability as separate verdict levels."""

    if not activated:
        return "INACTIVE"
    if not predicted_relation_changed:
        return "UNRESOLVED" if official_target_improved else "MISLOCALIZED"
    if not official_target_improved:
        return "STATE_CORRECTING"
    if repeated_gain and (protection_safe or matched_transfer):
        return "STABLE_OR_REUSABLE"
    return "TASK_HELPFUL"
