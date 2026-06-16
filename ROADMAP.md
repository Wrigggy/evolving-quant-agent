# ROADMAP — explicitly NOT in v0

v0 is a mechanism check: the GDPval finance/accounting task family, a soft rubric-
percentage gate, a B-pile debugger with an information firewall, a leakage guard,
and a scriptable closed loop. Everything below is deferred. Each optimization
direction is framed as a hypothesis whose **core experiment is a `fitness vs
verifier-call-budget` curve**, measured against two baselines:

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
- **The worker is strongly capability-sufficient on numeric tasks.** On the 4
  well-specified tasks it wrote textbook solutions (math.erf Black-Scholes = exact,
  correct amortization to 0, NPV + Newton IRR to 1e-13). So once prompts are fixed
  the A-pile is likely ~7/7 — confirming iron law 1 was violated (capability-
  sufficient, not process-limited). **The A-pile numeric tasks have been removed as
  a benchmark** (superseded: no headroom). They survive only inside the offline
  synthetic fixture for the `--mock` plumbing test.
- **Eval non-determinism (real, secondary).** The quant_agent regenerates each
  solution via a fresh LLM call (temp 0.2) every evaluation, so re-evaluating the
  same harness gives slightly different scores. **Fix:** deliverable cache keyed by
  (task, harness signature) — now implemented in `_DeliverableCache`.
- **Weak evolve/ADB agent.** deepseek-v4-pro's ADB-lite diagnosis hallucinated a
  crash story and its edits were plausible but never beneficial — matches the AHE
  report's open question on evolve-agent model strength (try a stronger evolve
  agent once tasks + eval are clean).

## Findings from the GDPval-soft real run (deepseek, 30 original tasks)

End-to-end soft-rubric-driven evolution on the 30 original GDPval finance tasks ran
clean (timeout+concurrency+retry fixes held). Result: seed mean rubric 0.618 (19/30
>= 0.6); the evolve_agent proposed sensible edits, two of which IMPROVED the
aggregate (financial_computation_skill -> 0.651/22; variable_pay_middleware ->
0.645/21) — but ALL were rolled back, so the trajectory was flat ("soft headroom
NOT observed").

- **The strict gate was too strict for a noisy soft signal (now fixed).** The old
  `decide_keep` rejected any edit with unattributed regressions. With a soft judge,
  every candidate eval regenerates both the deliverable and the judge, so 1-2
  spurious per-task regressions appear on every edit -> MIXED -> rejected, even
  when the aggregate improved. **Fix implemented:** `decide_keep_soft` (keep if the
  aggregate mean rubric % improves beyond the eval noise floor), combined with
  the deliverable cache to remove regeneration noise.
- **Text-deliverable lower bound confirmed.** 0.618 is depressed by format/layout
  criteria the text worker cannot satisfy (see the xlsx/pptx generation item below).

## Findings from the GDPval-AA pairwise runs (2026-06-11)
[SUPERSEDED: pairwise grading replaced by the soft %-gate + grader/evaluator split; see below.]

Full report: `docs/reports/2026-06-11-gdpval-aa-grader-report.md`. Key findings
that fed the current design:

- **Clean null, decisive discrimination.** The pairwise gate showed clean null
  (seed-vs-seed exactly 0.500), decisive discrimination (candidate win shares
  spanning 0.000–0.522), 7/7 directional agreement with the rubric diagnostic,
  judge A/B (deepseek self-judge vs qwen cross-family) at ~90% agreement on
  decided matches, and a replication gate that killed the one sampling-noise keep.
  These validated pairwise judging as a trustworthy signal, and the same judge
  model was carried forward for the rubric %-grader.
- **THE finding — the proposer's OBSERVATION SPACE is wrong for B-pile.** The
  `_diagnose_real` / `_propose_real` path rendered every failing task in A-pile
  hard-verifier semantics (`base_pass / probe_pass / error`), which is degenerate
  for B tasks (fields are always false/None). The evolve_agent structurally could
  NOT see "the memo lacks a sensitivity analysis" and instead hallucinated
  "unparseable output" / "needs code_exec". Result: 8/8 edits in aa_run8 damaged
  free-form writing (4 decisively refuted; proposer predicted-fix hit rate 3/63).
  **Fix implemented:** the B-pile debugger (`qea/debugger.py`) with per-criterion
  rubric verdicts + Critic + firewall.
- **The discarded signals already existed.** SoftJudge was eliciting per-criterion
  verdicts and discarding them. No new scoring calls were needed — only wiring them
  to the proposer behind the firewall.

The GDPval-AA pairwise grader (`PairwiseJudge`, Bradley-Terry/Elo, win-rate gate)
has been **deleted**: it fused measurement and decision and could not produce an
absolute score. The rubric %-gate (`decide_keep_soft`) is the current gate. Pairwise
/ Elo are not retained even as a diagnostic.

## Next experiments (priority order)

1. **Run the B-pile debugger on the original 30 GDPval tasks** (the first real
   experiment under the new architecture). Acceptance: run N iterations under the
   `decide_keep_soft` gate; success = keep rate departs 0 with replicated wins
   (budget ~$15 / ~3h). The B-debugger + sanitized observations fix the structural
   reason all prior edits were refused or harmful.
2. **File-producing worker for the Accountants/Auditors wall** (rubric mean 0.100;
   capability gap, untouched by all prior middleware edits) — .xlsx/.pdf output via
   openpyxl/LibreOffice in the sandbox; overlaps with the "GDPval B-pile grading
   fidelity" stub below.
3. **Judge options (settled, act when relevant):** switch `QEA_JUDGE_MODEL` to
   `google/gemini-3.1-pro-preview` for full rubric fidelity once accessible; or
   use the ~3x-cheaper deepseek judge for long runs (A/B-validated at ~90%
   agreement; qwen stays default for its smaller null deviation).

## Stubs carried over from v0 (close these first)

- **Real isolation for `code_exec`.** v0 uses restricted `exec` + SIGALRM in the
  main thread. Move to subprocess/container/E2B before running untrusted or large
  solutions.
- **Selection split + regime split.** v0 has no selection split; the leakage guard
  + observation firewall carry the anti-overfit signal. Re-introduce SkillOpt's
  independent selection split, and generalize from task-k-fold to **cross-time-
  window / cross-regime** folds for non-stationary (time-series) families.
- **Look-ahead data-access middleware.** The slot + stub exist; wire the runtime
  guard (block reads of data at time > backtest clock) when a time-series family
  lands.
- **GDPval B-pile grading fidelity.** v0 grades against the open `rubric_json`
  per-criterion on the candidate's TEXT. Two gaps to close: (1) the agent emits
  text, not real .pdf/.pptx/.xlsx, so format/layout criteria fail — have the agent
  produce real files. (2) Full fidelity = OpenAI's actual method: render each
  deliverable page to PNG via LibreOffice and grade with a multimodal model,
  pairwise vs the gold human deliverable (gold ships for 17/25 finance tasks) →
  win-rate. The official grader itself (GPT-5-high) has no public API/code.
- **SkillOpt edit-budget schedule.** v0 fixes `L_t = 1`. Add the cosine schedule
  (start 3-4, decay to 1-2) and the rank-and-keep-top-L clip.
- **Buffer semantic dedup.** v0 uses signature match only. Add normalized-diff /
  embedding dedup only if verbatim re-proposals are observed.
- **Multi-benchmark routing.** v0 has one real benchmark (GDPval). The `Benchmark`
  abstraction is built to accommodate more; add them via new `Benchmark` instances
  as new task families land.

## Deferred items from the grader/evaluator redesign

- **Gold-deliverable-text in the leakage corpus.** GDPval gold is binary xlsx/pptx
  behind URLs; extracting text needs fetch + Office parsing. v1 corpus is
  rubric-criteria text only. When gold-deliverable text is available, add it to
  `answer_corpus` for a stronger leakage signal.
- **Leakage-guard threshold tuning.** The `threshold` parameter in `LeakageGuard`
  is currently an untuned placeholder (0.6). Tune via holdout: measure false-
  positive rate on known-clean edits and false-negative rate on injected leaks.
  Also: add a short-edit bypass (edits shorter than `n` tokens have no shingles
  and are currently never flagged — this is a known v1 limitation).
- **Free-LLM attribution mode for component rewrites.** `diagnose_b_pile` is
  dual-mode (`mode="hybrid"` default, `mode="free"` for rewrite-level changes
  where the tag→slot affinity is too coarse). Wire the `free` mode trigger when
  a proposed edit replaces a component wholesale.
- **New benchmarks via the Benchmark abstraction.** The `Benchmark` dataclass is
  forward-looking: plug in a new `(tasks, grader, answer_corpus, debugger_kind)`
  to add any future benchmark without touching the loop.

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
proxies are rank-faithful is itself a contribution.

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

### 5. Worker k-sampling
The deliverable cache removes regeneration noise per harness; the next step is to
k-sample the worker (majority vote or best-of-k) so `cand_mean` is further denoised
before it reaches the evaluator. Confirmed companion to the %-gate.

## Benchmark expansion (transfer / final validation, not the v0 loop)

- **Hard-verifier families that drive evolution:** FinRL-Meta (NeurIPS 2022 D&B,
  friction-adjusted backtest with a leak-proof train-test-trade pipeline),
  FinBen trading subset (NeurIPS 2024 D&B), Finance Agent Benchmark (ships its
  own harness — highest comparison value).
- **Soft-verifier transfer eval (frozen harness only):** GDPval B-pile (current),
  EconAgent (ACL 2024), FinanceBench.
- **Live final validation (not in the loop):** Agent Market Arena (WWW 2026).

## GDPval file-grading sub-projects (v0.1 onward)

Sub-project 1 (file-producing worker) shipped in v0.1. Two remain:

- **Sub-project 2 — gold human-deliverable file acquisition.** Fetch and cache the
  binary files behind `deliverable_file_urls` in the GDPval fork (`data/gdpval/`).
  Files ship for 17/25 finance tasks (xlsx / pptx). Needed to: (a) add gold-
  deliverable text to the leakage corpus for a stronger leakage signal, and (b)
  enable pairwise-vs-gold multimodal grading in sub-project 3.
- **Sub-project 3 — faithful file-aware / multimodal grader.** xlsx/pptx →
  LibreOffice-headless render → page images → multimodal judge, pairwise vs the
  gold human deliverable. AHE's `read_visual_file` is the reference pattern.
  Also: formula-value computation deferred from v0.1 (LibreOffice recalc on the
  produced file, or a `formulas`/`pycel` pip engine) so rendered cell values are
  numeric rather than formula strings.

## Future directions (post sub-project 3)

- **Tool synthesis.** Let evolved `tool` components carry executable code run by an
  agentic worker — not just inert descriptors. AHE (`nexau.archs.sandbox` + the
  `run_code_tool` / file / web / session toolset) is the reference substrate;
  `exec_artifact` is the minimal stdlib slice of it. The trajectory is: seed
  `tool:xlsx_writer` (v0.1, static effect tag) → evolved tools carry real code →
  agentic worker dispatches them dynamically.
- **Container / cloud exec isolation.** `exec_artifact` v0.1 uses a subprocess
  posture (temp `work_dir`, scrubbed env, kill-on-timeout). Harden to docker
  container or nexau `E2BSandbox` before running adversarially generated or
  user-supplied code at scale.
- **Couple to AHE / evolve a real agentic harness (Track 2).** The broader
  direction — coupling QEA to the full AHE substrate and evolving a real agentic
  harness (tool dispatch, multi-step reasoning, web/file/session tools) — is being
  tracked as a parallel branch. `exec_artifact` is a stepping stone; the full
  harness is the destination.
