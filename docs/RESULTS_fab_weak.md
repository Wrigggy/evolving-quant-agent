# FAB v2 — weak seed baseline — CHECKPOINT (run PAUSED, resume later)

**Status:** PAUSED before completion. The weak-FAB scoring run was stopped after setup;
**no partial results were saved** (the run script only writes this file at the end), so the
run is restartable from scratch. Setup is committed on branch `qea/fab-weak` (`4b7c40f`).

## What is staged
- **Weak FAB worker** `qea/worker_fab_weak/`: minimal prompt + only the 2 generic web
  primitives (`fetch_page`, `web_search`). The 4 SEC-specialized tools
  (`edgar_search`, `company_filings`, `retrieve_from_filing`, `price_history`) are removed
  and left for evolution to (re)discover.
- **Run script** `scripts/nexau_fab_run.py` is worker-dir/output configurable
  (`QEA_WORKER_DIR`, `QEA_RESULTS_MD`).

## Hypothesis under test
FAB is **tool-gated** (unlike GDPval's general shell, which let the weak worker self-recover
in one episode). Without `retrieve_from_filing` a plain `fetch_page` of a large 10-K returns
only its first portion, and without `company_filings`/`edgar_search` the filing URL is hard to
find — a deep-filing-read + URL-discovery gap the worker can't reconstruct within an episode.
Expect **weak FAB << full FAB** if FAB has the Level-B headroom GDPval lacked.

## Baseline to compare against
- Full FAB NexAU worker: **generous 0.618 / strict 0.269** (`docs/RESULTS_fab_nexau.md`).

## To resume (exact command)
```bash
cd /Users/kevinwu/Coding/evolving-quant-agent
export http_proxy=http://127.0.0.1:7897 https_proxy=http://127.0.0.1:7897 all_proxy=socks5://127.0.0.1:7897
export QEA_WORKER_DIR=qea/worker_fab_weak QEA_RESULTS_MD=docs/RESULTS_fab_weak.md QEA_FAB_CONCURRENCY=4
.venv-nexau/bin/python scripts/nexau_fab_run.py        # ~27 tasks, conc 4, ~30-60 min
```
Running it overwrites this checkpoint file with the actual results table.
