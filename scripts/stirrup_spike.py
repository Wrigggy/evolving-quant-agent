"""One-off spike: pin Stirrup's E2B run shapes (finish_params/metadata/output files).

Run once after install; read the printed output and confirm
qea/workers/stirrup_worker.py (_extract_final_text + auth env) match. Not imported
by anything; safe to keep or delete.

FINDINGS (2026-06-21 first run, deepseek-v4-pro):
- auth env       : Stirrup's ChatCompletionsClient reads OPENAI_API_KEY -> mirror
                   OPENROUTER_API_KEY into it (worker does os.environ.setdefault).
- finish_params  : stirrup.tools.finish.FinishParams(reason=str, paths=[relnames]).
                   Final text = finish_params.reason. (history[-1] is a message LIST.)
- output files   : auto-downloaded by session.run to output_dir (report.xlsx appeared).
"""
import asyncio, os, json
from pathlib import Path


def load_dotenv(path=".env"):  # no-dep loader (repo convention)
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_dotenv()
# Stirrup's ChatCompletionsClient may read OPENAI_API_KEY rather than OPENROUTER_API_KEY.
os.environ.setdefault("OPENAI_API_KEY", os.environ.get("OPENROUTER_API_KEY", ""))

from stirrup import Agent
from stirrup.clients.chat_completions_client import ChatCompletionsClient
from stirrup.tools.code_backends.e2b import E2BCodeExecToolProvider


async def main() -> None:
    out_dir = Path("output/stirrup_spike")
    client = ChatCompletionsClient(
        base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        model=os.environ.get("QEA_QUANT_AGENT_MODEL", "deepseek/deepseek-v4-pro"),
    )
    code_exec = E2BCodeExecToolProvider(template="code-interpreter-v1")
    agent = Agent(client=client, name="spike", tools=[code_exec], max_turns=8)
    async with agent.session(output_dir=str(out_dir)) as session:
        finish_params, history, metadata = await session.run(
            "Create a 2-sheet Excel file report.xlsx with openpyxl: sheet 'A' cell A1='hello', "
            "sheet 'B' cell A1=42. Save it. Then reply with one sentence confirming you saved it."
        )
    print("=== finish_params ===", type(finish_params), repr(finish_params)[:2000])
    print("=== metadata ===", type(metadata), repr(metadata)[:2000])
    print("=== history len ===", len(history), "last:", repr(history[-1])[:1000] if history else None)
    print("=== output files ===", [str(p) for p in out_dir.rglob("*") if p.is_file()])


if __name__ == "__main__":
    asyncio.run(main())
