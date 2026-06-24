# Phase 4 — Level-B Evolve Loop (NexAU substrate unification) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a deterministic Level-B evolution loop that runs the *real* NexAU GDPval worker, grades it with the *same* multimodal judge used in the base test, feeds an answer-free (verdicts + worker-trace) diagnosis to a *file-editing NexAU evolve agent* that edits a snapshot of the worker directory, and keeps/rolls back the snapshot on an aggregate-score gate.

**Architecture:** A plain-code loop (`qea/loop_levelb.py`) orchestrates two sibling NexAU agents — a deliberately weakened worker (`qea/worker_gdpval_weak/`) and a file-editing evolve agent (`qea/evolve_agent/`). The worker call is unified into a reusable `run_worker()` (`qea/worker_runtime.py`) lifted from `scripts/nexau_gdpval_run.py`. Grading reuses `qea/grading/render.py` + `qea/grading/multimodal_judge.py`. The firewalled debugger (`qea/debugger.py`) is extended to also consume the worker trace. keep/rollback, the noise-floor gate (`decide_keep_soft`), the leakage guard, and the rejected-edit buffer all stay in code; the evolve agent decides nothing.

**Tech Stack:** Python 3.14 (`.venv-nexau`), NexAU (`AgentConfig.from_yaml` / `Agent` / `agent.full_trace`), OpenRouter via `api_type: openai_chat_completion`, pytest.

**Branch:** Create `qea/phase4-levelb` off `main` before Task 1. Do NOT implement on `main`.

**Environment:** All commands run from repo root `/Users/kevinwu/Coding/evolving-quant-agent` with `.venv-nexau/bin/python` and `.env` providing `OPENROUTER_API_KEY` + proxy vars (`http_proxy`/`https_proxy=http://127.0.0.1:7897`, `all_proxy=socks5://127.0.0.1:7897`). NexAU-real steps are gated behind `QEA_LEVELB_SMOKE=1` so the default test suite stays offline and fast.

---

## File Structure

| File | Responsibility |
|---|---|
| `qea/worker_runtime.py` (Create) | Reusable NexAU worker invocation: `run_worker(task, worker_dir, run_dir)` → `WorkerRun(deliverable_text, produced_files, trace)`; `summarize_trace(agent)` (lifted from the script). |
| `qea/worker_gdpval_weak/` (Create dir) | The deliberately weakened seed worker (minimal prompt; bare shell tool; finish-guidance + extension hints removed) to create headroom. |
| `qea/debugger.py` (Modify) | Add `process_note(trace)` (answer-free) and thread an optional `traces` map through `diagnose_b_pile` so the diagnosis covers the process side. |
| `qea/evolve_agent/` (Create dir) | File-editing NexAU agent (agent.yaml + systemprompt.md + shell tool) that edits a worker-dir snapshot from the sanitized diagnosis only. |
| `qea/evolve_runtime.py` (Create) | `snapshot_dir`, `dir_unified_diff`, `diff_signature`, `DirEdit` (Edit-like shim for the buffer/leakage-guard), `run_evolve_agent(snapshot_dir, sanitized_diagnosis, run_dir)`. |
| `qea/loop_levelb.py` (Create) | The deterministic Level-B loop: `LevelBConfig`, `evaluate_dir`, `run_gdpval_levelb` → `LevelBResult`. Reuses grader/firewall/gate/buffer. |
| `run.py` (Modify) | Add `--levelb` mode wiring to `run_gdpval_levelb` + a `_print_levelb` summary. |
| `tests/test_levelb.py` (Create) | Unit tests for all pure logic (trace summary, process note, snapshot/diff/signature, firewall, gate reuse) + a gated NexAU smoke test. |
| `docs/RESULTS_levelb_gdpval.md` (Create at Task 6) | Weak-seed vs full-worker headroom measurement + loop behavior. |

---

### Task 1: Reusable `run_worker()` runtime

**Files:**
- Create: `qea/worker_runtime.py`
- Create: `tests/test_levelb.py`

- [ ] **Step 1: Create the branch**

Run:
```bash
cd /Users/kevinwu/Coding/evolving-quant-agent
git checkout -b qea/phase4-levelb
```
Expected: `Switched to a new branch 'qea/phase4-levelb'`

- [ ] **Step 2: Write the failing test for `summarize_trace`**

Create `tests/test_levelb.py`:
```python
"""Phase-4 Level-B loop: unit tests for the pure logic + a gated NexAU smoke test.

The NexAU-real pieces (run_worker / run_evolve_agent / the full loop) require an
API key + proxy and are gated behind QEA_LEVELB_SMOKE=1; everything else is
offline and deterministic.
"""
import os
from pathlib import Path

import pytest


class _FakeMsg:
    def __init__(self, role, text):
        self.role = role
        self._text = text
    def get_text_content(self):
        return self._text


class _FakeAgent:
    def __init__(self, msgs):
        self.full_trace = msgs


def test_summarize_trace_counts_roles_and_errors():
    from qea.worker_runtime import summarize_trace
    agent = _FakeAgent([
        _FakeMsg("assistant", "let me build it"),
        _FakeMsg("tool", "ok, file written"),
        _FakeMsg("assistant", "now verify"),
        _FakeMsg("tool", "Traceback (most recent call last): Error: boom"),
        _FakeMsg("user", "the task prompt"),
    ])
    mon = summarize_trace(agent)
    assert mon["turns"] == 2          # two assistant messages
    assert mon["tool_calls"] == 2     # two non-user tool/result messages
    assert mon["tool_errors"] == 1    # one carried an error marker
```

- [ ] **Step 3: Run it to verify it fails**

Run: `.venv-nexau/bin/python -m pytest tests/test_levelb.py::test_summarize_trace_counts_roles_and_errors -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'qea.worker_runtime'`

- [ ] **Step 4: Create `qea/worker_runtime.py`**

```python
"""Reusable NexAU worker invocation for both the base test and the Level-B loop.

Lifted from scripts/nexau_gdpval_run.py (run_task / _trace_summary) so the loop
runs the SAME real worker we base-tested at mean multimodal 0.797 — not a legacy
single-completion. Returns the deliverable text, the produced deliverable files,
and an answer-free trace summary (tool_calls / tool_errors / turns / secs).
"""
from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

SUPPORTED = {".xlsx", ".pptx", ".docx", ".pdf"}


@dataclass
class WorkerRun:
    deliverable_text: str
    produced_files: list = field(default_factory=list)
    trace: dict = field(default_factory=dict)


def summarize_trace(agent) -> dict:
    """Answer-free monitoring from the NexAU trace. A message has no tool_calls
    field (tool activity is in content/role), so count by role: assistant turns +
    tool-result messages (proxy for tool calls) + error markers in tool results."""
    turns = tool_results = tool_errors = 0
    try:
        for m in (agent.full_trace or []):
            role = getattr(m, "role", "")
            try:
                text = m.get_text_content()
            except Exception:  # noqa: BLE001
                text = str(getattr(m, "content", "") or "")
            if role == "assistant":
                turns += 1
            elif role in ("tool", "tool_result", "function", "user") and text:
                if role != "user":
                    tool_results += 1
                if any(k in text for k in ("Error", "❌", "failed", "Traceback", "Invalid parameters")):
                    tool_errors += 1
    except Exception:  # noqa: BLE001
        pass
    return {"tool_calls": tool_results, "tool_errors": tool_errors, "turns": turns}


def run_worker(task, worker_dir: Path, run_dir: Path) -> WorkerRun:
    """Run the NexAU worker (the agent dir at worker_dir) on one task in an isolated
    per-task workdir under run_dir. Copies the task reference files in, pins the
    sandbox cwd, captures produced deliverable files (before/after diff) + trace."""
    from nexau import Agent, AgentConfig
    t0 = time.time()
    worker_dir, run_dir = Path(worker_dir), Path(run_dir)
    workdir = run_dir / str(task.task_id) / "work"
    workdir.mkdir(parents=True, exist_ok=True)
    ref_names = set()
    for rf in (getattr(task, "reference_files", None) or []):
        rf = Path(rf)
        if rf.exists():
            shutil.copy(rf, workdir / rf.name)
            ref_names.add(rf.name)
    pre = {p for p in workdir.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED}

    cfg = AgentConfig.from_yaml(config_path=worker_dir / "agent.yaml")
    agent = Agent(config=cfg)
    try:
        agent.sandbox_manager.instance.work_dir = workdir
    except Exception:  # noqa: BLE001
        pass
    note = (f"\n\nIMPORTANT: Your working directory is {workdir}\n"
            f"The reference input files {sorted(ref_names)} are in that directory. "
            f"Read inputs from there, and SAVE your deliverable file(s) into that directory.")
    ctx = {"date": "2026-06-25", "username": os.environ.get("USER", "kevin"),
           "working_directory": str(workdir)}
    ctx["env_content"] = dict(ctx)
    resp = agent.run(message=task.prompt + note, context=ctx)
    final_text = resp if isinstance(resp, str) else resp[0]

    produced = [p for p in workdir.rglob("*")
                if p.is_file() and p.suffix.lower() in SUPPORTED
                and p not in pre and p.name not in ref_names]
    produced = sorted(produced, key=lambda p: p.stat().st_mtime, reverse=True)[:12]
    trace = summarize_trace(agent)
    trace["secs"] = round(time.time() - t0, 1)
    trace["files"] = len(produced)
    return WorkerRun(final_text, produced, trace)
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `.venv-nexau/bin/python -m pytest tests/test_levelb.py::test_summarize_trace_counts_roles_and_errors -v`
Expected: PASS

- [ ] **Step 6: Refactor the base-test script to reuse the shared runtime (DRY)**

In `scripts/nexau_gdpval_run.py`, replace the local `_trace_summary` and the body of `run_task` so they delegate to the shared runtime (keep the script's public behavior identical). Modify `run_task` (lines 61-102) to:
```python
def run_task(task):
    """Returns (final_text, [produced deliverable file paths], monitor dict).
    Delegates to qea.worker_runtime.run_worker so the base test and the Level-B
    loop run the IDENTICAL worker invocation."""
    from qea.worker_runtime import run_worker
    run = run_worker(task, WORKER, REPO / "output" / "nexau_gdpval" / str(task.task_id))
    return run.deliverable_text, run.produced_files, run.trace
```
And delete the now-unused `_trace_summary` function (lines 36-58) plus the now-unused `import shutil` / `SUPPORTED` if no longer referenced (verify with grep before deleting).

Run: `cd /Users/kevinwu/Coding/evolving-quant-agent && grep -n "_trace_summary\|SUPPORTED\|shutil" scripts/nexau_gdpval_run.py`
Expected: no remaining references to `_trace_summary`; remove `SUPPORTED`/`shutil` lines only if grep shows zero other uses.

- [ ] **Step 7: Verify the script still imports cleanly**

Run: `.venv-nexau/bin/python -c "import ast; ast.parse(open('scripts/nexau_gdpval_run.py').read()); print('parse ok')"`
Expected: `parse ok`

- [ ] **Step 8: Commit**

```bash
git add qea/worker_runtime.py tests/test_levelb.py scripts/nexau_gdpval_run.py
git commit -m "feat(levelb): reusable run_worker() runtime; base script delegates to it"
```

---

### Task 2: Deliberately weakened seed worker

**Files:**
- Create: `qea/worker_gdpval_weak/agent.yaml`
- Create: `qea/worker_gdpval_weak/systemprompt.md`
- Create: `qea/worker_gdpval_weak/tool_descriptions/run_shell_command.tool.yaml`
- Test: `tests/test_levelb.py`

- [ ] **Step 1: Write the failing test for the weak seed config**

Add to `tests/test_levelb.py`:
```python
WEAK_DIR = Path(__file__).resolve().parent.parent / "qea" / "worker_gdpval_weak"
FULL_PROMPT = (Path(__file__).resolve().parent.parent
               / "qea" / "worker_gdpval" / "systemprompt.md").read_text()


def test_weak_seed_is_process_limited_not_capability_walled():
    # The weak seed must still load as a NexAU config and keep the shell tool
    # (so evolution CAN recover capability), but its prompt must be stripped of the
    # high-level finish-guidance / per-extension hints the full worker ships.
    from nexau import AgentConfig
    cfg = AgentConfig.from_yaml(config_path=WEAK_DIR / "agent.yaml")
    assert cfg is not None
    weak_prompt = (WEAK_DIR / "systemprompt.md").read_text()
    # headroom markers present in the FULL worker prompt, removed from the weak seed:
    assert "ls -la" not in weak_prompt              # finish/verify guidance removed
    assert "openpyxl" not in weak_prompt            # per-extension tool hints removed
    assert "Verify the file was written" not in weak_prompt
    assert len(weak_prompt) < len(FULL_PROMPT)      # strictly leaner
    # but the shell tool is still available (capability is recoverable by editing)
    tool_yaml = (WEAK_DIR / "tool_descriptions" / "run_shell_command.tool.yaml").read_text()
    assert "run_shell_command" in tool_yaml
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv-nexau/bin/python -m pytest tests/test_levelb.py::test_weak_seed_is_process_limited_not_capability_walled -v`
Expected: FAIL (config path does not exist)

- [ ] **Step 3: Create the weak worker directory and tool description**

```bash
mkdir -p qea/worker_gdpval_weak/tool_descriptions
```
Create `qea/worker_gdpval_weak/tool_descriptions/run_shell_command.tool.yaml` (identical primitive shell tool — the primitive is kept; the *guidance* is what we strip):
```yaml
type: tool
name: run_shell_command
description: >-
  Execute a shell command as `bash -c <command>` in the working directory.
  Returns combined stdout/stderr.
input_schema:
  type: object
  properties:
    command: {type: string, description: "Exact bash command to execute."}
    description: {type: string, description: "Brief description of the command."}
    is_background: {type: boolean, description: "(optional) run in background; default false."}
    dir_path: {type: string, description: "(optional) directory to run in; default the working directory."}
  required: [command]
  additionalProperties: false
```

- [ ] **Step 4: Create the weak system prompt (stripped of high-level guidance)**

Create `qea/worker_gdpval_weak/systemprompt.md`:
```markdown
You are completing a finance/accounting task. You have a shell tool (`run_shell_command`). Produce whatever the task asks for.
```

- [ ] **Step 5: Create the weak agent.yaml (same model/budget knobs, weak prompt)**

Create `qea/worker_gdpval_weak/agent.yaml` (mirror `qea/worker_gdpval/agent.yaml` exactly, including the `timeout: 180` connect-timeout fix, but point `system_prompt` at the weak prompt and rename the agent):
```yaml
type: agent
name: qea_gdpval_worker_weak
max_context_tokens: 200000
system_prompt: ./systemprompt.md
system_prompt_type: jinja
tool_call_mode: openai
max_iterations: 60

llm_config:
  model: ${env.LLM_MODEL}
  base_url: ${env.LLM_BASE_URL}
  api_key: ${env.LLM_API_KEY}
  max_tokens: 32000
  temperature: 0.2
  stream: true
  api_type: openai_chat_completion
  # connect-timeout fix (see qea/worker_gdpval/agent.yaml): single float ->
  # httpx connect=read=write=pool; SDK default connect=5s times out under the
  # concurrent-startup TLS-handshake burst through the local SOCKS proxy.
  timeout: 180

tools:
  - name: run_shell_command
    yaml_path: ./tool_descriptions/run_shell_command.tool.yaml
    binding: nexau.archs.tool.builtin.shell_tools.run_shell_command:run_shell_command

tracers:
  - import: nexau.archs.tracer.adapters.in_memory:InMemoryTracer
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `.venv-nexau/bin/python -m pytest tests/test_levelb.py::test_weak_seed_is_process_limited_not_capability_walled -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add qea/worker_gdpval_weak/ tests/test_levelb.py
git commit -m "feat(levelb): deliberately weakened seed worker (process-limited, shell-only)"
```

---

### Task 3: Trace-aware firewalled debugger

**Files:**
- Modify: `qea/debugger.py`
- Test: `tests/test_levelb.py`

- [ ] **Step 1: Write the failing test for `process_note` (answer-free)**

Add to `tests/test_levelb.py`:
```python
def test_process_note_is_answer_free_and_flags_no_deliverable():
    from qea.debugger import process_note
    # produced no file, burned few turns -> the headroom signal
    n = process_note({"files": 0, "turns": 4, "tool_calls": 2, "tool_errors": 1, "secs": 30.0})
    assert "no deliverable file" in n.lower()
    assert "4 turn" in n
    assert "1 tool error" in n
    # a healthy run produces a benign note
    ok = process_note({"files": 1, "turns": 11, "tool_calls": 6, "tool_errors": 0, "secs": 200.0})
    assert "produced" in ok.lower() and "no deliverable file" not in ok.lower()
    # process notes carry only counts — never any answer/number-from-the-task content
    assert "$" not in n and "going-concern" not in n
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv-nexau/bin/python -m pytest tests/test_levelb.py::test_process_note_is_answer_free_and_flags_no_deliverable -v`
Expected: FAIL with `ImportError: cannot import name 'process_note'`

- [ ] **Step 3: Add `process_note` + thread `traces` through `diagnose_b_pile`**

In `qea/debugger.py`, add the pure function near the top (after `B_TAG_SLOT`):
```python
def process_note(trace: dict) -> str:
    """Turn a worker trace summary into an ANSWER-FREE process observation. The
    trace carries only counts (files/turns/tool_calls/tool_errors/secs), never any
    task answer, so it is inherently firewall-safe — this function only formats it."""
    if not trace:
        return "no trace captured"
    files = int(trace.get("files", 0) or 0)
    turns = int(trace.get("turns", 0) or 0)
    errs = int(trace.get("tool_errors", 0) or 0)
    parts = []
    if files == 0:
        parts.append(f"produced no deliverable file after {turns} turn(s)")
    else:
        parts.append(f"produced {files} file(s) in {turns} turn(s)")
    if errs:
        parts.append(f"{errs} tool error(s)")
    return "; ".join(parts)
```

Then modify `diagnose_b_pile` (line 70) to accept an optional `traces` map and fold the process notes into the per-task notes. Change the signature and the note-building loop:
```python
def diagnose_b_pile(eval_summary, tasks, *, llm, mode: str = "hybrid", traces: dict | None = None) -> SanitizedDiagnosis:
    # COST: one Critic judge-call per FAILING B task + one classify call, per
    # iteration. The worker trace (process side) is folded in answer-free.
    by_id = {t.task_id: t for t in tasks}
    critic = Critic(llm)
    notes, failing_ids, occ_counts = [], [], {}
    for tid, r in eval_summary.results.items():
        if r.pile != "B" or r.oos_pass:
            continue
        task = by_id.get(tid)
        if task is None:
            continue
        failed = _failed_criteria_texts(task, r.criterion_verdicts or {})
        try:
            note = critic.note(task, eval_summary.deliverables.get(tid, ""), failed)
        except Exception:  # noqa: BLE001 - a critic outage must not kill the run (mirror evaluate())
            note = f"deliverable left {len(failed)} rubric criterion(s) unmet (critic unavailable)"
        if traces and tid in traces:
            note = f"{note} [process: {process_note(traces[tid])}]"
        notes.append(note)
        failing_ids.append(tid)
        occ_counts[r.subtype] = occ_counts.get(r.subtype, 0) + 1
```
Leave the rest of `diagnose_b_pile` (the `if not notes` early return, the classify call, the `SanitizedDiagnosis` construction) unchanged.

- [ ] **Step 4: Run the new test to verify it passes**

Run: `.venv-nexau/bin/python -m pytest tests/test_levelb.py::test_process_note_is_answer_free_and_flags_no_deliverable -v`
Expected: PASS

- [ ] **Step 5: Verify the existing firewall + outage regression tests still pass**

Run: `.venv-nexau/bin/python -m pytest tests/test_smoke.py::test_b_debugger_attributes_and_firewalls tests/test_smoke.py::test_b_debugger_survives_llm_outage -v`
Expected: 2 passed (the new `traces` param defaults to `None`, so the old call sites are unaffected and the firewall still holds).

- [ ] **Step 6: Add a firewall test proving traces do not break the firewall**

Add to `tests/test_levelb.py`:
```python
def test_trace_fold_preserves_firewall():
    from qea.tasks import BTask
    from qea.verifier import TaskResult
    from qea.falsify import EvalSummary
    from qea.debugger import diagnose_b_pile

    class CriticLLM:
        def complete(self, prompt, *, role="judge"):
            if "Classify" in prompt:
                return '{"root_cause_tag": "WrongStructure", "target_slot": "prompt"}'
            return "The deliverable omits the required reconciliation section."

    res = {"t1": TaskResult("t1", "Accountants and Auditors", "B", False, False, False, 0.3, 0.0,
                            None, criterion_verdicts={"1": False})}
    tasks = [BTask(task_id="t1", subtype="Accountants and Auditors", prompt="reconcile the ledger",
                   rubric="", rubric_items=[{"points": 1, "criterion": "reconciles to control total"}],
                   gold="SECRET-CONTROL-TOTAL-98765")]
    diag = diagnose_b_pile(EvalSummary(res, {"t1": "weak memo"}), tasks, llm=CriticLLM(),
                           traces={"t1": {"files": 0, "turns": 3, "tool_errors": 1}})
    payload = repr(diag.proposer_payload())
    assert "SECRET-CONTROL-TOTAL-98765" not in payload   # firewall holds with traces folded in
    assert "t1" in diag.predicted_fix_task_ids
```

Run: `.venv-nexau/bin/python -m pytest tests/test_levelb.py::test_trace_fold_preserves_firewall -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add qea/debugger.py tests/test_levelb.py
git commit -m "feat(levelb): trace-aware firewalled debugger (process_note + traces fold-in)"
```

---

### Task 4: File-editing evolve agent + evolve runtime

**Files:**
- Create: `qea/evolve_agent/agent.yaml`
- Create: `qea/evolve_agent/systemprompt.md`
- Create: `qea/evolve_agent/tool_descriptions/run_shell_command.tool.yaml`
- Create: `qea/evolve_runtime.py`
- Test: `tests/test_levelb.py`

- [ ] **Step 1: Write the failing test for `snapshot_dir`, `dir_unified_diff`, `diff_signature`, `DirEdit`**

Add to `tests/test_levelb.py`:
```python
def test_snapshot_and_diff_and_signature(tmp_path):
    from qea.evolve_runtime import snapshot_dir, dir_unified_diff, diff_signature, DirEdit
    src = tmp_path / "incumbent"
    (src / "tool_descriptions").mkdir(parents=True)
    (src / "systemprompt.md").write_text("original line\n")
    (src / "agent.yaml").write_text("name: w\n")

    snap = tmp_path / "snap"
    snapshot_dir(src, snap)
    assert (snap / "systemprompt.md").read_text() == "original line\n"

    # no edit yet -> empty diff, and a DirEdit over an empty diff has empty content
    assert dir_unified_diff(src, snap) == ""
    # edit the snapshot
    (snap / "systemprompt.md").write_text("original line\nADDED guidance\n")
    diff = dir_unified_diff(src, snap)
    assert "ADDED guidance" in diff and "systemprompt.md" in diff

    sig = diff_signature(diff)
    assert isinstance(sig, str) and len(sig) == 64           # sha256 hex
    # identical diff -> identical signature; different diff -> different
    assert diff_signature(diff) == sig
    assert diff_signature(diff + "x") != sig

    # DirEdit is the Edit-like shim the buffer + leakage guard consume
    de = DirEdit(diff)
    assert de.signature() == sig
    assert "ADDED guidance" in de.content            # leakage guard inspects .content
    assert de.summary                                 # non-empty human summary
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv-nexau/bin/python -m pytest tests/test_levelb.py::test_snapshot_and_diff_and_signature -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'qea.evolve_runtime'`

- [ ] **Step 3: Create `qea/evolve_runtime.py`**

```python
"""Level-B evolve agent runtime: snapshot a worker dir, run the file-editing NexAU
evolve agent against it from a sanitized (answer-free) diagnosis, and produce the
diff artifacts the loop's buffer + leakage guard consume.

The evolve agent edits a SNAPSHOT (per-iteration copy), never the live incumbent;
the loop promotes the snapshot only on a kept edit. The agent's writes are confined
to the snapshot dir via the pinned sandbox work_dir + an explicit prompt constraint.
"""
from __future__ import annotations

import difflib
import hashlib
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

EVOLVE_DIR = Path(__file__).resolve().parent / "evolve_agent"
# Files in the worker dir the evolve agent is allowed to read/diff (text only).
_TEXT_SUFFIXES = {".yaml", ".yml", ".md", ".py", ".txt", ".json"}


def snapshot_dir(src: Path, dst: Path) -> None:
    """Full per-iteration copy (AHE-style). Overwrites dst if present."""
    src, dst = Path(src), Path(dst)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def _text_files(d: Path) -> dict:
    d = Path(d)
    out = {}
    for p in sorted(d.rglob("*")):
        if p.is_file() and p.suffix.lower() in _TEXT_SUFFIXES:
            try:
                out[str(p.relative_to(d))] = p.read_text().splitlines(keepends=True)
            except Exception:  # noqa: BLE001 - skip unreadable/binary
                pass
    return out


def dir_unified_diff(before: Path, after: Path) -> str:
    """Unified diff of the TEXT files between two worker dirs (relative paths)."""
    a, b = _text_files(before), _text_files(after)
    chunks = []
    for rel in sorted(set(a) | set(b)):
        d = difflib.unified_diff(a.get(rel, []), b.get(rel, []),
                                 fromfile=f"a/{rel}", tofile=f"b/{rel}")
        chunks.append("".join(d))
    return "".join(c for c in chunks if c)


def diff_signature(diff: str) -> str:
    """Stable signature of an edit = sha256 of its unified diff (buffer key)."""
    return hashlib.sha256(diff.encode("utf-8")).hexdigest()


@dataclass
class DirEdit:
    """Edit-like shim so the existing RejectedEditBuffer + LeakageGuard work on a
    directory diff unchanged (they only call .signature() / read .content / .summary)."""
    diff: str

    def signature(self) -> str:
        return diff_signature(self.diff)

    @property
    def content(self) -> str:
        # only the ADDED lines feed the leakage guard (mirrors edit.content semantics)
        return "\n".join(l[1:] for l in self.diff.splitlines()
                         if l.startswith("+") and not l.startswith("+++"))

    @property
    def summary(self) -> str:
        files = sorted({l[4:] for l in self.diff.splitlines() if l.startswith("+++ b/")})
        adds = sum(1 for l in self.diff.splitlines() if l.startswith("+") and not l.startswith("+++"))
        dels = sum(1 for l in self.diff.splitlines() if l.startswith("-") and not l.startswith("---"))
        return f"edit {', '.join(files) or '(none)'} (+{adds}/-{dels})" if self.diff else "(no change)"


def run_evolve_agent(snapshot_dir_path: Path, sanitized_diagnosis: dict, run_dir: Path) -> dict:
    """Invoke the file-editing NexAU evolve agent against the snapshot. Reads ONLY the
    sanitized diagnosis (answer-free) — never the grader gold / rubric text. Returns
    a small summary dict (final text + trace)."""
    from nexau import Agent, AgentConfig
    from .worker_runtime import summarize_trace
    snap = Path(snapshot_dir_path)
    cfg = AgentConfig.from_yaml(config_path=EVOLVE_DIR / "agent.yaml")
    agent = Agent(config=cfg)
    try:
        agent.sandbox_manager.instance.work_dir = snap
    except Exception:  # noqa: BLE001
        pass
    msg = (
        "You may improve the worker agent in your working directory. You may edit ONLY "
        "files inside the working directory (its agent.yaml, systemprompt.md, and "
        "tool_descriptions/). Make ONE focused improvement that addresses the diagnosis "
        "below, then stop. Do NOT invent task answers or domain facts — improve the "
        "agent's PROCESS (prompt guidance, tool descriptions).\n\n"
        f"SANITIZED DIAGNOSIS (answer-free):\n"
        f"- root cause: {sanitized_diagnosis.get('root_cause_tag')}\n"
        f"- category: {sanitized_diagnosis.get('deficiency_category')}\n"
        f"- suggested focus: {sanitized_diagnosis.get('suggested_target_slot')}\n"
        f"- overview: {sanitized_diagnosis.get('overview')}\n"
    )
    ctx = {"working_directory": str(snap), "username": os.environ.get("USER", "kevin")}
    ctx["env_content"] = dict(ctx)
    resp = agent.run(message=msg, context=ctx)
    final_text = resp if isinstance(resp, str) else (resp[0] if resp else "")
    return {"final_text": final_text, "trace": summarize_trace(agent)}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv-nexau/bin/python -m pytest tests/test_levelb.py::test_snapshot_and_diff_and_signature -v`
Expected: PASS

- [ ] **Step 5: Add the leakage-guard-over-DirEdit test**

Add to `tests/test_levelb.py`:
```python
def test_leakage_guard_blocks_dir_edit_that_pastes_answer():
    from qea.verifier import LeakageGuard
    from qea.evolve_runtime import DirEdit
    corpus = ["flags any going-concern triggers in the liquidity position"]
    guard = LeakageGuard(corpus, threshold=0.6)
    leaked_diff = ("--- a/systemprompt.md\n+++ b/systemprompt.md\n"
                   "+Always flags any going-concern triggers in the liquidity position.\n")
    assert guard.is_leak(DirEdit(leaked_diff)) is True
    ok_diff = ("--- a/systemprompt.md\n+++ b/systemprompt.md\n"
               "+After producing the file, list the directory to verify it was written.\n")
    assert guard.is_leak(DirEdit(ok_diff)) is False
```

Run: `.venv-nexau/bin/python -m pytest tests/test_levelb.py::test_leakage_guard_blocks_dir_edit_that_pastes_answer -v`
Expected: PASS

- [ ] **Step 6: Create the evolve agent NexAU directory**

```bash
mkdir -p qea/evolve_agent/tool_descriptions
```
Create `qea/evolve_agent/tool_descriptions/run_shell_command.tool.yaml`:
```yaml
type: tool
name: run_shell_command
description: >-
  Execute a shell command as `bash -c <command>` in the working directory. Use it
  to read the worker agent's files (cat / ls) and to edit them (e.g. rewrite
  systemprompt.md, or edit tool_descriptions/*.yaml). Returns combined stdout/stderr.
input_schema:
  type: object
  properties:
    command: {type: string, description: "Exact bash command to execute."}
    description: {type: string, description: "Brief description of the command."}
    is_background: {type: boolean, description: "(optional) run in background; default false."}
    dir_path: {type: string, description: "(optional) directory to run in; default the working directory."}
  required: [command]
  additionalProperties: false
```

Create `qea/evolve_agent/systemprompt.md`:
```markdown
You are an agent-harness engineer. Your working directory contains a *worker agent* defined as files: `agent.yaml`, `systemprompt.md`, and `tool_descriptions/`.

Your job: make ONE focused improvement to the worker agent that addresses the diagnosis you are given, then stop.

Rules:
- Edit ONLY files inside your working directory. Never read or write anything outside it.
- Improve the worker's PROCESS — its prompt guidance and tool descriptions. For example: tell it to inspect input files first, to save the deliverable as a real file with the requested name, or to verify the file was written before finishing.
- Do NOT add task-specific answers, numbers, or domain facts. You are improving how the worker works, not solving the tasks for it.
- Inspect the current files first (`cat systemprompt.md`, `ls tool_descriptions/`), then make a minimal, targeted edit (e.g. rewrite `systemprompt.md`).
- End with a one-line summary of what you changed and why.
```

Create `qea/evolve_agent/agent.yaml` (same model/timeout knobs as the worker):
```yaml
type: agent
name: qea_evolve_agent
max_context_tokens: 200000
system_prompt: ./systemprompt.md
system_prompt_type: jinja
tool_call_mode: openai
max_iterations: 30

llm_config:
  model: ${env.LLM_MODEL}
  base_url: ${env.LLM_BASE_URL}
  api_key: ${env.LLM_API_KEY}
  max_tokens: 32000
  temperature: 0.3
  stream: true
  api_type: openai_chat_completion
  timeout: 180

tools:
  - name: run_shell_command
    yaml_path: ./tool_descriptions/run_shell_command.tool.yaml
    binding: nexau.archs.tool.builtin.shell_tools.run_shell_command:run_shell_command

tracers:
  - import: nexau.archs.tracer.adapters.in_memory:InMemoryTracer
```

- [ ] **Step 7: Verify the evolve agent config loads**

Add to `tests/test_levelb.py`:
```python
def test_evolve_agent_config_loads():
    from nexau import AgentConfig
    from qea.evolve_runtime import EVOLVE_DIR
    cfg = AgentConfig.from_yaml(config_path=EVOLVE_DIR / "agent.yaml")
    assert cfg is not None
```

Run: `.venv-nexau/bin/python -m pytest tests/test_levelb.py::test_evolve_agent_config_loads -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add qea/evolve_agent/ qea/evolve_runtime.py tests/test_levelb.py
git commit -m "feat(levelb): file-editing NexAU evolve agent + snapshot/diff/buffer runtime"
```

---

### Task 5: The deterministic Level-B loop

**Files:**
- Create: `qea/loop_levelb.py`
- Test: `tests/test_levelb.py`

- [ ] **Step 1: Write the failing test for the loop skeleton (offline, monkeypatched)**

Add to `tests/test_levelb.py`. This test stubs the three NexAU-real seams (`run_worker`, `run_evolve_agent`) and the judge so the loop's *control flow* (snapshot → grade → diagnose → evolve → diff/guard/buffer → keep/rollback) is exercised with no API:
```python
def test_levelb_loop_keeps_improving_edit_offline(tmp_path, monkeypatch):
    import qea.loop_levelb as L
    from qea.worker_runtime import WorkerRun
    from qea.grading.multimodal_judge import GradeResult
    from qea.tasks import BTask

    tasks = [BTask(task_id="t1", subtype="Accountants and Auditors", prompt="p", rubric="",
                   rubric_items=[{"points": 1, "criterion": "c"}], gold="g")]

    # worker: returns a fixed deliverable + trace; score depends on whether the
    # incumbent worker prompt has been improved (the evolve agent appends a marker).
    def fake_run_worker(task, worker_dir, run_dir):
        improved = "IMPROVED" in (worker_dir / "systemprompt.md").read_text()
        return WorkerRun(f"deliverable improved={improved}", [], {"files": 1, "turns": 5, "tool_errors": 0})
    monkeypatch.setattr(L, "run_worker", fake_run_worker)

    # judge: 0.50 for the seed, 0.90 once the worker prompt is improved
    class FakeJudge:
        def __init__(self, *a, **k): pass
        def grade(self, task, rendered):
            score = 0.90 if "improved=True" in rendered.text else 0.50
            return GradeResult(task.task_id, score, score, {"1": score > 0.6}, 0.0, False)
    monkeypatch.setattr(L, "MultimodalJudge", FakeJudge)

    # render: trivial passthrough exposing .text / .extracted_text / .images / .degraded
    def fake_render(text, produced, out_dir):
        from types import SimpleNamespace
        return SimpleNamespace(text=text, extracted_text=text, images=[], degraded=False)
    monkeypatch.setattr(L, "render", fake_render)

    # evolve agent: appends the IMPROVED marker to the snapshot's systemprompt.md
    def fake_run_evolve(snapshot_dir_path, diag, run_dir):
        sp = snapshot_dir_path / "systemprompt.md"
        sp.write_text(sp.read_text() + "\nIMPROVED: verify the file before finishing.\n")
        return {"final_text": "added verify guidance", "trace": {"turns": 2}}
    monkeypatch.setattr(L, "run_evolve_agent", fake_run_evolve)

    cfg = L.LevelBConfig(n_iters=1, k=1, n_tasks=1, results_dir=str(tmp_path / "res"),
                         seed_worker_dir=str(tmp_path / "seed"))
    # build a minimal seed worker dir
    seed = tmp_path / "seed"; (seed / "tool_descriptions").mkdir(parents=True)
    (seed / "agent.yaml").write_text("name: w\n")
    (seed / "systemprompt.md").write_text("do the task\n")

    res = L.run_gdpval_levelb(cfg, _tasks=tasks)
    assert res.n_kept == 1                                   # the +0.40 edit beats the noise floor
    assert res.mean_score_trajectory[-1] > res.mean_score_trajectory[0]
    assert "IMPROVED" in (Path(res.final_worker_dir) / "systemprompt.md").read_text()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv-nexau/bin/python -m pytest tests/test_levelb.py::test_levelb_loop_keeps_improving_edit_offline -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'qea.loop_levelb'`

- [ ] **Step 3: Create `qea/loop_levelb.py`**

```python
"""The deterministic Level-B evolution loop (NexAU substrate).

Orchestrates two sibling NexAU agents — the weak worker and the file-editing evolve
agent — around an INDEPENDENT grader (the same MultimodalJudge the base test used)
and a FIREWALLED debugger. keep/rollback, the noise-floor soft gate, the leakage
guard, and the rejected-edit buffer all live HERE, in code; the evolve agent decides
nothing and never runs the grader.

Incumbent = a worker DIRECTORY (not a Harness object). Each iteration snapshots the
incumbent dir, lets the evolve agent edit the snapshot from an answer-free diagnosis,
re-grades, and promotes the snapshot only on an aggregate-score gain beyond the noise
floor (decide_keep_soft).
"""
from __future__ import annotations

import json
import statistics
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .benchmark import gdpval_benchmark
from .debugger import diagnose_b_pile
from .evolve_runtime import DirEdit, dir_unified_diff, run_evolve_agent, snapshot_dir
from .falsify import EvalSummary, LEAKAGE_BLOCKED, RejectedEditBuffer, decide_keep_soft
from .grading.multimodal_judge import MultimodalJudge
from .grading.render import render
from .llm import make_llm
from .verifier import LeakageGuard, TaskResult
from .worker_runtime import run_worker


@dataclass
class LevelBConfig:
    n_iters: int = 2
    k: int = 2
    n_tasks: int = 5                 # small by default — Phase 4 stands up the loop
    broad: bool = True
    results_dir: str = "results/levelb"
    seed_worker_dir: str = "qea/worker_gdpval_weak"


@dataclass
class LevelBRecord:
    iteration: int
    blocked: bool
    verdict: str
    kept: bool
    edit_summary: str
    root_cause_tag: str
    inc_mean: float
    cand_mean: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LevelBResult:
    n_tasks: int
    mean_score_trajectory: list
    records: list
    noise_margin: float
    final_mean_score: float
    final_worker_dir: str
    n_kept: int = 0
    n_rolled_back: int = 0
    n_blocked: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["records"] = [r.to_dict() if isinstance(r, LevelBRecord) else r for r in self.records]
        return d


def _eval_summary_from_grades(grades: dict, traces: dict, deliverables: dict, tasks) -> EvalSummary:
    """Adapt MultimodalJudge GradeResults into the EvalSummary the debugger expects."""
    by_id = {t.task_id: t for t in tasks}
    results = {}
    for tid, g in grades.items():
        sub = getattr(by_id.get(tid), "subtype", "")
        oos = g.multimodal_fraction >= 0.60
        results[tid] = TaskResult(tid, sub, "B", oos, oos, oos, g.multimodal_fraction,
                                  g.variance, None, criterion_verdicts=g.verdicts)
    return EvalSummary(results, deliverables)


def evaluate_dir(worker_dir: Path, tasks, judge, run_dir: Path, *, k: int):
    """Run the worker on every task with the given worker dir, render + grade each.
    Returns (grades, traces, deliverables, mean_score)."""
    worker_dir, run_dir = Path(worker_dir), Path(run_dir)
    grades, traces, deliverables = {}, {}, {}
    for task in tasks:
        wr = run_worker(task, worker_dir, run_dir)
        rendered = render(wr.deliverable_text, wr.produced_files, run_dir / str(task.task_id))
        grades[task.task_id] = judge.grade(task, rendered)
        traces[task.task_id] = wr.trace
        deliverables[task.task_id] = rendered.text or ""
    mean = (statistics.mean(g.multimodal_fraction for g in grades.values()) if grades else 0.0)
    return grades, traces, deliverables, mean


def run_gdpval_levelb(cfg: LevelBConfig, *, _tasks=None) -> LevelBResult:
    """Stand up + run the Level-B loop. `_tasks` injects a task list for offline tests;
    in real use the GDPval benchmark provides them."""
    llm = make_llm(False)
    judge = MultimodalJudge(llm, k=cfg.k)
    if _tasks is not None:
        tasks, answer_corpus = _tasks, []
    else:
        bm = gdpval_benchmark(broad=cfg.broad, allow_download=True, llm=llm)
        tasks = bm.tasks[: cfg.n_tasks]
        answer_corpus = bm.answer_corpus
    guard = LeakageGuard(answer_corpus)
    buffer = RejectedEditBuffer()
    results_dir = Path(cfg.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    # incumbent = a live copy of the seed worker dir under the results dir
    incumbent = results_dir / "incumbent_worker"
    snapshot_dir(Path(cfg.seed_worker_dir), incumbent)

    # seed eval + a 2nd same-dir eval for the noise floor (mirror run_gdpval_soft)
    grades, traces, deliverables, inc_mean = evaluate_dir(incumbent, tasks, judge, results_dir / "seed", k=cfg.k)
    _, _, _, noise_mean = evaluate_dir(incumbent, tasks, judge, results_dir / "seed_noise", k=cfg.k)
    noise_margin = max(0.01, abs(inc_mean - noise_mean))

    ms_traj = [round(inc_mean, 4)]
    records: list = []
    n_kept = n_rb = n_blocked = 0

    for it in range(1, cfg.n_iters + 1):
        inc_eval = _eval_summary_from_grades(grades, traces, deliverables, tasks)
        diag = diagnose_b_pile(inc_eval, tasks, llm=llm, traces=traces).proposer_payload()

        cand_dir = results_dir / f"iter_{it:03d}" / "worker"
        snapshot_dir(incumbent, cand_dir)
        run_evolve_agent(cand_dir, diag, results_dir / f"iter_{it:03d}")
        diff = dir_unified_diff(incumbent, cand_dir)
        edit = DirEdit(diff)

        if not diff:
            verdict, kept = "NO_EDIT", False
            n_blocked += 1
        elif guard.is_leak(edit):
            verdict, kept = LEAKAGE_BLOCKED, False
            n_blocked += 1
            buffer.add(edit, verdict, 0, 0, "pasted answer material into a worker file")
        elif buffer.blocks(edit):
            verdict, kept = "BLOCKED", False
            n_blocked += 1
        else:
            cg, ct, cd, cand_mean = evaluate_dir(cand_dir, tasks, judge, results_dir / f"iter_{it:03d}" / "grade", k=cfg.k)
            kept = decide_keep_soft(inc_mean, cand_mean, noise_margin)
            verdict = "EFFECTIVE" if kept else "INEFFECTIVE"
            if kept:
                n_kept += 1
                incumbent = cand_dir
                grades, traces, deliverables, inc_mean = cg, ct, cd, cand_mean
            else:
                n_rb += 1
                buffer.add(edit, verdict, 0, 0, "no aggregate score gain beyond the noise floor")
            records.append(LevelBRecord(it, False, verdict, kept, edit.summary,
                                        diag.get("root_cause_tag", ""), round(inc_mean, 4), round(cand_mean, 4)))
            ms_traj.append(round(inc_mean, 4))
            _persist(results_dir, it, verdict, kept, edit, diag, inc_mean)
            continue

        records.append(LevelBRecord(it, True, verdict, kept, edit.summary,
                                    diag.get("root_cause_tag", ""), round(inc_mean, 4), round(inc_mean, 4)))
        ms_traj.append(round(inc_mean, 4))
        _persist(results_dir, it, verdict, kept, edit, diag, inc_mean)

    return LevelBResult(
        n_tasks=len(tasks), mean_score_trajectory=ms_traj, records=records,
        noise_margin=round(noise_margin, 4), final_mean_score=round(inc_mean, 4),
        final_worker_dir=str(incumbent), n_kept=n_kept, n_rolled_back=n_rb, n_blocked=n_blocked)


def _persist(results_dir: Path, it: int, verdict: str, kept: bool, edit, diag: dict, inc_mean: float) -> None:
    d = results_dir / f"iter_{it:03d}"
    d.mkdir(parents=True, exist_ok=True)
    (d / "manifest.json").write_text(json.dumps({
        "iteration": it, "verdict": verdict, "kept": kept,
        "edit_summary": edit.summary, "diff_signature": edit.signature(),
        "diagnosis": diag, "inc_mean": round(inc_mean, 4),
    }, indent=2, default=str))
    (d / "edit.diff").write_text(edit.diff)
```

- [ ] **Step 4: Run the loop test to verify it passes**

Run: `.venv-nexau/bin/python -m pytest tests/test_levelb.py::test_levelb_loop_keeps_improving_edit_offline -v`
Expected: PASS

- [ ] **Step 5: Add a rollback test (an edit that does NOT improve is discarded + buffered)**

Add to `tests/test_levelb.py`:
```python
def test_levelb_loop_rolls_back_non_improving_edit(tmp_path, monkeypatch):
    import qea.loop_levelb as L
    from qea.worker_runtime import WorkerRun
    from qea.grading.multimodal_judge import GradeResult
    from qea.tasks import BTask
    from types import SimpleNamespace

    tasks = [BTask(task_id="t1", subtype="x", prompt="p", rubric="",
                   rubric_items=[{"points": 1, "criterion": "c"}], gold="g")]
    monkeypatch.setattr(L, "run_worker",
                        lambda task, wd, rd: WorkerRun("same", [], {"files": 1, "turns": 5, "tool_errors": 0}))

    class FlatJudge:
        def __init__(self, *a, **k): pass
        def grade(self, task, rendered):
            return GradeResult(task.task_id, 0.50, 0.50, {"1": False}, 0.0, False)  # never improves
    monkeypatch.setattr(L, "MultimodalJudge", FlatJudge)
    monkeypatch.setattr(L, "render",
                        lambda t, p, o: SimpleNamespace(text=t, extracted_text=t, images=[], degraded=False))
    # evolve makes a real (but useless) change so the diff is non-empty
    def ev(snap, diag, rd):
        sp = snap / "systemprompt.md"; sp.write_text(sp.read_text() + "\nnoise edit\n")
        return {"final_text": "x", "trace": {}}
    monkeypatch.setattr(L, "run_evolve_agent", ev)

    seed = tmp_path / "seed"; (seed / "tool_descriptions").mkdir(parents=True)
    (seed / "agent.yaml").write_text("name: w\n"); (seed / "systemprompt.md").write_text("do it\n")
    cfg = L.LevelBConfig(n_iters=1, k=1, n_tasks=1, results_dir=str(tmp_path / "res"),
                         seed_worker_dir=str(seed))
    res = L.run_gdpval_levelb(cfg, _tasks=tasks)
    assert res.n_kept == 0 and res.n_rolled_back == 1        # flat score -> rolled back
    assert res.records[0].verdict == "INEFFECTIVE"
```

Run: `.venv-nexau/bin/python -m pytest tests/test_levelb.py::test_levelb_loop_rolls_back_non_improving_edit -v`
Expected: PASS

- [ ] **Step 6: Run the full offline Level-B test file**

Run: `.venv-nexau/bin/python -m pytest tests/test_levelb.py -v -k "not smoke"`
Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add qea/loop_levelb.py tests/test_levelb.py
git commit -m "feat(levelb): deterministic Level-B loop (snapshot/grade/diagnose/evolve/keep-rollback)"
```

---

### Task 6: CLI wiring, gated NexAU smoke test, and headroom measurement

**Files:**
- Modify: `run.py`
- Create: `docs/RESULTS_levelb_gdpval.md`
- Test: `tests/test_levelb.py`

- [ ] **Step 1: Add a `--levelb` mode to `run.py`**

In `run.py`, change the import line (line 18) to also import the Level-B entry:
```python
from qea.loop import Config, acceptance_signals, run_synthetic_fixture, run_gdpval_soft
from qea.loop_levelb import LevelBConfig, run_gdpval_levelb
```
Add the CLI flag in `main()` after the `--real` flag (inside the mutually-exclusive group, line 54):
```python
    mode.add_argument("--levelb", action="store_true",
                      help="real mode: Level-B evolution (file-editing evolve agent edits the NexAU worker dir)")
    ap.add_argument("--n-tasks", type=int, default=5, help="levelb: number of GDPval tasks per iteration")
```
Add the dispatch branch at the start of `main()`'s body, right after `_load_dotenv()` (line 62), BEFORE the `mock = not args.real` line:
```python
    if args.levelb:
        lcfg = LevelBConfig(n_iters=args.iters, k=args.k, n_tasks=args.n_tasks,
                            broad=not args.core, results_dir=args.results_dir)
        print(f"[run] mode=LEVEL-B (NexAU worker dir evolved by a file-editing evolve agent) "
              f"iters={lcfg.n_iters} k={lcfg.k} n_tasks={lcfg.n_tasks} -> {lcfg.results_dir}")
        res = run_gdpval_levelb(lcfg)
        _print_levelb(res)
        rose = res.mean_score_trajectory[-1] > res.mean_score_trajectory[0] + res.noise_margin
        print(f"\n  ==> LEVEL-B HEADROOM {'OBSERVED' if rose else 'NOT OBSERVED'}: "
              f"mean {res.mean_score_trajectory[0]:.3f} -> {res.mean_score_trajectory[-1]:.3f} "
              f"(noise floor {res.noise_margin:.3f}), {res.n_kept} edit(s) kept.")
        return 0 if rose else 1
```
Add the printer beside `_print_soft` (after line 110):
```python
def _print_levelb(res) -> None:
    print(f"\n=== Level-B evolution ({res.n_tasks} GDPval tasks, multimodal-grade gate) ===")
    print(f"  noise floor (gain a candidate must beat): {res.noise_margin}")
    print(f"  mean multimodal-score trajectory: {res.mean_score_trajectory}")
    print(f"  {'iter':>4} {'verdict':<16} {'kept':<8} inc->cand")
    for r in res.records:
        flag = "BLOCKED" if r.blocked else ("keep" if r.kept else "rollback")
        print(f"  {r.iteration:>4} {r.verdict:<16} {flag:<8} {r.inc_mean:.3f}->{r.cand_mean:.3f}  | {r.edit_summary}")
    print(f"  final mean multimodal score: {res.final_mean_score}")
    print(f"  final worker dir: {res.final_worker_dir}")
    print(f"  kept/rolledback/blocked: {res.n_kept}/{res.n_rolled_back}/{res.n_blocked}")
```

- [ ] **Step 2: Verify the CLI parses (no run)**

Run: `.venv-nexau/bin/python run.py --help`
Expected: help text lists `--levelb` and `--n-tasks`; exit 0.

- [ ] **Step 3: Add the gated NexAU smoke test (real API, opt-in)**

Add to `tests/test_levelb.py`:
```python
@pytest.mark.skipif(os.environ.get("QEA_LEVELB_SMOKE") != "1",
                    reason="set QEA_LEVELB_SMOKE=1 to run the real-API NexAU Level-B smoke test")
def test_levelb_smoke_one_task_one_iter(tmp_path):
    # End-to-end on ONE real GDPval task, ONE iteration, against the real NexAU
    # weak worker + evolve agent. Proves the wiring runs; makes no headroom claim.
    import run as runmod
    runmod._load_dotenv()
    from qea.loop_levelb import LevelBConfig, run_gdpval_levelb
    cfg = LevelBConfig(n_iters=1, k=1, n_tasks=1, results_dir=str(tmp_path / "res"))
    res = run_gdpval_levelb(cfg)
    assert res.n_tasks == 1
    assert len(res.mean_score_trajectory) >= 1
    assert Path(res.final_worker_dir).exists()
    assert (Path(cfg.results_dir) / "iter_001" / "manifest.json").exists()
```

- [ ] **Step 4: Run the gated smoke test for real (one task, one iter)**

Run:
```bash
QEA_LEVELB_SMOKE=1 .venv-nexau/bin/python -m pytest tests/test_levelb.py::test_levelb_smoke_one_task_one_iter -v -s
```
Expected: PASS. If it fails on a connect timeout, confirm the proxy is up and `timeout: 180` is present in both `qea/worker_gdpval_weak/agent.yaml` and `qea/evolve_agent/agent.yaml` (the documented connect-timeout gotcha). If it fails because the evolve agent wrote outside the snapshot, tighten the systemprompt constraint and re-run.

- [ ] **Step 5: Measure weak-seed vs full-worker headroom**

Run the weak seed across a small task set to get the weak baseline, then compare to the full-worker base result (0.797):
```bash
QEA_GDPVAL_CONCURRENCY=2 .venv-nexau/bin/python - <<'PY'
import run; run._load_dotenv()
from qea.loop_levelb import evaluate_dir, LevelBConfig
from qea.benchmark import gdpval_benchmark
from qea.grading.multimodal_judge import MultimodalJudge
from qea.llm import make_llm
from pathlib import Path
llm = make_llm(False)
bm = gdpval_benchmark(broad=True, allow_download=True, llm=llm)
tasks = bm.tasks[:5]
judge = MultimodalJudge(llm, k=2)
_, _, _, mean = evaluate_dir(Path("qea/worker_gdpval_weak"), tasks, judge, Path("output/levelb_weakbase"), k=2)
print(f"WEAK-SEED mean multimodal over {len(tasks)} tasks: {mean:.3f}  (full worker base: 0.797)")
PY
```
Expected: prints a weak-seed mean BELOW 0.797 (the headroom). Record the number for the results doc. (If the weak seed scores ~0.797, the weakening was insufficient — strip more guidance from `qea/worker_gdpval_weak/systemprompt.md` and re-measure.)

- [ ] **Step 6: Run a short real Level-B loop (3 tasks, 2 iters)**

Run:
```bash
QEA_GDPVAL_CONCURRENCY=2 .venv-nexau/bin/python run.py --levelb --n-tasks 3 --iters 2 --k 2 --results-dir results/levelb_smoke
```
Expected: the iteration table prints; each iter shows a verdict (keep/rollback/blocked) and an `inc->cand` mean. Capture the printed trajectory and the final line for the results doc.

- [ ] **Step 7: Write the results doc**

Create `docs/RESULTS_levelb_gdpval.md` with the actual numbers from Steps 5–6:
```markdown
# Phase 4 — Level-B evolve loop (NexAU substrate) — standup results

The loop now runs the REAL NexAU worker dir (not the retired single-completion over
the 7-slot abstraction) and grades with the SAME MultimodalJudge as the base test.

## Headroom (weak seed vs full worker)
- Full worker (base test, 30 tasks): mean multimodal **0.797**.
- Weak seed (`qea/worker_gdpval_weak/`, <N> tasks): mean multimodal **<fill from Step 5>**.
- Headroom the evolve loop can target: **<0.797 − weak>**.

## Loop behavior (short real run, 3 tasks, 2 iters)
- noise floor: <fill>
- mean-score trajectory: <fill>
- per-iteration verdicts: <fill the keep/rollback/blocked table>
- edits kept / rolled back / blocked: <fill>

## Notes
- Grader + debugger are independent of the evolve agent; the evolve agent reads only
  the answer-free sanitized diagnosis (+ folded-in process trace) and edits a snapshot.
- keep/rollback, the noise-floor gate, the leakage guard, and the rejected-edit buffer
  all live in `qea/loop_levelb.py` (deterministic), not in any agent.
```

- [ ] **Step 8: Run the full offline suite to confirm no regressions**

Run: `.venv-nexau/bin/python -m pytest tests/ -q`
Expected: all tests pass (the gated smoke test is skipped without `QEA_LEVELB_SMOKE=1`).

- [ ] **Step 9: Commit**

```bash
git add run.py docs/RESULTS_levelb_gdpval.md tests/test_levelb.py
git commit -m "feat(levelb): --levelb CLI mode, gated NexAU smoke test, headroom results"
```

- [ ] **Step 10: Finish the branch**

Use superpowers:finishing-a-development-branch to verify tests, then present merge options.

---

## Self-Review

**1. Spec coverage** (against `docs/superpowers/specs/2026-06-23-phase4-level-b-evolve-design.md`):
- Substrate unification (run the real NexAU worker, retire the single-completion path) → Task 1 (`run_worker`) + Task 5 (loop calls `run_worker`/`evaluate_dir`, never `quant_agent_solve`). ✓
- Worker trace as a debugger input → Task 3 (`process_note` + `traces` fold-in). ✓
- File-editing NexAU evolve agent editing a snapshot → Task 4 (`qea/evolve_agent/` + `run_evolve_agent` + `snapshot_dir`). ✓
- Seed weakening + headroom measurement → Task 2 (`qea/worker_gdpval_weak/`) + Task 6 Step 5. ✓
- keep/rollback / noise floor / leakage guard / rejected-edit buffer stay in code → Task 5 (`decide_keep_soft`, `LeakageGuard`, `RejectedEditBuffer` reused; `DirEdit` shim). ✓
- Firewall (answer-free to evolve agent) → Task 3 firewall test + Task 4 prompt constraint + `proposer_payload()` reuse. ✓
- Grader = same MultimodalJudge as base test → Task 5 (`evaluate_dir` uses `render` + `MultimodalJudge.grade`). ✓
- Mock path keeps the 7-slot abstraction (not retired globally) → unchanged `qea/loop.py:run_synthetic_fixture`; Level-B is a separate module, so `run.py --mock` still works. ✓

**2. Placeholder scan:** The results-doc `<fill>` markers in Task 6 Step 7 are intentional run-output capture points (the engineer fills them from Steps 5–6 output), not code placeholders — every code step shows complete code. No `TODO`/`implement later` in any code block.

**3. Type consistency:** `WorkerRun(deliverable_text, produced_files, trace)` is produced by `run_worker` (Task 1) and consumed in `evaluate_dir` (Task 5) by the same field names. `GradeResult.multimodal_fraction` / `.verdicts` / `.variance` (read in Task 5) match `qea/grading/multimodal_judge.py`. `DirEdit.signature()/.content/.summary` (Task 4) are exactly what `RejectedEditBuffer.blocks/add` and `LeakageGuard.is_leak` call. `diagnose_b_pile(..., traces=...)` (Task 3) matches the call in Task 5. `LevelBConfig` fields (`n_iters/k/n_tasks/broad/results_dir/seed_worker_dir`) match both the loop and the `run.py` construction.
