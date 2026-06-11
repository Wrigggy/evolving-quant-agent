# ROADMAP — explicitly NOT in v0

v0 is a mechanism check: one task family, a hard A-pile verifier, a soft B-pile
transfer, a scripted-mockable closed loop. Everything below is deferred. Each
optimization direction is framed as a hypothesis whose **core experiment is a
`fitness vs verifier-call-budget` curve**, measured against two baselines:

- **Life-Harness-style full-iterate baseline** — re-evaluate every candidate on
  the full task set every iteration (no budget discipline).
- **AHE-style file-edit baseline** — the reproduced AHE loop (uniform harness
  search, single-edit, full re-eval).

A direction "wins" only if its curve dominates both baselines (higher fitness at
equal verifier-call budget, or equal fitness at lower budget).

## Findings from the v0 real run (deepseek-v4-pro, real GDPval B-pile)

A per-task diagnostic against deepseek-v4-pro revealed the real picture:

- **Task-authoring bug (DOMINANT, now fixed).** The 3 supplement A-tasks
  (A_opt_02, A_val_02, A_amort_wall) had non-self-contained prompts ("Same
  contract as A_opt_01, different inputs"). Each solve is an independent LLM call
  that never sees A_opt_01, so the model hallucinated unrelated problems
  (demand-curve optimizer, descriptive statistics, future-value) -> KeyError/
  TypeError -> deterministic fail. Fixed: every A-task prompt is now self-contained.
  Lesson: any task whose prompt references another task is broken under
  independent-call evaluation.
- **The worker is strongly capability-sufficient here.** On the 4 well-specified
  tasks it wrote textbook solutions (math.erf Black-Scholes = exact, correct
  amortization to 0, NPV + Newton IRR to 1e-13). So once prompts are fixed the
  A-pile is likely ~7/7 -> the open question becomes whether these numeric tasks
  have ANY process-headroom for a strong model, or are simply capability-sufficient
  (iron law 1). If the latter, swap in genuinely process-limited tasks.
- **Eval non-determinism (real, secondary).** The quant_agent regenerates each
  solution via a fresh LLM call (temp 0.2) every evaluation, so re-evaluating the
  same harness gives slightly different scores; k-repeat denoises the
  verifier/probe, not solution generation. Fix: cache the solution per (task,
  harness signature) for reproducible/cheaper re-eval, optionally k-sample the
  worker (majority/best) or set temperature 0. (Earlier this was mis-diagnosed as
  THE blocker; the per-iteration wobble was actually confounded by different
  candidate harnesses per iter, not same-harness noise.)
- **Weak evolve/ADB agent.** deepseek-v4-pro's ADB-lite diagnosis hallucinated a
  crash story and its edits were plausible but never beneficial — matches the AHE
  report's open question on evolve-agent model strength (try a stronger evolve
  agent once tasks + eval are clean).

## Findings from the GDPval-soft real run (deepseek, 30 original tasks)

End-to-end soft-rubric-driven evolution on the 30 original GDPval finance tasks ran
clean (timeout+concurrency+retry fixes held). Result: seed mean rubric 0.618 (19/30
>= 0.6); the evolve_agent proposed sensible edits, two of which IMPROVED the aggregate
(financial_computation_skill -> 0.651/22; variable_pay_middleware -> 0.645/21) — but
ALL were rolled back, so the trajectory was flat ("soft headroom NOT observed").

- **The strict gate is too strict for a NOISY soft signal (THE fix).** decide_keep
  rejects any edit with unattributed regressions. With the soft judge, every candidate
  eval regenerates both the deliverable and the judge, so 1-2 spurious per-task
  regressions appear on EVERY edit -> verdict MIXED -> rejected, even when the aggregate
  improved. The gate (correct for a clean hard signal, added after code review) conflates
  noise-regressions with real harm. **Fix: a noise-aware gate for soft mode** — keep if
  the aggregate (mean rubric score / oos count) improves beyond the eval noise floor,
  tolerating a few per-task regressions; estimate the noise floor by re-evaluating the
  incumbent k times. Combine with eval denoising (cache deliverables per harness
  signature; higher k; temperature 0) so the regressions that remain are real. With this,
  iter2/iter3 would be kept and soft headroom would likely be OBSERVED.
- **Text-deliverable lower bound confirmed.** 0.618 is depressed by format/layout
  criteria the text worker can't satisfy (see the .xlsx/.pptx generation item below).

## Findings from the GDPval-AA pairwise runs (2026-06-11)

Full report: `docs/reports/2026-06-11-gdpval-aa-grader-report.md`. The grader was
migrated to the Artificial Analysis GDPval-AA protocol (blind pairwise, ties
excluded, BT-Elo vs frozen seed anchor, measured null margin, replication gate).
This SUPERSEDES the "noise-aware mean-score gate" fix above as the soft decision
signal (the mean rubric score remains as a diagnostic only).

- **The grader line is closed: the pairwise gate is trustworthy.** Clean null
  (seed-vs-seed exactly 0.500), decisive discrimination (candidate win shares
  spanning 0.000–0.522), 7/7 directional agreement with the rubric diagnostic,
  judge A/B (deepseek self-judge vs qwen cross-family) shows ~90% agreement on
  decided matches and identical keep decisions, and a replication gate that
  killed the one sampling-noise keep (financial_calculator, 0.609 first pass,
  0.40–0.46 on fresh samples under both judges).
- **THE finding — the proposer's OBSERVATION SPACE is wrong for B-pile, and it,
  not evolve-model strength, is the current bottleneck.** `_diagnose_real` and
  `_propose_real` (qea/agents.py) render every failing task in A-pile
  hard-verifier semantics — `base={bool} probe={bool} err=None`, tag set
  {Hardcoding, BadFormat, ToolBroken, ...}, "quant harness / code_exec" framing.
  For B-pile soft tasks these fields are degenerate (base/probe are copies of
  "rubric score >= 0.5", err is always None), so the Agent Debugger structurally
  CANNOT see "the memo lacks a sensitivity analysis" and instead hallucinates
  "unparseable output" / "needs code_exec". The proposer then prescribes
  format/code middleware that damages free-form writing — 8/8 edits in the
  aa_run8 experiment, 4 decisively refuted (iter1: a force-JSON prompt lost
  0/28); proposer predicted-fix hit rate 3/63. Lesson (transferable): the AHE
  diagnose->propose->falsify MECHANISM ports across domains; the observation
  INSTANTIATION does not. Do not upgrade the evolve model before fixing what it
  observes — a stronger model reading the same wrong dashboard fails the same way.
- **The discarded signals already exist.** SoftJudge elicits PER-CRITERION
  true/false verdicts and keeps only the quantized score; PairwiseJudge asks for
  {"winner"} only and discards any loss reason. The fix needs no new scoring
  calls — route existing signals to the proposer.

## Next experiments (priority order)

1. **B-pile-specific diagnosis + proposer reframing (do this first; low cost,
   high certainty).**
   - Render per failing task: occupation + the verbatim rubric criteria judged
     unmet + (when available) a one-line pairwise loss reason (extend the
     PairwiseJudge JSON to {"winner", "reason"}).
   - Replace the A-pile tag set with a writing-domain taxonomy:
     {MissingCriteria, MissingArtifact (.xlsx/.pdf required), WrongRegister,
     ShallowAnalysis, FormatMismatch, IgnoredContext}.
   - Reframe `_propose_real`: the worker WRITES DELIVERABLES (memos, emails,
     analyses), not code; slot pharmacopoeia becomes writing-oriented (style
     guides, occupation personas, checklists, exemplar memories).
   - Acceptance: rerun 8 iterations under the unchanged AA gate; success = keep
     rate departs 0 with replicated wins (budget ~$15 / ~3h).
2. **File-producing worker for the Accountants/Auditors wall** (rubric mean
   0.100; capability gap, untouched by all 8 middleware edits) — .xlsx/.pdf
   output via openpyxl/LibreOffice in the sandbox; overlaps with the
   "GDPval B-pile grading fidelity" stub below.
3. **Judge options (settled, act when relevant):** switch `QEA_JUDGE_MODEL` to
   `google/gemini-3.1-pro-preview` for full AA fidelity once accessible; or use
   the ~3x-cheaper deepseek judge for long runs (A/B-validated as agreeing with
   qwen ~90% on decided matches; qwen stays default for its smaller null
   deviation, 0.05 vs 0.119).

## Stubs carried over from v0 (close these first)

- **Real isolation for `code_exec`.** v0 uses restricted `exec` + SIGALRM in the
  main thread. Move to subprocess/container/E2B before running untrusted or
  large solutions.
- **Selection split + regime split.** v0 has no selection split; the probe and
  B-transfer carry the OOS signal. Re-introduce SkillOpt's independent selection
  split, and generalize from task-k-fold to **cross-time-window / cross-regime**
  folds for non-stationary (time-series) families.
- **Look-ahead data-access middleware.** The slot + stub exist; wire the runtime
  guard (block reads of data at time > backtest clock) when a time-series family
  lands. Numeric tasks have no time axis, so v0 never exercises it.
- **Real GDPval A-pile verifier.** v0 authors clean A-pile instances. To verify
  *raw* GDPval numeric tasks, add a structured-output contract + an answer-key
  extractor from `rubric_json`, or a deliverable parser (.xlsx/.pdf).
- **GDPval B-pile grading fidelity.** v0 grades against the open `rubric_json`
  per-criterion (weighted) on the candidate's TEXT. Two gaps to close: (1) the
  agent emits text, not real .pdf/.pptx/.xlsx, so format/layout criteria fail —
  have the agent produce real files. (2) Full fidelity = OpenAI's actual method:
  render each deliverable page to PNG via LibreOffice and grade with a multimodal
  model, pairwise vs the gold human deliverable (gold ships for 17/25 finance
  tasks) → win-rate. The official grader itself (GPT-5-high) has no public
  API/code — its web-form service appears unavailable — so the official win-rate
  can only ever be a manual, periodic external check, never in-harness.
- **SkillOpt edit-budget schedule.** v0 fixes `L_t = 1`. Add the cosine schedule
  (start 3-4, decay to 1-2) and the rank-and-keep-top-L clip.
- **Buffer semantic dedup.** v0 uses signature match only. Add normalized-diff /
  embedding dedup only if verbatim re-proposals are observed.
- **Multi-family routing.** v0 has one family, two piles. Generalize the router.

## Optimization directions (hypotheses to test)

### 1. Prioritized / credit-assigned harness search
Stop searching the harness space uniformly. Use failure-diagnosis + a PUCT-like
**value-of-information** rule to choose which slot to mutate and which instances
to evaluate next. Hypothesis: VOI-guided search reaches equal fitness at a
fraction of the verifier-call budget vs uniform AHE search.

### 2. Multi-fidelity verifier
Run a cheap proxy check first; escalate to the full expensive verifier only for
survivors (successive halving). **Load-bearing prerequisite:** first verify the
cheap proxy is rank-correlated with the full verifier — characterizing which
proxies are rank-faithful is itself a contribution. (Quant proxies: short-window
backtest vs full; a few perturbation seeds vs many; coarse vs fine tolerance.)

### 3. Entropic / risk-seeking pruning
When pruning to save budget, do **not** prune on mean fitness; protect
high-variance, high-upside "late-bloomer" edits (a transplant of TTT-Discover's
favour-the-max objective into a pruning criterion). Hypothesis: risk-seeking
pruning preserves edits that a mean-based pruner discards too early.

### 4. Offline-amortized base + online-per-instance adaptation
v0 is offline (evolve a harness on a train set, freeze, eval held-out). The open
axis is whether to additionally run a **per-instance online** evolution pass at
inference. Nobody has done harness-level + hard-verifier on the online side; the
experiment is offline-only vs offline+online on the same verifier-call budget.

## Benchmark expansion (transfer / final validation, not the v0 loop)

- **Hard-verifier families that drive evolution:** FinRL-Meta (NeurIPS 2022 D&B,
  friction-adjusted backtest with a leak-proof train-test-trade pipeline),
  FinBen trading subset (NeurIPS 2024 D&B), Finance Agent Benchmark (ships its
  own harness — highest comparison value).
- **Soft-verifier transfer eval (frozen harness only):** GDPval B-pile (current),
  EconAgent (ACL 2024), FinanceBench.
- **Live final validation (not in the loop):** Agent Market Arena (WWW 2026).
