"""Admission boundary for one reviewed QRS main harness candidate.

The checker is deliberately local and byte-oriented.  It does not execute a
Worker, inspect benchmark outcomes, or infer task semantics.  It verifies that
one reviewed candidate remains a valid six-state base harness and differs from
its frozen H0 only on the explicitly admitted prompt/skill text surfaces.
"""

from __future__ import annotations

import difflib
import os
import re
from collections.abc import Sequence
from pathlib import Path

from qea.frozen_base_harness import (
    FrozenBaseHarnessError,
    inspect_base_harness,
)


_SIX_STAGE_SKILL_SUFFIX = (
    "skills/quant-research-six-stage-workflow/SKILL.md"
)


class QRSCandidateBoundaryError(ValueError):
    """The caller supplied an invalid candidate-boundary configuration."""


def _terms(values: Sequence[str], *, label: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or any(
        not isinstance(value, str) or not value.strip() for value in values
    ):
        raise QRSCandidateBoundaryError(
            f"{label} must contain only non-empty strings"
        )
    return tuple(sorted({value.strip() for value in values}))


def _reason(
    code: str,
    *,
    path: str | None = None,
    scope: str | None = None,
) -> dict[str, str]:
    result = {"code": code}
    if path is not None:
        result["path"] = path
    if scope is not None:
        result["scope"] = scope
    return result


def _ordinary_tree(
    root_value: str | Path,
    *,
    role: str,
) -> tuple[Path, set[str], set[str], list[dict[str, str]]]:
    """Enumerate ordinary files/directories without following symlinks."""

    root = Path(root_value).expanduser().absolute()
    files: set[str] = set()
    directories: set[str] = set()
    reasons: list[dict[str, str]] = []
    if root.is_symlink():
        reasons.append(_reason("symlink_not_allowed", path=".", scope=role))
        return root, files, directories, reasons
    if not root.is_dir():
        reasons.append(_reason("worker_tree_unavailable", scope=role))
        return root, files, directories, reasons

    def walk_error(_error: OSError) -> None:
        reasons.append(_reason("worker_tree_unreadable", scope=role))

    for current, dir_names, file_names in os.walk(
        root, topdown=True, followlinks=False, onerror=walk_error
    ):
        current_path = Path(current)
        retained_dirs: list[str] = []
        for name in sorted(dir_names):
            path = current_path / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                reasons.append(
                    _reason("symlink_not_allowed", path=relative, scope=role)
                )
            elif path.is_dir():
                directories.add(relative)
                retained_dirs.append(name)
            else:
                reasons.append(
                    _reason("non_regular_tree_entry", path=relative, scope=role)
                )
        dir_names[:] = retained_dirs
        for name in sorted(file_names):
            path = current_path / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                reasons.append(
                    _reason("symlink_not_allowed", path=relative, scope=role)
                )
            elif path.is_file():
                files.add(relative)
            else:
                reasons.append(
                    _reason("non_regular_tree_entry", path=relative, scope=role)
                )
    return root, files, directories, reasons


def _declared_mutation_surfaces(
    inspection: dict[str, object],
    requested: Sequence[str],
) -> tuple[set[str], list[dict[str, str]]]:
    """Restrict mutation to the declared prompt and six-stage skill files."""

    prompt = str(inspection["declared_prompt_surface"])
    skill_values = inspection.get("declared_skill_surfaces")
    skills = (
        [str(value) for value in skill_values]
        if isinstance(skill_values, list)
        else []
    )
    six_stage_skills = [
        value for value in skills if value == _SIX_STAGE_SKILL_SUFFIX
    ]
    admitted = {prompt, *six_stage_skills}
    reasons: list[dict[str, str]] = []
    if len(six_stage_skills) != 1:
        reasons.append(_reason("six_stage_skill_surface_not_unique"))

    allowed: set[str] = set()
    seen: set[str] = set()
    if isinstance(requested, (str, bytes)):
        return allowed, [
            *reasons,
            _reason("invalid_allowed_mutation_surface"),
        ]
    for value in requested:
        if not isinstance(value, str) or not value.strip():
            reasons.append(_reason("invalid_allowed_mutation_surface"))
            continue
        relative = Path(value.strip())
        if relative.is_absolute() or ".." in relative.parts:
            reasons.append(_reason("invalid_allowed_mutation_surface"))
            continue
        normalized = relative.as_posix()
        if normalized in seen:
            reasons.append(
                _reason("duplicate_allowed_mutation_surface", path=normalized)
            )
            continue
        seen.add(normalized)
        if normalized not in admitted:
            reasons.append(
                _reason(
                    "mutation_surface_not_prompt_or_six_stage_skill",
                    path=normalized,
                )
            )
            continue
        allowed.add(normalized)
    if not requested:
        reasons.append(_reason("no_allowed_mutation_surfaces"))
    return allowed, reasons


def _changed_text(parent: str, candidate: str) -> str:
    """Return only inserted/replaced candidate text, excluding common spans."""

    matcher = difflib.SequenceMatcher(None, parent, candidate, autojunk=False)
    return "\n".join(
        candidate[candidate_start:candidate_end]
        for tag, _parent_start, _parent_end, candidate_start, candidate_end in (
            matcher.get_opcodes()
        )
        if tag in {"insert", "replace"} and candidate_start != candidate_end
    )


def _contains_term(text: str, term: str) -> bool:
    """Match one label as a token, treating space/dash/underscore alike."""

    pieces = [
        re.escape(value)
        for value in re.split(r"[\s_-]+", term.casefold().strip())
        if value
    ]
    if not pieces:
        return False
    pattern = r"(?<![a-z0-9])" + r"[\s_-]+".join(pieces) + r"(?![a-z0-9])"
    return re.search(pattern, text.casefold()) is not None


def _deduplicate_reasons(
    reasons: Sequence[dict[str, str]],
) -> list[dict[str, str]]:
    unique = {
        (value.get("code", ""), value.get("path", ""), value.get("scope", ""))
        for value in reasons
    }
    result: list[dict[str, str]] = []
    for code, path, scope in sorted(unique):
        result.append(
            _reason(code, path=path or None, scope=scope or None)
        )
    return result


def inspect_qrs_candidate_boundary(
    *,
    frozen_h0_worker: str | Path,
    reviewed_candidate: str | Path,
    allowed_mutation_surfaces: Sequence[str],
    development_task_ids: Sequence[str],
    sealed_task_ids: Sequence[str],
    development_family_labels: Sequence[str],
    sealed_family_labels: Sequence[str],
) -> dict[str, object]:
    """Return a JSON-friendly PASS/REJECT verdict for one reviewed candidate."""

    development_tasks = _terms(
        development_task_ids, label="development_task_ids"
    )
    sealed_tasks = _terms(sealed_task_ids, label="sealed_task_ids")
    development_families = _terms(
        development_family_labels, label="development_family_labels"
    )
    sealed_families = _terms(
        sealed_family_labels, label="sealed_family_labels"
    )
    reasons: list[dict[str, str]] = []
    changed_files: set[str] = set()
    (
        h0_root,
        h0_files,
        h0_directories,
        h0_tree_reasons,
    ) = _ordinary_tree(frozen_h0_worker, role="frozen_h0")
    (
        candidate_root,
        candidate_files,
        candidate_directories,
        candidate_tree_reasons,
    ) = _ordinary_tree(reviewed_candidate, role="reviewed_candidate")
    reasons.extend(h0_tree_reasons)
    reasons.extend(candidate_tree_reasons)

    h0_inspection: dict[str, object] | None = None
    try:
        h0_inspection = inspect_base_harness(h0_root)
    except (FrozenBaseHarnessError, OSError, UnicodeError):
        reasons.append(_reason("frozen_h0_contract_invalid"))
    try:
        inspect_base_harness(candidate_root)
    except (FrozenBaseHarnessError, OSError, UnicodeError):
        reasons.append(_reason("reviewed_candidate_contract_invalid"))

    allowed: set[str] = set()
    if h0_inspection is not None:
        allowed, surface_reasons = _declared_mutation_surfaces(
            h0_inspection, allowed_mutation_surfaces
        )
        reasons.extend(surface_reasons)

    for relative in sorted(h0_directories - candidate_directories):
        reasons.append(_reason("tree_directory_removed", path=relative))
    for relative in sorted(candidate_directories - h0_directories):
        reasons.append(_reason("tree_directory_added", path=relative))
    for relative in sorted(h0_files | candidate_files):
        if relative not in h0_files:
            changed_files.add(relative)
            reasons.append(_reason("tree_file_added", path=relative))
            continue
        if relative not in candidate_files:
            changed_files.add(relative)
            reasons.append(_reason("tree_file_removed", path=relative))
            continue
        try:
            parent_bytes = h0_root.joinpath(relative).read_bytes()
            candidate_bytes = candidate_root.joinpath(relative).read_bytes()
        except OSError:
            reasons.append(_reason("worker_file_unreadable", path=relative))
            continue
        if parent_bytes == candidate_bytes:
            continue
        changed_files.add(relative)
        if relative not in allowed:
            reasons.append(
                _reason("non_allowed_file_changed", path=relative)
            )
            continue
        try:
            parent_text = parent_bytes.decode("utf-8")
            candidate_text = candidate_bytes.decode("utf-8")
        except UnicodeDecodeError:
            reasons.append(
                _reason("allowed_surface_not_utf8_text", path=relative)
            )
            continue
        changed_text = _changed_text(parent_text, candidate_text)
        term_groups = (
            ("development", "task_id", development_tasks),
            ("sealed", "task_id", sealed_tasks),
            ("development", "family_label", development_families),
            ("sealed", "family_label", sealed_families),
        )
        for scope, kind, terms in term_groups:
            if any(_contains_term(changed_text, term) for term in terms):
                reasons.append(
                    _reason(
                        f"changed_text_contains_{kind}",
                        path=relative,
                        scope=scope,
                    )
                )

    retained_reasons = _deduplicate_reasons(reasons)
    return {
        "schema_version": 1,
        "verdict": "PASS" if not retained_reasons else "REJECT",
        "reasons": retained_reasons,
        "changed_files": sorted(changed_files),
    }
