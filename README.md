# QEA v0 — Evolving Quant Agent

A **primitive but runnable** v0 of an evolutionary harness agent for quant/finance
work. It reuses the `evolve -> falsify -> rollback` loop from a reproduced
[Agentic Harness Engineering (AHE)](https://arxiv.org/abs/2604.25850) codebase,
but swaps the component layer to quant semantics and drives evolution with a
**deterministic hard verifier** instead of an LLM judge.

v0 is a **mechanism check, not a performance run.** Success is not a high score —
it is that the closed loop demonstrably works (see [Acceptance](#acceptance)).

## TL;DR

```bash
# Offline smoke test — no API key, no third-party packages, ~0.1s.
python3 run.py --mock

# Tests (needs pytest).
python3 -m pytest

# Real run on OpenRouter (deepseek-v4-pro). Needs .env (see .env.example).
pip install -e ".[real,gdpval]"
cp .env.example .env   # then set OPENROUTER_API_KEY
python3 run.py --real --b-n 12
```

**Two run modes:**
- `--mock` — offline **hard-verifier mechanism demo**: a synthetic A-pile (numeric
  tasks with a deterministic verifier + perturbation probe) and scripted edits
  exercise the full evolve→falsify→rollback loop with clean attribution. No API
  key. This is the iron-law-faithful mechanism check.
- `--real` — evolve **directly on the ~30 original GDPval finance/accounting tasks**
  (Accountants/Auditors, Financial Managers, Investment Analysts, Financial
  Advisors, Securities Sales, Real Estate Brokers), gated by the **GDPval-AA
  pairwise grader** (see below): each candidate's deliverables are compared blind
  and pairwise against the incumbent's, ties excluded, and progress is reported as
  win rate / Bradley-Terry Elo vs the frozen seed (anchor 1000). The per-criterion
  `rubric_json` score is kept as a diagnostic. These are open-ended deliverables
  with **no hard verifier**, so the loop is driven by a **soft signal — which
  deliberately relaxes iron law 2** (a chosen tradeoff to evolve on real
  economically-valuable tasks). Treat its "soft headroom" result as indicative,
  not proof.

## What it does

The task family is the **GDPval finance/accounting** set (the "Finance and
Insurance" sector: accountants/auditors, financial managers, investment analysts,
advisors, securities sales). It is split into:

- **A-pile (hard verifier, drives evolution):** numeric tasks with an objective
  core — option pricing, loan amortization, audit/liquidity metrics, NPV/IRR.
  Each ships a deterministic `reference(inputs)` and a **perturbation probe**.
- **B-pile (soft judge, transfer only):** real GDPval deliverable tasks graded
  against the **open `rubric_json`** — the judge decides per-criterion whether the
  deliverable satisfies it, weighted by the criterion points → normalized score.
  Used to measure whether a harness evolved on hard-A transfers to qualitative
  finance work. The grader model is pluggable via `QEA_JUDGE_MODEL`.

  > This is rubric-satisfaction scoring from the **open** GDPval rubric, **not**
  > OpenAI's headline pairwise-vs-human win-rate: that official grader (GPT-5-high,
  > multimodal, pairwise vs the gold human deliverable) ships no public API/code —
  > it was a manual web-form service that does not appear available. Format
  > criteria (e.g. "two PDFs submitted") will fail for a text-only deliverable, so
  > the rubric score is a noisy lower bound. See ROADMAP for the full-fidelity path.

### GDPval-AA pairwise grading (the decision signal in `--real`)

The keep/rollback gate follows the **GDPval-AA protocol** published by
[Artificial Analysis](https://artificialanalysis.ai/methodology/intelligence-benchmarking)
(their GDPval-AA leaderboard, added to the Intelligence Index v4.0):

- Two submissions to the same task are **randomly anonymized as Submission A / B**
  ("to mitigate any model or position bias from the grader") and the judge is asked
  which **better responds to the task** — win / loss / tie (`PairwiseJudge` in
  `qea/verifier.py`).
- **Ties are excluded** from scoring; the aggregate is a **Bradley-Terry rating
  from pairwise win/loss** (AA anchors GPT-5.1 Non-Reasoning at Elo 1000; we anchor
  the **frozen seed harness** at 1000, the 2-player special case).
- In the loop: candidate-vs-incumbent matches decide keep/rollback (win share over
  decided matches must beat 0.5 + a seed-vs-seed null margin); incumbent-vs-seed
  matches give the trajectory (win rate + Elo).

Documented deviations from AA (kept honest, not invented): AA's exact grader
prompt is unpublished (ours reconstructs their one-sentence description); AA's
judge is **Gemini 3.1 Pro Preview** fed reference + submission **files**
multimodally (set `QEA_JUDGE_MODEL="google/gemini-3.1-pro-preview"` to match the
judge; our deliverables are text-only); AA runs a fleet-wide Elo tournament with
balanced + active sampling, while we only ever rate two players per match set.

### The local GDPval fork

`data/gdpval/` is a pinned snapshot of the `openai/gdpval` gold set (v2: prompts +
`rubric_json`/`rubric_pretty` + human deliverable URLs), created by
`python scripts/fork_gdpval.py` (SHA256 provenance in `data/gdpval/MANIFEST.md`).
Loaders read the snapshot first and fall back to the network only when it is
missing. `scripts/fork_gdpval.py --push <user>/<repo>` mirrors the fork to your
Hugging Face account (needs `HF_TOKEN`).

GDPval ships **no deterministic verifier** with any task (grading is
expert/LLM-judge), so the A-pile tasks are authored in code with clean reference
values, each citing a real GDPval `task_id` for lineage (e.g. the $559,377.61
amortization balance, NPV/IRR at WACC=9%, American option pricing). The raw
GDPval dataset is wired only for the soft-judged B-pile (`load_gdpval_b_pile`,
with an offline fixture fallback).

### The 2-arm ablation

- **Arm 1 (iron-law-2 clean):** evolve on A only (hard verifier) → freeze →
  transfer-eval on B.
- **Arm 2 (relaxes iron law 2):** evolve on A+B, with the soft B judge *inside*
  the loop.

The comparison answers: does putting the soft-B signal in the loop help, or just
add falsification noise? (In mock the numbers are illustrative; the real run is
the experiment.)

## The four iron laws (design principles)

1. **Headroom.** The task must sit in the "harness is the real bottleneck" regime
   (process-limited, not capability-limited). The A-pile is fixable by discipline
   (anti-hardcoding); one task is a deliberate **capability wall** the harness can
   never lift, and it stays visible per-subtype (you cannot fake progress on it).
2. **Hard verifier only in the loop.** The `evolve -> falsify -> rollback` chain
   consumes only the deterministic A-pile verifier. The soft judge is for
   transfer eval (Arm 1) — and, only in the explicitly-flagged Arm 2, in the loop
   (which is the thing the ablation measures, not a default).
3. **Task-aware denoising.** Edits are evaluated k times (`--k`, default 2). Hard
   scores are clean (variance ~0); soft scores are repeated and the variance is
   recorded — so "soft signal is noisy in the loop" is measured, not assumed.
4. **No single aggregate metric.** OOS is recorded **per subtype**
   (option_pricing / amortization / audit_metric / valuation), recorded per task
   in `eval.json`. An edit that regresses any unpredicted task is downgraded to
   MIXED/HARMFUL and rejected, and the gate additionally requires strict
   total-OOS improvement — so "lift one subtype, regress another" is both visible
   and not auto-kept.

## Architecture map

```
                         task --> [router] --pile A--> HardVerifier  (+ perturbation probe)
                                          \--pile B--> SoftJudge (LLM, transfer / Arm2 only)
  seed harness (7 slots, only `tool` filled)
  ┌───────────────────────────────────────────────────────────┐
  │ tool*  middleware  skill  prompt  validator  memory  router │   *seed = one code_exec tool
  └───────────────────────────────────────────────────────────┘
        │
        ▼  each iteration:
  evaluate (hard + k-repeat) -> diagnose (ADB-lite root cause)
        -> evolve_agent proposes ONE edit (budget L_t=1)
        -> rejected-edit buffer blocks repeats?  ──yes──> skip
        -> apply to a clone -> re-evaluate -> falsify (verdict)
        -> strict gate: keep (EFFECTIVE/PARTIALLY & strict OOS rise) or ROLLBACK (+ buffer)
        -> persist 3 layers: eval.json / change_manifest.json / workspace.json
```

**Seven slots** (NexAU-style): five inherited from AHE
(`tool / middleware / skill / prompt / memory`) plus two quant-native:
- **`validator`** — the hard verifier / **integrity guard**. In v0 the integrity
  guard is realized as a **perturbation probe** inside the verifier: a hardcoded
  constant passes the base inputs but fails on perturbed inputs. (A look-ahead
  data-access guard for time-series families is stubbed; numeric tasks have no
  time axis. See ROADMAP.)
- **`router`** — classifies a task to its pile and routes to the right verifier.

**Minimal seed** (attribution purity): only the `tool` slot is filled (one
code-execution sandbox); the other six are empty, so every component the
evolve-agent adds must earn its place via measured OOS delta.

**Falsification** reuses the AHE verdict taxonomy
(`EFFECTIVE / PARTIALLY_EFFECTIVE / MIXED / INEFFECTIVE / HARMFUL`) and the
falsifiable change-manifest. v0 ports three mechanisms from
[SkillOpt](https://arxiv.org/abs/2605.23904) (MIT):
- **rejected-edit buffer** — rolled-back edits are remembered (signature match,
  no semantic dedup) so the proposer cannot re-propose them;
- **strict gate** — keep only on strict OOS improvement (ties reject);
- **edit budget** `L_t = 1` per iteration.

> Note: v0 deliberately has **no selection split** (a deferred SkillOpt
> mechanism). The OOS / anti-overfit signal is the **perturbation probe**
> (held-out *parameter* space) plus the B-pile transfer — not a held-out task
> fold. See ROADMAP for the selection-split + regime-split return.

## Acceptance

Mechanism-level (not absolute score). The mock run and `tests/test_smoke.py`
assert all three:

1. **Causal connectivity** — the same root cause is traceable across
   EVAL → DIAGNOSE → WORKSPACE → VERDICT (Case-A audit; see
   `results/latest/<arm>/iteration_001/*.json`).
2. **OOS monotonic rise** — the selected family's OOS rises with iterations
   (headroom; iron law 1).
3. **Correct rollback** — falsification rolls back a harmful edit (broke
   `code_exec`) and an overfit edit (memorized base, killed by the perturbation
   probe), and the buffer blocks a re-proposed edit.

## Layout

```
qea/
  loop.py          evolve->falsify->rollback driver + 2-arm ablation + acceptance_signals
  harness.py       7-slot Harness, minimal seed, Component/Edit, clone/apply/rollback
  falsify.py       ported evaluate_changes verdict engine + diff + strict gate + rejected-edit buffer
  verifier.py      HardVerifier (numeric + perturbation probe) + SoftJudge (LLM) + k-repeat
  tasks.py         load_gdpval_a_pile() / load_gdpval_b_pile() + reference fns + GDPval lineage
  agents.py        quant_agent + evolve_agent (scripted mock) + diagnose (ADB-lite)
  llm.py           OpenRouter client (provider pin / backoff) + MockLLM
  observability.py three-layer persistence
run.py             CLI entry
tests/test_smoke.py
PLAN.md            the design + the four iron laws + reuse map
ROADMAP.md         next steps, explicitly NOT-in-v0
```
