#!/usr/bin/env python3
"""Statistical treatment of the held-out seed-vs-evolved comparisons: is the evolved
worker's gain real, given judge + worker stochasticity?

Three ingredients, each from a heldout summary.json produced by eval_worker_heldout.py:
  --pairs   one or more summary.json files whose FIRST worker is the seed and SECOND
            the evolved candidate; their per-task scores are pooled into one paired
            sample (task-level pairing removes between-task variance).
  --repeats two summary.json files that evaluated the SAME workers on the SAME tasks
            in independent runs (fresh cache); per-task |run2 - run1| for the same
            worker estimates the repeat noise sigma the delta must clear.

Outputs: pooled paired mean delta, a seeded 10k-resample bootstrap 95% CI, an exact
sign test p-value, per-worker repeat-noise sigma (per task and of the n-task mean),
and the delta/noise ratio. No network, no LLM — pure JSON arithmetic.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import random
from pathlib import Path


def _load(path):
    s = json.loads(Path(path).read_text())
    names = list(s)
    return names, s


def paired_deltas(summary_paths):
    """Pool per-task (seed, evolved) score pairs across summaries. First worker in
    each file = baseline, second = candidate."""
    pairs = []
    for p in summary_paths:
        names, s = _load(p)
        base, cand = s[names[0]]["per_task"], s[names[1]]["per_task"]
        for tid in sorted(base):
            if tid in cand:
                pairs.append((tid, base[tid], cand[tid]))
    return pairs


def bootstrap_ci(deltas, n_resamples=10_000, seed=7, alpha=0.05):
    rng = random.Random(seed)
    n = len(deltas)
    means = sorted(sum(rng.choice(deltas) for _ in range(n)) / n for _ in range(n_resamples))
    lo = means[int(alpha / 2 * n_resamples)]
    hi = means[int((1 - alpha / 2) * n_resamples) - 1]
    return lo, hi


def sign_test_p(deltas, tol=1e-9):
    """Exact two-sided binomial sign test on nonzero paired deltas."""
    pos = sum(1 for d in deltas if d > tol)
    neg = sum(1 for d in deltas if d < -tol)
    n = pos + neg
    if n == 0:
        return 1.0
    k = min(pos, neg)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n * 2
    return min(1.0, p)


def repeat_noise(path_a, path_b):
    """Per-worker repeat noise between two independent evals of the same (worker,
    tasks): per-task |d| stats and the sigma of the n-task MEAN (= what the keep
    decision and the held-out delta actually compare)."""
    names_a, a = _load(path_a)
    names_b, b = _load(path_b)
    out = {}
    for n1 in names_a:
        n2 = next((x for x in names_b if x == n1), None)
        if n2 is None:
            continue
        ta, tb = a[n1]["per_task"], b[n2]["per_task"]
        ds = [tb[t] - ta[t] for t in sorted(ta) if t in tb]
        if not ds:
            continue
        per_task_sd = (sum(d * d for d in ds) / len(ds)) ** 0.5  # sd around 0 (same worker)
        out[n1] = {
            "n": len(ds),
            "mean_delta": sum(ds) / len(ds),
            "mean_abs_delta": sum(abs(d) for d in ds) / len(ds),
            "per_task_sd": per_task_sd,
            "sd_of_mean": per_task_sd / len(ds) ** 0.5,
            "per_task_deltas": {t: round(tb[t] - ta[t], 4) for t in sorted(ta) if t in tb},
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", nargs="+", required=True,
                    help="summary.json files: worker[0]=seed, worker[1]=evolved")
    ap.add_argument("--repeats", nargs=2, default=None,
                    help="two summary.json files of the SAME workers/tasks (independent runs)")
    ap.add_argument("--out", default=None, help="write the full report JSON here")
    args = ap.parse_args()

    pairs = paired_deltas(args.pairs)
    deltas = [c - b for _, b, c in pairs]
    n = len(deltas)
    mean_d = sum(deltas) / n
    lo, hi = bootstrap_ci(deltas)
    p = sign_test_p(deltas)
    wins = sum(1 for d in deltas if d > 1e-9)
    losses = sum(1 for d in deltas if d < -1e-9)

    print(f"[paired] n={n} held-out tasks pooled from {len(args.pairs)} slice(s)")
    print(f"[paired] mean delta (evolved - seed) = {mean_d:+.4f}")
    print(f"[paired] bootstrap 95% CI = [{lo:+.4f}, {hi:+.4f}]"
          + ("  (excludes 0)" if lo > 0 or hi < 0 else "  (includes 0)"))
    print(f"[paired] sign test: {wins} wins / {losses} losses / {n - wins - losses} ties, p = {p:.4f}")

    report = {"n_pairs": n, "mean_delta": round(mean_d, 4),
              "bootstrap_ci95": [round(lo, 4), round(hi, 4)], "sign_test_p": round(p, 4),
              "wins": wins, "losses": losses,
              "per_task": [{"task": t, "seed": b, "evolved": c, "delta": round(c - b, 4)}
                           for t, b, c in pairs]}

    if args.repeats:
        noise = repeat_noise(*args.repeats)
        report["repeat_noise"] = noise
        for w, st in noise.items():
            print(f"[noise] {w}: n={st['n']} mean|d|={st['mean_abs_delta']:.4f} "
                  f"per-task sd={st['per_task_sd']:.4f} sd of {st['n']}-task mean={st['sd_of_mean']:.4f}")
        sds = [st["sd_of_mean"] for st in noise.values()]
        if sds:
            # two independent worker evals are compared, so the delta's noise sigma
            # adds in quadrature; scale the per-mean sd to the pooled n
            sd_pair = (sum(s * s for s in sds) / len(sds)) ** 0.5 * math.sqrt(2)
            print(f"[noise] est. sigma of a seed-vs-cand mean DELTA at n={noise[list(noise)[0]]['n']}: "
                  f"~{sd_pair:.4f}; observed pooled delta = {mean_d:+.4f} "
                  f"({abs(mean_d) / sd_pair:.1f}x sigma)" if sd_pair else "")
            report["delta_noise_sigma_est"] = round(sd_pair, 4)

    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2))
        print(f"[out] {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
