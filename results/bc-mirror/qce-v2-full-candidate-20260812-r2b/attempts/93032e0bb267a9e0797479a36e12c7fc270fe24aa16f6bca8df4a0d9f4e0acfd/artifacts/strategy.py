"""Volatility-Managed Portfolios (Moreira & Muir 2017) -- canonical Mkt-RF strategy.

Implements the realized-variance volatility-managed market portfolio described
in the paper (Section 2.2, Table 1 "Mkt" row, full sample 1926-2015):

    f_managed[t+1] = (c / RV[t]) * mktrf[t+1]

where RV[t] is the realized variance (SUM of squared daily excess returns) of
calendar month t, mktrf are decimal monthly excess returns, and the constant c
is chosen so that the managed series has the same unconditional standard
deviation as the buy-and-hold market factor (paper footnote 5).

All arithmetic is in decimal (not percent) units.  The weight is continuous
(c / RV), never clipped or capped, and no rf is added back to mktrf.
"""

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# 1. Realized variance (R1, R2)
# ---------------------------------------------------------------------------
def compute_realized_variance(daily_df):
    """Realized variance of daily mktrf within each calendar month.

    rv[m] = sum_{d in calendar month m} mktrf_d ** 2   (NOT pd.var / N-1).

    Output is one row per calendar month, dated at the calendar month-end, so
    it aligns exactly with the Ken French monthly file dates.
    """
    df = daily_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    df["_ym"] = df["date"].dt.to_period("M")

    grouped = df.groupby("_ym", sort=True).agg(
        rv=("mktrf", lambda s: float((s.astype(float) ** 2).sum()))
    ).reset_index()
    grouped["date"] = grouped["_ym"].dt.to_timestamp(how="end")
    return grouped[["date", "rv"]]


# ---------------------------------------------------------------------------
# 2. Weight = c / RV (R3, R4, R5)
# ---------------------------------------------------------------------------
def compute_weight(rv_df, c):
    """Weight at month-end t equals c / rv[t]; applied to the NEXT month's return.

    The first row (t = t_0) produces the weight applied to month t_0 + 1.
    Weight is continuous in (0, inf): no clipping, no capping, no signal.
    """
    df = rv_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    df["weight"] = c / df["rv"].astype(float)
    return df[["date", "weight"]]


# ---------------------------------------------------------------------------
# 3. Managed returns (R3, R8)
# ---------------------------------------------------------------------------
def compute_managed_returns(weight_df, monthly_df):
    """f_managed[t+1] = weight[t] * monthly_df.mktrf[t+1].

    Realization month-ends are the output dates.  The first month of the
    sample (no prior weight) is dropped -- no NaN imputation.
    """
    w = weight_df.copy()
    m = monthly_df.copy()
    w["_p"] = pd.to_datetime(w["date"]).dt.to_period("M")
    m["_p"] = pd.to_datetime(m["date"]).dt.to_period("M")
    w = w.drop_duplicates("_p").set_index("_p")["weight"]
    m = m.drop_duplicates("_p").set_index("_p")["mktrf"]

    idx = m.index.intersection(w.index)
    weight_prev = w.reindex(idx).shift(1)          # weight at t-1 (strict lag)
    managed = m.reindex(idx) * weight_prev         # f_managed[t] = w[t-1] * mktrf[t]

    out = pd.DataFrame(
        {
            "date": idx.to_timestamp(how="end"),
            "f_managed": managed.astype(float).values,
        }
    )
    out = out.dropna(subset=["f_managed"])
    return out[["date", "f_managed"]].reset_index(drop=True)


# ---------------------------------------------------------------------------
# 4. Normalization constant (R6, footnote 5)
# ---------------------------------------------------------------------------
def solve_normalization_constant(rv_df, monthly_df):
    """Full-sample scalar c such that std(f_managed) == std(monthly mktrf).

    Closed form: m_t = mktrf_t / rv_{t-1};  c = std(mktrf) / std(m)
    computed over the overlapping months that have a prior-month RV.
    """
    rv = rv_df.copy()
    m = monthly_df.copy()
    rv["_p"] = pd.to_datetime(rv["date"]).dt.to_period("M")
    m["_p"] = pd.to_datetime(m["date"]).dt.to_period("M")
    rv = rv.drop_duplicates("_p").set_index("_p")["rv"]
    m = m.drop_duplicates("_p").set_index("_p")["mktrf"]

    idx = m.index.intersection(rv.index)
    rv_prev = rv.reindex(idx).shift(1)             # rv of the previous month
    mktrf = m.reindex(idx).astype(float)

    mask = rv_prev.notna()
    m_scaled = mktrf[mask] / rv_prev[mask]
    c = mktrf[mask].std(ddof=1) / m_scaled.std(ddof=1)
    return float(c)


# ---------------------------------------------------------------------------
# 5. Appraisal (OLS of f_managed on mktrf)
# ---------------------------------------------------------------------------
def compute_alpha_appraisal(managed_df, monthly_df):
    """OLS: f_managed = alpha + beta * mktrf + eps (monthly, decimal units).

    Returns a dict with alpha_monthly, alpha_annual_pct, beta, r_squared,
    sigma_eps_monthly, appraisal_ratio_annual, n_obs.
    """
    md = managed_df.copy()
    m = monthly_df.copy()
    md["_p"] = pd.to_datetime(md["date"]).dt.to_period("M")
    m["_p"] = pd.to_datetime(m["date"]).dt.to_period("M")
    md = md.drop_duplicates("_p").set_index("_p")["f_managed"]
    m = m.drop_duplicates("_p").set_index("_p")["mktrf"]

    idx = md.index.intersection(m.index)
    y = md.reindex(idx).astype(float).values
    x = m.reindex(idx).astype(float).values
    n = int(len(y))

    if n < 3:
        return {
            "alpha_monthly": float("nan"),
            "alpha_annual_pct": float("nan"),
            "beta": float("nan"),
            "r_squared": float("nan"),
            "sigma_eps_monthly": float("nan"),
            "appraisal_ratio_annual": float("nan"),
            "n_obs": n,
        }

    x_mean = x.mean()
    y_mean = y.mean()
    x_dm = x - x_mean
    y_dm = y - y_mean
    ss_xx = float(np.dot(x_dm, x_dm))

    if ss_xx <= 0.0:
        beta = float("nan")
        alpha = float("nan")
        r2 = float("nan")
        sigma_eps = float("nan")
    else:
        beta = float(np.dot(x_dm, y_dm) / ss_xx)
        alpha = float(y_mean - beta * x_mean)
        resid = y - (alpha + beta * x)
        ss_res = float(np.dot(resid, resid))
        ss_tot = float(np.dot(y_dm, y_dm))
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0.0 else float("nan")
        sigma_eps = float(math.sqrt(ss_res / (n - 2.0)))

    appraisal = (
        (alpha / sigma_eps) * math.sqrt(12.0)
        if sigma_eps is not None and not np.isnan(sigma_eps) and sigma_eps > 0.0
        else float("nan")
    )

    return {
        "alpha_monthly": alpha,
        "alpha_annual_pct": alpha * 12.0 * 100.0,
        "beta": beta,
        "r_squared": r2,
        "sigma_eps_monthly": sigma_eps,
        "appraisal_ratio_annual": appraisal,
        "n_obs": n,
    }


# ---------------------------------------------------------------------------
# 6. Entry point
# ---------------------------------------------------------------------------
def _load_data(data_dir):
    data_dir = Path(data_dir)
    monthly = pd.read_csv(data_dir / "ff3_monthly.csv", parse_dates=["date"])
    daily = pd.read_csv(data_dir / "ff3_daily.csv", parse_dates=["date"])
    return daily, monthly


def main(data_dir=None):
    """Run the full strategy pipeline; write trade_log.json next to the script.

    Returns the metrics dict.
    """
    if data_dir is None:
        parser = argparse.ArgumentParser(description="Volatility-managed portfolios")
        parser.add_argument("--data-dir", default=None,
                            help="Directory containing ff3_monthly.csv and ff3_daily.csv")
        args, _ = parser.parse_known_args()
        data_dir = args.data_dir

    if data_dir is None:
        # Default to the public data directory alongside this repo layout.
        data_dir = Path(__file__).resolve().parent.parent / "data"

    daily, monthly = _load_data(data_dir)

    # Pipeline (R3/R6: c solved once on the full sample).
    rv = compute_realized_variance(daily)
    c = solve_normalization_constant(rv, monthly)
    weight = compute_weight(rv, c)
    managed = compute_managed_returns(weight, monthly)
    appraisal = compute_alpha_appraisal(managed, monthly)

    f = managed["f_managed"].astype(float)

    # ---- metrics ----
    ann_factor = math.sqrt(12.0)
    sharpe = float(f.mean() / f.std(ddof=1) * ann_factor)
    ann_return = float(f.mean() * 12.0)
    cum = (1.0 + f).cumprod()
    peak = cum.cummax()
    drawdown = cum / peak - 1.0
    max_drawdown = float(drawdown.min())
    calmar = float(ann_return / abs(max_drawdown)) if max_drawdown < 0.0 else float("nan")
    cumulative_return = float(cum.iloc[-1] - 1.0)
    num_trades = int(len(f))  # one monthly rebalance per managed month

    metrics = {
        "sharpe": sharpe,
        "ann_return": ann_return,
        "max_drawdown": max_drawdown,
        "calmar": calmar,
        "cumulative_return": cumulative_return,
        "num_trades": num_trades,
        "alpha_annual_pct": appraisal["alpha_annual_pct"],
        "appraisal_ratio_annual": appraisal["appraisal_ratio_annual"],
        "r_squared": appraisal["r_squared"],
        "n_obs": appraisal["n_obs"],
        "c": float(c),
    }

    # ---- trade log: month-end, applied weight, realized managed return ----
    w = weight.copy()
    w["_p"] = pd.to_datetime(w["date"]).dt.to_period("M")
    w = w.drop_duplicates("_p").set_index("_p")["weight"]
    w_prev = w.shift(1)  # at period p holds the weight applied to month p

    mdates = pd.to_datetime(managed["date"])
    periods = mdates.dt.to_period("M")
    applied_weight = w_prev.reindex(periods).astype(float).values

    monthly_returns = []
    for d, wt, fv in zip(mdates, applied_weight, f.values):
        monthly_returns.append(
            {
                "date": d.strftime("%Y-%m-%d"),
                "weight": float(wt),
                "f_managed": float(fv),
            }
        )

    trade_log = {"metrics": metrics, "monthly_returns": monthly_returns}

    out_path = Path(__file__).resolve().parent / "trade_log.json"
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(trade_log, fh, indent=2)

    return metrics


if __name__ == "__main__":
    main()
