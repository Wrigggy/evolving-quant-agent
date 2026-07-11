"""Per-rubric judge over multimodally-rendered deliverables.

Reuses the SHARED scorer (qea.verifier.build_rubric_prompt + score_rubric) so the
scoring math is identical to SoftJudge. Produces two reads of the SAME deliverable:
- multimodal_fraction: rubric % with rendered page images + extracted text attached
- text_fraction:       rubric % with extracted text only (the ablation that isolates
                       the worker effect from the grader-input effect)
k-repeat median, matching the existing soft-judge denoising.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from ..verifier import build_rubric_prompt, rubric_reasons, score_rubric


@dataclass
class GradeResult:
    task_id: str
    multimodal_fraction: float
    text_fraction: float
    verdicts: dict
    variance: float
    degraded: bool
    # Per-criterion judge rationales (reason mode). HUMAN DEBUG ONLY: the evaluator
    # writes these to judge_reasons.json and they must never reach TaskEval or the
    # debugger/evolve evidence path (a reason can paraphrase expected values).
    reasons: dict = field(default_factory=dict)


class MultimodalJudge:
    def __init__(self, llm, k: int = 2) -> None:
        self.llm = llm
        self.k = k

    # Cap deliverable text fed to the judge: a data-heavy .xlsx can extract to >1M
    # tokens and overflow the judge's context. Page images carry the layout; this
    # bounds the text portion. Tunable via QEA_JUDGE_DELIVERABLE_CHARS.
    import os as _os
    MAX_DELIVERABLE_CHARS = int(_os.environ.get("QEA_JUDGE_DELIVERABLE_CHARS", "60000"))

    def grade(self, task, rendered) -> GradeResult:
        items = getattr(task, "rubric_items", None) or []
        deliverable_text = (rendered.extracted_text or rendered.text)[:self.MAX_DELIVERABLE_CHARS]
        if not items:
            return GradeResult(task.task_id, 0.0, 0.0, {}, 0.0, True)

        # text-only ablation
        text_samples = []
        for _ in range(self.k):
            p = build_rubric_prompt(task, deliverable_text, items)
            frac, _ = score_rubric(self.llm.complete(p, role="judge"), items)
            text_samples.append(frac)

        # multimodal — the LAST sample runs in reason mode so every eval leaves a
        # per-criterion "why" trail for humans (debug artifact; never fed onward).
        mm_samples = []
        last_verdicts: dict = {}
        reasons: dict = {}
        for i in range(self.k):
            with_reasons = i == self.k - 1
            p = build_rubric_prompt(task, deliverable_text, items,
                                    has_images=bool(rendered.images), with_reasons=with_reasons)
            raw = self.llm.complete(p, role="judge", images=rendered.images or None)
            frac, verdicts = score_rubric(raw, items)
            mm_samples.append(frac)
            last_verdicts = verdicts
            if with_reasons:
                reasons = rubric_reasons(raw, items)

        var = statistics.pvariance(mm_samples) if len(mm_samples) > 1 else 0.0
        degraded = bool(rendered.degraded) or not rendered.images
        return GradeResult(task.task_id, statistics.median(mm_samples),
                           statistics.median(text_samples), last_verdicts, var, degraded,
                           reasons=reasons)
