# Open issues (tracked, not yet fixed)

## 1. Grader context overflow on data-heavy deliverables
**Status:** mitigated, not solved. **Filed:** 2026-06-23.

A data-heavy `.xlsx` (e.g. the agent copies a full reference population into the
deliverable) extracts to >1M tokens, which overflowed the multimodal judge's
context (observed 1,103,526 tokens vs a 1,000,000 limit → HTTP 400).

**Current mitigation:** `qea/grading/multimodal_judge.py` caps the deliverable text
fed to the judge at `QEA_JUDGE_DELIVERABLE_CHARS` (default 60k chars); page images
still carry the layout. This stops the overflow but a hard truncation can drop
rubric-relevant rows/values beyond the cap.

**Proper fix (later):** structured/section-aware reduction instead of a blind char
cap — e.g. (a) per-sheet sampling that keeps headers + a representative slice + any
cells matching rubric keywords, (b) chunked grading (grade per criterion against the
most relevant slice), or (c) a context-compression pass. Decide when the GDPval-on-
NexAU full run shows how often the cap bites.
