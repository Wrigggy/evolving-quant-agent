"""Deterministic, answer-free indexing of public task contracts.

The index preserves the exact public ``instruction.md`` bytes for each task and
adds stable clause records with source-line provenance.  It does not inspect
tests, solutions, reference data, verifier output, or any other evaluator-only
surface.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Mapping


_TASK_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_HEADING = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")
_LIST_ITEM = re.compile(r"^[ \t]*(?:[-+*]|\d+[.)])[ \t]+")
_FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,})")
_MAX_INSTRUCTION_BYTES = 2 * 1024 * 1024
_INDEX_SCHEMA_VERSION = 2
_INDEX_PROTOCOL = "public_contract_clauses_v2"
_SOURCE_IDENTITY_PROTOCOL = "pinned_public_role_instructions_v1"


class PublicContractEvidenceError(ValueError):
    """A public instruction corpus cannot be indexed safely or exactly."""


@dataclass(frozen=True)
class PublicContractClause:
    """One deterministic source span in a public task instruction."""

    clause_id: str
    ordinal: int
    kind: str
    heading_path: tuple[str, ...]
    start_line: int
    end_line: int
    text: str
    text_sha256: str

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["heading_path"] = list(self.heading_path)
        return payload


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _clause_kind(lines: list[str], default: str) -> str:
    if default != "paragraph":
        return default
    nonempty = [line for line in lines if line.strip()]
    if nonempty and all("|" in line for line in nonempty):
        return "table"
    return default


def split_public_contract(
    *,
    task_id: str,
    instruction: str,
) -> tuple[PublicContractClause, ...]:
    """Split one Markdown instruction into stable, source-addressable blocks.

    Headings, list items, fenced code blocks, tables, and prose paragraphs are
    kept distinct.  Every non-blank source line belongs to exactly one clause;
    blank separators are intentionally not semantic clauses.
    """

    if not isinstance(task_id, str) or _TASK_ID.fullmatch(task_id) is None:
        raise PublicContractEvidenceError(f"unsafe task ID: {task_id!r}")
    if not isinstance(instruction, str):
        raise PublicContractEvidenceError("public instruction must be UTF-8 text")

    source_lines = instruction.splitlines()
    clauses: list[PublicContractClause] = []
    heading_stack: list[str] = []
    buffer: list[str] = []
    buffer_start = 0
    buffer_kind = "paragraph"
    buffer_headings: tuple[str, ...] = ()
    fence_marker: str | None = None

    def emit(lines: list[str], start_line: int, end_line: int, kind: str) -> None:
        if not lines or not any(line.strip() for line in lines):
            return
        text = "\n".join(lines)
        ordinal = len(clauses) + 1
        clauses.append(
            PublicContractClause(
                clause_id=f"{task_id}#c{ordinal:04d}",
                ordinal=ordinal,
                kind=_clause_kind(lines, kind),
                heading_path=buffer_headings,
                start_line=start_line,
                end_line=end_line,
                text=text,
                text_sha256=_sha256(text.encode("utf-8")),
            )
        )

    def flush(end_line: int) -> None:
        nonlocal buffer, buffer_start, buffer_kind, buffer_headings
        if buffer:
            emit(buffer, buffer_start, end_line, buffer_kind)
        buffer = []
        buffer_start = 0
        buffer_kind = "paragraph"
        buffer_headings = ()

    for line_number, line in enumerate(source_lines, start=1):
        if fence_marker is not None:
            buffer.append(line)
            stripped = line.lstrip()
            if stripped.startswith(fence_marker):
                flush(line_number)
                fence_marker = None
            continue

        fence = _FENCE.match(line)
        if fence is not None:
            flush(line_number - 1)
            marker = fence.group(1)
            fence_marker = marker[0] * len(marker)
            buffer = [line]
            buffer_start = line_number
            buffer_kind = "code_block"
            buffer_headings = tuple(heading_stack)
            continue

        heading = _HEADING.match(line)
        if heading is not None:
            flush(line_number - 1)
            level = len(heading.group(1))
            title = heading.group(2).strip()
            heading_stack[level - 1 :] = [title]
            buffer_headings = tuple(heading_stack)
            emit([line], line_number, line_number, "heading")
            buffer_headings = ()
            continue

        if not line.strip():
            flush(line_number - 1)
            continue

        if _LIST_ITEM.match(line) is not None:
            flush(line_number - 1)
            buffer = [line]
            buffer_start = line_number
            buffer_kind = "list_item"
            buffer_headings = tuple(heading_stack)
            continue

        if not buffer:
            buffer = [line]
            buffer_start = line_number
            buffer_kind = "paragraph"
            buffer_headings = tuple(heading_stack)
        else:
            buffer.append(line)

    flush(len(source_lines))

    covered_lines: list[int] = []
    for clause in clauses:
        covered_lines.extend(
            line_number
            for line_number in range(clause.start_line, clause.end_line + 1)
            if source_lines[line_number - 1].strip()
        )
    expected_lines = [
        index
        for index, line in enumerate(source_lines, start=1)
        if line.strip()
    ]
    if covered_lines != expected_lines:
        raise PublicContractEvidenceError(
            f"deterministic clause coverage failed for task {task_id!r}"
        )
    return tuple(clauses)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _instruction_source(qfbench_root: Path, task_id: str) -> Path:
    if _TASK_ID.fullmatch(task_id) is None:
        raise PublicContractEvidenceError(f"unsafe task ID: {task_id!r}")
    task_root = qfbench_root / "tasks" / task_id
    instruction = task_root / "instruction.md"
    if task_root.is_symlink() or instruction.is_symlink():
        raise PublicContractEvidenceError(
            f"public instruction path must not use symlinks: {task_id}"
        )
    if not task_root.is_dir() or not instruction.is_file():
        raise PublicContractEvidenceError(
            f"public instruction is unavailable for task {task_id!r}"
        )
    resolved_root = qfbench_root.resolve(strict=True)
    resolved = instruction.resolve(strict=True)
    try:
        resolved.relative_to(resolved_root / "tasks" / task_id)
    except ValueError as exc:
        raise PublicContractEvidenceError(
            f"public instruction escapes task root: {task_id!r}"
        ) from exc
    return resolved


def _canonical_member_digest(
    root: Path,
    members: Iterable[str],
) -> str:
    digest = hashlib.sha256()
    for relative in sorted(members):
        payload = (root / relative).read_bytes()
        encoded = relative.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def public_contract_source_identity(
    *,
    public_task_root: str | Path,
    task_ids: Iterable[str],
    benchmark_commit: str,
) -> dict[str, object]:
    """Bind exact public instructions to one verified public role manifest.

    The returned member digest covers both each canonical source path and its
    exact bytes.  It is included in the evidence contract and is deterministically
    derived from the protocol/task panel plus public role manifest already pinned
    by the materialized A6 launch identity.  A self-consistent corpus built from
    another checkout or role tree therefore cannot substitute for the source.
    """

    normalized_task_ids = tuple(str(value) for value in task_ids)
    if not normalized_task_ids or len(set(normalized_task_ids)) != len(
        normalized_task_ids
    ):
        raise PublicContractEvidenceError(
            "public-contract task IDs must be non-empty and unique"
        )
    root = Path(public_task_root).expanduser()
    if root.is_symlink() or not root.is_dir():
        raise PublicContractEvidenceError(
            "public task root must be a regular role directory"
        )
    try:
        from .rootless_images import RootlessImageError, verify_role_root
    except ImportError as exc:
        raise PublicContractEvidenceError(
            "public role verification is unavailable in this runtime"
        ) from exc
    try:
        verified = verify_role_root(root, "public")
    except (OSError, RootlessImageError) as exc:
        raise PublicContractEvidenceError(
            f"public task role root is invalid: {exc}"
        ) from exc
    if verified.commit != benchmark_commit:
        raise PublicContractEvidenceError(
            "public task role manifest commit differs from the frozen benchmark"
        )
    revision = verified.root / ".qfbench-revision"
    if revision.is_symlink() or not revision.is_file():
        raise PublicContractEvidenceError(
            "public task role root has no pinned revision file"
        )
    try:
        observed_revision = revision.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError) as exc:
        raise PublicContractEvidenceError(
            "public task role revision is unreadable"
        ) from exc
    if observed_revision != benchmark_commit:
        raise PublicContractEvidenceError(
            "public task role revision differs from the frozen benchmark"
        )
    missing_tasks = sorted(set(normalized_task_ids) - set(verified.task_ids))
    if missing_tasks:
        raise PublicContractEvidenceError(
            "public task role manifest is missing frozen tasks: "
            + ", ".join(missing_tasks)
        )

    members: list[dict[str, object]] = []
    member_paths: list[str] = []
    for task_id in normalized_task_ids:
        source_path = f"tasks/{task_id}/instruction.md"
        manifest_record = verified.records.get(source_path)
        if not isinstance(manifest_record, Mapping):
            raise PublicContractEvidenceError(
                f"public task role manifest has no instruction: {task_id!r}"
            )
        source = _instruction_source(verified.root, task_id)
        payload = source.read_bytes()
        if len(payload) > _MAX_INSTRUCTION_BYTES:
            raise PublicContractEvidenceError(
                f"public instruction exceeds size limit: {task_id!r}"
            )
        sha256 = _sha256(payload)
        if (
            manifest_record.get("sha256") != sha256
            or manifest_record.get("size_bytes") != len(payload)
        ):
            raise PublicContractEvidenceError(
                f"public task role instruction identity differs: {task_id!r}"
            )
        member_paths.append(source_path)
        members.append(
            {
                "task_id": task_id,
                "source_path": source_path,
                "sha256": sha256,
                "size_bytes": len(payload),
            }
        )
    return {
        "schema_version": 1,
        "protocol": _SOURCE_IDENTITY_PROTOCOL,
        "benchmark_commit": benchmark_commit,
        "task_ids": list(normalized_task_ids),
        "public_task_role_manifest_sha256": verified.manifest_sha256,
        "instruction_member_count": len(members),
        "instruction_members_sha256": _canonical_member_digest(
            verified.root, member_paths
        ),
        "members": members,
    }


def build_public_contract_index(
    *,
    qfbench_root: str | Path,
    task_ids: Iterable[str],
    destination: str | Path,
    benchmark_commit: str,
) -> dict[str, object]:
    """Copy and index only the named tasks' public ``instruction.md`` files."""

    normalized_task_ids = tuple(str(value) for value in task_ids)
    if not normalized_task_ids or len(set(normalized_task_ids)) != len(
        normalized_task_ids
    ):
        raise PublicContractEvidenceError(
            "public-contract task IDs must be non-empty and unique"
        )
    source_identity = public_contract_source_identity(
        public_task_root=qfbench_root,
        task_ids=normalized_task_ids,
        benchmark_commit=benchmark_commit,
    )
    root = Path(qfbench_root).expanduser().resolve(strict=True)
    source_members = {
        str(record["task_id"]): record
        for record in source_identity["members"]
        if isinstance(record, Mapping)
    }
    output = Path(destination)
    if output.exists():
        raise PublicContractEvidenceError(
            f"public-contract destination already exists: {output}"
        )
    output.mkdir(parents=True)

    task_records: list[dict[str, object]] = []
    clause_count = 0
    for task_id in normalized_task_ids:
        source = _instruction_source(root, task_id)
        payload = source.read_bytes()
        if len(payload) > _MAX_INSTRUCTION_BYTES:
            raise PublicContractEvidenceError(
                f"public instruction exceeds size limit: {task_id!r}"
            )
        try:
            instruction = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise PublicContractEvidenceError(
                f"public instruction is not UTF-8: {task_id!r}"
            ) from exc
        clauses = split_public_contract(task_id=task_id, instruction=instruction)
        task_root = output / task_id
        task_root.mkdir()
        instruction_path = task_root / "instruction.md"
        instruction_path.write_bytes(payload)
        clauses_path = task_root / "clauses.json"
        clause_payload = {
            "schema_version": _INDEX_SCHEMA_VERSION,
            "protocol": _INDEX_PROTOCOL,
            "task_id": task_id,
            "source_path": f"tasks/{task_id}/instruction.md",
            "instruction_path": f"contracts/{task_id}/instruction.md",
            "instruction_sha256": _sha256(payload),
            "source_line_count": len(instruction.splitlines()),
            "nonblank_source_line_count": sum(
                bool(line.strip()) for line in instruction.splitlines()
            ),
            "clause_count": len(clauses),
            "clauses": [clause.as_dict() for clause in clauses],
        }
        _write_json(clauses_path, clause_payload)
        clause_count += len(clauses)
        task_records.append(
            {
                "task_id": task_id,
                "source_path": source_members[task_id]["source_path"],
                "instruction_path": f"contracts/{task_id}/instruction.md",
                "clauses_path": f"contracts/{task_id}/clauses.json",
                "instruction_sha256": clause_payload["instruction_sha256"],
                "clause_count": len(clauses),
            }
        )

    index = {
        "schema_version": _INDEX_SCHEMA_VERSION,
        "protocol": _INDEX_PROTOCOL,
        "benchmark_commit": benchmark_commit,
        "task_ids": list(normalized_task_ids),
        "task_count": len(normalized_task_ids),
        "clause_count": clause_count,
        "tasks": task_records,
        "source_identity": source_identity,
        "answer_free": True,
        "private_evaluator_material": False,
        "official_solutions": False,
    }
    _write_json(output / "index.json", index)
    return index


def load_public_contract_clause(
    *,
    evidence_root: str | Path,
    task_id: str,
    clause_id: str,
) -> tuple[dict[str, object], tuple[str, str]]:
    """Load one clause and revalidate it against the copied exact instruction."""

    if not isinstance(task_id, str) or _TASK_ID.fullmatch(task_id) is None:
        raise PublicContractEvidenceError(f"unsafe task ID: {task_id!r}")
    if not isinstance(clause_id, str) or re.fullmatch(
        re.escape(task_id) + r"#c[0-9]{4,}", clause_id
    ) is None:
        raise PublicContractEvidenceError(f"unsafe clause ID: {clause_id!r}")
    root = Path(evidence_root).resolve(strict=True)
    contracts_root = root / "contracts"
    task_root = contracts_root / task_id
    clauses_path = task_root / "clauses.json"
    instruction_path = task_root / "instruction.md"
    if contracts_root.is_symlink() or task_root.is_symlink():
        raise PublicContractEvidenceError(
            f"indexed public contract must not use symlinks: {task_id!r}"
        )
    for path in (clauses_path, instruction_path):
        if path.is_symlink() or not path.is_file():
            raise PublicContractEvidenceError(
                f"indexed public contract is unavailable: {task_id!r}"
            )
        try:
            path.resolve(strict=True).relative_to(root)
        except ValueError as exc:
            raise PublicContractEvidenceError(
                f"indexed public contract escapes evidence root: {task_id!r}"
            ) from exc
    try:
        payload = json.loads(clauses_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PublicContractEvidenceError(
            f"indexed clause JSON is invalid: {task_id!r}"
        ) from exc
    if not isinstance(payload, Mapping):
        raise PublicContractEvidenceError("indexed clause payload must be an object")
    instruction_bytes = instruction_path.read_bytes()
    if payload.get("instruction_sha256") != _sha256(instruction_bytes):
        raise PublicContractEvidenceError("indexed public instruction digest differs")
    try:
        instruction = instruction_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PublicContractEvidenceError(
            "indexed public instruction is not UTF-8"
        ) from exc
    clauses = split_public_contract(task_id=task_id, instruction=instruction)
    indexed = payload.get("clauses")
    if not isinstance(indexed, list) or indexed != [
        clause.as_dict() for clause in clauses
    ]:
        raise PublicContractEvidenceError("indexed public clauses differ from source")
    selected = next(
        (clause.as_dict() for clause in clauses if clause.clause_id == clause_id),
        None,
    )
    if selected is None:
        raise PublicContractEvidenceError(
            f"unknown public contract clause: {clause_id!r}"
        )
    return selected, (
        clauses_path.relative_to(root).as_posix(),
        instruction_path.relative_to(root).as_posix(),
    )


def validate_public_contract_index(
    *,
    evidence_root: str | Path,
    public_task_root: str | Path,
    task_ids: Iterable[str],
    benchmark_commit: str,
) -> dict[str, object]:
    """Revalidate a corpus against the exact frozen panel and public role root."""

    expected_task_ids = [str(value) for value in task_ids]
    if not expected_task_ids or len(set(expected_task_ids)) != len(expected_task_ids):
        raise PublicContractEvidenceError(
            "public-contract task IDs must be non-empty and unique"
        )
    source_identity = public_contract_source_identity(
        public_task_root=public_task_root,
        task_ids=expected_task_ids,
        benchmark_commit=benchmark_commit,
    )
    source_root = Path(public_task_root).expanduser().resolve(strict=True)
    root = Path(evidence_root).expanduser()
    if root.is_symlink() or not root.is_dir():
        raise PublicContractEvidenceError("evidence root must be a regular directory")
    root = root.resolve(strict=True)
    contracts_root = root / "contracts"
    index_path = contracts_root / "index.json"
    if contracts_root.is_symlink() or index_path.is_symlink() or not index_path.is_file():
        raise PublicContractEvidenceError("public-contract index is unavailable")
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PublicContractEvidenceError("public-contract index is invalid JSON") from exc
    expected_keys = {
        "answer_free",
        "benchmark_commit",
        "clause_count",
        "official_solutions",
        "private_evaluator_material",
        "protocol",
        "schema_version",
        "source_identity",
        "task_count",
        "task_ids",
        "tasks",
    }
    if not isinstance(index, dict) or set(index) != expected_keys:
        raise PublicContractEvidenceError("public-contract index fields differ")
    if index.get("source_identity") != source_identity:
        raise PublicContractEvidenceError(
            "public-contract source identity differs from the pinned public "
            "task role root"
        )
    if (
        index.get("schema_version") != _INDEX_SCHEMA_VERSION
        or index.get("protocol") != _INDEX_PROTOCOL
        or index.get("benchmark_commit") != benchmark_commit
        or index.get("task_ids") != expected_task_ids
        or index.get("task_count") != len(expected_task_ids)
        or index.get("answer_free") is not True
        or index.get("private_evaluator_material") is not False
        or index.get("official_solutions") is not False
    ):
        raise PublicContractEvidenceError(
            "public-contract index identity differs from the frozen panel"
        )
    task_records = index.get("tasks")
    if not isinstance(task_records, list) or len(task_records) != len(
        expected_task_ids
    ):
        raise PublicContractEvidenceError("public-contract task records differ")
    observed_clause_count = 0
    for task_id, record in zip(expected_task_ids, task_records):
        if not isinstance(record, dict) or set(record) != {
            "clause_count",
            "clauses_path",
            "instruction_path",
            "instruction_sha256",
            "source_path",
            "task_id",
        }:
            raise PublicContractEvidenceError(
                f"public-contract task record differs: {task_id!r}"
            )
        expected_instruction = f"contracts/{task_id}/instruction.md"
        expected_clauses = f"contracts/{task_id}/clauses.json"
        expected_source = f"tasks/{task_id}/instruction.md"
        clause_count = record.get("clause_count")
        instruction_sha256 = record.get("instruction_sha256")
        if (
            record.get("task_id") != task_id
            or record.get("source_path") != expected_source
            or record.get("instruction_path") != expected_instruction
            or record.get("clauses_path") != expected_clauses
            or isinstance(clause_count, bool)
            or not isinstance(clause_count, int)
            or clause_count <= 0
            or not isinstance(instruction_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", instruction_sha256) is None
        ):
            raise PublicContractEvidenceError(
                f"public-contract task identity differs: {task_id!r}"
            )
        first_clause, paths = load_public_contract_clause(
            evidence_root=root,
            task_id=task_id,
            clause_id=f"{task_id}#c0001",
        )
        if first_clause.get("ordinal") != 1 or paths != (
            expected_clauses,
            expected_instruction,
        ):
            raise PublicContractEvidenceError(
                f"public-contract clause paths differ: {task_id!r}"
            )
        instruction_path = root / expected_instruction
        source_path = source_root / expected_source
        clauses_path = root / expected_clauses
        clauses_payload = json.loads(clauses_path.read_text(encoding="utf-8"))
        instruction_bytes = instruction_path.read_bytes()
        if instruction_bytes != source_path.read_bytes():
            raise PublicContractEvidenceError(
                "indexed public instruction differs from the pinned public "
                f"task role root: {task_id!r}"
            )
        if (
            _sha256(instruction_bytes) != instruction_sha256
            or not isinstance(clauses_payload, Mapping)
            or clauses_payload.get("clause_count") != clause_count
        ):
            raise PublicContractEvidenceError(
                f"public-contract task digest or count differs: {task_id!r}"
            )
        observed_clause_count += clause_count
    if index.get("clause_count") != observed_clause_count:
        raise PublicContractEvidenceError("public-contract clause_count differs")
    return index


__all__ = [
    "PublicContractClause",
    "PublicContractEvidenceError",
    "build_public_contract_index",
    "load_public_contract_clause",
    "public_contract_source_identity",
    "split_public_contract",
    "validate_public_contract_index",
]
