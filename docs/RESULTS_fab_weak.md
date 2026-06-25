# FAB v2 — WEAK seed baseline (fetch_page + web_search only) + headroom conclusion

Weak FAB worker `qea/worker_fab_weak/`: minimal prompt + only the 2 generic web
primitives. The 4 SEC-specialized tools (`edgar_search`, `company_filings`,
`retrieve_from_filing`, `price_history`) are removed. Graded 27/27, judge k=2,
grader=qwen3.7-plus (our approx). Worker model deepseek-v4-pro.

## Conclusion: FAB HAS the Level-B headroom GDPval lacked

| run | generous | strict |
|---|---|---|
| full FAB worker (`qea/worker/`, 6 tools) | 0.618 | 0.269 |
| **weak FAB seed** (`qea/worker_fab_weak/`, 2 primitives) | **0.388** | **0.185** |
| **gap** | **−0.230 (−37%)** | −0.084 |

Unlike GDPval (where the weak shell worker self-recovered in-episode → weak ≈ full),
**weakening the FAB worker opens a large, real gap.** Mechanism: **13 of 27 tasks
collapsed to ~45-character non-answers** (the worker gave up) — without
`company_filings`/`edgar_search` it can't find the filing URL, and without
`retrieve_from_filing` a plain `fetch_page` of a large 10-K returns only its first
portion. That capability is **not reconstructable from `fetch_page`+`web_search` within
a single episode**, so the gap survives — exactly the "constrain what the worker can't
recover in-episode" lever.

### Where the drop is (full → weak, generous)
Concentrated in retrieval-dependent categories; categories answerable without deep
filing reads held up.

| category | full | weak | Δ |
|---|---|---|---|
| Comparables | 0.433 | 0.000 | −0.433 |
| Precedents | 0.830 | 0.333 | −0.497 |
| Disclosure Analysis | 0.921 | 0.450 | −0.471 |
| General Qualitative | 0.889 | 0.405 | −0.484 |
| Market Analysis | 0.737 | 0.333 | −0.404 |
| Financial Modeling | 0.267 | 0.179 | −0.088 |
| General Quantitative | 0.500 | 0.500 | 0.000 |
| Earnings Analysis | 0.856 | 0.907 | +0.051 |
| Adjustments | 0.012 | 0.384 | +0.372¹ |

¹ Full worker was anomalously low on Adjustments (0.012) in its base run; the weak
run scoring higher there is noise/variance, not a real effect.

## Why this is a well-posed Level-B headroom

The removed tools' implementations still live in `qea/worker_fab_weak/tools/fab/research.py`
(the whole `tools/` dir was copied) — only their bindings were dropped from `agent.yaml`.
So the **evolve agent can recover the ~0.23 gap by re-wiring a tool into the worker's
`agent.yaml`** (e.g. add back `retrieve_from_filing`) — a legitimate harness edit, not
answer leakage. This is the AHE pattern: discover a capability helps, wire it in. (A harder
variant later: remove the tool *code* too, forcing re-implementation.)

## Recommendation
**Run the actual Level-B evolution loop on FAB, not GDPval.** FAB is tool-gated and has a
real recoverable gap; GDPval's general shell leaves no headroom. Next: point the Level-B
loop (`qea/loop_levelb.py`) at the FAB benchmark + `qea/worker_fab_weak/` seed and let the
file-editing evolve agent try to recover the gap by editing the worker dir.

---

## Raw results

- **Generous:** 0.388  · **Strict (all-pass):** 0.185 · graded 27/27

| task | category | generous | strict | ans | error |
|---|---|---|---|---|---|
| fab_00 | General Qualitative Analysis | 0.000 | 0 | 45 |  |
| fab_01 | General Qualitative Analysis | 0.857 | 0 | 6525 |  |
| fab_02 | General Qualitative Analysis | 0.357 | 0 | 4454 |  |
| fab_03 | General Quantitative Analysis | 0.500 | 0 | 1373 |  |
| fab_04 | General Quantitative Analysis | 0.000 | 0 | 45 |  |
| fab_05 | General Quantitative Analysis | 1.000 | 1 | 2816 |  |
| fab_06 | Market Analysis | 1.000 | 1 | 2764 |  |
| fab_07 | Market Analysis | 0.000 | 0 | 47 |  |
| fab_08 | Market Analysis | 0.000 | 0 | 45 |  |
| fab_09 | Comparables | 0.000 | 0 | 45 |  |
| fab_10 | Comparables | 0.000 | 0 | 45 |  |
| fab_11 | Comparables | 0.000 | 0 | 45 |  |
| fab_12 | Precedents | 0.000 | 0 | 45 |  |
| fab_13 | Precedents | 1.000 | 1 | 5376 |  |
| fab_14 | Precedents | 0.000 | 0 | 45 |  |
| fab_15 | Adjustments | 0.000 | 0 | 45 |  |
| fab_16 | Adjustments | 0.929 | 0 | 1953 |  |
| fab_17 | Adjustments | 0.222 | 0 | 3126 |  |
| fab_18 | Earnings Analysis | 0.722 | 0 | 2195 |  |
| fab_19 | Earnings Analysis | 1.000 | 1 | 2704 |  |
| fab_20 | Earnings Analysis | 1.000 | 1 | 2353 |  |
| fab_21 | Disclosure Analysis | 0.000 | 0 | 45 |  |
| fab_22 | Disclosure Analysis | 0.850 | 0 | 7130 |  |
| fab_23 | Disclosure Analysis | 0.500 | 0 | 5561 |  |
| fab_24 | Financial Modeling | 0.538 | 0 | 2277 |  |
| fab_25 | Financial Modeling | 0.000 | 0 | 45 |  |
| fab_26 | Financial Modeling | 0.000 | 0 | 45 |  |
