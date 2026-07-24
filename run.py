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
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from qea.loop import Config, acceptance_signals, run_synthetic_fixture, run_gdpval_soft
from qea.loop_levelb import LevelBConfig, run_gdpval_levelb


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="QEA v0 — evolving quant agent")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--mock", action="store_true", help="offline scripted smoke test (default)")
    mode.add_argument("--real", action="store_true", help="real OpenRouter run (needs .env)")
    mode.add_argument("--levelb", action="store_true",
                      help="real mode: Level-B evolution (file-editing evolve agent edits the NexAU worker dir)")
    ap.add_argument("--benchmark", choices=("qfbench",), help="run a benchmark-specific evolution path")
    ap.add_argument("--executor", choices=("e2b",), default="e2b")
    ap.add_argument("--qfbench-root", type=Path)
    ap.add_argument("--qfbench-manifest", type=Path, default=Path("data/qfbench/MANIFEST.json"))
    ap.add_argument("--template-manifest-dir", type=Path)
    ap.add_argument("--run-id", help="stable run ID; required to resume a QFBench run")
    ap.add_argument("--concurrency", type=int, default=3,
                    help="QFBench task attempts evaluated concurrently")
    ap.add_argument("--global-e2b-cap", type=int, default=12,
                    help="shared worker+verifier sandbox lease cap")
    ap.add_argument("--approve-external-run", action="store_true",
                    help="acknowledge paid E2B use and public-task/model-provider data egress")
    ap.add_argument("--allow-verifier-network", action="store_true",
                    help="canary only: allow verifier network while dependencies are not yet baked")
    ap.add_argument("--worker-no-internet", action="store_true",
                    help="disable all worker network (requires an in-sandbox/local model endpoint)")
    ap.add_argument("--iters", type=int, default=None)
    ap.add_argument("--k", type=int, default=2)
    ap.add_argument("--core", action="store_true", help="real mode: ~25 core finance occupations instead of ~30 broad")
    ap.add_argument("--resume", action="store_true", help="continue a prior run from its checkpoint")
    ap.add_argument("--n-tasks", type=int, default=5, help="levelb: number of GDPval tasks per iteration")
    ap.add_argument("--results-dir", default="results/latest")
    return ap


def resolve_iterations(args) -> int:
    if args.benchmark == "qfbench":
        iterations = 3 if args.iters is None else args.iters
        if iterations not in {3, 5}:
            raise ValueError("QFBench pilot --iters must be 3 or 5")
        return iterations
    return 4 if args.iters is None else args.iters


def estimate_qfbench_attempts(
    optimize_count: int,
    held_out_count: int,
    iterations: int,
) -> int:
    if optimize_count < 1 or held_out_count < 1 or iterations not in {3, 5}:
        raise ValueError("invalid QFBench attempt schedule")
    return optimize_count * (iterations + 1) + held_out_count * 2


def load_template_ids(
    manifest_dir: str | Path,
    tasks,
    *,
    benchmark_commit: str,
) -> tuple[dict[str, str], dict[str, str]]:
    root = Path(manifest_dir).resolve()
    by_role: dict[str, dict[str, str]] = {"worker": {}, "verifier": {}}
    for task in tasks:
        for role in ("worker", "verifier"):
            path = root / f"{task.task_id}.{role}.image.json"
            if not path.is_file():
                raise ValueError(f"missing template manifest {path}")
            payload = json.loads(path.read_text())
            expected = (benchmark_commit, task.task_id, role)
            actual = (
                payload.get("benchmark_commit"), payload.get("task_id"), payload.get("role")
            )
            if actual != expected:
                raise ValueError(f"template manifest identity mismatch in {path}")
            if all(
                hasattr(task, attribute)
                for attribute in ("cpus", "memory_mb", "build_timeout_seconds")
            ):
                expected_resources = (
                    task.cpus,
                    task.memory_mb,
                    task.build_timeout_seconds,
                )
                actual_resources = (
                    payload.get("cpu_count"),
                    payload.get("memory_mb"),
                    payload.get("build_timeout_seconds"),
                )
                if actual_resources != expected_resources:
                    raise ValueError(
                        f"template manifest resource mismatch in {path}: "
                        f"expected {expected_resources}, found {actual_resources}"
                    )
            base_image = str(payload.get("base_image", ""))
            base_template_id = payload.get("base_template_id")
            base_build_id = payload.get("base_build_id")
            registry_pinned = "@sha256:" in base_image
            e2b_base_pinned = all(
                isinstance(value, str) and value
                for value in (base_template_id, base_build_id)
            )
            if not registry_pinned and not e2b_base_pinned:
                raise ValueError(f"template manifest has no immutable base in {path}")
            template_id = payload.get("published_template_id")
            if not isinstance(template_id, str) or not template_id:
                raise ValueError(f"template manifest is not published: {path}")
            if e2b_base_pinned:
                build_id = payload.get("published_build_id")
                if not isinstance(build_id, str) or not build_id:
                    raise ValueError(f"template manifest has no published build ID: {path}")
            by_role[role][task.task_id] = template_id
    return by_role["worker"], by_role["verifier"]


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


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)

    _load_dotenv()

    if args.benchmark == "qfbench":
        return _run_qfbench(args)

    iterations = resolve_iterations(args)

    if args.levelb:
        lcfg = LevelBConfig(n_iters=iterations, k=args.k, n_tasks=args.n_tasks,
                            broad=not args.core, results_dir=args.results_dir)
        print(f"[run] mode=LEVEL-B (NexAU worker dir evolved by a file-editing evolve agent) "
              f"iters={lcfg.n_iters} k={lcfg.k} n_tasks={lcfg.n_tasks} -> {lcfg.results_dir}")
        res = run_gdpval_levelb(lcfg)
        _print_levelb(res)
        rose = res.mean_score_trajectory[-1] > res.mean_score_trajectory[0] + res.noise_margin
        print(f"\n  ==> LEVEL-B HEADROOM {'OBSERVED' if rose else 'NOT OBSERVED'}: "
              f"mean {res.mean_score_trajectory[0]:.3f} -> {res.mean_score_trajectory[-1]:.3f} "
              f"(noise floor {res.noise_margin:.3f}), {res.n_kept} edit(s) kept.")
        return 0 if rose else 1
    mock = not args.real  # mock is the default
    if mock:
        os.environ["MOCK_LLM"] = "1"
    cfg = Config(mock=mock, n_iters=iterations, k=args.k,
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


def _run_qfbench(args) -> int:
    from qea.benchmarks.qfbench import load_qfbench_snapshot
    from qea.e2b_lease import E2BLeasePool
    from qea.executors.e2b_nexau import E2BNexAUConfig, E2BNexAUExecutor, E2BQFBenchVerifier
    from qea.loop_benchmark import (
        BenchmarkEvolutionConfig,
        QFBenchE2BEvaluator,
        run_benchmark_evolution,
    )

    if args.mock or args.real or args.levelb:
        raise ValueError("--benchmark qfbench cannot be combined with legacy mode flags")
    if args.qfbench_root is None:
        raise ValueError("--qfbench-root is required for QFBench")
    if args.template_manifest_dir is None:
        raise ValueError("--template-manifest-dir is required for QFBench E2B")
    if args.resume and not args.run_id:
        raise ValueError("--run-id is required with --resume")
    iterations = resolve_iterations(args)
    if args.concurrency < 1 or args.global_e2b_cap < 1:
        raise ValueError("QFBench concurrency and global E2B cap must be positive")

    snapshot = load_qfbench_snapshot(
        args.qfbench_root, manifest_path=args.qfbench_manifest
    )
    run_id = args.run_id or datetime.now(timezone.utc).strftime("qfbench-%Y%m%dT%H%M%SZ")
    estimated_attempts = estimate_qfbench_attempts(
        len(snapshot.optimize.tasks),
        len(snapshot.held_out.tasks),
        iterations,
    )
    print("[qfbench] resolved pilot")
    print(f"  commit: {snapshot.commit}")
    print(f"  optimize: {', '.join(snapshot.optimize.task_ids)}")
    print(f"  promotion held-out (seed/final only): {', '.join(snapshot.held_out.task_ids)}")
    print(f"  iterations: {iterations}; estimated task attempts: {estimated_attempts}")
    print(f"  verifier network: {'CANARY ENABLED' if args.allow_verifier_network else 'disabled'}")
    if not args.approve_external_run:
        print("  NOT STARTED: pass --approve-external-run to authorize paid E2B and model-provider egress")
        return 2

    worker_templates, verifier_templates = load_template_ids(
        args.template_manifest_dir,
        snapshot.tasks,
        benchmark_commit=snapshot.commit,
    )
    model_key = os.environ.get("LLM_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
    if not model_key:
        raise ValueError("LLM_API_KEY or OPENROUTER_API_KEY is required for QFBench E2B")
    model_env = {
        "LLM_API_KEY": model_key,
        "LLM_BASE_URL": os.environ.get(
            "LLM_BASE_URL", os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        ),
        "LLM_MODEL": os.environ.get("LLM_MODEL", "deepseek/deepseek-v4-pro"),
    }

    results_root = Path(args.results_dir).resolve()
    leases = E2BLeasePool(
        results_root / ".e2b-leases",
        max_leases=args.global_e2b_cap,
    )
    e2b_config = E2BNexAUConfig(
        worker_templates=worker_templates,
        verifier_templates=verifier_templates,
        worker_allow_internet=not args.worker_no_internet,
        verifier_allow_internet=args.allow_verifier_network,
    )
    executor = E2BNexAUExecutor(e2b_config, lease_pool=leases)
    verifier = E2BQFBenchVerifier(e2b_config, lease_pool=leases)
    evaluator = QFBenchE2BEvaluator(
        benchmark_commit=snapshot.commit,
        run_id=run_id,
        executor=executor,
        verifier=verifier,
        model_env=model_env,
        max_workers=args.concurrency,
    )
    result = run_benchmark_evolution(
        BenchmarkEvolutionConfig(
            run_id=run_id,
            n_iters=iterations,
            results_dir=results_root,
            seed_worker_dir=Path("qea/worker_gdpval_weak"),
            concurrency=args.concurrency,
            resume=args.resume,
        ),
        optimize_tasks=snapshot.optimize.tasks,
        held_out_tasks=snapshot.held_out.tasks,
        benchmark_commit=snapshot.commit,
        evaluator=evaluator,
    )
    _print_qfbench(result)
    return 0


def _print_qfbench(result) -> None:
    print(f"\n=== QFBench E2B evolution: {result.run_id} ===")
    print(f"  optimize domain-macro trajectory: {result.optimize_trajectory}")
    print(
        f"  promotion held-out: {result.held_out_seed.overall:.4f} -> "
        f"{result.held_out_final.overall:.4f} (not used for mutation selection)"
    )
    for record in result.records:
        print(
            f"  iter {record.iteration}: {'keep' if record.kept else 'rollback'} "
            f"{record.incumbent_before:.4f}->{record.candidate_overall:.4f} | {record.reason}"
        )
    print(f"  final worker: {result.final_worker_dir}")
    print(f"  artifacts: {result.run_dir}")


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
    print(f"\n=== Level-B evolution ({res.n_tasks} GDPval tasks, multimodal-grade gate) ===")
    print(f"  noise floor (gain a candidate must beat): {res.noise_margin}")
    print(f"  mean multimodal-score trajectory: {res.mean_score_trajectory}")
    print(f"  {'iter':>4} {'verdict':<16} {'kept':<8} inc->cand")
    for r in res.records:
        flag = "BLOCKED" if r.blocked else ("keep" if r.kept else "rollback")
        print(f"  {r.iteration:>4} {r.verdict:<16} {flag:<8} {r.inc_mean:.3f}->{r.cand_mean:.3f}  | {r.edit_summary}")
    print(f"  final mean multimodal score: {res.final_mean_score}")
    print(f"  final worker dir: {res.final_worker_dir}")
    print(f"  kept/rolledback/blocked: {res.n_kept}/{res.n_rolled_back}/{res.n_blocked}")


if __name__ == "__main__":
    raise SystemExit(main())
