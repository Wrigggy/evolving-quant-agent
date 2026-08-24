"""Entry point uploaded into a QFBench E2B sandbox to run NexAU in-process."""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys
import time
from collections.abc import Mapping
from pathlib import Path


_MIN_MODEL_CLIENT_TIMEOUT_SECONDS = 360.0
_EMPTY_MODEL_RESPONSE = "No response content or tool calls"
_EMPTY_MODEL_EXECUTION_ERROR = f"Error in agent execution: {_EMPTY_MODEL_RESPONSE}"
_REUSABLE_HARNESS_CONTRACT = (
    "- Complete this public task through reusable quantitative-research "
    "behavior, not a benchmark-specific answer patch.\n"
    "- Task-specific rules are allowed when the public instruction, supplied "
    "public data, or a predeclared public reference states them. Do not infer "
    "or encode hidden checker behavior, reference answers, expected outputs, "
    "official property identities, prior scores, or unstated benchmark "
    "constants.\n"
)


def _stage_repair_seed(work_dir: Path, output_dir: Path) -> bool:
    """Prestage the optional repair-probe seed at the promised output path."""

    source = work_dir / "data" / "probe_seed_strategy.py"
    target = output_dir / "strategy.py"
    if not source.is_file() or target.exists():
        return False
    shutil.copy2(source, target)
    return True


def _pin_no_replay_policy(config) -> None:
    """Force one SDK call per NexAU model turn, including sub-agent configs."""

    pending = [config]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        llm_config = getattr(current, "llm_config", None)
        if llm_config is None or not callable(
            getattr(llm_config, "to_client_kwargs", None)
        ):
            raise RuntimeError("NexAU no-replay policy requires an LLM config")

        current.retry_attempts = 1
        llm_config.max_retries = 0
        timeout = getattr(llm_config, "timeout", None)
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout)
            or timeout <= 0
        ):
            timeout = _MIN_MODEL_CLIENT_TIMEOUT_SECONDS
        llm_config.timeout = max(
            float(timeout), _MIN_MODEL_CLIENT_TIMEOUT_SECONDS
        )

        original_client_kwargs = llm_config.to_client_kwargs

        def exact_client_kwargs(
            original_client_kwargs=original_client_kwargs,
            llm_config=llm_config,
        ):
            kwargs = dict(original_client_kwargs())
            # NexAU 0.3.9 drops falsy zero and otherwise restores the OpenAI
            # SDK retry default. Insert the research contract explicitly.
            kwargs["max_retries"] = 0
            kwargs["timeout"] = llm_config.timeout
            return kwargs

        llm_config.to_client_kwargs = exact_client_kwargs
        sub_agents = getattr(current, "sub_agents", None) or {}
        if not isinstance(sub_agents, Mapping):
            raise RuntimeError("NexAU sub-agent config is not a mapping")
        pending.extend(sub_agents.values())


def _verify_no_replay_client(agent) -> None:
    client = getattr(agent, "openai_client", None)
    if type(getattr(client, "max_retries", None)) is not int or (
        client.max_retries != 0
    ):
        raise RuntimeError("NexAU model client retry policy drifted")


def _redact(text: str) -> str:
    scrubbed = text
    for name, value in os.environ.items():
        if value and any(marker in name.upper() for marker in ("KEY", "TOKEN", "SECRET")):
            scrubbed = scrubbed.replace(value, "[REDACTED]")
    return scrubbed


def _redact_value(value):
    """Apply the existing secret redaction recursively to trace metadata."""

    if isinstance(value, str):
        return _redact(value)
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, tuple):
        return [_redact_value(item) for item in value]
    if isinstance(value, Mapping):
        return {
            str(key): _redact_value(item)
            for key, item in value.items()
        }
    return value


def _message_text(message) -> str:
    text = ""
    try:
        text = message.get_text_content()
    except Exception:  # noqa: BLE001
        text = str(getattr(message, "content", "") or "")
    structured: list[str] = []
    for block in getattr(message, "content", ()) or ():
        block_type = str(getattr(block, "type", ""))
        if block_type == "tool_use":
            name = str(getattr(block, "name", "") or "")
            tool_input = getattr(block, "input", {})
            structured.append(
                "<ToolUse>"
                + json.dumps(
                    {"name": name, "input": tool_input},
                    sort_keys=True,
                    ensure_ascii=False,
                    default=str,
                )
                + "</ToolUse>"
            )
        elif block_type == "tool_result":
            result = getattr(block, "content", "")
            if isinstance(result, str):
                structured.append(result)
            elif isinstance(result, list):
                structured.append(
                    "".join(
                        str(getattr(part, "text", "") or "")
                        for part in result
                    )
                )
    return "\n".join(part for part in (text, *structured) if part)


def _structured_message_fields(message) -> dict[str, object]:
    """Preserve genuine NexAU tool blocks without inferring them from prose."""

    tool_calls: list[dict[str, object]] = []
    tool_results: list[dict[str, object]] = []
    for block in getattr(message, "content", ()) or ():
        block_type = str(getattr(block, "type", ""))
        if block_type == "tool_use":
            tool_calls.append(
                {
                    "id": _redact(str(getattr(block, "id", "") or "")),
                    "name": _redact(str(getattr(block, "name", "") or "")),
                    "input": _redact_value(getattr(block, "input", {})),
                }
            )
        elif block_type == "tool_result":
            tool_results.append(
                {
                    "tool_use_id": _redact(
                        str(getattr(block, "tool_use_id", "") or "")
                    ),
                    "is_error": bool(getattr(block, "is_error", False)),
                }
            )
    fields: dict[str, object] = {}
    if tool_calls:
        fields["structured_tool_calls"] = tool_calls
    if tool_results:
        fields["structured_tool_results"] = tool_results
    return fields


def _role_name(message) -> str:
    role = getattr(message, "role", "")
    return str(getattr(role, "value", role) or "")


def _is_empty_model_response_error(exc: BaseException) -> bool:
    """Recognize the pinned NexAU 0.3.9 empty-turn exception chain only."""

    if type(exc) is not RuntimeError or str(exc) != _EMPTY_MODEL_EXECUTION_ERROR:
        return False
    cause = exc.__cause__
    return type(cause) is Exception and str(cause) == _EMPTY_MODEL_RESPONSE


def run(task_dir: Path, worker_dir: Path, work_dir: Path, output_dir: Path, result_dir: Path) -> int:
    from nexau import Agent, AgentConfig

    started = time.time()
    output_dir.mkdir(parents=True, exist_ok=True)
    result_dir.mkdir(parents=True, exist_ok=True)
    _stage_repair_seed(work_dir, output_dir)
    worker_dir = worker_dir.resolve()
    if str(worker_dir) not in sys.path:
        sys.path.insert(0, str(worker_dir))
    config = AgentConfig.from_yaml(config_path=worker_dir / "agent.yaml")
    _pin_no_replay_policy(config)
    for name in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
        os.environ.pop(name, None)
    agent = Agent(config=config)
    _verify_no_replay_client(agent)
    try:
        agent.sandbox_manager.instance.work_dir = work_dir
    except Exception:  # noqa: BLE001
        pass

    instruction = (task_dir / "instruction.md").read_text()
    message = (
        instruction
        + "\n\nRUNTIME CONTRACT:\n"
        + f"- Work only inside {work_dir}.\n"
        + f"- Public input data is under {work_dir / 'data'}.\n"
        + f"- Save every requested deliverable under {output_dir}.\n"
        + "- Do not search for tests, solutions, reference answers, or credentials.\n"
        + _REUSABLE_HARNESS_CONTRACT
    )
    context = {
        "date": os.environ.get("QEA_EVAL_DATE", "2026-07-23"),
        "username": "qea-worker",
        "working_directory": str(work_dir),
    }
    context["env_content"] = dict(context)
    outcome = "completed"
    try:
        response = agent.run(message=message, context=context)
    except RuntimeError as exc:
        if not _is_empty_model_response_error(exc):
            raise
        # This is a consumed stochastic sample, not a transport retry. Preserve
        # any artifacts and trace produced before the empty turn so the
        # independent official verifier can score the attempt normally.
        response = ""
        outcome = "model_empty_response"
    final_text = response if isinstance(response, str) else (response[0] if response else "")
    (result_dir / "final.txt").write_text(_redact(str(final_text)))

    turns = tool_calls = tool_errors = 0
    trace_path = result_dir / "raw_trace.jsonl"
    with trace_path.open("w") as trace:
        for item in agent.full_trace or ():
            role = _role_name(item)
            text = _redact(_message_text(item))
            record = {"role": role, "content": text}
            record.update(_structured_message_fields(item))
            trace.write(json.dumps(record, ensure_ascii=False) + "\n")
            if role == "assistant":
                turns += 1
            elif role not in {"", "user"}:
                tool_calls += 1
                if any(marker in text.lower() for marker in ("error", "failed", "traceback")):
                    tool_errors += 1
    files = sum(1 for path in output_dir.rglob("*") if path.is_file())
    (result_dir / "summary.json").write_text(json.dumps({
        "outcome": outcome,
        "turns": turns,
        "tool_calls": tool_calls,
        "tool_errors": tool_errors,
        "files": files,
        "secs": round(time.time() - started, 3),
    }, sort_keys=True) + "\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-dir", type=Path, required=True)
    parser.add_argument("--worker-dir", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--result-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    return run(args.task_dir, args.worker_dir, args.work_dir, args.output_dir, args.result_dir)


if __name__ == "__main__":
    raise SystemExit(main())
