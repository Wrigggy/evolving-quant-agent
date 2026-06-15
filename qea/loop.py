"""The evolve -> falsify -> rollback driver + the 2-arm ablation.

Per iteration: evaluate the incumbent harness with the hard verifier (and, in
Arm 2, the soft judge) -> diagnose (ADB-lite) -> evolve_agent proposes ONE edit
(L_t = 1) -> if the rejected-edit buffer blocks it, skip; else apply to a clone,
re-evaluate, falsify (verdict), and keep (strict gate) or rollback (+ buffer).
Three layers are persisted each iteration.

Arm 1 (iron-law-2 clean): evolve on A only -> freeze -> transfer-eval on B.
Arm 2 (relaxes iron law 2): evolve on A+B (soft B in the loop). The comparison
is the ablation: does soft-B in the loop help, or just add falsification noise?
"""

from __future__ import annotations

import concurrent.futures
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .agents import diagnose, evolve_agent_propose, quant_agent_solve
from .falsify import (
    EvalSummary,
    LEAKAGE_BLOCKED,
    RejectedEditBuffer,
    compute_diff,
    decide_keep,
    decide_keep_soft,
    evaluate_changes,
)
from .harness import Harness, seed_harness
from .llm import make_llm
from .manifest import attach_verdict, build_manifest
from .observability import ExperimentDir, eval_to_dict
from .tasks import load_gdpval_a_pile, load_gdpval_b_pile, load_gdpval_finance, rubric_corpus
from .verifier import HardVerifier, LeakageGuard, SoftJudge, TaskResult


@dataclass
class Config:
    mock: bool = True
    n_iters: int = 4          # mock scripted sequence needs 4
    k: int = 2                # k-repeat denoise
    b_n: int = 12             # real B-pile sample size
    gdpval_broad: bool = True  # ~30 broad finance occupations vs ~25 core
    resume: bool = False       # continue a prior gdpval_soft run from its checkpoint
    results_dir: str = "results/latest"


@dataclass
class IterationRecord:
    iteration: int
    blocked: bool
    verdict: str
    kept: bool
    edit_summary: str
    edit_slot: str
    edit_component: str
    root_cause_tag: str
    diagnosis_overview: str
    incumbent_oos: int
    per_subtype: dict
    cand_oos: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ArmResult:
    arm: str
    oos_trajectory: list[int]
    records: list[IterationRecord]
    final_harness_summary: dict
    final_oos: int
    final_per_subtype: dict
    b_transfer: dict
    b_baseline: dict
    mean_eval_variance: float
    n_kept: int
    n_rolled_back: int
    n_blocked: int
    wall_unfixed: bool = True

    def to_dict(self) -> dict:
        d = asdict(self)
        d["records"] = [r.to_dict() if isinstance(r, IterationRecord) else r for r in self.records]
        return d


@dataclass
class AblationResult:
    arm1: ArmResult
    arm2: ArmResult
    comparison: dict = field(default_factory=dict)


class _DeliverableCache:
    """Caches a worker deliverable by (task_id, harness signature) so the same
    harness always produces the same text within a run — removes the regeneration
    noise that caused single-sample regression-to-mean in the % gate."""
    def __init__(self) -> None:
        self._d: dict[tuple[str, str], str] = {}

    def get_or_make(self, task_id: str, harness, make) -> str:
        key = (task_id, harness.signature())
        if key not in self._d:
            self._d[key] = make()
        return self._d[key]


def _score_one(task, harness, *, mock, llm, hard, soft, k, cache=None):
    if task.pile == "B" and cache is not None and not mock:
        solution = cache.get_or_make(task.task_id, harness,
                                     lambda: quant_agent_solve(task, harness, mock=mock, llm=llm))
    else:
        solution = quant_agent_solve(task, harness, mock=mock, llm=llm)
    if task.pile == "A":
        return task.task_id, hard.score(task, solution, harness, mock=mock, k=k), solution
    return task.task_id, soft.score(task, solution, harness, mock=mock, k=k), solution


def evaluate(harness, tasks, *, mock, llm, hard, soft, k, label: str = "", cache=None) -> EvalSummary:
    """Score every task. Mock runs sequentially (instant, deterministic); real runs
    concurrently (<= QEA_MAX_CONCURRENCY) so 30 LLM-bound tasks finish in minutes,
    and a single task's failure/timeout degrades to a 0 rather than killing the eval.
    B-pile deliverable texts are retained for the B-pile debugger's critic."""
    results: dict = {}
    deliverables: dict = {}
    if mock or len(tasks) <= 1:
        for t in tasks:
            tid, res, sol = _score_one(t, harness, mock=mock, llm=llm, hard=hard, soft=soft, k=k, cache=cache)
            results[tid] = res
            if t.pile == "B":
                deliverables[tid] = sol if isinstance(sol, str) else ""
        return EvalSummary(results, deliverables)

    mw = max(1, min(int(os.environ.get("QEA_MAX_CONCURRENCY", "8")), 16))
    done, total = 0, len(tasks)
    with concurrent.futures.ThreadPoolExecutor(max_workers=mw) as ex:
        futs = {ex.submit(_score_one, t, harness, mock=mock, llm=llm, hard=hard, soft=soft, k=k, cache=cache): t
                for t in tasks}
        for fut in concurrent.futures.as_completed(futs):
            t = futs[fut]
            try:
                tid, res, sol = fut.result()
                results[tid] = res
                if t.pile == "B":
                    deliverables[tid] = sol if isinstance(sol, str) else ""
            except Exception as exc:  # noqa: BLE001 - one task must not kill the eval
                results[t.task_id] = TaskResult(t.task_id, t.subtype, t.pile, False, False, False, 0.0, 0.0,
                                                f"eval error: {type(exc).__name__}: {exc}")
            done += 1
            if label and (done % 5 == 0 or done == total):
                print(f"[eval {label}] {done}/{total} scored", flush=True)
    return EvalSummary(results, deliverables)


def _failure_pattern(evaluation: dict, edit) -> str:
    if evaluation["verdict"] == "HARMFUL":
        return "broke previously-passing tasks"
    if edit.component_name == "overfit_cache":
        return "memorized base inputs but failed the perturbation probe"
    return "no OOS improvement on the hard verifier"


def run_arm(arm, a_tasks, b_tasks, *, cfg, llm, hard, soft, expdir, b_baseline) -> ArmResult:
    eval_set = a_tasks if arm == "arm1_A_only" else (a_tasks + b_tasks)
    buffer = RejectedEditBuffer()
    incumbent = seed_harness()
    inc_eval = evaluate(incumbent, eval_set, mock=cfg.mock, llm=llm, hard=hard, soft=soft, k=cfg.k)

    oos_traj = [inc_eval.total_oos()]
    variances = [inc_eval.mean_variance()]
    records: list[IterationRecord] = []
    n_kept = n_rb = n_blocked = 0

    for it in range(1, cfg.n_iters + 1):
        diag = diagnose(inc_eval, mock=cfg.mock, llm=llm)
        edit = evolve_agent_propose(it, inc_eval, diag, incumbent, buffer, mock=cfg.mock, llm=llm)

        if edit is None:
            # real-mode fail-safe: no valid single edit parsed -> no-op iteration
            records.append(IterationRecord(
                iteration=it, blocked=True, verdict="NO_EDIT", kept=False,
                edit_summary="(no valid edit proposed)", edit_slot="", edit_component="",
                root_cause_tag=diag.get("root_cause_tag", ""), diagnosis_overview=diag.get("overview", ""),
                incumbent_oos=inc_eval.total_oos(), per_subtype=inc_eval.per_subtype(),
                cand_oos=inc_eval.total_oos(),
            ))
            oos_traj.append(inc_eval.total_oos())
            expdir.persist_iteration(arm, {
                "iteration": it, "eval": None, "diagnosis": diag,
                "manifest": {"blocked": True, "reason": "no valid edit parsed"}, "workspace": incumbent.summary(),
            })
            continue

        if buffer.blocks(edit):
            n_blocked += 1
            rec = IterationRecord(
                iteration=it, blocked=True, verdict="BLOCKED", kept=False,
                edit_summary=edit.summary, edit_slot=edit.slot, edit_component=edit.component_name,
                root_cause_tag=diag.get("root_cause_tag", ""), diagnosis_overview=diag.get("overview", ""),
                incumbent_oos=inc_eval.total_oos(), per_subtype=inc_eval.per_subtype(),
                cand_oos=inc_eval.total_oos(),
            )
            records.append(rec)
            oos_traj.append(inc_eval.total_oos())
            expdir.persist_iteration(arm, {
                "iteration": it, "eval": None, "diagnosis": diag,
                "manifest": {"blocked": True, "reason": "rejected-edit buffer", "edit": edit.signature()},
                "workspace": incumbent.summary(),
            })
            continue

        candidate = incumbent.clone()
        candidate.apply(edit)
        cand_eval = evaluate(candidate, eval_set, mock=cfg.mock, llm=llm, hard=hard, soft=soft, k=cfg.k)
        diff = compute_diff(inc_eval, cand_eval)
        evaluation = evaluate_changes(edit, diff)
        kept = decide_keep(evaluation, inc_eval.total_oos(), cand_eval.total_oos())

        manifest = build_manifest(it, "evolve_agent", edit, arm)
        manifest = attach_verdict(manifest, evaluation, kept)

        if kept:
            n_kept += 1
            incumbent, inc_eval = candidate, cand_eval
        else:
            n_rb += 1
            buffer.add(edit, evaluation["verdict"], inc_eval.total_oos(), cand_eval.total_oos(), _failure_pattern(evaluation, edit))

        variances.append(cand_eval.mean_variance())
        oos_traj.append(inc_eval.total_oos())
        records.append(IterationRecord(
            iteration=it, blocked=False, verdict=evaluation["verdict"], kept=kept,
            edit_summary=edit.summary, edit_slot=edit.slot, edit_component=edit.component_name,
            root_cause_tag=diag.get("root_cause_tag", ""), diagnosis_overview=diag.get("overview", ""),
            incumbent_oos=inc_eval.total_oos(), per_subtype=inc_eval.per_subtype(),
            cand_oos=cand_eval.total_oos(),
        ))
        expdir.persist_iteration(arm, {
            "iteration": it, "eval": eval_to_dict(cand_eval), "diagnosis": diag,
            "manifest": manifest, "workspace": incumbent.summary(),
        })

    # freeze + transfer eval on B
    b_eval = evaluate(incumbent, b_tasks, mock=cfg.mock, llm=llm, hard=hard, soft=soft, k=cfg.k)
    b_transfer = {"mean_score": _mean_score(b_eval), "n_oos": b_eval.total_oos(), "n": len(b_tasks)}

    # iron law 1: the capability-wall task must remain unfixed by the evolved harness
    wall_unfixed = not any("wall" in tid for tid in inc_eval.oos_ids())

    result = ArmResult(
        arm=arm, oos_trajectory=oos_traj, records=records,
        final_harness_summary=incumbent.summary(), final_oos=inc_eval.total_oos(),
        final_per_subtype=inc_eval.per_subtype(), b_transfer=b_transfer, b_baseline=b_baseline,
        mean_eval_variance=sum(variances) / len(variances), n_kept=n_kept, n_rolled_back=n_rb, n_blocked=n_blocked,
        wall_unfixed=wall_unfixed,
    )
    expdir.persist_arm(arm, result.to_dict())
    return result


def _mean_score(eval_summary) -> float:
    if not eval_summary.results:
        return 0.0
    return sum(r.score for r in eval_summary.results.values()) / len(eval_summary.results)


def acceptance_signals(arm: ArmResult) -> dict:
    """The three §5.4 mechanism signals, evaluated on one arm's record."""
    recs = arm.records
    # 1. causal connectivity (Case A): iter1 diagnosis -> edit -> workspace -> verdict all align
    causal = bool(
        recs and recs[0].root_cause_tag == "Hardcoding" and recs[0].verdict == "EFFECTIVE"
        and recs[0].kept and "integrity_guard" in arm.final_harness_summary.get("validator", [])
    )
    # 2. OOS monotonic rise (headroom) — trajectory updated every iteration,
    #    non-decreasing (rollbacks prevent regression), and a strict rise occurred
    traj = arm.oos_trajectory
    non_decreasing = all(traj[i] <= traj[i + 1] for i in range(len(traj) - 1))
    monotonic = len(traj) >= 2 and non_decreasing and max(traj) > min(traj)
    # 3. falsification correctly rolls back harmful / overfit, and buffer blocks repeats
    harmful_rolled = any(r.verdict == "HARMFUL" and not r.kept for r in recs)
    ineffective_rolled = any(r.verdict == "INEFFECTIVE" and not r.kept for r in recs)
    blocked = any(r.verdict == "BLOCKED" for r in recs)
    correct_rollback = harmful_rolled and ineffective_rolled and blocked
    return {
        "causal_loop": causal,
        "monotonic_oos": monotonic,
        "correct_rollback": correct_rollback,
        "capability_wall_unfixed": arm.wall_unfixed,  # iron law 1
    }


@dataclass
class SoftRunResult:
    n_tasks: int
    oos_trajectory: list[int]
    mean_score_trajectory: list[float]   # the GATE signal now (was diagnostic)
    records: list[IterationRecord]
    final_per_occupation: dict
    final_mean_score: float
    n_kept: int
    n_rolled_back: int
    n_blocked: int
    noise_margin: float = 0.0
    final_per_occupation_mean: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["records"] = [r.to_dict() if isinstance(r, IterationRecord) else r for r in self.records]
        return d


def _write_resume(path: Path, last_iter, incumbent, noise_margin, buffer, records, oos_traj, ms_traj,
                  n_kept, n_rb, n_blocked) -> None:
    """Checkpoint the full run state after each iteration so --resume can continue."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "last_iter": last_iter, "incumbent": incumbent.to_state(), "noise_margin": noise_margin,
        "buffer": buffer.entries, "records": [r.to_dict() for r in records],
        "oos_traj": oos_traj, "ms_traj": ms_traj,
        "n_kept": n_kept, "n_rolled_back": n_rb, "n_blocked": n_blocked,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def run_gdpval_soft(cfg: Config) -> SoftRunResult:
    """Evolve a harness DIRECTLY on the original GDPval finance tasks. Relaxes iron
    law 2 (soft signal in the loop) by explicit user choice — there is no hard
    verifier for original GDPval deliverables.

    DECISION SIGNAL: the aggregate mean rubric score. Keep a candidate only if its
    mean score beats the incumbent's by more than the estimated eval noise floor
    (the gap between two fresh evals of the SAME seed harness — the regeneration +
    judge noise an edit must clear). The verdict taxonomy (evaluate_changes) is
    retained as an audit trail. Per-occupation deltas honor iron law 4."""
    llm = make_llm(cfg.mock)
    hard, soft = HardVerifier(), SoftJudge(llm)
    tasks = load_gdpval_finance(broad=cfg.gdpval_broad, allow_download=not cfg.mock)
    cache = _DeliverableCache()
    guard = LeakageGuard(rubric_corpus(tasks))
    expdir = ExperimentDir(cfg.results_dir)
    arm_dir = Path(cfg.results_dir) / "gdpval_soft"
    resume_path = arm_dir / "resume.json"
    buffer = RejectedEditBuffer()
    records: list[IterationRecord] = []
    n_kept = n_rb = n_blocked = 0
    start_iter = 1

    if cfg.resume and resume_path.exists():
        st = json.loads(resume_path.read_text())
        incumbent = Harness.from_state(st["incumbent"])
        noise_margin = st["noise_margin"]
        oos_traj, ms_traj = list(st["oos_traj"]), list(st["ms_traj"])
        n_kept, n_rb, n_blocked = st["n_kept"], st["n_rolled_back"], st["n_blocked"]
        for e in st.get("buffer", []):
            buffer._sigs.add(e["signature"]); buffer.entries.append(e)
        records = [IterationRecord(**r) for r in st["records"]]
        start_iter = st["last_iter"] + 1
        inc_eval = evaluate(incumbent, tasks, mock=cfg.mock, llm=llm, hard=hard, soft=soft, k=cfg.k, label="resume", cache=cache)
        print(f"[resume] checkpoint at iter {start_iter}; incumbent slots={incumbent.summary()}; "
              f"noise={noise_margin}", flush=True)
    elif cfg.resume and arm_dir.exists():
        # older run without a checkpoint: only a SEED incumbent is safely
        # reconstructable (a kept edit would need its full content).
        done = sorted(int(p.name.split("_")[1]) for p in arm_dir.glob("iteration_*") if (p / "change_manifest.json").exists())
        kept_iters, noise_margin = [], 0.0
        for i in done:
            m = json.loads((arm_dir / f"iteration_{i:03d}" / "change_manifest.json").read_text())
            if m.get("verification", {}).get("verdict") == "keep":
                kept_iters.append(i)
            noise_margin = noise_margin or m.get("verification", {}).get("result", {}).get("soft_gate", {}).get("noise_margin", 0.0)
        if kept_iters:
            raise SystemExit(f"[resume] iters {kept_iters} were KEPT; cannot rebuild a non-seed incumbent without a checkpoint — re-run fresh.")
        incumbent = seed_harness()
        start_iter = (max(done) + 1) if done else 1
        noise_margin = noise_margin or 0.0276
        inc_eval = evaluate(incumbent, tasks, mock=cfg.mock, llm=llm, hard=hard, soft=soft, k=cfg.k, label="resume-seed", cache=cache)
        oos_traj = [inc_eval.total_oos()]
        ms_traj = [round(_mean_score(inc_eval), 4)]
        print(f"[resume] no checkpoint; incumbent=SEED (0 edits kept in iters 1-{max(done) if done else 0}); "
              f"reusing noise floor {noise_margin}; continuing at iter {start_iter} (prior iters in docs/PARTIAL_RUN)", flush=True)
    else:
        incumbent = seed_harness()
        inc_eval = evaluate(incumbent, tasks, mock=cfg.mock, llm=llm, hard=hard, soft=soft, k=cfg.k, label="seed", cache=cache)
        # Noise floor: a 2nd fresh eval of the SAME seed harness; the gap between two
        # same-harness samples = the regeneration+judge noise an edit must beat.
        noise_eval = evaluate(incumbent, tasks, mock=cfg.mock, llm=llm, hard=hard, soft=soft, k=cfg.k, label="seed-noise", cache=cache)
        noise_margin = max(0.01, abs(_mean_score(inc_eval) - _mean_score(noise_eval)))
        print(f"[soft-gate] rubric-score noise floor {noise_margin:.4f} "
              f"(mean-score gain a candidate must beat)", flush=True)
        oos_traj = [inc_eval.total_oos()]
        ms_traj = [round(_mean_score(inc_eval), 4)]

    for it in range(start_iter, cfg.n_iters + 1):
        diag = diagnose(inc_eval, tasks, mock=cfg.mock, llm=llm)
        edit = evolve_agent_propose(it, inc_eval, diag, incumbent, buffer, mock=cfg.mock, llm=llm)

        if edit is not None and guard.is_leak(edit):
            n_blocked += 1
            records.append(IterationRecord(
                iteration=it, blocked=True, verdict=LEAKAGE_BLOCKED, kept=False,
                edit_summary=edit.summary, edit_slot=edit.slot, edit_component=edit.component_name,
                root_cause_tag=diag.get("root_cause_tag", ""), diagnosis_overview=diag.get("overview", ""),
                incumbent_oos=inc_eval.total_oos(), per_subtype=inc_eval.per_subtype(), cand_oos=inc_eval.total_oos()))
            buffer.add(edit, LEAKAGE_BLOCKED, inc_eval.total_oos(), inc_eval.total_oos(), "leaked answer material into a component")
            oos_traj.append(inc_eval.total_oos()); ms_traj.append(round(_mean_score(inc_eval), 4))
            expdir.persist_iteration("gdpval_soft", {"iteration": it, "eval": None, "diagnosis": diag,
                "manifest": {"blocked": True, "reason": "leakage guard", "edit": edit.signature()}, "workspace": incumbent.summary()})
        elif edit is None or buffer.blocks(edit):
            n_blocked += 1
            verdict = "NO_EDIT" if edit is None else "BLOCKED"
            mext = {"blocked": True, "reason": "no valid edit parsed" if edit is None else "rejected-edit buffer"}
            if edit is not None:
                mext["edit"] = edit.signature()
            records.append(IterationRecord(
                iteration=it, blocked=True, verdict=verdict, kept=False,
                edit_summary=(edit.summary if edit else "(none)"),
                edit_slot=(edit.slot if edit else ""), edit_component=(edit.component_name if edit else ""),
                root_cause_tag=diag.get("root_cause_tag", ""), diagnosis_overview=diag.get("overview", ""),
                incumbent_oos=inc_eval.total_oos(), per_subtype=inc_eval.per_subtype(), cand_oos=inc_eval.total_oos()))
            oos_traj.append(inc_eval.total_oos()); ms_traj.append(round(_mean_score(inc_eval), 4))
            expdir.persist_iteration("gdpval_soft", {"iteration": it, "eval": None, "diagnosis": diag,
                                                     "manifest": mext, "workspace": incumbent.summary()})
        else:
            candidate = incumbent.clone(); candidate.apply(edit)
            cand_eval = evaluate(candidate, tasks, mock=cfg.mock, llm=llm, hard=hard, soft=soft, k=cfg.k, label=f"iter{it}", cache=cache)
            diff = compute_diff(inc_eval, cand_eval)
            evaluation = evaluate_changes(edit, diff)  # verdict taxonomy, audit trail
            inc_mean, cand_mean = _mean_score(inc_eval), _mean_score(cand_eval)
            kept = decide_keep_soft(inc_mean, cand_mean, noise_margin)
            evaluation["soft_gate"] = {
                "inc_mean": round(inc_mean, 4), "cand_mean": round(cand_mean, 4),
                "noise_margin": round(noise_margin, 4), "kept": kept,
            }
            manifest = attach_verdict(build_manifest(it, "evolve_agent", edit, "gdpval_soft"), evaluation, kept)
            if kept:
                n_kept += 1; incumbent, inc_eval = candidate, cand_eval
            else:
                n_rb += 1
                buffer.add(edit, evaluation["verdict"], inc_eval.total_oos(), cand_eval.total_oos(), _failure_pattern(evaluation, edit))
            oos_traj.append(inc_eval.total_oos()); ms_traj.append(round(_mean_score(inc_eval), 4))
            records.append(IterationRecord(
                iteration=it, blocked=False, verdict=evaluation["verdict"], kept=kept,
                edit_summary=edit.summary, edit_slot=edit.slot, edit_component=edit.component_name,
                root_cause_tag=diag.get("root_cause_tag", ""), diagnosis_overview=diag.get("overview", ""),
                incumbent_oos=inc_eval.total_oos(), per_subtype=inc_eval.per_subtype(), cand_oos=cand_eval.total_oos()))
            expdir.persist_iteration("gdpval_soft", {"iteration": it, "eval": eval_to_dict(cand_eval),
                                                     "diagnosis": diag, "manifest": manifest, "workspace": incumbent.summary()})

        _write_resume(resume_path, it, incumbent, noise_margin, buffer, records, oos_traj, ms_traj,
                      n_kept, n_rb, n_blocked)

    result = SoftRunResult(
        n_tasks=len(tasks), oos_trajectory=oos_traj, mean_score_trajectory=ms_traj, records=records,
        final_per_occupation=inc_eval.per_subtype(), final_mean_score=round(_mean_score(inc_eval), 4),
        n_kept=n_kept, n_rolled_back=n_rb, n_blocked=n_blocked, noise_margin=round(noise_margin, 4),
        final_per_occupation_mean={k: round(v, 4) for k, v in inc_eval.per_subtype_mean().items()},
    )
    expdir.persist_arm("gdpval_soft", result.to_dict())
    return result


def run_ablation(cfg: Config) -> AblationResult:
    llm = make_llm(cfg.mock)
    hard, soft = HardVerifier(), SoftJudge(llm)
    a_tasks = load_gdpval_a_pile()
    b_tasks = load_gdpval_b_pile(cfg.b_n, allow_download=not cfg.mock)
    expdir = ExperimentDir(cfg.results_dir)

    b_base_eval = evaluate(seed_harness(), b_tasks, mock=cfg.mock, llm=llm, hard=hard, soft=soft, k=cfg.k)
    b_baseline = {"mean_score": _mean_score(b_base_eval), "n_oos": b_base_eval.total_oos(), "n": len(b_tasks)}

    arm1 = run_arm("arm1_A_only", a_tasks, b_tasks, cfg=cfg, llm=llm, hard=hard, soft=soft, expdir=expdir, b_baseline=b_baseline)
    arm2 = run_arm("arm2_A_plus_B", a_tasks, b_tasks, cfg=cfg, llm=llm, hard=hard, soft=soft, expdir=expdir, b_baseline=b_baseline)

    comparison = {
        "final_A_oos": {"arm1": arm1.final_oos, "arm2": arm2.final_oos},
        "B_transfer_mean": {"arm1": arm1.b_transfer["mean_score"], "arm2": arm2.b_transfer["mean_score"], "baseline": b_baseline["mean_score"]},
        "mean_eval_variance": {"arm1": arm1.mean_eval_variance, "arm2": arm2.mean_eval_variance},
        "kept/rolledback/blocked": {
            "arm1": [arm1.n_kept, arm1.n_rolled_back, arm1.n_blocked],
            "arm2": [arm2.n_kept, arm2.n_rolled_back, arm2.n_blocked],
        },
        "note": (
            "Arm2 puts soft-B in the loop (relaxes iron law 2). Compare eval-signal "
            "variance (cleanliness of falsification) and whether B-in-loop changed "
            "final A OOS or B transfer. In mock these values are illustrative."
        ),
    }
    expdir.persist_ablation(comparison)
    return AblationResult(arm1=arm1, arm2=arm2, comparison=comparison)
