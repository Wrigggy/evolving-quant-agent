"""Reusable NexAU worker invocation for both the base test and the Level-B loop.

Lifted from scripts/nexau_gdpval_run.py (run_task / _trace_summary) so the loop
runs the SAME real worker we base-tested at mean multimodal 0.797 — not a legacy
single-completion. Returns the deliverable text, the produced deliverable files,
and an answer-free trace summary (tool_calls / tool_errors / turns / secs).
"""
from __future__ import annotations

import os
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

SUPPORTED = {".xlsx", ".pptx", ".docx", ".pdf"}


def ensure_nexau_llm_env() -> None:
    """The NexAU agent.yaml resolves ${env.LLM_API_KEY|LLM_BASE_URL|LLM_MODEL} at
    config load. Map them from OPENROUTER_* (matching scripts/nexau_gdpval_run.py)
    so any caller of the NexAU runtime — base test OR Level-B loop — is covered.
    Only overrides LLM_API_KEY when OPENROUTER_API_KEY is present, so offline tests
    that set a dummy LLM_API_KEY are left untouched."""
    if os.environ.get("OPENROUTER_API_KEY"):
        os.environ["LLM_API_KEY"] = os.environ["OPENROUTER_API_KEY"]
    os.environ.setdefault("LLM_BASE_URL", os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"))
    os.environ.setdefault("LLM_MODEL", "deepseek/deepseek-v4-pro")


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
            # NexAU roles are an enum (Role.ASSISTANT/Role.TOOL/...); normalize to a
            # lowercase leaf string so counts work for BOTH the enum and plain strings.
            role = str(getattr(role, "value", role)).split(".")[-1].lower()
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
    ensure_nexau_llm_env()
    t0 = time.time()
    worker_dir, run_dir = Path(worker_dir), Path(run_dir)
    # FAB-style workers bind tools by RELATIVE module path (e.g. tools.fab.research:fn),
    # so the worker dir (each per-iteration snapshot) must be importable. Put it first
    # on sys.path and drop any cached `tools.*` modules so an edited snapshot's tool
    # code reloads instead of resolving to a previously-cached version.
    wd = str(worker_dir)
    if wd in sys.path:
        sys.path.remove(wd)
    sys.path.insert(0, wd)
    for m in [name for name in sys.modules if name == "tools" or name.startswith("tools.")]:
        del sys.modules[m]
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
    # Only file-deliverable tasks (reference files in, or a required deliverable
    # extension) get the file-saving note; text-answer benchmarks like FAB get the
    # bare prompt, matching their base test. Keyed to the task, not the benchmark name.
    is_file_task = bool(ref_names) or bool(getattr(task, "deliverable_exts", None))
    note = ((f"\n\nIMPORTANT: Your working directory is {workdir}\n"
             f"The reference input files {sorted(ref_names)} are in that directory. "
             f"Read inputs from there, and SAVE your deliverable file(s) into that directory.")
            if is_file_task else "")
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
    # Dump the full trajectory (capped) for the AHE-corpus evidence drill-down path.
    trace_path = workdir.parent / "trace.txt"
    try:
        msgs = []
        for m in (agent.full_trace or []):
            role = getattr(m, "role", "")
            try:
                txt = m.get_text_content()
            except Exception:  # noqa: BLE001
                txt = str(getattr(m, "content", "") or "")
            msgs.append(f"[{role}] {txt}")
        trace_path.write_text("\n\n".join(msgs)[:200000])
        trace["trace_path"] = str(trace_path)
    except Exception:  # noqa: BLE001
        trace["trace_path"] = ""
    return WorkerRun(final_text, produced, trace)
