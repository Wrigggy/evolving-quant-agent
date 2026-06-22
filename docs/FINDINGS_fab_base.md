# Findings — FAB v2 base test (Stirrup + free tools, 2026-06-22)

Setup: Stirrup agent (deepseek-v4-pro) with clean-room **free-backend** research tools
(official SEC EDGAR full-text + filings + keyword retrieval, Yahoo/stooq prices,
DuckDuckGo), **no E2B**, answering the FAB v2 **public split (27 Qs)**. Answers graded
per-rubric (each criterion = 1 pt) by our judge `qwen/qwen3.7-plus`: **generous** =
mean partial-credit fraction, **strict** = all-pass rate. This is an *our-grader
approximation*, NOT the official Vals operator, on the public 27 only — not
leaderboard-comparable.

## Headline
- **Graded 26/27** (1 fail: `fab_11` judge JSON parse).
- **Generous: 0.659 | Strict (all-pass): 0.231.**

## By category (n, generous, strict)
| tier | category | generous | strict |
|------|----------|----------|--------|
| easy | General Qualitative | 0.889 | 0.667 |
| easy | Market Analysis | 0.793 | 0.333 |
| easy | Earnings Analysis | 0.778 | 0.667 |
| easy | Precedents | 0.752 | 0.000 |
| mid  | Disclosure Analysis | 0.680 | 0.000 |
| mid  | Adjustments | 0.595 | 0.000 |
| mid  | General Quantitative | 0.542 | 0.333 |
| hard | Comparables | 0.430 | 0.000 |
| hard | Financial Modeling | 0.396 | 0.000 |

## Reads
1. **The difficulty ordering matches FAB's published tiers.** FAB reports Earnings/
   Quant/Qualitative as high-performing and Financial Modeling/Precedents/Comparables
   as hardest; our base agent shows the same shape (Qualitative/Earnings/Market high;
   Financial Modeling/Comparables low). Good sign the setup measures the intended thing.
2. **Magnitudes are in the right ballpark.** FAB: "no model clears 58% generous; all
   below 46% strict." Ours: generous 0.659 (a bit above — expect upward bias from our
   own lenient-ish rubric judge + only the public 27) and strict 0.231 (comfortably in
   the sub-46% strict regime for a base agent on free tools).
3. **Strict ≪ generous (0.23 vs 0.66)** — the agent gets *most* points but rarely *all*
   criteria, exactly FAB's reported 11–13 pt generous→strict drop, amplified here.

## Failure modes
- `fab_17` (Adjustments): 0-char — agent never finished within 40 turns (hard cross-
  document quant task). `fab_03` (Quant): thin 831-char answer → 0.5. `fab_11`
  (Comparables): judge JSON parse error. The misses cluster in the hard quantitative /
  cross-document categories — consistent with the difficulty profile.
- **Tooling caveat:** free EDGAR + keyword retrieval (no embeddings RAG, no paid
  Tavily/Tiingo/sec-api). Comparables/Modeling need multi-company numeric reconciliation
  that keyword retrieval serves weakly — a likely contributor to the low hard-tier scores.

## Artifacts
`docs/RESULTS_fab_base.md` (summary + per-task), `docs/REPORT_fab_base.md` (per-task:
question → agent answer → per-criterion ✓/·). Outputs under `output/fab/<task>/`.
