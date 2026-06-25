# Phase 4 — Level-B evolve loop (NexAU substrate) — standup results

The loop now runs the REAL NexAU worker dir (not the retired single-completion over
the 7-slot abstraction) and grades with the SAME `MultimodalJudge` as the base test.
Branch `qea/phase4-levelb`. Worker model `deepseek/deepseek-v4-pro`, judge
`qwen/qwen3.7-plus`, k=2.

## What is validated (the loop works end-to-end)

The gated real-API smoke test (`QEA_LEVELB_SMOKE=1`,
`tests/test_levelb.py::test_levelb_smoke_one_task_one_iter`) **passed**: one real
GDPval task, one iteration, exercising the full pipeline against real NexAU agents —
weak worker → render → multimodal grade → firewalled debugger (verdicts + trace) →
file-editing evolve agent edits a snapshot of the worker dir → re-grade →
`decide_keep_soft` keep/rollback → persisted `iter_001/manifest.json` + `edit.diff`.
4 real agent runs, ~49 min wall-clock.

So the **substrate is unified and the Level-B mechanism is plumbed**: the thing we
evolve is now the same NexAU worker dir we base-tested, and an agent edits its actual
files. keep/rollback, the noise-floor gate, the leakage guard, and the rejected-edit
buffer all live in `qea/loop_levelb.py` (deterministic); the evolve agent reads only
the answer-free sanitized diagnosis and decides nothing.

## Headroom measurement — NEGATIVE result (the weakening did not create a gap)

Weak seed (`qea/worker_gdpval_weak/`, minimal one-line prompt, bare shell tool) over
the first 5 GDPval tasks (all Accountants & Auditors — `tasks[:5]` is one occupation
block), k=2:

| task | weak-seed mm | full-worker mm (NexAU base) |
|---|---|---|
| 83d10b06 | 0.810 | 0.611 |
| 7b08cd4d | 0.831 | 0.843 |
| 7d7fc9a7 | 0.958 | 1.000 |
| 43dc9778 | 0.512 | 0.000 |
| ee09d943 | 0.602 | 0.568 |
| **mean** | **0.743** | **0.604** |

**The weakened seed scored HIGHER than the full worker (0.743 vs 0.604), not lower.**
Prompt-stripping did not bottleneck the worker. Two reasons visible in the traces:
- **deepseek-v4-pro is process-sufficient with a one-line prompt** on these tasks —
  the full worker's finish-guidance / per-extension hints were not load-bearing.
- On the hard 16-PDF task `43dc9778` the *full* worker abandoned in ~4 turns (base
  score 0.000), while the *weak* seed pushed to 47 turns and produced a file (0.512).
  Removing the guidance did not remove capability; if anything it removed a premature
  stop.

This is the [four-iron-laws law 1](../README.md) headroom condition failing to hold:
a strong base model on these tasks is **capability-sufficient, not process-limited**,
so there is no harness headroom for the evolve loop to recover. It echoes the prior
findings ([[project_ahe_deepseek_repro]]: evolve-agent strength is the bottleneck;
[[project_qea_fab_v2_base]]: strong base → no process headroom). The plan explicitly
anticipated this ("if the weak seed scores ~full, the weakening was insufficient").

### Caveats
- The 5 tasks are a single occupation (AA — the full worker's *worst*, 0.604), not a
  stratified sample, so 0.743 is NOT comparable to the full worker's overall 0.797.
- Judge noise is real (k=2); differences inside ~±0.05 are not meaningful.
- 2 of the 5 tasks hit transient `deepseek` "empty model response" (reasoning_tokens=1)
  blips, absorbed by NexAU's retry; both still scored.

## Full-30 weak-vs-full + deliverable-format gate (update 2026-06-25)

Ran the weak seed across the full 30 tasks (`scripts/nexau_gdpval_run.py` with
`QEA_WORKER_DIR=qea/worker_gdpval_weak`, conc 4) and applied a post-hoc
**deliverable-format gate** (`scripts/format_gate_analysis.py`): each task's required
format = its GDPval **gold deliverable extension**; a task whose gold is text requires
no file; `gated_mm` = `content_mm` if the worker produced a file of the required type,
else 0.

| run | content mean | format-gated mean | format misses |
|---|---|---|---|
| full worker (`qea/worker_gdpval/`) | 0.797 | 0.772 | 2 (`43dc9778` .pdf, `c7d83f01` .ipynb — both no-file) |
| weak seed (`qea/worker_gdpval_weak/`) | 0.791 | 0.771 | 1 (`c7d83f01` .ipynb — no-file) |

**Finding 1 — headroom still absent on the representative set.** On the full 30, weak ≈
full on both content (0.791 vs 0.797) and gated (0.771 vs 0.772) — a tie inside judge
noise. The earlier "weak 0.743 > full 0.604" was a **5-AA subset artifact** (AA is the
full worker's worst occupation + the `43dc9778` abandonment). Confirms the headroom
premise fails: a one-line-prompt weak seed is as good as the full worker; deepseek-v4-pro
is process-sufficient, prompt guidance is not the bottleneck.

**Finding 2 — the format gate is well-defined but immaterial for these workers.** It only
moves each run by ~−0.02, because both workers produce the correct file type on 29/30.
The 5-AA "text-answer beats Excel-gold" effect did NOT generalize (weak's `7b08cd4d` this
run produced a real `.xlsx`, 0.871). The only *systematic* miss is `c7d83f01` (gold
`.ipynb`): neither worker can emit a Jupyter notebook (the worker prompt/tooling never
mentions it) — a genuine capability gap, fairly gated to 0 for both.

Format-miss breakdown (why the gate doesn't separate them — both barely miss):

| worker | format OK | misses | detail |
|---|---|---|---|
| full | 28/30 | 2 | `c7d83f01` .ipynb no-file (0.755→0) + `43dc9778` .pdf no-file (already 0.000, no effect) |
| weak | 29/30 | 1 | `c7d83f01` .ipynb no-file (0.585→0) |

Note: there were **zero "wrong container" cases** (right file, wrong type) for either worker
— every miss was "produced no file when one was required," and both runs' real point loss
is dominated by the *same* shared `.ipynb` task. The gate is a near-equal translation on
both (full −0.025, weak −0.020), so it can't separate them; on the format dimension weak is
not worse than full (fewer misses). Worker output format is somewhat stochastic across runs
(the 5-AA `7b08cd4d` text answer vs the 30-run `.xlsx`), but over 30 tasks both reliably
emit files.

Implication: the gate is the right *semantics* but is **not** the lever that creates
Level-B headroom. The headroom work (cap iterations / narrow the tool / select tasks the
base worker genuinely cannot do, e.g. `.ipynb`) still stands.

**ADOPTED (baked in):** the deliverable-format gate is now the **canonical Level-B score**
(`qea/grading/format_gate.py`, applied in `qea/loop_levelb.py:evaluate_dir`): the score
driving keep/rollback + the debugger's oos is `gated_mm` (0 on a gold-format miss); the raw
`content_mm` is kept in the trace for the firewalled debugger's diagnosis (so "content good,
format wrong" stays distinguishable). Required format = `task.deliverable_exts` (the gold
deliverable extension(s), populated by the GDPval loader; empty = text deliverable, no file
required). The base-test script still reports `content_mm`; use `scripts/format_gate_analysis.py`
for its gated view.

## Conclusion + next steps (deliberately NOT run here)

The Level-B loop is built and proven; what is missing is a real headroom gap to
evolve against. A 3-task × 2-iter evolution run was **not** executed — with no
headroom it would only measure judge noise, at ~2.5 hrs of agent time. Before any
evolution experiment:

1. **Create genuine headroom**, not by trimming prompt prose but by a capability
   constraint the evolve agent can plausibly recover: e.g. cap `max_iterations` low,
   remove the shell tool's code-execution affordance (force the worker to (re)discover
   how to build files), or select process-limited tasks (multi-file inputs where the
   full worker already degrades, e.g. `43dc9778`).
2. **Re-measure** weak vs full on a stratified sample (≥1 per occupation) so the gap
   is comparable to 0.797.
3. **Add concurrency to `evaluate_dir`** (currently sequential; ~12 min/worker run →
   multi-task/iter runs are hours). Mirror the `ThreadPoolExecutor` in
   `scripts/nexau_gdpval_run.py`.

## Engineering notes
- **401 fix:** the NexAU `agent.yaml` resolves `${env.LLM_API_KEY}` at config load;
  the Level-B path never mapped `OPENROUTER_API_KEY → LLM_API_KEY`. Fixed via
  `qea/worker_runtime.py:ensure_nexau_llm_env()` (caught by the smoke test).
- **Cost/latency:** ~12 min per worker agent run dominates wall-clock; the judge +
  evolve agent are comparatively cheap.
