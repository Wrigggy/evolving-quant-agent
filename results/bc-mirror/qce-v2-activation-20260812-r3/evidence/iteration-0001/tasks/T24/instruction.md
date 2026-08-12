QEA QUANTCODEEVAL RUNTIME ADAPTER:
- The source paper is available at /app/data/paper_text.md.
- Save the submitted module as /app/output/strategy.py.
- Do not inspect checker, reference, property, or verdict files.

# Interface Contract: Earnings Extrapolation Time-Series Market Return Prediction

## Required Functions

All required functions must be importable as top-level module functions.
Parameter names should match the Input column names (or append `_df` suffix).

| # | Function | Key Output Columns |
|---|----------|--------------------|
| 1 | `compute_demeaned_signal(ff_factors_monthly)` | `is_newsy`, `sum_4_newsy`, `expanding_mean`, `raw_signal`, `demeaned_signal` |
| 2 | `compute_regression_coefficient(demeaned_signal_df)` | `mkt_demean`, `signal_lag`, `regression_coefficient` |
| 3 | `compute_portfolio_weight(regression_coefficient_df)` | `raw_weight`, `raw_excess_return`, `portfolio_weight` |
| 4 | `compute_strategy_returns(portfolio_weight_df)` | `strategy_return` |

### IO Shape

#### 1. `compute_demeaned_signal(ff_factors_monthly: pd.DataFrame) -> pd.DataFrame`
- **Input:** `ff_factors_monthly` with columns `[date, mkt, mkt_rf, rf, ...]`
- **Output:** Input DataFrame augmented with columns `[is_newsy, sum_4_newsy, expanding_mean, raw_signal, demeaned_signal]`

#### 2. `compute_regression_coefficient(demeaned_signal_df: pd.DataFrame) -> pd.DataFrame`
- **Input:** `demeaned_signal_df` with columns `[date, mkt, mkt_rf, rf, expanding_mean, demeaned_signal, ...]`
- **Output:** Input DataFrame augmented with columns `[mkt_demean, signal_lag, regression_coefficient]`

#### 3. `compute_portfolio_weight(regression_coefficient_df: pd.DataFrame) -> pd.DataFrame`
- **Input:** `regression_coefficient_df` with columns `[date, mkt, mkt_rf, rf, demeaned_signal, regression_coefficient, ...]`
- **Output:** Input DataFrame augmented with columns `[raw_weight, raw_excess_return, portfolio_weight]`

#### 4. `compute_strategy_returns(portfolio_weight_df: pd.DataFrame) -> pd.DataFrame`
- **Input:** `portfolio_weight_df` with columns `[date, mkt_rf, rf, portfolio_weight, ...]`
- **Output:** Input DataFrame augmented with column `[strategy_return]`

## Declared Task Conventions

### R1: Total market return, not excess return
- **source**: paper-text-anchor

The signal construction and regression use total market return (Mkt-RF + RF),
not excess return (Mkt-RF). The data file provides both; use the `mkt` column.

### R2: Expanding window mean endpoint
- **source**: paper-text-anchor

The expanding window mean must be strictly causal — it must not include the
current month's observation. Use only historical data available at the time.

The `expanding_mean` column in the output of `compute_demeaned_signal` refers
to the expanding mean of the total market return column `mkt` (not of any
intermediate signal quantity).

### R3: Constant volatility scaling
- **source**: paper-text-anchor

The volatility-scaling target is a **paper-specified fixed constant** — a
single numeric value prescribed by the paper text, independent of the
realized sample. It is NOT a full-sample standard-deviation estimate, a
rolling estimate, nor the market's own realized volatility. The paper
states this target explicitly; locate and use that value.

The `shift(1)` lag on `portfolio_weight` (no same-month trading) remains
mandatory (see R4).

### R4: `strategy_return` funding convention is not prescribed
- **source**: paper-text-anchor (Appendix C.1 describes a market-neutral zero-cost portfolio; main text reports alphas on excess returns)

The paper does not fix a single convention for the final `strategy_return`
column's treatment of the risk-free funding leg. The `shift(1)` lag on
`portfolio_weight` IS mandatory (no same-month trading). Downstream
performance metrics must be internally consistent with whichever convention
is adopted.
