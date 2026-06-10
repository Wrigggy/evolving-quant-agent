# Result — first GDPval-AA pairwise-gated run (qwen3.7-max judge), 2 iterations

30 original GDPval finance tasks (local fork). Worker = deepseek-v4-flash,
evolve = deepseek-v4-pro, judge = **qwen/qwen3.7-max** (cross-family, official
Alibaba provider pin; AA's official judge Gemini 3.1 Pro Preview not accessible).
This was a 2-iteration SMOKE TEST of the new GDPval-AA grader, not a headroom run.

## Verdict: pipeline VALIDATED; headroom not observed (2 iters, expected)

- **Pairwise null margin 0.0652** (seed-vs-seed W/L/T = 10/13/7) — the judge noise
  is measured, so a candidate must reach win share > 0.5652 over decided matches.
- Rubric-score noise floor 0.0583 (diagnostic) — higher than deepseek self-judging
  (0.0276); the cross-family judge is harsher and noisier on per-criterion grading.
- **The gate discriminates** — the key thing the old mean-score gate (0/8 kept,
  all within noise) could not do:

| iter | edit | cand-vs-inc W/L/T | win share | gate |
|---|---|---|---|---|
| 1 | memory:financial_formula_memory | 6/17/7 | 0.261 | **rollback** (decisive) |
| 2 | tool:financial_calculator | 14/9/7 | **0.609** | **KEEP** (first ever kept edit) |

- Anchor match (incumbent vs frozen seed): 11/10/9 → win rate **0.524**,
  **Elo vs seed 1015.8** (anchor 1000). Below 0.5 + null margin → headroom NOT
  observed at 2 iterations.

## Notable: pairwise and rubric DISAGREE on the kept edit

The kept financial_calculator edit won pairwise 14/9 but the rubric diagnostic
*dropped* (mean 0.533 → 0.517, pass count 21 → 19; falsify verdict MIXED).
Possible readings, unresolved: (a) pairwise rewards holistic quality the
itemized rubric misses; (b) Goodhart risk — the edit makes deliverables more
*persuasive* to a pairwise judge without satisfying more rubric criteria;
(c) both signals are weak at n=30, k=2. Worth a dedicated A/B before trusting
long pairwise-gated runs.

## Per-occupation (final incumbent, rubric diagnostic)

| occupation | pass (score>=0.6) | mean |
|---|---|---|
| Personal Financial Advisors | 5/5 | 0.900 |
| Real Estate Brokers | 5/5 | 0.750 |
| Financial and Investment Analysts | 4/5 | 0.600 |
| Securities/Commodities Sales | 3/5 | 0.450 |
| Financial Managers | 2/5 | 0.350 |
| Accountants and Auditors | 0/5 | **0.050** |

Same ordering as the deepseek-judged runs (Accountants/Auditors weakest), but the
qwen judge scores the weak tail much lower (0.050 vs ~0.25-0.31) — judge identity
materially shifts absolute rubric scores; pairwise relative signal is the point.

## Ops notes

- First attempt was killed silently at ~2h07m (background-task time limit);
  `--resume` from the iter-1 checkpoint worked exactly as designed (pw_margin,
  seed anchor deliverables, buffer all restored). Re-run detached via nohup +
  a watchdog (process-dead -> auto-resume; log stale >45min -> kill+resume).
- `PairwiseJudge.match_set` is sequential and silent (~30 min per 30-task match
  at k=2) — TODO: parallelize with QEA_MAX_CONCURRENCY + interim progress prints.
- Wall clock ~4h for seed×2 + null + 2 iters + 1 anchor match; ~5 transient
  APIConnectionError/JSONDecodeError per eval, all absorbed by retries.
