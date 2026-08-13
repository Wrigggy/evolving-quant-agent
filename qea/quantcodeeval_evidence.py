"""Answer-free evidence for QuantCodeEval property-guided search.

The trusted checker output contains individual property identifiers and details.
Those fields are useful to the verifier, but they are deliberately not part of
the Evolver surface.  This module accepts only a closed aggregate schema and
materializes coarse public/task-process facts for the PGBHS coordinator.
"""

from __future__ import annotations

import ast
from collections import Counter
import hashlib
import json
import os
import re
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Mapping

from .evolution_evidence import EvidenceRecord


_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_TASK_ID = re.compile(r"T(?:0[1-9]|[12][0-9]|30)\Z")
_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_FAMILY_KEYS = frozenset({"total", "passed", "failed", "skipped", "errors"})
_SUMMARY_KEYS = frozenset(
    {
        "schema_version",
        "benchmark",
        "official_reward",
        "property_families",
        "diagnostic_tags",
    }
)
_PROHIBITED_ORACLE_KEYS = frozenset(
    {
        "checker",
        "checkers",
        "detail",
        "expected",
        "gold",
        "golden_ref",
        "property_id",
        "reference",
        "reference_implementation",
        "verdict",
    }
)
_PROHIBITED_SOURCE_PARTS = frozenset(
    {
        "checker",
        "checkers",
        "gold",
        "golden_ref.py",
        "golden_ref_checker_results.json",
        "golden_ref_metrics.json",
        "properties",
        "reference",
        "references",
        "solution",
        "tests",
        "trusted-verifier",
        "trusted_verifier",
        "verifier",
    }
)
_PROHIBITED_SOURCE_NAMES = frozenset(
    {
        "ctrf.json",
        "golden_ref.py",
        "golden_ref_checker_results.json",
        "golden_ref_metrics.json",
        "strategy_digest.md",
    }
)
_PROCESS_FIELDS = frozenset(
    {
        "turns",
        "tool_calls",
        "tool_errors",
        "files",
        "elapsed_seconds",
        "timed_out",
        "dependency_lock_sha256",
    }
)


class QuantCodeEvalEvidenceError(ValueError):
    """Evidence input is incomplete or crosses the checker firewall."""


def _integer(value: object, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise QuantCodeEvalEvidenceError(f"{label} must be a non-negative integer")
    return value


@dataclass(frozen=True)
class PropertyFamilyProgress:
    """Aggregate completion for one public QuantCodeEval property family."""

    total: int
    passed: int
    failed: int
    skipped: int
    errors: int

    def __post_init__(self) -> None:
        for name in ("total", "passed", "failed", "skipped", "errors"):
            _integer(getattr(self, name), label=name)
        if self.total != self.passed + self.failed + self.skipped + self.errors:
            raise QuantCodeEvalEvidenceError(
                "property-family total differs from its status counts"
            )


@dataclass(frozen=True)
class QuantAttemptEvidence:
    """Closed, answer-free record for one completed task attempt."""

    task_id: str
    evaluation_id: str
    attempt_id: str
    checkpoint: str
    worker_digest: str
    official_reward: float
    type_a: PropertyFamilyProgress
    type_b: PropertyFamilyProgress
    diagnostic_tags: tuple[str, ...]

    def __post_init__(self) -> None:
        if _TASK_ID.fullmatch(self.task_id) is None:
            raise QuantCodeEvalEvidenceError("attempt has an invalid task ID")
        for name in ("evaluation_id", "attempt_id", "checkpoint"):
            value = getattr(self, name)
            if not isinstance(value, str) or _SAFE_ID.fullmatch(value) is None:
                raise QuantCodeEvalEvidenceError(f"{name} must be a path-safe ID")
        if _SHA256.fullmatch(self.worker_digest) is None:
            raise QuantCodeEvalEvidenceError("worker_digest must be SHA-256")
        if isinstance(self.official_reward, bool) or self.official_reward not in {
            0.0,
            1.0,
        }:
            raise QuantCodeEvalEvidenceError("official reward must be binary")
        if any(not isinstance(tag, str) or not tag for tag in self.diagnostic_tags):
            raise QuantCodeEvalEvidenceError("diagnostic tags must be non-empty text")


@dataclass(frozen=True)
class QuantEvidenceAttemptSource:
    """Coordinator-side public/process inputs for one evidence record."""

    record: QuantAttemptEvidence
    answer_free_summary_path: Path
    strategy_path: Path | None = None
    trace_path: Path | None = None
    final_text_path: Path | None = None
    process_summary_path: Path | None = None


def _json(path: Path, *, label: str) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise QuantCodeEvalEvidenceError(f"cannot read {label}: {exc}") from exc
    if not isinstance(payload, dict):
        raise QuantCodeEvalEvidenceError(f"{label} must be a JSON object")
    return payload


def _reject_oracle_keys(value: object, *, label: str) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).strip().casefold()
            if normalized in _PROHIBITED_ORACLE_KEYS:
                raise QuantCodeEvalEvidenceError(
                    f"{label} contains prohibited oracle field {key!r}"
                )
            _reject_oracle_keys(child, label=label)
    elif isinstance(value, list):
        for child in value:
            _reject_oracle_keys(child, label=label)


def _safe_source(path: Path, *, label: str) -> Path:
    unresolved = Path(path).expanduser()
    if unresolved.is_symlink() or not unresolved.is_file():
        raise QuantCodeEvalEvidenceError(f"{label} must be a regular file")
    resolved = unresolved.resolve()
    parts = {part.casefold() for part in resolved.parts}
    if parts & _PROHIBITED_SOURCE_PARTS or resolved.name.casefold() in (
        _PROHIBITED_SOURCE_NAMES
    ):
        raise QuantCodeEvalEvidenceError(f"{label} is on a prohibited oracle path")
    return resolved


def load_answer_free_property_summary(
    path: str | Path,
) -> tuple[float, PropertyFamilyProgress, PropertyFamilyProgress, tuple[str, ...]]:
    """Load only the closed family aggregate emitted by the trusted parser."""

    source = _safe_source(Path(path), label="answer-free property summary")
    payload = _json(source, label="answer-free property summary")
    _reject_oracle_keys(payload, label="answer-free property summary")
    if set(payload) != _SUMMARY_KEYS:
        raise QuantCodeEvalEvidenceError(
            "answer-free property summary has unknown or missing fields"
        )
    if payload["schema_version"] != 1 or payload["benchmark"] != "quantcodeeval":
        raise QuantCodeEvalEvidenceError("answer-free property summary identity differs")
    reward = payload["official_reward"]
    if isinstance(reward, bool) or reward not in {0, 0.0, 1, 1.0}:
        raise QuantCodeEvalEvidenceError("answer-free official reward must be binary")
    families = payload["property_families"]
    if not isinstance(families, dict) or set(families) != {"type_a", "type_b"}:
        raise QuantCodeEvalEvidenceError("property_families must contain Type A and B")

    def family(name: str) -> PropertyFamilyProgress:
        raw = families[name]
        if not isinstance(raw, dict) or set(raw) != _FAMILY_KEYS:
            raise QuantCodeEvalEvidenceError(f"{name} aggregate schema differs")
        return PropertyFamilyProgress(
            **{key: _integer(raw[key], label=f"{name}.{key}") for key in _FAMILY_KEYS}
        )

    tags = payload["diagnostic_tags"]
    if not isinstance(tags, list) or any(
        not isinstance(tag, str) or not tag for tag in tags
    ):
        raise QuantCodeEvalEvidenceError("diagnostic_tags must be a text list")
    type_a = family("type_a")
    type_b = family("type_b")
    all_passed = type_a.passed == type_a.total and type_b.passed == type_b.total
    if float(reward) != (1.0 if all_passed else 0.0):
        raise QuantCodeEvalEvidenceError(
            "answer-free reward differs from aggregate family completion"
        )
    return float(reward), type_a, type_b, tuple(sorted(set(tags)))


def strategy_ast_facts(path: str | Path) -> dict[str, object]:
    """Return source-structure facts without returning implementation text."""

    source = _safe_source(Path(path), label="submitted strategy")
    if source.name != "strategy.py":
        raise QuantCodeEvalEvidenceError("submitted strategy must be named strategy.py")
    payload = source.read_bytes()
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise QuantCodeEvalEvidenceError("submitted strategy must be UTF-8") from exc
    base: dict[str, object] = {
        "schema_version": 1,
        "path": "strategy.py",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size_bytes": len(payload),
        "line_count": len(text.splitlines()),
    }
    try:
        tree = ast.parse(text, filename="strategy.py")
    except SyntaxError as exc:
        return {
            **base,
            "parse_valid": False,
            "syntax_error": {
                "line": exc.lineno,
                "offset": exc.offset,
                "category": "syntax_error",
            },
            "import_roots": [],
            "top_level_symbols": [],
        }
    imports: set[str] = set()
    symbols: list[dict[str, object]] = []
    numeric_constants: list[dict[str, object]] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".", 1)[0])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            positional = (*node.args.posonlyargs, *node.args.args)
            symbols.append(
                {
                    "kind": "function",
                    "name": node.name,
                    "positional_arguments": [argument.arg for argument in positional],
                    "keyword_only_arguments": [
                        argument.arg for argument in node.args.kwonlyargs
                    ],
                    "accepts_varargs": node.args.vararg is not None,
                    "accepts_kwargs": node.args.kwarg is not None,
                    "is_async": isinstance(node, ast.AsyncFunctionDef),
                }
            )
        elif isinstance(node, ast.ClassDef):
            symbols.append({"kind": "class", "name": node.name})
        elif (
            isinstance(node, (ast.Assign, ast.AnnAssign))
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, (int, float))
            and not isinstance(node.value.value, bool)
        ):
            targets = (
                node.targets if isinstance(node, ast.Assign) else (node.target,)
            )
            for target in targets:
                if isinstance(target, ast.Name):
                    numeric_constants.append(
                        {"name": target.id, "value": node.value.value}
                    )
    return {
        **base,
        "parse_valid": True,
        "syntax_error": None,
        "import_roots": sorted(imports),
        "top_level_symbols": symbols,
        "module_numeric_constants": sorted(
            numeric_constants, key=lambda item: str(item["name"])
        ),
    }


def trace_coarse_facts(path: str | Path) -> dict[str, object]:
    """Retain an answer-free runtime timeline without messages or arguments."""

    source = _safe_source(Path(path), label="worker trace")
    payload = source.read_bytes()
    try:
        lines = payload.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise QuantCodeEvalEvidenceError("worker trace must be UTF-8") from exc
    roles: dict[str, int] = {}
    tool_events = tool_errors = malformed = 0
    longest_tool_error_run = current_tool_error_run = 0
    tool_durations_ms = 0
    exit_codes: dict[str, int] = {}
    timeline: list[dict[str, object]] = []
    action_counts: Counter[str] = Counter()
    quant_stage_counts: Counter[str] = Counter()
    public_probe_outcomes: Counter[str] = Counter()
    for index, line in enumerate(lines, start=1):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if not isinstance(event, Mapping):
            malformed += 1
            continue
        role = str(event.get("role", "unknown")).strip().casefold() or "unknown"
        if role.startswith("role."):
            role = role.removeprefix("role.")
        roles[role] = roles.get(role, 0) + 1
        content = event.get("content")
        timeline_item: dict[str, object] = {"event": index, "role": role}
        if role == "assistant" and isinstance(content, str):
            planned = _planned_trace_tools(content)
            if planned:
                timeline_item["planned_actions"] = planned
            for item in planned:
                action_counts[item["action_kind"]] += 1
                quant_stage_counts[item["quant_stage"]] += 1
        event_type = str(event.get("type", "")).casefold()
        is_tool = role in {"tool", "tool_result"} or "tool" in event_type
        inner: Mapping[str, object] = {}
        if is_tool and isinstance(content, str) and content.strip().startswith("{"):
            try:
                decoded = json.loads(content)
            except json.JSONDecodeError:
                decoded = None
            if isinstance(decoded, Mapping):
                inner = decoded
        status = str(event.get("status", inner.get("status", ""))).casefold()
        exit_code = inner.get("exit_code", event.get("exit_code"))
        is_error = (
            event.get("is_error") is True
            or inner.get("is_error") is True
            or status in {"error", "failed"}
            or (
                isinstance(exit_code, int)
                and not isinstance(exit_code, bool)
                and exit_code != 0
            )
        )
        if is_tool:
            tool_events += 1
            timeline_item["tool_status"] = "error" if is_error else "ok"
            if _is_public_probe_result(inner):
                timeline_item["action_kind"] = "public_probe_result"
                outcome = str(inner.get("status", "")).strip().casefold()
                if outcome not in {"passed", "failed"}:
                    outcome = "error" if is_error else "completed"
                timeline_item["probe_outcome"] = outcome
                public_probe_outcomes[outcome] += 1
            if isinstance(exit_code, int) and not isinstance(exit_code, bool):
                exit_codes[str(exit_code)] = exit_codes.get(str(exit_code), 0) + 1
            duration = inner.get("duration_ms", event.get("duration_ms"))
            if isinstance(duration, (int, float)) and not isinstance(duration, bool):
                tool_durations_ms += max(0, int(duration))
                timeline_item["duration_ms"] = max(0, int(duration))
            if inner.get("truncated") is True or event.get("truncated") is True:
                timeline_item["truncated"] = True
            if is_error:
                tool_errors += 1
                current_tool_error_run += 1
                longest_tool_error_run = max(
                    longest_tool_error_run, current_tool_error_run
                )
            else:
                current_tool_error_run = 0
        timeline.append(timeline_item)
    return {
        "schema_version": 3,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size_bytes": len(payload),
        "event_count": len(lines),
        "roles": dict(sorted(roles.items())),
        "tool_event_count": tool_events,
        "tool_error_count": tool_errors,
        "longest_consecutive_tool_errors": longest_tool_error_run,
        "tool_duration_ms_total": tool_durations_ms,
        "tool_exit_codes": dict(sorted(exit_codes.items())),
        "action_counts": dict(sorted(action_counts.items())),
        "quant_stage_counts": dict(sorted(quant_stage_counts.items())),
        "public_probe_outcomes": dict(sorted(public_probe_outcomes.items())),
        "implementation_revision_count": action_counts.get(
            "implementation_update", 0
        ),
        "runtime_timeline": timeline,
        "malformed_event_count": malformed,
        "content_exposed": False,
    }


_TOOL_USE = re.compile(r"<ToolUse>(.*?)</ToolUse>", re.DOTALL)


def _is_public_probe_result(value: Mapping[str, object]) -> bool:
    return "public_basis" in value and "competing_definitions" in value


def _planned_trace_tools(content: str) -> list[dict[str, str]]:
    """Classify Worker tool intentions without retaining arguments or output."""

    planned: list[dict[str, str]] = []
    for match in _TOOL_USE.finditer(content):
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, Mapping):
            continue
        name = payload.get("name")
        if not isinstance(name, str) or not name:
            continue
        item = {"tool_name": name}
        if name == "LoadSkill":
            item.update(
                action_kind="skill_load",
                quant_stage="requirement_comprehension",
            )
        elif name in {"probe_public_behavior", "probe_quant_invariants"}:
            item.update(
                action_kind="public_probe",
                quant_stage="implementation_realization",
            )
        elif name == "run_shell_command":
            raw_input = payload.get("input")
            input_map = raw_input if isinstance(raw_input, Mapping) else {}
            command = str(input_map.get("command", "")).casefold()
            description = str(input_map.get("description", "")).casefold()
            hint = f"{description}\n{command}"
            if (
                "/app/output/strategy.py" in command
                and any(
                    marker in command
                    for marker in ("cat >", "apply_patch", "patched")
                )
            ):
                item.update(
                    action_kind="implementation_update",
                    quant_stage="implementation_realization",
                )
            elif any(
                marker in hint
                for marker in ("sanity", "smoke", "assert", "fixture", "py_compile")
            ):
                item.update(
                    action_kind="synthetic_invariant",
                    quant_stage="implementation_realization",
                )
            elif "paper_text" in hint:
                item.update(
                    action_kind="public_definition_retrieval",
                    quant_stage="source_retrieval",
                )
            elif any(
                marker in hint
                for marker in (
                    "data_descriptor",
                    "read_csv",
                    "factor_returns_monthly",
                    "data profile",
                    "peek csv",
                )
            ):
                item.update(
                    action_kind="data_profile",
                    quant_stage="requirement_comprehension",
                )
            elif any(
                marker in hint
                for marker in ("import strategy", "import ok", "interface")
            ):
                item.update(
                    action_kind="artifact_smoke",
                    quant_stage="execution_completion",
                )
            else:
                item.update(
                    action_kind="shell_inspection",
                    quant_stage="implementation_realization",
                )
        else:
            item.update(
                action_kind="other_tool",
                quant_stage="implementation_realization",
            )
        planned.append(item)
    return planned


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def _copy_public_text(source: Path, destination: Path, *, label: str) -> None:
    safe = _safe_source(source, label=label)
    try:
        text = safe.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise QuantCodeEvalEvidenceError(f"{label} must be UTF-8") from exc
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")


def _digest_tree(root: Path) -> tuple[str, tuple[str, ...]]:
    digest = hashlib.sha256()
    members: list[str] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file() or path.name == "access_log.jsonl":
            continue
        relative = path.relative_to(root).as_posix()
        payload = path.read_bytes()
        encoded = relative.encode()
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
        members.append(relative)
    return digest.hexdigest(), tuple(members)


def _attempt_payload(source: QuantEvidenceAttemptSource) -> dict[str, object]:
    reward, type_a, type_b, tags = load_answer_free_property_summary(
        source.answer_free_summary_path
    )
    record = source.record
    if (
        reward != record.official_reward
        or type_a != record.type_a
        or type_b != record.type_b
        or tags != tuple(sorted(set(record.diagnostic_tags)))
    ):
        raise QuantCodeEvalEvidenceError(
            f"answer-free summary differs from attempt record {record.attempt_id}"
        )
    return {
        "schema_version": 1,
        "task_id": record.task_id,
        "evaluation_id": record.evaluation_id,
        "attempt_id": record.attempt_id,
        "checkpoint": record.checkpoint,
        "worker_digest": record.worker_digest,
        "official_reward": reward,
        "diagnostic_tags": list(tags),
        "property_families": {
            "type_a": asdict(type_a),
            "type_b": asdict(type_b),
        },
    }


def _process_facts(path: Path) -> dict[str, object]:
    source = _safe_source(path, label="worker process summary")
    payload = _json(source, label="worker process summary")
    _reject_oracle_keys(payload, label="worker process summary")
    facts = {
        key: payload[key]
        for key in sorted(_PROCESS_FIELDS & set(payload))
        if isinstance(payload[key], (bool, int, float, str)) or payload[key] is None
    }
    return {"schema_version": 1, "facts": facts, "content_exposed": False}


def build_quantcodeeval_evidence(
    *,
    destination: str | Path,
    public_task_roots: Mapping[str, str | Path],
    attempts: Iterable[QuantEvidenceAttemptSource],
    current_evaluation_id: str,
    history: Iterable[Mapping[str, object]] = (),
) -> EvidenceRecord:
    """Materialize one immutable answer-free PGBHS evidence corpus."""

    roots = {str(task_id): Path(path).resolve() for task_id, path in public_task_roots.items()}
    if not roots or any(_TASK_ID.fullmatch(task_id) is None for task_id in roots):
        raise QuantCodeEvalEvidenceError("public task roots contain an invalid task ID")
    sources = tuple(attempts)
    if not sources:
        raise QuantCodeEvalEvidenceError("evidence requires at least one attempt")
    if (
        not isinstance(current_evaluation_id, str)
        or _SAFE_ID.fullmatch(current_evaluation_id) is None
    ):
        raise QuantCodeEvalEvidenceError("current_evaluation_id must be path-safe")
    current = [item for item in sources if item.record.evaluation_id == current_evaluation_id]
    if {item.record.task_id for item in current} != set(roots):
        raise QuantCodeEvalEvidenceError(
            "current evaluation must cover the complete fixed task panel"
        )
    if any(item.record.task_id not in roots for item in sources):
        raise QuantCodeEvalEvidenceError("attempt is outside the fixed task panel")

    target = Path(destination).expanduser().resolve()
    if target.exists() or target.is_symlink():
        raise QuantCodeEvalEvidenceError("evidence destination must not already exist")
    staging = target.with_name(target.name + ".partial")
    if staging.exists() or staging.is_symlink():
        raise QuantCodeEvalEvidenceError("evidence staging path already exists")
    staging.mkdir(parents=True)
    try:
        (staging / "access_log.jsonl").write_text("", encoding="utf-8")
        _write_json(
            staging / "contract.json",
            {
                "schema_version": 1,
                "stage": "PGBHS",
                "benchmark": "quantcodeeval",
                "decision_protocol": "quant_property_v1",
                "feedback_tier": "answer_free_property_family_v1",
                "task_ids": sorted(roots),
                "current_evaluation_id": current_evaluation_id,
                "oracle_fields_exposed": False,
            },
        )
        history_payload = [dict(item) for item in history]
        _reject_oracle_keys(history_payload, label="iteration history")
        _write_json(staging / "history" / "iterations.json", history_payload)
        _write_json(
            staging / "current.json",
            {
                "schema_version": 1,
                "evaluation_id": current_evaluation_id,
                "task_ids": sorted(roots),
                "attempt_ids": {
                    item.record.task_id: item.record.attempt_id
                    for item in sorted(current, key=lambda value: value.record.task_id)
                },
            },
        )

        for task_id, task_root in sorted(roots.items()):
            instruction = task_root / "instruction.md"
            paper = task_root / "environment" / "data" / "paper_text.md"
            task_destination = staging / "tasks" / task_id
            _copy_public_text(
                instruction,
                task_destination / "instruction.md",
                label=f"{task_id} public instruction",
            )
            _copy_public_text(
                paper,
                task_destination / "paper_text.md",
                label=f"{task_id} public paper",
            )

        seen: set[tuple[str, str]] = set()
        for source in sorted(
            sources,
            key=lambda item: (item.record.evaluation_id, item.record.task_id),
        ):
            record = source.record
            identity = (record.evaluation_id, record.task_id)
            if identity in seen:
                raise QuantCodeEvalEvidenceError("duplicate task evaluation evidence")
            seen.add(identity)
            root = (
                staging
                / "tasks"
                / record.task_id
                / "evaluations"
                / record.evaluation_id
            )
            payload = _attempt_payload(source)
            _write_json(root / "official_and_families.json", payload)
            if source.strategy_path is not None:
                facts = strategy_ast_facts(source.strategy_path)
                _write_json(root / "strategy_ast_facts.json", facts)
                _write_json(
                    root / "artifact_manifest.json",
                    {
                        "schema_version": 1,
                        "artifacts": [
                            {
                                "path": "strategy.py",
                                "sha256": facts["sha256"],
                                "size_bytes": facts["size_bytes"],
                            }
                        ],
                        "content_exposed": False,
                    },
                )
            else:
                _write_json(
                    root / "artifact_manifest.json",
                    {"schema_version": 1, "artifacts": [], "content_exposed": False},
                )
            if source.trace_path is not None:
                _write_json(root / "trace_facts.json", trace_coarse_facts(source.trace_path))
            if source.process_summary_path is not None:
                _write_json(
                    root / "process_facts.json",
                    _process_facts(source.process_summary_path),
                )
            if source.final_text_path is not None:
                final_source = _safe_source(source.final_text_path, label="worker final text")
                final_bytes = final_source.read_bytes()
                try:
                    final_bytes.decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise QuantCodeEvalEvidenceError("worker final text must be UTF-8") from exc
                _write_json(
                    root / "final_facts.json",
                    {
                        "schema_version": 1,
                        "sha256": hashlib.sha256(final_bytes).hexdigest(),
                        "size_bytes": len(final_bytes),
                        "content_exposed": False,
                    },
                )

        for path in staging.rglob("*"):
            if path.is_symlink():
                raise QuantCodeEvalEvidenceError("evidence tree contains a symlink")
            if path.is_file():
                path.read_text(encoding="utf-8")
        sha256, members = _digest_tree(staging)
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging, target)
        return EvidenceRecord(root=target, sha256=sha256, members=members)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise


__all__ = [
    "PropertyFamilyProgress",
    "QuantAttemptEvidence",
    "QuantCodeEvalEvidenceError",
    "QuantEvidenceAttemptSource",
    "build_quantcodeeval_evidence",
    "load_answer_free_property_summary",
    "strategy_ast_facts",
    "trace_coarse_facts",
]
