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


def _extract_final_text(finish_params, history) -> str:  # noqa: ARG001
    """Pull the agent's final text. Spike-confirmed shape: Stirrup returns a
    ``FinishParams(reason=..., paths=[...])`` object; ``reason`` is the final
    message. Fallbacks kept defensive in case the finish tool schema changes."""
    fp = finish_params
    reason = getattr(fp, "reason", None)
    if reason:
        return str(reason)
    if isinstance(fp, dict):
        for key in ("reason", "final_message", "message", "summary", "response", "text"):
            if fp.get(key):
                return str(fp[key])
    for attr in ("final_message", "message", "summary", "response", "text"):
        if getattr(fp, attr, None):
            return str(getattr(fp, attr))
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
        """Sync wrapper. For concurrent runs use ``await arun_task`` directly."""
        return asyncio.run(self.arun_task(task))

    async def arun_task(self, task) -> Deliverable:
        from stirrup import Agent
        from stirrup.clients.chat_completions_client import ChatCompletionsClient

        from .e2b_reconnect import ReconnectingE2BCodeExecToolProvider

        out_dir = self.out_root / str(task.task_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        client = ChatCompletionsClient(
            base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            model=self.model,
            # Transport-level retries of a SINGLE failed call (flaky SOCKS proxy ->
            # "Server disconnected"). This recovers the one output; it is NOT a
            # whole-task re-roll / best-of-N (the conversation is unchanged).
            max_retries=int(os.environ.get("QEA_LLM_MAX_RETRIES", "6")),
        )
        # Reconnecting provider: an E2B disconnect retries the sandbox command only
        # (LLM untouched -> single output attempt). Tunable via QEA_E2B_RECONNECT_TRIES.
        code_exec = ReconnectingE2BCodeExecToolProvider(
            template=self.template,
            reconnect_tries=int(os.environ.get("QEA_E2B_RECONNECT_TRIES", "4")),
            reconnect_backoff=float(os.environ.get("QEA_BACKOFF_BASE_SEC", "2.0")),
        )
        agent = Agent(client=client, name="qea-base", tools=[code_exec], max_turns=self.max_turns)
        # GDPval ships reference INPUT files; upload them so the agent uses real
        # inputs instead of improvising (Stirrup lists them in the system prompt).
        ref_files = [str(p) for p in getattr(task, "reference_files", None) or []
                     if Path(p).exists()]
        sess_kwargs: dict = {"output_dir": str(out_dir)}
        if ref_files:
            sess_kwargs["input_files"] = ref_files
        async with agent.session(**sess_kwargs) as session:
            finish_params, history, _metadata = await session.run(task.prompt)
        files = [p for p in out_dir.rglob("*") if p.is_file()]
        return Deliverable(str(task.task_id), _extract_final_text(finish_params, history), files)
