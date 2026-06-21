"""FAB v2 base test: Stirrup agent (free-backend EDGAR/price/web tools) answers
each public FAB question; we grade the TEXT answer with our per-rubric judge.

Reuses qea.verifier.score_rubric: each FAB criterion = 1 point, so the fraction is
FAB "generous" (partial credit) and frac==1.0 is FAB "strict" (all-pass). Grading
is our own LLM judge (qwen/qwen3.7-plus), NOT the official Vals operator -> these
are approximations, not leaderboard numbers.

    .venv312/bin/python scripts/fab_base_test.py [--n N]
"""
from __future__ import annotations

import argparse
import asyncio
import os
import statistics
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from qea.llm import make_llm
from qea.tasks_fab import load_fab_v2
from qea.workers.fab_worker import FabWorker
from qea.verifier import build_rubric_prompt, score_rubric


def _load_dotenv(path: str = ".env") -> None:
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _grade(judge, task, answer, k):
    items = task.rubric_items
    if not items:
        return 0.0, {}
    fracs, verdicts = [], {}
    for _ in range(k):
        txt = judge.complete(build_rubric_prompt(task, answer, items), role="judge")
        f, v = score_rubric(txt, items)
        fracs.append(f)
        verdicts = v
    return statistics.median(fracs), verdicts


async def _amain(args) -> None:
    tasks = load_fab_v2()
    if args.n:
        tasks = tasks[: args.n]
    k = int(os.environ.get("QEA_JUDGE_K", "2"))
    conc = int(os.environ.get("QEA_FAB_CONCURRENCY", "6"))
    worker = FabWorker()
    judge = make_llm(mock=False)
    sem = asyncio.Semaphore(conc)
    loop = asyncio.get_running_loop()
    pool = ThreadPoolExecutor(max_workers=conc + 2)
    rows = [None] * len(tasks)
    print(f"running {len(tasks)} FAB tasks | concurrency {conc} | judge k={k}")

    async def process(i, task):
        async with sem:
            try:
                answer = await worker.arun_task(task)
                frac, verdicts = await loop.run_in_executor(pool, _grade, judge, task, answer, k)
                rows[i] = {"task": task, "answer": answer, "frac": frac, "verdicts": verdicts, "err": ""}
                print(f"[ok  {task.task_id}] {task.subtype[:24]:24} generous={frac:.3f} "
                      f"strict={'1' if frac>=0.999 else '0'} ans={len(answer)}c")
            except Exception as exc:  # noqa: BLE001
                rows[i] = {"task": task, "answer": "", "frac": None, "verdicts": {}, "err": f"{type(exc).__name__}: {exc}"}
                print(f"[FAIL {task.task_id}] {type(exc).__name__}: {exc}")

    await asyncio.gather(*(process(i, t) for i, t in enumerate(tasks)))
    pool.shutdown(wait=True)
    _write(rows, k)


def _write(rows, k):
    ok = [r for r in rows if r["frac"] is not None]
    gen = statistics.mean(r["frac"] for r in ok) if ok else 0.0
    strict = (sum(1 for r in ok if r["frac"] >= 0.999) / len(ok)) if ok else 0.0
    by = defaultdict(list)
    for r in ok:
        by[r["task"].subtype].append(r["frac"])

    # ---- RESULTS summary ----
    res = [
        "# FAB v2 base test — Stirrup + free EDGAR/price/web tools (our-grader approx)",
        "",
        f"Graded {len(ok)}/{len(rows)} | judge k={k} | grader=qwen3.7-plus (NOT official Vals).",
        "",
        f"- **Generous (mean partial-credit %):** {gen:.3f}",
        f"- **Strict (all-pass rate):** {strict:.3f}",
        "",
        "### By category",
        "| category | n | generous | strict |",
        "|----------|---|----------|--------|",
    ]
    for cat, fs in sorted(by.items()):
        sp = sum(1 for x in fs if x >= 0.999) / len(fs)
        res.append(f"| {cat} | {len(fs)} | {statistics.mean(fs):.3f} | {sp:.3f} |")
    res += ["", "### Per task", "| task | category | generous | strict | ans chars | error |",
            "|------|----------|----------|--------|-----------|-------|"]
    for r in rows:
        t = r["task"]
        g = f"{r['frac']:.3f}" if r["frac"] is not None else "—"
        s = ("1" if (r["frac"] or 0) >= 0.999 else "0") if r["frac"] is not None else "—"
        res.append(f"| {t.task_id} | {t.subtype} | {g} | {s} | {len(r['answer'])} | {r['err']} |")
    Path("docs/RESULTS_fab_base.md").write_text("\n".join(res) + "\n")

    # ---- detailed REPORT (per-task answer + per-criterion) ----
    rep = ["# FAB v2 base test — per-task report", "",
           "Agent answers + per-criterion grading. Single grading pass shown; "
           "see RESULTS for k-median aggregates.", ""]
    from qea.verifier import _truthy
    for r in rows:
        t = r["task"]
        rep.append(f"## {t.task_id} — {t.subtype}")
        rep.append("")
        rep.append(f"**Question:** {t.prompt[:700]}" + ("…" if len(t.prompt) > 700 else ""))
        rep.append("")
        if r["frac"] is None:
            rep.append(f"_FAILED: {r['err']}_\n")
            continue
        rep.append(f"**Score (generous):** {r['frac']:.3f}  |  strict: {'PASS' if r['frac']>=0.999 else 'fail'}")
        rep.append("")
        rep.append("**Per-criterion (✓/·):**")
        for j, c in enumerate(t.rubric_items):
            ok_ = "✓" if _truthy(r["verdicts"].get(str(j + 1))) else "·"
            rep.append(f"- {ok_} {c['criterion'][:130]}")
        rep.append("")
        rep.append(f"**Agent answer:**\n\n{r['answer'][:2500]}" + ("…" if len(r["answer"]) > 2500 else ""))
        rep.append("")
    Path("docs/REPORT_fab_base.md").write_text("\n".join(rep) + "\n")
    print(f"\nGraded {len(ok)}/{len(rows)}  generous={gen:.3f}  strict={strict:.3f}")
    print("Wrote docs/RESULTS_fab_base.md + docs/REPORT_fab_base.md")


def main() -> None:
    _load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=0, help="subset size (0=all 27)")
    main_args = ap.parse_args()
    asyncio.run(_amain(main_args))


if __name__ == "__main__":
    main()
