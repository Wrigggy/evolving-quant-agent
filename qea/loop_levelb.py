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

import hashlib
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


# Transient infra failures (E2B 429/rate-limit, sandbox create/resume, RemoteProtocolError
# "Server disconnected", broken-pipe I/O drops, 5xx gateways) are NOT real task results.
# Shared here so BOTH the eval (don't-cache + retry) and the keep decision (exclude from the
# seed-vs-candidate comparison) treat them identically — a task that infra-failed on either
# side must never count as a regression that masks a real edit at the noise-floor margin.
_TRANSIENT_KEYS = (
    "ratelimit", "429", "rate limit", "sandbox", "timeout", "timed out", "connection",
    "disconnect", "remoteprotocol", "protocolerror", "temporarily", "econnreset",
    "eof occurred", "broken pipe", "writeerror", "errno 32", "readerror",
    "connectionreset", "connectionerror", "502", "503", "504",
)


def _is_transient_error(err: str) -> bool:
    """True if an answer-free trace's error string is a transient infra failure."""
    if not err:
        return False
    e = err.lower()
    return any(k in e for k in _TRANSIENT_KEYS)


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
    # noise floor for decide_keep_soft. 0.0 = MEASURE it via a 2nd same-dir seed eval
    # (accurate but doubles the slow seed cost). >0 = use this fixed margin and SKIP the
    # 2nd eval (cheap; for expensive workers). e.g. 0.05.
    noise_margin: float = 0.0
    # Cross-leg memory: results dir(s) of PRIOR runs this run's evolution continues
    # from (comma-separated, oldest first). Their iter manifests + diffs are prepended
    # to the evolve agent's edit history / attempt archive so already-falsified edit
    # directions aren't re-proposed. "" = auto-detect the immediate prior leg from
    # seed_worker_dir (use its parent when that dir contains iter manifests).
    prior_history_dir: str = ""
    # Second-confirmation eval for near-floor keeps. Measured on GDPval (two independent
    # 8-task evals of the same workers): the sigma of a seed-vs-candidate mean DELTA is
    # ~0.054 — LARGER than the 0.05 noise floor, so a single eval clearing the floor by
    # a hair is ~1 sigma from noise. When a keep's fair gain is below noise_margin +
    # confirm_band, the candidate is evaluated a SECOND time (fresh, cache-bypassed) and
    # kept only if the averaged gain still clears the floor. 0 = off.
    confirm_band: float = 0.0
    concurrency: int = 1             # parallel worker runs per eval (essential for full FAB)
    # Worker execution backend. "local" = run the agent in the local Python process
    # (fast, but each run holds a large LLM context locally -> memory-bound at high
    # concurrency). "e2b_full" = run the ENTIRE agent inside a per-task E2B cloud VM
    # (Harbor-style full offload via worker_e2b.run_worker_e2b): local footprint stays
    # near-zero, so 20-way concurrency no longer risks a macOS memory batch-kill.
    execution: str = "local"


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


def _worker_sig(worker_dir: Path) -> str:
    """Short stable hash of the worker dir's text files — the cache key so RESUME
    only reuses a cached task result when the worker dir is byte-identical (seed is
    stable across relaunches; an evolved candidate has a different sig)."""
    from .evolve_runtime import _text_files
    tf = _text_files(Path(worker_dir))
    h = hashlib.sha1()
    for rel in sorted(tf):
        h.update(rel.encode()); h.update("".join(tf[rel]).encode())
    return h.hexdigest()[:12]


def evaluate_dir(worker_dir: Path, tasks, evaluator, run_dir: Path, *, concurrency: int = 1,
                 cache_dir=None, execution: str = "local"):
    """Run the worker on every task with the given worker dir, then score each run
    through the benchmark's Evaluator (which owns render/grade/gate). Returns
    (evals, traces, deliverables, mean_gated_score). The loop imports no grader.

    `concurrency` worker runs in parallel (ThreadPoolExecutor) — essential for full
    benchmarks (FAB 27 tasks). The cross-snapshot `tools.*` reload is done ONCE here
    (prepare_worker_imports) BEFORE the pool, so threads only import (lock-safe).

    `cache_dir` enables RESUME: a completed task's result is persisted to
    `cache_dir/{worker_sig}__{task_id}.json`; on a later launch (after the environment
    reaps a long run) the cached result is loaded instead of re-running the worker, so
    repeated launches ACCUMULATE to completion."""
    from .evaluator import TaskEval
    worker_dir, run_dir = Path(worker_dir), Path(run_dir)
    # Backend select. "e2b_full" runs the whole agent in a cloud VM (worker_e2b), so the
    # local `tools.*` reload is irrelevant (the worker never imports in-process here).
    if execution == "e2b_full":
        from .worker_e2b import run_worker_e2b as _run_worker
    else:
        from .worker_runtime import prepare_worker_imports, run_worker as _run_worker
        prepare_worker_imports(worker_dir)
    evals, traces, deliverables = {}, {}, {}
    sig = _worker_sig(worker_dir) if cache_dir else None
    if cache_dir:
        Path(cache_dir).mkdir(parents=True, exist_ok=True)

    def _cache_file(task):
        return Path(cache_dir) / f"{sig}__{task.task_id}.json" if cache_dir else None

    def _one(task):
        cf = _cache_file(task)
        if cf is not None and cf.exists():
            try:
                d = json.loads(cf.read_text())
                return task.task_id, TaskEval(**d["eval"]), d["trace"], d["deliverable"]
            except Exception:  # noqa: BLE001 - corrupt cache entry -> just re-run
                pass
        # A transient infra failure (E2B 429/rate-limit, sandbox create/resume, a
        # RemoteProtocolError "Server disconnected" between the VM worker and OpenRouter)
        # is NOT a real task result. Scoring it 0 asymmetrically penalizes whichever eval
        # got unlucky — on a candidate that means a spurious regression that flips the
        # keep/rollback verdict at the noise-floor margin. So: retry the worker on a
        # transient error before giving up, and never cache a transient 0 (it would poison
        # resume). A genuine worker/grader failure (non-transient) is a real 0 and is cached.
        def _is_transient(exc):
            return _is_transient_error(f"{type(exc).__name__}: {exc}")
        transient = False
        _MAX_ATTEMPTS = 4
        for _attempt in range(_MAX_ATTEMPTS):
            try:
                wr = _run_worker(task, worker_dir, run_dir)
                te = evaluator.evaluate(task, wr, run_dir / str(task.task_id))
                tr = {**wr.trace, "content": round(te.content_score, 4), "format_ok": te.format_ok}
                out = (task.task_id, te, tr, te.deliverable_text)
                transient = False
                break
            except Exception as exc:  # noqa: BLE001 - one worker/grader failure must not kill
                # a multi-task/iteration run. A crashed worker IS a task failure: score 0 so
                # the debugger flags it, and record the error in the answer-free trace.
                tr = {"error": f"{type(exc).__name__}: {exc}"[:300], "files": 0, "turns": 0,
                      "tool_calls": 0, "tool_errors": 1, "content": 0.0, "format_ok": False}
                out = (task.task_id, TaskEval(0.0, 0.0, False, "", {}, 0.0), tr, "")
                transient = _is_transient(exc)
                if transient and _attempt < _MAX_ATTEMPTS - 1:
                    print(f"[eval] {task.task_id} transient error "
                          f"(attempt {_attempt + 1}/{_MAX_ATTEMPTS}), retrying: {tr['error'][:80]}")
                    continue
                break
        if cf is not None and not transient:
            try:
                cf.write_text(json.dumps({"eval": asdict(out[1]), "trace": out[2],
                                          "deliverable": out[3]}, default=str))
            except Exception:  # noqa: BLE001
                pass
        return out

    if concurrency > 1 and len(tasks) > 1:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            results = list(pool.map(_one, tasks))
    else:
        results = [_one(t) for t in tasks]

    for tid, te, tr, deliv in results:
        evals[tid], traces[tid], deliverables[tid] = te, tr, deliv
    mean = statistics.mean(e.gated_score for e in evals.values()) if evals else 0.0
    return evals, traces, deliverables, mean


def _load_prior_history(prior_dir) -> str:
    """Cross-leg memory: when a run continues evolution from a prior run's evolved
    worker, the evolve agent must inherit that run's labeled edit history too —
    otherwise it re-proposes edits the prior leg already falsified (observed: three
    separate excel-reader-tool attempts across two legs, every one HARMFUL). Reads the
    prior run's iter manifests; returns the same one-line-per-edit format as
    _edit_history."""
    lines = []
    for d in _prior_dirs(prior_dir):
        leg = Path(d).name
        for mf in sorted(Path(d).glob("iter_*/manifest.json")):
            try:
                m = json.loads(mf.read_text())
                tag = "KEPT" if m.get("kept") else m.get("verdict", "?")
                lines.append(f"- prior run {leg}/{mf.parent.name}: {m.get('edit_summary', '')} -> {tag}"
                             + _helped_hurt(m.get("improved") or [], m.get("regressed") or []))
            except Exception:  # noqa: BLE001
                continue
    return "\n".join(lines)


def _prior_dirs(spec) -> list:
    """Parse the prior_history_dir spec: comma-separated results dirs, oldest first
    (an evolution can span several legs; each leg only auto-detects its immediate
    parent, so a 3rd leg must be handed leg1,leg2 explicitly to keep the full
    falsified-attempt record)."""
    return [s.strip() for s in str(spec or "").split(",") if s.strip()]


def _load_prior_edits(prior_dir) -> list:
    """Cross-leg attempt archive: prior runs' per-iteration diffs + outcomes, so the
    evidence corpus can expose WHAT each falsified attempt actually changed (observed:
    one-line history alone did not stop the evolve agent re-proposing the same
    excel-reader tool across legs — it judged each variant 'different'). Returns the
    same entry dicts as the in-run `past_edits` list."""
    out = []
    for d in _prior_dirs(prior_dir):
        leg = Path(d).name
        for mf in sorted(Path(d).glob("iter_*/manifest.json")):
            try:
                m = json.loads(mf.read_text())
                diff = (mf.parent / "edit.diff").read_text() if (mf.parent / "edit.diff").exists() else ""
                if not diff:
                    continue
                out.append({"name": f"prior_{leg}_{mf.parent.name}", "kept": bool(m.get("kept")),
                            "verdict": m.get("verdict", "?"), "summary": m.get("edit_summary", ""),
                            "improved": m.get("improved") or [], "regressed": m.get("regressed") or [],
                            "diff": diff})
            except Exception:  # noqa: BLE001
                continue
    return out


def _helped_hurt(improved, regressed) -> str:
    """' (helped: a,b | hurt: c)' suffix for a history line — the per-task outcome is
    what lets the evolve agent see WHY an edit was rolled back (whack-a-mole: it fixed
    some tasks but broke others), instead of just an opaque verdict label."""
    if not improved and not regressed:
        return ""
    fmt = lambda ts: ", ".join(str(t)[:8] for t in ts) or "-"  # noqa: E731
    return f" (helped: {fmt(improved)} | hurt: {fmt(regressed)})"


def _edit_history(records: list) -> str:
    """AFlow-style labeled edit history fed to the evolve agent so it does not
    re-propose falsified edits. One line per prior iteration: summary -> verdict,
    plus which tasks the edit helped/hurt."""
    lines = []
    for r in records:
        tag = "KEPT" if r.kept else r.verdict
        lines.append(f"- iter {r.iteration}: {r.edit_summary} -> {tag}"
                     + _helped_hurt(r.improved, r.regressed))
    return "\n".join(lines)


_ANTI_FIXATION = """
## Approach constraints (READ before choosing an edit)
Every attempt above was EVALUATED on this exact task set. A rolled-back verdict means
that approach — as implemented — was empirically falsified; re-submitting a variant of
it is the most common wasted iteration (observed: four separate excel-reader tools,
all rolled back). Before attempting anything similar to a listed edit, read its diff
in `past_edits/` and state in your final message what SPECIFICALLY was wrong with the
prior attempt and how yours differs. Most rolled-back edits helped 1-2 tasks while
hurting 1-2 others (see helped/hurt above and archive_scores.md): the winning move is
usually to MERGE — graft only the component that helped its tasks, and leave whatever
the hurt tasks depend on untouched.
"""


def _build_evidence(evidence_dir: Path, diag: dict, evals: dict, traces: dict,
                    deliverables: dict, tasks, records: list,
                    prior_history: str = "", attempt_scores: dict = None,
                    past_edits: list = None) -> Path:
    """AHE-style evidence corpus (firewall-OFF mode). overview.md distills per FAILING
    task: failed rubric criteria + process + the worker's OWN deliverable (truncated);
    evolution_history.md logs prior edits + verdicts + an anti-fixation directive;
    past_edits/ holds each prior attempt's full diff labeled with its outcome;
    archive_scores.md is the task x attempt score matrix. The gold answer is NEVER
    written here."""
    evidence_dir = Path(evidence_dir)
    (evidence_dir / "traces").mkdir(parents=True, exist_ok=True)
    by_id = {t.task_id: t for t in tasks}
    lines = ["# Evidence overview (root-cause corpus; failed criteria include expected values "
             "for diagnosis — do NOT hard-code any answer into a worker file)", "",
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
    hist = "\n".join(x for x in (prior_history, _edit_history(records)) if x) or "(none yet)"
    directive = _ANTI_FIXATION if (records or prior_history) else ""
    (evidence_dir / "evolution_history.md").write_text(
        "# Evolution history\n\n" + hist + "\n" + directive)
    # Attempt archive: full diff of every prior attempt (this run + prior legs), headed
    # by its outcome, so "was this already tried?" is answerable by reading the file.
    if past_edits:
        pe_dir = evidence_dir / "past_edits"
        pe_dir.mkdir(parents=True, exist_ok=True)
        for e in past_edits:
            head = (f"# {e['name']}: {e.get('summary', '')}\n"
                    f"# outcome: {'KEPT' if e.get('kept') else e.get('verdict', '?') + ' (rolled back)'}"
                    f"{_helped_hurt(e.get('improved') or [], e.get('regressed') or [])}\n")
            (pe_dir / f"{e['name']}.diff").write_text(head + e["diff"])
    # Task x attempt score matrix — which attempt helped which task, at a glance.
    if attempt_scores:
        tids = sorted({tid for sc in attempt_scores.values() for tid in sc})
        cols = list(attempt_scores)
        rows = ["| task | " + " | ".join(cols) + " |",
                "|---" * (len(cols) + 1) + "|"]
        for tid in tids:
            cells = [f"{attempt_scores[c].get(tid, float('nan')):.2f}" if tid in attempt_scores[c]
                     else "-" for c in cols]
            rows.append(f"| {str(tid)[:8]} | " + " | ".join(cells) + " |")
        (evidence_dir / "archive_scores.md").write_text(
            "# Gated score per task per attempt (KEPT = promoted to incumbent)\n\n"
            + "\n".join(rows) + "\n")
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

    # seed eval; noise floor either fixed (cfg.noise_margin>0, cheap) or measured via a
    # 2nd same-dir eval (cfg.noise_margin==0, accurate but doubles the slow seed cost).
    evals, traces, deliverables, inc_mean = evaluate_dir(incumbent, tasks, evaluator, results_dir / "seed", concurrency=cfg.concurrency, cache_dir=results_dir / "_cache", execution=cfg.execution)
    if cfg.noise_margin > 0:
        noise_margin = cfg.noise_margin
    else:
        _, _, _, noise_mean = evaluate_dir(incumbent, tasks, evaluator, results_dir / "seed_noise", concurrency=cfg.concurrency, cache_dir=results_dir / "_cache", execution=cfg.execution)
        noise_margin = max(0.01, abs(inc_mean - noise_mean))

    ms_traj = [round(inc_mean, 4)]
    records: list = []
    n_kept = n_rb = n_blocked = 0

    # Cross-leg edit-history inheritance (explicit dir, or auto-detected when the seed
    # worker is a prior run's evolved artifact — its parent dir holds iter manifests).
    prior_dir = cfg.prior_history_dir
    if not prior_dir:
        seed_parent = Path(cfg.seed_worker_dir).resolve().parent
        if any(seed_parent.glob("iter_*/manifest.json")):
            prior_dir = str(seed_parent)
    prior_history = _load_prior_history(prior_dir)
    if prior_history:
        print(f"[levelb] inherited {len(prior_history.splitlines())} prior edit-history "
              f"line(s) from {prior_dir}", flush=True)

    # Attempt archive fed to the evidence corpus: per-attempt diffs + per-task score
    # columns, seeded with the prior leg's attempts when continuing an evolution.
    past_edits = _load_prior_edits(prior_dir)
    attempt_scores = {"seed": {str(t): round(e.gated_score, 4) for t, e in evals.items()}}

    for it in range(1, cfg.n_iters + 1):
        inc_eval = _eval_summary(evals, deliverables, tasks)
        # Phase markers: the diagnose step makes one critic (judge) call per failing task
        # (~n sequential calls) then one evolve-agent call, so it can legitimately take
        # minutes — without a marker a slow diagnose is indistinguishable from a hang.
        print(f"[iter {it}] diagnosing ({sum(1 for r in inc_eval.results.values() if r.pile=='B' and not r.oos_pass)} failing B tasks)...", flush=True)
        diag = diagnose_b_pile(inc_eval, tasks, llm=llm, traces=traces).proposer_payload()

        iterdir = results_dir / f"iter_{it:03d}"
        cand_dir = iterdir / "worker"
        pred_file = iterdir / "prediction.json"
        if cand_dir.exists() and pred_file.exists():
            # RESUME: a prior (reaped) launch already produced this iteration's edit —
            # reuse it verbatim instead of re-running the evolve agent, so the candidate
            # eval below can cache-accumulate across relaunches.
            pred = json.loads(pred_file.read_text())
        else:
            snapshot_dir(incumbent, cand_dir)
            evidence_dir = None
            if cfg.evidence_mode == "ahe_corpus":
                evidence_dir = _build_evidence(iterdir / "evidence", diag, evals, traces,
                                               deliverables, tasks, records,
                                               prior_history=prior_history,
                                               attempt_scores=attempt_scores,
                                               past_edits=past_edits)
            print(f"[iter {it}] evolve agent editing the worker dir...", flush=True)
            # Both sibling agents (worker + evolve) run in the cloud when execution=e2b_full,
            # so the local orchestrator stays memory-light (matters for GDPval's heavier local
            # grade/render). The evolve backend edits a VM copy of cand_dir and downloads it back.
            if cfg.execution == "e2b_full":
                from .evolve_e2b import run_evolve_agent_e2b as _run_evolve
            else:
                _run_evolve = run_evolve_agent
            full_history = "\n".join(x for x in (prior_history, _edit_history(records)) if x)
            ev_out = _run_evolve(cand_dir, diag, iterdir,
                                 edit_history=full_history, evidence_dir=evidence_dir)
            pred = ev_out.get("prediction") or {}
            iterdir.mkdir(parents=True, exist_ok=True)
            pred_file.write_text(json.dumps(pred))
            # The final message is where the agent must justify a retry of a
            # falsified approach (anti-fixation directive) — persist it for audit.
            (iterdir / "evolve_final.txt").write_text(str(ev_out.get("final_text") or ""))
        print(f"[iter {it}] evaluating candidate on {len(tasks)} tasks...", flush=True)
        diff = dir_unified_diff(incumbent, cand_dir)
        edit = DirEdit(diff, predicted_fixes=pred.get("predicted_fixes", []),
                       risk_tasks=pred.get("risk_tasks", []))

        improved = regressed = []
        cand_scores = {}
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
            cand_evals, ct, cd, cand_mean = evaluate_dir(cand_dir, tasks, evaluator, iterdir / "grade", concurrency=cfg.concurrency, cache_dir=results_dir / "_cache", execution=cfg.execution)
            # FAIR-SUBSET keep: exclude any task that hit a transient infra failure on the
            # incumbent OR the candidate side, so infra noise (429/sandbox/disconnect) can
            # never score a task 0 and mask a real edit at the noise-floor margin. In a clean
            # run (no masking) fair_tids == all tasks and this is a no-op. The verdict AND the
            # gain gate are both computed on the fair subset for consistency.
            masked = {t.task_id for t in tasks
                      if _is_transient_error(ct.get(t.task_id, {}).get("error", ""))
                      or _is_transient_error(traces.get(t.task_id, {}).get("error", ""))}
            fair_tids = [t.task_id for t in tasks if t.task_id in cand_evals and t.task_id not in masked]
            fair_inc = statistics.mean(evals[tid].gated_score for tid in fair_tids) if fair_tids else inc_mean
            fair_cand = statistics.mean(cand_evals[tid].gated_score for tid in fair_tids) if fair_tids else cand_mean
            fair_evals = {tid: evals[tid] for tid in fair_tids}
            fair_cevals = {tid: cand_evals[tid] for tid in fair_tids}
            cls = _classify(edit, fair_evals, fair_cevals, noise_margin)
            verdict, improved, regressed = cls["verdict"], cls["flipped"], cls["regressed"]
            if masked:
                print(f"[iter {it}] fair-subset keep: {len(masked)} task(s) infra-masked and "
                      f"excluded; decided on {len(fair_tids)}/{len(tasks)} "
                      f"(fair inc={fair_inc:.4f} cand={fair_cand:.4f}, full cand={cand_mean:.4f})", flush=True)
            # promote iff a real aggregate gain beyond the noise floor AND not harmful
            kept = decide_keep_soft(fair_inc, fair_cand, noise_margin) and verdict != "HARMFUL"
            if kept and cfg.confirm_band > 0 and (fair_cand - fair_inc) < noise_margin + cfg.confirm_band:
                # Near-floor gain: one eval clearing the floor by a hair is within the
                # measured eval noise. Confirm with a second INDEPENDENT candidate eval
                # (cache_dir=None — the sig-keyed cache would just replay the first one)
                # and require the two-eval average to still clear the floor.
                print(f"[iter {it}] near-floor gain ({fair_cand - fair_inc:+.4f} < "
                      f"{noise_margin + cfg.confirm_band:.4f}): running confirmation eval...", flush=True)
                cand2, ct2, _, _ = evaluate_dir(cand_dir, tasks, evaluator, iterdir / "grade_confirm",
                                                concurrency=cfg.concurrency, cache_dir=None,
                                                execution=cfg.execution)
                fair2 = [tid for tid in fair_tids if tid in cand2
                         and not _is_transient_error(ct2.get(tid, {}).get("error", ""))]
                if fair2:
                    avg_cand = statistics.mean((cand_evals[tid].gated_score + cand2[tid].gated_score) / 2
                                               for tid in fair2)
                    avg_inc = statistics.mean(evals[tid].gated_score for tid in fair2)
                    kept = decide_keep_soft(avg_inc, avg_cand, noise_margin)
                    print(f"[iter {it}] confirmation: avg cand={avg_cand:.4f} vs inc={avg_inc:.4f} "
                          f"on {len(fair2)} task(s) -> {'CONFIRMED' if kept else 'NOT CONFIRMED (rolled back)'}", flush=True)
            if kept:
                n_kept += 1
                # Materialize the kept state INTO the incumbent_worker dir (mirror copy)
                # instead of repointing at the iter's snapshot: the iter dir stays a
                # frozen historical artifact, and results_dir/incumbent_worker — the
                # path the run advertises as "final worker dir" — is actually current.
                # (Bug: it used to hold the untouched seed forever.)
                snapshot_dir(cand_dir, results_dir / "incumbent_worker")
                incumbent = results_dir / "incumbent_worker"
                evals, traces, deliverables, inc_mean = cand_evals, ct, cd, cand_mean
            else:
                n_rb += 1
                buffer.add(edit, verdict, 0, 0, "no aggregate score gain beyond the noise floor")
            cand_scores = {str(t): round(e.gated_score, 4) for t, e in cand_evals.items()}
            attempt_scores[f"iter{it}" + (" KEPT" if kept else "")] = cand_scores
            past_edits.append({"name": f"iter_{it:03d}", "kept": kept, "verdict": verdict,
                               "summary": edit.summary, "improved": list(improved),
                               "regressed": list(regressed), "diff": diff})

        records.append(LevelBRecord(
            it, verdict in ("NO_EDIT", LEAKAGE_BLOCKED, "BLOCKED"), verdict, kept,
            edit.summary, diag.get("root_cause_tag", ""), round(inc_mean, 4),
            round(cand_mean, 4), list(improved), list(regressed)))
        ms_traj.append(round(inc_mean, 4))
        _persist(results_dir, it, verdict, kept, edit, diag, inc_mean,
                 cand_scores=cand_scores, improved=improved, regressed=regressed)

    return LevelBResult(
        n_tasks=len(tasks), mean_score_trajectory=ms_traj, records=records,
        noise_margin=round(noise_margin, 4), final_mean_score=round(inc_mean, 4),
        final_worker_dir=str(incumbent), benchmark=cfg.benchmark,
        n_kept=n_kept, n_rolled_back=n_rb, n_blocked=n_blocked)


def _persist(results_dir: Path, it: int, verdict: str, kept: bool, edit, diag: dict, inc_mean: float,
             *, cand_scores: dict = None, improved=(), regressed=()) -> None:
    d = results_dir / f"iter_{it:03d}"
    d.mkdir(parents=True, exist_ok=True)
    (d / "manifest.json").write_text(json.dumps({
        "iteration": it, "verdict": verdict, "kept": kept,
        "edit_summary": edit.summary, "diff_signature": edit.signature(),
        "predicted_fixes": list(getattr(edit, "predicted_fixes", [])),
        "risk_tasks": list(getattr(edit, "risk_tasks", [])),
        "diagnosis": diag, "inc_mean": round(inc_mean, 4),
        # Per-task outcome of this attempt — consumed by _load_prior_history /
        # _load_prior_edits when a later leg continues from this run's evolved worker.
        "cand_scores": cand_scores or {}, "improved": [str(t) for t in improved],
        "regressed": [str(t) for t in regressed],
    }, indent=2, default=str))
    (d / "edit.diff").write_text(edit.diff)
