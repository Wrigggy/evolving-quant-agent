"""The deterministic Level-B evolution loop (NexAU substrate).

Orchestrates two sibling NexAU agents — the weak worker and the file-editing evolve
agent — around an INDEPENDENT grader (the same MultimodalJudge the base test used)
and a FIREWALLED debugger. keep/rollback, the noise-floor soft gate, the leakage
guard, and the rejected-edit buffer all live HERE, in code; the evolve agent decides
nothing and never runs the grader.

Incumbent = a worker DIRECTORY (not a Harness object). Each iteration snapshots the
incumbent dir, lets the evolve agent edit the snapshot from an answer-free diagnosis,
re-grades, and promotes the snapshot only on an aggregate-score gain beyond the noise
floor (decide_keep_soft).
"""
from __future__ import annotations

import json
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path

from .benchmark import gdpval_benchmark
from .debugger import diagnose_b_pile
from .evolve_runtime import DirEdit, dir_unified_diff, run_evolve_agent, snapshot_dir
from .falsify import EvalSummary, LEAKAGE_BLOCKED, RejectedEditBuffer, decide_keep_soft
from .grading.format_gate import apply_gate
from .grading.multimodal_judge import MultimodalJudge
from .grading.render import render
from .llm import make_llm
from .verifier import LeakageGuard, TaskResult
from .worker_runtime import run_worker


@dataclass
class LevelBConfig:
    n_iters: int = 2
    k: int = 2
    n_tasks: int = 5                 # small by default — Phase 4 stands up the loop
    broad: bool = True
    results_dir: str = "results/levelb"
    seed_worker_dir: str = "qea/worker_gdpval_weak"


@dataclass
class LevelBRecord:
    iteration: int
    blocked: bool
    verdict: str
    kept: bool
    edit_summary: str
    root_cause_tag: str
    inc_mean: float
    cand_mean: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LevelBResult:
    n_tasks: int
    mean_score_trajectory: list
    records: list
    noise_margin: float
    final_mean_score: float
    final_worker_dir: str
    n_kept: int = 0
    n_rolled_back: int = 0
    n_blocked: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["records"] = [r.to_dict() if isinstance(r, LevelBRecord) else r for r in self.records]
        return d


def _eval_summary_from_grades(grades: dict, gated: dict, traces: dict, deliverables: dict, tasks) -> EvalSummary:
    """Adapt MultimodalJudge GradeResults into the EvalSummary the debugger expects.
    The canonical score is the FORMAT-GATED score (`gated[tid]`); a format miss makes
    the task fail oos so the debugger flags it for the evolve agent to fix."""
    by_id = {t.task_id: t for t in tasks}
    results = {}
    for tid, g in grades.items():
        sub = getattr(by_id.get(tid), "subtype", "")
        score = gated.get(tid, g.multimodal_fraction)
        oos = score >= 0.60
        results[tid] = TaskResult(tid, sub, "B", oos, oos, oos, score,
                                  g.variance, None, criterion_verdicts=g.verdicts)
    return EvalSummary(results, deliverables)


def evaluate_dir(worker_dir: Path, tasks, judge, run_dir: Path, *, k: int):
    """Run the worker on every task with the given worker dir, render + grade each,
    then apply the deliverable-format gate (canonical score = gated; content kept for
    diagnosis). Returns (grades, gated, traces, deliverables, mean_gated_score)."""
    worker_dir, run_dir = Path(worker_dir), Path(run_dir)
    grades, gated, traces, deliverables = {}, {}, {}, {}
    for task in tasks:
        wr = run_worker(task, worker_dir, run_dir)
        rendered = render(wr.deliverable_text, wr.produced_files, run_dir / str(task.task_id))
        g = judge.grade(task, rendered)
        gscore, fmt_ok = apply_gate(g.multimodal_fraction, task, wr.produced_files)
        grades[task.task_id] = g
        gated[task.task_id] = gscore
        traces[task.task_id] = {**wr.trace, "content_mm": round(g.multimodal_fraction, 4),
                                "format_ok": fmt_ok}
        deliverables[task.task_id] = rendered.text or ""
    mean = (statistics.mean(gated.values()) if gated else 0.0)
    return grades, gated, traces, deliverables, mean


def run_gdpval_levelb(cfg: LevelBConfig, *, _tasks=None, _llm=None) -> LevelBResult:
    """Stand up + run the Level-B loop. `_tasks` / `_llm` inject a task list / LLM for
    offline tests; in real use the GDPval benchmark + make_llm provide them."""
    llm = _llm if _llm is not None else make_llm(False)
    judge = MultimodalJudge(llm, k=cfg.k)
    if _tasks is not None:
        tasks, answer_corpus = _tasks, []
    else:
        bm = gdpval_benchmark(broad=cfg.broad, allow_download=True, llm=llm)
        tasks = bm.tasks[: cfg.n_tasks]
        answer_corpus = bm.answer_corpus
    guard = LeakageGuard(answer_corpus)
    buffer = RejectedEditBuffer()
    results_dir = Path(cfg.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    # incumbent = a live copy of the seed worker dir under the results dir
    incumbent = results_dir / "incumbent_worker"
    snapshot_dir(Path(cfg.seed_worker_dir), incumbent)

    # seed eval + a 2nd same-dir eval for the noise floor (mirror run_gdpval_soft)
    grades, gated, traces, deliverables, inc_mean = evaluate_dir(incumbent, tasks, judge, results_dir / "seed", k=cfg.k)
    _, _, _, _, noise_mean = evaluate_dir(incumbent, tasks, judge, results_dir / "seed_noise", k=cfg.k)
    noise_margin = max(0.01, abs(inc_mean - noise_mean))

    ms_traj = [round(inc_mean, 4)]
    records: list = []
    n_kept = n_rb = n_blocked = 0

    for it in range(1, cfg.n_iters + 1):
        inc_eval = _eval_summary_from_grades(grades, gated, traces, deliverables, tasks)
        diag = diagnose_b_pile(inc_eval, tasks, llm=llm, traces=traces).proposer_payload()

        cand_dir = results_dir / f"iter_{it:03d}" / "worker"
        snapshot_dir(incumbent, cand_dir)
        run_evolve_agent(cand_dir, diag, results_dir / f"iter_{it:03d}")
        diff = dir_unified_diff(incumbent, cand_dir)
        edit = DirEdit(diff)

        if not diff:
            verdict, kept, cand_mean = "NO_EDIT", False, inc_mean
            n_blocked += 1
        elif guard.is_leak(edit):
            verdict, kept, cand_mean = LEAKAGE_BLOCKED, False, inc_mean
            n_blocked += 1
            buffer.add(edit, verdict, 0, 0, "pasted answer material into a worker file")
        elif buffer.blocks(edit):
            verdict, kept, cand_mean = "BLOCKED", False, inc_mean
            n_blocked += 1
        else:
            cg, cgated, ct, cd, cand_mean = evaluate_dir(cand_dir, tasks, judge, results_dir / f"iter_{it:03d}" / "grade", k=cfg.k)
            kept = decide_keep_soft(inc_mean, cand_mean, noise_margin)
            verdict = "EFFECTIVE" if kept else "INEFFECTIVE"
            if kept:
                n_kept += 1
                incumbent = cand_dir
                grades, gated, traces, deliverables, inc_mean = cg, cgated, ct, cd, cand_mean
            else:
                n_rb += 1
                buffer.add(edit, verdict, 0, 0, "no aggregate score gain beyond the noise floor")

        records.append(LevelBRecord(it, verdict in ("NO_EDIT", LEAKAGE_BLOCKED, "BLOCKED"), verdict, kept,
                                    edit.summary, diag.get("root_cause_tag", ""),
                                    round(inc_mean, 4), round(cand_mean, 4)))
        ms_traj.append(round(inc_mean, 4))
        _persist(results_dir, it, verdict, kept, edit, diag, inc_mean)

    return LevelBResult(
        n_tasks=len(tasks), mean_score_trajectory=ms_traj, records=records,
        noise_margin=round(noise_margin, 4), final_mean_score=round(inc_mean, 4),
        final_worker_dir=str(incumbent), n_kept=n_kept, n_rolled_back=n_rb, n_blocked=n_blocked)


def _persist(results_dir: Path, it: int, verdict: str, kept: bool, edit, diag: dict, inc_mean: float) -> None:
    d = results_dir / f"iter_{it:03d}"
    d.mkdir(parents=True, exist_ok=True)
    (d / "manifest.json").write_text(json.dumps({
        "iteration": it, "verdict": verdict, "kept": kept,
        "edit_summary": edit.summary, "diff_signature": edit.signature(),
        "diagnosis": diag, "inc_mean": round(inc_mean, 4),
    }, indent=2, default=str))
    (d / "edit.diff").write_text(edit.diff)
