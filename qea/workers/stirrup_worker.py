"""Vanilla Stirrup agentic worker on an E2B sandbox.

run_task(task) runs an out-of-box Stirrup Agent (default code_exec on E2B, finish
tool) on the task prompt, then returns the agent's final text + every file the
agent produced (auto-downloaded by Stirrup to the per-task output_dir). No QEA
7-slot harness is injected -- this measures the BASE substrate.
"""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Deliverable:
    task_id: str
    final_text: str
    files: list  # list[Path]


class StubWorker:
    """Offline test double: returns a canned deliverable; no network."""
    def __init__(self, final_text: str, files) -> None:
        self._final_text = final_text
        self._files = list(files)

    def run_task(self, task) -> Deliverable:
        return Deliverable(task.task_id, self._final_text, self._files)


def _extract_final_text(finish_params, history) -> str:
    """Defensive: pull the agent's final message across plausible Stirrup shapes.
    Refine to the exact shape recorded in the Task 1 spike comment."""
    fp = finish_params
    if isinstance(fp, dict):
        for key in ("final_message", "message", "summary", "response", "text"):
            if fp.get(key):
                return str(fp[key])
    for attr in ("final_message", "message", "summary", "response", "text"):
        if hasattr(fp, attr) and getattr(fp, attr):
            return str(getattr(fp, attr))
    if history:
        last = history[-1]
        if isinstance(last, dict):
            return str(last.get("content", last))
        return str(getattr(last, "content", last))
    return ""


class StirrupWorker:
    def __init__(self, *, out_root: str = "output/stirrup", max_turns: int | None = None,
                 model: str | None = None, template: str = "code-interpreter-v1") -> None:
        self.out_root = Path(out_root)
        self.max_turns = max_turns or int(os.environ.get("QEA_STIRRUP_MAX_TURNS", "20"))
        self.model = model or os.environ.get("QEA_QUANT_AGENT_MODEL", "deepseek/deepseek-v4-pro")
        self.template = template
        # Stirrup's ChatCompletionsClient may read OPENAI_API_KEY; mirror the key.
        os.environ.setdefault("OPENAI_API_KEY", os.environ.get("OPENROUTER_API_KEY", ""))

    def run_task(self, task) -> Deliverable:
        return asyncio.run(self._run(task))

    async def _run(self, task) -> Deliverable:
        from stirrup import Agent
        from stirrup.clients.chat_completions_client import ChatCompletionsClient
        from stirrup.tools.code_backends.e2b import E2BCodeExecToolProvider

        out_dir = self.out_root / str(task.task_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        client = ChatCompletionsClient(
            base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            model=self.model,
        )
        code_exec = E2BCodeExecToolProvider(template=self.template)
        agent = Agent(client=client, name="qea-base", tools=[code_exec], max_turns=self.max_turns)
        async with agent.session(output_dir=str(out_dir)) as session:
            finish_params, history, _metadata = await session.run(task.prompt)
        files = [p for p in out_dir.rglob("*") if p.is_file()]
        return Deliverable(str(task.task_id), _extract_final_text(finish_params, history), files)
