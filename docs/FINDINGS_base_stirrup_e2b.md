# Findings — vanilla Stirrup-on-E2B base harness (GDPval finance, 2026-06-21)

Setup: vanilla Stirrup agentic worker (deepseek-v4-pro), E2B sandbox, GDPval
reference INPUT files uploaded, multimodal per-rubric grading (qwen/qwen3.7-plus
over LibreOffice-rendered pages + extracted text), scoring math unchanged from
`SoftJudge`. Concurrency 16 (under the 20 E2B cap). Evolve loop untouched.

Raw table: `docs/RESULTS_base_stirrup_e2b.md`. First attempt at concurrency 20 lost
~10 tasks to E2B's 20-sandbox cap (boundary 429s): `docs/RESULTS_base_stirrup_e2b_run1_partial.md`.

## Headline

- **Graded: 27/30.** Residual failures: 2× LLM `Server disconnected` (proxy,
  exhausted transport retries), 1× `JSONDecodeError` (Stirrup parsing a malformed
  tool call). No re-roll on any (LLM-single-attempt contract).
- **Mean multimodal rubric %: 0.689** | text-only: 0.661 | prior no-input
  text-baseline: 0.618.
- **The aggregate understates capability.** Split by whether the agent produced a
  deliverable at all:
  - **21/27 produced a deliverable → mean multimodal 0.873 (text 0.837).** Strong.
  - **5/27 produced NO deliverable → scored 0.** These are genuine base-harness
    misses (max-turns / couldn't complete), not grading artifacts.
  - 1 partial/degraded (`6074bba3`, 0.258).

## What this says about the base harness

1. **When it finishes, the vanilla agentic harness is strong (~0.87).** Real files
   produced (xlsx/pdf/csv), rendered, graded per-rubric. This is well above the
   0.618 prompt-only/text-only baseline — but the honest comparison is the
   completion-conditioned 0.87 vs the non-completion 0.

2. **The reference-file fix matters a lot.** With GDPval input files uploaded,
   `83d10b06` went 0.52–0.66 (improvising) → **0.992** (real input). Faithfulness
   to the benchmark's intended setup changes the result materially.

3. **New dominant failure mode: non-completion on heavy-input tasks.** The two
   monster-input tasks (`43dc9778` = 15 input files, `ee09d943` = 17) both scored
   0 — 40 turns is not enough to ingest that much data and produce a deliverable.
   `7d7fc9a7` (6 inputs) did complete (0.853). So ≤~6 inputs OK, 15–17 overflow the
   turn budget. Candidate next step: higher `max_turns` for high-input tasks, or a
   data-triage step.

4. **Grader-input effect (multimodal vs text) is small and mixed (+0.028 overall).**
   Seeing the rendered file changes the score per task in both directions
   (`9a0d8d36`: mm 0.962 vs text 0.760; `4520f882`: 0.686 vs 0.406; others equal or
   slightly lower). Net slightly positive here; the earlier n=2/3 pilots saw
   slightly negative — i.e. the effect is real but second-order vs completion.

## Issues to flag (not fixed; scoring left as-is per instruction)

- **Scores can exceed 1.0 (`2d06bc0a` = 1.066).** GDPval rubrics include NEGATIVE
  (penalty) criteria, so `earned/total` can be >1 when the deliverable banks
  positives and avoids penalties (total denominator shrinks). The inherited
  `score_rubric` does not handle penalty criteria or clamp. Decide: clamp to [0,1],
  or score against positive-points only, or model penalties explicitly.
- **Residual transient failures (3/30).** LLM proxy disconnects + one tool-call
  parse error. Re-runnable (these produced no output, so re-running is not a
  re-roll), but left as honest failures here.
- **Concurrency headroom.** Run a few under the E2B cap (16 for a 20-cap); running
  at exactly the cap races sandbox-cleanup → 429.

## Caveats

- Worker model deepseek-v4-pro; judge qwen/qwen3.7-plus (no Gemini access). The
  0.618 baseline used a different (text) judge over a slightly different setup, so
  the +0.043 "worker effect" is directional, not a controlled delta.
- Vanilla Stirrup = no QEA 7-slot harness, not wired into the evolve loop
  (Track-2). This measures the base substrate only.
