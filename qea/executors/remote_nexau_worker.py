"""Entry point uploaded into a QFBench E2B sandbox to run NexAU in-process."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from collections.abc import Mapping
from pathlib import Path


_MIN_MODEL_CLIENT_TIMEOUT_SECONDS = 360.0


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


def _message_text(message) -> str:
    try:
        return message.get_text_content()
    except Exception:  # noqa: BLE001
        return str(getattr(message, "content", "") or "")


def run(task_dir: Path, worker_dir: Path, work_dir: Path, output_dir: Path, result_dir: Path) -> int:
    from nexau import Agent, AgentConfig

    started = time.time()
    output_dir.mkdir(parents=True, exist_ok=True)
    result_dir.mkdir(parents=True, exist_ok=True)
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
    )
    context = {
        "date": os.environ.get("QEA_EVAL_DATE", "2026-07-23"),
        "username": "qea-worker",
        "working_directory": str(work_dir),
    }
    context["env_content"] = dict(context)
    response = agent.run(message=message, context=context)
    final_text = response if isinstance(response, str) else (response[0] if response else "")
    (result_dir / "final.txt").write_text(_redact(str(final_text)))

    turns = tool_calls = tool_errors = 0
    trace_path = result_dir / "raw_trace.jsonl"
    with trace_path.open("w") as trace:
        for item in agent.full_trace or ():
            role = str(getattr(item, "role", ""))
            text = _redact(_message_text(item))
            trace.write(json.dumps({"role": role, "content": text}, ensure_ascii=False) + "\n")
            if role == "assistant":
                turns += 1
            elif role not in {"", "user"}:
                tool_calls += 1
                if any(marker in text.lower() for marker in ("error", "failed", "traceback")):
                    tool_errors += 1
    files = sum(1 for path in output_dir.rglob("*") if path.is_file())
    (result_dir / "summary.json").write_text(json.dumps({
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
