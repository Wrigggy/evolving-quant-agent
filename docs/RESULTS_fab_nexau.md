# FAB v2 base test — NexAU worker (free EDGAR/price/web tools)

Graded 26/27 | judge k=2 | grader=qwen3.7-plus (our approx).
Stirrup comparison: generous 0.659 / strict 0.231.

- **Generous:** 0.618
- **Strict (all-pass):** 0.269

| category | n | generous | strict |
|---|---|---|---|
| Adjustments | 3 | 0.012 | 0.000 |
| Comparables | 3 | 0.433 | 0.000 |
| Disclosure Analysis | 3 | 0.921 | 0.333 |
| Earnings Analysis | 3 | 0.856 | 0.333 |
| Financial Modeling | 2 | 0.267 | 0.000 |
| General Qualitative Analysis | 3 | 0.889 | 0.667 |
| General Quantitative Analysis | 3 | 0.500 | 0.333 |
| Market Analysis | 3 | 0.737 | 0.333 |
| Precedents | 3 | 0.830 | 0.333 |

| task | category | generous | strict | ans | error |
|---|---|---|---|---|---|
| fab_00 | General Qualitative Analysis | 0.667 | 0 | 9033 |  |
| fab_01 | General Qualitative Analysis | 1.000 | 1 | 7581 |  |
| fab_02 | General Qualitative Analysis | 1.000 | 1 | 4531 |  |
| fab_03 | General Quantitative Analysis | 0.500 | 0 | 953 |  |
| fab_04 | General Quantitative Analysis | 0.000 | 0 | 3316 |  |
| fab_05 | General Quantitative Analysis | 1.000 | 1 | 2075 |  |
| fab_06 | Market Analysis | 1.000 | 1 | 2613 |  |
| fab_07 | Market Analysis | 0.545 | 0 | 2224 |  |
| fab_08 | Market Analysis | 0.667 | 0 | 2524 |  |
| fab_09 | Comparables | 0.423 | 0 | 3194 |  |
| fab_10 | Comparables | 0.875 | 0 | 2595 |  |
| fab_11 | Comparables | 0.000 | 0 | 2736 |  |
| fab_12 | Precedents | 1.000 | 1 | 5188 |  |
| fab_13 | Precedents | 0.600 | 0 | 5561 |  |
| fab_14 | Precedents | 0.889 | 0 | 1939 |  |
| fab_15 | Adjustments | 0.036 | 0 | 33068 |  |
| fab_16 | Adjustments | 0.000 | 0 | 106 |  |
| fab_17 | Adjustments | 0.000 | 0 | 220 |  |
| fab_18 | Earnings Analysis | 0.667 | 0 | 9069 |  |
| fab_19 | Earnings Analysis | 1.000 | 1 | 2938 |  |
| fab_20 | Earnings Analysis | 0.900 | 0 | 3130 |  |
| fab_21 | Disclosure Analysis | 0.846 | 0 | 3910 |  |
| fab_22 | Disclosure Analysis | 1.000 | 1 | 5977 |  |
| fab_23 | Disclosure Analysis | 0.917 | 0 | 6293 |  |
| fab_24 | Financial Modeling | — | — | 0 | RuntimeError: Error in agent execution: No response content or tool calls |
| fab_25 | Financial Modeling | 0.200 | 0 | 4408 |  |
| fab_26 | Financial Modeling | 0.333 | 0 | 3862 |  |
