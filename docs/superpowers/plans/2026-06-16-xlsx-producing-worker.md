# File-producing B-pile worker (xlsx) — Implementation Plan (v0.1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the real B-pile worker produce a real `.xlsx` (worker writes openpyxl code → subprocess sandbox runs it → file is persisted + rendered to text appended to the deliverable), so the current `SoftJudge` can credit artifact rubric criteria and the "format basin" unblocks.

**Architecture:** A subprocess-based `exec_artifact` (AHE `LocalSandbox` pattern: `python script.py` in a throwaway temp work_dir, scrubbed env, kill-on-timeout) plus an `artifacts` module (extract openpyxl code → exec → persist → render). The B worker self-selects code vs text. `EvalSummary.deliverables` stays `str` (= narrative + rendered artifact); A-pile, the gate, firewall, leakage guard, and mock are untouched.

**Tech Stack:** Python 3.10+, `openpyxl` (new `[artifacts]` extra), stdlib `subprocess`, `pytest`. Spec: `docs/superpowers/specs/2026-06-16-xlsx-producing-worker-design.md`. Branch: `qea/xlsx-producing-worker`. Ships as **v0.1**.

---

## File map
- `pyproject.toml` — add `[artifacts]` optional extra (`openpyxl`); bump `version` to `0.1.0` (Task 6).
- `qea/sandbox.py` (**new**) — `ArtifactResult` + `exec_artifact(code, timeout)`: the subprocess executor.
- `qea/artifacts.py` (**new**) — `extract_openpyxl_code(text)`, `render_xlsx(path, …)`, `assemble_artifact_deliverable(llm_text, task, artifact_dir)`: extraction + rendering + orchestration. (openpyxl imported lazily inside functions so the module imports without the extra.)
- `qea/harness.py` — `seed_harness()` adds the `tool:xlsx_writer` seed component.
- `qea/agents.py` — `_quant_solve_real` B branch calls the orchestration when `xlsx_writer` is present; `quant_agent_solve` gains `artifact_dir`.
- `qea/loop.py` — thread `artifact_dir` through `evaluate`/`_score_one`; `run_gdpval_soft` passes `Path(cfg.results_dir)/"artifacts"`.
- `tests/test_smoke.py` — new tests (artifact-touching ones use `pytest.importorskip("openpyxl")` so the pure-stdlib core stays green without the extra).
- `README.md`, `ROADMAP.md` — docs + v0.1 (Task 6).

---

## Task 1: Subprocess executor `exec_artifact`

**Files:**
- Modify: `pyproject.toml`
- Create: `qea/sandbox.py`
- Test: `tests/test_smoke.py::test_exec_artifact_*`

- [ ] **Step 1: Add the `[artifacts]` extra** to `pyproject.toml` (under `[project.optional-dependencies]`, after the `gdpval` line):

```toml
# Real .xlsx artifact production by the B-pile worker (subprocess exec + render).
artifacts = ["openpyxl>=3.1"]
```
Then install it locally so the tests can run: `pip install -e ".[artifacts]"`.

- [ ] **Step 2: Write the failing tests** (append to `tests/test_smoke.py`):

```python
def test_exec_artifact_produces_xlsx_and_scrubs_env(tmp_path, monkeypatch):
    import pytest
    pytest.importorskip("openpyxl")
    from qea.sandbox import exec_artifact
    monkeypatch.setenv("OPENROUTER_API_KEY", "SECRET_KEY_DO_NOT_LEAK")
    code = (
        "import openpyxl, os\n"
        "assert 'OPENROUTER_API_KEY' not in os.environ, 'secret leaked into child'\n"
        "wb = openpyxl.Workbook(); ws = wb.active; ws['A1'] = 'hello'\n"
        "wb.save('report.xlsx')\n"
    )
    res = exec_artifact(code, timeout=10.0)
    assert res.status == "success"
    assert len(res.paths) == 1 and res.paths[0].name == "report.xlsx"


def test_exec_artifact_error_and_timeout_dont_crash_parent():
    import pytest
    from qea.sandbox import exec_artifact
    err = exec_artifact("raise RuntimeError('boom')\n", timeout=10.0)
    assert err.status == "error" and "boom" in err.stderr
    slow = exec_artifact("while True:\n    pass\n", timeout=1.0)
    assert slow.status == "timeout"   # parent process is still alive to assert this
```

- [ ] **Step 3: Run, expect FAIL** — `python3 -m pytest tests/test_smoke.py::test_exec_artifact_produces_xlsx_and_scrubs_env -v` → FAIL (no `qea.sandbox`).

- [ ] **Step 4: Create `qea/sandbox.py`:**

```python
"""Subprocess-based file-capable executor for B-pile artifact code.

Pattern mirrors AHE's nexau `LocalSandbox`: run model-written code as a SEPARATE
`python script.py` process in a throwaway work_dir, with a scrubbed env and
kill-on-timeout. Isolation is the OS process boundary, not a crippled in-process
interpreter — so the child can `import openpyxl` and write files normally. This is
the v0.1 posture; container/cloud isolation (docker / nexau E2BSandbox) is ROADMAP.
The strict in-process `safe_exec_solve` (A-pile, no files) is unaffected.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ArtifactResult:
    status: str                         # "success" | "error" | "timeout"
    paths: list = field(default_factory=list)   # produced *.xlsx Paths (in work_dir)
    stdout: str = ""
    stderr: str = ""
    work_dir: str = ""                  # temp dir holding artifacts (caller copies, then removes)


def _scrubbed_env() -> dict:
    """Child env minus secrets so model-written code cannot exfiltrate credentials."""
    out = {}
    for k, v in os.environ.items():
        ku = k.upper()
        if ku.endswith("_API_KEY") or ku.endswith("_TOKEN") or ku.startswith("OPENROUTER"):
            continue
        out[k] = v
    return out


def exec_artifact(code: str, timeout: float = 10.0) -> ArtifactResult:
    """Run `code` as `python script.py` in a fresh temp work_dir; collect produced
    *.xlsx. Never raises for child failures — returns an ArtifactResult."""
    work_dir = tempfile.mkdtemp(prefix="qea_artifact_")
    (Path(work_dir) / "script.py").write_text(code, encoding="utf-8")
    try:
        proc = subprocess.run(
            [sys.executable, "script.py"],
            cwd=work_dir, timeout=timeout, capture_output=True, text=True,
            env=_scrubbed_env(),
        )
    except subprocess.TimeoutExpired as exc:
        return ArtifactResult(status="timeout", stdout=(exc.stdout or ""),
                              stderr=(exc.stderr or ""), work_dir=work_dir)
    paths = sorted(Path(work_dir).glob("*.xlsx"))
    status = "success" if (proc.returncode == 0 and paths) else "error"
    return ArtifactResult(status=status, paths=paths,
                          stdout=proc.stdout, stderr=proc.stderr, work_dir=work_dir)
```

- [ ] **Step 5: Run, expect PASS** — `python3 -m pytest tests/test_smoke.py::test_exec_artifact_produces_xlsx_and_scrubs_env tests/test_smoke.py::test_exec_artifact_error_and_timeout_dont_crash_parent -v` → PASS. Then full suite `python3 -m pytest -q` → still green (other tests unaffected).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml qea/sandbox.py tests/test_smoke.py
git commit -m "feat(sandbox): subprocess exec_artifact (file-capable, scrubbed env, kill-on-timeout)"
```

---

## Task 2: `render_xlsx` + `extract_openpyxl_code`

**Files:**
- Create: `qea/artifacts.py`
- Test: `tests/test_smoke.py::test_render_xlsx_*`, `::test_extract_openpyxl_code`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_smoke.py`):

```python
def test_render_xlsx_dumps_values_and_formulas(tmp_path):
    import pytest
    pytest.importorskip("openpyxl")
    import openpyxl
    from qea.artifacts import render_xlsx
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Summary"
    ws["A1"] = "Revenue"; ws["B1"] = 1000; ws["B2"] = "=B1*2"
    p = tmp_path / "model.xlsx"; wb.save(p)
    text = render_xlsx(p)
    assert "[ARTIFACT FILE: model.xlsx]" in text
    assert 'Sheet "Summary"' in text
    assert "'Revenue'" in text and "1000" in text
    assert "=B1*2" in text          # formula string is rendered (data_only=False)


def test_extract_openpyxl_code():
    from qea.artifacts import extract_openpyxl_code
    md = "Here is the workbook:\n```python\nimport openpyxl\nwb=openpyxl.Workbook()\nwb.save('x.xlsx')\n```\nDone."
    code = extract_openpyxl_code(md)
    assert code is not None and "openpyxl" in code and "save(" in code
    assert extract_openpyxl_code("just a plain memo, no code") is None
    assert extract_openpyxl_code("```python\nprint('hi')\n```") is None  # not an artifact block
```

- [ ] **Step 2: Run, expect FAIL** — no `qea.artifacts`.

- [ ] **Step 3: Create `qea/artifacts.py`** (openpyxl imported lazily inside `render_xlsx` so the module imports without the extra):

```python
"""Artifact handling for the B-pile worker: extract the worker's openpyxl code,
render a produced .xlsx to faithful text, and orchestrate produce->capture->render.

The text rendering is the interim grader bridge (sub-project 1): it makes artifact
rubric criteria creditable by the existing text SoftJudge. NOTE (known v0.1 limit):
openpyxl-written formulas carry no computed value, so we render the formula STRING +
literal values, not formula results — value computation is sub-project 3."""
from __future__ import annotations

import shutil
from pathlib import Path


def extract_openpyxl_code(text: str) -> str | None:
    """Return the first ```python code block that builds + saves a workbook
    (mentions openpyxl AND saves), else None (text deliverable)."""
    if "```" not in text:
        return None
    parts = text.split("```")
    for i in range(1, len(parts), 2):           # odd indices are fenced blocks
        block = parts[i]
        if block.startswith("python"):
            block = block[len("python"):]
        if "openpyxl" in block and ".save(" in block:
            return block.strip()
    return None


def _strip_code_blocks(text: str) -> str:
    """Drop fenced ``` blocks, leaving the narrative."""
    if "```" not in text:
        return text.strip()
    parts = text.split("```")
    return "".join(parts[i] for i in range(0, len(parts), 2)).strip()


def render_xlsx(path, max_rows: int = 100, max_cols: int = 30) -> str:
    """Faithful text dump of a workbook: filename + per-sheet name/dims + a bounded
    grid of non-empty cells (literal values, and formula strings for formula cells)."""
    import openpyxl  # lazy: keeps qea.artifacts importable without the [artifacts] extra
    wb = openpyxl.load_workbook(path, data_only=False)
    lines = [f"[ARTIFACT FILE: {Path(path).name}]"]
    for ws in wb.worksheets:
        lines.append(f'Sheet "{ws.title}" ({ws.max_row}x{ws.max_column}):')
        for row in ws.iter_rows(max_row=min(ws.max_row, max_rows),
                                max_col=min(ws.max_column, max_cols)):
            for cell in row:
                if cell.value is not None:
                    lines.append(f"  {cell.coordinate}: {cell.value!r}")
        if ws.max_row > max_rows or ws.max_column > max_cols:
            lines.append(f"  ...(truncated to {max_rows}x{max_cols})")
    return "\n".join(lines)
```

- [ ] **Step 4: Run, expect PASS** — `python3 -m pytest tests/test_smoke.py::test_render_xlsx_dumps_values_and_formulas tests/test_smoke.py::test_extract_openpyxl_code -v`.

- [ ] **Step 5: Commit**

```bash
git add qea/artifacts.py tests/test_smoke.py
git commit -m "feat(artifacts): render_xlsx (values+formula strings) + extract_openpyxl_code"
```

---

## Task 3: Orchestration `assemble_artifact_deliverable`

**Files:**
- Modify: `qea/artifacts.py`
- Test: `tests/test_smoke.py::test_assemble_artifact_deliverable_*`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_smoke.py`):

```python
def _BTaskStub(tid="b1"):
    from qea.tasks import BTask
    return BTask(task_id=tid, subtype="Accountants and Auditors", prompt="produce report.xlsx", rubric="")

def test_assemble_artifact_deliverable_produces_and_persists(tmp_path):
    import pytest
    pytest.importorskip("openpyxl")
    from qea.artifacts import assemble_artifact_deliverable
    llm_text = ("Here is the workbook.\n```python\nimport openpyxl\n"
                "wb=openpyxl.Workbook(); ws=wb.active; ws.title='Summary'; ws['A1']='Total'; ws['B1']=42\n"
                "wb.save('report.xlsx')\n```")
    artifact_dir = tmp_path / "artifacts"
    out = assemble_artifact_deliverable(llm_text, _BTaskStub(), artifact_dir)
    assert "[ARTIFACT FILE: report.xlsx]" in out and "'Total'" in out
    assert "import openpyxl" not in out            # raw code stripped from the narrative
    assert (artifact_dir / "b1" / "report.xlsx").exists()   # persisted under <dir>/<task_id>/

def test_assemble_artifact_deliverable_text_and_error_paths(tmp_path):
    from qea.artifacts import assemble_artifact_deliverable
    # plain text task -> unchanged
    assert assemble_artifact_deliverable("just a memo", _BTaskStub(), tmp_path) == "just a memo"
    # erroring artifact code -> graceful: keep the narrative, no crash
    bad = "```python\nimport openpyxl\nraise RuntimeError('x')\nwb=1\n.save('y.xlsx')\n```narrative"
    out = assemble_artifact_deliverable(bad, _BTaskStub(), tmp_path)
    assert "[ARTIFACT FILE" not in out             # nothing produced
```

- [ ] **Step 2: Run, expect FAIL** — no `assemble_artifact_deliverable`.

- [ ] **Step 3: Add `assemble_artifact_deliverable` to `qea/artifacts.py`:**

```python
def assemble_artifact_deliverable(llm_text: str, task, artifact_dir) -> str:
    """If the worker emitted openpyxl code, run it in the subprocess sandbox; on
    success persist the .xlsx under <artifact_dir>/<task_id>/ and return
    narrative + rendered artifact. Otherwise (text task or failed exec) return the
    text unchanged — never raises, so a bad workbook just degrades to its narrative."""
    code = extract_openpyxl_code(llm_text)
    if code is None:
        return llm_text
    from .sandbox import exec_artifact          # local import: sandbox is stdlib-only
    res = exec_artifact(code)
    if res.status != "success" or not res.paths:
        if res.work_dir:
            shutil.rmtree(res.work_dir, ignore_errors=True)
        return llm_text
    renderings = []
    for p in res.paths:
        renderings.append(render_xlsx(p))
        if artifact_dir is not None:
            dest = Path(artifact_dir) / task.task_id
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dest / p.name)
    shutil.rmtree(res.work_dir, ignore_errors=True)
    narrative = _strip_code_blocks(llm_text)
    return (narrative + "\n\n" + "\n\n".join(renderings)).strip()
```

- [ ] **Step 4: Run, expect PASS** — `python3 -m pytest tests/test_smoke.py::test_assemble_artifact_deliverable_produces_and_persists tests/test_smoke.py::test_assemble_artifact_deliverable_text_and_error_paths -v`.

- [ ] **Step 5: Commit**

```bash
git add qea/artifacts.py tests/test_smoke.py
git commit -m "feat(artifacts): assemble_artifact_deliverable (exec->persist->render orchestration)"
```

---

## Task 4: Seed tool + worker wiring + `artifact_dir` threading

**Files:**
- Modify: `qea/harness.py` (`seed_harness`), `qea/agents.py` (`quant_agent_solve`, `_quant_solve_real`), `qea/loop.py` (`evaluate`, `_score_one`, `run_gdpval_soft`)
- Test: `tests/test_smoke.py::test_b_worker_*`, `::test_seed_has_xlsx_writer`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_smoke.py`):

```python
def test_seed_has_xlsx_writer():
    from qea.harness import seed_harness
    h = seed_harness()
    assert h.has("tool", "xlsx_writer") and h.has("tool", "code_exec")

def test_b_worker_real_produces_artifact_when_seed_has_tool(tmp_path):
    import pytest
    pytest.importorskip("openpyxl")
    from qea.agents import quant_agent_solve
    from qea.harness import seed_harness
    from qea.tasks import BTask

    class CodeLLM:
        def complete(self, prompt, *, role="quant_agent"):
            assert "openpyxl" in prompt   # the seed tool advertised the capability
            return ("Workbook attached.\n```python\nimport openpyxl\n"
                    "wb=openpyxl.Workbook(); wb.active['A1']='ok'; wb.save('out.xlsx')\n```")
    t = BTask(task_id="bx", subtype="x", prompt="make out.xlsx", rubric="")
    out = quant_agent_solve(t, seed_harness(), mock=False, llm=CodeLLM(),
                            artifact_dir=tmp_path)
    assert "[ARTIFACT FILE: out.xlsx]" in out
    assert (tmp_path / "bx" / "out.xlsx").exists()

def test_b_worker_real_text_task_unchanged():
    from qea.agents import quant_agent_solve
    from qea.harness import seed_harness
    from qea.tasks import BTask
    class TextLLM:
        def complete(self, prompt, *, role="quant_agent"):
            return "A plain advisory memo with no spreadsheet."
    t = BTask(task_id="bt", subtype="x", prompt="write a memo", rubric="")
    out = quant_agent_solve(t, seed_harness(), mock=False, llm=TextLLM(), artifact_dir=None)
    assert out == "A plain advisory memo with no spreadsheet."

def test_b_worker_mock_unaffected():
    from qea.agents import quant_agent_solve
    from qea.harness import seed_harness
    from qea.tasks import BTask
    t = BTask(task_id="bm", subtype="x", prompt="p", rubric="")
    assert quant_agent_solve(t, seed_harness(), mock=True, llm=None) == ""
```

- [ ] **Step 2: Run, expect FAIL** — no `xlsx_writer`, `quant_agent_solve` has no `artifact_dir`.

- [ ] **Step 3: Add the seed tool** in `qea/harness.py` `seed_harness()` (after the `code_exec` component, before `return h`):

```python
    h.slots["tool"]["xlsx_writer"] = Component(
        name="xlsx_writer",
        slot="tool",
        content=(
            "xlsx_writer: produce an .xlsx workbook deliverable by emitting a Python "
            "code block using openpyxl that builds and saves the file; it is run in a "
            "sandbox and the produced workbook is captured and graded."
        ),
        effect="artifact_ok",
        origin="seed",
    )
```

- [ ] **Step 4: Wire the worker** in `qea/agents.py`. Replace `quant_agent_solve` and the B branch of `_quant_solve_real`:

```python
def quant_agent_solve(task, harness, *, mock: bool, llm, artifact_dir=None):
    if mock:
        return _quant_solve_mock(task, harness)
    return _quant_solve_real(task, harness, llm, artifact_dir=artifact_dir)
```

In `_quant_solve_real`, change the signature to `def _quant_solve_real(task, harness, llm, artifact_dir=None):` and replace the B-pile tail (the two lines after the A-pile block) with:

```python
    can_xlsx = harness.has("tool", "xlsx_writer")
    extra = ""
    if can_xlsx:
        extra = (
            "\n\nIf the task requires a spreadsheet/workbook deliverable, output a "
            "single Python code block that uses `openpyxl` to build the workbook and "
            "save it (use the exact filename the task requires) in the current "
            "directory. Otherwise, write the text deliverable."
        )
    prompt = f"{sys}\n\nTASK: {task.prompt}\n\nWrite the deliverable.{extra}"
    txt = llm.complete(prompt, role="quant_agent")
    if can_xlsx:
        from .artifacts import assemble_artifact_deliverable
        return assemble_artifact_deliverable(txt, task, artifact_dir)
    return txt
```

- [ ] **Step 5: Thread `artifact_dir`** in `qea/loop.py`. Update `_score_one` and `evaluate` to carry it, and have `run_gdpval_soft` pass it.

`_score_one` (add `artifact_dir=None`; forward to both worker calls):
```python
def _score_one(task, harness, *, mock, llm, hard, soft, k, cache=None, artifact_dir=None):
    if task.pile == "B" and cache is not None and not mock:
        solution = cache.get_or_make(task.task_id, harness,
                                     lambda: quant_agent_solve(task, harness, mock=mock, llm=llm,
                                                               artifact_dir=artifact_dir))
    else:
        solution = quant_agent_solve(task, harness, mock=mock, llm=llm, artifact_dir=artifact_dir)
    if task.pile == "A":
        return task.task_id, hard.score(task, solution, harness, mock=mock, k=k), solution
    return task.task_id, soft.score(task, solution, harness, mock=mock, k=k), solution
```

`evaluate` (add `artifact_dir=None` to the signature and forward `artifact_dir=artifact_dir` to `_score_one` in BOTH the sequential and the `ex.submit(...)` branches).

`run_gdpval_soft`: define `artifact_dir = Path(cfg.results_dir) / "artifacts"` next to where `cache`/`guard` are built, and pass `artifact_dir=artifact_dir` to **every** `evaluate(...)` call inside `run_gdpval_soft` (seed, noise, resume, per-iteration cand). `run_arm` is left without it (A-pile / synthetic — defaults to None).

- [ ] **Step 6: Run, expect PASS** — `python3 -m pytest tests/test_smoke.py::test_seed_has_xlsx_writer tests/test_smoke.py::test_b_worker_real_produces_artifact_when_seed_has_tool tests/test_smoke.py::test_b_worker_real_text_task_unchanged tests/test_smoke.py::test_b_worker_mock_unaffected -v`. Then full suite `python3 -m pytest -q` → all green (incl. the synthetic-fixture signals — `seed_harness` gaining `xlsx_writer` is inert for A-pile; verify `test_signal_*`/`test_acceptance_all_signals` still pass), and `python3 run.py --mock` exits 0.

- [ ] **Step 7: Commit**

```bash
git add qea/harness.py qea/agents.py qea/loop.py tests/test_smoke.py
git commit -m "feat(worker): seed xlsx_writer tool + file-producing B worker wired through artifact_dir"
```

---

## Task 5: Acceptance — grader credits an artifact criterion

**Files:**
- Test: `tests/test_smoke.py::test_softjudge_credits_artifact_from_rendering`

- [ ] **Step 1: Write the test** (append to `tests/test_smoke.py`) — proves the *interim grader bridge* works end to end: a rendered-artifact deliverable lets the existing `SoftJudge` credit an artifact criterion.

```python
def test_softjudge_credits_artifact_from_rendering():
    from qea.tasks import BTask
    from qea.verifier import SoftJudge

    class ArtifactJudge:
        # credits each criterion iff the deliverable text shows the workbook/sheet
        def complete(self, prompt, *, role="judge"):
            d = prompt.split("DELIVERABLE:")[1]
            v = {"1": "report.xlsx" in d, "2": 'Sheet "Summary"' in d}
            import json
            return json.dumps({k: bool(x) for k, x in v.items()})

    t = BTask(task_id="b", subtype="x", prompt="produce report.xlsx", rubric="",
              rubric_items=[{"points": 1, "criterion": "submitted as an Excel workbook named report.xlsx"},
                            {"points": 1, "criterion": "has a Summary sheet"}])
    deliverable = 'Done.\n\n[ARTIFACT FILE: report.xlsx]\nSheet "Summary" (1x1):\n  A1: \'Total\''
    r = SoftJudge(ArtifactJudge()).score(t, deliverable, None, mock=False, k=1)
    assert r.score == 1.0                       # both artifact criteria credited
    assert r.criterion_verdicts == {"1": True, "2": True}
```

- [ ] **Step 2: Run, expect PASS** — `python3 -m pytest tests/test_smoke.py::test_softjudge_credits_artifact_from_rendering -v` (no implementation needed — this validates the existing `SoftJudge` against a rendered deliverable; if it fails, the bug is upstream and must be fixed before proceeding).

- [ ] **Step 3: Full suite + offline demo** — `python3 -m pytest -q` (all green) and `python3 run.py --mock` (exit 0). Confirm with openpyxl absent too if feasible: the artifact tests `importorskip`, the core stays green.

- [ ] **Step 4: Commit**

```bash
git add tests/test_smoke.py
git commit -m "test: SoftJudge credits artifact criteria from the rendered xlsx (interim bridge)"
```

---

## Task 6: Docs + v0.1 release

**Files:**
- Modify: `pyproject.toml` (version), `README.md`, `ROADMAP.md`

- [ ] **Step 1: Bump the version** in `pyproject.toml`: change `version = "0.0.1"` to `version = "0.1.0"`.

- [ ] **Step 2: Update `README.md`** — add a short subsection under the architecture/worker area: the B-pile worker can now produce a real `.xlsx` (worker writes openpyxl code → `exec_artifact` subprocess sandbox → persisted + rendered to text so the grader credits artifact criteria); note the `[artifacts]` extra (`pip install -e ".[artifacts]"`); note this is **v0.1**, the first of three sub-projects toward faithful GDPval file grading (the other two: gold-file acquisition; file-aware/multimodal grader).

- [ ] **Step 3: Update `ROADMAP.md`** — add entries: (a) **sub-project 2** gold human-deliverable file acquisition; (b) **sub-project 3** faithful file-aware/multimodal grader (xlsx → LibreOffice render → image → multimodal judge; plus formula-value computation); (c) **tool synthesis** as a future direction (evolved tool components carrying executable code + an agentic worker — AHE is the reference substrate); (d) container/cloud exec isolation (docker / nexau E2BSandbox) to harden `exec_artifact` beyond the v0.1 subprocess posture.

- [ ] **Step 4: Verify + commit**

Run `python3 -m pytest -q` (green) and `python3 -c "import qea.sandbox, qea.artifacts, qea.loop, run"`.
```bash
git add pyproject.toml README.md ROADMAP.md
git commit -m "docs: file-producing worker in README/ROADMAP; bump version to 0.1.0 (v0.1)"
```

(The `git tag v0.1` on the merge commit happens at branch-finish, not here.)

---

## Self-review checklist (run before execution)

- **Spec coverage:** exec_artifact subprocess (T1, spec §4.1); `[artifacts]` openpyxl (T1, §7); render_xlsx values+formula-strings, no compute (T2, §4.2/§6); extract code (T2, §4.3); orchestration persist+render, deliverable stays str (T3, §4.5/§3/§5); seed `xlsx_writer` (T4, §4.4); worker self-select + artifact_dir threading (T4, §4.3); A-pile/gate/firewall/mock unchanged (T4 full-suite gate, §5); grader credits artifact (T5, §11.4); subprocess error/timeout/env-scrub (T1, §11.6); v0.1 + docs + future-direction/ROADMAP (T6, §9/§10/§12).
- **Placeholder scan:** none — every step has full code/commands.
- **Type consistency:** `ArtifactResult{status,paths,stdout,stderr,work_dir}` (T1) consumed by `assemble_artifact_deliverable` (T3: `.status`,`.paths`,`.work_dir`); `extract_openpyxl_code`/`render_xlsx`/`_strip_code_blocks` (T2) consumed in T3; `assemble_artifact_deliverable(llm_text, task, artifact_dir)` (T3) called by `_quant_solve_real` (T4); `quant_agent_solve(..., artifact_dir=None)` (T4) called by `_score_one` (T4) fed by `evaluate(..., artifact_dir=None)` (T4) from `run_gdpval_soft` (T4). `seed_harness` `xlsx_writer` (T4) gates the worker branch (T4) and is asserted in T4.
