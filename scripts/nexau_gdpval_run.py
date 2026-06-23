"""GDPval base test on the NexAU worker (Phase 3 of Stirrup->NexAU migration).

The NexAU agent (qea/worker_gdpval/, shell/code tool) builds a REAL deliverable file
in its sandbox; we copy the task's reference INPUT files into the sandbox first and
export the produced deliverables afterwards. Grading is the UNCHANGED multimodal
per-rubric pipeline (qea.grading.render + multimodal_judge) — runtime-independent.

    .venv-nexau/bin/python scripts/nexau_gdpval_run.py [--n N] [--stratify]
"""
from __future__ import annotations

import argparse
import os
import shutil
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WORKER = REPO / "qea" / "worker_gdpval"
sys.path.insert(0, str(REPO))
SUPPORTED = {".xlsx", ".pptx", ".docx", ".pdf"}


def _load_dotenv():
    for line in (REPO / ".env").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    os.environ["LLM_API_KEY"] = os.environ.get("OPENROUTER_API_KEY", "")
    os.environ["LLM_BASE_URL"] = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    os.environ.setdefault("LLM_MODEL", "deepseek/deepseek-v4-pro")


def _trace_summary(agent) -> dict:
    """Lightweight monitoring from the NexAU trace. Message has no tool_calls field
    (tool activity is in content/role), so count by role: assistant turns + tool-result
    messages (proxy for tool calls) + error markers in tool results."""
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
                # NexAU surfaces tool outputs as tool/user-role messages
                if role != "user":
                    tool_results += 1
                if any(k in text for k in ("Error", "❌", "failed", "Traceback", "Invalid parameters")):
                    tool_errors += 1
    except Exception:  # noqa: BLE001
        pass
    return {"tool_calls": tool_results, "tool_errors": tool_errors, "turns": turns}


def run_task(task):
    """Returns (final_text, [produced deliverable file paths], monitor dict).

    Uses a CONTROLLED absolute working dir (LocalSandbox runs locally, so absolute
    paths are reliable) instead of the sandbox's work_dir, which can resume to a new
    path mid-run and lose the produced files."""
    import time
    from nexau import Agent, AgentConfig
    t0 = time.time()
    workdir = REPO / "output" / "nexau_gdpval" / str(task.task_id) / "work"
    workdir.mkdir(parents=True, exist_ok=True)
    ref_names = set()
    for rf in (task.reference_files or []):
        rf = Path(rf)
        if rf.exists():
            shutil.copy(rf, workdir / rf.name)
            ref_names.add(rf.name)
    pre = {p for p in workdir.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED}
    cfg = AgentConfig.from_yaml(config_path=WORKER / "agent.yaml")
    agent = Agent(config=cfg)
    # Pin the sandbox cwd to our isolated per-task dir so the agent's saves (relative
    # OR absolute) land here -> clean counts + parallel-safe (no shared sandbox dir).
    try:
        agent.sandbox_manager.instance.work_dir = workdir
    except Exception:  # noqa: BLE001
        pass
    note = (f"\n\nIMPORTANT: Your working directory is {workdir}\n"
            f"The reference input files {sorted(ref_names)} are in that directory. "
            f"Read inputs from there, and SAVE your deliverable file(s) into that directory. "
            f"Run `ls -la` to verify your file is saved before finishing.")
    ctx = {"date": "2026-06-23", "username": os.environ.get("USER", "kevin"),
           "working_directory": str(workdir)}
    ctx["env_content"] = dict(ctx)
    resp = agent.run(message=task.prompt + note, context=ctx)
    final_text = resp if isinstance(resp, str) else resp[0]
    produced = [p for p in workdir.rglob("*")
                if p.is_file() and p.suffix.lower() in SUPPORTED
                and p not in pre and p.name not in ref_names]
    produced = sorted(produced, key=lambda p: p.stat().st_mtime, reverse=True)
    mon = _trace_summary(agent)
    mon["secs"] = round(time.time() - t0, 1)
    return final_text, produced[:12], mon


def main():
    _load_dotenv()
    from qea.tasks import load_gdpval_finance
    from qea.grading.render import render
    from qea.grading.multimodal_judge import MultimodalJudge
    from qea.llm import make_llm

    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=0)
    ap.add_argument("--stratify", action="store_true")
    args = ap.parse_args()
    tasks = load_gdpval_finance(broad=True, allow_download=True)
    if args.n:
        if args.stratify:
            buckets = {}
            for t in tasks:
                buckets.setdefault(t.subtype, []).append(t)
            order, picked = list(buckets.values()), []
            while len(picked) < args.n and any(order):
                for b in order:
                    if b and len(picked) < args.n:
                        picked.append(b.pop(0))
            tasks = picked
        else:
            tasks = tasks[: args.n]
    k = int(os.environ.get("QEA_JUDGE_K", "2"))
    judge = MultimodalJudge(make_llm(mock=False), k=k)
    import json, threading
    from concurrent.futures import ThreadPoolExecutor
    conc = int(os.environ.get("QEA_GDPVAL_CONCURRENCY", "3"))
    rows = [None] * len(tasks)
    mon_dir = REPO / "output" / "nexau_gdpval"
    mon_dir.mkdir(parents=True, exist_ok=True)
    monf = open(mon_dir / "monitor.jsonl", "w")
    lock = threading.Lock()
    done = [0]
    print(f"running {len(tasks)} GDPval tasks on NexAU | conc {conc} | judge k={k}", flush=True)

    def process(i, task):
        try:
            final_text, produced, mon = run_task(task)
            rendered = render(final_text, produced, mon_dir / str(task.task_id))
            res = judge.grade(task, rendered)
            row = {"id": task.task_id, "sub": task.subtype, "mm": res.multimodal_fraction,
                   "text": res.text_fraction, "files": len(produced), "imgs": len(rendered.images),
                   "deg": res.degraded, "err": "", **mon}
            msg = (f"mm={res.multimodal_fraction:.3f} text={res.text_fraction:.3f} "
                   f"files={len(produced)} turns={mon['turns']} {mon['secs']}s")
        except Exception as exc:  # noqa: BLE001
            row = {"id": task.task_id, "sub": task.subtype, "mm": None, "text": None, "files": 0,
                   "imgs": 0, "deg": True, "err": f"{type(exc).__name__}: {exc}",
                   "tool_calls": 0, "tool_errors": 0, "turns": 0, "secs": 0}
            msg = f"FAIL {type(exc).__name__}: {exc}"
        rows[i] = row
        with lock:
            done[0] += 1
            print(f"[{done[0]}/{len(tasks)}] {task.task_id} ({task.subtype}) {msg}", flush=True)
            monf.write(json.dumps(row) + "\n"); monf.flush()

    with ThreadPoolExecutor(max_workers=conc) as pool:
        list(pool.map(lambda a: process(*a), enumerate(tasks)))
    monf.close()

    ok = [r for r in rows if r["mm"] is not None]
    mm = statistics.mean(r["mm"] for r in ok) if ok else 0.0
    tx = statistics.mean(r["text"] for r in ok) if ok else 0.0
    lines = ["# GDPval base test — NexAU worker (file-producing) + multimodal grade", "",
             f"Graded {len(ok)}/{len(rows)} | judge k={k}",
             "Stirrup comparison: mean multimodal 0.807.", "",
             f"- **Mean multimodal:** {mm:.3f}", f"- **Mean text-only:** {tx:.3f}", "",
             "| task | subtype | multimodal | text | files | imgs | degraded | error |",
             "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        mmv = f"{r['mm']:.3f}" if r["mm"] is not None else "—"
        txv = f"{r['text']:.3f}" if r["text"] is not None else "—"
        lines.append(f"| {r['id']} | {r['sub']} | {mmv} | {txv} | {r['files']} | {r['imgs']} | {r['deg']} | {r['err']} |")
    Path("docs/RESULTS_gdpval_nexau.md").write_text("\n".join(lines) + "\n")
    print(f"\nGraded {len(ok)}/{len(rows)}  mean mm={mm:.3f}  -> docs/RESULTS_gdpval_nexau.md")


if __name__ == "__main__":
    main()
