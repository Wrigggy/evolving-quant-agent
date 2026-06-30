#!/usr/bin/env python3
"""QEA v0 entrypoint.

    python run.py --mock              # offline synthetic plumbing fixture (no API key)
    python run.py --real              # real OpenRouter run (needs .env)

MOCK prints the synthetic-fixture iteration table (verdict + per-subtype OOS),
the OOS trajectory, and the mechanism signals (the three §5.4 signals). It makes
no headroom claim — it deterministically exercises evolve->falsify->rollback.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from qea.loop import Config, acceptance_signals, run_synthetic_fixture, run_gdpval_soft
from qea.loop_levelb import LevelBConfig, run_levelb


def _load_dotenv(path: str = ".env") -> None:
    """Minimal .env loader (no dependency). Does not override already-set vars."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        os.environ.setdefault(key, val)


def _print_arm(arm) -> None:
    print(f"\n=== {arm.arm} ===")
    print(f"  OOS trajectory (incumbent): {arm.oos_trajectory}")
    print(f"  {'iter':>4} {'verdict':<20} {'kept':<6} {'oos':>4}  per-subtype(oos/total)")
    for r in arm.records:
        ps = " ".join(f"{k}={v[0]}/{v[1]}" for k, v in r.per_subtype.items())
        flag = "BLOCKED" if r.blocked else ("keep" if r.kept else "rollback")
        print(f"  {r.iteration:>4} {r.verdict:<20} {flag:<6} {r.incumbent_oos:>4}  {ps}")
    print(f"  final harness slots: {arm.final_harness_summary}")
    print(f"  B transfer: mean={arm.b_transfer['mean_score']:.3f} (baseline {arm.b_baseline['mean_score']:.3f}), "
          f"oos {arm.b_transfer['n_oos']}/{arm.b_transfer['n']}")
    print(f"  mean eval-signal variance: {arm.mean_eval_variance:.5f}")
    print(f"  kept/rolledback/blocked: {arm.n_kept}/{arm.n_rolled_back}/{arm.n_blocked}")


def main() -> int:
    ap = argparse.ArgumentParser(description="QEA v0 — evolving quant agent")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--mock", action="store_true", help="offline scripted smoke test (default)")
    mode.add_argument("--real", action="store_true", help="real OpenRouter run (needs .env)")
    mode.add_argument("--levelb", action="store_true",
                      help="real mode: Level-B evolution (file-editing evolve agent edits the NexAU worker dir)")
    ap.add_argument("--iters", type=int, default=4)
    ap.add_argument("--k", type=int, default=2)
    ap.add_argument("--core", action="store_true", help="real mode: ~25 core finance occupations instead of ~30 broad")
    ap.add_argument("--resume", action="store_true", help="real mode: continue a prior gdpval_soft run from its checkpoint")
    ap.add_argument("--n-tasks", type=int, default=5, help="levelb: number of tasks per iteration")
    ap.add_argument("--benchmark", default="fab", choices=["fab", "gdpval"],
                    help="levelb: which benchmark to evolve on (default fab)")
    ap.add_argument("--seed-worker", default=None,
                    help="levelb: seed worker dir (defaults per benchmark)")
    ap.add_argument("--results-dir", default="results/latest")
    args = ap.parse_args()

    _load_dotenv()

    if args.levelb:
        seed = args.seed_worker or ("qea/worker_fab_weak" if args.benchmark == "fab"
                                    else "qea/worker_gdpval_weak")
        lcfg = LevelBConfig(n_iters=args.iters, k=args.k, n_tasks=args.n_tasks,
                            broad=not args.core, results_dir=args.results_dir,
                            benchmark=args.benchmark, seed_worker_dir=seed)
        print(f"[run] mode=LEVEL-B ({lcfg.benchmark} worker dir evolved by a file-editing evolve agent) "
              f"iters={lcfg.n_iters} k={lcfg.k} n_tasks={lcfg.n_tasks} seed={seed} -> {lcfg.results_dir}")
        res = run_levelb(lcfg)
        _print_levelb(res)
        rose = res.mean_score_trajectory[-1] > res.mean_score_trajectory[0] + res.noise_margin
        print(f"\n  ==> LEVEL-B HEADROOM {'OBSERVED' if rose else 'NOT OBSERVED'}: "
              f"mean {res.mean_score_trajectory[0]:.3f} -> {res.mean_score_trajectory[-1]:.3f} "
              f"(noise floor {res.noise_margin:.3f}), {res.n_kept} edit(s) kept.")
        return 0 if rose else 1
    mock = not args.real  # mock is the default
    if mock:
        os.environ["MOCK_LLM"] = "1"
    cfg = Config(mock=mock, n_iters=args.iters, k=args.k,
                 gdpval_broad=not args.core, resume=args.resume, results_dir=args.results_dir)

    # MOCK = offline synthetic plumbing fixture (deterministic, no API key).
    # REAL = evolve directly on the ORIGINAL GDPval finance tasks, soft-rubric-driven.
    if mock:
        print(f"[run] mode=MOCK (synthetic plumbing fixture; no headroom claim) iters={cfg.n_iters} k={cfg.k} -> {cfg.results_dir}")
        fix = run_synthetic_fixture(cfg)
        _print_arm(fix)
        print("\n=== MECHANISM SIGNALS (synthetic fixture) ===")
        sig = acceptance_signals(fix)
        for name, ok in sig.items():
            print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        overall = all(sig.values())
        print(f"\n  ==> MECHANISM {'CONFIRMED' if overall else 'NOT CONFIRMED'} (MOCK plumbing).")
        return 0 if overall else 1

    print(f"[run] mode=REAL (soft-rubric-graded evolution on ORIGINAL GDPval finance tasks; "
          f"no hard verifier — soft signal in the loop) iters={cfg.n_iters} k={cfg.k} broad={cfg.gdpval_broad} -> {cfg.results_dir}")
    res = run_gdpval_soft(cfg)
    _print_soft(res)
    rose = res.mean_score_trajectory[-1] > res.mean_score_trajectory[0] + res.noise_margin
    print(f"\n  ==> SOFT HEADROOM {'OBSERVED' if rose else 'NOT OBSERVED'} (REAL, mean-rubric-score gate): "
          f"mean score {res.mean_score_trajectory[0]:.3f} -> {res.mean_score_trajectory[-1]:.3f} "
          f"(noise floor {res.noise_margin:.3f}), {res.n_kept} edit(s) kept. "
          f"NOTE: soft signal (no hard verifier) — treat as indicative, not proof.")
    return 0 if rose else 1


def _print_soft(res) -> None:
    print(f"\n=== GDPval-soft evolution ({res.n_tasks} original tasks, mean-rubric-score gate) ===")
    print(f"  rubric-score noise floor (gain a candidate must beat): {res.noise_margin}")
    print(f"  OOS trajectory (#score>=0.6): {res.oos_trajectory}")
    print(f"  mean rubric score trajectory (the gate signal): {res.mean_score_trajectory}")
    print(f"  {'iter':>4} {'verdict':<18} {'kept':<8} {'oos':>4}")
    for r in res.records:
        flag = "BLOCKED" if r.blocked else ("keep" if r.kept else "rollback")
        print(f"  {r.iteration:>4} {r.verdict:<18} {flag:<8} {r.incumbent_oos:>4}  | edit: {r.edit_slot}:{r.edit_component}")
    print(f"  final mean rubric score: {res.final_mean_score}")
    print("  final per-occupation PASS RATE (score>=0.6) + mean rubric score:")
    means = res.final_per_occupation_mean or {}
    for occ, (o, t) in sorted(res.final_per_occupation.items()):
        pr = (100.0 * o / t) if t else 0.0
        print(f"    {occ[:46]:46} {o}/{t} = {pr:5.1f}%   mean {means.get(occ, 0.0):.3f}")
    print(f"  kept/rolledback/blocked: {res.n_kept}/{res.n_rolled_back}/{res.n_blocked}")


def _print_levelb(res) -> None:
    print(f"\n=== Level-B evolution ({res.n_tasks} {res.benchmark or ''} tasks, format-gated score) ===")
    print(f"  noise floor (gain a candidate must beat): {res.noise_margin}")
    print(f"  mean gated-score trajectory: {res.mean_score_trajectory}")
    print(f"  {'iter':>4} {'verdict':<16} {'kept':<8} inc->cand")
    for r in res.records:
        flag = "BLOCKED" if r.blocked else ("keep" if r.kept else "rollback")
        print(f"  {r.iteration:>4} {r.verdict:<16} {flag:<8} {r.inc_mean:.3f}->{r.cand_mean:.3f}  | {r.edit_summary}")
    print(f"  final mean gated score: {res.final_mean_score}")
    print(f"  final worker dir: {res.final_worker_dir}")
    print(f"  kept/rolledback/blocked: {res.n_kept}/{res.n_rolled_back}/{res.n_blocked}")


if __name__ == "__main__":
    raise SystemExit(main())
