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
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
# Worker dir + output label are overridable so the same harness can base-test the
# full worker OR the weak seed without clobbering each other's results.
WORKER = REPO / (os.environ.get("QEA_WORKER_DIR") or "qea/worker_gdpval")
RUN_LABEL = os.environ.get("QEA_RUN_LABEL", "nexau_gdpval")
RESULTS_MD = os.environ.get("QEA_RESULTS_MD", "docs/RESULTS_gdpval_nexau.md")
sys.path.insert(0, str(REPO))


def _load_dotenv():
    for line in (REPO / ".env").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    os.environ["LLM_API_KEY"] = os.environ.get("OPENROUTER_API_KEY", "")
    os.environ["LLM_BASE_URL"] = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    os.environ.setdefault("LLM_MODEL", "deepseek/deepseek-v4-pro")


def run_task(task):
    """Returns (final_text, [produced deliverable file paths], monitor dict).
    Delegates to qea.worker_runtime.run_worker so the base test and the Level-B
    loop run the IDENTICAL worker invocation."""
    from qea.worker_runtime import run_worker
    run = run_worker(task, WORKER, REPO / "output" / RUN_LABEL / str(task.task_id))
    return run.deliverable_text, run.produced_files, run.trace


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
    mon_dir = REPO / "output" / RUN_LABEL
    mon_dir.mkdir(parents=True, exist_ok=True)
    monf = open(mon_dir / "monitor.jsonl", "w")
    lock = threading.Lock()
    done = [0]
    print(f"running {len(tasks)} GDPval tasks on NexAU | conc {conc} | judge k={k}", flush=True)

    import time as _time
    attempts = int(os.environ.get("QEA_GDPVAL_TASK_ATTEMPTS", "2"))

    def process(i, task):
        # Stagger the first wave's startup so N concurrent TLS handshakes through the
        # local proxy don't all fire at once (the handshake burst that caused the
        # ConnectTimeouts). Only spreads each wave by a few seconds.
        _time.sleep((i % conc) * 2.5)
        row = msg = None
        for attempt in range(1, attempts + 1):
            try:
                final_text, produced, mon = run_task(task)
                rendered = render(final_text, produced, mon_dir / str(task.task_id))
                res = judge.grade(task, rendered)
                row = {"id": task.task_id, "sub": task.subtype, "mm": res.multimodal_fraction,
                       "text": res.text_fraction, "files": len(produced), "imgs": len(rendered.images),
                       "deg": res.degraded, "err": "", **mon}
                msg = (f"mm={res.multimodal_fraction:.3f} text={res.text_fraction:.3f} "
                       f"files={len(produced)} turns={mon['turns']} {mon['secs']}s"
                       + (f" (attempt {attempt})" if attempt > 1 else ""))
                break
            except Exception as exc:  # noqa: BLE001
                row = {"id": task.task_id, "sub": task.subtype, "mm": None, "text": None, "files": 0,
                       "imgs": 0, "deg": True, "err": f"{type(exc).__name__}: {exc}",
                       "tool_calls": 0, "tool_errors": 0, "turns": 0, "secs": 0}
                msg = f"FAIL (attempt {attempt}/{attempts}) {type(exc).__name__}: {exc}"
                if attempt < attempts:
                    _time.sleep(5 * attempt)  # backoff before whole-task retry
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
    Path(RESULTS_MD).write_text("\n".join(lines) + "\n")
    print(f"\nGraded {len(ok)}/{len(rows)}  mean mm={mm:.3f}  -> {RESULTS_MD}")


if __name__ == "__main__":
    main()
