# Result — GDPval-soft, flash worker + pro evolve, 8 iterations (6 + resumed 2)

30 original GDPval finance tasks, soft per-criterion `rubric_json` judge (deepseek-v4-pro).
quant_agent = deepseek-v4-flash; evolve_agent = deepseek-v4-pro. Iron law 2 relaxed by design.
Ran iters 1-6, stopped for offline, then `--resume` finished iters 7-8.

## Verdict: SOFT HEADROOM NOT OBSERVED — but inconclusive (noise-limited)

- Seed mean rubric score ~**0.60**; eval **noise floor = 0.0276**.
- **0 / 8 edits kept.** Every pro edit landed within/below the noise floor (deltas roughly
  -0.04 .. 0), so the noise-aware gate credited none -> trajectory flat.
- This is NOT a clean "evolve doesn't help": the soft signal + single-sample incumbent is
  too noisy to resolve edit effects (the per-occupation numbers below swing run-to-run by
  more than the edit sizes). To get a conclusive answer, denoise the source: **k-sample the
  worker's deliverables** (generate each 2-3x, take the median) so incumbent and candidate
  means are stable, then the gate can actually credit a real gain. (ROADMAP #1.)

## Per-occupation pass rate

Two estimates — note the spread between them IS the noise we're fighting:

| occupation | pass rate (6-eval avg, robust) | mean (6-avg) | pass rate (final single sample) | mean (single) |
|---|---|---|---|---|
| Personal Financial Advisors | 100.0% | 0.819 | 100.0% | 0.816 |
| Real Estate Brokers | 86.7% | 0.761 | 100.0% | 0.816 |
| Financial and Investment Analysts | 66.7% | 0.596 | 80.0% | 0.654 |
| Financial Managers | 56.7% | 0.557 | 40.0% | 0.491 |
| Securities/Commodities Sales | 43.3% | 0.493 | 60.0% | 0.526 |
| Accountants and Auditors | 13.3% | 0.252 | 0.0% | 0.314 |

**Clear, stable signal across both:** Accountants/Auditors is the weak spot (flash struggles
on accounting/audit — numeric + format-heavy), Advisors/Real-Estate are near-ceiling.

## Confounds / caveats
- Text-only deliverables fail format/layout rubric criteria -> scores are a lower bound
  (see ROADMAP .xlsx/.pptx generation).
- Soft self-judge (deepseek), not the official GDPval pairwise grader (no public API).
- Single-sample incumbent -> regression-to-mean; the k-sample fix is the prerequisite for a
  conclusive headroom verdict.
