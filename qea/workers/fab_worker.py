"""FAB v2 worker: a Stirrup agent equipped with the free-backend research tools
(EDGAR / filings / fetch / price / web search). No E2B sandbox — FAB is research +
reasoning that produces a TEXT answer. Returns the agent's final answer string.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

from .fab_tools import fab_tools
from .stirrup_worker import _extract_final_text

_SYSTEM = (
    "You are an entry-level financial analyst answering a question about public "
    "companies and their SEC filings. Use the provided tools to find the relevant "
    "filings/data and read them (use retrieve_from_filing to read specific topics in "
    "large 10-K/10-Q documents).\n\n"
    "CRITICAL — how to finish: when you call the finish tool, the `reason` field MUST "
    "contain your COMPLETE final written answer — the full analysis with the specific "
    "facts, figures, product names, and risks you found, each supported by the filing. "
    "Do NOT put a status note like 'analysis complete' or 'all disclosures cited'; that "
    "scores zero. The text you put in `reason` IS your graded answer, so write the entire "
    "answer there, in full."
)


class FabWorker:
    def __init__(self, *, out_root: str = "output/fab", max_turns: int | None = None,
                 model: str | None = None) -> None:
        self.out_root = Path(out_root)
        self.max_turns = max_turns or int(os.environ.get("QEA_FAB_MAX_TURNS", "30"))
        self.model = model or os.environ.get("QEA_QUANT_AGENT_MODEL", "deepseek/deepseek-v4-pro")
        os.environ.setdefault("OPENAI_API_KEY", os.environ.get("OPENROUTER_API_KEY", ""))

    def run_task(self, task) -> str:
        return asyncio.run(self.arun_task(task))

    async def arun_task(self, task) -> str:
        from stirrup import Agent
        from stirrup.clients.chat_completions_client import ChatCompletionsClient

        out_dir = self.out_root / str(task.task_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        client = ChatCompletionsClient(
            base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            model=self.model,
            max_retries=int(os.environ.get("QEA_LLM_MAX_RETRIES", "6")),
        )
        agent = Agent(client=client, name="fab", tools=fab_tools(),
                      max_turns=self.max_turns, system_prompt=_SYSTEM,
                      turns_remaining_warning_threshold=6)  # nudge it to finish before cutoff
        async with agent.session(output_dir=str(out_dir)) as session:
            finish_params, history, _meta = await session.run(task.prompt)
        return _extract_final_text(finish_params, history)
