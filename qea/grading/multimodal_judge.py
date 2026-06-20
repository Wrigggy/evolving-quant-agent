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
from dataclasses import dataclass

from ..verifier import build_rubric_prompt, score_rubric


@dataclass
class GradeResult:
    task_id: str
    multimodal_fraction: float
    text_fraction: float
    verdicts: dict
    variance: float
    degraded: bool


class MultimodalJudge:
    def __init__(self, llm, k: int = 2) -> None:
        self.llm = llm
        self.k = k

    def grade(self, task, rendered) -> GradeResult:
        items = getattr(task, "rubric_items", None) or []
        deliverable_text = rendered.extracted_text or rendered.text
        if not items:
            return GradeResult(task.task_id, 0.0, 0.0, {}, 0.0, True)

        # text-only ablation
        text_samples = []
        for _ in range(self.k):
            p = build_rubric_prompt(task, deliverable_text, items)
            frac, _ = score_rubric(self.llm.complete(p, role="judge"), items)
            text_samples.append(frac)

        # multimodal
        mm_samples = []
        last_verdicts: dict = {}
        for _ in range(self.k):
            p = build_rubric_prompt(task, deliverable_text, items, has_images=bool(rendered.images))
            frac, verdicts = score_rubric(
                self.llm.complete(p, role="judge", images=rendered.images or None), items)
            mm_samples.append(frac)
            last_verdicts = verdicts

        var = statistics.pvariance(mm_samples) if len(mm_samples) > 1 else 0.0
        degraded = bool(rendered.degraded) or not rendered.images
        return GradeResult(task.task_id, statistics.median(mm_samples),
                           statistics.median(text_samples), last_verdicts, var, degraded)
