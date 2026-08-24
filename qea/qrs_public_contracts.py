"""Build the development-only public-contract tree used by QRS main.

The materializer reads only public task instructions named by the frozen QRS
method plan.  It copies their exact UTF-8 text and derives source-line clauses
without reading evaluation or result material.  Existing identical output is a
valid resume; any other pre-existing destination is rejected.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from collections.abc import Mapping
from pathlib import Path


_TASK_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_HEADING = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")
_LIST_ITEM = re.compile(r"^[ \t]*(?:[-+*]|\d+[.)])[ \t]+")
_FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,})")


class QRSPublicContractsError(ValueError):
    """The public source cannot form the QRS development contract tree."""


def _read_json(path: Path, *, label: str) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise QRSPublicContractsError(f"{label} is unavailable: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise QRSPublicContractsError(f"cannot read {label}: {path}") from exc
    if not isinstance(value, dict):
        raise QRSPublicContractsError(f"{label} must contain a JSON object")
    return value


def _safe_task_id(value: object, *, label: str) -> str:
    if not isinstance(value, str) or _TASK_ID.fullmatch(value) is None:
        raise QRSPublicContractsError(f"{label} is not a safe task ID: {value!r}")
    return value


def _method_partition(
    method: Mapping[str, object],
) -> tuple[list[str], list[str]]:
    raw_panels = method.get("development_panels")
    raw_sealed = method.get("sealed_main_tasks")
    if not isinstance(raw_panels, list) or not raw_panels:
        raise QRSPublicContractsError("method plan has no development panels")
    if not isinstance(raw_sealed, list):
        raise QRSPublicContractsError("method plan has no sealed task partition")

    development: list[str] = []
    expected_panel = 1
    for panel in raw_panels:
        if not isinstance(panel, Mapping):
            raise QRSPublicContractsError("development panel must be an object")
        if panel.get("panel_index") != expected_panel:
            raise QRSPublicContractsError(
                "development panels must be consecutively indexed from one"
            )
        task_ids = panel.get("task_ids")
        if not isinstance(task_ids, list) or not task_ids:
            raise QRSPublicContractsError(
                f"development panel {expected_panel} has no task IDs"
            )
        normalized = [
            _safe_task_id(value, label=f"panel {expected_panel} task")
            for value in task_ids
        ]
        if normalized != sorted(normalized) or len(normalized) != len(set(normalized)):
            raise QRSPublicContractsError(
                f"panel {expected_panel} task IDs must be sorted and unique"
            )
        development.extend(normalized)
        expected_panel += 1
    if len(development) != len(set(development)):
        raise QRSPublicContractsError(
            "a development task occurs in more than one panel"
        )

    sealed: list[str] = []
    for position, value in enumerate(raw_sealed, start=1):
        task_id = value.get("task_id") if isinstance(value, Mapping) else None
        sealed.append(_safe_task_id(task_id, label=f"sealed task {position}"))
    if len(sealed) != len(set(sealed)):
        raise QRSPublicContractsError("sealed task IDs must be unique")
    overlap = set(development).intersection(sealed)
    if overlap:
        raise QRSPublicContractsError(
            f"development and sealed tasks overlap: {sorted(overlap)}"
        )
    return sorted(development), sorted(sealed)


def _candidate_task_roots(source: Path) -> list[Path]:
    return [
        source / "tasks",
        source / "benchmarks" / "qfbench" / "tasks",
        source,
    ]


def _task_source_root(source: Path, task_ids: list[str]) -> Path:
    if source.is_symlink() or not source.is_dir():
        raise QRSPublicContractsError(
            f"QFBench public source root is unavailable: {source}"
        )
    matches: list[Path] = []
    for candidate in _candidate_task_roots(source):
        if candidate.is_symlink() or not candidate.is_dir():
            continue
        if all((candidate / task_id).is_dir() for task_id in task_ids):
            matches.append(candidate.resolve())
    unique = sorted(set(matches), key=str)
    if len(unique) != 1:
        raise QRSPublicContractsError(
            "QFBench public source must resolve to exactly one direct task root"
        )
    return unique[0]


def _instruction_bytes(task_root: Path, task_id: str) -> bytes:
    task_dir = task_root / task_id
    instruction = task_dir / "instruction.md"
    if task_dir.is_symlink() or not task_dir.is_dir():
        raise QRSPublicContractsError(
            f"public task directory must be regular and exact: {task_id}"
        )
    if task_dir.parent.resolve() != task_root.resolve() or task_dir.name != task_id:
        raise QRSPublicContractsError(
            f"public task directory is not a direct exact member: {task_id}"
        )
    if instruction.is_symlink() or not instruction.is_file():
        raise QRSPublicContractsError(
            f"public instruction must be a regular file: {task_id}"
        )
    try:
        payload = instruction.read_bytes()
        text = payload.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise QRSPublicContractsError(
            f"public instruction must be readable UTF-8: {task_id}"
        ) from exc
    if not text.strip() or "\x00" in text:
        raise QRSPublicContractsError(
            f"public instruction must contain non-empty UTF-8 text: {task_id}"
        )
    return payload


def _clause_payload(task_id: str, instruction: str) -> dict[str, object]:
    lines = instruction.splitlines()
    clauses: list[dict[str, object]] = []
    headings: list[str] = []
    index = 0

    def append(kind: str, start: int, end: int) -> None:
        text = "\n".join(lines[start - 1 : end])
        clauses.append(
            {
                "clause_id": f"{task_id}#c{len(clauses) + 1:04d}",
                "ordinal": len(clauses) + 1,
                "kind": kind,
                "heading_path": list(headings),
                "start_line": start,
                "end_line": end,
                "text": text,
            }
        )

    while index < len(lines):
        if not lines[index].strip():
            index += 1
            continue
        line_number = index + 1
        heading = _HEADING.match(lines[index])
        if heading is not None:
            level = len(heading.group(1))
            headings[level - 1 :] = [heading.group(2).strip()]
            append("heading", line_number, line_number)
            index += 1
            continue
        fence = _FENCE.match(lines[index])
        if fence is not None:
            marker = fence.group(1)
            character = marker[0]
            minimum = len(marker)
            end = index + 1
            while end < len(lines):
                stripped = lines[end].lstrip()
                if stripped.startswith(character * minimum):
                    end += 1
                    break
                end += 1
            append("code_block", line_number, end)
            index = end
            continue
        kind = "list_item" if _LIST_ITEM.match(lines[index]) else "paragraph"
        end = index + 1
        while end < len(lines) and lines[end].strip():
            if _HEADING.match(lines[end]) or _FENCE.match(lines[end]):
                break
            if kind == "list_item" and _LIST_ITEM.match(lines[end]):
                break
            if kind == "paragraph" and _LIST_ITEM.match(lines[end]):
                break
            end += 1
        append(kind, line_number, end)
        index = end

    covered = [
        line_number
        for clause in clauses
        for line_number in range(clause["start_line"], clause["end_line"] + 1)
        if lines[line_number - 1].strip()
    ]
    expected = [
        line_number
        for line_number, line in enumerate(lines, start=1)
        if line.strip()
    ]
    if covered != expected:
        raise QRSPublicContractsError(
            f"public clause coverage failed for {task_id}"
        )
    return {
        "schema_version": 1,
        "record_kind": "qrs_public_contract_clauses",
        "task_id": task_id,
        "source": "instruction.md",
        "clause_count": len(clauses),
        "clauses": clauses,
    }


def _expected_tree(
    task_root: Path,
    development: list[str],
    sealed_count: int,
) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for task_id in development:
        instruction = _instruction_bytes(task_root, task_id)
        files[f"{task_id}/instruction.md"] = instruction
        clauses = _clause_payload(task_id, instruction.decode("utf-8"))
        files[f"{task_id}/clauses.json"] = (
            json.dumps(clauses, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        ).encode("utf-8")
    manifest = {
        "schema_version": 1,
        "record_kind": "qrs_development_public_contracts",
        "status": "complete",
        "layout": "<root>/<development-task-id>/{instruction.md,clauses.json}",
        "development_only": True,
        "development_task_count": len(development),
        "development_task_ids": development,
        "sealed_task_count": sealed_count,
        "sealed_materialized": False,
    }
    files["QRS-PUBLIC-CONTRACTS.json"] = (
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    return files


def _existing_tree(destination: Path) -> tuple[set[str], dict[str, bytes]]:
    if destination.is_symlink() or not destination.is_dir():
        raise QRSPublicContractsError(
            f"existing destination must be a regular directory: {destination}"
        )
    directories: set[str] = set()
    files: dict[str, bytes] = {}
    for path in sorted(destination.rglob("*"), key=str):
        if path.is_symlink():
            raise QRSPublicContractsError(
                f"existing destination contains a symbolic link: {path}"
            )
        if path.is_dir():
            directories.add(path.relative_to(destination).as_posix())
            continue
        if not path.is_file():
            raise QRSPublicContractsError(
                f"existing destination contains a non-regular member: {path}"
            )
        files[path.relative_to(destination).as_posix()] = path.read_bytes()
    return directories, files


def materialize_qrs_public_contracts(
    *,
    qfbench_public_source_root: str | Path,
    method_plan_path: str | Path,
    destination: str | Path,
) -> dict[str, object]:
    """Materialize or verify one exact development-only contract directory."""

    method_file = Path(method_plan_path).expanduser().resolve()
    source = Path(qfbench_public_source_root).expanduser().resolve()
    target = Path(destination).expanduser().resolve()
    method = _read_json(method_file, label="QRS method plan")
    development, sealed = _method_partition(method)
    task_root = _task_source_root(source, development)
    expected = _expected_tree(task_root, development, len(sealed))

    if target.exists() or target.is_symlink():
        observed_directories, observed_files = _existing_tree(target)
        expected_directories = set(development)
        if (
            observed_directories != expected_directories
            or observed_files != expected
        ):
            raise QRSPublicContractsError(
                "existing destination differs from the requested public contracts"
            )
        return {
            "schema_version": 1,
            "status": "complete",
            "destination": str(target),
            "development_task_count": len(development),
            "sealed_task_count": len(sealed),
            "resumed_identical": True,
        }

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_root = Path(
        tempfile.mkdtemp(prefix=f".{target.name}-", dir=target.parent)
    )
    staging = temporary_root / "contracts"
    try:
        for relative, payload in expected.items():
            output = staging / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(payload)
        os.replace(staging, target)
    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)
    return {
        "schema_version": 1,
        "status": "complete",
        "destination": str(target),
        "development_task_count": len(development),
        "sealed_task_count": len(sealed),
        "resumed_identical": False,
    }


__all__ = ["QRSPublicContractsError", "materialize_qrs_public_contracts"]
