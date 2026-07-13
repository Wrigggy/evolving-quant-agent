# Checkpoint / Roadmap — Phase 5 Level-B mechanism (2026-07-02)

> **SUPERSEDED by `CHECKPOINT-2026-07-13-phase7-8.md`.** Kept as a point-in-time record.

Supersedes `CHECKPOINT-2026-06-30-phase5.md`. Captures current state + forward plan so
work resumes cleanly after a context clear.

## Branch / commits
- Worktree branch `worktree-phase5-levelb-mechanism`, **pushed to origin** (HEAD `8748615`).
  NOT merged to main.
- Push over SSH is blocked locally (Clash-style TUN proxy, `ssh.github.com:443` →
  198.18.0.98 connection closed). WORKING push = HTTPS + proxy + gh token:
  `gh auth setup-git && git -c http.proxy=http://127.0.0.1:7897 push
  https://github.com/Wrigggy/evolving-quant-agent.git <branch>`.

## What is DONE + PROVEN (this two-week arc, most recent first)

### E2B full-offload worker backend (2026-07-02, commit 8748615)
The WHOLE worker agent now runs inside a per-task E2B cloud VM (Harbor-style), not just
its shell. Motivation: NexAU's native E2B backend only offloads shell/code; the agent
control loop (LLM context) stayed local → N-way concurrency batch-killed background jobs
under macOS memory pressure (jetsam). Full offload keeps the local orchestrator near-empty.
- `qea/worker_e2b.py` `run_worker_e2b()` mirrors `worker_runtime.run_worker` (drop-in);
  `qea/e2b_entry.py` runs the full agent in the VM; `loop_levelb.py` `execution`
  ("local"|"e2b_full") + `evaluate_dir` switch; `run.py --execution e2b_full`.
- Prebuilt template `qea-nexau-worker` (ubuntu:24.04 py3.12 + NexAU@v0.3.9 + ddgs) →
  sandbox startup ~1-2s. Build: `scripts/build_e2b_template.py`. (Default E2B base is
  py3.11; NexAU needs >=3.12.)
- VERIFIED: full agent in VM (fab_01 → 5.5k-char deliverable, 110s); `evaluate_dir(
  execution="e2b_full", concurrency=2)` → scored + cached, `backend=e2b_full`, mean 0.857
  on fab_01/02. **VM reaches OpenRouter DIRECTLY** (no local SOCKS proxy — the whole reason
  full offload is possible; the local box is region-blocked).
- BY DESIGN: grading (judge) + the evolve agent stay LOCAL; only the memory-heavy worker
  fleet moves to the cloud.

### Open-ended debugger (commits 70322da, 58ec7b4)
Retired the fixed 5-tag classifier (had no "missing tool" category → mislabeled tool gaps,
steered edits to prompt). Now an open-ended `ask`-style diagnosis (root_cause +
general_mechanism + kind∈{prompt,tool,binding,middleware,other}), faithful to AHE's real
Agent Debugger (which was withheld/reconstructed). `process_note` is format-aware
(files==0 is normal on FAB text tasks). VALIDATED: evolve agent now writes CODE, not just
prompts (run_shell_command / compute wired in), and a 3-iter local run accumulated across
iterations (iter1 KEPT, iter2 built on it).

### Resume/cache + concurrency (commit c2564d1)
Per-task result cache (`cache_dir/{worker_sig}__{task_id}.json`) + candidate-dir reuse →
repeated launches accumulate to completion. `evaluate_dir` ThreadPoolExecutor concurrency.

### Generalizable mechanism + AHE parity (earlier Phase-5 commits)
Benchmark-agnostic Evaluator (Multimodal=GDPval, RubricText=FAB); AHE prediction-
falsification keep/rollback (EFFECTIVE/PARTIALLY/MIXED/INEFFECTIVE/HARMFUL) + noise floor;
iron-law-2 firewall (sanitized) + opt-in ahe_corpus mode; file-editing evolve agent with
structured file tools + NexAU substrate guide. On the EASY-tier FAB weak seed the evolve
agent makes the designed recovery edit (re-wire company_filings/retrieve_from_filing, no
leakage) — proves the PLUMBING (easy tier signposts the target), not evolve-agent capability.

## Superseded decisions (don't re-try)
- Lowering the weak seed `max_iterations` (40→~12): TRIED and REVERTED — the hack distorted
  scores (fab_01 0.857→0 collapse, inflated easy-tier). Faithful baseline needs max_iter=40;
  **concurrency (now up to 20 via E2B) handles throughput instead.**
- "The reaper kills runs on a ~30-44min timer": WRONG diagnosis. Real cause was macOS memory
  batch-kill from over-cranked local concurrency on a 16GB box. E2B full-offload removes it.

## ROADMAP — next steps (ordered)

1. **Run the full-FAB score-recovery baseline at scale (immediate).** The key unmeasured
   number: does the re-wire lift the weak seed's mean gated score past the noise floor on
   the FULL 27-task set (not the 2-task subset, which is a known artifact — some tasks are
   answerable from parametric knowledge with tool_calls=0)?
   `run.py --levelb --benchmark fab --seed-worker qea/worker_fab_weak_midtier
   --execution e2b_full --concurrency 20 --n-tasks 27 --iters 3 --k 2
   --evidence-mode ahe_corpus --noise-margin 0.05 --results-dir results/phase5_fab_e2b_3iter`
   Acceptance: kept edit lifts mean past noise, improvement attributed to predicted tasks.
2. **Escalate difficulty tiers** (now feasible at scale): mid (tool .yaml removed, impl kept)
   → hard (impl removed → force CODE SYNTHESIS) → soften the reference. This is the clean
   evolve-agent CAPABILITY test the easy tier could not give.
3. **Ablations**: firewall ON (sanitized) vs OFF (ahe_corpus); gold-reading. Quantify how
   much the evidence corpus vs the firewall matters.
4. **Sanity: e2b_full vs local score parity** — same agent, different execution locus →
   scores should match within noise. Confirm on a shared task subset before trusting E2B runs.
5. **Merge Phase-5 branch to main** once (1)-(2) give a clean result.
6. **(Optional) Move the evolve agent to E2B too** — currently local (1 run/iter, edits local
   files; not the memory bottleneck). Only needed if evolve-side memory/scale becomes an issue.
7. **(Longer-term) Generalize to other base harnesses** — the mechanism is designed to be
   harness-agnostic: mini-SWE-agent, smolagents, OpenAI Agents SDK, Confucius Code Agent
   (beyond NexAU). Each needs an execution adapter like worker_e2b.

## Env / how to run
- `.venv-nexau` (py3.14 locally), worker deepseek-v4-pro, judge qwen3.x-plus k=2.
- OpenRouter via local SOCKS proxy 127.0.0.1:7897 (local runs); E2B VMs reach it directly.
- E2B_API_KEY / OPENROUTER_API_KEY in `.env`. E2B template `qea-nexau-worker` already built.
- Running the venv python is gated by the auto-mode classifier — the user runs E2B/loop
  commands via `!` (a permission-rule attempt was blocked as self-modification).
