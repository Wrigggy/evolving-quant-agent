"""Entry point uploaded into a QFBench E2B sandbox to run NexAU in-process."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path


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
    for name in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
        os.environ.pop(name, None)
    agent = Agent(config=config)
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
