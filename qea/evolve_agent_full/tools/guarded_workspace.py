"""Capability-limited workspace tools for the full-harness evolver.

The evolver may read its immutable evidence and framework-reference corpora and
may read/write only the candidate worker tree.  It never receives a
general-purpose shell or Python execution primitive.
"""

from __future__ import annotations

import ast
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
            and record.get("operation") in {"read", "trace_slice", "compare"}
            and isinstance(record.get("relative_path"), str)
        ):
            paths.add(record["relative_path"])
    return paths


def _require_intervention_unlocked() -> dict[str, Any]:
    path = _result_path(_DISCOVERY_STATE_NAME)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GuardedWorkspaceError(
            "candidate writes are locked; call unlock_candidate after evidence-based "
            "discovery"
        ) from exc
    if payload.get("schema_version") != 1 or payload.get("unlocked") is not True:
        raise GuardedWorkspaceError("candidate intervention state is invalid")
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


def write_candidate(file_path: str, content: str) -> dict[str, Any]:
    """Atomically write one UTF-8 file inside the candidate tree."""

    _require_intervention_unlocked()
    if not isinstance(content, str):
        raise GuardedWorkspaceError("content must be text")
    encoded = content.encode("utf-8")
    if len(encoded) > _MAX_WRITE_BYTES:
        raise GuardedWorkspaceError(f"content exceeds {_MAX_WRITE_BYTES}-byte write limit")
    path, relative = _resolve("candidate", file_path, must_exist=False)
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
