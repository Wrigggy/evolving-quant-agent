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
- **OpenAI GDPval grader as a separate soft-eval track** (never the loop verifier).
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
