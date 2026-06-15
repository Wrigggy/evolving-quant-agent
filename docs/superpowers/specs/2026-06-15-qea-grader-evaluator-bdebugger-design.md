# QEA — Grader / Evaluator split + B-pile debugger (design)

Date: 2026-06-15
Status: approved design, pre-implementation
Branch: `qea/grader-evaluator-bdebugger`

## 1. Motivation

Two problems in the current loop, found from the GDPval-soft real runs:

1. **The B-pile proposer is flying blind.** `diagnose()` (`agents.py:101`,
   `_diagnose_real`) only reads A-pile semantics (`base_pass / probe_pass /
   error`). For open-ended B deliverables there is no such signal, so the
   evolve_agent "fixes" phantom failures. Evidence: `docs/PARTIAL_RUN_gdpval_soft.md`
   — all 6 of pro's edits were `occupation_*` / formula-guidance edits landing
   within the noise floor (0 kept, flat trajectory). Meanwhile the per-criterion
   rubric verdicts that *would* tell the proposer what is actually wrong are
   **computed and then discarded** inside `SoftJudge._real_sample` (`verifier.py:286`).

2. **"verifier" conflates measurement and decision.** `verifier.py` holds three
   things with mixed responsibilities: `HardVerifier` and `SoftJudge` measure an
   absolute score, but `PairwiseJudge` is *comparative + decision* (it directly
   emits the keep signal and cannot produce an absolute score). This made the
   keep/rollback gate, the absolute benchmark score, and the judging all tangle
   together.

This design fixes both: a clean **grader / evaluator** separation, a
**benchmark-owned** grader, and a real **B-pile debugger** behind an information
firewall.

## 2. Iron laws update

- **Law 2 is removed** and replaced by the **observation-firewall law**:
  > The driving signal may be soft, but ground-truth (rubric verdicts, gold
  > deliverables, reference answers) flows only *into diagnosis*. It must never
  > reach the proposer or be encoded into a harness component.
- Laws 1 (headroom), 3 (k-repeat denoise), 4 (per-subtype, no single aggregate)
  are unchanged.

Rationale: we now evolve primarily on the soft pile, so "hard verifier only in
the loop" (old law 2) no longer holds. The risk it guarded against — a harness
that cheats instead of generalizing — is now guarded by the firewall + the
leakage guard (§7).

## 3. Three-layer architecture

| Layer | Responsibility | Owner | Model |
|---|---|---|---|
| **grader** (was "verifier") | `(task, deliverable) → absolute score` + structured per-criterion verdicts | the **benchmark** | an independent **neutral judge model**, distinct from worker & proposer |
| **evaluator** | take grader scores (incumbent vs candidate) → keep / rollback decision; run the leakage guard; assign the falsification verdict | the **loop** | none — pure logic |
| **loop** | drive evolve → propose → leakage-check → apply → grade → evaluate; persist; checkpoint | benchmark-agnostic | — |

The split is the core idea: **measurement (grader) is decoupled from decision
(evaluator)**. The loop no longer knows how a benchmark scores; it asks the
benchmark's grader for a number and hands it to the evaluator.

## 4. Benchmark abstraction

Introduce a `Benchmark` that owns:

```
Benchmark = { tasks, grader, answer_corpus }
```

- **GDPval benchmark** (the only *real* benchmark): rubric grader (continuous %,
  §5), `answer_corpus` = rubric-criteria text + gold human deliverable text.
- **A-pile is removed.** The original numeric A-pile tasks (option pricing,
  amortization, NPV/IRR) were found capability-sufficient — no process headroom
  (ROADMAP findings) — so they are dropped as a benchmark, along with the 2-arm
  ablation (`run_ablation`) that compared A-only vs A+B (moot once law 2 and the
  A benchmark are gone).
- **A minimal synthetic fixture is kept** purely for the offline `--mock`
  plumbing test — it is *not* a real benchmark and makes no headroom claim; it
  exists to exercise evolve→falsify→rollback→buffer deterministically with no API.

The **router** routes each task to its benchmark's `(grader, debugger)` pair.
With A-pile gone there is one real benchmark today, but the routing abstraction
is forward-looking: new benchmarks will be added later, and the router selects
the grader+debugger per benchmark. (The old "A vs B pile" split is the
single-benchmark special case of this.)

## 5. Grader (GDPval): rubric percentage

Change `SoftJudge._real_sample` (renamed conceptually to the GDPval grader):

- Keep the per-criterion judging (judge decides each `rubric_json` criterion
  pass/fail).
- **Score = `earned / total`** (points-weighted fraction), a continuous
  percentage. **Remove `_quantize_parity`** (the `{0, 0.5, 1}` collapse).
- **Expose the per-criterion verdict dict** on `TaskResult` (a new field), so the
  B-pile debugger can read which criteria failed per occupation. Today this dict
  is computed (`verifier.py:286`) and thrown away.
- The grader uses `role="judge"` → `QEA_JUDGE_MODEL`. Document/default it to a
  **different family** from `QEA_QUANT_AGENT_MODEL` and `QEA_EVOLVE_AGENT_MODEL`
  (the judge A/B report already validated cross-family judging at ~90% agreement).
- The legacy "pass" threshold (`_SOFT_PASS` / parity) survives **only for
  reporting** (the per-occupation pass-rate table), never for the gate.

The `HardVerifier` + perturbation probe survive **only inside the synthetic mock
fixture** (offline plumbing test); there is no real A-pile benchmark. The probe
remains documented as a grader-intrinsic anti-hardcode capability that future
*parametric* benchmarks can revive.

## 6. Evaluator: keep/rollback gate revert

- The gate reverts to **`decide_keep_soft`** (`falsify.py:142`, already written,
  currently unused): keep iff `cand_mean > inc_mean + noise_margin`.
- `noise_margin` reuses the existing seed-noise second eval (`loop.py:428`).
- **`PairwiseJudge` is deleted** (class + `decide_keep_pairwise` + the AA gate +
  replication gate + Elo path in `run_gdpval_soft`). It was measurement+decision
  fused and could only yield relative values.
- The falsification verdict taxonomy (`evaluate_changes`, `compute_diff`,
  rejected-edit buffer) stays in the evaluator layer.

**Companion denoising (required, not optional).** A single-sample mean-% gate has
regression-to-mean noise (confirmed in `PARTIAL_RUN`). To make the reverted gate
trustworthy, the worker's deliverables are **k-sampled** (per ROADMAP) so
`cand_mean` is denoised before it reaches the evaluator. Confirmed companion: a
**deliverable cache keyed by (task, harness-signature)** so re-evals are cheap
and reproducible.

## 7. B-pile debugger (core new mechanism)

Three layers; the firewall sits between them.

### 7.1 Observation (sees ground truth)
- **Per-criterion rubric verdicts** — wired through from the grader (§5), free.
- **Critic pass** — a new LLM call per failed task. Input: deliverable + the
  failed criteria (+ gold deliverable as reference). Output: an **answer-free
  deficiency note** ("missing the depreciation schedule the rubric requires"),
  *never* an answer value ("...should be $559,377.61"). The critic is the inner
  wall of the firewall: prompted to describe missing **capability/structure**
  only. Uses the neutral judge model (`QEA_CRITIC_MODEL`, default = judge model).

### 7.2 Attribution (failure → component)
- **Default: hybrid (c).** A B-pile root-cause tag vocabulary —
  `MissingDomainKnowledge / WrongStructure / FormatGap / OccupationMismatch /
  CalcError` — into which the diagnose-LLM classifies the critic notes. Each tag
  carries a documented **slot affinity** (knowledge→memory/skill,
  structure→prompt/skill, occupation→router, calc→tool/validator) that *guides*
  but does not *force* the proposer. This mirrors the existing A-pile tag design.
- **Switchable: free-LLM attribution (a).** When a change is "rewrite-level" (a
  component is being replaced wholesale, where the tag→slot affinity binds), the
  diagnose-LLM names the target slot/component directly. The attribution layer is
  built dual-mode from the start.

### 7.3 Firewall exit
`diagnose()` emits only a **sanitized package** to the proposer:
`{ root_cause_tag, deficiency_category, suggested_target_slot, predicted_fix_task_ids }`.
The evolve_agent never receives raw rubric verdicts, gold text, or any answer
value — so even a proposer that *wanted* to hardcode has nothing to hardcode.

## 8. Leakage guard (universal evaluator-layer anti-cheat)

A single, **pile-agnostic** rule enforced in the evaluator: *no component may
contain task-specific answer material.* It audits the proposed **edit's
component content** (not the deliverable) against the benchmark's `answer_corpus`:

- Normalized n-gram / substring overlap above a configurable threshold →
  **reject the edit** with a new verdict `LEAKAGE_BLOCKED`, recorded distinctly
  and added to the rejected-edit buffer. Runs **pre-apply** (before grading).
- `answer_corpus` is benchmark-supplied: A → reference numeric answers; B →
  rubric-criteria text + gold deliverable text.
- Threshold: **TBD (待定)** — deferred to a later decision. The implementation
  exposes it as a config key with a conservative placeholder, but the actual
  value is not fixed in this design.

### Two-line anti-hardcode defense

| Defense | Layer | Catches | Parametric benchmark (synthetic / future) | GDPval (B) |
|---|---|---|---|---|
| perturbation probe | grader (score-intrinsic) | hardcode → probe score drops | ✅ | ✘ (no params to perturb; a leaked answer scores *high*) |
| leakage guard | evaluator (audits edit content) | component contains answer material | ✅ | ✅ (B's **only** content-level defense) |

Key asymmetry that makes the guard necessary on B: **parametric-task cheating
shows up in the score (grader catches it); B-pile cheating shows up in the
component content (only the guard catches it)** — because a leaked B answer
*satisfies* the rubric and scores higher, so the grader cannot see it. The guard
is uniform; only the `answer_corpus` differs per benchmark. Today it is active on
GDPval and on the synthetic fixture; it future-proofs any later benchmark whose
grader cannot perturb.

## 9. Information flow

```
ground truth (rubric verdicts + gold)        ← answers visible ONLY here
   │
   ├─ grader: rubric % score (per-criterion verdicts as byproduct)
   ▼
critic ──answer-free deficiency notes──▶ diagnose (tag + attribution, sanitize)
                                              │  ── FIREWALL ──
                                              ▼  component-level signal only
                                          evolve_agent → 1 edit (L_t = 1)
                                              ▼
                              leakage guard (edit content vs answer_corpus)
                                     │ over threshold → LEAKAGE_BLOCKED (+ buffer)
                                     ▼ pass
                              apply to clone → grade (rubric %, k-sampled)
                                     ▼
                              evaluator: decide_keep_soft → keep / rollback
```

## 10. What stays unchanged

7-slot harness; minimal seed (`tool` only); clone/apply/rollback; rejected-edit
buffer (signature match); edit budget `L_t = 1`; k-repeat denoise; per-subtype /
iron-law-4; three-layer manifest persistence; checkpoint/resume.

## 11. Code touch points (to be detailed in the plan)

- **`qea/verifier.py`** → conceptually `grader.py`: drop `_quantize_parity`;
  expose per-criterion verdicts on `TaskResult`; add the **Critic**; add the
  **LeakageGuard**; **delete `PairwiseJudge`** + `bt_elo`. Keep `HardVerifier` +
  the probe only as the synthetic mock fixture's grader.
- **`qea/agents.py`**: new B-pile branch in `diagnose` (rubric verdicts + critic
  → tags/attribution, dual-mode); firewall in `_propose_real` (sanitized input
  only).
- **`qea/falsify.py`**: GDPval gate → `decide_keep_soft`; add `LEAKAGE_BLOCKED`
  handling; remove `decide_keep_pairwise`.
- **`qea/loop.py`**: rewire `run_gdpval_soft` to the % gate + B-debugger + leakage
  guard; remove the pairwise anchor/Elo/replication machinery; **remove the 2-arm
  ablation** (`run_ablation` / A-only-vs-A+B `run_arm`); introduce the `Benchmark`
  abstraction (tasks + grader + answer_corpus); add worker k-sampling + a
  per-(task, harness-signature) deliverable cache.
- **`qea/tasks.py`**: load gold deliverable text into the GDPval benchmark's
  `answer_corpus`; **drop the real A-pile task loaders**, keeping only the
  synthetic fixture used by `--mock`.
- **`qea/harness.py`**: no structural change expected (the leakage guard is
  evaluator-side, not a harness slot).
- **`run.py` / tests**: `--mock` now drives the synthetic plumbing fixture; the
  ablation entry points are removed.

## 12. Acceptance criteria for this change

1. **Firewall holds**: in a unit test, the proposer's input dict provably
   contains no rubric-answer / gold substring (assert sanitization).
2. **Leakage guard fires**: an edit whose content embeds an answer-corpus n-gram
   is `LEAKAGE_BLOCKED` and buffered — tested on the GDPval (B) corpus and on the
   synthetic fixture corpus.
3. **Grader is absolute**: GDPval grader returns a continuous % in [0,1] (no
   `{0,0.5,1}` collapse) and the per-criterion verdicts are present on the result.
4. **Evaluator decides on %**: keep/rollback goes through `decide_keep_soft`;
   no `PairwiseJudge` symbol remains in the codebase.
5. **B-debugger attributes**: on a seeded failing B fixture, `diagnose` produces a
   non-empty root-cause tag + target-slot suggestion derived from the critic note
   (not from A-pile `base_pass/probe_pass`).
6. The synthetic mock fixture's plumbing signals (causal connectivity, monotonic
   progress, correct rollback, buffer block) still pass offline with no API.

## 13. Deferred / out of scope

- **New benchmarks** — the `Benchmark` abstraction is built so more can be added
  later; only GDPval ships now. A-pile is removed (no headroom), not deferred.
- **Leakage-guard threshold value** — TBD (§8); only the mechanism + config key
  land now.
- Held-out task split / regime split (still deferred per ROADMAP).
- Multi-task aggregation rule for attribution (considered, not adopted — single-
  task failures remain actionable).
- Pairwise / Elo (dropped entirely, not retained even as a diagnostic).
- Semantic (embedding) leakage detection — v1 guard is n-gram/substring only.
