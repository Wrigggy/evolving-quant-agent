QEA QUANTCODEEVAL RUNTIME ADAPTER:
- The source paper is available at /app/data/paper_text.md.
- Save the submitted module as /app/output/strategy.py.
- Do not inspect checker, reference, property, or verdict files.

# Sample Instruction: Volatility-Managed Portfolios

Paper: Moreira & Muir (2017), "Volatility-Managed Portfolios", *Journal of Finance* 72(4).

This task instruction defines the function interface and implementation requirements for the
canonical Mkt-RF realized-variance volatility-managed strategy
(Table 1, "Mkt" row, full sample 1926-2015).

## Required Functions

All functions must be importable as **top-level module functions** of the agent's
strategy file. Argument names should match the Input column names (or the
suffix `_df`). Functions are pure (no I/O besides the entry point `main`).

| # | Function                                                | Key Output Columns                |
|---|---------------------------------------------------------|-----------------------------------|
| 1 | `compute_realized_variance(daily_df)`                   | `date, rv`                        |
| 2 | `compute_weight(rv_df, c)`                              | `date, weight`                    |
| 3 | `compute_managed_returns(weight_df, monthly_df)`        | `date, f_managed`                 |
| 4 | `solve_normalization_constant(rv_df, monthly_df)`       | scalar `c` (float)                |
| 5 | `compute_alpha_appraisal(managed_df, monthly_df)`       | dict with `alpha, sigma_eps, ...` |
| 6 | `main(data_dir=None)`                                   | entry point; writes `trade_log.json` |

### IO Shape

#### 1. `compute_realized_variance(daily_df: pd.DataFrame) -> pd.DataFrame`
- **Input**: `daily_df` with columns `[date, mktrf]` (decimal daily Mkt-RF excess
  returns; one row per trading day).
- **Output**: DataFrame with columns `[date, rv]` indexed by **calendar
  month-end** (one row per calendar month). `rv` is the realized variance of
  daily mktrf within that calendar month.
- **Temporal anchor**: `rv` at month-end date `m` uses only daily returns whose
  date falls in calendar month `m` (i.e. `≤ m`).

#### 2. `compute_weight(rv_df: pd.DataFrame, c: float) -> pd.DataFrame`
- **Input**: `rv_df` from (1); scalar `c`.
- **Output**: DataFrame with columns `[date, weight]` indexed by month-end. The
  weight at date `t` (month-end) is the weight applied to the **next month's**
  factor return.
- **Lag rule (R3 below)**: `weight[t] = c / rv[t]`. The first row `t = t_0`
  produces a weight that is meant to be applied to the return over month `t_0+1`.

#### 3. `compute_managed_returns(weight_df, monthly_df) -> pd.DataFrame`
- **Input**: `weight_df` from (2); `monthly_df` with columns `[date, mktrf]`
  (decimal monthly Mkt-RF returns, one row per calendar month).
- **Output**: DataFrame with columns `[date, f_managed]` where `date` is the
  realization month-end and `f_managed[t+1] = weight[t] * monthly_df.mktrf[t+1]`.
  The first month of the sample (no prior weight) is **dropped** (no NaN
  imputation).

#### 4. `solve_normalization_constant(rv_df, monthly_df) -> float`
- **Input**: `rv_df`, `monthly_df` covering the same time range.
- **Output**: scalar `c` such that `std(f_managed) == std(monthly_df.mktrf)` over
  the sample. This is full-sample (paper footnote 5: "c has no effect on Sharpe").
- One acceptable solution: compute unscaled managed series `m_t = mktrf_t / rv_{t-1}`,
  then `c = std(mktrf) / std(m)`.

#### 5. `compute_alpha_appraisal(managed_df, monthly_df) -> dict`
- **Input**: `managed_df` from (3); `monthly_df`.
- **Output**: dict with keys (all `float`, monthly units unless noted):
  - `alpha_monthly` — OLS intercept of f_managed on mktrf (decimal)
  - `alpha_annual_pct` — `alpha_monthly * 12 * 100`
  - `beta` — slope coefficient
  - `r_squared`
  - `sigma_eps_monthly` — residual std (decimal)
  - `appraisal_ratio_annual` — `(alpha_monthly / sigma_eps_monthly) * sqrt(12)`
  - `n_obs` — number of overlapping monthly observations

#### 6. `main(data_dir: str | Path = None) -> dict`
- **Input**: optional `data_dir` containing `ff3_monthly.csv` and `ff3_daily.csv`
  (column schema: `[date, mktrf, smb, hml, rf]`, decimal units). When `None`,
  accepts `--data-dir` argparse.
- **Output**: writes `trade_log.json` next to the script with keys
  - `metrics`: dict with `sharpe`, `ann_return`, `max_drawdown`, `calmar`,
    `cumulative_return`, `num_trades`, plus paper-specific
    `alpha_annual_pct`, `appraisal_ratio_annual`, `r_squared`, `n_obs`, `c`.
  - `monthly_returns`: list of dicts `[{date, weight, f_managed}]`.
  Returns the `metrics` dict.

## Declared Task Conventions

### R1: Realized variance is the SUM of squared daily excess returns
- **source**: §2.2 — "we keep the portfolio construction even simpler by using
  the previous month realized variance as a proxy for the conditional variance"
- Implementation: `rv[m] = sum_{d in calendar month m} mktrf_d ** 2`. Do **not**
  use `pd.var()` (which de-means and uses `N-1` denominator). For zero-mean
  daily excess returns the difference is small but non-zero.

### R2: Calendar-month windows, not rolling 22-day
- The intramonth window is the **calendar month**, defined by the `date` field
  in `daily_df`. Do not use `rolling(22).var()` — that crosses month boundaries.

### R3: Strict one-month lag — weight at t uses RV of month t-1
- **source**: §2.2 — "previous month realized variance"
- Required pipeline: at the formation moment (end of month `t-1`), compute
  `rv[t-1]`; produce `weight[t] = c / rv[t-1]`; apply weight to `mktrf[t]` to get
  `f_managed[t]`. The variance and the return must NOT come from the same
  calendar month.

### R4: Linear scaling — no thresholding, no long/short signal
- **source**: §2.2 — "we approximate the conditional risk-return trade-off by
  the inverse of the conditional variance"
- The factor exposure is **continuous in (0, ∞)**. There is no median split, no
  long/short conversion, and no quantile bucketing.

### R5: No leverage cap in the baseline
- **source**: Table 1 main result is reported gross of leverage constraints.
- The unscaled weight `1/RV_{t-1}` may exceed 5x in calm months. Do **not** clip
  the weight, do **not** add margin/borrow constraints, do **not** cap at 1.0.

### R6: Constant c is computed once on the full sample
- **source**: §2.1 footnote 5 — "Importantly c has no effect on our strategy's
  Sharpe ratio, thus the fact that we use the full sample to compute c does not
  impact our results."
- `c` is a single scalar, not a rolling/per-period statistic. It is solved
  exactly once at the end (or via closed form `c = std(mktrf)/std(mktrf/rv.shift(1))`).

### R7: Annualization conventions
- Sharpe ratio annualization factor: `sqrt(12)` (monthly returns).
- Alpha annualization for reporting: `alpha_monthly * 12` (in decimal) or
  `* 1200` for percent.
- Appraisal ratio annualization: `(alpha_m / sigma_eps_m) * sqrt(12)`.

### R8: Drop first month of sample (boundary condition)
- The first month has no prior RV, so `f_managed[t_0]` is undefined. Drop it.
  Do not impute weight=1, do not forward-fill, do not zero-fill.

### R9: Use mktrf (excess return), not total return
- Both `daily_df.mktrf` and `monthly_df.mktrf` are already excess returns.
  Do NOT add `rf` back. The managed series `f_managed` is also an excess return.

### R10: Period and observation count
- Backtest period: 1926-07-31 .. 2015-12-31 (full Ken French monthly file).
- Expected number of managed observations after dropping the first month:
  `len(monthly_df) - 1` ≈ 1073 months (paper Table 1 "Observations" col reports
  1065 — the small discrepancy reflects paper's truncation; 1073 is acceptable).

## Performance Targets (informational, not enforced by the task requirements)

| Metric                           | Paper Table 1 (Mkt)  | Released task range |
|----------------------------------|----------------------|--------------------------|
| Annualized Sharpe (managed)       | 0.52                 | 0.45 - 0.60              |
| Annualized α (%)                  | 4.86                 | 4.0 - 5.5                |
| Appraisal ratio                   | 0.34                 | 0.28 - 0.40              |
| R²                                | 0.37                 | 0.32 - 0.42              |
| Observations                      | 1065                 | 1070 - 1075              |

## Forbidden Patterns (any of the following is a defect)

- Using `rv` of the **same** month as the return (look-ahead).
- Computing rv with `pd.Series.var()` (de-meaning bias) without explicitly
  documenting the choice.
- Clipping or capping the weight.
- Treating the strategy as a long/short signal.
- Annualizing the Sharpe with `sqrt(252)`.
- Adding `rf` to `mktrf`.
