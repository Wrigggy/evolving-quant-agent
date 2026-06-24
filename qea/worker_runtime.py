"""Reusable NexAU worker invocation for both the base test and the Level-B loop.

Lifted from scripts/nexau_gdpval_run.py (run_task / _trace_summary) so the loop
runs the SAME real worker we base-tested at mean multimodal 0.797 — not a legacy
single-completion. Returns the deliverable text, the produced deliverable files,
and an answer-free trace summary (tool_calls / tool_errors / turns / secs).
"""
from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

SUPPORTED = {".xlsx", ".pptx", ".docx", ".pdf"}


@dataclass
class WorkerRun:
    deliverable_text: str
    produced_files: list = field(default_factory=list)
    trace: dict = field(default_factory=dict)


def summarize_trace(agent) -> dict:
    """Answer-free monitoring from the NexAU trace. A message has no tool_calls
    field (tool activity is in content/role), so count by role: assistant turns +
    tool-result messages (proxy for tool calls) + error markers in tool results."""
    turns = tool_results = tool_errors = 0
    try:
        for m in (agent.full_trace or []):
            role = getattr(m, "role", "")
            try:
                text = m.get_text_content()
            except Exception:  # noqa: BLE001
                text = str(getattr(m, "content", "") or "")
            if role == "assistant":
                turns += 1
            elif role in ("tool", "tool_result", "function", "user") and text:
                if role != "user":
                    tool_results += 1
                if any(k in text for k in ("Error", "❌", "failed", "Traceback", "Invalid parameters")):
                    tool_errors += 1
    except Exception:  # noqa: BLE001
        pass
    return {"tool_calls": tool_results, "tool_errors": tool_errors, "turns": turns}


def run_worker(task, worker_dir: Path, run_dir: Path) -> WorkerRun:
    """Run the NexAU worker (the agent dir at worker_dir) on one task in an isolated
    per-task workdir under run_dir. Copies the task reference files in, pins the
    sandbox cwd, captures produced deliverable files (before/after diff) + trace."""
    from nexau import Agent, AgentConfig
    t0 = time.time()
    worker_dir, run_dir = Path(worker_dir), Path(run_dir)
    workdir = run_dir / str(task.task_id) / "work"
    workdir.mkdir(parents=True, exist_ok=True)
    ref_names = set()
    for rf in (getattr(task, "reference_files", None) or []):
        rf = Path(rf)
        if rf.exists():
            shutil.copy(rf, workdir / rf.name)
            ref_names.add(rf.name)
    pre = {p for p in workdir.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED}

    cfg = AgentConfig.from_yaml(config_path=worker_dir / "agent.yaml")
    agent = Agent(config=cfg)
    try:
        agent.sandbox_manager.instance.work_dir = workdir
    except Exception:  # noqa: BLE001
        pass
    note = (f"\n\nIMPORTANT: Your working directory is {workdir}\n"
            f"The reference input files {sorted(ref_names)} are in that directory. "
            f"Read inputs from there, and SAVE your deliverable file(s) into that directory.")
    ctx = {"date": "2026-06-25", "username": os.environ.get("USER", "kevin"),
           "working_directory": str(workdir)}
    ctx["env_content"] = dict(ctx)
    resp = agent.run(message=task.prompt + note, context=ctx)
    final_text = resp if isinstance(resp, str) else resp[0]

    produced = [p for p in workdir.rglob("*")
                if p.is_file() and p.suffix.lower() in SUPPORTED
                and p not in pre and p.name not in ref_names]
    produced = sorted(produced, key=lambda p: p.stat().st_mtime, reverse=True)[:12]
    trace = summarize_trace(agent)
    trace["secs"] = round(time.time() - t0, 1)
    trace["files"] = len(produced)
    return WorkerRun(final_text, produced, trace)
