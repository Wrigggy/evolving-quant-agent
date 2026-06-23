"""FAB v2 base test on the NexAU worker (Phase 2 of the Stirrup->NexAU migration).

Same benchmark + grader as scripts/fab_base_test.py (unchanged score_rubric), but
the worker is the NexAU agent defined in qea/worker/ (agent.yaml + tools). Used to
confirm port fidelity vs the Stirrup FAB number (generous 0.659).

    .venv-nexau/bin/python scripts/nexau_fab_run.py [--n N]
"""
from __future__ import annotations

import argparse
import os
import statistics
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WORKER = REPO / "qea" / "worker"
sys.path.insert(0, str(REPO))     # for qea.*
sys.path.insert(0, str(WORKER))   # for the `tools.fab.research` tool bindings


def _load_dotenv():
    for line in (REPO / ".env").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    os.environ["LLM_API_KEY"] = os.environ.get("OPENROUTER_API_KEY", "")
    os.environ["LLM_BASE_URL"] = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    os.environ.setdefault("LLM_MODEL", "deepseek/deepseek-v4-pro")


def run_task(task) -> str:
    from nexau import Agent, AgentConfig
    cfg = AgentConfig.from_yaml(config_path=WORKER / "agent.yaml")
    agent = Agent(config=cfg)
    sbx = agent.sandbox_manager.instance
    ctx = {"date": "2026-06-23", "username": os.environ.get("USER", "kevin"),
           "working_directory": str(sbx.work_dir if sbx else os.getcwd())}
    ctx["env_content"] = dict(ctx)
    resp = agent.run(message=task.prompt, context=ctx)
    return resp if isinstance(resp, str) else resp[0]


def grade(judge, task, answer, k):
    from qea.verifier import build_rubric_prompt, score_rubric
    items = task.rubric_items
    if not items:
        return 0.0, {}
    fracs, verdicts = [], {}
    for _ in range(k):
        f, v = score_rubric(judge.complete(build_rubric_prompt(task, answer, items), role="judge"), items)
        fracs.append(f); verdicts = v
    return statistics.median(fracs), verdicts


def main():
    _load_dotenv()
    from qea.tasks_fab import load_fab_v2
    from qea.llm import make_llm
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=0)
    args = ap.parse_args()
    tasks = load_fab_v2()
    if args.n:
        tasks = tasks[: args.n]
    k = int(os.environ.get("QEA_JUDGE_K", "2"))
    conc = int(os.environ.get("QEA_FAB_CONCURRENCY", "4"))
    judge = make_llm(mock=False)
    rows = [None] * len(tasks)
    print(f"running {len(tasks)} FAB tasks on NexAU | conc {conc} | judge k={k}")

    def process(i, task):
        try:
            ans = run_task(task)
            frac, verdicts = grade(judge, task, ans, k)
            rows[i] = {"task": task, "answer": ans, "frac": frac, "verdicts": verdicts, "err": ""}
            print(f"[ok  {task.task_id}] {task.subtype[:22]:22} generous={frac:.3f} "
                  f"strict={'1' if frac>=0.999 else '0'} ans={len(ans)}c")
        except Exception as exc:  # noqa: BLE001
            rows[i] = {"task": task, "answer": "", "frac": None, "verdicts": {}, "err": f"{type(exc).__name__}: {exc}"}
            print(f"[FAIL {task.task_id}] {type(exc).__name__}: {exc}")

    with ThreadPoolExecutor(max_workers=conc) as pool:
        list(pool.map(lambda a: process(*a), enumerate(tasks)))

    ok = [r for r in rows if r["frac"] is not None]
    gen = statistics.mean(r["frac"] for r in ok) if ok else 0.0
    strict = (sum(1 for r in ok if r["frac"] >= 0.999) / len(ok)) if ok else 0.0
    by = defaultdict(list)
    for r in ok:
        by[r["task"].subtype].append(r["frac"])
    lines = ["# FAB v2 base test — NexAU worker (free EDGAR/price/web tools)", "",
             f"Graded {len(ok)}/{len(rows)} | judge k={k} | grader=qwen3.7-plus (our approx).",
             f"Stirrup comparison: generous 0.659 / strict 0.231.", "",
             f"- **Generous:** {gen:.3f}", f"- **Strict (all-pass):** {strict:.3f}", "",
             "| category | n | generous | strict |", "|---|---|---|---|"]
    for cat, fs in sorted(by.items()):
        lines.append(f"| {cat} | {len(fs)} | {statistics.mean(fs):.3f} | "
                     f"{sum(1 for x in fs if x>=0.999)/len(fs):.3f} |")
    lines += ["", "| task | category | generous | strict | ans | error |", "|---|---|---|---|---|---|"]
    for r in rows:
        t = r["task"]; g = f"{r['frac']:.3f}" if r["frac"] is not None else "—"
        s = ("1" if (r["frac"] or 0) >= 0.999 else "0") if r["frac"] is not None else "—"
        lines.append(f"| {t.task_id} | {t.subtype} | {g} | {s} | {len(r['answer'])} | {r['err']} |")
    Path("docs/RESULTS_fab_nexau.md").write_text("\n".join(lines) + "\n")
    print(f"\nGraded {len(ok)}/{len(rows)}  generous={gen:.3f}  strict={strict:.3f}  -> docs/RESULTS_fab_nexau.md")


if __name__ == "__main__":
    main()
