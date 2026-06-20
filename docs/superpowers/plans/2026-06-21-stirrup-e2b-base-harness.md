# Stirrup-on-E2B Base-Harness Test — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Measure how a vanilla (unevolved) Stirrup agentic harness performs on the GDPval finance tasks in a real E2B sandbox, graded by QEA's existing per-rubric scorer fed multimodally-rendered real files.

**Architecture:** Thin parallel pipeline (Approach A). All new code is additive and isolated: a Stirrup worker → a LibreOffice render step → a multimodal per-rubric judge that *reuses* the existing `SoftJudge` scoring math → an orchestrator script. The evolve loop (`qea/loop.py`, `qea/harness.py`, `qea/debugger.py`) and the `SoftJudge` scoring math are NOT modified — the judge's *input* changes (text → rendered files), not the scoring.

**Tech Stack:** Python 3, Stirrup (`git+https://github.com/ArtificialAnalysis/Stirrup`), E2B SaaS sandbox, LibreOffice-headless + PyMuPDF for rendering, openpyxl/python-pptx/python-docx for text extraction, a Qwen-VL multimodal judge over OpenRouter, pytest.

**Spec:** `docs/superpowers/specs/2026-06-21-stirrup-e2b-base-harness-design.md`

---

## File Structure

| Path | New/Mod | Responsibility |
|------|---------|----------------|
| `pyproject.toml` | Mod | Add `[stirrup]` optional-deps extra (Stirrup, e2b, pymupdf, python-pptx, python-docx, openpyxl). |
| `.env.example` | Mod | Document `E2B_API_KEY`, Qwen-VL `QEA_JUDGE_MODEL`, `QEA_STIRRUP_MAX_TURNS`, `QEA_JUDGE_K`. |
| `scripts/stirrup_spike.py` | New | One-off live spike: pins Stirrup's finish/metadata/output-file shapes + auth env. |
| `qea/llm.py` | Mod | Add `images=` param to `complete()` on all three clients (multimodal message). |
| `qea/verifier.py` | Mod | Extract `build_rubric_prompt()` + `score_rubric()` module helpers from `SoftJudge._real_sample` (behavior-preserving). |
| `qea/grading/__init__.py` | New | Package marker. |
| `qea/grading/render.py` | New | `render(final_text, files, out_dir)` → `RenderedDeliverable{text, extracted_text, images, degraded}`. |
| `qea/grading/multimodal_judge.py` | New | `MultimodalJudge.grade(task, rendered)` → `GradeResult` (multimodal + text-only ablation). |
| `qea/workers/__init__.py` | New | Package marker. |
| `qea/workers/stirrup_worker.py` | New | `Deliverable`, `StubWorker`, `StirrupWorker.run_task(task)`. |
| `scripts/base_harness_test.py` | New | Orchestrator: tasks → worker → render → grade → `docs/RESULTS_base_stirrup_e2b.md`. |
| `tests/test_stirrup_pipeline.py` | New | Offline smoke: refactor equivalence, render degraded path, stub-worker grade. |

---

## Task 1: Dependencies, env, and the Stirrup API spike

**Files:**
- Modify: `pyproject.toml`
- Modify: `.env.example`
- Create: `scripts/stirrup_spike.py`

- [ ] **Step 1: Add the `[stirrup]` extra to `pyproject.toml`**

Under `[project.optional-dependencies]`, add:

```toml
stirrup = [
    "stirrup @ git+https://github.com/ArtificialAnalysis/Stirrup.git",
    "e2b",
    "pymupdf",
    "python-pptx",
    "python-docx",
    "openpyxl",
]
```

- [ ] **Step 2: Document new env vars in `.env.example`**

Append:

```bash
# ---- Stirrup base-harness test (qea/stirrup-e2b-base-harness) ----------------
# E2B SaaS sandbox key. Copy the working key from
# ../agentic-harness-engineering/.env (real key already present there).
# SaaS default: set ONLY this (leave E2B_API_URL / E2B_DOMAIN unset).
E2B_API_KEY="e2b_..."

# Multimodal judge. No Gemini access -> use a Qwen-VL (vision) model.
# Confirm exact OpenRouter slug at run time; fallback "qwen/qwen-vl-max".
QEA_JUDGE_MODEL="qwen/qwen3-vl-max"

# Stirrup agent turn cap and judge k-repeat (median).
QEA_STIRRUP_MAX_TURNS=20
QEA_JUDGE_K=2
```

- [ ] **Step 3: Install and copy the key**

Run:
```bash
cd /Users/kevinwu/Coding/evolving-quant-agent
pip install -e ".[real,gdpval,stirrup]"
grep -E '^E2B_API_KEY=' ../agentic-harness-engineering/.env >> .env   # then dedupe/edit .env
```
Expected: Stirrup + e2b + pymupdf import without error; `.env` contains a real `E2B_API_KEY`.

- [ ] **Step 4: Write the spike script** (`scripts/stirrup_spike.py`)

This is a *live* probe whose only job is to pin the real shapes of Stirrup's
return values + auth so Task 6 is written against facts, not guesses.

```python
"""One-off spike: pin Stirrup's E2B run shapes (finish_params/metadata/output files).

Run once after install; read the printed output and update qea/workers/stirrup_worker.py
(_final_text + auth env) to match. Not imported by anything; safe to keep or delete.
"""
import asyncio, os, json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
# Stirrup's ChatCompletionsClient may read OPENAI_API_KEY rather than OPENROUTER_API_KEY.
# Mirror the key so either name works; confirm which is actually used from the run.
os.environ.setdefault("OPENAI_API_KEY", os.environ.get("OPENROUTER_API_KEY", ""))

from stirrup import Agent
from stirrup.clients.chat_completions_client import ChatCompletionsClient
from stirrup.tools.code_backends.e2b import E2BCodeExecToolProvider


async def main() -> None:
    out_dir = Path("output/stirrup_spike")
    client = ChatCompletionsClient(
        base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        model=os.environ.get("QEA_QUANT_AGENT_MODEL", "deepseek/deepseek-v4-pro"),
    )
    code_exec = E2BCodeExecToolProvider(template="code-interpreter-v1")
    agent = Agent(client=client, name="spike", tools=[code_exec], max_turns=8)
    async with agent.session(output_dir=str(out_dir)) as session:
        finish_params, history, metadata = await session.run(
            "Create a 2-sheet Excel file report.xlsx with openpyxl: sheet 'A' cell A1='hello', "
            "sheet 'B' cell A1=42. Save it. Then reply with one sentence confirming you saved it."
        )
    print("=== finish_params ===", type(finish_params), repr(finish_params)[:2000])
    print("=== metadata ===", type(metadata), repr(metadata)[:2000])
    print("=== history len ===", len(history), "last:", repr(history[-1])[:1000] if history else None)
    print("=== output files ===", [str(p) for p in out_dir.rglob("*") if p.is_file()])


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 5: Run the spike and record findings**

Run: `python scripts/stirrup_spike.py`
Expected: `report.xlsx` appears under `output/stirrup_spike/`; the prints reveal
(a) whether the key came from `OPENAI_API_KEY` or `OPENROUTER_API_KEY`,
(b) the structure of `finish_params` (dict? object? where the final text lives),
(c) that output files are auto-downloaded to `output_dir`.
Write a 5-line note of these facts at the top of `scripts/stirrup_spike.py` as a
comment — Task 6 depends on them.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .env.example scripts/stirrup_spike.py
git commit -m "chore: stirrup deps, env, and API spike for base-harness test"
```

---

## Task 2: Multimodal support in the LLM clients

**Files:**
- Modify: `qea/llm.py`
- Test: `tests/test_stirrup_pipeline.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_stirrup_pipeline.py` with:

```python
from qea.llm import MockLLM, _encode_image


def test_mock_llm_accepts_and_ignores_images(tmp_path):
    img = tmp_path / "x.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 16)  # minimal png-ish bytes
    out = MockLLM().complete("grade this", role="judge", images=[img])
    assert out == ""


def test_encode_image_returns_base64_data_url(tmp_path):
    img = tmp_path / "x.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 16)
    url = _encode_image(img)
    assert url.startswith("data:image/png;base64,")
    assert len(url) > 30
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_stirrup_pipeline.py -v`
Expected: FAIL — `ImportError: cannot import name '_encode_image'` and `MockLLM.complete()` rejects `images`.

- [ ] **Step 3: Implement multimodal support in `qea/llm.py`**

Add at module top (after the imports):

```python
import base64


def _encode_image(path) -> str:
    """Local PNG/JPG -> data URL for multimodal message content."""
    from pathlib import Path
    p = Path(path)
    mime = "image/jpeg" if p.suffix.lower() in (".jpg", ".jpeg") else "image/png"
    b64 = base64.b64encode(p.read_bytes()).decode()
    return f"data:{mime};base64,{b64}"
```

Change `MockLLM.complete` signature to accept and ignore images:

```python
    def complete(self, prompt: str, *, role: str = "agent", images=None) -> str:  # noqa: ARG002
        return ""
```

In `OpenRouterLLM.complete`, change the signature to
`def complete(self, prompt: str, *, role: str = "agent", images=None) -> str:`
and replace the `messages=[...]` construction with:

```python
                if images:
                    content = [{"type": "text", "text": prompt}]
                    for im in images:
                        content.append({"type": "image_url", "image_url": {"url": _encode_image(im)}})
                    messages = [{"role": "user", "content": content}]
                else:
                    messages = [{"role": "user", "content": prompt}]
                resp = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.2,
                    extra_body=extra or None,
                )
```

In `AnthropicLLM.complete`, change the signature the same way and replace the
`messages=[...]` arg of `self.client.messages.create(...)` with:

```python
                if images:
                    blocks = [{"type": "text", "text": prompt}]
                    for im in images:
                        from pathlib import Path
                        data = base64.b64encode(Path(im).read_bytes()).decode()
                        mime = "image/jpeg" if str(im).lower().endswith((".jpg", ".jpeg")) else "image/png"
                        blocks.append({"type": "image", "source": {"type": "base64", "media_type": mime, "data": data}})
                    msgs = [{"role": "user", "content": blocks}]
                else:
                    msgs = [{"role": "user", "content": prompt}]
                resp = self.client.messages.create(
                    model=model,
                    max_tokens=self.max_tokens,
                    temperature=0.2,
                    messages=msgs,
                )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_stirrup_pipeline.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Commit**

```bash
git add qea/llm.py tests/test_stirrup_pipeline.py
git commit -m "feat(llm): optional image attachments for multimodal judge calls"
```

---

## Task 3: Extract the shared rubric scorer (behavior-preserving)

**Files:**
- Modify: `qea/verifier.py`
- Test: `tests/test_stirrup_pipeline.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_stirrup_pipeline.py`:

```python
from dataclasses import dataclass, field

from qea.verifier import build_rubric_prompt, score_rubric, SoftJudge


@dataclass
class _FakeTask:
    task_id: str = "T1"
    subtype: str = "valuation"
    prompt: str = "Write a memo."
    rubric_items: list = field(default_factory=lambda: [
        {"points": 2, "criterion": "States the discount rate."},
        {"points": 1, "criterion": "Gives a recommendation."},
    ])


class _FixedLLM:
    def __init__(self, text): self.text = text
    def complete(self, prompt, *, role="agent", images=None): return self.text


def test_score_rubric_points_weighted_fraction():
    items = _FakeTask().rubric_items
    frac, verdicts = score_rubric('{"1": true, "2": false}', items)
    assert abs(frac - (2 / 3)) < 1e-9
    assert verdicts == {"1": True, "2": False}


def test_build_rubric_prompt_contains_task_rubric_deliverable():
    t = _FakeTask()
    p = build_rubric_prompt(t, "MY DELIVERABLE", t.rubric_items)
    assert "Write a memo." in p and "States the discount rate." in p
    assert "MY DELIVERABLE" in p and p.rstrip().endswith("JSON:")


def test_softjudge_real_sample_uses_shared_scorer():
    t = _FakeTask()
    j = SoftJudge(_FixedLLM('{"1": true, "2": true}'))
    frac, verdicts = j._real_sample(t, "deliverable text")
    assert abs(frac - 1.0) < 1e-9
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_stirrup_pipeline.py -k rubric -v`
Expected: FAIL — `ImportError: cannot import name 'build_rubric_prompt'`.

- [ ] **Step 3: Add the module helpers and refactor `_real_sample`**

In `qea/verifier.py`, add these module-level functions (after `_truthy`, before `_SOFT_PASS`):

```python
def build_rubric_prompt(task, deliverable: str, items: list, *, has_images: bool = False) -> str:
    """Single source of truth for the per-criterion rubric prompt (text + multimodal)."""
    lines = [f"{i + 1}. (+{c['points']}) {c['criterion']}" for i, c in enumerate(items)]
    img_note = (" Rendered pages of the deliverable are attached as images; "
                "its extracted text is included below." if has_images else "")
    return (
        "You are grading a finance deliverable against an itemized GDPval rubric. "
        "For EACH numbered criterion, decide whether the deliverable satisfies it. "
        'Return ONLY a JSON object mapping each criterion number (as a string) to '
        "true or false." + img_note + "\n\n"
        f"TASK:\n{task.prompt}\n\nRUBRIC:\n" + "\n".join(lines) +
        f"\n\nDELIVERABLE:\n{deliverable}\n\nJSON:"
    )


def score_rubric(txt: str, items: list) -> tuple[float, dict]:
    """Parse judge JSON -> (points-weighted continuous fraction in [0,1], verdicts)."""
    verdicts = _parse_json_obj(txt) or {}
    earned = sum(c["points"] for i, c in enumerate(items) if _truthy(verdicts.get(str(i + 1))))
    total = sum(c["points"] for c in items) or 1.0
    return earned / total, verdicts
```

Then replace the body of `SoftJudge._real_sample` with:

```python
    def _real_sample(self, task, deliverable: str) -> tuple[float, dict]:
        """GDPval rubric grading via the shared scorer (text deliverable path)."""
        items = getattr(task, "rubric_items", None) or []
        if not items:
            return self._real_holistic(task, deliverable), {}
        prompt = build_rubric_prompt(task, deliverable, items)
        txt = self.llm.complete(prompt, role="judge")
        return score_rubric(txt, items)
```

> Note: `has_images` defaults False, so the text prompt is byte-identical to the old inline prompt — `SoftJudge` behavior is unchanged.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_stirrup_pipeline.py -k rubric -v && python -m pytest tests/test_smoke.py -v`
Expected: PASS — new scorer tests pass AND the existing smoke test still passes (no regression).

- [ ] **Step 5: Commit**

```bash
git add qea/verifier.py tests/test_stirrup_pipeline.py
git commit -m "refactor(verifier): extract shared rubric scorer (behavior-preserving)"
```

---

## Task 4: The render step (files → images + extracted text)

**Files:**
- Create: `qea/grading/__init__.py`
- Create: `qea/grading/render.py`
- Test: `tests/test_stirrup_pipeline.py`

- [ ] **Step 1: Write the failing test** (uses a tmp .xlsx, no LibreOffice required — exercises the degraded path)

Append to `tests/test_stirrup_pipeline.py`:

```python
from qea.grading.render import render, RenderedDeliverable


def _make_xlsx(path):
    from openpyxl import Workbook
    wb = Workbook(); ws = wb.active; ws["A1"] = "DISCOUNT_RATE_9PCT"; wb.save(path)


def test_render_extracts_text_and_degrades_without_render(tmp_path):
    xlsx = tmp_path / "deliverable.xlsx"; _make_xlsx(xlsx)
    out = render("final text", [xlsx], tmp_path / "render")
    assert isinstance(out, RenderedDeliverable)
    assert out.text == "final text"
    assert "DISCOUNT_RATE_9PCT" in out.extracted_text
    # images may be present (if soffice installed) or empty + degraded note (if not);
    # either way the contract holds:
    assert isinstance(out.images, list)
    assert isinstance(out.degraded, list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_stirrup_pipeline.py -k render -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'qea.grading'`.

- [ ] **Step 3: Create the package marker**

Create `qea/grading/__init__.py`:
```python
```
(empty file)

- [ ] **Step 4: Implement `qea/grading/render.py`**

```python
"""Render produced deliverable files to page images + extracted text.

LibreOffice-headless converts office files to PDF; PyMuPDF rasterizes pages to PNG.
Text is extracted per type for the text-only ablation and as judge context. If
LibreOffice or a parser is unavailable, the file degrades to text-only (logged),
never crashing the run.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

SUPPORTED = {".xlsx", ".pptx", ".docx", ".pdf"}


@dataclass
class RenderedDeliverable:
    text: str                                  # the agent's final message
    extracted_text: str                        # text pulled from produced files
    images: list = field(default_factory=list) # list[Path] of PNG page images
    degraded: list = field(default_factory=list)  # human-readable degrade notes


def _soffice() -> str | None:
    for name in ("soffice", "libreoffice"):
        p = shutil.which(name)
        if p:
            return p
    return None


def _to_pdf(f: Path, out_dir: Path) -> Path | None:
    if f.suffix.lower() == ".pdf":
        return f
    exe = _soffice()
    if not exe:
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run([exe, "--headless", "--convert-to", "pdf", "--outdir", str(out_dir), str(f)],
                   check=True, capture_output=True, timeout=120)
    pdf = out_dir / (f.stem + ".pdf")
    return pdf if pdf.exists() else None


def _pdf_to_pngs(pdf: Path, out_dir: Path, limit: int) -> list:
    import fitz  # PyMuPDF
    out_dir.mkdir(parents=True, exist_ok=True)
    imgs: list = []
    doc = fitz.open(pdf)
    try:
        for i, page in enumerate(doc):
            if len(imgs) >= limit:
                break
            pix = page.get_pixmap(dpi=110)
            png = out_dir / f"{pdf.stem}_p{i + 1}.png"
            pix.save(str(png))
            imgs.append(png)
    finally:
        doc.close()
    return imgs


def _extract_text(f: Path) -> str:
    ext = f.suffix.lower()
    if ext == ".xlsx":
        from openpyxl import load_workbook
        wb = load_workbook(f, read_only=True, data_only=True)
        out = []
        for ws in wb.worksheets:
            out.append(f"# sheet: {ws.title}")
            for row in ws.iter_rows(values_only=True):
                cells = [str(c) for c in row if c is not None]
                if cells:
                    out.append("\t".join(cells))
        return "\n".join(out)
    if ext == ".pptx":
        from pptx import Presentation
        out = []
        for i, slide in enumerate(Presentation(f).slides):
            out.append(f"# slide {i + 1}")
            for shape in slide.shapes:
                if shape.has_text_frame:
                    out.append(shape.text_frame.text)
        return "\n".join(out)
    if ext == ".docx":
        from docx import Document
        return "\n".join(p.text for p in Document(f).paragraphs)
    if ext == ".pdf":
        import fitz
        doc = fitz.open(f)
        try:
            return "\n".join(page.get_text() for page in doc)
        finally:
            doc.close()
    return ""


def render(final_text: str, files, out_dir, *, max_images: int = 8) -> RenderedDeliverable:
    out_dir = Path(out_dir)
    texts: list[str] = []
    images: list = []
    degraded: list[str] = []
    for raw in files:
        f = Path(raw)
        if f.suffix.lower() not in SUPPORTED:
            continue
        try:
            t = _extract_text(f)
            if t.strip():
                texts.append(f"=== {f.name} ===\n{t}")
        except Exception as exc:  # noqa: BLE001
            degraded.append(f"{f.name}: text-extract failed ({type(exc).__name__}: {exc})")
        if len(images) >= max_images:
            continue
        try:
            pdf = _to_pdf(f, out_dir)
            if pdf is None:
                degraded.append(f"{f.name}: LibreOffice unavailable, render skipped (text-only)")
                continue
            images.extend(_pdf_to_pngs(pdf, out_dir, max_images - len(images)))
        except Exception as exc:  # noqa: BLE001
            degraded.append(f"{f.name}: render failed ({type(exc).__name__}: {exc})")
    return RenderedDeliverable(final_text, "\n\n".join(texts), images, degraded)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_stirrup_pipeline.py -k render -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add qea/grading/__init__.py qea/grading/render.py tests/test_stirrup_pipeline.py
git commit -m "feat(grading): render produced files to images + extracted text"
```

---

## Task 5: The multimodal judge (multimodal + text-only ablation)

**Files:**
- Create: `qea/grading/multimodal_judge.py`
- Test: `tests/test_stirrup_pipeline.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_stirrup_pipeline.py`:

```python
from qea.grading.multimodal_judge import MultimodalJudge, GradeResult
from qea.grading.render import RenderedDeliverable


class _CountingLLM:
    """Returns a fixed verdict JSON; records whether images were passed each call."""
    def __init__(self): self.image_calls = 0; self.text_calls = 0
    def complete(self, prompt, *, role="agent", images=None):
        if images:
            self.image_calls += 1
        else:
            self.text_calls += 1
        return '{"1": true, "2": false}'


def test_multimodal_judge_grades_both_paths():
    t = _FakeTask()
    rendered = RenderedDeliverable("final", "extracted DISCOUNT_RATE", images=["/tmp/p1.png"], degraded=[])
    llm = _CountingLLM()
    judge = MultimodalJudge(llm, k=2)
    res = judge.grade(t, rendered)
    assert isinstance(res, GradeResult)
    assert abs(res.multimodal_fraction - (2 / 3)) < 1e-9
    assert abs(res.text_fraction - (2 / 3)) < 1e-9
    assert llm.image_calls == 2 and llm.text_calls == 2   # k=2 each path
    assert res.degraded is False                            # had images, no degrade notes
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_stirrup_pipeline.py -k multimodal_judge -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'qea.grading.multimodal_judge'`.

- [ ] **Step 3: Implement `qea/grading/multimodal_judge.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_stirrup_pipeline.py -k multimodal_judge -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add qea/grading/multimodal_judge.py tests/test_stirrup_pipeline.py
git commit -m "feat(grading): multimodal per-rubric judge with text-only ablation"
```

---

## Task 6: The Stirrup worker

**Files:**
- Create: `qea/workers/__init__.py`
- Create: `qea/workers/stirrup_worker.py`
- Test: `tests/test_stirrup_pipeline.py`

- [ ] **Step 1: Write the failing test** (stub worker — no E2B/API needed)

Append to `tests/test_stirrup_pipeline.py`:

```python
from qea.workers.stirrup_worker import Deliverable, StubWorker


def test_stub_worker_returns_deliverable(tmp_path):
    f = tmp_path / "out.xlsx"; _make_xlsx(f)
    w = StubWorker(final_text="done", files=[f])
    d = w.run_task(_FakeTask())
    assert isinstance(d, Deliverable)
    assert d.task_id == "T1" and d.final_text == "done" and d.files == [f]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_stirrup_pipeline.py -k stub_worker -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'qea.workers'`.

- [ ] **Step 3: Create the package marker**

Create `qea/workers/__init__.py`:
```python
```
(empty file)

- [ ] **Step 4: Implement `qea/workers/stirrup_worker.py`**

> Before writing `_final_text`, apply the facts recorded in the Task 1 spike
> comment (finish_params shape + which env var holds the key). The defaults below
> are defensive fallbacks; tighten them to the spike's findings.

```python
"""Vanilla Stirrup agentic worker on an E2B sandbox.

run_task(task) runs an out-of-box Stirrup Agent (default code_exec on E2B, finish
tool) on the task prompt, then returns the agent's final text + every file the
agent produced (auto-downloaded by Stirrup to the per-task output_dir). No QEA
7-slot harness is injected — this measures the BASE substrate.
"""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Deliverable:
    task_id: str
    final_text: str
    files: list  # list[Path]


class StubWorker:
    """Offline test double: returns a canned deliverable; no network."""
    def __init__(self, final_text: str, files) -> None:
        self._final_text = final_text
        self._files = list(files)

    def run_task(self, task) -> Deliverable:
        return Deliverable(task.task_id, self._final_text, self._files)


def _extract_final_text(finish_params, history) -> str:
    """Defensive: pull the agent's final message across plausible Stirrup shapes.
    Refine to the exact shape recorded in the Task 1 spike comment."""
    fp = finish_params
    if isinstance(fp, dict):
        for key in ("final_message", "message", "summary", "response", "text"):
            if fp.get(key):
                return str(fp[key])
    for attr in ("final_message", "message", "summary", "response", "text"):
        if hasattr(fp, attr) and getattr(fp, attr):
            return str(getattr(fp, attr))
    if history:
        last = history[-1]
        if isinstance(last, dict):
            return str(last.get("content", last))
        return str(getattr(last, "content", last))
    return ""


class StirrupWorker:
    def __init__(self, *, out_root: str = "output/stirrup", max_turns: int | None = None,
                 model: str | None = None, template: str = "code-interpreter-v1") -> None:
        self.out_root = Path(out_root)
        self.max_turns = max_turns or int(os.environ.get("QEA_STIRRUP_MAX_TURNS", "20"))
        self.model = model or os.environ.get("QEA_QUANT_AGENT_MODEL", "deepseek/deepseek-v4-pro")
        self.template = template
        # Stirrup's ChatCompletionsClient may read OPENAI_API_KEY; mirror the key.
        os.environ.setdefault("OPENAI_API_KEY", os.environ.get("OPENROUTER_API_KEY", ""))

    def run_task(self, task) -> Deliverable:
        return asyncio.run(self._run(task))

    async def _run(self, task) -> Deliverable:
        from stirrup import Agent
        from stirrup.clients.chat_completions_client import ChatCompletionsClient
        from stirrup.tools.code_backends.e2b import E2BCodeExecToolProvider

        out_dir = self.out_root / str(task.task_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        client = ChatCompletionsClient(
            base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            model=self.model,
        )
        code_exec = E2BCodeExecToolProvider(template=self.template)
        agent = Agent(client=client, name="qea-base", tools=[code_exec], max_turns=self.max_turns)
        async with agent.session(output_dir=str(out_dir)) as session:
            finish_params, history, _metadata = await session.run(task.prompt)
        files = [p for p in out_dir.rglob("*") if p.is_file()]
        return Deliverable(str(task.task_id), _extract_final_text(finish_params, history), files)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_stirrup_pipeline.py -k stub_worker -v`
Expected: PASS. (The real `StirrupWorker` is exercised live in Task 8, not in unit tests.)

- [ ] **Step 6: Commit**

```bash
git add qea/workers/__init__.py qea/workers/stirrup_worker.py tests/test_stirrup_pipeline.py
git commit -m "feat(workers): vanilla Stirrup-on-E2B worker + offline stub"
```

---

## Task 7: The orchestrator script + RESULTS doc

**Files:**
- Create: `scripts/base_harness_test.py`

- [ ] **Step 1: Implement the orchestrator**

```python
"""Base-harness test: vanilla Stirrup-on-E2B worker + multimodal per-rubric grade.

Loop the GDPval finance tasks (or a --n subset), run each through the Stirrup
worker, render the produced files, grade with the multimodal judge (+ text-only
ablation), and write docs/RESULTS_base_stirrup_e2b.md. Does NOT touch the evolve
loop. Compares against the prior text-worker/text-grade baseline (0.618).

Usage:
    python scripts/base_harness_test.py --n 5      # pilot subset
    python scripts/base_harness_test.py            # full set
"""
from __future__ import annotations

import argparse
import statistics
from pathlib import Path

from dotenv import load_dotenv

from qea.llm import make_llm
from qea.tasks import load_gdpval_finance
from qea.workers.stirrup_worker import StirrupWorker
from qea.grading.render import render
from qea.grading.multimodal_judge import MultimodalJudge

PRIOR_TEXT_BASELINE = 0.618  # single-call text worker + text grade (ROADMAP)


def main() -> None:
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=0, help="pilot subset size (0 = all)")
    ap.add_argument("--out", default="docs/RESULTS_base_stirrup_e2b.md")
    args = ap.parse_args()

    tasks = load_gdpval_finance(broad=True, allow_download=True)
    if args.n:
        tasks = tasks[: args.n]
    import os
    judge_k = int(os.environ.get("QEA_JUDGE_K", "2"))

    worker = StirrupWorker()
    judge = MultimodalJudge(make_llm(mock=False), k=judge_k)

    rows = []
    for i, task in enumerate(tasks, 1):
        print(f"[{i}/{len(tasks)}] {task.task_id} ({task.subtype})")
        try:
            deliverable = worker.run_task(task)
            rendered = render(deliverable.final_text, deliverable.files,
                              Path("output/render") / str(task.task_id))
            res = judge.grade(task, rendered)
            rows.append({
                "task_id": task.task_id, "subtype": task.subtype,
                "mm": res.multimodal_fraction, "text": res.text_fraction,
                "var": res.variance, "n_files": len(deliverable.files),
                "n_imgs": len(rendered.images), "degraded": res.degraded,
                "error": "",
            })
        except Exception as exc:  # noqa: BLE001
            print(f"  ERROR: {type(exc).__name__}: {exc}")
            rows.append({"task_id": task.task_id, "subtype": task.subtype, "mm": None,
                         "text": None, "var": None, "n_files": 0, "n_imgs": 0,
                         "degraded": True, "error": f"{type(exc).__name__}: {exc}"})

    ok = [r for r in rows if r["mm"] is not None]
    mean_mm = statistics.mean(r["mm"] for r in ok) if ok else 0.0
    mean_text = statistics.mean(r["text"] for r in ok) if ok else 0.0

    lines = [
        "# Base-harness test — vanilla Stirrup on E2B + multimodal per-rubric grade",
        "",
        f"Tasks graded: {len(ok)}/{len(rows)}  |  judge k={judge_k}",
        "",
        f"- **Mean multimodal rubric %:** {mean_mm:.3f}",
        f"- **Mean text-only rubric % (ablation):** {mean_text:.3f}",
        f"- **Prior text-worker/text-grade baseline:** {PRIOR_TEXT_BASELINE:.3f}",
        f"- **Worker effect (text-grade − prior):** {mean_text - PRIOR_TEXT_BASELINE:+.3f}",
        f"- **Grader-input effect (mm − text):** {mean_mm - mean_text:+.3f}",
        "",
        "| task | subtype | multimodal % | text-only % | var | files | imgs | degraded | error |",
        "|------|---------|-------------|------------|-----|-------|------|----------|-------|",
    ]
    for r in rows:
        mm = f"{r['mm']:.3f}" if r["mm"] is not None else "—"
        tx = f"{r['text']:.3f}" if r["text"] is not None else "—"
        vr = f"{r['var']:.3f}" if r["var"] is not None else "—"
        lines.append(f"| {r['task_id']} | {r['subtype']} | {mm} | {tx} | {vr} | "
                     f"{r['n_files']} | {r['n_imgs']} | {r['degraded']} | {r['error']} |")
    Path(args.out).write_text("\n".join(lines) + "\n")
    print(f"\nWrote {args.out}\n  mean multimodal={mean_mm:.3f}  mean text={mean_text:.3f}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke-check the script wiring (no live call)**

Run: `python -c "import ast; ast.parse(open('scripts/base_harness_test.py').read()); print('parse ok')"`
Expected: `parse ok`.

- [ ] **Step 3: Commit**

```bash
git add scripts/base_harness_test.py
git commit -m "feat(scripts): base-harness orchestrator + RESULTS doc writer"
```

---

## Task 8: Live pilot run, then full set

**Files:**
- Output: `docs/RESULTS_base_stirrup_e2b.md` (generated)

- [ ] **Step 1: Confirm the multimodal judge model is reachable**

Run:
```bash
python -c "from dotenv import load_dotenv; load_dotenv(); from qea.llm import make_llm; print(make_llm(False).complete('reply with the single word: ok', role='judge'))"
```
Expected: prints `ok` (or similar). If the Qwen-VL slug 404s, switch `QEA_JUDGE_MODEL`
to `qwen/qwen-vl-max` (or a confirmed Chinese multimodal slug: GLM-4V / Doubao-vision / Step-1V)
and add its provider pin via `QEA_PROVIDER_MAP` if needed.

- [ ] **Step 2: Run the pilot subset (5 tasks)**

Run: `python scripts/base_harness_test.py --n 5`
Expected: `output/stirrup/<task_id>/` populated with produced files; `output/render/<task_id>/`
contains PNGs (if LibreOffice present); `docs/RESULTS_base_stirrup_e2b.md` written with 5 rows
and the worker-effect / grader-input-effect breakdown. Inspect for: real files produced,
non-empty extracted text, sane fractions, low `degraded` count.

- [ ] **Step 3: Triage the pilot**

If `degraded` is high because LibreOffice is missing, install it
(`brew install --cask libreoffice`) and re-run. If the worker produces no files,
confirm the E2B key and `code-interpreter-v1` template. If fractions look wrong,
re-read a single `output/render/<task_id>/` deliverable against its rubric.

- [ ] **Step 4: Commit the pilot result**

```bash
git add docs/RESULTS_base_stirrup_e2b.md
git commit -m "results: Stirrup-on-E2B base-harness pilot (n=5)"
```

- [ ] **Step 5: Run the full set**

Run: `python scripts/base_harness_test.py`
Expected: full GDPval finance set graded; RESULTS doc shows mean multimodal %, mean
text-only %, and the two deltas vs the 0.618 baseline.

- [ ] **Step 6: Commit the full result and push**

```bash
git add docs/RESULTS_base_stirrup_e2b.md
git commit -m "results: Stirrup-on-E2B base-harness full run"
git push -u origin qea/stirrup-e2b-base-harness
```

---

## Self-Review

**Spec coverage:** worker=vanilla Stirrup/E2B (T6, T8) ✓; scoring math unchanged + shared scorer (T3) ✓; multimodal render input (T4, T5) ✓; Qwen-VL judge / no Gemini (T1 env, T8 step 1) ✓; text-vs-multimodal ablation (T5, T7) ✓; E2B key from AHE repo (T1) ✓; pilot-then-30 (T8) ✓; offline-testable pipeline + smoke tests (T2–T6) ✓; evolve loop untouched (no task modifies loop/harness/debugger; SoftJudge math preserved in T3) ✓; error handling: E2B/render/parse/no-files degrade paths (T4, T5, T7) ✓.

**Placeholder scan:** the only deferred-to-runtime items are the Stirrup return-value shapes and the auth env var — both are *pinned by the Task 1 live spike* with defensive fallbacks in T6, not left as "TODO". The Qwen-VL slug has a concrete default + a verification step (T8 s1) + named fallbacks. No bare TODO/TBD.

**Type consistency:** `Deliverable{task_id, final_text, files}`, `RenderedDeliverable{text, extracted_text, images, degraded}`, `GradeResult{task_id, multimodal_fraction, text_fraction, verdicts, variance, degraded}`, `build_rubric_prompt(task, deliverable, items, *, has_images)`, `score_rubric(txt, items)->(float,dict)`, `render(final_text, files, out_dir)`, `MultimodalJudge.grade(task, rendered)`, `worker.run_task(task)->Deliverable` — names used consistently across T3–T7.
