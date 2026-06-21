"""Base-harness test: vanilla Stirrup-on-E2B worker + multimodal per-rubric grade.

Loop the GDPval finance tasks (or a --n subset), run each through the Stirrup
worker, render the produced files, grade with the multimodal judge (+ text-only
ablation), and write docs/RESULTS_base_stirrup_e2b.md. Does NOT touch the evolve
loop. Compares against the prior text-worker/text-grade baseline (0.618).

Usage:
    python scripts/base_harness_test.py --n 5      # pilot subset
    python scripts/base_harness_test.py            # full set
"""
from __future__ import annotations

import argparse
import os
import statistics
from pathlib import Path

from qea.llm import make_llm
from qea.tasks import load_gdpval_finance
from qea.workers.stirrup_worker import StirrupWorker
from qea.grading.render import render
from qea.grading.multimodal_judge import MultimodalJudge

PRIOR_TEXT_BASELINE = 0.618  # single-call text worker + text grade (ROADMAP)


def _load_dotenv(path: str = ".env") -> None:
    """Minimal .env loader (no dependency; mirrors run.py). Does not override set vars."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def _run_with_retry(worker, task, attempts: int, backoff: float):
    """Stirrup worker has no internal retry; transient proxy/E2B disconnects
    (RemoteProtocolError / WriteError) are common here. Retry the whole task."""
    import time
    last = None
    for i in range(attempts):
        try:
            return worker.run_task(task)
        except Exception as exc:  # noqa: BLE001
            last = exc
            wait = backoff * (2 ** i)
            print(f"  worker attempt {i + 1}/{attempts} failed ({type(exc).__name__}: {exc}); "
                  f"retry in {wait:.0f}s")
            time.sleep(wait)
    raise last


def main() -> None:
    _load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=0, help="pilot subset size (0 = all)")
    ap.add_argument("--stratify", action="store_true",
                    help="pick round-robin across subtypes (diverse pilot incl. the wall occupation)")
    ap.add_argument("--out", default="docs/RESULTS_base_stirrup_e2b.md")
    args = ap.parse_args()

    tasks = load_gdpval_finance(broad=True, allow_download=True)
    if args.n:
        if args.stratify:
            buckets: dict = {}
            for t in tasks:
                buckets.setdefault(t.subtype, []).append(t)
            order = list(buckets.values())
            picked = []
            while len(picked) < args.n and any(order):
                for b in order:
                    if b and len(picked) < args.n:
                        picked.append(b.pop(0))
            tasks = picked
        else:
            tasks = tasks[: args.n]
    judge_k = int(os.environ.get("QEA_JUDGE_K", "2"))
    worker_retries = int(os.environ.get("QEA_WORKER_RETRIES", "5"))
    backoff = float(os.environ.get("QEA_BACKOFF_BASE_SEC", "2.0"))

    worker = StirrupWorker()
    judge = MultimodalJudge(make_llm(mock=False), k=judge_k)

    rows = []
    for i, task in enumerate(tasks, 1):
        print(f"[{i}/{len(tasks)}] {task.task_id} ({task.subtype})")
        try:
            deliverable = _run_with_retry(worker, task, worker_retries, backoff)
            rendered = render(deliverable.final_text, deliverable.files,
                              Path("output/render") / str(task.task_id))
            res = judge.grade(task, rendered)
            rows.append({
                "task_id": task.task_id, "subtype": task.subtype,
                "mm": res.multimodal_fraction, "text": res.text_fraction,
                "var": res.variance, "n_files": len(deliverable.files),
                "n_imgs": len(rendered.images), "degraded": res.degraded,
                "error": "",
            })
        except Exception as exc:  # noqa: BLE001
            print(f"  ERROR: {type(exc).__name__}: {exc}")
            rows.append({"task_id": task.task_id, "subtype": task.subtype, "mm": None,
                         "text": None, "var": None, "n_files": 0, "n_imgs": 0,
                         "degraded": True, "error": f"{type(exc).__name__}: {exc}"})

    ok = [r for r in rows if r["mm"] is not None]
    mean_mm = statistics.mean(r["mm"] for r in ok) if ok else 0.0
    mean_text = statistics.mean(r["text"] for r in ok) if ok else 0.0

    lines = [
        "# Base-harness test — vanilla Stirrup on E2B + multimodal per-rubric grade",
        "",
        f"Tasks graded: {len(ok)}/{len(rows)}  |  judge k={judge_k}",
        "",
        f"- **Mean multimodal rubric %:** {mean_mm:.3f}",
        f"- **Mean text-only rubric % (ablation):** {mean_text:.3f}",
        f"- **Prior text-worker/text-grade baseline:** {PRIOR_TEXT_BASELINE:.3f}",
        f"- **Worker effect (text-grade − prior):** {mean_text - PRIOR_TEXT_BASELINE:+.3f}",
        f"- **Grader-input effect (mm − text):** {mean_mm - mean_text:+.3f}",
        "",
        "| task | subtype | multimodal % | text-only % | var | files | imgs | degraded | error |",
        "|------|---------|-------------|------------|-----|-------|------|----------|-------|",
    ]
    for r in rows:
        mm = f"{r['mm']:.3f}" if r["mm"] is not None else "—"
        tx = f"{r['text']:.3f}" if r["text"] is not None else "—"
        vr = f"{r['var']:.3f}" if r["var"] is not None else "—"
        lines.append(f"| {r['task_id']} | {r['subtype']} | {mm} | {tx} | {vr} | "
                     f"{r['n_files']} | {r['n_imgs']} | {r['degraded']} | {r['error']} |")
    Path(args.out).write_text("\n".join(lines) + "\n")
    print(f"\nWrote {args.out}\n  mean multimodal={mean_mm:.3f}  mean text={mean_text:.3f}")


if __name__ == "__main__":
    main()
