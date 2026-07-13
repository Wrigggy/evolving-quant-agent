# CHECKPOINT 2026-07-13 — phase 7/8: protocol v2, benchmark expansion, dual-gate legs

Supersedes `CHECKPOINT-2026-07-02-phase5.md`. Captures state + forward plan after the
protocol-v2 arc (2026-07-10..13). All commits pushed on `worktree-phase5-levelb-mechanism`
(28ad90c..3636ae5, ~25 commits this arc).

## Where we are

**Thesis (user-set)**: a GENERAL evolve agent + a base worker -> task-specialized
worker. Edge = automated harness engineering for long-tail workflows (not absolute
scores vs Cowork/GPT-Work); headline metrics are mechanism-level (delta per
iteration, cross-benchmark consistency, weak-model+evolved-harness cost trade).

**Protocol v2 (all landed, all live-validated)**:
- `--n-samples N` per-task worker sampling (variance reduction; measured per-task
  repeat sd up to 0.29 on GDPval, 0<->1 flips on SSB)
- `--keep-rule paired` bootstrap gate + `--stability-lambda` (kills noise-driven
  keeps; live-killed a 0.7-sigma keep)
- `--confirm-tasks N` held-out CONFIRM gate at promote time (Regimes-style;
  live-killed an overfit keep: pool +0.056, held-out -0.074)
- `--task-ids` hand-picked optimize pools; `--confirm-band`; multi-leg
  `--prior-history-dir a,b,c`
- Attempt archive with BEHAVIORAL autopsies: per hurt/helped task tool-call
  histograms + turns/errors, confirm-gate outcomes with worst-collapse behavior,
  full prior diffs — inherited across legs (7484e05)
- Grader rationales: `judge_reasons.json` per eval (human debug only, firewalled)

**Benchmarks integrated** (qea/bench_*.py, `make_benchmark` names):
- `ssb`/`ssb_912`/`ssb_verified`: SpreadsheetBench — 2726/394 case-tasks, official
  checker = DETERMINISTIC binary (zero judge noise). Data at data/spreadsheetbench/.
- `dsbench`: 466 ModelOff finance questions, deterministic letter/numeric match +
  official LLM-judge fallback. Split by whole competitions. data/dsbench/.
- `apex_ib`: 160 IB tasks/10 worlds, rubric judge reused; worlds stage in-VM via
  `vm_setup_cmd` HF download (eval-only license — never in a training corpus).
- `gdpval_all`: 205 renderable tasks (12 unrenderable + 3 heavy-ref excluded),
  all reference files local (1.5GB).
- Generic seed: `qea/worker_base_generic` (one-line prompt, no domain words).

## Key results this arc

1. **GDPval train gains do NOT transfer at small scale**: r3-final train +0.16 ->
   held-out (2x22, repeat-averaged) pooled +0.010 (0.1 sigma, sign p=1.0). Exactly
   reproduces the Regimes in-sample->held-out collapse. Eval noise decomposition:
   worker stochasticity >> judge noise (0.83<->0.0 flips per task).
2. **ph7 hardcore-18 GDPval leg (dual gates): 0 kept / 5 rolled back, 0.488 flat.**
   iter2 (web_search) = the money case: pool +0.056 passed the paired CI, held-out
   FAIL — the candidate perseverated (63 web_search calls, no deliverable,
   f84ea6ac 0.797->0.0). Under the old soft gate this would have been a FALSE KEEP.
   Weak-model lesson: new tools are perseveration channels, "tool + hard usage
   guard" is the pattern (the agent synthesized exactly that in iter5 after the
   archive gained behavior histograms — still failed the pool CI).
3. **ph8 probes (generic worker)**: SSB 0.533 (14/30 fail), DSBench 0.700 (x2 waves,
   18/60 fail). GDPval hard-40 probe: xlsx-deliverable tasks are THE weak spot
   (mean 0.445); pptx is NOT hard (judge lenient on visuals).
4. **SSB leg1 (28-task pool, seed fair 0.185), through iter2**: iter1 read-plan-
   verify prompt (+0.018 CI<0, ROLLBACK), iter2 synthesized read_workbook tool
   (-0.02, ROLLBACK). Leg STOPPED at user request mid-iter2-replay (r3, pid gone);
   RESUME: relaunch the exact command in tmp/ssb_evolve_leg1_r3.log header —
   everything cached, fast-forwards to iter3.
5. **Bug chain found+fixed (the day's infra story)**: (a) big SSB sheets get dumped
   whole -> 22-32k prompt tokens -> qwen3.5-flash returns EMPTY response
   (finish_reason=unknown) -> NexAU fatal -> deterministic entry crash;
   (b) benign NexAU stderr ("Sandbox is not running") matched the "sandbox"
   transient key -> crashes retried 4x AND infra-masked = invisible to evolution.
   Fixed on the exception path (3636ae5): crashes now classify real, cached, and
   visible. (c) HARMFUL-verdict veto silently overrode the paired gate (344152c).
   (d) E2B concurrent-sandbox budget ~15 on this account: parallel runs' conc must
   sum under it. (e) QEA_E2B_SANDBOX_TIMEOUT=3300 now in .env (55min < 1h cap).

## Forward plan (in order)

1. **Resume SSB leg1** (command above; iters 3-5 will see the empty-response class
   for the first time — expect schema+sample-only reading rules to evolve).
2. DSBench leg: pool = 18 measured failures (waves 1+2), same dual-gate config;
   respect competition-level splits (tmp/ds ids need rebuilding from both waves).
3. Observation-space upgrades (user-brainstormed, prioritized P1 > P2 > P5):
   P1 = give the evolve agent a `run_worker_once <task>` live-reproduction tool
   (edit->run->observe inner loop, firewall-safe, 2-3 calls/iter);
   P2 = WORKER_NOTES.md persistent self-curated notes in the worker dir
   (CLAUDE.md analogue; carries environment facts across legs);
   P5 = no-gold self-checks inside the worker (SSB answer_position non-empty,
   values-not-formulas) — agent already half-invented this in iter1.
4. APEX-IB smoke (needs HF_TOKEN forwarding validated end-to-end).
5. Cross-benchmark headline: same evolve agent, 3 benchmarks, defensible deltas.

## Open questions for the user

- SSB pool difficulty: seed fair 0.185 may be too hard (like GDPval hardcore).
  Consider a mixed pool (failures + mid-scoring tasks) so the CI has gradient.
- Component-level keep (decision (1) successor): serial archive-driven composition
  works (leg3 iter4) but is slow; component-decomposed evaluation is ~3x cost.
- Whether to grow n_samples to 3 on binary benchmarks (0/1 flips need it most).
