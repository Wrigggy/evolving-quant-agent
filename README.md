# QEA v0 — Evolving Quant Agent

A **primitive but runnable** v0 of an evolutionary harness agent for quant/finance
work. It reuses the `evolve -> falsify -> rollback` loop from a reproduced
[Agentic Harness Engineering (AHE)](https://arxiv.org/abs/2604.25850) codebase,
but swaps the component layer to quant semantics and drives evolution on the
**GDPval finance/accounting** task set under a **soft rubric-percentage gate**.

v0 is a **mechanism check, not a performance run.** Success is not a high score —
it is that the closed loop demonstrably works (see [Acceptance](#acceptance)).

## TL;DR

```bash
# Offline synthetic plumbing fixture — no API key, no third-party packages, ~0.1s.
python3 run.py --mock

# Tests (needs pytest).
python3 -m pytest

# Real run on OpenRouter (deepseek-v4-pro). Needs .env (see .env.example).
pip install -e ".[real,gdpval]"
cp .env.example .env   # then set OPENROUTER_API_KEY
python3 run.py --real
```

**Two run modes:**
- `--mock` — offline **synthetic plumbing fixture**: scripted edits over a small
  deterministic synthetic task set exercise the full evolve→falsify→rollback loop.
  No API key. Makes **no headroom claim** — purpose is to confirm mechanism signals
  (causal connectivity, monotonic progress, correct rollback, buffer block) offline.
- `--real` — evolve **directly on the ~30 original GDPval finance/accounting tasks**
  (Accountants/Auditors, Financial Managers, Investment Analysts, Financial
  Advisors, Securities Sales, Real Estate Brokers), gated by the **soft rubric-score
  gate** (`decide_keep_soft`): keep a candidate only if its mean rubric % beats the
  incumbent's by more than the estimated eval noise floor. Progress is tracked as
  the mean rubric score trajectory. There is no hard verifier for open-ended GDPval
  deliverables, so the loop is driven by a soft signal (the old "hard-verifier-only"
  constraint is dropped). The current law 2 — the observation firewall — still holds
  unconditionally here (see the four iron laws below).

## What it does

The task family is the **GDPval finance/accounting** set ("Finance and Insurance"
sector): accountants/auditors, financial managers, investment analysts, advisors,
securities sales. All tasks are the original open-ended B-pile deliverable tasks —
graded against the `rubric_json` per criterion — scored as a **continuous rubric
percentage** (earned/total points), with no `{0, 0.5, 1}` quantization.

> The GDPval rubric score is a lower bound vs. OpenAI's official pairwise-vs-gold
> method (GPT-5-high, multimodal, file-level) — format/layout criteria can fail for
> text-only deliverables, and the official grader has no public API. See ROADMAP.

### The local GDPval fork

`data/gdpval/` is a pinned snapshot of the `openai/gdpval` gold set (v2: prompts +
`rubric_json`/`rubric_pretty` + human deliverable URLs), created by
`python scripts/fork_gdpval.py` (SHA256 provenance in `data/gdpval/MANIFEST.md`).
Loaders read the snapshot first and fall back to the network only when it is
missing. `scripts/fork_gdpval.py --push <user>/<repo>` mirrors the fork to your
Hugging Face account (needs `HF_TOKEN`).

## The four iron laws (design principles)

1. **Headroom.** The task must sit in the "harness is the real bottleneck" regime
   (process-limited, not capability-limited). Tasks where a strong base model is
   already capability-sufficient produce no signal — the evolved harness cannot
   improve. A minimal **synthetic fixture** is kept for offline `--mock` only
   (mechanism check, no headroom claim).
2. **Observation-firewall law.** The driving signal may be soft, but ground truth
   (rubric verdicts, gold deliverables, reference answers) flows **only into
   diagnosis**, never to the proposer or encoded into a harness component. The
   B-pile debugger enforces this firewall: it sees rubric verdicts and Critic notes
   internally, but emits only a **sanitized component-level payload** to the
   proposer. The leakage guard enforces it at the evaluator layer (edit content
   audited against the benchmark's `answer_corpus` before it is applied).
3. **Task-aware denoising.** Edits are evaluated k times (`--k`, default 2).
   Deliverables are cached per (task, harness-signature) to prevent regeneration
   noise from masking real signal. The noise floor is estimated from two fresh
   same-harness evals; a candidate must clear that margin to be kept.
4. **No single aggregate metric.** Score is recorded **per occupation/subtype**
   (per-task in `eval.json`). An edit that regresses any unpredicted subtype is
   visible in the per-occupation table and subject to the verdict taxonomy — so
   "lift one occupation, regress another" is both visible and not auto-kept.

## Architecture map

```
Benchmark (owns: tasks, grader, answer_corpus, debugger_kind)
  GDPval benchmark --> router --> SoftJudge grader (rubric %, per-criterion verdicts)
  Synthetic fixture (--mock only) --> HardVerifier (+ perturbation probe)

seed harness (7 slots, only `tool` filled)
┌───────────────────────────────────────────────────────────┐
│ tool*  middleware  skill  prompt  validator  memory  router │   *seed = one code_exec tool
└───────────────────────────────────────────────────────────┘
      │
      ▼  each iteration:
evaluate (rubric %, k-repeat, deliverable cache)
      -> B-pile debugger: rubric verdicts + Critic (answer-free) -> sanitized diagnosis
      -> evolve_agent proposes ONE edit (budget L_t=1)
      -> leakage guard: edit content vs answer_corpus? over threshold -> LEAKAGE_BLOCKED
      -> rejected-edit buffer blocks repeats?  ──yes──> skip
      -> apply to a clone -> re-evaluate -> falsify (verdict audit trail)
      -> soft gate (decide_keep_soft): mean rubric % > incumbent + noise_margin? -> keep or ROLLBACK + buffer
      -> persist 3 layers: eval.json / change_manifest.json / workspace.json
```

### Three-layer architecture

| Layer | Responsibility | Owner |
|---|---|---|
| **grader** | `(task, deliverable) → absolute rubric %` + per-criterion verdicts | the **Benchmark** (`SoftJudge` / `HardVerifier`) |
| **evaluator** | grader scores → keep/rollback (`decide_keep_soft`); leakage guard; verdict taxonomy | the **loop** (pure logic, no model) |
| **loop** | evolve → propose → leakage-check → apply → grade → evaluate; persist; checkpoint | benchmark-agnostic |

The grader measures; the evaluator decides. The loop does not know how a benchmark
scores — it asks the benchmark's grader for a number and hands it to the evaluator.

### Seven slots (NexAU-style)

Five inherited from AHE (`tool / middleware / skill / prompt / memory`) plus two
quant-native:
- **`validator`** — the integrity guard. In the synthetic fixture this is realized
  as a **perturbation probe** inside the `HardVerifier`: a hardcoded constant
  passes the base inputs but fails on perturbed inputs. (Probing is the
  grader-intrinsic anti-hardcode defense for parametric benchmarks; the leakage
  guard covers GDPval where there are no parameters to perturb.)
- **`router`** — classifies a task to its benchmark and routes to the right
  (grader, debugger) pair.

**Minimal seed** (attribution purity): only the `tool` slot is filled (one
code-execution sandbox); the other six are empty, so every component the
evolve-agent adds must earn its place via measured rubric-score delta.

### Falsification

Reuses the AHE verdict taxonomy
(`EFFECTIVE / PARTIALLY_EFFECTIVE / MIXED / INEFFECTIVE / HARMFUL`) as an
audit trail. v0 ports three mechanisms from
[SkillOpt](https://arxiv.org/abs/2605.23904) (MIT):
- **rejected-edit buffer** — rolled-back edits are remembered (signature match,
  no semantic dedup) so the proposer cannot re-propose them;
- **`LEAKAGE_BLOCKED`** — a distinct verdict recorded when the leakage guard fires
  pre-apply; the edit is buffered so it cannot be re-proposed;
- **edit budget** `L_t = 1` per iteration.

> Note: v0 deliberately has **no selection split** (a deferred SkillOpt
> mechanism). The OOS anti-overfit signal for the synthetic fixture is the
> **perturbation probe** (held-out parameter space); for GDPval the observation
> firewall + leakage guard take this role. See ROADMAP for the selection-split +
> regime-split return.

### B-pile debugger

The `qea/debugger.py` B-pile debugger runs between the grader and the proposer,
behind an information firewall:

1. **Observation (sees ground truth):** per-criterion rubric verdicts wired from
   the grader + a **Critic** LLM call per failing task that reads the failed
   criteria and produces an **answer-free deficiency note** ("missing the
   depreciation schedule the rubric requires" — never a specific value).
2. **Attribution:** the diagnose-LLM classifies critic notes into a B-pile tag
   vocabulary (`MissingDomainKnowledge / WrongStructure / FormatGap /
   OccupationMismatch / CalcError`), each carrying a documented slot affinity
   that guides but does not force the proposer. Free-LLM mode (for rewrite-level
   changes) names the target slot directly.
3. **Firewall exit:** `diagnose()` emits only a **sanitized payload** to the
   proposer: `{root_cause_tag, deficiency_category, suggested_target_slot,
   predicted_fix_task_ids}`. The evolve_agent never receives raw rubric verdicts,
   gold text, or any answer value.

### Leakage guard (universal evaluator-layer anti-cheat)

`LeakageGuard` (`qea/verifier.py`) audits each proposed edit's content against
the benchmark's `answer_corpus` (n-gram/substring overlap) **before it is applied**.
Over a configurable threshold → `LEAKAGE_BLOCKED`.

- GDPval `answer_corpus` (v1) = rubric-criteria text. Gold-deliverable text is
  deferred (GDPval gold is binary xlsx/pptx URLs; text extraction needs
  fetch + Office parsing — see ROADMAP).
- Synthetic fixture `answer_corpus` = the numeric reference answers.
- Threshold is an untuned placeholder (TBD — see ROADMAP).

**Two-line anti-hardcode defense:**

| Defense | Layer | Catches |
|---|---|---|
| perturbation probe | grader (score-intrinsic) | hardcoded constant → probe score drops; for parametric/synthetic benchmarks |
| leakage guard | evaluator (audits edit content) | component embeds answer material; covers all benchmarks, the only content-level defense on GDPval |

### Benchmark abstraction

`qea/benchmark.py` introduces `Benchmark = {name, tasks, grader, answer_corpus,
debugger_kind}`. The router selects the (grader, debugger) pair per benchmark.

- **GDPval benchmark** (the only real benchmark): `SoftJudge` grader (continuous
  rubric %, per-criterion verdicts), `answer_corpus` = rubric-criteria text (v1).
  `debugger_kind = "b_pile"`.
- **Synthetic fixture** (`--mock` only): `HardVerifier` grader (perturbation
  probe), `answer_corpus` = numeric reference answers. `debugger_kind =
  "synthetic"`. Not a real benchmark; makes no headroom claim.

The A-pile (numeric tasks: option pricing, amortization, NPV/IRR) was found
capability-sufficient for strong models — no process headroom — and has been
**removed as a benchmark**. It survives only inside the synthetic fixture for the
offline `--mock` plumbing test.

### Worker deliverable cache

`_DeliverableCache` (keyed by `(task_id, harness_signature)`) ensures the same
harness always produces the same deliverable text within a run, eliminating
regeneration noise from the rubric-score comparisons.

## Acceptance

Mechanism-level (not absolute score). The offline `--mock` run and
`tests/test_smoke.py` assert all four signals on the **synthetic fixture**:

1. **Causal connectivity** — the same root cause is traceable across
   EVAL → DIAGNOSE → WORKSPACE → VERDICT (iter-1 Hardcoding tag → EFFECTIVE
   verdict → `integrity_guard` slot added).
2. **OOS monotonic rise** — the selected subtype's OOS rises (non-decreasing
   trajectory, strict rise at least once; seed starts at 0).
3. **Correct rollback** — falsification rolls back a harmful edit (broke
   `code_exec`) and an overfit edit (memorized base, killed by the perturbation
   probe), and the buffer blocks a re-proposed edit.
4. **Capability wall unfixed** — the capability-wall subtype (amortization wall)
   remains unsolved by the evolved harness (iron law 1 visible per-subtype).

The `--real` outcome is reported as a soft-headroom observation (mean rubric score
trajectory), not a mechanism assertion.

## Layout

```
qea/
  loop.py          evolve->falsify->rollback driver: run_gdpval_soft + run_synthetic_fixture + acceptance_signals
  benchmark.py     Benchmark abstraction: gdpval_benchmark / synthetic_fixture_benchmark
  harness.py       7-slot Harness, minimal seed, Component/Edit, clone/apply/rollback
  falsify.py       verdict engine (evaluate_changes) + decide_keep_soft + LEAKAGE_BLOCKED + rejected-edit buffer
  verifier.py      SoftJudge (rubric %, continuous, per-criterion verdicts) + HardVerifier (probe) + LeakageGuard
  debugger.py      B-pile debugger: Critic + attribution + firewall -> SanitizedDiagnosis
  tasks.py         load_gdpval_finance() / load_gdpval_a_pile() (fixture only) + rubric_corpus + reference fns
  agents.py        quant_agent + evolve_agent (scripted mock) + diagnose (B-pile branch + firewall)
  llm.py           OpenRouter client (provider pin / backoff) + MockLLM
  observability.py three-layer persistence
run.py             CLI entry (--mock / --real)
tests/test_smoke.py
ROADMAP.md         next steps, explicitly NOT-in-v0
```
