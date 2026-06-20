# Stirrup-on-E2B base-harness test — design

**Date:** 2026-06-21
**Branch:** `qea/stirrup-e2b-base-harness`
**Status:** approved (brainstorm) → ready for implementation plan

## Goal (first principles)

Measure how a **base (unevolved) agentic harness** performs on the GDPval
finance/accounting tasks, using the *official* agentic substrate (Artificial
Analysis' [Stirrup](https://github.com/ArtificialAnalysis/Stirrup)) running in a
real E2B sandbox, graded by the **existing per-rubric scorer with its scoring math
unchanged** but fed *multimodally rendered real files* instead of a text string.

This establishes the honest baseline / headroom that QEA v0 lacked: prior runs
used a single-call text worker graded on text only, which capped the mean rubric
score at ~0.618 (depressed by format/layout criteria a text worker cannot satisfy).

**Explicit non-goal:** the evolution loop is NOT touched. No changes to
`qea/loop.py`, `qea/harness.py`, `qea/debugger.py`, or the `SoftJudge` scoring
math. This is a measurement of the substrate, not an evolution run.

## Key decisions (resolved in brainstorm)

1. **Worker = vanilla Stirrup on E2B (SaaS).** Out-of-box Stirrup `Agent` with its
   default `code_exec` + finish tools, E2B backend. Truest "official base harness"
   reference. No QEA 7-slot harness injection (that is Track-2, later).
2. **Scoring math unchanged.** Per-criterion `earned/total` continuous fraction,
   exactly as in `SoftJudge._real_sample`. The multimodal grader *imports/reuses*
   that scorer; it does not reimplement it.
3. **Grader input = full multimodal render.** Produced `.xlsx/.pptx/.docx/.pdf`
   files → LibreOffice-headless → PNG page images. The judge reads images +
   extracted text. Closest to AA's multimodal parsing.
4. **Judge model = a Chinese multimodal model (no Gemini access).** Default to a
   **Qwen-VL** variant (vision-capable, same family as the current default
   `qwen` judge, available via OpenRouter), configured through `QEA_JUDGE_MODEL`.
   E.g. `qwen/qwen3-vl-max` (confirm exact OpenRouter slug at implementation time;
   fall back to `qwen/qwen-vl-max`). Other Chinese multimodal options if Qwen-VL is
   unavailable: GLM-4V (Zhipu), Doubao-vision, Step-1V.
5. **Ablation logged.** For the *same* Stirrup deliverable, record BOTH a
   text-only grade (existing path) and the multimodal grade. The text grade
   isolates the *worker* effect; the multimodal grade adds the *grader-input*
   effect. This is what makes the single new number interpretable against 0.618.
6. **E2B key source.** A working `E2B_API_KEY` already exists in
   `agentic-harness-engineering/.env` (real key, SaaS default — no `E2B_API_URL`/
   `E2B_DOMAIN`). Copy it into the QEA `.env`. Do not hardcode or commit it.
7. **Scope.** Pilot subset first (`--n 5`, spanning subtypes incl. the
   Accountants/Auditors *wall* task that requires real file output), inspect the
   RESULTS doc, then full 30.

## Architecture: thin parallel pipeline (Approach A)

All new code is additive and isolated. The evolve loop, harness model, and
`SoftJudge` scoring are imported, never modified.

```
GDPval finance task.prompt
        │
        ▼
qea/workers/stirrup_worker.py  ── vanilla Stirrup Agent on E2B
        │   Deliverable{ final_text, files:[paths] }
        ▼
qea/grading/render.py          ── LibreOffice-headless: files → [png] (+ text extract)
        │   RenderedDeliverable{ text, images:[png], extracted_text }
        ▼
qea/grading/multimodal_judge.py ── reuses SoftJudge per-criterion scorer,
        │                           attaches images+text to a Qwen-VL judge
        │   (multimodal fraction, verdicts)  AND  (text-only fraction)  ← ablation
        ▼
scripts/base_harness_test.py   ── loop tasks, aggregate mean, write RESULTS doc
```

## Components (all new)

### `qea/workers/stirrup_worker.py`
- `StirrupWorker.run_task(task) -> Deliverable` where `Deliverable` carries
  `final_text: str` and `files: list[Path]`.
- Configures a **vanilla** Stirrup `Agent`: default `LocalCodeExec`-equivalent
  tool bound to an **E2B** sandbox backend, finish tool, `max_turns` cap
  (env `QEA_STIRRUP_MAX_TURNS`, default e.g. 20).
- System prompt = the GDPval task prompt verbatim (no QEA harness injection).
- After the run: enumerate files written in the sandbox working dir, download them
  locally to a per-task output dir, return paths + the agent's final message.
- Reads `E2B_API_KEY` from env. Worker LLM = `QEA_QUANT_AGENT_MODEL` (current QEA
  worker model) via Stirrup's `ChatCompletionsClient`/LiteLLM pointed at the same
  OpenRouter (or DashScope) endpoint QEA already uses.

### `qea/grading/render.py`
- `render(files) -> RenderedDeliverable` — for each supported file, LibreOffice
  headless convert to PDF then rasterize pages to PNG (e.g. `pdftoppm`/`pymupdf`),
  AND extract text (openpyxl / python-pptx / python-docx / pdf text) for the
  text-only ablation path and as judge context.
- Degraded fallback: if render fails for a file, log `"degraded"` and use its
  extracted text only.

### `qea/grading/multimodal_judge.py`
- `grade(task, deliverable) -> GradeResult` returning `multimodal_fraction`,
  `text_fraction`, `verdicts`, `variance`, and `degraded` flags.
- **Reuses the exact per-criterion rubric prompt + `earned/total` aggregation**
  factored out of `SoftJudge._real_sample` (refactor that method into a shared
  helper that both the text judge and the multimodal judge call — no scoring-math
  divergence). k-repeat median identical to the existing path
  (`QEA_JUDGE_K`, default 2).
- Multimodal call attaches the rendered PNGs + extracted text; text-only call uses
  extracted text alone (the ablation), against the same rubric.

### `qea/llm.py` (extend, do not rewrite)
- Add optional `images: list[Path] | None` to `complete(...)` on both
  `OpenRouterLLM` and `AnthropicLLM`. When present, build a multimodal `content`
  array: OpenAI-compatible `image_url` (`data:image/png;base64,...`) blocks for
  OpenRouter; Anthropic image source blocks for the DashScope gateway.
- `MockLLM.complete` accepts and ignores `images` (offline path).

### `scripts/base_harness_test.py`
- Loads N GDPval finance tasks (`--n` pilot flag; default full 30).
- For each: `StirrupWorker.run_task` → `render` → `multimodal_judge.grade`.
- Aggregates mean multimodal %, mean text-only %, per-task table, variance,
  turn/token cost, degraded count.
- Writes `docs/RESULTS_base_stirrup_e2b.md` with the comparison against the prior
  text-worker/text-grade baseline (0.618).

## Data shapes

- `Deliverable{ task_id, final_text:str, files:[Path] }`
- `RenderedDeliverable{ text:str, images:[Path], extracted_text:str, degraded:[str] }`
- `GradeResult{ task_id, multimodal_fraction:float, text_fraction:float,
  verdicts:dict, variance:float, degraded:bool }`

## Error handling

- E2B sandbox create/exec failure → retry with backoff (reuse QEA retry envs),
  then mark task `error` and continue.
- LibreOffice render failure → degraded text-only for that file (logged).
- Judge JSON parse failure → existing `_parse_json_obj` fallback (verdicts `{}` →
  fraction 0 contribution for that criterion), consistent with current behavior.
- No files produced by the agent → grade text-only, flag `degraded=True`.
- Per-task `max_turns` and per-run token/$ logging guard runaway cost.

## Testing

- **Offline stub worker:** a fake `StirrupWorker` returning a canned deliverable +
  a tiny committed sample `.xlsx`, so `render` + `multimodal_judge` are testable
  without E2B or API (judge stubbed via `MockLLM` returning a fixed verdict JSON).
- `tests/test_stirrup_pipeline.py` smoke test: stub worker → render → grade →
  asserts a fraction in [0,1] and that scoring matches the shared `SoftJudge`
  helper on the same text.

## Dependencies / setup

- Stirrup via a new `[stirrup]` extra in `pyproject.toml` (`pip install` from its
  git repo). Plus `e2b` (or Stirrup's E2B extra), and render deps
  (`python-pptx`, `python-docx`, `pymupdf`/`pdf2image`; openpyxl already present).
- System: LibreOffice headless available locally (or in the render step's
  environment).
- `.env` additions: `E2B_API_KEY` (copied from AHE repo), `QEA_JUDGE_MODEL` set to
  a Qwen-VL slug, `QEA_STIRRUP_MAX_TURNS`, `QEA_JUDGE_K`.

## Out of scope (deferred)

- Wiring Stirrup into the evolve loop (Track-2 coupling).
- Pairwise-vs-gold Elo grading (deleted in prior design; not revived).
- Gold human-deliverable acquisition / leakage-corpus enrichment.
- Self-hosted E2B (SaaS default is sufficient).
