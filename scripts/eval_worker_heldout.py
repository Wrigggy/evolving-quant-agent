#!/usr/bin/env python3
"""Held-out comparison of two worker dirs on a GDPval task slice the Level-B loop
never evolved on. The loop optimizes on tasks[:n]; evaluating seed vs evolved on
tasks[offset:offset+n] separates domain specialization (evolved worker generalizes
to unseen tasks of the same occupations) from per-task overfitting.

    python scripts/eval_worker_heldout.py \
        --workers qea/worker_gdpval_weak results/<run>/incumbent_worker \
        --offset 8 --n 8 --k 2 --concurrency 4 --results-dir results/<out>

Worker dirs are evaluated SEQUENTIALLY (one E2B wave at a time) so a single process
stays within the parallel-run budget. Scores are cached per (worker_sig, task_id)
exactly like the loop, so a re-launch resumes.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from run import _load_dotenv  # noqa: E402
from qea.benchmark import make_benchmark  # noqa: E402
from qea.llm import make_llm  # noqa: E402
from qea.loop_levelb import evaluate_dir  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", nargs="+", required=True,
                    help="worker dirs to evaluate (e.g. seed + evolved incumbent)")
    ap.add_argument("--benchmark", default="gdpval")
    ap.add_argument("--offset", type=int, default=8, help="first task index of the held-out slice")
    ap.add_argument("--n", type=int, default=8, help="number of held-out tasks")
    ap.add_argument("--task-ids", default="",
                    help="comma-separated task ids (or @file containing them) to evaluate "
                         "instead of the offset/n slice — for hand-picked subsets")
    ap.add_argument("--k", type=int, default=2)
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--execution", default="e2b_full", choices=["local", "e2b_full"])
    ap.add_argument("--n-samples", type=int, default=1,
                    help="worker samples per task; per-task score = sample mean")
    ap.add_argument("--results-dir", required=True)
    args = ap.parse_args()

    _load_dotenv()
    llm = make_llm(False)
    bench = make_benchmark(args.benchmark, llm=llm, broad=True, k=args.k)
    if args.task_ids:
        spec = args.task_ids
        if spec.startswith("@"):
            spec = Path(spec[1:]).read_text().strip()
        wanted = [x.strip() for x in spec.split(",") if x.strip()]
        by_id = {str(t.task_id): t for t in bench.tasks}
        missing = [w for w in wanted if w not in by_id]
        if missing:
            raise SystemExit(f"[heldout] task ids not in benchmark: {missing}")
        tasks = [by_id[w] for w in wanted]
        print(f"[heldout] {len(tasks)} hand-picked tasks: {[str(t.task_id)[:8] for t in tasks]}", flush=True)
    else:
        tasks = bench.tasks[args.offset:args.offset + args.n]
        print(f"[heldout] {len(tasks)} tasks (index {args.offset}..{args.offset + len(tasks) - 1}): "
              f"{[str(t.task_id)[:8] for t in tasks]}", flush=True)

    results_dir = Path(args.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    summary = {}
    for wd in args.workers:
        name = Path(wd).parent.name if Path(wd).name == "incumbent_worker" else Path(wd).name
        out = results_dir / name
        print(f"[heldout] evaluating {wd} -> {out}", flush=True)
        evals, traces, _, mean = evaluate_dir(
            Path(wd), tasks, bench.evaluator, out,
            concurrency=args.concurrency, cache_dir=results_dir / "_cache",
            execution=args.execution, n_samples=args.n_samples)
        # evals: dict task_id -> EvalSummary (attr gated_score), keyed like the loop
        per_task = {str(tid)[:8]: round(e.gated_score, 4) for tid, e in evals.items()}
        summary[name] = {"worker_dir": str(wd), "mean": round(mean, 4), "per_task": per_task}
        print(f"[heldout] {name}: mean={mean:.4f} per_task={per_task}", flush=True)

    (results_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    names = list(summary)
    if len(names) >= 2:
        delta = summary[names[1]]["mean"] - summary[names[0]]["mean"]
        print(f"\n[heldout] {names[1]} - {names[0]} = {delta:+.4f} "
              f"({summary[names[0]]['mean']:.4f} -> {summary[names[1]]['mean']:.4f})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
