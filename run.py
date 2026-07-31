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
import hashlib
import json
import os
from dataclasses import dataclass, replace
from decimal import Decimal
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
    ap.add_argument(
        "--qfbench-baseline",
        action="store_true",
        help="evaluate one immutable base worker repeatedly without an evolver",
    )
    ap.add_argument(
        "--executor",
        choices=("rootless-docker", "e2b"),
        default="rootless-docker",
    )
    ap.add_argument("--qfbench-root", type=Path)
    ap.add_argument(
        "--qfbench-manifest",
        type=Path,
        default=None,
    )
    ap.add_argument("--template-manifest-dir", type=Path)
    ap.add_argument("--evolver-template-manifest", type=Path)
    ap.add_argument("--rootless-config", type=Path)
    ap.add_argument("--rootless-image-set-manifest", type=Path)
    ap.add_argument("--feedback-mode", choices=("control", "rich"))
    ap.add_argument("--feedback-manifest", type=Path)
    ap.add_argument("--verifier-criteria-map", type=Path)
    ap.add_argument("--run-id", help="stable run ID; required to resume a QFBench run")
    ap.add_argument("--concurrency", type=int, default=None,
                    help="deprecated alias for QFBench worker concurrency")
    ap.add_argument("--worker-concurrency", type=int, default=None,
                    help="QFBench worker-stage concurrency")
    ap.add_argument("--verifier-concurrency", type=int, default=None,
                    help="QFBench verifier-stage concurrency")
    ap.add_argument("--global-e2b-cap", type=int, default=12,
                    help="shared worker+verifier sandbox lease cap")
    ap.add_argument("--approve-external-run", action="store_true",
                    help="acknowledge selected-backend compute and public-task/model-provider data egress")
    ap.add_argument("--allow-verifier-network", action="store_true",
                    help="canary only: allow verifier network while dependencies are not yet baked")
    ap.add_argument("--worker-no-internet", action="store_true",
                    help="disable all worker network (requires an in-sandbox/local model endpoint)")
    ap.add_argument("--iters", type=int, default=None)
    ap.add_argument("--repetitions", type=int, default=None)
    ap.add_argument("--stop-after-repetition", type=int, default=None)
    ap.add_argument("--k", type=int, default=2)
    ap.add_argument("--core", action="store_true", help="real mode: ~25 core finance occupations instead of ~30 broad")
    ap.add_argument("--resume", action="store_true", help="continue a prior run from its checkpoint")
    ap.add_argument("--n-tasks", type=int, default=5, help="levelb: number of GDPval tasks per iteration")
    ap.add_argument("--results-dir", default="results/latest")
    return ap


def resolve_iterations(args) -> int:
    if args.benchmark == "qfbench":
        iterations = 3 if args.iters is None else args.iters
        allowed = {1, 3, 5} if args.executor == "rootless-docker" else {3, 5}
        if iterations not in allowed:
            choices = "1, 3, or 5" if 1 in allowed else "3 or 5"
            raise ValueError(f"QFBench pilot --iters must be {choices}")
        return iterations
    return 4 if args.iters is None else args.iters


def estimate_qfbench_attempts(
    optimize_count: int,
    held_out_count: int,
    iterations: int,
) -> int:
    if optimize_count < 1 or held_out_count < 1 or iterations not in {1, 3, 5}:
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


def load_evolver_template(
    manifest_path: str | Path,
    *,
    benchmark_commit: str,
) -> tuple[str, str]:
    path = Path(manifest_path).resolve()
    if not path.is_file():
        raise ValueError(f"missing evolver template manifest {path}")
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid evolver template manifest {path}: {exc}") from exc
    if (
        payload.get("role") != "evolver"
        or payload.get("benchmark_commit") != benchmark_commit
    ):
        raise ValueError(f"evolver template manifest identity mismatch in {path}")
    if not all(
        isinstance(payload.get(name), str) and payload.get(name)
        for name in (
            "base_template_id",
            "base_build_id",
            "published_template_id",
            "published_build_id",
        )
    ):
        raise ValueError(f"evolver template manifest is not immutably published: {path}")
    identity = payload.get("identity_sha256")
    if (
        not isinstance(identity, str)
        or len(identity) != 64
        or any(character not in "0123456789abcdef" for character in identity)
    ):
        raise ValueError(f"evolver template manifest has no SHA-256 identity: {path}")
    return str(payload["published_template_id"]), identity


def template_set_identity_digest(
    manifest_dir: str | Path,
    tasks,
    evolver_manifest: str | Path,
) -> str:
    root = Path(manifest_dir).resolve()
    records = []
    for task in sorted(tasks, key=lambda item: item.task_id):
        for role in ("worker", "verifier"):
            path = root / f"{task.task_id}.{role}.image.json"
            payload = json.loads(path.read_text())
            records.append({
                "task_id": task.task_id,
                "role": role,
                "identity_sha256": payload.get("identity_sha256"),
                "published_template_id": payload.get("published_template_id"),
                "published_build_id": payload.get("published_build_id"),
            })
    evolver = json.loads(Path(evolver_manifest).resolve().read_text())
    records.append({
        "role": "evolver",
        "identity_sha256": evolver.get("identity_sha256"),
        "published_template_id": evolver.get("published_template_id"),
        "published_build_id": evolver.get("published_build_id"),
    })
    return hashlib.sha256(
        json.dumps(records, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def validate_qfbench_full_harness_args(args) -> None:
    if args.benchmark != "qfbench":
        return
    required = (
        ("feedback_mode", "--feedback-mode"),
        ("feedback_manifest", "--feedback-manifest"),
        ("verifier_criteria_map", "--verifier-criteria-map"),
    )
    for attribute, flag in required:
        if getattr(args, attribute, None) is None:
            raise ValueError(f"{flag} is required for QFBench full-harness evolution")
    if args.executor == "rootless-docker":
        for attribute, flag in (
            ("rootless_config", "--rootless-config"),
            ("rootless_image_set_manifest", "--rootless-image-set-manifest"),
        ):
            if getattr(args, attribute, None) is None:
                raise ValueError(
                    f"{flag} is required for rootless QFBench full-harness evolution"
                )
        if args.allow_verifier_network:
            raise ValueError("rootless verifier network must remain disabled")
        if args.worker_no_internet:
            raise ValueError(
                "--worker-no-internet is E2B-only; rootless workers use proxy-only egress"
            )
        if any(
            getattr(args, name, None) is not None
            for name in (
                "template_manifest_dir",
                "evolver_template_manifest",
            )
        ):
            raise ValueError("rootless execution rejects E2B-only template manifests")
        return
    if args.evolver_template_manifest is None:
        raise ValueError(
            "--evolver-template-manifest is required for QFBench full-harness evolution"
        )


def validate_qfbench_baseline_args(args) -> None:
    """Fail closed when a pure baseline is mixed with evolution or E2B flags."""

    if args.benchmark != "qfbench" or not args.qfbench_baseline:
        raise ValueError("QFBench baseline mode must be selected explicitly")
    if args.executor != "rootless-docker":
        raise ValueError("QFBench baseline currently requires rootless-docker")
    for attribute, flag in (
        ("qfbench_root", "--qfbench-root"),
        ("qfbench_manifest", "--qfbench-manifest"),
        ("rootless_config", "--rootless-config"),
        ("rootless_image_set_manifest", "--rootless-image-set-manifest"),
        ("run_id", "--run-id"),
    ):
        if getattr(args, attribute, None) is None:
            raise ValueError(f"{flag} is required for the QFBench baseline")
    if args.repetitions != 5:
        raise ValueError("QFBench baseline requires exactly five repetitions")
    if args.stop_after_repetition is not None and not (
        1 <= args.stop_after_repetition <= 5
    ):
        raise ValueError("--stop-after-repetition must be between 1 and 5")
    if args.iters is not None:
        raise ValueError("--iters is an evolver-only flag in QFBench baseline mode")
    if any(
        getattr(args, name, None) is not None
        for name in (
            "feedback_mode",
            "feedback_manifest",
            "verifier_criteria_map",
            "template_manifest_dir",
            "evolver_template_manifest",
        )
    ):
        raise ValueError("feedback/evolver-only flags are forbidden in baseline mode")
    if args.allow_verifier_network:
        raise ValueError("rootless verifier network must remain disabled")
    if args.worker_no_internet:
        raise ValueError(
            "--worker-no-internet is E2B-only; rootless workers use proxy-only egress"
        )


def resolve_qfbench_concurrency(args, *, config=None) -> tuple[int, int]:
    """Resolve the compatibility alias into distinct worker/verifier limits."""

    alias = getattr(args, "concurrency", None)
    worker = getattr(args, "worker_concurrency", None)
    verifier = getattr(args, "verifier_concurrency", None)
    if alias is not None and worker is not None and alias != worker:
        raise ValueError(
            "conflicting worker concurrency values: --concurrency and "
            "--worker-concurrency differ"
        )
    resolved_worker = worker if worker is not None else alias
    if resolved_worker is None:
        resolved_worker = getattr(config, "worker_concurrency", 8)
    if verifier is None:
        verifier = getattr(config, "verifier_concurrency", 3)
    for name, value in (
        ("worker concurrency", resolved_worker),
        ("verifier concurrency", verifier),
    ):
        if type(value) is not int or value < 1:
            raise ValueError(f"QFBench {name} must be positive")
    return resolved_worker, verifier


def qfbench_external_run_approval_text(executor: str) -> str:
    if executor == "rootless-docker":
        return "model-provider egress and self-hosted compute"
    if executor == "e2b":
        return "paid E2B and model-provider egress"
    raise ValueError(f"unsupported QFBench executor {executor!r}")


@dataclass(frozen=True)
class _QFBenchRunPlan:
    snapshot: object
    run_id: str
    iterations: int
    estimated_attempts: int
    contract_digest: str
    admission_digest: str
    task_manifest_digest: str
    results_root: Path


@dataclass(frozen=True)
class _QFBenchBaselinePlan:
    snapshot: object
    run_id: str
    repetitions: int
    estimated_attempts: int
    task_manifest_digest: str
    results_root: Path


def _prepare_qfbench_run(args) -> _QFBenchRunPlan:
    """Validate and resolve provider-neutral QFBench run inputs."""

    from qea.benchmarks.qfbench import load_qfbench_snapshot
    from qea.candidate_admission import AdmissionPolicy
    from qea.evolution_feedback import feedback_contract_digest

    if args.mock or args.real or args.levelb:
        raise ValueError("--benchmark qfbench cannot be combined with legacy mode flags")
    validate_qfbench_full_harness_args(args)
    if args.qfbench_root is None:
        raise ValueError("--qfbench-root is required for QFBench")
    if args.resume and not args.run_id:
        raise ValueError("--run-id is required with --resume")
    iterations = resolve_iterations(args)
    manifest_path = args.qfbench_manifest or Path("data/qfbench/MANIFEST_30.json")
    snapshot = load_qfbench_snapshot(args.qfbench_root, manifest_path=manifest_path)
    run_id = args.run_id or datetime.now(timezone.utc).strftime(
        "qfbench-%Y%m%dT%H%M%SZ"
    )
    estimated_attempts = estimate_qfbench_attempts(
        len(snapshot.optimize.tasks),
        len(snapshot.held_out.tasks),
        iterations,
    )
    contract_digest = feedback_contract_digest(
        args.feedback_mode, args.feedback_manifest
    )
    admission_digest = AdmissionPolicy.qfbench_full(
        forbidden_content=sorted(snapshot.held_out.task_ids)
    ).digest()
    task_manifest_digest = hashlib.sha256(
        Path(manifest_path).resolve().read_bytes()
    ).hexdigest()
    return _QFBenchRunPlan(
        snapshot=snapshot,
        run_id=run_id,
        iterations=iterations,
        estimated_attempts=estimated_attempts,
        contract_digest=contract_digest,
        admission_digest=admission_digest,
        task_manifest_digest=task_manifest_digest,
        results_root=Path(args.results_dir).resolve(),
    )


def _prepare_qfbench_baseline_run(args) -> _QFBenchBaselinePlan:
    from qea.benchmarks.qfbench import load_qfbench_baseline_snapshot

    if args.mock or args.real or args.levelb:
        raise ValueError("--benchmark qfbench cannot be combined with legacy mode flags")
    validate_qfbench_baseline_args(args)
    snapshot = load_qfbench_baseline_snapshot(
        args.qfbench_root, manifest_path=args.qfbench_manifest
    )
    task_count = len(snapshot.primary) + len(snapshot.diagnostic)
    if task_count != 85:
        raise ValueError(f"QFBench baseline manifest must resolve 85 tasks, found {task_count}")
    return _QFBenchBaselinePlan(
        snapshot=snapshot,
        run_id=args.run_id,
        repetitions=args.repetitions,
        estimated_attempts=task_count * args.repetitions,
        task_manifest_digest=hashlib.sha256(
            Path(args.qfbench_manifest).resolve().read_bytes()
        ).hexdigest(),
        results_root=Path(args.results_dir).resolve(),
    )


def _print_qfbench_plan(plan, args, *, backend: str) -> None:
    snapshot = plan.snapshot
    print("[qfbench] resolved pilot")
    print(f"  backend: {backend}")
    print(f"  feedback arm: {args.feedback_mode}")
    print(f"  commit: {snapshot.commit}")
    print(f"  optimize: {', '.join(snapshot.optimize.task_ids)}")
    print(
        "  promotion held-out (seed/final only): "
        + ", ".join(snapshot.held_out.task_ids)
    )
    print(
        f"  iterations: {plan.iterations}; "
        f"official scoring attempts: {plan.estimated_attempts}"
    )
    print(f"  feedback contract: {plan.contract_digest}")
    print(f"  admission policy: {plan.admission_digest}")
    print(f"  output: {plan.results_root / plan.run_id}")


def _print_qfbench_baseline_plan(plan, *, backend: str) -> None:
    snapshot = plan.snapshot
    task_count = len(snapshot.primary) + len(snapshot.diagnostic)
    print("[qfbench] resolved repeated base-worker baseline")
    print(f"  backend: {backend}")
    print(f"  commit: {snapshot.commit}")
    print(
        f"  task panels: {len(snapshot.primary)} primary + "
        f"{len(snapshot.diagnostic)} diagnostic = {task_count}"
    )
    print(f"  repetitions: {plan.repetitions}")
    print(f"  official scoring attempts: {plan.estimated_attempts}")
    print(f"  maximum worker/verifier lifecycles: {plan.estimated_attempts * 2}")
    print("  evolver lifecycles: 0")
    print(f"  output: {plan.results_root / plan.run_id}")


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

    if args.benchmark == "qfbench":
        if args.qfbench_baseline:
            return _run_qfbench_rootless_baseline(args)
        if args.executor == "e2b":
            _load_dotenv()
            return _run_qfbench_e2b(args)
        return _run_qfbench_rootless(args)

    _load_dotenv()

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


def _run_qfbench_rootless(args) -> int:
    from qea.loop_benchmark import (
        BenchmarkEvolutionConfig,
        run_benchmark_evolution,
    )
    from qea.rootless_full_harness import (
        build_rootless_full_harness_runtime,
        load_rootless_full_harness_config,
        rootless_model_route_identity,
    )

    plan = _prepare_qfbench_run(args)
    config = load_rootless_full_harness_config(args.rootless_config)
    worker_concurrency, verifier_concurrency = resolve_qfbench_concurrency(
        args, config=config
    )
    config = replace(
        config,
        worker_concurrency=worker_concurrency,
        verifier_concurrency=verifier_concurrency,
    )
    _print_qfbench_plan(plan, args, backend="rootless-docker")
    print("  verifier network: disabled")
    print(f"  model upstream base: {config.upstream_base_url}")
    print(f"  model caller prefix: {config.allowed_path_prefix}")
    print(f"  model identity: {config.allowed_model}")
    approval_surface = qfbench_external_run_approval_text("rootless-docker")
    auto_approved = os.environ.get("QEA_PAID_EVAL_AUTO_APPROVE") == "1"
    if not (args.approve_external_run or auto_approved):
        print(
            "  NOT STARTED: pass --approve-external-run to authorize "
            + approval_surface
        )
        return 2
    print(
        "  execution approval: "
        + ("standing auto-approval" if auto_approved else "explicit CLI approval")
        + f" ({approval_surface})"
    )

    runtime = build_rootless_full_harness_runtime(
        config=config,
        image_set_manifest=args.rootless_image_set_manifest,
        benchmark_commit=plan.snapshot.commit,
        tasks=plan.snapshot.tasks,
        run_id=plan.run_id,
        results_root=plan.results_root,
    )
    try:
        print(f"  runtime backend: {runtime.backend.backend_name}")
        print(f"  image identity: {runtime.image_identity_digest}")
        print(f"  scheduler identity: {runtime.scheduler_identity_digest}")
        print(f"  runtime identity: {runtime.runtime_identity_digest}")

        def secure_proposer(context):
            return runtime.proposer.propose(
                candidate_dir=context.candidate_dir,
                evidence_dir=context.evidence,
                evolver_dir=Path("qea/evolve_agent_full").resolve(),
                diagnosis=context.diagnosis,
                iteration=context.iteration,
                run_id=plan.run_id,
                run_dir=context.run_dir,
            )

        model_identity = rootless_model_route_identity(
            upstream_base_url=config.upstream_base_url,
            allowed_path_prefix=config.allowed_path_prefix,
            allowed_model=config.allowed_model,
        )
        result = run_benchmark_evolution(
            BenchmarkEvolutionConfig(
                run_id=plan.run_id,
                n_iters=plan.iterations,
                results_dir=plan.results_root,
                seed_worker_dir=Path("qea/worker_gdpval_weak"),
                worker_concurrency=worker_concurrency,
                verifier_concurrency=verifier_concurrency,
                scheduler_identity_digest=runtime.scheduler_identity_digest,
                resume=args.resume,
                feedback_mode=args.feedback_mode,
                feedback_contract_digest=plan.contract_digest,
                public_rubric_path=args.feedback_manifest,
                verifier_mapping_path=args.verifier_criteria_map,
                admission_policy_digest=plan.admission_digest,
                task_manifest_digest=plan.task_manifest_digest,
                model_identity=model_identity,
                template_identity_digest=runtime.runtime_identity_digest,
            ),
            optimize_tasks=plan.snapshot.optimize.tasks,
            held_out_tasks=plan.snapshot.held_out.tasks,
            benchmark_commit=plan.snapshot.commit,
            evaluator=runtime.evaluator,
            proposer=secure_proposer,
        )
        _print_qfbench(result, backend=runtime.backend.backend_name)
        return 0
    finally:
        runtime.close()


def _run_qfbench_rootless_baseline(args) -> int:
    from qea.qfbench_baseline import (
        BaselineConfig,
        audit_baseline_proxy_costs,
        run_qfbench_baseline,
    )
    from qea.rootless_full_harness import (
        build_rootless_full_harness_runtime,
        load_rootless_full_harness_config,
        rootless_model_route_identity,
    )

    plan = _prepare_qfbench_baseline_run(args)
    config = load_rootless_full_harness_config(args.rootless_config)
    worker_concurrency, verifier_concurrency = resolve_qfbench_concurrency(
        args, config=config
    )
    config = replace(
        config,
        worker_concurrency=worker_concurrency,
        verifier_concurrency=verifier_concurrency,
    )
    _print_qfbench_baseline_plan(plan, backend="rootless-docker")
    print("  verifier network: disabled")
    print(f"  model upstream base: {config.upstream_base_url}")
    print(f"  model caller prefix: {config.allowed_path_prefix}")
    print(f"  model identity: {config.allowed_model}")
    approval_surface = qfbench_external_run_approval_text("rootless-docker")
    auto_approved = os.environ.get("QEA_PAID_EVAL_AUTO_APPROVE") == "1"
    if not (args.approve_external_run or auto_approved):
        print(
            "  NOT STARTED: pass --approve-external-run to authorize "
            + approval_surface
        )
        return 2
    print(
        "  execution approval: "
        + ("standing auto-approval" if auto_approved else "explicit CLI approval")
        + f" ({approval_surface})"
    )

    runtime = build_rootless_full_harness_runtime(
        config=config,
        image_set_manifest=args.rootless_image_set_manifest,
        benchmark_commit=plan.snapshot.commit,
        tasks=plan.snapshot.tasks,
        run_id=plan.run_id,
        results_root=plan.results_root,
    )
    try:
        print(f"  runtime backend: {runtime.backend.backend_name}")
        print(f"  image identity: {runtime.image_identity_digest}")
        print(f"  scheduler identity: {runtime.scheduler_identity_digest}")
        print(f"  runtime identity: {runtime.runtime_identity_digest}")
        model_identity = rootless_model_route_identity(
            upstream_base_url=config.upstream_base_url,
            allowed_path_prefix=config.allowed_path_prefix,
            allowed_model=config.allowed_model,
        )
        result = run_qfbench_baseline(
            BaselineConfig(
                run_id=plan.run_id,
                repetitions=plan.repetitions,
                results_dir=plan.results_root,
                seed_worker_dir=Path("qea/worker_gdpval_weak"),
                model_identity=model_identity,
                task_manifest_digest=plan.task_manifest_digest,
                runtime_identity_digest=runtime.runtime_identity_digest,
                scheduler_identity_digest=runtime.scheduler_identity_digest,
                template_identity_digest=runtime.image_identity_digest,
                worker_concurrency=worker_concurrency,
                verifier_concurrency=verifier_concurrency,
                resume=args.resume,
            ),
            primary_tasks=plan.snapshot.primary,
            diagnostic_tasks=plan.snapshot.diagnostic,
            benchmark_commit=plan.snapshot.commit,
            evaluator=runtime.evaluator,
            stop_after_repetition=args.stop_after_repetition,
        )
    finally:
        runtime.close()

    completed_repetitions = len(result.repetitions)
    expected_attempts = completed_repetitions * (
        len(plan.snapshot.primary) + len(plan.snapshot.diagnostic)
    )
    cost = audit_baseline_proxy_costs(
        result.run_dir, expected_attempts=expected_attempts
    )
    observed_cost = Decimal(cost["provider_cost_usd"])
    projected_cost = (
        observed_cost / completed_repetitions * plan.repetitions
    )
    print(f"  completed repetitions: {completed_repetitions}/{plan.repetitions}")
    print(
        "  primary domain-macro mean: "
        f"{result.aggregate['primary']['repeat_domain_macro']['mean']:.6f}"
    )
    print(
        f"  provider ledger: {cost['request_count']} requests, "
        f"{cost['total_tokens']} tokens, USD {observed_cost}"
    )
    print(f"  projected five-repetition provider cost: USD {projected_cost}")
    if projected_cost > Decimal("60"):
        print("  continuation cost gate: FAIL (projected total exceeds USD 60)")
        return 3
    print("  continuation cost gate: PASS")
    return 0


def _run_qfbench_e2b(args) -> int:
    from qea.e2b_lease import E2BLeasePool
    from qea.executors.e2b_evolver import (
        E2BEvolverConfig,
        E2BFullHarnessProposer,
    )
    from qea.executors.e2b_nexau import E2BNexAUConfig, E2BNexAUExecutor, E2BQFBenchVerifier
    from qea.loop_benchmark import (
        BenchmarkEvolutionConfig,
        QFBenchE2BEvaluator,
        run_benchmark_evolution,
    )

    plan = _prepare_qfbench_run(args)
    if args.template_manifest_dir is None:
        raise ValueError("--template-manifest-dir is required for QFBench E2B")
    worker_concurrency, verifier_concurrency = resolve_qfbench_concurrency(args)
    if args.global_e2b_cap < 1:
        raise ValueError("QFBench global E2B cap must be positive")

    snapshot = plan.snapshot
    run_id = plan.run_id
    iterations = plan.iterations
    estimated_attempts = plan.estimated_attempts
    worker_templates, verifier_templates = load_template_ids(
        args.template_manifest_dir,
        snapshot.tasks,
        benchmark_commit=snapshot.commit,
    )
    evolver_template, evolver_identity = load_evolver_template(
        args.evolver_template_manifest,
        benchmark_commit=snapshot.commit,
    )
    contract_digest = plan.contract_digest
    admission_digest = plan.admission_digest
    task_manifest_digest = plan.task_manifest_digest
    template_identity = template_set_identity_digest(
        args.template_manifest_dir,
        snapshot.tasks,
        args.evolver_template_manifest,
    )
    max_lifecycles = estimated_attempts * 2 + iterations
    _print_qfbench_plan(plan, args, backend="e2b")
    print(f"  maximum worker/verifier/evolver lifecycles: {max_lifecycles}")
    print(f"  evolver template: {evolver_template} ({evolver_identity})")
    print(f"  task templates: {len(worker_templates)} worker + {len(verifier_templates)} verifier")
    print(f"  verifier network: {'CANARY ENABLED' if args.allow_verifier_network else 'disabled'}")
    auto_approved = os.environ.get("QEA_PAID_EVAL_AUTO_APPROVE") == "1"
    if not (args.approve_external_run or auto_approved):
        print("  NOT STARTED: pass --approve-external-run to authorize paid E2B and model-provider egress")
        return 2
    print(
        "  paid execution approval: "
        + ("standing auto-approval" if auto_approved else "explicit CLI approval")
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

    results_root = plan.results_root
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
        worker_concurrency=worker_concurrency,
        verifier_concurrency=verifier_concurrency,
    )
    evolver = E2BFullHarnessProposer(
        E2BEvolverConfig(template=evolver_template),
        lease_pool=leases,
    )

    def secure_proposer(context):
        return evolver.propose(
            candidate_dir=context.candidate_dir,
            evidence_dir=context.evidence.root,
            evolver_dir=Path("qea/evolve_agent_full").resolve(),
            diagnosis=json.dumps(
                context.diagnosis, sort_keys=True, separators=(",", ":")
            ),
            iteration=context.iteration,
            run_id=run_id,
            run_dir=context.run_dir,
            model_env=model_env,
        )

    result = run_benchmark_evolution(
        BenchmarkEvolutionConfig(
            run_id=run_id,
            n_iters=iterations,
            results_dir=results_root,
            seed_worker_dir=Path("qea/worker_gdpval_weak"),
            concurrency=worker_concurrency,
            verifier_concurrency=verifier_concurrency,
            resume=args.resume,
            feedback_mode=args.feedback_mode,
            feedback_contract_digest=contract_digest,
            public_rubric_path=args.feedback_manifest,
            verifier_mapping_path=args.verifier_criteria_map,
            admission_policy_digest=admission_digest,
            task_manifest_digest=task_manifest_digest,
            model_identity=model_env["LLM_MODEL"],
            template_identity_digest=template_identity,
        ),
        optimize_tasks=snapshot.optimize.tasks,
        held_out_tasks=snapshot.held_out.tasks,
        benchmark_commit=snapshot.commit,
        evaluator=evaluator,
        proposer=secure_proposer,
    )
    _print_qfbench(result, backend="e2b")
    return 0


def _print_qfbench(result, *, backend: str = "e2b") -> None:
    print(f"\n=== QFBench {backend} evolution: {result.run_id} ===")
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
