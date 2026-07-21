# Benchmark Authority Report Rewrite Design

> Date: 2026-07-21
>
> Target: `docs/reports/2026-07-21-qea-benchmark-authority-screen-report.md` and its PDF
>
> Status: approved content direction; implementation pending user review of this written specification

## Goal

Revise the benchmark authority screen report so it documents the evidence collected so far without treating the evolution-benchmark architecture as settled. The expanded report should make the single-benchmark versus multi-benchmark choice, held-out evaluation, and capability coverage easy to discuss before a small pilot is run.

## Editorial Scope

- Preserve the existing factual benchmark screen, benchmark tables, provenance boundaries, and GDPval/BTB case studies in Part 1.
- Expand Part 1 with a clearer distinction between:
  - facts established by the benchmark screen;
  - interpretations suggested by current project evidence;
  - hypotheses that still require a pilot.
- Make only the minimum consistency edits to Part 0. Its conclusion will say that the screen produced a candidate set and capability map, while the choice between single-benchmark and multi-benchmark evolution remains open.
- Delete Part 2, `分析 / Analysis`, in full. Do not move its fixed suite weights, `UpgradeIndex`, adapter architecture, or multi-fidelity recommendation into another numbered analysis section.
- Keep the remaining sections numbered as Parts 3 and 4, matching the user's requested structure.
- Replace Part 3 with exactly two substantive open questions.
- Replace Part 4 with a small-test plan after an initial benchmark choice. Do not include license work.

## Part 1 Expansion

Part 1 will retain its current subsections and add a concluding subsection titled `1.5 当前证据能回答什么、仍需验证什么 / What the Evidence Resolves and What Remains Open`.

That subsection will cover:

1. **Capability map.** Describe QFBench as the strongest deterministic quant-task candidate, FINCH as an enterprise finance/accounting workflow candidate, BTB as an investment-banking deliverable candidate, and GDPval as an authoritative professional-task transfer candidate. These descriptions define capability coverage, not a finalized evolution suite.
2. **Single-benchmark hypothesis.** Explain that a single benchmark offers cleaner attribution and a simpler reward signal, but may only demonstrate improvement on one task distribution or capability family.
3. **Multi-benchmark hypothesis.** Explain that multiple benchmarks may test whether one evolver can improve multiple capabilities, such as quant analysis, enterprise finance workflows, and banking deliverables. Also state that observed gains could be confounded by routing, benchmark weights, grader differences, or output-format adaptation.
4. **Held-out evaluation hypothesis.** State that repeated evolution on a single public benchmark raises overfitting and contamination concerns, making a lineage-aware held-out split a central design question. For multiple benchmarks, leave open whether each benchmark needs its own held-out split and whether cross-benchmark transfer can serve as an additional test.
5. **Benchmark relationship hypothesis.** Present two candidate multi-benchmark designs without choosing between them: benchmarks from related finance-workflow categories, such as GDPval and FINCH; or complementary capability benchmarks, such as QFBench, FINCH, and BTB.
6. **Evidence boundary.** Clearly label the above as proposed interpretations or hypotheses. Do not describe any benchmark combination, aggregate reward, adapter compatibility, or evolution gain as measured.

## Part 3 Replacement

Part 3 will contain only these two questions, edited for clarity but not answered prematurely:

1. Should evolution use a single benchmark or multiple benchmarks? If multiple benchmarks are used, can they deliberately evolve multiple capabilities, such as quant analysis, FINCH-style enterprise finance workflows, and BTB-style banking deliverables?
2. If a single benchmark is used, is a held-out test required to demonstrate generalization rather than benchmark-specific optimization? If multiple benchmarks are used, should they come from the same or closely related category, such as GDPval and FINCH, or cover complementary categories?

All other current Part 3 questions will be removed, including the separate questions about universal versus specialized workers, judge noise, license, version drift, and incomplete adapter pilots.

## Part 4 Replacement

Part 4 will be a short next-week plan:

1. Make a preliminary benchmark choice or shortlist.
2. Run a deliberately small pilot on a few representative tasks.
3. Compare the observed evolution effect, stability, and any cross-task or cross-benchmark transfer signal.
4. Use the pilot result to refine the benchmark decision before larger integration or experiments.

The plan will not include license auditing, outreach to benchmark authors, or a publishable data statement.

## Consistency and Integrity Rules

- Preserve source-backed factual claims and existing citations unless a sentence must be softened to keep the report internally consistent.
- Do not claim that single-benchmark or multi-benchmark evolution is already preferred, implemented, or measured.
- Do not reintroduce the deleted Part 2 conclusions under a different heading.
- Keep the report's current bilingual heading style and concise mentor-facing tone.
- Treat the repository's canonical project memory and the later QFBench/runtime decision as separate current records; this edit changes the requested report artifact only.

## PDF Regeneration and Verification

- Update the Markdown source first, then regenerate the PDF with its existing A4 visual style and stable filename.
- Render every page to PNG and inspect section transitions, tables, Chinese glyphs, wrapping, page numbers, and links.
- Extract text from the final PDF to confirm that Part 2 and all removed Part 3/license-plan language are absent, while the two replacement questions and small-test plan are present.
- Deliver both the revised Markdown source and PDF; do not change benchmark code or run paid/networked experiments.
