"""The deterministic Level-B evolution loop (NexAU substrate, benchmark-agnostic).

Orchestrates two sibling NexAU agents — the weak worker and the file-editing evolve
agent — around an INDEPENDENT, per-benchmark Evaluator and a FIREWALLED debugger.
keep/rollback, the noise-floor soft gate, the AHE prediction-falsification verdict,
the leakage guard, and the rejected-edit buffer all live HERE, in code; the evolve
agent decides nothing and never runs the grader.

The loop is benchmark-agnostic: it consumes a `Benchmark` (tasks + evaluator +
answer_corpus) and never imports a grader. The SAME `run_levelb` runs on FAB and
GDPval by swapping `cfg.benchmark` + `cfg.seed_worker_dir`.

Incumbent = a worker DIRECTORY (not a Harness object). Each iteration snapshots the
incumbent dir, lets the evolve agent edit the snapshot from an answer-free diagnosis,
re-grades, classifies the edit against the agent's own prediction, and promotes the
snapshot only on an aggregate-score gain beyond the noise floor that is not HARMFUL.
"""
from __future__ import annotations

import json
import statistics
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .benchmark import make_benchmark
from .debugger import diagnose_b_pile
from .evolve_runtime import DirEdit, dir_unified_diff, run_evolve_agent, snapshot_dir
from .falsify import (EvalSummary, LEAKAGE_BLOCKED, RejectedEditBuffer,
                      decide_keep_soft, evaluate_changes)
from .llm import make_llm
from .verifier import LeakageGuard, TaskResult
from .worker_runtime import run_worker


@dataclass
class LevelBConfig:
    n_iters: int = 2
    k: int = 2
    n_tasks: int = 5                 # small by default — stands up the loop
    broad: bool = True
    results_dir: str = "results/levelb"
    benchmark: str = "fab"           # "fab" | "gdpval"
    seed_worker_dir: str = "qea/worker_fab_weak"
    # "sanitized" = iron-law-2 firewall ON (evolve agent sees only the answer-free
    # diagnosis). "ahe_corpus" = AHE-style evidence corpus (traces + per-task failure
    # analysis + edit history); firewall relaxed, but the gold answer is NEVER included.
    evidence_mode: str = "sanitized"


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
    improved: list = field(default_factory=list)
    regressed: list = field(default_factory=list)

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
    benchmark: str = ""
    n_kept: int = 0
    n_rolled_back: int = 0
    n_blocked: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["records"] = [r.to_dict() if isinstance(r, LevelBRecord) else r for r in self.records]
        return d


def _eval_summary(evals: dict, deliverables: dict, tasks) -> EvalSummary:
    """Adapt per-task TaskEvals into the EvalSummary the debugger expects. The
    canonical score is the FORMAT-GATED score; a format miss makes the task fail oos
    so the debugger flags it for the evolve agent to fix."""
    by_id = {t.task_id: t for t in tasks}
    results = {}
    for tid, e in evals.items():
        sub = getattr(by_id.get(tid), "subtype", "")
        oos = e.gated_score >= 0.60
        results[tid] = TaskResult(tid, sub, "B", oos, oos, oos, e.gated_score,
                                  e.variance, None, criterion_verdicts=e.verdicts)
    return EvalSummary(results, deliverables)


def evaluate_dir(worker_dir: Path, tasks, evaluator, run_dir: Path):
    """Run the worker on every task with the given worker dir, then score each run
    through the benchmark's Evaluator (which owns render/grade/gate). Returns
    (evals, traces, deliverables, mean_gated_score). The loop imports no grader."""
    from .evaluator import TaskEval
    worker_dir, run_dir = Path(worker_dir), Path(run_dir)
    evals, traces, deliverables = {}, {}, {}
    for task in tasks:
        try:
            wr = run_worker(task, worker_dir, run_dir)
            te = evaluator.evaluate(task, wr, run_dir / str(task.task_id))
            evals[task.task_id] = te
            traces[task.task_id] = {**wr.trace, "content": round(te.content_score, 4),
                                    "format_ok": te.format_ok}
            deliverables[task.task_id] = te.deliverable_text
        except Exception as exc:  # noqa: BLE001 - one worker/grader failure must not
            # kill a multi-task, multi-iteration run (mirrors the base scripts'
            # per-task try/except). A crashed worker IS a task failure: score it 0 so
            # the debugger flags it, and record the error in the answer-free trace.
            evals[task.task_id] = TaskEval(0.0, 0.0, False, "", {}, 0.0)
            traces[task.task_id] = {"error": f"{type(exc).__name__}: {exc}"[:300],
                                    "files": 0, "turns": 0, "tool_calls": 0,
                                    "tool_errors": 1, "content": 0.0, "format_ok": False}
            deliverables[task.task_id] = ""
    mean = statistics.mean(e.gated_score for e in evals.values()) if evals else 0.0
    return evals, traces, deliverables, mean


def _edit_history(records: list) -> str:
    """AFlow-style labeled edit history fed to the evolve agent so it does not
    re-propose falsified edits. One line per prior iteration: summary -> verdict."""
    lines = []
    for r in records:
        lines.append(f"- iter {r.iteration}: {r.edit_summary} -> {r.verdict}")
    return "\n".join(lines)


def _build_evidence(evidence_dir: Path, diag: dict, evals: dict, traces: dict,
                    deliverables: dict, tasks, records: list) -> Path:
    """AHE-style evidence corpus (firewall-OFF mode). overview.md distills per FAILING
    task: failed rubric criteria + process + the worker's OWN deliverable (truncated);
    evolution_history.md logs prior edits + verdicts; raw per-task traces stay on disk
    for drill-down. The gold answer is NEVER written here."""
    evidence_dir = Path(evidence_dir)
    (evidence_dir / "traces").mkdir(parents=True, exist_ok=True)
    by_id = {t.task_id: t for t in tasks}
    lines = ["# Evidence overview (firewall-off corpus; NO gold answer included)", "",
             f"Dominant deficiency: {diag.get('root_cause_tag')} — {diag.get('overview', '')}", ""]
    for tid, e in evals.items():
        if e.gated_score >= 0.60:
            continue
        task = by_id.get(tid)
        items = getattr(task, "rubric_items", None) or []
        failed = [items[i]["criterion"] for i in range(len(items))
                  if e.verdicts and e.verdicts.get(str(i + 1)) is False]
        tr = traces.get(tid, {})
        proc = (f"files={tr.get('files', 0)} turns={tr.get('turns', 0)} "
                f"tool_errors={tr.get('tool_errors', 0)}"
                + (f" ERROR={tr.get('error')}" if tr.get("error") else ""))
        lines += [
            f"## {tid} ({getattr(task, 'subtype', '')}) — gated {e.gated_score:.2f}",
            f"- failed criteria ({len(failed)}): " + ("; ".join(failed[:8]) or "(none captured)"),
            f"- process: {proc}",
            f"- full trace: {tr.get('trace_path') or '(none)'}",
            "- worker deliverable (truncated):",
            (deliverables.get(tid, "") or "")[:1500], ""]
    (evidence_dir / "overview.md").write_text("\n".join(lines))
    hist = "\n".join(f"- iter {r.iteration}: {r.edit_summary} -> {r.verdict}" for r in records) or "(none yet)"
    (evidence_dir / "evolution_history.md").write_text("# Evolution history\n\n" + hist + "\n")
    return evidence_dir


def _classify(edit, inc_evals: dict, cand_evals: dict, delta: float) -> dict:
    """Continuous-score adaptation of AHE's prediction-falsification: a task counts
    as flipped/regressed only if its GATED score moved more than the noise tolerance
    `delta`; then evaluate_changes assigns the 5-class verdict against the evolve
    agent's predicted_fixes / risk_tasks."""
    inc = {tid: e.gated_score for tid, e in inc_evals.items()}
    cand = {tid: e.gated_score for tid, e in cand_evals.items()}
    flipped = sorted(t for t in cand if cand[t] - inc.get(t, 0.0) > delta)
    regressed = sorted(t for t in cand if inc.get(t, 0.0) - cand[t] > delta)
    ev = evaluate_changes(edit, {"flipped": flipped, "regressed": regressed})
    ev["flipped"], ev["regressed"] = flipped, regressed
    return ev


def run_levelb(cfg: LevelBConfig, benchmark=None, *, _tasks=None, _evaluator=None,
               _llm=None) -> LevelBResult:
    """Stand up + run the Level-B loop on `cfg.benchmark`. `_tasks`/`_evaluator`/`_llm`
    inject a task list / evaluator / LLM for offline tests; in real use a Benchmark
    (built here from cfg.benchmark unless one is passed) provides them."""
    llm = _llm if _llm is not None else make_llm(False)
    if _tasks is not None:
        tasks, evaluator, answer_corpus = _tasks, _evaluator, []
    else:
        if benchmark is None:
            benchmark = make_benchmark(cfg.benchmark, llm=llm, broad=cfg.broad, k=cfg.k)
        tasks = benchmark.tasks[: cfg.n_tasks]
        evaluator = benchmark.evaluator
        answer_corpus = benchmark.answer_corpus
    guard = LeakageGuard(answer_corpus)
    buffer = RejectedEditBuffer()
    results_dir = Path(cfg.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    # incumbent = a live copy of the seed worker dir under the results dir
    incumbent = results_dir / "incumbent_worker"
    snapshot_dir(Path(cfg.seed_worker_dir), incumbent)

    # seed eval + a 2nd same-dir eval for the noise floor
    evals, traces, deliverables, inc_mean = evaluate_dir(incumbent, tasks, evaluator, results_dir / "seed")
    _, _, _, noise_mean = evaluate_dir(incumbent, tasks, evaluator, results_dir / "seed_noise")
    noise_margin = max(0.01, abs(inc_mean - noise_mean))

    ms_traj = [round(inc_mean, 4)]
    records: list = []
    n_kept = n_rb = n_blocked = 0

    for it in range(1, cfg.n_iters + 1):
        inc_eval = _eval_summary(evals, deliverables, tasks)
        diag = diagnose_b_pile(inc_eval, tasks, llm=llm, traces=traces).proposer_payload()

        iterdir = results_dir / f"iter_{it:03d}"
        cand_dir = iterdir / "worker"
        snapshot_dir(incumbent, cand_dir)
        evidence_dir = None
        if cfg.evidence_mode == "ahe_corpus":
            evidence_dir = _build_evidence(iterdir / "evidence", diag, evals, traces,
                                           deliverables, tasks, records)
        ev_out = run_evolve_agent(cand_dir, diag, iterdir,
                                  edit_history=_edit_history(records), evidence_dir=evidence_dir)
        pred = ev_out.get("prediction") or {}
        diff = dir_unified_diff(incumbent, cand_dir)
        edit = DirEdit(diff, predicted_fixes=pred.get("predicted_fixes", []),
                       risk_tasks=pred.get("risk_tasks", []))

        improved = regressed = []
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
            cand_evals, ct, cd, cand_mean = evaluate_dir(cand_dir, tasks, evaluator, iterdir / "grade")
            cls = _classify(edit, evals, cand_evals, noise_margin)
            verdict, improved, regressed = cls["verdict"], cls["flipped"], cls["regressed"]
            # promote iff a real aggregate gain beyond the noise floor AND not harmful
            kept = decide_keep_soft(inc_mean, cand_mean, noise_margin) and verdict != "HARMFUL"
            if kept:
                n_kept += 1
                incumbent = cand_dir
                evals, traces, deliverables, inc_mean = cand_evals, ct, cd, cand_mean
            else:
                n_rb += 1
                buffer.add(edit, verdict, 0, 0, "no aggregate score gain beyond the noise floor")

        records.append(LevelBRecord(
            it, verdict in ("NO_EDIT", LEAKAGE_BLOCKED, "BLOCKED"), verdict, kept,
            edit.summary, diag.get("root_cause_tag", ""), round(inc_mean, 4),
            round(cand_mean, 4), list(improved), list(regressed)))
        ms_traj.append(round(inc_mean, 4))
        _persist(results_dir, it, verdict, kept, edit, diag, inc_mean)

    return LevelBResult(
        n_tasks=len(tasks), mean_score_trajectory=ms_traj, records=records,
        noise_margin=round(noise_margin, 4), final_mean_score=round(inc_mean, 4),
        final_worker_dir=str(incumbent), benchmark=cfg.benchmark,
        n_kept=n_kept, n_rolled_back=n_rb, n_blocked=n_blocked)


def _persist(results_dir: Path, it: int, verdict: str, kept: bool, edit, diag: dict, inc_mean: float) -> None:
    d = results_dir / f"iter_{it:03d}"
    d.mkdir(parents=True, exist_ok=True)
    (d / "manifest.json").write_text(json.dumps({
        "iteration": it, "verdict": verdict, "kept": kept,
        "edit_summary": edit.summary, "diff_signature": edit.signature(),
        "predicted_fixes": list(getattr(edit, "predicted_fixes", [])),
        "risk_tasks": list(getattr(edit, "risk_tasks", [])),
        "diagnosis": diag, "inc_mean": round(inc_mean, 4),
    }, indent=2, default=str))
    (d / "edit.diff").write_text(edit.diff)
