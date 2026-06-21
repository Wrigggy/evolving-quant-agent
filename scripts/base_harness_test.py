"""Base-harness test: vanilla Stirrup-on-E2B worker + multimodal per-rubric grade.

Runs the GDPval finance tasks (or a --n subset) CONCURRENTLY (E2B sandbox cap via
QEA_MAX_E2B, default 20), each through the Stirrup worker (which uploads the task's
reference INPUT files and reconnects E2B on disconnect WITHOUT re-sampling the LLM),
renders the produced files, and grades with the multimodal judge (+ text-only
ablation). Writes docs/RESULTS_base_stirrup_e2b.md. Does NOT touch the evolve loop.

Resilience contract: an E2B disconnect retries the sandbox command only; the LLM
produces its output exactly once (no whole-task re-roll, no best-of-N).

Usage:
    .venv312/bin/python scripts/base_harness_test.py --n 5 --stratify   # pilot
    .venv312/bin/python scripts/base_harness_test.py                     # full set
"""
from __future__ import annotations

import argparse
import asyncio
import os
import statistics
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from qea.llm import make_llm
from qea.tasks import load_gdpval_finance
from qea.workers.stirrup_worker import StirrupWorker, Deliverable
from qea.grading.render import render
from qea.grading.multimodal_judge import MultimodalJudge

PRIOR_TEXT_BASELINE = 0.618  # single-call text worker + text grade, NO reference files (ROADMAP)


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


def _select(tasks, n: int, stratify: bool):
    if not n:
        return tasks
    if not stratify:
        return tasks[:n]
    buckets: dict = {}
    for t in tasks:
        buckets.setdefault(t.subtype, []).append(t)
    order = list(buckets.values())
    picked = []
    while len(picked) < n and any(order):
        for b in order:
            if b and len(picked) < n:
                picked.append(b.pop(0))
    return picked


async def _amain(args) -> None:
    tasks = _select(load_gdpval_finance(broad=True, allow_download=True), args.n, args.stratify)
    judge_k = int(os.environ.get("QEA_JUDGE_K", "2"))
    e2b_cap = int(os.environ.get("QEA_MAX_E2B", "20"))
    judge_cap = int(os.environ.get("QEA_MAX_CONCURRENCY", "8"))

    worker = StirrupWorker()
    judge = MultimodalJudge(make_llm(mock=False), k=judge_k)

    e2b_sem = asyncio.Semaphore(e2b_cap)
    judge_sem = asyncio.Semaphore(judge_cap)
    loop = asyncio.get_running_loop()
    pool = ThreadPoolExecutor(max_workers=max(8, judge_cap + 4))
    rows: list = [None] * len(tasks)
    print(f"running {len(tasks)} tasks | E2B concurrency {e2b_cap} | judge k={judge_k} conc {judge_cap}")

    async def process(idx: int, task) -> None:
        nref = len(getattr(task, "reference_files", []) or [])
        try:
            existing = [p for p in (worker.out_root / str(task.task_id)).rglob("*")
                        if p.is_file()] if worker.out_root.exists() else []
            if args.reuse and existing:
                # 补跑/re-grade: reuse the saved deliverable, skip the worker + E2B
                # (applies the fixed scorer without re-sampling the LLM).
                deliverable = Deliverable(str(task.task_id), "", existing)
            else:
                async with e2b_sem:  # cap concurrent live sandboxes at the E2B account limit
                    deliverable = await worker.arun_task(task)  # LLM once; E2B reconnects internally
            rendered = await loop.run_in_executor(
                pool, render, deliverable.final_text, deliverable.files,
                Path("output/render") / str(task.task_id))
            async with judge_sem:
                res = await loop.run_in_executor(pool, judge.grade, task, rendered)
            rows[idx] = {"task_id": task.task_id, "subtype": task.subtype,
                         "mm": res.multimodal_fraction, "text": res.text_fraction,
                         "var": res.variance, "n_files": len(deliverable.files),
                         "n_imgs": len(rendered.images), "nref": nref,
                         "degraded": res.degraded, "error": ""}
            print(f"[ok  {task.task_id[:8]}] mm={res.multimodal_fraction:.3f} "
                  f"text={res.text_fraction:.3f} files={len(deliverable.files)} refs={nref}")
        except Exception as exc:  # noqa: BLE001 - record + continue; NO whole-task retry
            rows[idx] = {"task_id": task.task_id, "subtype": task.subtype, "mm": None,
                         "text": None, "var": None, "n_files": 0, "n_imgs": 0, "nref": nref,
                         "degraded": True, "error": f"{type(exc).__name__}: {exc}"}
            print(f"[FAIL {task.task_id[:8]}] {type(exc).__name__}: {exc}")

    await asyncio.gather(*(process(i, t) for i, t in enumerate(tasks)))
    pool.shutdown(wait=True)

    ok = [r for r in rows if r["mm"] is not None]
    mean_mm = statistics.mean(r["mm"] for r in ok) if ok else 0.0
    mean_text = statistics.mean(r["text"] for r in ok) if ok else 0.0

    lines = [
        "# Base-harness test — vanilla Stirrup on E2B + multimodal per-rubric grade",
        "",
        f"Tasks graded: {len(ok)}/{len(rows)}  |  judge k={judge_k}  |  E2B concurrency {e2b_cap}",
        "Worker uploads GDPval reference INPUT files; E2B reconnects on disconnect "
        "(LLM output single-attempt).",
        "",
        f"- **Mean multimodal rubric %:** {mean_mm:.3f}",
        f"- **Mean text-only rubric % (ablation):** {mean_text:.3f}",
        f"- **Prior text-worker/text-grade baseline (no ref files):** {PRIOR_TEXT_BASELINE:.3f}",
        f"- **Worker effect (text-grade − prior):** {mean_text - PRIOR_TEXT_BASELINE:+.3f}",
        f"- **Grader-input effect (mm − text):** {mean_mm - mean_text:+.3f}",
        "",
        "| task | subtype | multimodal % | text-only % | var | files | imgs | refs | degraded | error |",
        "|------|---------|-------------|------------|-----|-------|------|------|----------|-------|",
    ]
    for r in rows:
        mm = f"{r['mm']:.3f}" if r["mm"] is not None else "—"
        tx = f"{r['text']:.3f}" if r["text"] is not None else "—"
        vr = f"{r['var']:.3f}" if r["var"] is not None else "—"
        lines.append(f"| {r['task_id']} | {r['subtype']} | {mm} | {tx} | {vr} | "
                     f"{r['n_files']} | {r['n_imgs']} | {r['nref']} | {r['degraded']} | {r['error']} |")
    Path(args.out).write_text("\n".join(lines) + "\n")
    print(f"\nWrote {args.out}\n  graded {len(ok)}/{len(rows)}  mean multimodal={mean_mm:.3f}  "
          f"mean text={mean_text:.3f}")


def main() -> None:
    _load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=0, help="subset size (0 = all)")
    ap.add_argument("--stratify", action="store_true",
                    help="round-robin across subtypes (diverse pilot incl. the wall occupation)")
    ap.add_argument("--reuse", action="store_true",
                    help="re-grade saved deliverables (skip worker/E2B); run worker only for "
                         "tasks with no saved deliverable. For 补跑 + applying scoring fixes.")
    ap.add_argument("--out", default="docs/RESULTS_base_stirrup_e2b.md")
    args = ap.parse_args()
    asyncio.run(_amain(args))


if __name__ == "__main__":
    main()
