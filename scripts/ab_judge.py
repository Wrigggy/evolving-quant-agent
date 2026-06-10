#!/usr/bin/env python3
"""A/B test of judge identity for the GDPval-AA pairwise grader:
deepseek-v4-pro (same family as the worker -> self-judging) vs qwen3.7-max
(cross-family). Same frozen submission texts, same deterministic A/B
anonymization orderings -> any disagreement is attributable to the judge.

    python scripts/ab_judge.py --checkpoint results/aa_qwen_test/gdpval_soft/resume.json \
        --out results/ab_judge

Design (per judge):
  null   = match_set(S1 vs S0): two independent seed-harness samples; win share
           should be ~0.5; deviation = that judge's null margin.
  effect = match_set(C1 vs S0): incumbent (kept financial_calculator edit) vs
           the frozen seed anchor; replicates the iter-2 anchor rating.
Comparisons: per-task verdict agreement (all / decided-only), win shares, Elo,
and whether the "keep" decision (win share > 0.5 + own null margin) replicates.

S0 comes from the checkpoint (the run's actual frozen seed anchor); S1 and C1
are generated fresh once and shared by both judges.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _load_dotenv(path: str = ".env") -> None:
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--checkpoint", default="results/aa_qwen_test/gdpval_soft/resume.json")
    ap.add_argument("--judges", default="deepseek/deepseek-v4-pro,qwen/qwen3.7-max")
    ap.add_argument("--k", type=int, default=2)
    ap.add_argument("--out", default="results/ab_judge")
    args = ap.parse_args()

    _load_dotenv()
    os.environ["MOCK_LLM"] = "0"

    from qea.harness import Harness, seed_harness
    from qea.llm import OpenRouterLLM
    from qea.loop import _gen_deliverables
    from qea.tasks import load_gdpval_finance
    from qea.verifier import PairwiseJudge, bt_elo

    st = json.loads(Path(args.checkpoint).read_text())
    s0 = st["seed_deliverables"]
    incumbent = Harness.from_state(st["incumbent"])
    judges = [j.strip() for j in args.judges.split(",") if j.strip()]
    tasks = load_gdpval_finance(broad=True, allow_download=True)
    tasks = [t for t in tasks if t.task_id in s0]
    print(f"[ab] {len(tasks)} tasks; incumbent slots={incumbent.summary()}; judges={judges}")

    llm = OpenRouterLLM()
    pj = PairwiseJudge(llm)

    def _gen_complete(harness, name: str) -> dict:
        """Generate deliverables, retrying empty ones (failed generations come
        back as "" and would lose every match, poisoning the A/B)."""
        subs = _gen_deliverables(harness, tasks, mock=False, llm=llm)
        for rnd in range(1, 4):
            empty = [t for t in tasks if not subs.get(t.task_id, "").strip()]
            if not empty:
                break
            print(f"[ab] {name}: {len(empty)} empty deliverables; regen round {rnd}", flush=True)
            subs.update(_gen_deliverables(harness, empty, mock=False, llm=llm))
        return subs

    print("[ab] generating S1 (fresh seed sample) and C1 (incumbent sample) ...", flush=True)
    s1 = _gen_complete(seed_harness(), "S1")
    c1 = _gen_complete(incumbent, "C1")

    # Tasks with any still-empty submission are EXCLUDED (a blank entrant measures
    # the network, not the judge).
    bad = sorted(t.task_id for t in tasks
                 if not s0.get(t.task_id, "").strip() or not s1.get(t.task_id, "").strip()
                 or not c1.get(t.task_id, "").strip())
    if bad:
        print(f"[ab] EXCLUDING {len(bad)} tasks with empty submissions: {bad}", flush=True)
        tasks = [t for t in tasks if t.task_id not in bad]

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "submissions.json").write_text(json.dumps(
        {"S0": s0, "S1": s1, "C1": c1, "excluded": bad}, ensure_ascii=False, indent=2))

    results: dict = {"k": args.k, "n_tasks": len(tasks), "excluded": bad, "judges": {}}
    for judge in judges:
        os.environ["QEA_JUDGE_MODEL"] = judge  # _model() reads env per call
        tag = judge.split("/")[-1]
        null = pj.match_set(tasks, s1, s0, mock=False, k=args.k, label=f"{tag} null S1-vs-S0")
        effect = pj.match_set(tasks, c1, s0, mock=False, k=args.k, label=f"{tag} effect C1-vs-S0")
        margin = max(0.05, abs(null["win_share"] - 0.5))
        keep = effect["win_share"] > 0.5 + margin
        results["judges"][judge] = {
            "null": null, "effect": effect, "null_margin": round(margin, 4),
            "elo_vs_seed": bt_elo(effect["wins"], effect["losses"]),
            "keep_decision": keep,
        }
        print(f"[ab] {judge}: null {null['wins']}/{null['losses']}/{null['ties']} "
              f"(ws {null['win_share']}), effect {effect['wins']}/{effect['losses']}/{effect['ties']} "
              f"(ws {effect['win_share']}), Elo {results['judges'][judge]['elo_vs_seed']}, "
              f"keep={keep}", flush=True)

    # ---- cross-judge agreement on identical matches --------------------------
    if len(judges) == 2:
        j1, j2 = judges
        agree = {}
        for phase in ("null", "effect"):
            v1 = results["judges"][j1][phase]["per_task"]
            v2 = results["judges"][j2][phase]["per_task"]
            ids = sorted(v1)
            same = sum(1 for i in ids if v1[i] == v2[i])
            dec = [i for i in ids if v1[i] != "tie" and v2[i] != "tie"]
            same_dec = sum(1 for i in dec if v1[i] == v2[i])
            flipped = sum(1 for i in dec if v1[i] != v2[i])  # a<->b among mutually decided
            agree[phase] = {
                "all_agreement": round(same / len(ids), 4),
                "decided_both": len(dec),
                "decided_agreement": round(same_dec / len(dec), 4) if dec else None,
                "decided_flips": flipped,
                "disagreements": {i: [v1[i], v2[i]] for i in ids if v1[i] != v2[i]},
            }
        results["agreement"] = agree

    (out / "ab_judge.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"[ab] written -> {out / 'ab_judge.json'}")

    print("\n=== JUDGE A/B SUMMARY ===")
    for judge, r in results["judges"].items():
        print(f"  {judge}: null ws {r['null']['win_share']} (margin {r['null_margin']}), "
              f"effect ws {r['effect']['win_share']}, Elo {r['elo_vs_seed']}, keep={r['keep_decision']}")
    if "agreement" in results:
        for phase, a in results["agreement"].items():
            print(f"  agreement[{phase}]: all {a['all_agreement']}, "
                  f"decided {a['decided_agreement']} over {a['decided_both']} (flips {a['decided_flips']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
