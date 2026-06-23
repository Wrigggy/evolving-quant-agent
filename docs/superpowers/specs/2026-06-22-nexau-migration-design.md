# NexAU migration + Level-B evolvable worker — design

**Date:** 2026-06-22 · **Branch:** `qea/nexau-migration` · Reference: `/Users/kevinwu/Coding/agentic-harness-engineering` (AHE, NexAU-based)

## Goal
Move the worker substrate from **Stirrup (code-first)** to **NexAU (directory/YAML-defined agent)** so that:
1. The whole evolvable harness lives in **one place** (`qea/worker/`) as editable files — clean separation from loop/grader.
2. **Level B evolution** is native: the evolve agent edits the worker directory's tool/skill/prompt files (code synthesis), runs in the NexAU sandbox — no hand-built "agent-as-directory" layer (which Stirrup would require).

This is both the requested refactor AND the Level-B substrate, in one move.

## Decisions (settled in discussion)
- Evolution action space = **Level B** (edit worker codebase), not text-only config.
- Runtime = **NexAU** (AHE's substrate; agent = `agent.yaml` + `systemprompt.md` + `tool_descriptions/*.yaml` + `tools/*.py`, built-in sandbox). Stirrup dropped.
- Migrate, don't rewrite: our tool *logic* is plain Python (httpx → EDGAR/Yahoo/DDG); only the wrapper changes.
- Seed worker deliberately **weak** (primitives + minimal prompt) so evolution has headroom.

## Key clarification — what is and isn't coupled to NexAU
- **Grading is runtime-independent and unchanged.** `score_rubric`/`build_rubric_prompt` (per-rubric), and for GDPval the **multimodal pipeline** (`render.py` LibreOffice→PNG + `multimodal_judge.py`) operate on the deliverable **files/text on disk** — they do not care which runtime produced them. They carry over as-is.
- **The only NexAU touch-point for GDPval** is *getting the produced deliverable files out of the NexAU sandbox to a local dir* (replacing Stirrup's `session(output_dir=...)` auto-download), plus giving the agent a shell/code tool to write files. After extraction, render+grade are unchanged.

## Stirrup → NexAU mapping
| Stirrup (now) | NexAU (target) |
|---|---|
| `Tool[Params,_R](name, description, parameters=PydanticModel, executor=fn)` | `tool_descriptions/<name>.tool.yaml` (name + description + JSON-schema `input_schema`) + `tools/<group>/<name>.py` fn, bound via `binding: tools.<group>:<fn>` |
| `_SYSTEM` python string | `systemprompt.md` |
| `Agent(client, name, system_prompt, tools, max_turns)` | `agent.yaml` → `AgentConfig.from_yaml` / `Agent.from_yaml(...).run(...)` |
| `FabWorker` / `StirrupWorker` / `e2b_reconnect` | NexAU `Agent.run()` + NexAU built-in sandbox; deliverable files exported from sandbox |
| Stirrup `ChatCompletionsClient` (OpenRouter) | NexAU `llm_config` (base_url/api_key/api_type) → OpenRouter |

**Carries over unchanged (runtime-independent):** `qea/tasks.py` + `qea/tasks_fab.py` loaders, `qea/verifier.py` scorer, `qea/grading/*` (render + multimodal judge), rubric data, the free-tool httpx logic (re-wrapped, not rewritten).
**Dropped:** Stirrup dependency, `qea/workers/{stirrup_worker,fab_worker,fab_tools,e2b_reconnect}.py` (their *logic* moves into `qea/worker/`).

## Target structure
```
qea/
  bench/        # benchmarks (NOT evolved): loaders, graders, runner
      gdpval.py  fab.py  grade.py  render.py  runner.py
  evolve/       # evolution loop + evolve-agent (file tools scoped to qea/worker/) + sandbox glue (NOT evolved)
  worker/       # ★ THE EVOLVABLE HARNESS — the one place the evolve agent edits
      agent.yaml
      systemprompt.md             (prompt slot — minimal seed)
      tool_descriptions/*.tool.yaml
      tools/  (edgar.py, retrieve.py, price.py, web.py, shell/code …  SEED = primitives only)
      skills/  middleware/         (skill / middleware slots — empty at seed)
```
Each evolve iteration snapshots `qea/worker/` into `experiments/<ts>/worker/` (AHE pattern).

## Risks / unknowns (de-risk first)
1. **NexAU ↔ OpenRouter connectivity** — NexAU sample uses `api_type: openai_responses`; OpenRouter may need `openai` (chat-completions). **Highest-risk assumption; spike it first.**
2. **Python 3.14** — NexAU is installed in AHE's `.venv` (py3.14). Decide: shared venv vs a new QEA venv with `nexau @ git+...NexAU.git@v0.3.9`. (Our `.venv312` is 3.12 — confirm NexAU runs on 3.12 or use 3.14.)
3. **SOCKS proxy** — NexAU's LLM/tool HTTP must traverse the same proxy (we hit this with httpx; ensure NexAU honors it or set explicit proxy).
4. **Sandbox file export** (GDPval) — confirm how to pull produced files out of NexAU's sandbox.

## Phased plan
- **Phase 1 — connectivity spike:** install NexAU; run a trivial NexAU agent (1 custom tool) against OpenRouter through the proxy; confirm `llm_config` + tool binding + sandbox work. Smallest possible end-to-end. (De-risks #1–#3.)
- **Phase 2 — FAB worker on NexAU (text, simplest):** port the 5 free tools to NexAU tool files; `systemprompt.md`; run FAB end-to-end; grade with the unchanged scorer; compare to the Stirrup FAB number (0.659) as a port-fidelity check.
- **Phase 3 — structure + GDPval:** reorganize into `qea/{bench,evolve,worker}`; add shell/code tool + sandbox file-export for GDPval; multimodal grading unchanged; reproduce GDPval base.
- **Phase 4 — Level-B evolve loop:** wire the evolve loop + evolve-agent file-tools scoped to `qea/worker/`; snapshot per iteration; weaken the seed; measure headroom (weak-seed vs configured).

## Architecture (the mental model — worker vs evolve vs loop)
NOT "NexAU nested in NexAU". It is a **deterministic loop (plain code, NOT an agent)
orchestrating TWO sibling NexAU agents** at different levels:
- **worker agent** (NexAU) — does the benchmark task (`qea/worker/`, `qea/worker_gdpval/`).
- **evolve agent** (NexAU, **Phase 4, not built yet**) — edits the worker DIRECTORY's
  files (prompt/tools/skills) via file-edit tools; the AHE `agents/evolve_agent` analog.
- **loop** (`qea/loop.py`, deterministic code) — runs worker→score, feeds results to the
  evolve agent, it edits the dir, loop re-runs worker → keep/rollback. keep/rollback +
  fair scoring + budget stay in CODE, not inside an agent.

The current QEA evolve agent (`qea/agents.py` `evolve_agent_propose`) is **text-only**
(single LLM call → JSON slot-edit, Level A) and is NOT a NexAU agent. Spike
`scripts/nexau_edit_spike.py` confirms a NexAU agent CAN edit a harness file in place →
Phase 4 = make the evolve agent a file-editing NexAU agent (Level B) + weaken the seed.
NexAU supports sub-agents, so evolve COULD run worker nested — but don't; siblings + a
code loop is cleaner (AHE pattern).

## Out of scope (now)
- The actual evolution *experiments* (just stand up the loop + measure headroom).
- Porting the old `--mock` synthetic A-pile fixture to NexAU (evolution-side; leave on the current path until Phase 4 needs it).
