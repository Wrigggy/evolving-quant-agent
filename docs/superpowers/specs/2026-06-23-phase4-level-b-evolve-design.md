# Phase 4 — Level-B evolve loop (NexAU substrate unification + file-editing evolve agent)

**Date:** 2026-06-23 (rev. 2026-06-25) · **Depends on:** `2026-06-22-nexau-migration-design.md` (Phases 1–3 merged)

## Goal
Stand up the **Level-B evolution loop** on the NexAU substrate: a deterministic loop
orchestrating two sibling NexAU agents — a (deliberately weakened) **worker** and a
file-editing **evolve agent** — with an **independent grader + firewalled debugger**
producing the signal the evolve agent acts on. Out of scope: running large evolution
experiments; this phase stands up the loop and measures headroom.

## The substrate mismatch this revision fixes (read first)
Phases 1–3 base-tested the **real NexAU worker** (`qea/worker_gdpval/`: agent.yaml + sandbox +
shell tool + real deliverable files) → mean multimodal 0.797. **But the evolution loop does not
use it.** `qea/loop.py:run_gdpval_soft` → `agents.py:quant_agent_solve` → `_quant_solve_real` →
a single `llm.complete()` call over a **synthetic 7-slot `Harness` abstraction**
(`tool/middleware/skill/prompt/validator/memory/router`). So today there are **two unrelated
workers**:

- base test → the real NexAU agent (what we will ship and report);
- evolution loop → a legacy single-completion over an in-memory abstraction.

The evolve agent (`agents.py:evolve_agent_propose`) is therefore **Level A**: a text-only
`llm.complete()` returning JSON `Edit{op, slot, component_name, content}` that mutates the
in-memory `Harness` — **not a NexAU agent, and it never touches a file on disk.** AHE's core
move ("an agent edits another agent's actual code") is absent.

**Decision (2026-06-25): unify on the NexAU worker.** The evolution loop will run the real
`qea/worker_gdpval/` agent, and the evolve agent will edit that directory. The legacy
single-completion path (`_quant_solve_real`) and the abstract 7-slot `Harness` are **retired**
for the GDPval evolve loop. This makes the thing we evolve identical to the thing we base-tested
and will ship — fully AHE-faithful.

## What's already AHE-faithful (keep, do not rebuild)
- **Loop owns keep/rollback** + noise-floor soft gate (`decide_keep_soft`) + rejected-edit
  buffer + leakage guard — all deterministic code. The evolve agent decides nothing.
- **Observation firewall (iron law 2):** `_propose_real`'s B-pile branch already builds the
  proposer context from the *sanitized* diagnosis only (root-cause tag, component-level slot,
  opaque task ids) — no rubric/gold/deliverable text. This firewall discipline carries forward
  verbatim to the new evolve agent.
- **Benchmark abstraction:** `qea/benchmark.py` `Benchmark(tasks, grader, answer_corpus,
  debugger_kind)` binds each benchmark to its grader + debugger kind — keep it.

## Components (reuse vs new vs retire)
- **worker agent** (NexAU dir, `qea/worker_gdpval/`) — does the task; produces a
  **deliverable/answer AND a trace** (tool calls, errors, turns used). *Phase-4 change:* seed
  deliberately weak (primitive tools + minimal prompt; high-level tools/skills removed) to create
  headroom. The loop runs THIS agent (not the legacy completion).
- **`run_worker()`** (NEW, reusable) — lift the NexAU-invocation + trace-capture + file-capture
  logic out of `scripts/nexau_gdpval_run.py` (`run_task` / `_trace_summary`) into a function the
  loop calls per (task, worker-dir snapshot). Returns `(deliverable_text, produced_files, trace)`.
- **grader** (per benchmark; reuse `qea/verifier.py` `score_rubric` /
  `qea/grading/multimodal_judge.py`) — produces **score + per-criterion verdicts**. Independent
  of the evolve agent.
- **debugger / evaluator** (general; reuse + extend `qea/debugger.py`) — turns
  (verdicts + worker trace) into a **sanitized, answer-free diagnosis**. Independent.
- **evolve agent** (NexAU, **NEW**) — a file-editing NexAU agent (apply_patch/write_file/edit_file)
  that reads ONLY the sanitized diagnosis and edits a **snapshot of the worker DIRECTORY**.
  Replaces `agents.py:evolve_agent_propose` (Level A) for the GDPval loop.
- **RETIRE (for the GDPval evolve loop):** `_quant_solve_real` single-completion path and the
  abstract 7-slot `Harness` (`qea/harness.py`) as the evolution substrate. (The synthetic `--mock`
  fixture may keep using the abstraction as a cheap plumbing test — see Migration notes.)

## Dataflow (who produces "results/diagnosis", and the firewall)
```
worker(NexAU dir snapshot) ─run_worker()─► ① deliverable/answer  ② trace (tool calls/errors/turns)
                       │                          │
                       ▼                          ▼
                 ┌───────────┐            ┌──────────────────────────┐
                 │ grader     │            │ debugger / evaluator      │
                 │ (per-bench)│ ─verdicts─►│ (general, FIREWALLED)     │
                 │ score+verd │            │ in: verdicts + trace      │
                 └───────────┘            │ out: answer-free diagnosis │
                       │ score             └──────────────────────────┘
                       │ (to loop)                    │ sanitized diagnosis
                       ▼                               ▼
        keep/rollback ◄── loop ──────► evolve agent (NexAU) ── edits worker-dir snapshot
                       │ (snapshot promoted to incumbent on keep)
                       ▼
                 next iteration runs the promoted snapshot
```
- **Both grader and debugger are independent of the evolve agent** (measurement ≠ proposal —
  the deleted pairwise grader was removed precisely for fusing them).
- **Observation firewall (iron law 2):** the debugger's output to the evolve agent MUST be
  answer-free. The evolve agent never sees ground-truth answers / gold deliverables — only
  *which criteria failed* and *process diagnosis*. (See the prior leak: A-pile semantics fed
  to B-pile made the proposer fix phantom failures.)

## Worker trace as a NEW debugger input (the Level-B upgrade)
v0's worker was a single LLM call → the debugger only had rubric verdicts ("answer side").
The NexAU worker is a real agentic agent → it emits a **trajectory** (we already compute
`_trace_summary`: tool_calls / tool_errors / turns / secs). The debugger now also diagnoses the
**process / code-behavior side**, e.g.:
- ran out of turns before producing a deliverable;
- never called a relevant tool / never read the provided reference files;
- a tool errored, or the agent looped on repeated tool calls (stuck);
- produced no deliverable file (the `files=0` degraded case, e.g. the 16-PDF tax task → 0.000).
This process-side signal is the richer headroom source — it tells the evolve agent *what to
change in the worker's tools/prompt* (the AHE "Agent Debugger" / ADB pattern, already reproduced).

## keep/rollback (stays in the loop, deterministic)
The loop snapshots the worker dir to `experiments/<ts>/iter_<n>/worker/`, runs
`run_worker→grader` on the task set, lets the evolve agent edit the snapshot, re-runs, and keeps
the edit only if the aggregate score beats the incumbent beyond the eval-noise floor (reuse
`decide_keep_soft` + the same-seed noise-floor measurement already in `run_gdpval_soft`). On keep,
the edited snapshot becomes the incumbent dir; on rollback, it is discarded and the edit signature
goes into the rejected-edit buffer. The evolve agent does NOT decide keep/rollback and does NOT
run the grader.

## Seed weakening (to create headroom)
Strip the seed worker so it is *process-limited, not capability-walled*: minimal generic
system prompt; only primitive tools (bare shell), with high-level conveniences (e.g. an
explicit "save your deliverable and `ls -la` to verify" finish-guidance, any retrieval helpers,
context summarization hints) REMOVED from the seed and left for evolution to (re)discover.
Measure **(weak-seed score) vs (full-worker 0.797)** = the headroom the evolve loop can target.
Keep the weakening to the prompt/tool-availability layer so the gap is *recoverable by editing
the dir*, not a base-model capability wall (iron law 1: a true capability-wall task must stay
unfixed).

## Migration notes (retiring the legacy path safely)
- `run_gdpval_soft` currently calls `quant_agent_solve`. Replace that call with `run_worker()`
  against the incumbent worker-dir snapshot. The grader/firewall/gate/buffer code is unchanged.
- The `--mock` synthetic-fixture path (`run_synthetic_fixture`) may KEEP using the 7-slot
  abstraction + scripted `_propose_mock` as a fast, no-API plumbing test of
  evolve→falsify→rollback→buffer. It makes no headroom claim, so the abstraction is fine there.
  Document clearly that the abstraction is mock-only; the real GDPval loop is NexAU-dir-native.
- Keep `agents.py:evolve_agent_propose` only if the mock path needs it; the real GDPval loop
  no longer routes through it.

## Open questions
- Trace summarization format the debugger emits (keep answer-free).
- Evolve-agent edit scope/guardrails: confine writes to the snapshot worker dir; no test/grader
  access; reject edits that touch anything outside the snapshot.
- Snapshot granularity: full `qea/worker_gdpval/` copy per iteration (AHE-style) vs git-style diff.
  Default: full copy under `experiments/<ts>/iter_<n>/worker/`.
- Does the evolve agent run as a NexAU sub-agent of the loop, or as a sibling the loop invokes
  directly? Default: sibling invoked by the loop (AHE pattern; cleaner keep/rollback ownership).
- Per-benchmark debugger specialization vs one general debugger consuming benchmark verdicts.
