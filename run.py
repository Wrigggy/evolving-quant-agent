#!/usr/bin/env python3
"""QEA v0 entrypoint.

    python run.py --mock              # offline smoke test (no API key), both arms
    python run.py --real --b-n 12     # real OpenRouter run (needs .env)

Prints per-arm iteration tables (verdict + per-subtype OOS), the OOS trajectory,
the A+B ablation comparison, and a final headroom verdict (the three §5.4 signals).
"""

from __future__ import annotations

import argparse
import os

from qea.loop import Config, acceptance_signals, run_ablation


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
    ap.add_argument("--iters", type=int, default=4)
    ap.add_argument("--k", type=int, default=2)
    ap.add_argument("--b-n", type=int, default=12)
    ap.add_argument("--results-dir", default="results/latest")
    args = ap.parse_args()

    mock = not args.real  # mock is the default
    if mock:
        os.environ["MOCK_LLM"] = "1"

    cfg = Config(mock=mock, n_iters=args.iters, k=args.k, b_n=args.b_n, results_dir=args.results_dir)
    print(f"[run] mode={'MOCK' if mock else 'REAL'} iters={cfg.n_iters} k={cfg.k} -> {cfg.results_dir}")
    abl = run_ablation(cfg)

    _print_arm(abl.arm1)
    _print_arm(abl.arm2)

    print("\n=== ABLATION (Arm1 A-only vs Arm2 A+B) ===")
    for key, val in abl.comparison.items():
        print(f"  {key}: {val}")

    print("\n=== HEADROOM VERDICT (the three §5.4 signals, on Arm1) ===")
    sig = acceptance_signals(abl.arm1)
    for name, ok in sig.items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    overall = all(sig.values())
    tag = "MOCK" if mock else "REAL"
    print(f"\n  ==> HEADROOM {'CONFIRMED' if overall else 'NOT CONFIRMED'} ({tag}): "
          f"evolutionary harness has leverage on this quant family."
          if overall else
          f"\n  ==> HEADROOM NOT CONFIRMED ({tag}): see failing signals above.")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
