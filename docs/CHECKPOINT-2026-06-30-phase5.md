# Checkpoint — Phase 5 generalizable Level-B mechanism (2026-06-30)

> **SUPERSEDED by `CHECKPOINT-2026-07-02-phase5.md`.** Kept as a point-in-time record.
> Since this was written: open-ended debugger landed, the max_iterations lowering was
> tried and REVERTED, and the E2B full-offload worker backend was added (solves the
> throughput/memory problem this checkpoint's "pending optimizations" were chasing).

Paused mid-run. This captures state so work can resume cleanly.

## Branch / commits
- Worktree branch: `worktree-phase5-levelb-mechanism` (NOT merged to main).
- Commits (in order): spec → feat(loop+evaluator+prediction-falsify) → feat(AHE-parity:
  reference+evidence corpus) → fix(timeout+trace-enum) → fix(provider-pin) →
  fix(absolute work_dir + structured file tools) → docs(roadmap difficulty tiers).
  HEAD around `0a6be4c`.

## What is PROVEN (end-to-end, evolve side)
The generalizable Level-B mechanism + AHE-parity evolve agent runs end-to-end and makes
the designed FAB recovery edit. On the EASY-tier FAB weak seed, the evolve agent:
- correctly diagnoses `MissingRetrievalCapability` from the firewall-off evidence corpus,
- re-wires the unbound `company_filings` + `retrieve_from_filing` tools into `agent.yaml`
  (impl + descriptions were left in the dir; only bindings were removed),
- rewrites systemprompt.md into a 4-step retrieval flow, improves tool descriptions,
- emits a correct prediction (`predicted_fixes: [fab_00, fab_08]`), no answer leakage.

Caveat (recorded in ROADMAP 1c): the EASY tier signposts the recovery target (leftover
descriptions + the reference names the re-wire move), so this proves the PLUMBING, not
evolve-agent capability.

## Where the run stopped
`results/phase5_fab_loop/` (n_tasks=2 [fab_00, fab_01], iters=1, ahe_corpus):
- DONE: seed eval + seed_noise eval for both tasks (`seed/`, `seed_noise/` traces present).
- NOT DONE: the evolve-agent edit + candidate eval + keep/rollback verdict. So the
  score-RECOVERY number (does the re-wire lift 0.388→toward 0.618 past the noise floor)
  is NOT yet measured.

## Why it was slow (not a bug — throughput)
Each weak-FAB worker run flails to `max_iterations: 40` (~10–17 min) because without
retrieval tools it loops on fetch_page. The noise floor runs the slow seed TWICE, and
`evaluate_dir` is sequential → ~80 min for n_tasks=2/iters=1.

## Pending optimizations before the next run (throughput only, not mechanism)
1. Lower the weak seed `max_iterations` (40 → ~12): it collapses regardless; bounds the
   flail time. (Only the weak seed; candidate with retrieval is already fast.)
2. Make the noise floor a cheap fixed margin (≈0.05) instead of a second full eval.
3. Add concurrency to `evaluate_dir` (ThreadPoolExecutor; base FAB used conc=4).

## How to resume
- Apply the 3 optimizations, then: `run.py --levelb --benchmark fab --evidence-mode
  ahe_corpus --n-tasks 2 --iters 1 --results-dir results/phase5_fab_loop`.
- Acceptance: the kept edit lifts the mean gated score past the noise floor with the
  improvement attributed to the predicted tasks (EFFECTIVE/PARTIALLY_EFFECTIVE).

## Fixed infra gotchas this session (durable)
- NexAU agents need provider pinning via `extra_body.provider` (LLMConfig has no field;
  inject through `extra_params` → `to_openai_params`) — else OpenRouter routes to flaky
  providers returning empty completions.
- `work_dir` MUST be absolute — the sandbox shell/file tools resolve relative to it from
  a different base cwd; a relative work_dir → "File not found" on every read/edit.
- A weak executor (deepseek) needs STRUCTURED file tools (read_file/write_file/replace),
  not shell heredocs, to land multi-line edits.
- FAB workers needed `llm_config.timeout: 180` (connect-timeout gotcha).
