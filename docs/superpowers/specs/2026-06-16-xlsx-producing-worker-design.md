# File-producing B-pile worker (xlsx) — design

Date: 2026-06-16
Status: approved design, pre-implementation
Branch: `qea/xlsx-producing-worker`

> This is **sub-project 1 of 3** toward faithful GDPval file-level grading. The
> other two (gold-file acquisition; file-aware/multimodal grader) get their own
> spec → plan cycles. Sub-project 1 is the foundation: it is a prerequisite for
> any file-grading **and** it independently unblocks the "format basin" finding.

## 1. Motivation

The 10-iter real run (`results/loop_test_2026-06-16/`) confirmed the new pipeline
runs end-to-end (keep rate departed 0: 3 kept / 7 rolled back), but surfaced a
hard ceiling: **all 10 proposed edits were format-type** (`output_format_validator`,
`format_instructions`, `output_schema`, `output_autoformatter`, …). The proposer
is trapped in a "format basin" — and the Accountants/Auditors occupation *regressed*
(0.35 → 0.28).

Root cause: GDPval rubrics for that tail require **artifact deliverables**
("submitted as an Excel workbook named X, with sheet Y, cell Z"). The B-pile worker
is **text-only** (`_quant_solve_real`, `agents.py:53` = one `llm.complete` returning
a string), so those artifact criteria are *structurally unsatisfiable*. The
B-debugger then surfaces format failures every iteration, and the proposer's only
lever is prompt text — so it proposes format tweaks that can never turn text into an
`.xlsx`.

**Scaffold vs substrate.** Harness components are inert prompt text consumed by
`assemble_system_prompt()` (which injects only `prompt/skill/memory/validator`).
The worker's execution model (one text completion) and the tool implementations are
**framework substrate**, outside the evolvable surface — so the evolve agent
*cannot* grow an xlsx tool itself (a proposed `tool:xlsx_writer` would be an inert
string, not executable). Producing files is a **capability gap in the substrate**,
not a process gap, so per iron law 1 it is correctly fixed at the framework/seed
level; evolution then does process work (when/how to use it) on top. xlsx production
is also universal to the task family — it should not be rediscovered per run.

## 2. Scope

**In:** the real B-pile worker can produce a real `.xlsx`; the produced file is
persisted and rendered to faithful text appended to the deliverable, so the
**current** `SoftJudge` can already credit artifact criteria.

**Out (own sub-projects / deferred, §10):** `.pptx`/`.docx`; formula-value
computation; faithful multimodal/file-level grading; gold-file acquisition;
tool-synthesis (§9).

## 3. The produce → capture → render chain

```
B worker (real)
  ├─ task needs a workbook?  → emit an openpyxl Python code block
  │     ▼
  │   exec_artifact(code)   # subprocess: `python script.py` in a fresh temp work_dir
  │     ▼  produced *.xlsx captured
  │   persist to results/<run>/artifacts/<task_id>/   (for sub-proj 3 later)
  │     ▼
  │   render_xlsx(path) → faithful text
  │     ▼
  │   deliverable = narrative_text + "\n\n[ARTIFACT FILE: name.xlsx]\n<rendering>"
  └─ else (text task) → deliverable = text   (unchanged path)
```

The worker **self-selects**: it emits openpyxl code when the task asks for a
workbook, plain text otherwise — no separate classifier. Detection of "produced a
file" = "the worker output contained a runnable openpyxl code block that wrote an
`.xlsx`."

## 4. Components

### 4.1 `exec_artifact(code, timeout=10.0) -> ArtifactResult`  (new module `qea/sandbox.py`)
A **subprocess-based** file-capable executor — the pattern AHE uses (its `nexau`
`LocalSandbox` runs model code as a separate process in a `work_dir`; see the AHE
cross-reference below). It is **author-agnostic** — runs model-written code whether
authored by the worker now or a synthesized tool later (§9), so it is reusable
substrate. Isolation comes from the **OS process boundary**, not from crippling
builtins:
- Write `code` to `script.py` inside a **fresh temp work_dir**.
- `subprocess.run([sys.executable, "script.py"], cwd=work_dir, timeout=timeout,
  capture_output=True, text=True, env=<scrubbed>)`. The child is a **normal Python** —
  it `import openpyxl`, `open()`s files, writes the `.xlsx` into `work_dir`, with **no
  whitelist gymnastics**.
- `env` is **scrubbed of secrets** (drop `OPENROUTER_API_KEY` and any `*_API_KEY` /
  `*_TOKEN`) so child code cannot exfiltrate credentials; the harness grants no
  network.
- On overrun, `subprocess.run(timeout=)` raises `TimeoutExpired` and the **process
  tree is killed** — robust teardown (vs the in-process SIGALRM of `safe_exec_solve`).
- After it returns, **collect** produced files (`glob('*.xlsx')` in `work_dir`) and
  return `ArtifactResult{ paths, stdout, stderr, status }`. The worker controls the
  basename (so it can match a rubric-required name). The temp dir is removed after the
  produced file is copied to the persistence dir (§4.5).
- **Safety posture (v0.1):** process + cwd-confinement + scrubbed env + kill-on-
  timeout — **strictly better isolation than in-process**, for ~one process spawn of
  overhead. It shares QEA's Python env (so `openpyxl` lives in the `[artifacts]`
  extra, §7); it is **not** a container. Full container / cloud isolation
  (docker / NexAU `E2BSandbox`) stays a ROADMAP item.

`safe_exec_solve` (A-pile, `solve()→dict`, no files) is **unchanged** — it stays
in-process; `exec_artifact` is the separate subprocess path for B-pile file output.

> **AHE cross-reference:** AHE's tool layer (`nexau.archs.sandbox.BaseSandbox`, impls
> `LocalSandbox` / `E2BSandbox`; `run_code_tool` → `sandbox.execute_code`) is a full
> agentic substrate that QEA's port collapsed into inert-text components + the
> in-process `safe_exec_solve`. `exec_artifact` re-introduces a minimal, stdlib-only
> slice of `LocalSandbox` (subprocess + work_dir). We deliberately **do not** take a
> `nexau` dependency (QEA stays stdlib-minimal); we copy the pattern, not the package.

### 4.2 `render_xlsx(path, max_rows=100, max_cols=30) -> str`  (new)
openpyxl-only faithful text rendering (no formula engine — see §6):
- Header: `[ARTIFACT FILE: <basename>]`.
- Per sheet: sheet name + used dimensions; a bounded grid (cap `max_rows × max_cols`,
  noting truncation) of each cell's **literal value** and, when the cell holds a
  formula, the **formula string** (e.g. `D5: =SUM(D2:D4)`). Read with openpyxl twice
  (or once with both): `data_only=False` for formula strings; literal values are
  available directly.
- Returns the text block appended to the deliverable.

### 4.3 B worker prompt change  (`agents.py:_quant_solve_real`, B branch)
Gated on the seed having `tool:xlsx_writer`, the prompt gains:
> "If the task requires a spreadsheet/workbook deliverable, output a single Python
> code block that uses `openpyxl` to build the workbook and save it (choose the
> exact filename the task requires) into the current directory. Otherwise, write the
> text deliverable. You may include a short narrative plus the code block."

Flow: run the LLM; if the output contains a runnable openpyxl code block →
`exec_artifact` → persist + `render_xlsx` → deliverable = narrative (code stripped) +
rendering. Else → deliverable = text (unchanged).

### 4.4 Seed tool  (`harness.py:seed_harness`)
Add `tool:xlsx_writer` documenting the capability (real component → visible to the
proposer, attributable). It **gates** §4.3's artifact instruction. This is the
user's original "add a tool to the seed" — realized as a genuine seed capability
backed by `exec_artifact`, not an inert string. The minimal-seed principle bends
here by explicit choice (capability, not process).

### 4.5 Artifact persistence
Produced `.xlsx` files are copied to `results/<run>/artifacts/<task_id>/` so
sub-project 3's file-aware grader can consume the real binaries later. The interim
grader uses only the rendered text.

## 5. What stays unchanged
`EvalSummary.deliverables[task_id]` **remains a `str`** (= narrative + rendered
artifact) — so `SoftJudge`, the B-debugger critic, the leakage guard, and checkpoint
serialization are all untouched. A-pile, `code_exec`/`safe_exec_solve`, the
`decide_keep_soft` gate, the information firewall, and the mock/synthetic fixture
(mock B worker still returns `""`) are all unaffected.

## 6. Known tradeoff: openpyxl formulas have no computed values
An `.xlsx` written by openpyxl with formulas carries **no cached results**
(`data_only=True` → `None` for formula cells). The interim render (§4.2) therefore
shows the **formula string + any literal values**, but not formula-computed numbers.
Consequence: the judge can verify "uses formulas" and literal content and structure,
but can only check formula *correctness* by mentally evaluating simple formulas. This
is accepted for the interim — **the format-basin unblock does not depend on it.**
Formula-value computation (via a `formulas`/`pycel` pip engine or LibreOffice-headless
recalc) is deferred to **sub-project 3** (the faithful grader), where LibreOffice also
yields the images/PDF for multimodal grading.

## 7. Dependencies
Add `openpyxl` to a new `[artifacts]` optional extra in `pyproject.toml` (alongside
`real`/`gdpval`). The core stays pure-stdlib; `--mock` and the smoke test need no new
deps.

## 8. Testing (stubbed LLM, no API)
1. `exec_artifact` runs a stub openpyxl snippet in a subprocess → an `.xlsx` is
   produced and its path returned with `status="success"`; a snippet that raises
   returns `status="error"` with stderr (not a crash of the parent); an infinite-loop
   snippet hits `TimeoutExpired` → `status="timeout"` and the parent survives; the
   scrubbed `env` does not contain `OPENROUTER_API_KEY` (assert from inside the child).
2. `render_xlsx` on a known workbook (literal values + a formula cell) → text contains
   the basename, sheet name, the literal values, and the formula string.
3. B worker (stub LLM → openpyxl code) → deliverable string contains the rendering
   **and** the file is persisted under the artifacts dir.
4. B worker (stub LLM → plain text, no code block) → deliverable == the text (unchanged
   path).
5. `SoftJudge` (stub judge) credits an "Excel workbook named X" criterion from the
   rendered text.
6. mock B worker still returns `""`; the synthetic-fixture mechanism signals still pass.

## 9. Future direction: tool synthesis (recorded, not in scope)
The user's question "why doesn't the evolve agent make its own xlsx tool?" exposes a
real boundary: today evolved components are **inert prompt text** and the worker
substrate is **fixed**, so the proposer can only edit scaffold, never extend the
runtime. A more powerful (and more dangerous) paradigm — **tool synthesis** — would
let evolved `tool` components carry **executable code** that the framework safely
execs and exposes to an **agentic worker**. Notably, `exec_artifact` (§4.1) is the
substrate for this: in the seed version it already runs model-written code; synthesis
only changes the *author* (evolve agent vs worker) and *lifetime* (a reusable evolved
component vs one-shot). Because the seed version is a strict subset/prerequisite,
building it now is not throwaway. **AHE is the reference implementation of this
substrate** (real executable tools via `nexau.archs.sandbox.BaseSandbox` + an agentic
worker loop); QEA's port stripped it out, and tool synthesis is essentially
re-adopting a slice of it. Tool synthesis gets its own spec if pursued. Add a ROADMAP
entry.

## 10. Deferred / out of scope
- `.pptx` / `.docx` producing workers (same pattern; later).
- Formula-value computation (§6) → sub-project 3.
- Faithful file-aware / multimodal grader → **sub-project 3**.
- Gold human-deliverable file acquisition (from `deliverable_file_urls`) →
  **sub-project 2**.
- Tool synthesis (§9) — separate future direction.
- Container / cloud exec isolation (docker / NexAU `E2BSandbox`) — ROADMAP (the
  subprocess sandbox is the v0.1 posture).

## 11. Acceptance criteria
1. Given a stub worker that emits openpyxl code, the run produces a real `.xlsx`,
   persists it under `results/<run>/artifacts/<task_id>/`, and the deliverable string
   contains a faithful rendering (basename + sheet + cells + formula strings).
2. The strict A-pile path (`safe_exec_solve`, `code_exec`) and the synthetic-fixture
   mechanism signals are unchanged (full smoke suite green).
3. `EvalSummary.deliverables` remains `str`-typed; no downstream signature changes.
4. A rubric "is an Excel workbook named X / has sheet Y" criterion is creditable by
   the existing `SoftJudge` from the rendered text (stub-judge test).
5. A text-only B task is unaffected (no code block → plain text deliverable).
6. `exec_artifact` runs in a subprocess: a raising snippet → `status="error"` (parent
   survives), an infinite loop → `status="timeout"` (process killed), and the child's
   `env` has no `OPENROUTER_API_KEY`.

## 12. Release
Ships as **QEA v0.1** — bump `pyproject.toml` `version` `0.0.1 → 0.1.0`, note it in
the README, and tag `v0.1` on the merge commit. This is the release name for the
file-producing-worker milestone.
