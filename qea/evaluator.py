"""Benchmark-agnostic scoring of a worker run.

The Level-B loop must run on FAB (text answers, `score_rubric`, no render) AND
GDPval (multimodal render + per-rubric judge + deliverable-format gate) without
special-casing either. Each benchmark carries an `Evaluator` that turns one
`WorkerRun` into a `TaskEval`; the loop only ever calls `evaluator.evaluate(...)`
and never imports a grader directly.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Protocol

from .grading.format_gate import apply_gate


def _write_judge_reasons(out_dir, reasons) -> None:
    """Persist the judge's per-criterion rationales to <out_dir>/judge_reasons.json.
    HUMAN DEBUG ARTIFACT ONLY: the file sits next to the eval outputs for manual
    failure triage and is read by nothing in the loop — reasons can paraphrase
    expected values, so feeding them to the debugger/evolve agent would break the
    observation firewall."""
    if not reasons or out_dir is None:
        return
    import json
    from pathlib import Path
    try:
        d = Path(out_dir)
        d.mkdir(parents=True, exist_ok=True)
        (d / "judge_reasons.json").write_text(json.dumps(reasons, indent=2, ensure_ascii=False))
    except Exception:  # noqa: BLE001 - debug artifact must never fail an eval
        pass


@dataclass
class TaskEval:
    content_score: float        # raw rubric/multimodal fraction in [0,1]
    gated_score: float          # canonical score after the deliverable-format gate
    format_ok: bool
    deliverable_text: str       # text the firewalled debugger/critic may read
    verdicts: dict = field(default_factory=dict)
    variance: float = 0.0


class Evaluator(Protocol):
    def evaluate(self, task, worker_run, out_dir) -> TaskEval: ...


class MultimodalEvaluator:
    """GDPval: render produced files -> page images + text, grade per-rubric with the
    multimodal judge, then apply the deliverable-format gate. Owns the render +
    MultimodalJudge imports the loop used to hardwire."""

    def __init__(self, llm, k: int = 2) -> None:
        from .grading.multimodal_judge import MultimodalJudge
        self.judge = MultimodalJudge(llm, k=k)

    def evaluate(self, task, worker_run, out_dir) -> TaskEval:
        from .grading.render import render
        rendered = render(worker_run.deliverable_text, worker_run.produced_files, out_dir)
        g = self.judge.grade(task, rendered)
        gated, ok = apply_gate(g.multimodal_fraction, task, worker_run.produced_files)
        _write_judge_reasons(out_dir, getattr(g, "reasons", None))
        return TaskEval(g.multimodal_fraction, gated, ok, rendered.text or "",
                        g.verdicts, g.variance)


class RubricTextEvaluator:
    """FAB: per-rubric judge over the worker's TEXT answer (k-sample median). No
    render. The format gate is a no-op for text-gold tasks (`deliverable_exts == []`
    -> `format_ok=True`, `gated == content`), so it is reused unchanged."""

    def __init__(self, llm, k: int = 2) -> None:
        self.llm = llm
        self.k = k

    def evaluate(self, task, worker_run, out_dir=None) -> TaskEval:
        from .verifier import build_rubric_prompt, rubric_reasons, score_rubric
        text = worker_run.deliverable_text or ""
        items = getattr(task, "rubric_items", None) or []
        if not items:
            return TaskEval(0.0, 0.0, True, text, {}, 0.0)
        fracs, verdicts = [], {}
        for i in range(self.k):
            with_reasons = i == self.k - 1
            raw = self.llm.complete(
                build_rubric_prompt(task, text, items, with_reasons=with_reasons), role="judge")
            f, v = score_rubric(raw, items)
            fracs.append(f)
            verdicts = v
            if with_reasons:
                _write_judge_reasons(out_dir, rubric_reasons(raw, items))
        content = statistics.median(fracs)
        gated, ok = apply_gate(content, task, worker_run.produced_files)
        var = statistics.pvariance(fracs) if len(fracs) > 1 else 0.0
        return TaskEval(content, gated, ok, text, verdicts, var)
