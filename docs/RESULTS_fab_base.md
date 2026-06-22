# FAB v2 base test — Stirrup + free EDGAR/price/web tools (our-grader approx)

Graded 26/27 | judge k=2 | grader=qwen3.7-plus (NOT official Vals).

- **Generous (mean partial-credit %):** 0.659
- **Strict (all-pass rate):** 0.231

### By category
| category | n | generous | strict |
|----------|---|----------|--------|
| Adjustments | 3 | 0.595 | 0.000 |
| Comparables | 2 | 0.430 | 0.000 |
| Disclosure Analysis | 3 | 0.680 | 0.000 |
| Earnings Analysis | 3 | 0.778 | 0.667 |
| Financial Modeling | 3 | 0.396 | 0.000 |
| General Qualitative Analysis | 3 | 0.889 | 0.667 |
| General Quantitative Analysis | 3 | 0.542 | 0.333 |
| Market Analysis | 3 | 0.793 | 0.333 |
| Precedents | 3 | 0.752 | 0.000 |

### Per task
| task | category | generous | strict | ans chars | error |
|------|----------|----------|--------|-----------|-------|
| fab_00 | General Qualitative Analysis | 0.667 | 0 | 14249 |  |
| fab_01 | General Qualitative Analysis | 1.000 | 1 | 9680 |  |
| fab_02 | General Qualitative Analysis | 1.000 | 1 | 7965 |  |
| fab_03 | General Quantitative Analysis | 0.500 | 0 | 831 |  |
| fab_04 | General Quantitative Analysis | 0.125 | 0 | 4052 |  |
| fab_05 | General Quantitative Analysis | 1.000 | 1 | 2769 |  |
| fab_06 | Market Analysis | 1.000 | 1 | 2879 |  |
| fab_07 | Market Analysis | 0.545 | 0 | 2840 |  |
| fab_08 | Market Analysis | 0.833 | 0 | 3068 |  |
| fab_09 | Comparables | 0.423 | 0 | 5163 |  |
| fab_10 | Comparables | 0.438 | 0 | 3128 |  |
| fab_11 | Comparables | — | — | 0 | JSONDecodeError: Expecting value: line 271 column 1 (char 1485) |
| fab_12 | Precedents | 0.667 | 0 | 5779 |  |
| fab_13 | Precedents | 0.700 | 0 | 11036 |  |
| fab_14 | Precedents | 0.889 | 0 | 2454 |  |
| fab_15 | Adjustments | 0.857 | 0 | 11310 |  |
| fab_16 | Adjustments | 0.929 | 0 | 2097 |  |
| fab_17 | Adjustments | 0.000 | 0 | 0 |  |
| fab_18 | Earnings Analysis | 0.333 | 0 | 3850 |  |
| fab_19 | Earnings Analysis | 1.000 | 1 | 2867 |  |
| fab_20 | Earnings Analysis | 1.000 | 1 | 5138 |  |
| fab_21 | Disclosure Analysis | 0.923 | 0 | 5411 |  |
| fab_22 | Disclosure Analysis | 0.700 | 0 | 9417 |  |
| fab_23 | Disclosure Analysis | 0.417 | 0 | 7493 |  |
| fab_24 | Financial Modeling | 0.654 | 0 | 5855 |  |
| fab_25 | Financial Modeling | 0.200 | 0 | 3351 |  |
| fab_26 | Financial Modeling | 0.333 | 0 | 2848 |  |
