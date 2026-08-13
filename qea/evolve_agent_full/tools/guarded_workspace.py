"""Capability-limited workspace tools for the full-harness evolver.

The evolver may read its immutable evidence and framework-reference corpora and
may read/write only the candidate worker tree.  It never receives a
general-purpose shell or Python execution primitive.
"""

from __future__ import annotations

import ast
import csv
import difflib
import hashlib
import importlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from collections import Counter, defaultdict
from typing import Any, Mapping

try:
    from qea.public_contract_evidence import (
        PublicContractEvidenceError,
        load_public_contract_clause,
    )
except ModuleNotFoundError:  # Uploaded Evolver runtime exposes qea modules flat.
    from public_contract_evidence import (  # type: ignore[no-redef]
        PublicContractEvidenceError,
        load_public_contract_clause,
    )


_ROOT_ENV = {
    "candidate": "QEA_CANDIDATE_ROOT",
    "evidence": "QEA_EVIDENCE_ROOT",
    "reference": "QEA_REFERENCE_ROOT",
}
_MAX_LISTED_PATHS = 2_000
_MAX_READ_BYTES = 256_000
_MAX_WRITE_BYTES = 512_000
_MAX_SEARCH_FILES = 2_000
_MAX_SEARCH_LINE_BYTES = 8_000
_MAX_PROCESS_OUTPUT_BYTES = 128_000
_MAX_DISCOVERY_RETURN_BYTES = 256_000
_DISCOVERY_STATE_NAME = "discovery-hypothesis.json"
_PROBE_LOG_NAME = "probe-log.jsonl"
_COMPONENT_TEST_LOG_NAME = "component-tests.jsonl"
_PROBE_ID = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_SEMANTIC_PROBE_KIND = "typed_contract_artifact_trace_v1"
_ANSWER_FREE_FEEDBACK_TIER = "answer_free_public_process"
_TRACE_PHASE_PATTERNS = {
    "task_interpretation": re.compile(
        r"\b(?:instruction|requirement|deliverable|contract|specification)\b",
        re.IGNORECASE,
    ),
    "input_inventory": re.compile(
        r"(?:<ToolUse>|\b)(?:ls|find|tree|pwd)\b", re.IGNORECASE
    ),
    "artifact_construction": re.compile(
        r"(?:/root/output|\boutput/|\bartifact|\bwrite|\bsave|to_csv|to_json)",
        re.IGNORECASE,
    ),
    "validation": re.compile(
        r"\b(?:pytest|validate|validation|verify|verification|assert|check)\b",
        re.IGNORECASE,
    ),
    "output_inspection": re.compile(
        r"\b(?:cat|head|tail|jq|inspect|re-read|read back)\b.{0,160}"
        r"(?:/root/output|\boutput/|\bartifact|deliverable)",
        re.IGNORECASE,
    ),
    "completion": re.compile(
        r"\b(?:complete|completed|done|finished|final answer)\b", re.IGNORECASE
    ),
}
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
_QUANT_FAILURE_CLASSES = frozenset(
    {
        "interface_delivery",
        "data_universe_preprocessing",
        "temporal_causality",
        "formula_parameterization",
        "signal_direction",
        "portfolio_accounting",
        "runtime_completion",
        "isolated_task_specific",
        "unknown",
    }
)
_QUANT_BREAKDOWN_STAGES = frozenset(
    {
        "source_retrieval",
        "requirement_comprehension",
        "specification_preservation",
        "implementation_realization",
        "execution_completion",
        "unable_to_decide",
    }
)


class GuardedWorkspaceError(ValueError):
    """Raised when an evolver operation violates the workspace contract."""


def _root(source: str) -> Path:
    env_name = _ROOT_ENV.get(source)
    if env_name is None:
        raise GuardedWorkspaceError(f"unknown workspace source: {source!r}")
    raw = os.environ.get(env_name)
    if not raw:
        raise GuardedWorkspaceError(f"required environment variable {env_name} is unset")
    root = Path(raw)
    if not root.is_dir():
        raise GuardedWorkspaceError(f"workspace root does not exist: {source}")
    return root.resolve(strict=True)


def _runtime_root() -> Path:
    raw = os.environ.get("QEA_RUNTIME_ROOT")
    if not raw:
        raise GuardedWorkspaceError(
            "required environment variable QEA_RUNTIME_ROOT is unset"
        )
    root = Path(raw)
    if not root.is_dir():
        raise GuardedWorkspaceError("runtime root does not exist")
    return root.resolve(strict=True)


def _relative(value: str, *, label: str = "path") -> PurePosixPath:
    if not isinstance(value, str) or not value or "\x00" in value or "\\" in value:
        raise GuardedWorkspaceError(f"unsafe relative {label}: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise GuardedWorkspaceError(f"unsafe relative {label}: {value!r}")
    return path


def _reject_symlinks(root: Path, relative: PurePosixPath) -> None:
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise GuardedWorkspaceError(f"symlink paths are forbidden: {relative}")
        if not current.exists():
            break


def _resolve(source: str, value: str, *, must_exist: bool) -> tuple[Path, str]:
    relative = _relative(value)
    root = _root(source)
    _reject_symlinks(root, relative)
    target = root.joinpath(*relative.parts)
    if must_exist and not target.exists():
        raise GuardedWorkspaceError(f"path does not exist: {relative}")
    resolved = target.resolve(strict=must_exist)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise GuardedWorkspaceError(f"path escapes {source} workspace: {relative}") from exc
    return resolved, relative.as_posix()


def _audit(
    *, operation: str, source: str, relative_path: str, bytes_returned: int = 0
) -> None:
    raw = os.environ.get("QEA_ACCESS_LOG")
    if not raw:
        raise GuardedWorkspaceError("required environment variable QEA_ACCESS_LOG is unset")
    log_path = Path(raw)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "operation": operation,
        "source": source,
        "relative_path": relative_path,
        "bytes_returned": bytes_returned,
    }
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def _read_text(path: Path) -> str:
    if not path.is_file():
        raise GuardedWorkspaceError(f"not a regular file: {path.name}")
    size = path.stat().st_size
    if size > _MAX_READ_BYTES:
        raise GuardedWorkspaceError(
            f"file exceeds {_MAX_READ_BYTES}-byte read limit: {path.name}"
        )
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise GuardedWorkspaceError(f"file is not UTF-8 text: {path.name}") from exc


def _result_path(name: str) -> Path:
    """Resolve one evolver-owned result file beside the append-only access log."""

    raw = os.environ.get("QEA_ACCESS_LOG")
    if not raw:
        raise GuardedWorkspaceError("required environment variable QEA_ACCESS_LOG is unset")
    log_path = Path(raw).resolve()
    if log_path.name != "access_log.jsonl":
        raise GuardedWorkspaceError("QEA_ACCESS_LOG must name access_log.jsonl")
    result_root = log_path.parent
    if not result_root.is_dir():
        raise GuardedWorkspaceError("evolver result root does not exist")
    return result_root / name


def _accessed_evidence_paths() -> set[str]:
    paths: set[str] = set()
    log_path = _result_path("access_log.jsonl")
    if not log_path.is_file():
        return paths
    for line in log_path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if (
            record.get("source") == "evidence"
            and record.get("operation")
            in {"read", "trace_slice", "compare", "probe", "semantic_probe"}
            and isinstance(record.get("relative_path"), str)
        ):
            paths.add(record["relative_path"])
    return paths


def _text(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GuardedWorkspaceError(f"{label} must be non-empty text")
    return value.strip()


def _text_list(
    value: object,
    *,
    label: str,
    minimum: int = 0,
) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise GuardedWorkspaceError(f"{label} must be a list of non-empty text")
    normalized = [item.strip() for item in value]
    if len(normalized) < minimum:
        raise GuardedWorkspaceError(
            f"{label} must contain at least {minimum} entries"
        )
    if len(set(normalized)) != len(normalized):
        raise GuardedWorkspaceError(f"{label} must not contain duplicates")
    return normalized


def _contract() -> dict[str, Any]:
    path, _ = _resolve("evidence", "contract.json", must_exist=True)
    try:
        payload = json.loads(_read_text(path))
    except json.JSONDecodeError as exc:
        raise GuardedWorkspaceError("evidence contract is invalid JSON") from exc
    if not isinstance(payload, Mapping):
        raise GuardedWorkspaceError("evidence contract must be an object")
    return dict(payload)


def _feedback_contract(contract: Mapping[str, object]) -> str:
    tier = contract.get("evaluator_feedback_tier")
    if tier is None and contract.get("stage") != "A6":
        # Preserve older A5 evidence contracts. A6 freezes the tier explicitly
        # and must fail closed if that identity field is absent.
        tier = _ANSWER_FREE_FEEDBACK_TIER
    if tier != _ANSWER_FREE_FEEDBACK_TIER:
        raise GuardedWorkspaceError("unsupported evaluator feedback tier")
    digest = contract.get("feedback_manifest_digest")
    if digest is not None and (
        not isinstance(digest, str) or _SHA256.fullmatch(digest) is None
    ):
        raise GuardedWorkspaceError("feedback_manifest_digest is invalid")
    return tier


def _probe_records() -> dict[str, dict[str, Any]]:
    path = _result_path(_PROBE_LOG_NAME)
    records: dict[str, dict[str, Any]] = {}
    if not path.is_file():
        return records
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        probe_id = payload.get("probe_id")
        if isinstance(probe_id, str):
            records[probe_id] = payload
    return records


def _require_intervention_unlocked() -> dict[str, Any]:
    path = _result_path(_DISCOVERY_STATE_NAME)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GuardedWorkspaceError(
            "candidate writes are locked; call unlock_candidate after evidence-based "
            "discovery"
        ) from exc
    if payload.get("schema_version") not in {1, 2, 3, 4}:
        raise GuardedWorkspaceError("candidate intervention state is invalid")
    if payload.get("unlocked") is not True:
        raise GuardedWorkspaceError("candidate writes are locked by the decision")
    return payload


def _evidence_kind(relative: str) -> str:
    name = PurePosixPath(relative).name
    parts = PurePosixPath(relative).parts
    if "worker_trace.jsonl" == name or "trace" in name:
        return "trace"
    if name in {"public_evaluation.json", "task_scores.json"}:
        return "outcome"
    if name == "process_summary.json":
        return "process"
    if name in {"worker_final.txt", "final.txt"}:
        return "final"
    if parts and parts[0] == "debugger":
        return "debugger"
    if parts and parts[0] == "contracts":
        return "public_contract"
    if parts and parts[0] == "history":
        return "history"
    if parts and parts[0] in {"candidate", "archive", "prior"}:
        return "candidate_history"
    if name == "contract.json":
        return "contract"
    return "other"


def _json_facts(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, RecursionError):
        return {}
    if not isinstance(payload, Mapping):
        return {"json_type": type(payload).__name__}
    facts: dict[str, Any] = {"top_level_keys": sorted(str(key) for key in payload)[:40]}
    for key in (
        "schema_version",
        "task_id",
        "checkpoint",
        "stage",
        "status",
        "official_reward",
        "reward",
        "component",
    ):
        value = payload.get(key)
        if isinstance(value, (str, int, float, bool)) or value is None:
            if key in payload:
                facts[key] = value
    tags = payload.get("diagnostic_tags")
    if isinstance(tags, list):
        facts["diagnostic_tags"] = [str(value) for value in tags[:20]]
    return facts


def map_evidence(max_files: int = 500) -> dict[str, Any]:
    """Return an agent-legible map of the authorized evidence corpus."""

    if not 1 <= max_files <= 1_000:
        raise GuardedWorkspaceError("max_files must be between 1 and 1000")
    root = _root("evidence")
    files: list[dict[str, Any]] = []
    categories: Counter[str] = Counter()
    tasks: dict[str, set[str]] = defaultdict(set)
    total_bytes = 0
    all_paths = [
        path
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.is_symlink()
    ]
    for path in all_paths[:max_files]:
        relative = path.relative_to(root).as_posix()
        _reject_symlinks(root, PurePosixPath(relative))
        size = path.stat().st_size
        total_bytes += size
        kind = _evidence_kind(relative)
        categories[kind] += 1
        parts = PurePosixPath(relative).parts
        task_id = None
        if "tasks" in parts:
            index = parts.index("tasks")
            if index + 1 < len(parts):
                task_id = parts[index + 1]
                tasks[task_id].add(kind)
        entry: dict[str, Any] = {
            "path": relative,
            "kind": kind,
            "bytes": size,
        }
        if task_id:
            entry["task_id"] = task_id
        try:
            text = _read_text(path)
        except GuardedWorkspaceError:
            text = ""
        if text:
            entry["lines"] = len(text.splitlines())
            if path.suffix == ".json":
                entry["facts"] = _json_facts(text)
        files.append(entry)
    payload = {
        "schema_version": 1,
        "file_count": len(all_paths),
        "returned_file_count": len(files),
        "truncated": len(all_paths) > len(files),
        "returned_bytes": total_bytes,
        "categories": dict(sorted(categories.items())),
        "tasks": {
            task_id: sorted(kinds) for task_id, kinds in sorted(tasks.items())
        },
        "files": files,
    }
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    if len(encoded) > _MAX_DISCOVERY_RETURN_BYTES:
        raise GuardedWorkspaceError(
            "evidence map exceeds return limit; request fewer files"
        )
    _audit(
        operation="map",
        source="evidence",
        relative_path="**/*",
        bytes_returned=len(encoded),
    )
    return payload


def trace_slice(
    file_path: str,
    pattern: str,
    context_lines: int = 3,
    max_matches: int = 20,
) -> dict[str, Any]:
    """Return bounded, contextual matches from one authorized trace or text file."""

    if not pattern or len(pattern) > 256:
        raise GuardedWorkspaceError("pattern must contain 1..256 characters")
    if not 0 <= context_lines <= 20:
        raise GuardedWorkspaceError("context_lines must be between 0 and 20")
    if not 1 <= max_matches <= 100:
        raise GuardedWorkspaceError("max_matches must be between 1 and 100")
    try:
        expression = re.compile(pattern, flags=re.IGNORECASE)
    except re.error as exc:
        raise GuardedWorkspaceError(f"invalid trace regex: {exc}") from exc
    path, relative = _resolve("evidence", file_path, must_exist=True)
    lines = _read_text(path).splitlines()
    matches: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        if expression.search(line) is None:
            continue
        start = max(1, line_number - context_lines)
        end = min(len(lines), line_number + context_lines)
        matches.append(
            {
                "match_line": line_number,
                "start_line": start,
                "end_line": end,
                "content": "\n".join(lines[start - 1 : end]),
            }
        )
        if len(matches) >= max_matches:
            break
    payload = {
        "path": relative,
        "total_lines": len(lines),
        "matches": matches,
        "truncated": len(matches) >= max_matches,
    }
    returned = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    if returned > _MAX_DISCOVERY_RETURN_BYTES:
        raise GuardedWorkspaceError("trace slice exceeds bounded return limit")
    _audit(
        operation="trace_slice",
        source="evidence",
        relative_path=relative,
        bytes_returned=returned,
    )
    return payload


def compare_evidence(
    left_path: str,
    right_path: str,
    max_lines: int = 400,
) -> dict[str, Any]:
    """Return a bounded unified diff between two authorized evidence files."""

    if not 1 <= max_lines <= 2_000:
        raise GuardedWorkspaceError("max_lines must be between 1 and 2000")
    left, left_relative = _resolve("evidence", left_path, must_exist=True)
    right, right_relative = _resolve("evidence", right_path, must_exist=True)
    diff_lines = list(
        difflib.unified_diff(
            _read_text(left).splitlines(),
            _read_text(right).splitlines(),
            fromfile=left_relative,
            tofile=right_relative,
            lineterm="",
        )
    )
    content = "\n".join(diff_lines[:max_lines])
    payload = {
        "left_path": left_relative,
        "right_path": right_relative,
        "diff": content,
        "diff_lines": len(diff_lines),
        "truncated": len(diff_lines) > max_lines,
    }
    returned = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    if returned > _MAX_DISCOVERY_RETURN_BYTES:
        raise GuardedWorkspaceError("evidence diff exceeds bounded return limit")
    for relative in (left_relative, right_relative):
        _audit(
            operation="compare",
            source="evidence",
            relative_path=relative,
            bytes_returned=returned // 2,
        )
    return payload


def _probe_profile(path: Path, relative: str) -> dict[str, Any]:
    """Return a deterministic, answer-free structural profile of one file."""

    text = _read_text(path)
    suffix = path.suffix.casefold()
    if suffix == ".json":
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            return {
                "path": relative,
                "kind": "json",
                "valid": False,
                "error": str(exc),
            }
        if isinstance(value, Mapping):
            keys = sorted(str(key) for key in value)
            value_types = {
                str(key): type(item).__name__ for key, item in value.items()
            }
            size = len(value)
        elif isinstance(value, list):
            keys = []
            value_types = {}
            size = len(value)
        else:
            keys = []
            value_types = {}
            size = None
        return {
            "path": relative,
            "kind": "json",
            "valid": True,
            "root_type": type(value).__name__,
            "size": size,
            "keys": keys[:200],
            "value_types": value_types,
        }
    if suffix == ".csv":
        rows = list(csv.DictReader(text.splitlines()))
        fields = list(rows[0]) if rows else list(csv.DictReader(text.splitlines()).fieldnames or ())
        missing = {
            field: sum(row.get(field, "").strip() == "" for row in rows)
            for field in fields
        }
        numeric: dict[str, dict[str, float | int]] = {}
        for field in fields:
            values: list[float] = []
            for row in rows:
                try:
                    values.append(float(row.get(field, "")))
                except (TypeError, ValueError):
                    continue
            if values:
                numeric[field] = {
                    "parsed_count": len(values),
                    "min": min(values),
                    "max": max(values),
                }
        return {
            "path": relative,
            "kind": "csv",
            "rows": len(rows),
            "columns": fields,
            "missing_by_column": missing,
            "numeric_ranges": numeric,
        }

    lines = text.splitlines()
    lowered = text.casefold()
    roles: Counter[str] = Counter()
    tool_uses = 0
    if suffix == ".jsonl":
        for line in lines:
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, Mapping):
                roles[str(value.get("role", "unknown"))] += 1
                content = str(value.get("content", ""))
                tool_uses += content.count("<ToolUse>")
    markers = {
        "error": len(re.findall(r"\b(?:error|traceback|failed)\b", lowered)),
        "inventory": len(re.findall(r"\b(?:ls|find|tree)\b", lowered)),
        "validation": len(
            re.findall(r"\b(?:pytest|validate|verification|assert)\b", lowered)
        ),
        "artifact": len(re.findall(r"\b(?:output|artifact|deliverable)\b", lowered)),
    }
    return {
        "path": relative,
        "kind": "jsonl" if suffix == ".jsonl" else "text",
        "lines": len(lines),
        "bytes": len(text.encode("utf-8")),
        "roles": dict(sorted(roles.items())),
        "tool_uses": tool_uses,
        "markers": markers,
    }


def _typed_value(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, Mapping):
        return "object"
    if isinstance(value, list):
        return "array"
    return type(value).__name__


def _json_pointer(value: object, pointer: str) -> tuple[bool, object | None]:
    if pointer == "":
        return True, value
    if not pointer.startswith("/") or len(pointer) > 1_024:
        raise GuardedWorkspaceError(
            "JSON pointer must be empty or an RFC 6901 path beginning with /"
        )
    current = value
    for raw in pointer[1:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(current, Mapping):
            if token not in current:
                return False, None
            current = current[token]
        elif isinstance(current, list):
            if not token.isdigit():
                return False, None
            index = int(token)
            if index >= len(current):
                return False, None
            current = current[index]
        else:
            return False, None
    return True, current


def _value_shape(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        keys = sorted(str(key) for key in value)
        return {"key_count": len(keys), "keys": keys[:200]}
    if isinstance(value, list):
        return {
            "length": len(value),
            "element_types": sorted({_typed_value(item) for item in value}),
        }
    if isinstance(value, str):
        return {"length": len(value)}
    return {}


def _artifact_observation(
    *,
    path: Path,
    relative: str,
    selector: Mapping[str, object],
) -> dict[str, Any]:
    kind = _text(selector.get("kind"), label="artifact selector kind")
    raw_value = selector.get("value", "")
    if not isinstance(raw_value, str):
        raise GuardedWorkspaceError("artifact selector value must be text")
    value = raw_value
    text = _read_text(path)
    suffix = path.suffix.casefold()
    if kind == "json_pointer":
        if suffix != ".json":
            raise GuardedWorkspaceError("json_pointer requires a .json artifact")
        try:
            document = json.loads(text)
        except json.JSONDecodeError as exc:
            return {
                "path": relative,
                "selector": {"kind": kind, "value": value},
                "document_valid": False,
                "exists": False,
                "value_type": "invalid_json",
                "shape": {},
                "parse_error": str(exc),
            }
        exists, selected = _json_pointer(document, value)
        return {
            "path": relative,
            "selector": {"kind": kind, "value": value},
            "document_valid": True,
            "exists": exists,
            "value_type": _typed_value(selected) if exists else "missing",
            "shape": _value_shape(selected) if exists else {},
        }
    if kind == "csv_column":
        if suffix != ".csv":
            raise GuardedWorkspaceError("csv_column requires a .csv artifact")
        reader = csv.DictReader(text.splitlines())
        fields = list(reader.fieldnames or ())
        rows = list(reader)
        exists = value in fields
        values = [str(row.get(value, "")) for row in rows] if exists else []
        parsed_types: set[str] = set()
        for item in values:
            if not item.strip():
                continue
            try:
                int(item)
            except ValueError:
                try:
                    float(item)
                except ValueError:
                    parsed_types.add("string")
                else:
                    parsed_types.add("number")
            else:
                parsed_types.add("integer")
        return {
            "path": relative,
            "selector": {"kind": kind, "value": value},
            "document_valid": True,
            "exists": exists,
            "value_type": "csv_column" if exists else "missing",
            "shape": (
                {
                    "row_count": len(rows),
                    "missing_count": sum(not item.strip() for item in values),
                    "nonempty_count": sum(bool(item.strip()) for item in values),
                    "value_types": sorted(parsed_types),
                }
                if exists
                else {}
            ),
        }
    if kind == "csv_table":
        if suffix != ".csv" or value not in {"", "$table"}:
            raise GuardedWorkspaceError(
                "csv_table requires a .csv artifact and selector value $table"
            )
        reader = csv.DictReader(text.splitlines())
        fields = list(reader.fieldnames or ())
        rows = list(reader)
        return {
            "path": relative,
            "selector": {"kind": kind, "value": "$table"},
            "document_valid": True,
            "exists": True,
            "value_type": "csv_table",
            "shape": {
                "row_count": len(rows),
                "column_count": len(fields),
                "columns": fields,
            },
        }
    if kind == "file_shape":
        if value not in {"", "$file"}:
            raise GuardedWorkspaceError("file_shape selector value must be $file")
        return {
            "path": relative,
            "selector": {"kind": kind, "value": "$file"},
            "document_valid": True,
            "exists": True,
            "value_type": "file",
            "shape": {
                "bytes": len(text.encode("utf-8")),
                "lines": len(text.splitlines()),
                "suffix": suffix,
                "utf8": True,
            },
        }
    raise GuardedWorkspaceError(
        "artifact selector kind must be json_pointer, csv_column, csv_table, "
        "or file_shape"
    )


def _trace_phase_observation(
    *, path: Path, relative: str, phase: str
) -> dict[str, Any]:
    pattern = _TRACE_PHASE_PATTERNS.get(phase)
    if pattern is None:
        raise GuardedWorkspaceError(
            "trace_phase must be one of: " + ", ".join(sorted(_TRACE_PHASE_PATTERNS))
        )
    events: list[dict[str, Any]] = []
    matched_count = 0
    for line_number, line in enumerate(_read_text(path).splitlines(), start=1):
        role = "unknown"
        content = line
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, Mapping):
            role = str(payload.get("role", "unknown")).casefold()
            content = str(payload.get("content", ""))
        if role in {"user", "system"} or pattern.search(content) is None:
            continue
        matched_count += 1
        if len(events) < 20:
            encoded = content.encode("utf-8")[:1_000]
            events.append(
                {
                    "line": line_number,
                    "role": role,
                    "content": encoded.decode("utf-8", errors="ignore"),
                    "content_sha256": hashlib.sha256(
                        content.encode("utf-8")
                    ).hexdigest(),
                }
            )
    return {
        "path": relative,
        "phase": phase,
        "phase_present": matched_count > 0,
        "event_count": matched_count,
        "events": events,
        "truncated": matched_count > len(events),
    }


def _shape_subset(expected: object, observed: object) -> bool:
    if isinstance(expected, Mapping):
        return isinstance(observed, Mapping) and all(
            key in observed and _shape_subset(value, observed[key])
            for key, value in expected.items()
        )
    if isinstance(expected, list):
        return isinstance(observed, list) and expected == observed
    return expected == observed


def _normalize_semantic_expectations(
    raw: Mapping[str, object],
) -> dict[str, dict[str, object]]:
    if len(raw) < 2:
        raise GuardedWorkspaceError(
            "a typed semantic probe requires at least two hypothesis expectations"
        )
    allowed = {
        "artifact_exists",
        "artifact_value_type",
        "artifact_shape",
        "trace_phase_present",
    }
    normalized: dict[str, dict[str, object]] = {}
    for raw_id, raw_expectation in raw.items():
        hypothesis_id = _text(raw_id, label="hypothesis ID")
        if not isinstance(raw_expectation, Mapping) or not raw_expectation:
            raise GuardedWorkspaceError(
                f"typed expectation for {hypothesis_id!r} must be a non-empty object"
            )
        unknown = set(raw_expectation) - allowed
        if unknown:
            raise GuardedWorkspaceError(
                f"typed expectation for {hypothesis_id!r} has unknown fields: "
                + ", ".join(sorted(str(value) for value in unknown))
            )
        expectation = dict(raw_expectation)
        for field in ("artifact_exists", "trace_phase_present"):
            if field in expectation and not isinstance(expectation[field], bool):
                raise GuardedWorkspaceError(
                    f"typed expectation {field} for {hypothesis_id!r} must be boolean"
                )
        if "artifact_value_type" in expectation and not isinstance(
            expectation["artifact_value_type"], str
        ):
            raise GuardedWorkspaceError(
                "typed expectation artifact_value_type for "
                f"{hypothesis_id!r} must be text"
            )
        if "artifact_shape" in expectation and not isinstance(
            expectation["artifact_shape"], Mapping
        ):
            raise GuardedWorkspaceError(
                "typed expectation artifact_shape for "
                f"{hypothesis_id!r} must be an object"
            )
        normalized[hypothesis_id] = expectation
    signatures = {
        json.dumps(value, sort_keys=True, separators=(",", ":"))
        for value in normalized.values()
    }
    if len(signatures) < 2:
        raise GuardedWorkspaceError(
            "typed semantic probe expectations must predict different observations"
        )
    return normalized


def _expectation_match(
    expectation: Mapping[str, object],
    artifact: Mapping[str, object],
    trace: Mapping[str, object],
) -> tuple[bool, dict[str, bool]]:
    checks: dict[str, bool] = {}
    if "artifact_exists" in expectation:
        checks["artifact_exists"] = artifact.get("exists") is expectation[
            "artifact_exists"
        ]
    if "artifact_value_type" in expectation:
        checks["artifact_value_type"] = (
            artifact.get("value_type") == expectation["artifact_value_type"]
        )
    if "artifact_shape" in expectation:
        checks["artifact_shape"] = _shape_subset(
            expectation["artifact_shape"], artifact.get("shape")
        )
    if "trace_phase_present" in expectation:
        checks["trace_phase_present"] = (
            trace.get("phase_present") is expectation["trace_phase_present"]
        )
    return all(checks.values()), checks


def probe_contract_semantics(
    probe_id: str,
    question: str,
    hypothesis_expectations: Mapping[str, Mapping[str, object]],
    task_id: str,
    clause_id: str,
    artifact_path: str,
    artifact_selector: Mapping[str, object],
    trace_phase: str,
    semantic_relation: str,
    comparison_claim: str,
) -> dict[str, Any]:
    """Link an exact public clause, artifact observation, and trace phase.

    The artifact and trace must come from the same train task as the cited
    public contract.  Expectations are machine-checkable typed predicates, so
    an ACT gate can require that the selected hypothesis matched while a named
    competitor did not.  The comparison claim remains an Evolver inference;
    this tool grounds it but does not certify causal truth.
    """

    if not isinstance(probe_id, str) or _PROBE_ID.fullmatch(probe_id) is None:
        raise GuardedWorkspaceError("probe_id must be safe lower-case text")
    if probe_id in _probe_records():
        raise GuardedWorkspaceError(f"probe_id already exists: {probe_id}")
    question = _text(question, label="probe question")
    comparison_claim = _text(comparison_claim, label="comparison_claim")
    semantic_relation = _text(
        semantic_relation, label="semantic_relation"
    ).casefold()
    if semantic_relation not in {"supports", "contradicts", "insufficient"}:
        raise GuardedWorkspaceError(
            "semantic_relation must be supports, contradicts, or insufficient"
        )
    task_id = _text(task_id, label="task_id")
    clause_id = _text(clause_id, label="clause_id")
    contract = _contract()
    if contract.get("public_contract_evidence") is not True:
        raise GuardedWorkspaceError(
            "typed semantic probes require indexed public-contract evidence"
        )
    if contract.get("public_contract_index") != "contracts/index.json":
        raise GuardedWorkspaceError("public-contract index identity is invalid")
    _feedback_contract(contract)
    allowed_tasks = set(
        _text_list(contract.get("train_task_ids", []), label="train_task_ids")
    )
    if task_id not in allowed_tasks:
        raise GuardedWorkspaceError("semantic probe task is outside the train panel")

    evidence_root = _root("evidence")
    try:
        clause, clause_paths = load_public_contract_clause(
            evidence_root=evidence_root,
            task_id=task_id,
            clause_id=clause_id,
        )
    except PublicContractEvidenceError as exc:
        raise GuardedWorkspaceError(str(exc)) from exc
    artifact, artifact_relative = _resolve(
        "evidence", artifact_path, must_exist=True
    )
    artifact_prefix = f"tasks/{task_id}/artifacts/"
    if not artifact_relative.startswith(artifact_prefix):
        raise GuardedWorkspaceError(
            "semantic probe artifact must belong to the cited task"
        )
    manifest_path, manifest_relative = _resolve(
        "evidence", f"tasks/{task_id}/artifact_manifest.json", must_exist=True
    )
    try:
        manifest = json.loads(_read_text(manifest_path))
    except json.JSONDecodeError as exc:
        raise GuardedWorkspaceError("artifact manifest is invalid JSON") from exc
    records = manifest.get("artifacts") if isinstance(manifest, Mapping) else None
    authorized_artifacts = {
        str(value.get("evidence_path"))
        for value in records
        if isinstance(records, list)
        and isinstance(value, Mapping)
        and isinstance(value.get("evidence_path"), str)
    } if isinstance(records, list) else set()
    if artifact_relative not in authorized_artifacts:
        raise GuardedWorkspaceError(
            "semantic probe artifact is not named by its public artifact manifest"
        )
    trace, trace_relative = _resolve(
        "evidence", f"tasks/{task_id}/worker_trace.jsonl", must_exist=True
    )
    expectations = _normalize_semantic_expectations(hypothesis_expectations)
    artifact_observation = _artifact_observation(
        path=artifact,
        relative=artifact_relative,
        selector=artifact_selector,
    )
    trace_observation = _trace_phase_observation(
        path=trace, relative=trace_relative, phase=trace_phase
    )
    matches: dict[str, bool] = {}
    match_details: dict[str, dict[str, bool]] = {}
    for hypothesis_id, expectation in expectations.items():
        matched, details = _expectation_match(
            expectation, artifact_observation, trace_observation
        )
        matches[hypothesis_id] = matched
        match_details[hypothesis_id] = details
    evidence_paths = [
        clause_paths[0],
        clause_paths[1],
        artifact_relative,
        manifest_relative,
        trace_relative,
    ]
    record: dict[str, Any] = {
        "schema_version": 2,
        "probe_kind": _SEMANTIC_PROBE_KIND,
        "probe_id": probe_id,
        "question": question,
        "task_id": task_id,
        "clause": clause,
        "artifact": artifact_observation,
        "trace": trace_observation,
        "semantic_relation": semantic_relation,
        "comparison_claim": comparison_claim,
        "hypothesis_expectations": expectations,
        "expectation_matches": matches,
        "expectation_match_details": match_details,
        "evidence_paths": evidence_paths,
        "causal_truth_certified": False,
    }
    encoded = json.dumps(
        record, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    if len(encoded) > _MAX_DISCOVERY_RETURN_BYTES:
        raise GuardedWorkspaceError("typed semantic probe result exceeds return limit")
    record["result_sha256"] = hashlib.sha256(encoded).hexdigest()
    with _result_path(_PROBE_LOG_NAME).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
    for relative in evidence_paths:
        _audit(
            operation="semantic_probe",
            source="evidence",
            relative_path=relative,
            bytes_returned=len(encoded) // len(evidence_paths),
        )
    return record


def probe_evidence(
    probe_id: str,
    question: str,
    hypothesis_expectations: Mapping[str, str],
    evidence_paths: list[str],
    operation: str = "compare_profiles",
) -> dict[str, Any]:
    """Execute one bounded structural probe over authorized public evidence.

    The probe is deliberately constrained: it profiles exact JSON, CSV, trace,
    or text evidence and cannot execute arbitrary model-written code, reach the
    network, inspect evaluator material, or mutate the candidate.
    """

    if not isinstance(probe_id, str) or _PROBE_ID.fullmatch(probe_id) is None:
        raise GuardedWorkspaceError("probe_id must be safe lower-case text")
    question = _text(question, label="probe question")
    if operation not in {"profile", "compare_profiles"}:
        raise GuardedWorkspaceError("unsupported constrained probe operation")
    if not isinstance(hypothesis_expectations, Mapping):
        raise GuardedWorkspaceError("hypothesis_expectations must be an object")
    expectations = {
        _text(key, label="hypothesis ID"): _text(
            value, label=f"expectation for {key!r}"
        )
        for key, value in hypothesis_expectations.items()
    }
    if len(expectations) < 2:
        raise GuardedWorkspaceError(
            "a discriminating probe requires expectations for at least two hypotheses"
        )
    paths = _text_list(
        evidence_paths, label="probe evidence_paths", minimum=1
    )
    if len(paths) > 12:
        raise GuardedWorkspaceError("one probe may inspect at most 12 evidence files")
    if operation == "compare_profiles" and len(paths) < 2:
        raise GuardedWorkspaceError("compare_profiles requires at least two files")
    existing = _probe_records()
    if probe_id in existing:
        raise GuardedWorkspaceError(f"probe_id already exists: {probe_id}")

    profiles: list[dict[str, Any]] = []
    normalized_paths: list[str] = []
    for raw in paths:
        path, relative = _resolve("evidence", raw, must_exist=True)
        profiles.append(_probe_profile(path, relative))
        normalized_paths.append(relative)
    observation = {
        "operation": operation,
        "profiles": profiles,
    }
    encoded_observation = json.dumps(
        observation, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    if len(encoded_observation) > _MAX_DISCOVERY_RETURN_BYTES:
        raise GuardedWorkspaceError("probe result exceeds bounded return limit")
    result_sha256 = hashlib.sha256(encoded_observation).hexdigest()
    record = {
        "schema_version": 1,
        "probe_id": probe_id,
        "question": question,
        "hypothesis_expectations": expectations,
        "evidence_paths": normalized_paths,
        "operation": operation,
        "result_sha256": result_sha256,
        # Persist the bounded structural observation, not only its digest.  A
        # terminal-reserve transition must be able to make an honest calibrated
        # decision without re-reading evidence or relying on model memory.
        "observation": observation,
    }
    with _result_path(_PROBE_LOG_NAME).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
    for relative in normalized_paths:
        _audit(
            operation="probe",
            source="evidence",
            relative_path=relative,
            bytes_returned=len(encoded_observation) // len(normalized_paths),
        )
    return dict(record)


def _component_role(relative: str) -> str:
    path = PurePosixPath(relative)
    if relative == "systemprompt.md":
        return "systemprompt"
    if relative == "agent.yaml":
        return "agent_config"
    if not path.parts:
        return "other"
    head = path.parts[0]
    return head if head in _COMPONENT_ROLES else "other"


def _local_binding_path(module: str) -> tuple[PurePosixPath, PurePosixPath]:
    base = PurePosixPath(*module.split("."))
    return base.with_suffix(".py"), base / "__init__.py"


def inspect_candidate() -> dict[str, Any]:
    """Inspect candidate components, declarations, bindings, and syntax."""

    root = _root("candidate")
    paths = sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink()
    )
    roles: dict[str, list[str]] = defaultdict(list)
    for relative in paths:
        roles[_component_role(relative)].append(relative)
    issues: list[str] = []
    for relative in paths:
        if relative.endswith(".py"):
            path, _ = _resolve("candidate", relative, must_exist=True)
            try:
                ast.parse(_read_text(path), filename=relative)
            except SyntaxError as exc:
                issues.append(f"python syntax: {relative}:{exc.lineno}: {exc.msg}")

    agent_path = root / "agent.yaml"
    agent: Mapping[str, Any] = {}
    if not agent_path.is_file():
        issues.append("agent.yaml is missing")
    else:
        try:
            import yaml

            parsed = yaml.safe_load(_read_text(agent_path))
        except Exception as exc:  # noqa: BLE001 - diagnostic boundary.
            issues.append(f"agent.yaml parse: {type(exc).__name__}: {exc}")
        else:
            if not isinstance(parsed, Mapping):
                issues.append("agent.yaml must decode to an object")
            else:
                agent = parsed

    declarations: list[dict[str, Any]] = []
    tools = agent.get("tools", []) if isinstance(agent, Mapping) else []
    if isinstance(tools, list):
        for entry in tools:
            if not isinstance(entry, Mapping):
                issues.append("agent tool declaration is not an object")
                continue
            name = str(entry.get("name", ""))
            yaml_path = str(entry.get("yaml_path", ""))
            binding = str(entry.get("binding", ""))
            declaration = {"kind": "tool", "name": name, "yaml_path": yaml_path, "binding": binding}
            declarations.append(declaration)
            if yaml_path.startswith("./"):
                relative_yaml = yaml_path[2:]
                if relative_yaml not in paths:
                    issues.append(f"tool {name!r} description is missing: {relative_yaml}")
            if binding.startswith("tools.") and ":" in binding:
                module, function = binding.split(":", 1)
                candidates = _local_binding_path(module)
                existing = [candidate.as_posix() for candidate in candidates if candidate.as_posix() in paths]
                if not existing:
                    issues.append(f"tool {name!r} local binding module is missing: {module}")
                else:
                    module_path = root / existing[0]
                    try:
                        tree = ast.parse(_read_text(module_path), filename=existing[0])
                    except SyntaxError:
                        pass
                    else:
                        functions = {
                            node.name
                            for node in tree.body
                            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                        }
                        if function not in functions:
                            issues.append(
                                f"tool {name!r} binding function is missing: {binding}"
                            )

    skills = agent.get("skills", []) if isinstance(agent, Mapping) else []
    if skills is not None and not isinstance(skills, list):
        issues.append("agent skills declaration must be a list")
    elif isinstance(skills, list):
        for raw in skills:
            relative = str(raw)[2:] if str(raw).startswith("./") else str(raw)
            skill_path = f"{relative.rstrip('/')}/SKILL.md"
            declarations.append({"kind": "skill", "path": relative})
            if skill_path not in paths:
                issues.append(f"registered skill is missing SKILL.md: {relative}")

    middlewares = agent.get("middlewares", []) if isinstance(agent, Mapping) else []
    if middlewares is not None and not isinstance(middlewares, list):
        issues.append("agent middlewares declaration must be a list")
    elif isinstance(middlewares, list):
        for raw in middlewares:
            imported = raw.get("import") if isinstance(raw, Mapping) else None
            declarations.append({"kind": "middleware", "import": imported})
            if isinstance(imported, str) and imported.startswith("middleware."):
                module = imported.split(":", 1)[0]
                candidates = _local_binding_path(module)
                if not any(candidate.as_posix() in paths for candidate in candidates):
                    issues.append(f"local middleware module is missing: {module}")

    payload = {
        "schema_version": 1,
        "files": paths,
        "components": {role: members for role, members in sorted(roles.items())},
        "absent_components": sorted(_COMPONENT_ROLES - set(roles)),
        "declarations": declarations,
        "issues": issues,
        "valid": not issues,
    }
    returned = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    _audit(
        operation="inspect",
        source="candidate",
        relative_path="**/*",
        bytes_returned=returned,
    )
    return payload


def unlock_candidate(hypothesis: Mapping[str, Any]) -> dict[str, Any]:
    """Unlock writes only after a falsifiable, evidence-backed discovery plan."""

    contract_path = _root("evidence") / "contract.json"
    if (
        contract_path.is_file()
        and _contract().get("decision_protocol") == "quant_property_v2"
    ):
        raise GuardedWorkspaceError(
            "quant_property_v2 requires decide_candidate; legacy unlock is forbidden"
        )
    if not isinstance(hypothesis, Mapping):
        raise GuardedWorkspaceError("hypothesis must be an object")
    required_text = (
        "selected_mechanism",
        "counterevidence",
        "uncertainty",
        "discriminating_probe",
    )
    for field in required_text:
        value = hypothesis.get(field)
        if not isinstance(value, str) or not value.strip():
            raise GuardedWorkspaceError(f"hypothesis {field} must be non-empty text")
    alternatives = hypothesis.get("hypotheses_considered")
    if (
        not isinstance(alternatives, list)
        or len(alternatives) < 2
        or any(not isinstance(value, str) or not value.strip() for value in alternatives)
    ):
        raise GuardedWorkspaceError(
            "hypotheses_considered must contain at least two non-empty alternatives"
        )
    refs = hypothesis.get("evidence_refs")
    if (
        not isinstance(refs, list)
        or len(refs) < 2
        or any(not isinstance(value, str) or not value for value in refs)
    ):
        raise GuardedWorkspaceError("evidence_refs must contain at least two paths")
    normalized_refs: list[str] = []
    for raw in refs:
        _, relative = _resolve("evidence", raw, must_exist=True)
        normalized_refs.append(relative)
    accessed = _accessed_evidence_paths()
    missing_access = sorted(set(normalized_refs) - accessed)
    if missing_access:
        raise GuardedWorkspaceError(
            "evidence_refs must be read or inspected before unlock: "
            + ", ".join(missing_access)
        )
    component = hypothesis.get("component")
    if component not in _COMPONENT_ROLES:
        raise GuardedWorkspaceError(
            "hypothesis component must name one declared harness component role"
        )
    risk_tasks = hypothesis.get("risk_tasks")
    if not isinstance(risk_tasks, list) or any(
        not isinstance(value, str) or not value for value in risk_tasks
    ):
        raise GuardedWorkspaceError("risk_tasks must be a list of task IDs or risks")
    prediction = hypothesis.get("prediction")
    if not isinstance(prediction, (str, list, Mapping)) or not prediction:
        raise GuardedWorkspaceError("prediction must be a non-empty falsifiable value")

    normalized = dict(hypothesis)
    normalized["evidence_refs"] = sorted(set(normalized_refs))
    encoded = json.dumps(
        normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    if len(encoded) > 128_000:
        raise GuardedWorkspaceError("discovery hypothesis exceeds size limit")
    digest = hashlib.sha256(encoded).hexdigest()
    state = {
        "schema_version": 1,
        "unlocked": True,
        "hypothesis_sha256": digest,
        "hypothesis": normalized,
    }
    path = _result_path(_DISCOVERY_STATE_NAME)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(state, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)
    _audit(
        operation="unlock",
        source="discovery",
        relative_path=digest,
        bytes_returned=0,
    )
    return {
        "unlocked": True,
        "hypothesis_sha256": digest,
        "evidence_refs": normalized["evidence_refs"],
        "component": component,
    }


def _decision_probe_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Keep semantic observations auditable without embedding trace excerpts."""

    if record.get("probe_kind") != _SEMANTIC_PROBE_KIND:
        compact = dict(record)
        observation = compact.pop("observation", None)
        if observation is not None:
            compact["observation_sha256"] = hashlib.sha256(
                json.dumps(
                    observation,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ).encode("utf-8")
            ).hexdigest()
        return compact
    clause = record.get("clause")
    clause = dict(clause) if isinstance(clause, Mapping) else {}
    artifact = record.get("artifact")
    artifact = dict(artifact) if isinstance(artifact, Mapping) else {}
    trace = record.get("trace")
    trace = dict(trace) if isinstance(trace, Mapping) else {}
    return {
        "schema_version": record.get("schema_version"),
        "probe_kind": record.get("probe_kind"),
        "probe_id": record.get("probe_id"),
        "question": record.get("question"),
        "task_id": record.get("task_id"),
        "clause": {
            key: clause.get(key)
            for key in (
                "clause_id",
                "kind",
                "heading_path",
                "start_line",
                "end_line",
                "text_sha256",
            )
        },
        "artifact": {
            key: artifact.get(key)
            for key in (
                "path",
                "selector",
                "document_valid",
                "exists",
                "value_type",
                "shape",
            )
        },
        "trace": {
            key: trace.get(key)
            for key in (
                "path",
                "phase",
                "phase_present",
                "event_count",
                "truncated",
            )
        },
        "comparison_claim": record.get("comparison_claim"),
        "semantic_relation": record.get("semantic_relation"),
        "hypothesis_expectations": record.get("hypothesis_expectations"),
        "expectation_matches": record.get("expectation_matches"),
        "expectation_match_details": record.get("expectation_match_details"),
        "evidence_paths": record.get("evidence_paths"),
        "result_sha256": record.get("result_sha256"),
        "causal_truth_certified": False,
    }


def _decide_quant_property_candidate(
    discovery: Mapping[str, Any], contract: Mapping[str, Any]
) -> dict[str, Any]:
    """Record a QuantCodeEval v2 decision without requiring cross-task failures."""

    if contract.get("feedback_tier") != "answer_free_property_family_v2":
        raise GuardedWorkspaceError("unsupported QuantCodeEval feedback tier")
    decision = _text(discovery.get("decision"), label="decision").upper()
    if decision not in {"ACT", "ABSTAIN"}:
        raise GuardedWorkspaceError("decision must be ACT or ABSTAIN")
    classification_required = (
        contract.get("quant_failure_classification_required_for_act") is True
    )
    raw_failure_class = discovery.get("failure_class")
    failure_class = (
        _text(raw_failure_class, label="failure_class").casefold()
        if raw_failure_class is not None
        else "unclassified"
    )
    if classification_required and failure_class not in _QUANT_FAILURE_CLASSES:
        raise GuardedWorkspaceError("failure_class is unsupported")

    raw_hypotheses = discovery.get("hypotheses_considered")
    if not isinstance(raw_hypotheses, list) or len(raw_hypotheses) < 2:
        raise GuardedWorkspaceError(
            "hypotheses_considered must contain at least two mechanism hypotheses"
        )
    hypothesis_ids: set[str] = set()
    normalized_hypotheses: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_hypotheses):
        if not isinstance(raw, Mapping):
            raise GuardedWorkspaceError(
                f"hypotheses_considered[{index}] must be an object"
            )
        hypothesis_id = _text(
            raw.get("hypothesis_id"),
            label=f"hypotheses_considered[{index}].hypothesis_id",
        )
        if hypothesis_id in hypothesis_ids:
            raise GuardedWorkspaceError(f"duplicate hypothesis ID: {hypothesis_id}")
        hypothesis_ids.add(hypothesis_id)
        normalized_hypotheses.append(
            {
                **dict(raw),
                "hypothesis_id": hypothesis_id,
                "mechanism": _text(
                    raw.get("mechanism"),
                    label=f"hypotheses_considered[{index}].mechanism",
                ),
                "prediction": _text(
                    raw.get("prediction"),
                    label=f"hypotheses_considered[{index}].prediction",
                ),
            }
        )

    evidence_refs = _text_list(
        discovery.get("evidence_refs"), label="evidence_refs", minimum=2
    )
    normalized_refs: list[str] = []
    for value in evidence_refs:
        _, relative = _resolve("evidence", value, must_exist=True)
        normalized_refs.append(relative)
    accessed = _accessed_evidence_paths()
    missing_access = sorted(set(normalized_refs) - accessed)
    if missing_access:
        raise GuardedWorkspaceError(
            "discovery evidence_refs must be read before decision: "
            + ", ".join(missing_access)
        )
    if contract.get("history_required") is True:
        history_refs = [
            value
            for value in normalized_refs
            if value.startswith("history/archive/")
            and (
                "/entries/" in value
                or "/diffs/" in value
                or "/objects/" in value
            )
        ]
        if not history_refs:
            raise GuardedWorkspaceError(
                "this round must inspect an exact prior entry, diff, or candidate source"
            )

    selected = discovery.get("selected_hypothesis_id")
    selected_id = (
        _text(selected, label="selected_hypothesis_id")
        if selected is not None
        else None
    )
    if selected_id is not None and selected_id not in hypothesis_ids:
        raise GuardedWorkspaceError("selected_hypothesis_id is unknown")
    normalized: dict[str, Any] = {
        **dict(discovery),
        "decision": decision,
        "failure_class": failure_class,
        "hypotheses_considered": normalized_hypotheses,
        "selected_hypothesis_id": selected_id,
        "evidence_refs": sorted(set(normalized_refs)),
        "counterevidence": _text(
            discovery.get("counterevidence"), label="counterevidence"
        ),
        "uncertainty": _text(discovery.get("uncertainty"), label="uncertainty"),
    }
    normalized["search_operator"] = _text(
        discovery.get("search_operator", "NEW_PROBE"), label="search_operator"
    ).upper()
    if normalized["search_operator"] not in {
        "CONTINUE",
        "REUSE",
        "REVERT",
        "FUSE",
        "COMPOSE",
        "SYNTHESIZE",
        "ROUTE",
        "NEW_PROBE",
    }:
        raise GuardedWorkspaceError("search_operator is unsupported")
    normalized["domain_tags"] = _text_list(
        discovery.get("domain_tags", []), label="domain_tags"
    )

    components: list[str] = []
    primary_components: list[str] = []
    if decision == "ACT":
        if classification_required and failure_class in {
            "unknown",
            "isolated_task_specific",
        }:
            raise GuardedWorkspaceError(
                "unknown or isolated_task_specific evidence must ABSTAIN"
            )
        if selected_id is None:
            raise GuardedWorkspaceError("ACT requires selected_hypothesis_id")
        if classification_required:
            breakdown_stage = _text(
                discovery.get("breakdown_stage"), label="breakdown_stage"
            ).casefold()
            if breakdown_stage not in _QUANT_BREAKDOWN_STAGES:
                raise GuardedWorkspaceError("breakdown_stage is unsupported")
            if breakdown_stage == "unable_to_decide":
                raise GuardedWorkspaceError(
                    "unable_to_decide breakdown evidence must ABSTAIN"
                )
            normalized["breakdown_stage"] = breakdown_stage
            normalized["observed_symptoms"] = _text_list(
                discovery.get("observed_symptoms"),
                label="observed_symptoms",
                minimum=1,
            )
            adjacent = _text_list(
                discovery.get("adjacent_failure_classes_considered"),
                label="adjacent_failure_classes_considered",
                minimum=1,
            )
            if any(value not in _QUANT_FAILURE_CLASSES for value in adjacent):
                raise GuardedWorkspaceError(
                    "adjacent_failure_classes_considered contains an unknown class"
                )
            if failure_class in adjacent:
                raise GuardedWorkspaceError(
                    "adjacent failure classes must differ from failure_class"
                )
            normalized["adjacent_failure_classes_considered"] = adjacent
            normalized["class_selection_reason"] = _text(
                discovery.get("class_selection_reason"),
                label="class_selection_reason",
            )
            normalized["component_state_target"] = _text(
                discovery.get("component_state_target"),
                label="component_state_target",
            )
        else:
            for field in (
                "breakdown_stage",
                "observed_symptoms",
                "adjacent_failure_classes_considered",
                "class_selection_reason",
                "component_state_target",
            ):
                if field in discovery:
                    normalized[field] = discovery[field]
        components = _text_list(
            discovery.get("components"), label="components", minimum=1
        )
        primary_components = _text_list(
            discovery.get("primary_components"),
            label="primary_components",
            minimum=1,
        )
        if any(component not in _COMPONENT_ROLES for component in components):
            raise GuardedWorkspaceError("components contains an unknown role")
        if any(component not in _COMPONENT_ROLES for component in primary_components):
            raise GuardedWorkspaceError("primary_components contains an unknown role")
        if not set(primary_components) <= set(components):
            raise GuardedWorkspaceError(
                "primary_components must be a subset of all declared components"
            )
        max_primary = contract.get("max_primary_components", 2)
        max_declared = contract.get("max_declared_components", 6)
        if (
            isinstance(max_primary, bool)
            or not isinstance(max_primary, int)
            or max_primary < 1
        ):
            raise GuardedWorkspaceError("contract max_primary_components is invalid")
        if (
            isinstance(max_declared, bool)
            or not isinstance(max_declared, int)
            or max_declared < max_primary
        ):
            raise GuardedWorkspaceError("contract max_declared_components is invalid")
        if len(primary_components) > max_primary:
            raise GuardedWorkspaceError(
                f"ACT may name at most {max_primary} primary component roles"
            )
        if len(components) > max_declared:
            raise GuardedWorkspaceError(
                f"ACT may change at most {max_declared} component roles"
            )
        preferred_map = contract.get("preferred_primary_components", {})
        preferred = []
        if isinstance(preferred_map, Mapping):
            raw_preferred = preferred_map.get(failure_class, [])
            if isinstance(raw_preferred, list):
                preferred = [str(value) for value in raw_preferred]
        if preferred and not set(primary_components) & set(preferred):
            normalized["component_override_reason"] = _text(
                discovery.get("component_override_reason"),
                label="component_override_reason",
            )
        prediction = discovery.get("prediction")
        if not isinstance(prediction, (str, list, Mapping)) or not prediction:
            raise GuardedWorkspaceError("ACT requires a falsifiable prediction")
        normalized["prediction"] = prediction
        normalized["risk_tasks"] = _text_list(
            discovery.get("risk_tasks", []), label="risk_tasks"
        )
    else:
        if selected_id is not None:
            raise GuardedWorkspaceError("ABSTAIN must not select a hypothesis")
        if discovery.get("components") not in (None, []):
            raise GuardedWorkspaceError("ABSTAIN must not declare components")
        if discovery.get("primary_components") not in (None, []):
            raise GuardedWorkspaceError(
                "ABSTAIN must not declare primary_components"
            )
        normalized["abstain_reason"] = _text(
            discovery.get("abstain_reason"), label="abstain_reason"
        )
    normalized["components"] = components
    normalized["primary_components"] = primary_components
    if len(components) == 1:
        normalized["component"] = components[0]

    encoded = json.dumps(
        normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    if len(encoded) > 256_000:
        raise GuardedWorkspaceError("discovery decision exceeds size limit")
    digest = hashlib.sha256(encoded).hexdigest()
    state = {
        "schema_version": 4,
        "protocol": "quant_property_v2",
        "decision": decision,
        "unlocked": decision == "ACT",
        "hypothesis_sha256": digest,
        "hypothesis": normalized,
        "contract_requirements": {
            "feedback_tier": contract.get("feedback_tier"),
            "history_required": contract.get("history_required"),
            "max_primary_components": contract.get("max_primary_components"),
            "max_declared_components": contract.get("max_declared_components"),
            "preferred_primary_components": contract.get(
                "preferred_primary_components"
            ),
        },
    }
    path = _result_path(_DISCOVERY_STATE_NAME)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(state, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)
    _audit(
        operation="decision",
        source="discovery",
        relative_path=f"{decision.casefold()}:{digest}",
        bytes_returned=0,
    )
    return {
        "decision": decision,
        "unlocked": decision == "ACT",
        "hypothesis_sha256": digest,
        "failure_class": failure_class,
        "primary_components": primary_components,
        "components": components,
    }


def decide_candidate(discovery: Mapping[str, Any]) -> dict[str, Any]:
    """Record an A5 ACT/ABSTAIN decision after type induction and probes.

    ACT unlocks a coherent edit spanning at most the contract's component
    limit. ABSTAIN records a completed discovery result while writes remain
    locked. This makes insufficient evidence a first-class outcome rather than
    forcing the Evolver to manufacture a candidate.
    """

    if not isinstance(discovery, Mapping):
        raise GuardedWorkspaceError("discovery must be an object")
    contract = _contract()
    protocol = contract.get("decision_protocol")
    if protocol == "quant_property_v2":
        return _decide_quant_property_candidate(discovery, contract)
    if protocol not in {"failure_type_v1", "semantic_contract_v1"}:
        raise GuardedWorkspaceError(
            "decide_candidate requires failure_type_v1 or semantic_contract_v1 "
            "in the evidence contract"
        )
    feedback_tier = _feedback_contract(contract)
    decision = _text(discovery.get("decision"), label="decision").upper()
    if decision not in {"ACT", "ABSTAIN"}:
        raise GuardedWorkspaceError("decision must be ACT or ABSTAIN")

    target_tasks = set(
        _text_list(
            contract.get("target_task_ids", []),
            label="contract target_task_ids",
        )
    )
    contrast_tasks = set(
        _text_list(
            contract.get("protection_task_ids", []),
            label="contract protection_task_ids",
        )
    )
    raw_types = discovery.get("failure_types")
    if not isinstance(raw_types, list) or not raw_types:
        raise GuardedWorkspaceError("failure_types must contain at least one type")
    type_ids: set[str] = set()
    type_members: dict[str, set[str]] = {}
    normalized_types: list[dict[str, Any]] = []
    all_type_refs: set[str] = set()
    for index, raw in enumerate(raw_types):
        if not isinstance(raw, Mapping):
            raise GuardedWorkspaceError(f"failure_types[{index}] must be an object")
        type_id = _text(raw.get("type_id"), label=f"failure_types[{index}].type_id")
        if type_id in type_ids:
            raise GuardedWorkspaceError(f"duplicate failure type ID: {type_id}")
        type_ids.add(type_id)
        label = _text(raw.get("label"), label=f"failure_types[{index}].label")
        members = _text_list(
            raw.get("member_tasks"),
            label=f"failure_types[{index}].member_tasks",
            minimum=2,
        )
        if not set(members) <= target_tasks:
            raise GuardedWorkspaceError(
                f"failure type {type_id!r} contains a non-target task"
            )
        type_members[type_id] = set(members)
        excluded = _text_list(
            raw.get("excluded_tasks", []),
            label=f"failure_types[{index}].excluded_tasks",
        )
        if not set(excluded) <= target_tasks or set(excluded) & set(members):
            raise GuardedWorkspaceError(
                f"failure type {type_id!r} has invalid excluded_tasks"
            )
        matched = _text_list(
            raw.get("matched_success_tasks", []),
            label=f"failure_types[{index}].matched_success_tasks",
        )
        if not set(matched) <= contrast_tasks:
            raise GuardedWorkspaceError(
                f"failure type {type_id!r} has a non-contrast success task"
            )
        refs = _text_list(
            raw.get("evidence_refs"),
            label=f"failure_types[{index}].evidence_refs",
            minimum=2,
        )
        normalized_refs: list[str] = []
        for value in refs:
            _, relative = _resolve("evidence", value, must_exist=True)
            normalized_refs.append(relative)
            all_type_refs.add(relative)
        normalized_types.append(
            {
                **dict(raw),
                "type_id": type_id,
                "label": label,
                "member_tasks": members,
                "excluded_tasks": excluded,
                "matched_success_tasks": matched,
                "evidence_refs": sorted(set(normalized_refs)),
            }
        )

    raw_hypotheses = discovery.get("hypotheses_considered")
    if not isinstance(raw_hypotheses, list) or len(raw_hypotheses) < 2:
        raise GuardedWorkspaceError(
            "hypotheses_considered must contain at least two hypothesis objects"
        )
    hypothesis_ids: set[str] = set()
    hypothesis_type: dict[str, str] = {}
    normalized_hypotheses: list[dict[str, Any]] = []
    success_policy = contract.get("success_counterfactual", "optional")
    for index, raw in enumerate(raw_hypotheses):
        if not isinstance(raw, Mapping):
            raise GuardedWorkspaceError(
                f"hypotheses_considered[{index}] must be an object"
            )
        hypothesis_id = _text(
            raw.get("hypothesis_id"),
            label=f"hypotheses_considered[{index}].hypothesis_id",
        )
        if hypothesis_id in hypothesis_ids:
            raise GuardedWorkspaceError(f"duplicate hypothesis ID: {hypothesis_id}")
        hypothesis_ids.add(hypothesis_id)
        failure_type_id = _text(
            raw.get("failure_type_id"),
            label=f"hypotheses_considered[{index}].failure_type_id",
        )
        if failure_type_id not in type_ids:
            raise GuardedWorkspaceError(
                f"hypothesis {hypothesis_id!r} names an unknown failure type"
            )
        hypothesis_type[hypothesis_id] = failure_type_id
        mechanism = _text(
            raw.get("mechanism"),
            label=f"hypotheses_considered[{index}].mechanism",
        )
        failure_prediction = _text(
            raw.get("failure_prediction"),
            label=f"hypotheses_considered[{index}].failure_prediction",
        )
        counterfactual = raw.get("success_counterfactual")
        insufficient = raw.get("insufficient_contrast") is True
        if success_policy == "required_or_insufficient" and not (
            isinstance(counterfactual, str) and counterfactual.strip()
        ) and not insufficient:
            raise GuardedWorkspaceError(
                f"hypothesis {hypothesis_id!r} needs a success counterfactual "
                "or insufficient_contrast=true"
            )
        normalized_hypotheses.append(
            {
                **dict(raw),
                "hypothesis_id": hypothesis_id,
                "failure_type_id": failure_type_id,
                "mechanism": mechanism,
                "failure_prediction": failure_prediction,
            }
        )

    evidence_refs = _text_list(
        discovery.get("evidence_refs"), label="evidence_refs", minimum=2
    )
    normalized_evidence_refs: list[str] = []
    for value in evidence_refs:
        _, relative = _resolve("evidence", value, must_exist=True)
        normalized_evidence_refs.append(relative)
    required_access = set(normalized_evidence_refs) | all_type_refs
    missing_access = sorted(required_access - _accessed_evidence_paths())
    if missing_access:
        raise GuardedWorkspaceError(
            "discovery evidence_refs must be read or probed before decision: "
            + ", ".join(missing_access)
        )

    used_probe_ids = _text_list(
        discovery.get("probe_ids_used"), label="probe_ids_used", minimum=1
    )
    probes = _probe_records()
    missing_probes = sorted(set(used_probe_ids) - set(probes))
    if missing_probes:
        raise GuardedWorkspaceError(
            "decision references unknown probes: " + ", ".join(missing_probes)
        )
    probed_hypothesis_ids: set[str] = set()
    for probe_id in used_probe_ids:
        expectations = probes[probe_id].get("hypothesis_expectations")
        if isinstance(expectations, Mapping):
            probed_hypothesis_ids.update(str(value) for value in expectations)
    unknown_probe_hypotheses = sorted(probed_hypothesis_ids - hypothesis_ids)
    if unknown_probe_hypotheses:
        raise GuardedWorkspaceError(
            "probe expectations name unknown hypotheses: "
            + ", ".join(unknown_probe_hypotheses)
        )
    eliminated = _text_list(
        discovery.get("hypotheses_eliminated", []),
        label="hypotheses_eliminated",
    )
    if not set(eliminated) <= hypothesis_ids:
        raise GuardedWorkspaceError("hypotheses_eliminated contains an unknown ID")
    selected = discovery.get("selected_hypothesis_id")
    selected_id = (
        _text(selected, label="selected_hypothesis_id")
        if selected is not None
        else None
    )
    if selected_id is not None and selected_id not in hypothesis_ids:
        raise GuardedWorkspaceError("selected_hypothesis_id is unknown")
    if selected_id in set(eliminated):
        raise GuardedWorkspaceError("selected hypothesis cannot be eliminated")
    decision_hypotheses = set(eliminated)
    if selected_id is not None:
        decision_hypotheses.add(selected_id)
    unprobed_decision_hypotheses = sorted(
        decision_hypotheses - probed_hypothesis_ids
    )
    if unprobed_decision_hypotheses:
        raise GuardedWorkspaceError(
            "selected or eliminated hypotheses lack probe expectations: "
            + ", ".join(unprobed_decision_hypotheses)
        )

    normalized: dict[str, Any] = {
        **dict(discovery),
        "decision": decision,
        "failure_types": normalized_types,
        "hypotheses_considered": normalized_hypotheses,
        "evidence_refs": sorted(set(normalized_evidence_refs)),
        "probe_ids_used": used_probe_ids,
        "probe_records_used": [
            _decision_probe_record(probes[probe_id]) for probe_id in used_probe_ids
        ],
        "hypotheses_eliminated": eliminated,
        "selected_hypothesis_id": selected_id,
        "counterevidence": _text(
            discovery.get("counterevidence"), label="counterevidence"
        ),
        "uncertainty": _text(discovery.get("uncertainty"), label="uncertainty"),
    }
    components: list[str] = []
    if decision == "ACT":
        if not eliminated:
            raise GuardedWorkspaceError(
                "ACT requires a probe that eliminated at least one hypothesis"
            )
        if selected_id is None:
            raise GuardedWorkspaceError("ACT requires selected_hypothesis_id")
        grounded_probe_ids: list[str] = []
        grounded_comparisons: list[dict[str, Any]] = []
        if protocol == "semantic_contract_v1":
            if contract.get("probe_policy") != _SEMANTIC_PROBE_KIND:
                raise GuardedWorkspaceError(
                    "semantic_contract_v1 requires the typed semantic probe policy"
                )
            if contract.get("semantic_comparison") != "required_for_act":
                raise GuardedWorkspaceError(
                    "semantic_contract_v1 must require semantic_comparison for ACT"
                )
            grounded_probe_ids = _text_list(
                discovery.get("grounded_comparison_probe_ids"),
                label="grounded_comparison_probe_ids",
                minimum=1,
            )
        elif discovery.get("grounded_comparison_probe_ids") is not None:
            # A6-E may use the exact public-contract representation without
            # making a typed comparison an ACT precondition. Preserve any
            # voluntarily declared comparisons so the representation-only arm
            # remains observable in the audit.
            grounded_probe_ids = _text_list(
                discovery.get("grounded_comparison_probe_ids"),
                label="grounded_comparison_probe_ids",
            )
        if grounded_probe_ids:
            if not set(grounded_probe_ids) <= set(used_probe_ids):
                raise GuardedWorkspaceError(
                    "grounded semantic comparisons must be included in probe_ids_used"
                )
            for probe_id in grounded_probe_ids:
                record = probes[probe_id]
                if record.get("probe_kind") != _SEMANTIC_PROBE_KIND:
                    raise GuardedWorkspaceError(
                        f"grounded comparison {probe_id!r} is not a typed "
                        "semantic probe"
                    )
                if record.get("semantic_relation") not in {
                    "supports",
                    "contradicts",
                }:
                    raise GuardedWorkspaceError(
                        f"typed semantic probe {probe_id!r} has an insufficient "
                        "relation and cannot ground ACT"
                    )
                expectations = record.get("hypothesis_expectations")
                matches = record.get("expectation_matches")
                if not isinstance(expectations, Mapping) or not isinstance(
                    matches, Mapping
                ):
                    raise GuardedWorkspaceError(
                        f"typed semantic probe {probe_id!r} has no match record"
                    )
                if (
                    selected_id not in expectations
                    or matches.get(selected_id) is not True
                ):
                    raise GuardedWorkspaceError(
                        f"typed semantic probe {probe_id!r} does not match the "
                        "selected hypothesis"
                    )
                contradicted = [
                    hypothesis_id
                    for hypothesis_id in eliminated
                    if hypothesis_id in expectations
                    and matches.get(hypothesis_id) is False
                ]
                if not contradicted:
                    raise GuardedWorkspaceError(
                        f"typed semantic probe {probe_id!r} does not contradict "
                        "an eliminated competing hypothesis"
                    )
                task_id = record.get("task_id")
                selected_type = hypothesis_type[selected_id]
                if task_id not in type_members[selected_type]:
                    raise GuardedWorkspaceError(
                        f"typed semantic probe {probe_id!r} is outside the selected "
                        "failure type"
                    )
                compact = _decision_probe_record(record)
                grounded_comparisons.append(
                    {
                        "probe_id": probe_id,
                        "task_id": compact.get("task_id"),
                        "clause": compact.get("clause"),
                        "artifact": compact.get("artifact"),
                        "trace": compact.get("trace"),
                        "comparison_claim": compact.get("comparison_claim"),
                        "semantic_relation": compact.get("semantic_relation"),
                        "selected_hypothesis_id": selected_id,
                        "contradicted_hypothesis_ids": contradicted,
                        "result_sha256": compact.get("result_sha256"),
                        "causal_truth_certified": False,
                    }
                )
            normalized["grounded_comparison_probe_ids"] = grounded_probe_ids
            normalized["grounded_semantic_comparisons"] = grounded_comparisons
        components = _text_list(
            discovery.get("components"), label="components", minimum=1
        )
        max_components = contract.get("max_components", 1)
        if isinstance(max_components, bool) or not isinstance(max_components, int):
            raise GuardedWorkspaceError("contract max_components is invalid")
        if len(components) > max_components:
            raise GuardedWorkspaceError(
                f"ACT may change at most {max_components} component roles"
            )
        if any(component not in _COMPONENT_ROLES for component in components):
            raise GuardedWorkspaceError("components contains an unknown role")
        prediction = discovery.get("prediction")
        if not isinstance(prediction, (str, list, Mapping)) or not prediction:
            raise GuardedWorkspaceError("ACT requires a falsifiable prediction")
        normalized["prediction"] = prediction
        normalized["risk_tasks"] = _text_list(
            discovery.get("risk_tasks", []), label="risk_tasks"
        )
    else:
        normalized["abstain_reason"] = _text(
            discovery.get("abstain_reason"), label="abstain_reason"
        )
        if discovery.get("components") not in (None, []):
            raise GuardedWorkspaceError("ABSTAIN must not declare components")
        if discovery.get("grounded_comparison_probe_ids") is not None:
            grounded = _text_list(
                discovery.get("grounded_comparison_probe_ids"),
                label="grounded_comparison_probe_ids",
            )
            if not set(grounded) <= set(used_probe_ids):
                raise GuardedWorkspaceError(
                    "ABSTAIN grounded comparisons must be included in probe_ids_used"
                )
            normalized["grounded_comparison_probe_ids"] = grounded
    normalized["components"] = components
    if len(components) == 1:
        normalized["component"] = components[0]

    encoded = json.dumps(
        normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    if len(encoded) > 256_000:
        raise GuardedWorkspaceError("discovery decision exceeds size limit")
    digest = hashlib.sha256(encoded).hexdigest()
    state = {
        "schema_version": 3 if protocol == "semantic_contract_v1" else 2,
        "protocol": protocol,
        "decision": decision,
        "unlocked": decision == "ACT",
        "hypothesis_sha256": digest,
        "hypothesis": normalized,
        "contract_requirements": {
            "success_counterfactual": success_policy,
            "probe_policy": contract.get("probe_policy"),
            "max_components": contract.get("max_components"),
            "semantic_comparison": contract.get("semantic_comparison"),
            "evaluator_feedback_tier": feedback_tier,
            "feedback_manifest_digest": contract.get("feedback_manifest_digest"),
        },
    }
    path = _result_path(_DISCOVERY_STATE_NAME)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(state, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)
    _audit(
        operation="decision",
        source="discovery",
        relative_path=f"{decision.casefold()}:{digest}",
        bytes_returned=0,
    )
    return {
        "decision": decision,
        "unlocked": decision == "ACT",
        "hypothesis_sha256": digest,
        "components": components,
        "probe_ids_used": used_probe_ids,
        "hypotheses_eliminated": eliminated,
        "grounded_comparison_probe_ids": normalized.get(
            "grounded_comparison_probe_ids", []
        ),
    }


def list_workspace(source: str, pattern: str = "**/*") -> dict[str, Any]:
    """List files in a candidate, evidence, or framework-reference workspace."""

    relative_pattern = _relative(pattern, label="pattern")
    root = _root(source)
    paths: list[str] = []
    for path in root.glob(relative_pattern.as_posix()):
        relative = path.relative_to(root)
        if path.is_symlink() or not path.is_file():
            continue
        _reject_symlinks(root, PurePosixPath(relative.as_posix()))
        paths.append(relative.as_posix())
        if len(paths) > _MAX_LISTED_PATHS:
            raise GuardedWorkspaceError("workspace listing exceeds path limit")
    paths.sort()
    _audit(
        operation="list",
        source=source,
        relative_path=relative_pattern.as_posix(),
        bytes_returned=sum(len(path.encode("utf-8")) for path in paths),
    )
    return {"paths": paths}


def read_workspace(
    source: str,
    file_path: str,
    start_line: int = 1,
    max_lines: int = 400,
) -> dict[str, Any]:
    """Read a bounded line range from an authorized workspace text file."""

    if start_line < 1 or not 1 <= max_lines <= 2_000:
        raise GuardedWorkspaceError("start_line must be >= 1 and max_lines must be 1..2000")
    path, relative = _resolve(source, file_path, must_exist=True)
    text = _read_text(path)
    lines = text.splitlines(keepends=True)
    content = "".join(lines[start_line - 1 : start_line - 1 + max_lines])
    _audit(
        operation="read",
        source=source,
        relative_path=relative,
        bytes_returned=len(content.encode("utf-8")),
    )
    return {
        "path": relative,
        "content": content,
        "start_line": start_line,
        "lines_returned": len(content.splitlines()),
        "total_lines": len(lines),
    }


def search_evidence(pattern: str, max_hits: int = 100) -> dict[str, Any]:
    """Search immutable evidence text without exposing another filesystem root."""

    if not isinstance(pattern, str) or not pattern or len(pattern) > 256:
        raise GuardedWorkspaceError("search pattern must contain 1..256 characters")
    if not 1 <= max_hits <= 500:
        raise GuardedWorkspaceError("max_hits must be between 1 and 500")
    try:
        expression = re.compile(pattern, flags=re.IGNORECASE)
    except re.error as exc:
        raise GuardedWorkspaceError(f"invalid search regex: {exc}") from exc

    root = _root("evidence")
    hits: list[dict[str, Any]] = []
    files_seen = 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        _reject_symlinks(root, PurePosixPath(relative))
        files_seen += 1
        if files_seen > _MAX_SEARCH_FILES:
            raise GuardedWorkspaceError("evidence search exceeds file limit")
        try:
            text = _read_text(path)
        except GuardedWorkspaceError:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            if expression.search(line):
                encoded = line.encode("utf-8")[:_MAX_SEARCH_LINE_BYTES]
                hits.append(
                    {
                        "path": relative,
                        "line": line_number,
                        "text": encoded.decode("utf-8", errors="ignore"),
                    }
                )
                if len(hits) >= max_hits:
                    break
        if len(hits) >= max_hits:
            break
    returned = len(json.dumps(hits, ensure_ascii=False).encode("utf-8"))
    _audit(
        operation="search",
        source="evidence",
        relative_path=pattern,
        bytes_returned=returned,
    )
    return {"hits": hits, "truncated": len(hits) >= max_hits}


def _require_declared_component(state: Mapping[str, Any], relative: str) -> None:
    if state.get("protocol") not in {
        "failure_type_v1",
        "semantic_contract_v1",
        "quant_property_v2",
    }:
        return
    hypothesis = state.get("hypothesis")
    hypothesis = dict(hypothesis) if isinstance(hypothesis, Mapping) else {}
    components = hypothesis.get("components")
    declared = {
        str(value) for value in components if isinstance(value, str)
    } if isinstance(components, list) else set()
    role = _component_role(relative)
    if role not in declared:
        raise GuardedWorkspaceError(
            f"candidate path {relative!r} belongs to undeclared component {role!r}"
        )


def write_candidate(file_path: str, content: str) -> dict[str, Any]:
    """Atomically write one UTF-8 file inside the candidate tree."""

    state = _require_intervention_unlocked()
    if not isinstance(content, str):
        raise GuardedWorkspaceError("content must be text")
    encoded = content.encode("utf-8")
    if len(encoded) > _MAX_WRITE_BYTES:
        raise GuardedWorkspaceError(f"content exceeds {_MAX_WRITE_BYTES}-byte write limit")
    path, relative = _resolve("candidate", file_path, must_exist=False)
    _require_declared_component(state, relative)
    root = _root("candidate")
    parent_relative = PurePosixPath(relative).parent
    if parent_relative.as_posix() != ".":
        _reject_symlinks(root, parent_relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    _reject_symlinks(root, PurePosixPath(relative))
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temp_path = Path(handle.name)
    try:
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()
    _audit(
        operation="write",
        source="candidate",
        relative_path=relative,
        bytes_returned=0,
    )
    return {"path": relative, "bytes_written": len(encoded)}


def replace_candidate(
    file_path: str,
    old_string: str,
    new_string: str,
    expected_replacements: int = 1,
) -> dict[str, Any]:
    """Replace an exact, expected number of occurrences in a candidate file."""

    if not old_string:
        raise GuardedWorkspaceError("old_string must not be empty")
    if expected_replacements < 1:
        raise GuardedWorkspaceError("expected_replacements must be positive")
    path, relative = _resolve("candidate", file_path, must_exist=True)
    text = _read_text(path)
    actual = text.count(old_string)
    if actual != expected_replacements:
        raise GuardedWorkspaceError(
            f"expected {expected_replacements} replacements, found {actual}"
        )
    write_candidate(relative, text.replace(old_string, new_string))
    _audit(
        operation="replace",
        source="candidate",
        relative_path=relative,
        bytes_returned=0,
    )
    return {"path": relative, "replacements": actual}


def delete_candidate(file_path: str) -> dict[str, Any]:
    """Delete one declared candidate file without exposing a general shell."""

    state = _require_intervention_unlocked()
    path, relative = _resolve("candidate", file_path, must_exist=True)
    _require_declared_component(state, relative)
    if relative in {"agent.yaml", "systemprompt.md"}:
        raise GuardedWorkspaceError(
            f"required candidate file cannot be deleted: {relative}"
        )
    if path.is_symlink() or not path.is_file():
        raise GuardedWorkspaceError("delete_candidate requires one regular file")
    root = _root("candidate")
    path.unlink()
    parent = path.parent
    while parent != root:
        try:
            parent.rmdir()
        except OSError:
            break
        parent = parent.parent
    _audit(
        operation="delete",
        source="candidate",
        relative_path=relative,
        bytes_returned=0,
    )
    return {"path": relative, "deleted": True}


def _declared_components(state: Mapping[str, Any]) -> set[str]:
    hypothesis = state.get("hypothesis")
    hypothesis = dict(hypothesis) if isinstance(hypothesis, Mapping) else {}
    raw = hypothesis.get("components")
    if isinstance(raw, list):
        return {str(value) for value in raw if isinstance(value, str)}
    component = hypothesis.get("component")
    return {str(component)} if isinstance(component, str) else set()


def _record_component_test(result: Mapping[str, Any]) -> dict[str, Any]:
    """Append one bounded component test result beside the candidate audit."""

    normalized = json.loads(
        json.dumps(dict(result), sort_keys=True, ensure_ascii=False, default=str)
    )
    path = _result_path(_COMPONENT_TEST_LOG_NAME)
    index = 1
    if path.is_file():
        index += len(path.read_text(encoding="utf-8").splitlines())
    record = {
        "schema_version": 1,
        "test_index": index,
        "candidate_digest": _candidate_tree_digest(),
        **normalized,
    }
    payload = json.dumps(record, sort_keys=True, ensure_ascii=False)
    if len(payload.encode("utf-8")) > _MAX_PROCESS_OUTPUT_BYTES * 2:
        raise GuardedWorkspaceError("component test record exceeds bounded size")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(payload + "\n")
    return record


def _candidate_tree_digest() -> str:
    """Match the coordinator's worker identity for a component-test snapshot."""

    root = _root("candidate")
    digest = hashlib.sha256()
    members = tuple(root.rglob("*"))
    if any(path.is_symlink() for path in members):
        raise GuardedWorkspaceError("candidate component smoke forbids symlinks")
    files = sorted(
        (
            path
            for path in members
            if path.is_file()
            and ".git" not in path.parts
            and "__pycache__" not in path.parts
        ),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    for path in files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        payload = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def smoke_candidate_component(
    component: str,
    target: str,
    operation: str = "import",
    symbol: str = "",
    args_json: str = "{}",
    timeout_seconds: int = 20,
) -> dict[str, Any]:
    """Smoke one declared component or the complete NexAU configuration graph.

    This is deliberately narrower than arbitrary Python or shell execution.  It
    supports import/call/construct for local component modules, frontmatter
    loading for one registered skill, and a no-model ``AgentConfig`` load for
    the complete graph.  The subprocess receives placeholders instead of model
    credentials.
    """

    state = _require_intervention_unlocked()
    if component not in _COMPONENT_ROLES:
        raise GuardedWorkspaceError("component is not a harness component role")
    if component not in _declared_components(state):
        raise GuardedWorkspaceError("component was not declared by the ACT decision")
    if operation not in {"import", "call", "construct", "load", "graph"}:
        raise GuardedWorkspaceError("component smoke operation is unsupported")
    if not 1 <= timeout_seconds <= 120:
        raise GuardedWorkspaceError("timeout_seconds must be between 1 and 120")
    try:
        arguments = json.loads(args_json)
    except json.JSONDecodeError as exc:
        raise GuardedWorkspaceError(f"args_json is invalid JSON: {exc}") from exc
    if not isinstance(arguments, dict):
        raise GuardedWorkspaceError("args_json must decode to an object")

    root = _root("candidate")
    runtime_root = _runtime_root()
    importlib.invalidate_caches()
    if component == "skills":
        if operation != "load":
            raise GuardedWorkspaceError("skills support only the load smoke operation")
        path, relative = _resolve("candidate", target, must_exist=True)
        if not relative.startswith("skills/") or not relative.endswith("/SKILL.md"):
            raise GuardedWorkspaceError("skill smoke target must be skills/*/SKILL.md")
        text = _read_text(path)
        lines = text.splitlines()
        if not lines or lines[0].strip() != "---":
            raise GuardedWorkspaceError("skill frontmatter is missing")
        try:
            closing = next(
                index
                for index, line in enumerate(lines[1:], start=1)
                if line.strip() == "---"
            )
        except StopIteration as exc:
            raise GuardedWorkspaceError("skill frontmatter is unterminated") from exc
        try:
            import yaml

            metadata = yaml.safe_load("\n".join(lines[1:closing]))
        except Exception as exc:  # noqa: BLE001 - bounded parse boundary.
            raise GuardedWorkspaceError(
                f"skill frontmatter is invalid: {type(exc).__name__}: {exc}"
            ) from exc
        if not isinstance(metadata, Mapping) or not all(
            isinstance(metadata.get(key), str) and str(metadata[key]).strip()
            for key in ("name", "description")
        ):
            raise GuardedWorkspaceError("skill frontmatter needs name and description")
        _audit(
            operation="component_smoke",
            source="candidate",
            relative_path=relative,
            bytes_returned=len(text.encode("utf-8")),
        )
        return _record_component_test({
            "component": component,
            "operation": operation,
            "target": relative,
            "status": "passed",
            "exit_code": 0,
            "metadata": {"name": metadata["name"], "description": metadata["description"]},
        })

    if component == "agent_config":
        if operation != "graph" or target != "agent.yaml":
            raise GuardedWorkspaceError(
                "agent_config smoke requires target=agent.yaml and operation=graph"
            )
        runner = (
            "import json,sys;"
            "from pathlib import Path;"
            "from nexau import AgentConfig;"
            "c=AgentConfig.from_yaml(config_path=Path(sys.argv[1]));"
            "print(json.dumps({'tools':len(c.tools)},sort_keys=True))"
        )
        argv = [sys.executable, "-c", runner, str(root / "agent.yaml")]
        relative_target = "agent.yaml"
    else:
        if component not in {"tools", "validator", "middleware", "routing", "memory"}:
            raise GuardedWorkspaceError(
                "this component has no executable smoke contract"
            )
        prefix = component
        if not re.fullmatch(
            rf"{re.escape(prefix)}(?:\.[A-Za-z_][A-Za-z0-9_]*)+", target
        ):
            raise GuardedWorkspaceError(
                f"target must be a dotted module below {prefix}"
            )
        if operation in {"call", "construct"} and (
            not symbol.isidentifier() or symbol.startswith("_")
        ):
            raise GuardedWorkspaceError(
                "call or construct smoke requires a public symbol"
            )
        runner = (
            "import importlib,json,sys;"
            "m=importlib.import_module(sys.argv[1]);"
            "op=sys.argv[2];s=sys.argv[3];a=json.loads(sys.argv[4]);"
            "o=m if op=='import' else getattr(m,s);"
            "r=({'module':m.__name__} if op=='import' else "
            "o(**a) if op=='call' else {'constructed':type(o(**a)).__name__});"
            "print(json.dumps(r,sort_keys=True,default=str))"
        )
        argv = [
            sys.executable,
            "-c",
            runner,
            target,
            operation,
            symbol,
            json.dumps(arguments),
        ]
        relative_target = f"{target}:{symbol}" if symbol else target

    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": os.pathsep.join((str(root), str(runtime_root))),
        "PYTHONDONTWRITEBYTECODE": "1",
        "LANG": "C.UTF-8",
        "LLM_MODEL": "component-smoke-only",
        "LLM_BASE_URL": "https://invalid.local/v1",
        "LLM_API_KEY": "not-a-real-key",
    }
    try:
        completed = subprocess.run(
            argv,
            cwd=root,
            env=env,
            capture_output=True,
            text=False,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        _record_component_test(
            {
                "component": component,
                "operation": operation,
                "target": relative_target,
                "status": "failed",
                "exit_code": None,
                "timed_out": True,
                "timeout_seconds": timeout_seconds,
            }
        )
        raise GuardedWorkspaceError(
            f"candidate component timed out after {timeout_seconds} seconds"
        ) from exc
    stdout = completed.stdout[:_MAX_PROCESS_OUTPUT_BYTES]
    stderr = completed.stderr[:_MAX_PROCESS_OUTPUT_BYTES]
    _audit(
        operation="component_smoke",
        source="candidate",
        relative_path=f"{component}:{relative_target}:{operation}",
        bytes_returned=len(stdout) + len(stderr),
    )
    return _record_component_test({
        "component": component,
        "operation": operation,
        "target": relative_target,
        "status": "passed" if completed.returncode == 0 else "failed",
        "exit_code": completed.returncode,
        "stdout": stdout.decode("utf-8", errors="replace"),
        "stderr": stderr.decode("utf-8", errors="replace"),
        "output_truncated": (
            len(completed.stdout) > _MAX_PROCESS_OUTPUT_BYTES
            or len(completed.stderr) > _MAX_PROCESS_OUTPUT_BYTES
        ),
    })


def smoke_candidate_tool(
    module: str,
    function: str,
    args_json: str = "{}",
    timeout_seconds: int = 20,
) -> dict[str, Any]:
    """Import and invoke a candidate local tool through a bounded Python argv."""

    if not re.fullmatch(r"tools(?:\.[A-Za-z_][A-Za-z0-9_]*)+", module):
        raise GuardedWorkspaceError("module must be a dotted path below tools")
    if not function.isidentifier() or function.startswith("_"):
        raise GuardedWorkspaceError("function must be a public Python identifier")
    if not 1 <= timeout_seconds <= 120:
        raise GuardedWorkspaceError("timeout_seconds must be between 1 and 120")
    try:
        arguments = json.loads(args_json)
    except json.JSONDecodeError as exc:
        raise GuardedWorkspaceError(f"args_json is invalid JSON: {exc}") from exc
    if not isinstance(arguments, dict):
        raise GuardedWorkspaceError("args_json must decode to an object")

    root = _root("candidate")
    runtime_root = _runtime_root()
    importlib.invalidate_caches()
    runner = (
        "import importlib,json,sys;"
        "m=importlib.import_module(sys.argv[1]);"
        "f=getattr(m,sys.argv[2]);"
        "a=json.loads(sys.argv[3]);"
        "print(json.dumps(f(**a),sort_keys=True,default=str))"
    )
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": os.pathsep.join((str(root), str(runtime_root))),
        "PYTHONDONTWRITEBYTECODE": "1",
        "LANG": "C.UTF-8",
    }
    try:
        completed = subprocess.run(
            [sys.executable, "-c", runner, module, function, json.dumps(arguments)],
            cwd=root,
            env=env,
            capture_output=True,
            text=False,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise GuardedWorkspaceError(
            f"candidate tool timed out after {timeout_seconds} seconds"
        ) from exc
    stdout = completed.stdout[:_MAX_PROCESS_OUTPUT_BYTES]
    stderr = completed.stderr[:_MAX_PROCESS_OUTPUT_BYTES]
    _audit(
        operation="smoke",
        source="candidate",
        relative_path=f"{module}:{function}",
        bytes_returned=len(stdout) + len(stderr),
    )
    return {
        "exit_code": completed.returncode,
        "stdout": stdout.decode("utf-8", errors="replace"),
        "stderr": stderr.decode("utf-8", errors="replace"),
        "output_truncated": (
            len(completed.stdout) > _MAX_PROCESS_OUTPUT_BYTES
            or len(completed.stderr) > _MAX_PROCESS_OUTPUT_BYTES
        ),
    }
