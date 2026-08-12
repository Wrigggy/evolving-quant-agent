"""Deterministic size and surface metrics for one harness mutation."""

from __future__ import annotations

import ast
import difflib
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Iterable, Mapping


_COMPONENT_ROLES = frozenset(
    {
        "systemprompt",
        "agent_config",
        "tool_descriptions",
        "tools",
        "validator",
        "skills",
        "memory",
        "middleware",
        "routing",
    }
)


def _files(root: Path) -> dict[str, bytes]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError(f"worker root must be one regular directory: {root}")
    payloads: dict[str, bytes] = {}
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise ValueError(f"worker mutation contains a symlink: {relative}")
        if path.is_file():
            payloads[relative] = path.read_bytes()
    return payloads


def component_role(relative: str) -> str:
    """Map one candidate path to the full-harness component ontology."""

    if relative == "systemprompt.md":
        return "systemprompt"
    if relative == "agent.yaml":
        return "agent_config"
    parts = PurePosixPath(relative).parts
    if parts and parts[0] in _COMPONENT_ROLES:
        return parts[0]
    return "other"


def surface_class(relative: str) -> str:
    """Separate prompt/description edits from executable code and config."""

    path = PurePosixPath(relative)
    role = component_role(relative)
    if relative == "systemprompt.md" or role in {"tool_descriptions", "memory"}:
        return "prompt_or_description"
    if role == "skills" and path.suffix.casefold() in {".md", ".txt", ".yaml", ".yml"}:
        return "prompt_or_description"
    if path.suffix.casefold() == ".py":
        return "executable_code"
    if relative == "agent.yaml" or path.suffix.casefold() in {".yaml", ".yml", ".toml"}:
        return "configuration"
    return "other"


def _text_lines(payload: bytes) -> list[str]:
    try:
        return payload.decode("utf-8").splitlines(keepends=True)
    except UnicodeDecodeError:
        return []


def _line_delta(before: bytes, after: bytes) -> dict[str, int]:
    left = _text_lines(before)
    right = _text_lines(after)
    if (not left and before) or (not right and after):
        return {
            "added_lines": 0,
            "deleted_lines": 0,
            "added_bytes": len(after),
            "deleted_bytes": len(before),
        }
    added_lines = deleted_lines = added_bytes = deleted_bytes = 0
    matcher = difflib.SequenceMatcher(a=left, b=right, autojunk=False)
    for tag, left_start, left_end, right_start, right_end in matcher.get_opcodes():
        if tag in {"delete", "replace"}:
            chunk = left[left_start:left_end]
            deleted_lines += len(chunk)
            deleted_bytes += sum(len(value.encode("utf-8")) for value in chunk)
        if tag in {"insert", "replace"}:
            chunk = right[right_start:right_end]
            added_lines += len(chunk)
            added_bytes += sum(len(value.encode("utf-8")) for value in chunk)
    return {
        "added_lines": added_lines,
        "deleted_lines": deleted_lines,
        "added_bytes": added_bytes,
        "deleted_bytes": deleted_bytes,
    }


def _top_level_symbols(payload: bytes, relative: str) -> dict[str, str]:
    if not relative.endswith(".py"):
        return {}
    try:
        tree = ast.parse(payload.decode("utf-8"), filename=relative)
    except (UnicodeDecodeError, SyntaxError):
        return {}
    symbols: dict[str, str] = {}
    for node in tree.body:
        names: list[str] = []
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names = [node.name]
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    names.append(target.id)
        for name in names:
            symbols[name] = ast.dump(node, include_attributes=False)
    return symbols


def measure_mutation(
    *,
    before_root: str | Path,
    after_root: str | Path,
    declared_roles: Iterable[str] = (),
) -> dict[str, object]:
    """Measure a mutation without changing or enforcing its admission envelope."""

    before = _files(Path(before_root).resolve())
    after = _files(Path(after_root).resolve())
    changed_paths = sorted(
        relative
        for relative in set(before) | set(after)
        if before.get(relative) != after.get(relative)
    )
    path_records: list[dict[str, object]] = []
    totals = defaultdict(int)
    ast_records: list[dict[str, object]] = []
    for relative in changed_paths:
        left = before.get(relative, b"")
        right = after.get(relative, b"")
        status = (
            "added"
            if relative not in before
            else "deleted" if relative not in after else "modified"
        )
        delta = _line_delta(left, right)
        for key, value in delta.items():
            totals[key] += value
        totals[f"{status}_files"] += 1
        role = component_role(relative)
        category = surface_class(relative)
        path_records.append(
            {
                "path": relative,
                "status": status,
                "component_role": role,
                "surface_class": category,
                "before_bytes": len(left),
                "after_bytes": len(right),
                **delta,
            }
        )
        before_symbols = _top_level_symbols(left, relative)
        after_symbols = _top_level_symbols(right, relative)
        if before_symbols or after_symbols:
            ast_records.append(
                {
                    "path": relative,
                    "added_symbols": sorted(set(after_symbols) - set(before_symbols)),
                    "deleted_symbols": sorted(set(before_symbols) - set(after_symbols)),
                    "changed_symbols": sorted(
                        name
                        for name in set(before_symbols) & set(after_symbols)
                        if before_symbols[name] != after_symbols[name]
                    ),
                }
            )
    actual_roles = sorted(
        {component_role(relative) for relative in changed_paths}
    )
    normalized_declared = sorted({str(value) for value in declared_roles})
    surface_counts = {
        name: sum(record["surface_class"] == name for record in path_records)
        for name in (
            "prompt_or_description",
            "executable_code",
            "configuration",
            "other",
        )
    }
    return {
        "schema_version": 1,
        "measurement_only": True,
        "mutation_envelope_changed": False,
        "changed_file_count": len(changed_paths),
        "added_file_count": totals["added_files"],
        "deleted_file_count": totals["deleted_files"],
        "modified_file_count": totals["modified_files"],
        "added_lines": totals["added_lines"],
        "deleted_lines": totals["deleted_lines"],
        "added_bytes": totals["added_bytes"],
        "deleted_bytes": totals["deleted_bytes"],
        "net_tree_bytes": (
            sum(map(len, after.values())) - sum(map(len, before.values()))
        ),
        "component_roles": actual_roles,
        "surface_file_counts": surface_counts,
        "prompt_or_description_only": bool(changed_paths)
        and surface_counts["prompt_or_description"] == len(changed_paths),
        "touches_executable_code": surface_counts["executable_code"] > 0,
        "python_top_level_symbols": ast_records,
        "declared_roles": normalized_declared,
        "declared_roles_match_actual": normalized_declared == actual_roles,
        "files": path_records,
    }


__all__ = ["component_role", "measure_mutation", "surface_class"]
