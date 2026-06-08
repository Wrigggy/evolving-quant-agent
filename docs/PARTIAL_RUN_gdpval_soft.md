# Partial run — GDPval-soft (flash worker + pro evolve, 8 iters requested)

Stopped after **6 of 8** iterations (user left network). 30 original GDPval finance tasks, soft per-criterion rubric judge (deepseek-v4-pro). Iron law 2 relaxed by design.

- Seed mean rubric score (flash worker): **0.6032**
- Eval noise floor (gate margin to beat): **0.0276**
- Edits kept: **0** / 6 (all others rolled back)

## Per-iteration (noise-aware gate)
| iter | edit | inc_mean | cand_mean | delta | gate |
|---|---|---|---|---|---|
| 001 | prompt:occupation_matcher_prompt | 0.6032 | 0.5877 | -0.0155 | revert |
| 002 | prompt:correct_financial_formula_guidance | 0.6032 | 0.5597 | -0.0435 | revert |
| 003 | memory:occupation_knowledge_base | 0.6032 | 0.5746 | -0.0286 | revert |
| 004 | skill:occupation_probability_estimator | 0.6032 | 0.5834 | -0.0198 | revert |
| 005 | router:ProbabilityTaskRouter | 0.6032 | 0.5939 | -0.0093 | revert |
| 006 | tool:occupation_lookup | 0.6032 | 0.5787 | -0.0245 | revert |

## Per-occupation pass rate + mean score
(Aggregated across the 6 completed evals = 30 samples/occupation, to smooth single-sample noise. Incumbent stayed at seed — all edits rolled back — so this ~= seed-harness performance.)

| occupation | pass rate (score>=0.6) | mean rubric score |
|---|---|---|
| Accountants and Auditors | 4/30 = 13.3% | 0.252 |
| Financial Managers | 17/30 = 56.7% | 0.557 |
| Financial and Investment Analysts | 20/30 = 66.7% | 0.596 |
| Personal Financial Advisors | 30/30 = 100.0% | 0.819 |
| Real Estate Brokers | 26/30 = 86.7% | 0.761 |
| Securities, Commodities, and Financial Services Sales Agents | 13/30 = 43.3% | 0.493 |

## Read
All 6 of pro's edits landed within/below the noise floor (deltas -0.04..+0.0), so none was credited -> flat. Likely confounded by single-sample regression-to-mean on the incumbent baseline; the fix is to k-sample the worker's deliverables (ROADMAP). Re-run when back online to finish iters 7-8.
