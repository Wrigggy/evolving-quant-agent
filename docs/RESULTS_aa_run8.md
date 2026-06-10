# Result — 8-iteration GDPval-AA pairwise-gated evolution (qwen3.7-max judge)

30 original GDPval finance tasks (local fork). Worker = deepseek-v4-flash,
evolve = deepseek-v4-pro, judge = qwen/qwen3.7-max (official Alibaba pin).
Gate = blind pairwise cand-vs-inc, ties excluded, keep iff win share > 0.5 +
null margin, plus the replication step (regen + rematch) added after the judge
A/B. Fresh seed; null margin came out clean: seed-vs-seed 11/11/8 → **0.050**.
Wall clock 2h40m (match_set parallelized); ~$18 of OpenRouter credits.

## Verdict: NO HEADROOM — and this time it is a CLEAN negative

**0/7 edits kept (1 iteration blocked).** Win rate vs frozen seed flat at 0.500,
Elo 1000. Unlike the old mean-score run ("0/8 kept, everything within noise,
inconclusive"), the pairwise gate shows most edits actively DAMAGED deliverable
quality — decisive losses, not noise:

| iter | edit | W/L/T | win share | verdict |
|---|---|---|---|---|
| 1 | prompt:output_format_prompt | 0/28/2 | **0.000** | HARMFUL |
| 2 | (no valid edit / buffer block) | — | — | BLOCKED |
| 3 | skill:financial_calculations | 11/15/4 | 0.423 | HARMFUL |
| 4 | validator:financial_sanity_validator | 3/19/8 | 0.136 | MIXED |
| 5 | memory:financial_knowledge_base | 9/10/11 | 0.474 | HARMFUL |
| 6 | router:financial_occupation_router | 13/13/4 | 0.500 | HARMFUL |
| 7 | prompt:enable_code_exec_for_calculations | 5/16/9 | 0.238 | MIXED |
| 8 | tool:fin_knowledge_retrieve | 12/11/7 | 0.522 | INEFFECTIVE |

Reading: 4 of 8 edits lost decisively (≤0.42); only iters 5/6/8 were
noise-level (~0.5). The replication gate was never triggered (nothing passed
the first gate). The signature failure is iter 1: a format-forcing prompt
component lost 28 of 30 matches — harness middleware actively degrades a
capable worker's free-form finance writing.

## Interpretation

1. **The evolve agent (deepseek-v4-pro) is the bottleneck, not the gate.** The
   gate now has discriminative power (decisive rejections, clean null), and the
   AHE finding repeats: a mid-tier evolve agent's edits hurt more than help on
   tasks the worker is already competent at.
2. Consistent with iron law 1: most of these tasks are not process-limited for
   flash; bolting on prompts/validators/routers subtracts. The weak tail
   (Accountants and Auditors, mean 0.100) is a capability gap that no
   middleware edit fixed — the same wall as ever.
3. The aa_qwen_test "keep" (financial_calculator, 0.609) now looks even more
   clearly like the sampling noise the judge A/B said it was: under a clean
   null and 8 fresh attempts, nothing replicated that win.

## Per-occupation (final = seed, rubric diagnostic)

| occupation | pass (>=0.6) | mean |
|---|---|---|
| Personal Financial Advisors | 5/5 | 0.900 |
| Real Estate Brokers | 5/5 | 0.700 |
| Financial and Investment Analysts | 4/5 | 0.600 |
| Financial Managers | 3/5 | 0.550 |
| Securities/Commodities Sales | 3/5 | 0.500 |
| Accountants and Auditors | 1/5 | **0.100** |

## What would move the needle next

- A stronger evolve agent (the AHE paper's gap: GPT-5.4-class proposer) — the
  rejection reasons are rich; the proposer keeps making format-heavy edits.
- Target the wall directly: Accountants/Auditors needs file-producing
  capability (.xlsx), not prompt middleware (ROADMAP item).
- The gate itself is now trustworthy: clean null, decisive discrimination,
  replication backstop. Reuse as-is for the next experiment.
