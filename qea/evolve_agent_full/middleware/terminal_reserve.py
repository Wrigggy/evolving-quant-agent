"""Fail-closed terminal reserve for long full-harness discovery runs.

The NexAU executor normally stops only after the prompt has already crossed its
context limit.  A long evidence investigation can therefore consume the space
needed for the required ACT/ABSTAIN decision.  This middleware uses the exact
executor token counter and structured-tool payload before every model call.  At
a hard pre-limit threshold it replaces the execution history with a bounded,
deterministic decision state and removes every tool except ``decide_candidate``.
After a decision is durably recorded, no tools are exposed.

The middleware never manufactures a decision.  An invalid or missing terminal
response remains invalid and is rejected by the ordinary discovery/admission
gates.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping, Sequence, cast

from nexau.archs.main_sub.execution.hooks import (
    AfterAgentHookInput,
    AfterModelHookInput,
    AfterToolHookInput,
    BeforeAgentHookInput,
    BeforeModelHookInput,
    HookResult,
    Middleware,
    ModelCallParams,
    ModelCallFn,
    ToolCallFn,
    ToolCallParams,
)
from nexau.core.messages import Message, Role, TextBlock, ToolResultBlock, ToolUseBlock


_AUDIT_NAME = "terminal-reserve.json"
_DISCOVERY_STATE_NAME = "discovery-hypothesis.json"
_PROBE_LOG_NAME = "probe-log.jsonl"
_FULL_TRACE_MESSAGES_KEY = "__nexau_full_trace_messages__"
_FULL_TRACE_SEEN_IDS_KEY = "__nexau_full_trace_seen_ids__"
_ALLOWED_TERMINAL_TOOL = "decide_candidate"
_VALID_DECISIONS = frozenset({"ACT", "ABSTAIN"})
_PROBE_COMPACT_MAX_BYTES = 32_768


class TerminalReserveError(RuntimeError):
    """Raised when the bounded terminal contract cannot be maintained."""


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")


def _utf8_prefix(value: str, limit: int) -> str:
    if limit <= 0:
        return ""
    payload = value.encode("utf-8")
    if len(payload) <= limit:
        return value
    return payload[:limit].decode("utf-8", errors="ignore")


def _utf8_suffix(value: str, limit: int) -> str:
    if limit <= 0:
        return ""
    payload = value.encode("utf-8")
    if len(payload) <= limit:
        return value
    return payload[-limit:].decode("utf-8", errors="ignore")


def _block_payload(block: object, *, max_bytes: int) -> object:
    if isinstance(block, TextBlock):
        return {"kind": "text", "text": _utf8_suffix(block.text, max_bytes)}
    if isinstance(block, ToolUseBlock):
        raw_input = block.raw_input
        if raw_input is None:
            try:
                raw_input = json.dumps(
                    block.input,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                )
            except TypeError:
                raw_input = str(block.input)
        return {
            "kind": "tool_use",
            "name": block.name,
            "input": _utf8_suffix(str(raw_input), max_bytes),
        }
    if isinstance(block, ToolResultBlock):
        content = block.content
        if isinstance(content, str):
            rendered = content
        else:
            rendered = "\n".join(
                item.text if isinstance(item, TextBlock) else "[image]"
                for item in content
            )
        return {
            "kind": "tool_result",
            "is_error": bool(block.is_error),
            "content": _utf8_suffix(rendered, max_bytes),
        }
    return {"kind": type(block).__name__, "text": _utf8_suffix(str(block), max_bytes)}


def _message_payload(message: Message, *, max_bytes: int) -> dict[str, object]:
    blocks = [
        _block_payload(block, max_bytes=max(256, max_bytes // max(len(message.content), 1)))
        for block in message.content
    ]
    payload: dict[str, object] = {"role": message.role.value, "content": blocks}
    encoded = _canonical_bytes(payload)
    if len(encoded) <= max_bytes:
        return payload
    return {
        "role": message.role.value,
        "content": [
            {
                "kind": "bounded_text",
                "text": _utf8_suffix(message.get_text_content(), max(0, max_bytes - 128)),
            }
        ],
    }


def _tool_name(tool: object) -> str | None:
    value: object = tool
    if not isinstance(value, Mapping):
        dumper = getattr(value, "model_dump", None)
        if callable(dumper):
            value = dumper(mode="python", exclude_none=True)
    if not isinstance(value, Mapping):
        return None
    function = value.get("function")
    if isinstance(function, Mapping) and isinstance(function.get("name"), str):
        return cast(str, function["name"])
    name = value.get("name")
    return name if isinstance(name, str) else None


def _normalize_tools(tools: Sequence[object] | None) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for tool in tools or ():
        value: object = tool
        if not isinstance(value, Mapping):
            dumper = getattr(value, "model_dump", None)
            if callable(dumper):
                value = dumper(mode="python", exclude_none=True)
        if not isinstance(value, Mapping):
            raise TerminalReserveError("structured tool payload is not JSON-like")
        normalized.append(dict(value))
    return normalized


def _usage_tokens(value: object) -> dict[str, int | None]:
    if value is None:
        payload: Mapping[str, object] = {}
    elif isinstance(value, Mapping):
        payload = value
    else:
        dumper = getattr(value, "model_dump", None)
        dumped = dumper() if callable(dumper) else {}
        payload = dumped if isinstance(dumped, Mapping) else {}

    def first(*names: str) -> int | None:
        for name in names:
            candidate = payload.get(name)
            if type(candidate) is int and candidate >= 0:
                return candidate
        return None

    return {
        "input_tokens": first("input_tokens", "prompt_tokens"),
        "output_tokens": first("output_tokens", "completion_tokens"),
        "total_tokens": first("total_tokens"),
    }


class DiscoveryTerminalReserve(Middleware):
    """Enter a bounded, tool-restricted terminal phase before context overflow."""

    def __init__(
        self,
        *,
        max_context_tokens: int = 200_000,
        terminal_reserve_tokens: int = 64_000,
        terminal_output_tokens: int = 32_000,
        compact_state_max_bytes: int = 65_536,
        recent_message_max_bytes: int = 8_192,
        max_terminal_model_calls: int = 3,
    ) -> None:
        for name, value in (
            ("max_context_tokens", max_context_tokens),
            ("terminal_reserve_tokens", terminal_reserve_tokens),
            ("terminal_output_tokens", terminal_output_tokens),
            ("compact_state_max_bytes", compact_state_max_bytes),
            ("recent_message_max_bytes", recent_message_max_bytes),
            ("max_terminal_model_calls", max_terminal_model_calls),
        ):
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if terminal_reserve_tokens >= max_context_tokens:
            raise ValueError("terminal_reserve_tokens must be smaller than context")
        if terminal_output_tokens >= terminal_reserve_tokens:
            raise ValueError("terminal output must fit inside terminal reserve")
        if compact_state_max_bytes > terminal_reserve_tokens * 2:
            raise ValueError("compact state byte cap is not conservative")

        self.max_context_tokens = max_context_tokens
        self.terminal_reserve_tokens = terminal_reserve_tokens
        self.terminal_output_tokens = terminal_output_tokens
        self.compact_state_max_bytes = compact_state_max_bytes
        self.recent_message_max_bytes = recent_message_max_bytes
        self.max_terminal_model_calls = max_terminal_model_calls
        self.trigger_tokens = max_context_tokens - terminal_reserve_tokens
        self._phase = "explore"
        self._terminal_model_calls = 0
        self._blocked_tool_calls: Counter[str] = Counter()
        self._events: list[dict[str, object]] = []
        self._trigger: dict[str, object] | None = None
        self._last_compact: dict[str, object] | None = None
        self._initial_candidate_sha256: str | None = None
        self._requires_terminal_abstain = False
        self._model_guard: dict[str, object] | None = None
        self._bound_executor: object | None = None
        self._lock = threading.RLock()

    @staticmethod
    def _result_root() -> Path:
        raw = os.environ.get("QEA_ACCESS_LOG")
        if not raw:
            raise TerminalReserveError("QEA_ACCESS_LOG is required")
        access_log = Path(raw)
        if access_log.name != "access_log.jsonl":
            raise TerminalReserveError("QEA_ACCESS_LOG must name access_log.jsonl")
        root = access_log.parent.resolve(strict=True)
        if access_log.resolve(strict=False).parent != root:
            raise TerminalReserveError("terminal audit path escapes result root")
        return root

    @classmethod
    def _audit_path(cls) -> Path:
        return cls._result_root() / _AUDIT_NAME

    @classmethod
    def _decision_path(cls) -> Path:
        return cls._result_root() / _DISCOVERY_STATE_NAME

    @classmethod
    def _probe_path(cls) -> Path:
        return cls._result_root() / _PROBE_LOG_NAME

    @classmethod
    def _access_path(cls) -> Path:
        return cls._result_root() / "access_log.jsonl"

    @staticmethod
    def _read_json(path: Path) -> Mapping[str, object] | None:
        if not path.is_file() or path.is_symlink():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return value if isinstance(value, Mapping) else None

    @classmethod
    def _decision_state(cls) -> Mapping[str, object] | None:
        state = cls._read_json(cls._decision_path())
        if state is None:
            return None
        decision = state.get("decision")
        if decision not in _VALID_DECISIONS or state.get("unlocked") is not (decision == "ACT"):
            return None
        protocol = state.get("protocol")
        if protocol not in {
            "failure_type_v1",
            "semantic_contract_v1",
            "quant_property_v2",
        }:
            return None
        return state

    @staticmethod
    def _candidate_sha256() -> str:
        raw = os.environ.get("QEA_CANDIDATE_ROOT")
        if not raw:
            raise TerminalReserveError("QEA_CANDIDATE_ROOT is required")
        root = Path(raw).resolve(strict=True)
        if not root.is_dir():
            raise TerminalReserveError("candidate root is unavailable")
        digest = hashlib.sha256()
        for path in sorted(
            root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()
        ):
            relative_path = path.relative_to(root)
            if path.is_symlink():
                raise TerminalReserveError(
                    f"candidate symlink is forbidden: {relative_path}"
                )
            if path.is_dir():
                continue
            if not path.is_file():
                raise TerminalReserveError(
                    f"candidate entry is not regular: {relative_path}"
                )
            relative = relative_path.as_posix().encode("utf-8")
            payload = path.read_bytes()
            digest.update(len(relative).to_bytes(8, "big"))
            digest.update(relative)
            digest.update(len(payload).to_bytes(8, "big"))
            digest.update(payload)
        return digest.hexdigest()

    def _candidate_snapshot(self) -> dict[str, object]:
        current = self._candidate_sha256()
        return {
            "initial_sha256": self._initial_candidate_sha256,
            "current_sha256": current,
            "changed": (
                current != self._initial_candidate_sha256
                if self._initial_candidate_sha256 is not None
                else None
            ),
        }

    def _terminal_phase(self) -> str:
        decision = self._decision_state()
        if decision is None:
            self._requires_terminal_abstain = True
            return "decision"
        if decision.get("decision") == "ACT":
            candidate = self._candidate_snapshot()
            if candidate["changed"] is not True:
                self._requires_terminal_abstain = True
                return "decision"
        self._requires_terminal_abstain = False
        return "final"

    @classmethod
    def _access_snapshot(cls) -> dict[str, object]:
        path = cls._access_path()
        operations: Counter[str] = Counter()
        sources: Counter[str] = Counter()
        evidence_paths: set[str] = set()
        returned_bytes = 0
        record_count = 0
        if path.is_file() and not path.is_symlink():
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(record, Mapping):
                    continue
                record_count += 1
                operations[str(record.get("operation", "unknown"))] += 1
                sources[str(record.get("source", "unknown"))] += 1
                size = record.get("bytes_returned")
                if type(size) is int and size >= 0:
                    returned_bytes += size
                if record.get("source") == "evidence" and isinstance(
                    record.get("relative_path"), str
                ):
                    evidence_paths.add(cast(str, record["relative_path"]))
        return {
            "record_count": record_count,
            "operations": dict(sorted(operations.items())),
            "sources": dict(sorted(sources.items())),
            "bytes_returned": returned_bytes,
            "evidence_path_count": len(evidence_paths),
            "evidence_paths_sha256": _sha256(
                _canonical_bytes(sorted(evidence_paths))
            ),
        }

    @classmethod
    def _probe_snapshot(cls, *, max_bytes: int = _PROBE_COMPACT_MAX_BYTES) -> dict[str, object]:
        path = cls._probe_path()
        if not path.is_file() or path.is_symlink():
            return {"record_count": 0, "sha256": _sha256(b""), "records": []}
        payload = path.read_bytes()
        records: list[dict[str, object]] = []
        for line in payload.splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                records.append(record)
        snapshot: dict[str, object] = {
            "record_count": len(records),
            "sha256": _sha256(payload),
            "records": records,
        }
        if len(_canonical_bytes(snapshot)) <= max_bytes:
            return snapshot

        compacted: list[dict[str, object]] = []
        for record in records:
            core = {
                key: record.get(key)
                for key in (
                    "schema_version",
                    "probe_kind",
                    "probe_id",
                    "question",
                    "task_id",
                    "hypothesis_expectations",
                    "expectation_matches",
                    "expectation_match_details",
                    "evidence_paths",
                    "operation",
                    "semantic_relation",
                    "comparison_claim",
                    "result_sha256",
                )
                if key in record
            }
            observation = record.get("observation")
            if observation is not None:
                core["observation"] = observation
            for name in ("clause", "artifact", "trace"):
                value = record.get(name)
                if isinstance(value, Mapping):
                    if name == "trace":
                        value = {
                            key: value.get(key)
                            for key in (
                                "path",
                                "phase",
                                "phase_present",
                                "event_count",
                                "truncated",
                            )
                        }
                    core[name] = value
            compacted.append(core)
        snapshot["records"] = compacted
        if len(_canonical_bytes(snapshot)) <= max_bytes:
            return snapshot

        # Preserve every probe's identity, expectations, evidence paths, typed
        # match result, and observation digest.  If all bounded observations do
        # not fit, the terminal contract permits ABSTAIN but never a fabricated
        # ACT.  No early probe is dropped merely because later reads occurred.
        minimal: list[dict[str, object]] = []
        for record in compacted:
            observation = record.get("observation")
            minimal.append(
                {
                    key: value
                    for key, value in {
                        "probe_kind": record.get("probe_kind"),
                        "probe_id": record.get("probe_id"),
                        "question": record.get("question"),
                        "hypothesis_expectations": record.get(
                            "hypothesis_expectations"
                        ),
                        "expectation_matches": record.get("expectation_matches"),
                        "evidence_paths": record.get("evidence_paths"),
                        "semantic_relation": record.get("semantic_relation"),
                        "result_sha256": record.get("result_sha256"),
                        "observation_sha256": (
                            _sha256(_canonical_bytes(observation))
                            if observation is not None
                            else None
                        ),
                    }.items()
                    if value is not None
                }
            )
        snapshot["records"] = minimal
        if len(_canonical_bytes(snapshot)) > max_bytes:
            raise TerminalReserveError("probe decision capsule exceeds byte cap")
        return snapshot

    @staticmethod
    def _record_full_trace(agent_state: object, messages: Sequence[Message]) -> None:
        getter = getattr(agent_state, "get_context_value")
        setter = getattr(agent_state, "set_context_value")
        raw_full = getter(_FULL_TRACE_MESSAGES_KEY, [])
        full = list(raw_full) if isinstance(raw_full, list) else []
        raw_seen = getter(_FULL_TRACE_SEEN_IDS_KEY, set())
        seen = set(raw_seen) if isinstance(raw_seen, (set, list)) else set()
        for message in messages:
            identity = id(message)
            if identity in seen:
                continue
            seen.add(identity)
            try:
                full.append(message.model_copy(deep=True))
            except Exception:  # pragma: no cover - future Message compatibility.
                full.append(message)
        setter(_FULL_TRACE_MESSAGES_KEY, full)
        setter(_FULL_TRACE_SEEN_IDS_KEY, seen)

    def _transcript_tail(self, messages: Sequence[Message], *, max_bytes: int) -> list[object]:
        selected: list[object] = []
        used = 2
        for message in reversed(messages):
            if message.role == Role.SYSTEM:
                continue
            item = _message_payload(message, max_bytes=self.recent_message_max_bytes)
            encoded = _canonical_bytes(item)
            if used + len(encoded) > max_bytes:
                remaining = max_bytes - used
                if remaining >= 512:
                    selected.append(
                        {
                            "role": message.role.value,
                            "content": [
                                {
                                    "kind": "bounded_text",
                                    "text": _utf8_suffix(
                                        message.get_text_content(), remaining - 128
                                    ),
                                }
                            ],
                        }
                    )
                break
            selected.append(item)
            used += len(encoded)
        selected.reverse()
        return selected

    def _compact_payload(
        self,
        messages: Sequence[Message],
        *,
        phase: str,
        prompt_tokens: int,
    ) -> dict[str, object]:
        decision = self._decision_state()
        fixed = {
            "schema_version": 1,
            "phase": phase,
            "source_prompt_tokens": prompt_tokens,
            "decision_state": decision,
            "access": self._access_snapshot(),
            "probes": self._probe_snapshot(),
        }
        fixed_bytes = len(_canonical_bytes(fixed))
        tail_budget = max(0, self.compact_state_max_bytes - fixed_bytes - 256)
        payload = {
            **fixed,
            "recent_transcript": self._transcript_tail(messages, max_bytes=tail_budget),
        }
        encoded = _canonical_bytes(payload)
        if len(encoded) > self.compact_state_max_bytes:
            payload["recent_transcript"] = []
            encoded = _canonical_bytes(payload)
        if len(encoded) > self.compact_state_max_bytes:
            decision_payload = payload.get("decision_state")
            payload["decision_state"] = (
                {
                    "sha256": _sha256(_canonical_bytes(decision_payload)),
                    "decision": decision_payload.get("decision"),
                    "protocol": decision_payload.get("protocol"),
                }
                if isinstance(decision_payload, Mapping)
                else None
            )
            encoded = _canonical_bytes(payload)
        if len(encoded) > self.compact_state_max_bytes:
            raise TerminalReserveError("deterministic terminal state exceeds byte cap")
        return payload

    def _compact_messages(
        self,
        messages: Sequence[Message],
        *,
        phase: str,
        prompt_tokens: int,
    ) -> list[Message]:
        system = next((message for message in messages if message.role == Role.SYSTEM), None)
        if system is None:
            raise TerminalReserveError("terminal compaction requires a system message")
        payload = self._compact_payload(
            messages, phase=phase, prompt_tokens=prompt_tokens
        )
        encoded = _canonical_bytes(payload)
        allowed = (
            "Call decide_candidate exactly once with a contract-valid ABSTAIN object. "
            "The intervention window has closed, so ACT is forbidden: there is no "
            "remaining mutation or validation phase. No evidence, inspection, probe, "
            "mutation, or candidate-write tool is available. Do not invent missing evidence."
            if phase == "decision"
            else "A valid decision is already durably recorded. Call no tools and return "
            "the compact final JSON report required by the system contract."
        )
        instruction = (
            "TERMINAL RESERVE (hard, fail-closed):\n"
            f"{allowed}\n"
            "If the bounded state is insufficient, record a valid calibrated ABSTAIN; "
            "do not claim ACT. Invalid or missing output will remain invalid.\n\n"
            "BOUNDED TERMINAL STATE:\n"
            + encoded.decode("utf-8")
        )
        compacted = [system, Message.user(instruction)]
        self._last_compact = {
            "phase": phase,
            "bytes": len(encoded),
            "sha256": _sha256(encoded),
            "message_count": len(compacted),
        }
        return compacted

    def _attached_executor(self, agent_state: object) -> object:
        """Return NexAU's exact private executor attachment or fail closed."""

        try:
            executor = object.__getattribute__(agent_state, "_executor")
        except AttributeError as exc:
            raise TerminalReserveError(
                "agent state has no attached NexAU executor"
            ) from exc
        if executor is None:
            raise TerminalReserveError("agent state has no attached NexAU executor")
        if self._bound_executor is None:
            self._bound_executor = executor
        elif self._bound_executor is not executor:
            raise TerminalReserveError("attached NexAU executor identity changed")
        counter = getattr(executor, "token_counter", None)
        if counter is None or not callable(getattr(counter, "count_tokens", None)):
            raise TerminalReserveError("executor token counter is unavailable")
        if not hasattr(executor, "structured_tool_payload"):
            raise TerminalReserveError("executor structured tool payload is unavailable")
        return executor

    def _executor_tools(self, hook_input: BeforeModelHookInput) -> list[dict[str, Any]]:
        executor = self._attached_executor(hook_input.agent_state)
        return _normalize_tools(executor.structured_tool_payload)

    @staticmethod
    def _message_counts(messages: Sequence[Message]) -> dict[str, int]:
        assistant_turns = 0
        tool_uses = 0
        tool_results = 0
        for message in messages:
            if message.role == Role.ASSISTANT:
                assistant_turns += 1
            for block in message.content:
                if isinstance(block, ToolUseBlock):
                    tool_uses += 1
                elif isinstance(block, ToolResultBlock):
                    tool_results += 1
        return {
            "assistant_turn_count": assistant_turns,
            "tool_use_count": tool_uses,
            "tool_result_count": tool_results,
        }

    @staticmethod
    def _messages_sha256(messages: Sequence[Message]) -> str:
        digest = hashlib.sha256()
        for message in messages:
            dumper = getattr(message, "model_dump", None)
            if callable(dumper):
                value = dumper(mode="json", exclude_none=True)
            else:  # pragma: no cover - future Message compatibility.
                value = {
                    "role": message.role.value,
                    "content": [str(block) for block in message.content],
                }
            payload = _canonical_bytes(value)
            digest.update(len(payload).to_bytes(8, "big"))
            digest.update(payload)
        return digest.hexdigest()

    def _arm_model_guard(
        self,
        *,
        messages: Sequence[Message],
        prompt_tokens: int,
    ) -> None:
        self._model_guard = {
            "phase": self._phase,
            "messages_sha256": self._messages_sha256(messages),
            "prompt_tokens": prompt_tokens,
        }
        self._event(
            "model_guard_armed",
            phase=self._phase,
            messages_sha256=self._model_guard["messages_sha256"],
            prompt_tokens=prompt_tokens,
        )

    def _prompt_tokens(
        self,
        hook_input: BeforeModelHookInput,
        messages: Sequence[Message],
        tools: Sequence[object] | None = None,
    ) -> int:
        executor = self._attached_executor(hook_input.agent_state)
        counter = executor.token_counter
        normalized = _normalize_tools(tools) if tools is not None else self._executor_tools(hook_input)
        return int(counter.count_tokens(messages, tools=normalized))

    def _audit_payload(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "phase": self._phase,
            "activated": self._trigger is not None,
            "max_context_tokens": self.max_context_tokens,
            "terminal_reserve_tokens": self.terminal_reserve_tokens,
            "trigger_tokens": self.trigger_tokens,
            "terminal_output_tokens": self.terminal_output_tokens,
            "compact_state_max_bytes": self.compact_state_max_bytes,
            "max_terminal_model_calls": self.max_terminal_model_calls,
            "terminal_model_calls": self._terminal_model_calls,
            "blocked_tool_calls": dict(sorted(self._blocked_tool_calls.items())),
            "trigger": self._trigger,
            "last_compact": self._last_compact,
            "decision_state_present": self._decision_state() is not None,
            "requires_terminal_abstain": self._requires_terminal_abstain,
            "model_guard": self._model_guard,
            "candidate": self._candidate_snapshot(),
            "access": self._access_snapshot(),
            "events": self._events,
        }

    def _persist(self) -> None:
        payload = _canonical_bytes(self._audit_payload())
        if len(payload) > 256_000:
            raise TerminalReserveError("terminal audit exceeds bounded contract")
        path = self._audit_path()
        temporary = path.with_suffix(path.suffix + ".tmp")
        with temporary.open("wb") as handle:
            os.fchmod(handle.fileno(), 0o600)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)

    def _event(self, kind: str, **payload: object) -> None:
        self._events.append(
            {
                "sequence": len(self._events) + 1,
                "kind": kind,
                **payload,
            }
        )
        self._persist()

    def before_agent(self, hook_input: BeforeAgentHookInput) -> HookResult:
        with self._lock:
            self._record_full_trace(hook_input.agent_state, hook_input.messages)
            self._initial_candidate_sha256 = self._candidate_sha256()
            self._event(
                "before_agent",
                candidate_sha256=self._initial_candidate_sha256,
            )
            return HookResult.no_changes()

    def before_model(self, hook_input: BeforeModelHookInput) -> HookResult:
        with self._lock:
            self._record_full_trace(hook_input.agent_state, hook_input.messages)
            tools = self._executor_tools(hook_input)
            prompt_tokens = self._prompt_tokens(
                hook_input, hook_input.messages, tools
            )
            access = self._access_snapshot()
            message_counts = self._message_counts(hook_input.messages)
            self._event(
                "pre_model",
                iteration=hook_input.current_iteration,
                phase=self._phase,
                prompt_tokens=prompt_tokens,
                message_count=len(hook_input.messages),
                access_record_count=access["record_count"],
                access_bytes_returned=access["bytes_returned"],
                **message_counts,
            )
            if self._phase == "explore" and prompt_tokens < self.trigger_tokens:
                self._arm_model_guard(
                    messages=hook_input.messages,
                    prompt_tokens=prompt_tokens,
                )
                return HookResult.no_changes()

            if self._phase == "explore":
                self._phase = self._terminal_phase()
                self._trigger = {
                    "iteration": hook_input.current_iteration,
                    "prompt_tokens": prompt_tokens,
                    "access_record_count": access["record_count"],
                    "access_bytes_returned": access["bytes_returned"],
                }

            compacted = self._compact_messages(
                hook_input.messages,
                phase=self._phase,
                prompt_tokens=prompt_tokens,
            )
            compacted_tokens = self._prompt_tokens(hook_input, compacted, tools)
            if compacted_tokens + self.terminal_output_tokens > self.max_context_tokens:
                raise TerminalReserveError(
                    "terminal compact state does not leave the guaranteed output budget"
                )
            self._event(
                "terminal_compaction",
                iteration=hook_input.current_iteration,
                phase=self._phase,
                pre_prompt_tokens=prompt_tokens,
                post_prompt_tokens=compacted_tokens,
                compact_state_bytes=self._last_compact["bytes"] if self._last_compact else None,
                compact_state_sha256=self._last_compact["sha256"] if self._last_compact else None,
            )
            self._arm_model_guard(
                messages=compacted,
                prompt_tokens=compacted_tokens,
            )
            return HookResult.with_modifications(messages=compacted)

    def wrap_model_call(
        self, params: ModelCallParams, call_next: ModelCallFn
    ) -> object:
        with self._lock:
            guard = self._model_guard
            if guard is None:
                raise TerminalReserveError(
                    "model call has no successful before-model audit guard"
                )
            messages_sha256 = self._messages_sha256(params.messages)
            if (
                guard.get("phase") != self._phase
                or guard.get("messages_sha256") != messages_sha256
            ):
                raise TerminalReserveError(
                    "model call differs from its before-model audit guard"
                )
            all_tools = _normalize_tools(params.tools)
            executor = self._attached_executor(params.agent_state)
            counter = executor.token_counter
            guarded_prompt_tokens = int(
                counter.count_tokens(params.messages, tools=all_tools)
            )
            if guard.get("prompt_tokens") != guarded_prompt_tokens:
                raise TerminalReserveError(
                    "model prompt tokens differ from before-model audit guard"
                )
            self._model_guard = None
            self._event(
                "model_guard_consumed",
                phase=self._phase,
                messages_sha256=messages_sha256,
                prompt_tokens=guarded_prompt_tokens,
            )
            if self._phase == "explore":
                if guarded_prompt_tokens >= self.trigger_tokens:
                    raise TerminalReserveError(
                        "pre-model terminal transition did not compact a threshold prompt"
                    )
                return call_next(params)
            if self._terminal_model_calls >= self.max_terminal_model_calls:
                raise TerminalReserveError("terminal model-call budget exhausted")
            allowed_tools = (
                [tool for tool in all_tools if _tool_name(tool) == _ALLOWED_TERMINAL_TOOL]
                if self._phase == "decision"
                else []
            )
            if self._phase == "decision" and len(allowed_tools) != 1:
                raise TerminalReserveError("exact decide_candidate tool is unavailable")
            api_params = dict(params.api_params)
            api_params["max_tokens"] = self.terminal_output_tokens
            if params.tool_call_mode == "openai":
                if allowed_tools:
                    api_params["tools"] = allowed_tools
                    api_params["tool_choice"] = "auto"
                else:
                    api_params.pop("tools", None)
                    api_params.pop("tool_choice", None)
            normalized_tools = allowed_tools or None
            prompt_tokens = int(
                counter.count_tokens(params.messages, tools=normalized_tools)
            )
            if prompt_tokens + self.terminal_output_tokens > self.max_context_tokens:
                raise TerminalReserveError("terminal call cannot guarantee output budget")
            self._terminal_model_calls += 1
            self._event(
                "terminal_model_call",
                phase=self._phase,
                call_index=self._terminal_model_calls,
                prompt_tokens=prompt_tokens,
                output_budget_tokens=self.terminal_output_tokens,
                allowed_tools=[name for name in map(_tool_name, allowed_tools) if name],
            )
            bounded = replace(
                params,
                max_tokens=self.terminal_output_tokens,
                tools=cast(Any, allowed_tools),
                api_params=api_params,
            )
        return call_next(bounded)

    def wrap_tool_call(
        self, params: ToolCallParams, call_next: ToolCallFn
    ) -> object:
        with self._lock:
            if self._phase == "explore":
                return call_next(params)
            if self._phase == "decision" and params.tool_name == _ALLOWED_TERMINAL_TOOL:
                discovery = params.parameters.get("discovery")
                decision = (
                    str(discovery.get("decision", "")).upper()
                    if isinstance(discovery, Mapping)
                    else ""
                )
                if decision == "ABSTAIN":
                    return call_next(params)
                self._blocked_tool_calls["decide_candidate:non_abstain"] += 1
                self._event(
                    "blocked_terminal_decision",
                    phase=self._phase,
                    requested_decision=decision or None,
                )
                return {
                    "error": "terminal reserve permits only a contract-valid ABSTAIN; ACT has no remaining intervention phase",
                    "tool_blocked": True,
                }
            self._blocked_tool_calls[params.tool_name] += 1
            self._event(
                "blocked_terminal_tool",
                phase=self._phase,
                tool_name=params.tool_name,
            )
            return {
                "error": "terminal reserve permits only a contract-valid decide_candidate call",
                "tool_blocked": True,
            }

    def after_tool(self, hook_input: AfterToolHookInput) -> HookResult:
        with self._lock:
            try:
                rendered = json.dumps(
                    hook_input.tool_output,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                )
            except (TypeError, ValueError):
                rendered = str(hook_input.tool_output)
            self._event(
                "tool_event",
                phase=self._phase,
                tool_name=hook_input.tool_name,
                output_bytes=len(rendered.encode("utf-8")),
            )
            if self._phase != "decision" or hook_input.tool_name != _ALLOWED_TERMINAL_TOOL:
                return HookResult.no_changes()
            state = self._decision_state()
            if state is not None:
                self._phase = "final"
                self._event(
                    "decision_recorded",
                    decision=state["decision"],
                    protocol=state["protocol"],
                    state_sha256=_sha256(_canonical_bytes(state)),
                )
            else:
                self._event("decision_not_recorded")
            return HookResult.no_changes()

    def after_model(self, hook_input: AfterModelHookInput) -> HookResult:
        with self._lock:
            self._record_full_trace(hook_input.agent_state, hook_input.messages)
            usage = _usage_tokens(
                getattr(hook_input.model_response, "usage", None)
            )
            self._event(
                "post_model",
                iteration=hook_input.current_iteration,
                phase=self._phase,
                response_bytes=len(hook_input.original_response.encode("utf-8")),
                reported_input_tokens=usage["input_tokens"],
                reported_output_tokens=usage["output_tokens"],
                reported_total_tokens=usage["total_tokens"],
            )
            return HookResult.no_changes()

    def after_agent(self, hook_input: AfterAgentHookInput) -> HookResult:
        with self._lock:
            self._record_full_trace(hook_input.agent_state, hook_input.messages)
            decision = self._decision_state()
            if self._trigger is not None:
                valid_terminal_decision = decision is not None and (
                    not self._requires_terminal_abstain
                    or decision.get("decision") == "ABSTAIN"
                )
                self._phase = "complete" if valid_terminal_decision else "invalid"
            self._event(
                "after_agent",
                phase=self._phase,
                stop_reason=(
                    getattr(hook_input.stop_reason, "name", None)
                    if hook_input.stop_reason is not None
                    else None
                ),
                response_bytes=len(hook_input.agent_response.encode("utf-8")),
                response_sha256=_sha256(hook_input.agent_response.encode("utf-8")),
                decision=(decision.get("decision") if decision is not None else None),
            )
            return HookResult.no_changes()


__all__ = ["DiscoveryTerminalReserve", "TerminalReserveError"]
