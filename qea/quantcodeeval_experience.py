"""Compact, answer-free experience views over QuantCodeEval history.

The history archive remains the source of truth.  This module adds navigation:
short lessons, branch ancestry, and a small relevant set that an Evolver can
read before opening exact entries, diffs, or candidate source.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable, Mapping


class QuantCodeEvalExperienceError(ValueError):
    """A projected history archive cannot be summarized as experience."""


def _load_object(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise QuantCodeEvalExperienceError(f"cannot read history entry: {path}") from exc
    if not isinstance(value, dict):
        raise QuantCodeEvalExperienceError(f"history entry is not an object: {path}")
    return value


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _text_list(value: object) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item) for item in value if isinstance(item, str) and item.strip()]


def _task_outcomes(evaluation: Mapping[str, object]) -> list[dict[str, object]]:
    rewards = evaluation.get("official_rewards")
    if not isinstance(rewards, Mapping):
        return []
    answer_free = evaluation.get("answer_free")
    answer_free_map = answer_free if isinstance(answer_free, Mapping) else {}
    rows: list[dict[str, object]] = []
    for task_id in sorted(str(key) for key in rewards):
        row: dict[str, object] = {
            "task_id": task_id,
            "reward": rewards.get(task_id),
        }
        public_outcome = answer_free_map.get(task_id)
        if public_outcome is not None:
            row["answer_free_outcome"] = public_outcome
        rows.append(row)
    return rows


def _lesson(entry: Mapping[str, object]) -> tuple[str, str]:
    selection = str(entry.get("selection", "unknown"))
    evaluation = entry.get("evaluation")
    evaluation_map = evaluation if isinstance(evaluation, Mapping) else {}
    activation = entry.get("activation")
    activation_map = activation if isinstance(activation, Mapping) else {}
    reason = str(
        evaluation_map.get("reason")
        or entry.get("rollback_reason")
        or "no result explanation was recorded"
    )
    officially_measured = (
        evaluation_map.get("official_evaluated") is not False and bool(evaluation_map)
    )
    if activation_map.get("status") == "failed" or not officially_measured:
        return "not_measured", f"The intervention did not reach a valid task evaluation: {reason}"
    if selection == "accepted":
        return "supported", f"The measured panel supported keeping this intervention: {reason}"
    if selection == "archived":
        return "mixed", (
            "The intervention was kept as diagnostic experience but was not "
            f"promoted: {reason}"
        )
    if selection == "rejected":
        return "not_supported", f"The measured panel did not support this intervention: {reason}"
    return "unknown", reason


def _experience_card(
    entry: Mapping[str, object], *, ordinal: int, source_path: str
) -> dict[str, object]:
    decision = entry.get("decision")
    decision_map = decision if isinstance(decision, Mapping) else {}
    evaluation = entry.get("evaluation")
    evaluation_map = evaluation if isinstance(evaluation, Mapping) else {}
    mutation = entry.get("mutation_metrics")
    mutation_map = mutation if isinstance(mutation, Mapping) else {}
    files = mutation_map.get("files")
    changed_files = []
    if isinstance(files, list):
        changed_files = [
            str(item.get("path"))
            for item in files
            if isinstance(item, Mapping) and isinstance(item.get("path"), str)
        ]
    tags = _text_list(decision_map.get("domain_tags"))
    for field in ("breakdown_stage", "failure_class"):
        value = decision_map.get(field)
        if isinstance(value, str) and value and value not in tags:
            tags.append(value)
    prediction_result, lesson = _lesson(entry)
    selection = str(entry.get("selection", "unknown"))
    operators = {
        "accepted": ["CONTINUE", "REUSE"],
        "archived": ["FUSE", "NEW_PROBE"],
        "rejected": ["REVERT", "NEW_PROBE"],
    }.get(selection, ["NEW_PROBE"])
    return {
        "experience_key": f"experience-{ordinal:04d}",
        "source_entry": source_path,
        "run_id": entry.get("run_id"),
        "iteration": entry.get("iteration"),
        "mechanism": entry.get("mechanism"),
        "search_operator": decision_map.get("search_operator", "LEGACY_ACT"),
        "domain_tags": tags,
        "primary_components": list(entry.get("primary_components", [])),
        "changed_files": changed_files,
        "activation_status": (
            entry.get("activation", {}).get("status")
            if isinstance(entry.get("activation"), Mapping)
            else None
        ),
        "official_evaluated": evaluation_map.get("official_evaluated", False),
        "task_outcomes": _task_outcomes(evaluation_map),
        "worker_runtime": (
            list(evaluation_map["worker_runtime"])
            if isinstance(evaluation_map.get("worker_runtime"), list)
            else []
        ),
        "new_information": evaluation_map.get("new_information"),
        "selection": selection,
        "prediction_result": prediction_result,
        "lesson": lesson,
        "suggested_next_operators": operators,
    }


def materialize_quantcodeeval_experience(
    *,
    archive_root: str | Path,
    destination: str | Path,
    target_task_ids: Iterable[str] = (),
    current_parent: str | None = None,
    relevant_limit: int | None = None,
) -> dict[str, object]:
    """Build navigation files from an already validated history projection."""

    archive = Path(archive_root).expanduser().resolve()
    index = _load_object(archive / "INDEX.json")
    entry_ids = index.get("entries")
    if not isinstance(entry_ids, list) or any(not isinstance(item, str) for item in entry_ids):
        raise QuantCodeEvalExperienceError("history index entries are invalid")
    if relevant_limit is not None and (
        type(relevant_limit) is not int or relevant_limit < 1
    ):
        raise QuantCodeEvalExperienceError("relevant_limit must be positive or null")

    entries: list[dict[str, object]] = []
    cards: list[dict[str, object]] = []
    candidate_to_key: dict[str, str] = {}
    for ordinal, entry_id in enumerate(entry_ids, start=1):
        source_path = f"history/archive/entries/{entry_id}.json"
        entry = _load_object(archive / "entries" / f"{entry_id}.json")
        card = _experience_card(entry, ordinal=ordinal, source_path=source_path)
        entries.append(entry)
        cards.append(card)
        candidate = entry.get("candidate_digest")
        if isinstance(candidate, str):
            candidate_to_key[candidate] = str(card["experience_key"])

    ancestry_rows: list[dict[str, object]] = []
    for entry, card in zip(entries, cards):
        parent = entry.get("parent_digest")
        ancestry_rows.append(
            {
                "experience_key": card["experience_key"],
                "parent_experience_key": candidate_to_key.get(str(parent)),
                "selection": card["selection"],
            }
        )
    current_parent_key = candidate_to_key.get(current_parent or "")

    targets = {str(value) for value in target_task_ids}

    def relevance(card: Mapping[str, object]) -> tuple[int, int]:
        outcomes = card.get("task_outcomes")
        outcome_rows = outcomes if isinstance(outcomes, list) else []
        task_ids = {
            str(item.get("task_id"))
            for item in outcome_rows
            if isinstance(item, Mapping)
        }
        score = 4 * len(targets & task_ids)
        score += {"accepted": 3, "archived": 2, "rejected": 1}.get(
            str(card.get("selection")), 0
        )
        if card.get("new_information") is True:
            score += 2
        if card.get("domain_tags"):
            score += 1
        return score, int(card.get("iteration") or 0)

    relevant_cards = sorted(cards, key=relevance, reverse=True)
    if relevant_limit is not None:
        relevant_cards = relevant_cards[:relevant_limit]
    relevant_keys = {str(card["experience_key"]) for card in relevant_cards}
    if current_parent_key is not None and current_parent_key not in relevant_keys:
        current_card = next(
            card
            for card in cards
            if card["experience_key"] == current_parent_key
        )
        relevant_cards.insert(0, current_card)
    destination_path = Path(destination).expanduser().resolve()
    destination_path.mkdir(parents=True, exist_ok=True)
    for card in cards:
        _write_json(
            destination_path / "cards" / f"{card['experience_key']}.json", card
        )
    _write_json(
        destination_path / "CATALOG.json",
        {"schema_version": 1, "experience_count": len(cards), "experiences": cards},
    )
    _write_json(
        destination_path / "ANCESTRY.json",
        {
            "schema_version": 1,
            "current_parent_experience_key": current_parent_key,
            "branches": ancestry_rows,
        },
    )
    _write_json(
        destination_path / "RELEVANT.json",
        {
            "schema_version": 1,
            "target_task_ids": sorted(targets),
            "selection_policy": (
                "target overlap, measured result, new information, domain tags, recency"
            ),
            "experiences": relevant_cards,
        },
    )
    return {
        "experience_count": len(cards),
        "current_parent_experience_key": current_parent_key,
        "relevant_count": len(relevant_cards),
    }


__all__ = [
    "QuantCodeEvalExperienceError",
    "materialize_quantcodeeval_experience",
]
