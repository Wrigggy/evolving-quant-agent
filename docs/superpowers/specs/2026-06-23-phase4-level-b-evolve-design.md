# Phase 4 — Level-B evolve loop (grader / firewalled-debugger / evolve dataflow)

**Date:** 2026-06-23 · **Depends on:** `2026-06-22-nexau-migration-design.md` (Phases 1–3 merged)

## Goal
Stand up the **Level-B evolution loop** on the NexAU substrate: a deterministic loop
orchestrating two sibling NexAU agents — a (deliberately weakened) **worker** and a
file-editing **evolve agent** — with an **independent grader + firewalled debugger**
producing the signal the evolve agent acts on. Out of scope: running large evolution
experiments; this phase stands up the loop and measures headroom.

## Components (reuse vs new)
- **worker agent** (NexAU dir, `qea/worker*`) — does the task; produces a **deliverable/answer
  AND a trace** (tool calls, errors, turns used). *Phase-4 change:* seed deliberately weak
  (primitive tools + minimal prompt; high-level tools/skills removed) to create headroom.
- **grader** (per benchmark; reuse `qea/verifier.py` `score_rubric` / `qea/grading/multimodal_judge.py`)
  — produces **score + per-criterion verdicts**. Independent of the evolve agent.
- **debugger / evaluator** (general; reuse + extend `qea/debugger.py`) — turns
  (verdicts + worker trace) into a **sanitized, answer-free diagnosis**. Independent.
- **evolve agent** (NexAU, **NEW**) — a file-editing NexAU agent (apply_patch/write_file/edit_file)
  that reads ONLY the sanitized diagnosis and edits the worker DIRECTORY. Replaces the
  current text-only `qea/agents.py:evolve_agent_propose` (Level A).
- **loop** (deterministic code, `qea/loop.py`) — orchestrates; owns keep/rollback, scoring,
  budget. NOT an agent.

`qea/benchmark.py`'s `Benchmark(tasks, grader, answer_corpus, debugger_kind)` already binds
each benchmark to its grader + debugger kind — keep that abstraction.

## Dataflow (who produces "results/diagnosis", and the firewall)
```
worker(NexAU) ──► ① deliverable/answer      ② trace (tool calls / errors / turns)
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
                 keep/rollback ◄── loop ──────► evolve agent (NexAU) ── edits qea/worker/
```
- **Both grader and debugger are independent of the evolve agent** (measurement ≠ proposal —
  the deleted pairwise grader was removed precisely for fusing them).
- **Observation firewall (iron law 2):** the debugger's output to the evolve agent MUST be
  answer-free. The evolve agent never sees ground-truth answers / gold deliverables — only
  *which criteria failed* and *process diagnosis*. (See the prior leak: A-pile semantics fed
  to B-pile made the proposer fix phantom failures.)

## Worker trace as a NEW debugger input (the Level-B upgrade)
v0's worker was a single LLM call → the debugger only had rubric verdicts ("answer side").
The NexAU worker is a real agentic agent → it emits a **trajectory**. The debugger now also
diagnoses the **process / code-behavior side**, e.g.:
- ran out of turns before producing a deliverable;
- never called a relevant tool (e.g. `retrieve_from_filing` / `company_filings`);
- a tool errored, or the agent never read the provided reference files;
- repeated/looping tool calls (stuck).
Capture: NexAU exposes the run trace (it ships an `InMemoryTracer`; `agent.full_trace` /
`agent.history`). The debugger consumes a structured summary of it. This process-side signal
is the richer headroom source — it tells the evolve agent *what to change in the worker's
tools/prompt* (this is the AHE "Agent Debugger" / ADB pattern, already reproduced).

## keep/rollback (stays in the loop, deterministic)
The loop runs worker→grader on the task set, snapshots `qea/worker/` to `experiments/<ts>/`,
lets the evolve agent edit, re-runs, and keeps the edit only if the aggregate score beats the
incumbent beyond the eval-noise floor (reuse the `decide_keep_soft` idea). The evolve agent
does NOT decide keep/rollback and does NOT run the grader.

## Seed weakening (to create headroom)
Strip the seed worker so it is *process-limited, not capability-walled*: minimal generic
system prompt; only primitive tools (e.g. bare `fetch_page` / shell), with the high-level
conveniences (`retrieve_from_filing`, `company_filings`, the finish/answer guidance, context
summarization) REMOVED from the seed and left for evolution to (re)discover. Measure
(weak-seed score) vs (full-worker score) = the headroom the evolve loop can target.

## Open questions
- Trace summarization format the debugger emits (keep answer-free).
- Evolve-agent edit scope/guardrails (confine writes to `qea/worker/`; no test/grader access).
- Does the evolve agent edit a SNAPSHOT (per-iteration copy) or the live dir? (snapshot, AHE-style.)
- Per-benchmark debugger specialization vs one general debugger consuming benchmark verdicts.
