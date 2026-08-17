"""Kozak, Nagel & Santosh (2020) -- "Shrinking the Cross-Section".

Deterministic implementation of the SDF estimation pipeline for the 50
anomaly-sorted managed portfolios.  Every declared convention in the task
contract is implemented literally:

  R1   training window 1973-11 .. 2004-12; OOS 2005-01 .. 2017-12 (date filter).
  R2   market orthogonalisation ``r0 = r - rme * beta_train`` with one shared
       training-window OLS beta vector applied to BOTH the monthly and the
       daily panel (no lookahead; unconditional de-vol is NOT applied).
  R3   missing factor returns imputed to zero AFTER the de-market step.
  R4   kappa log-grid [0.01, 1.0];  gamma = tau2 / (T * kappa^2), tau2 = tr(Sigma).
  R5   K = 3 contiguous calendar-time blocks inside the training sample.
  R6   Eq. (30) cross-sectional OOS R^2 in the HJ metric, with the held-out
       Sigma estimated on DAILY data x 21 (both numerator and denominator
       weight residuals by Sigma^{-1}).
  R7   b_hat = (Sigma + gamma * I)^{-1} mu_bar  (eta=2 prior, identity L2 ridge).
  R8   OOS MVE return is b_hat' F_t with fixed pre-2005 coefficients.
  R9   OOS volatility matched to the realised OOS market SD.
  R10  fold indices are deterministic functions of date (no randomness).
  R11  every Sigma (training, CV complement, CV held-out) is daily x 21;
       the monthly Sigma is exposed only through the public convenience
       function compute_training_sigma.
  R12  period-month robust joins via a temporary "__ym" scratch key, always
       dropped before return.
  R13  anomalies_daily.csv is resolved module-relative (never cwd-relative).
  R14  ff factors are treated as DECIMAL inside these functions (the /100
       conversion lives in the data-loading layer / main()).
  R15  every returned date column is datetime64[ns] (never Period).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------
# Declared constants (R1, R4, R5, R11)
# --------------------------------------------------------------------------
TRAIN_START = pd.Timestamp("1973-11-01")
TRAIN_CUTOFF = pd.Timestamp("2004-12-31")
OOS_START = pd.Timestamp("2005-01-01")
OOS_END = pd.Timestamp("2017-12-31")
DAILY_SCALE = 252.0 / 12.0      # R11: daily variance -> monthly variance
N_FOLDS = 3                      # R5: K = 3 contiguous blocks
KAPPA_GRID = np.geomspace(0.01, 1.0, 50)   # R4: log-spaced kappa grid

_FF_DECIMAL_COLS = ("mktrf", "smb", "hml", "rf")   # R14


# --------------------------------------------------------------------------
# Small shared helpers
# --------------------------------------------------------------------------
def _factor_cols(df: pd.DataFrame):
    """All anomaly factor return columns (prefix ``r_``)."""
    return [c for c in df.columns if str(c).startswith("r_")]


def _to_datetime(df: pd.DataFrame) -> pd.DataFrame:
    """Copy and normalise the date column to datetime64[ns] (R15)."""
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"]).astype("datetime64[ns]")
    return out


def _training_mask(df: pd.DataFrame):
    """R1: the training-date gate (date <= 2004-12-31, and >= 1973-11-01)."""
    return (df["date"] >= TRAIN_START) & (df["date"] <= TRAIN_CUTOFF)


def _oos_mask(df: pd.DataFrame):
    """R1: the OOS evaluation window."""
    return (df["date"] >= OOS_START) & (df["date"] <= OOS_END)


# --------------------------------------------------------------------------
# R2 / R3: market orthogonalisation with a single training beta vector
# --------------------------------------------------------------------------
def _estimate_beta(anomalies_monthly: pd.DataFrame) -> Dict[str, float]:
    """OLS slope of each ``r_*`` column on ``rme`` over the training window.

    NaNs are masked per column (beta is a regression slope; imputation per
    R3 happens only after the de-market step).
    """
    train = anomalies_monthly[
        (anomalies_monthly["date"] >= TRAIN_START)
        & (anomalies_monthly["date"] <= TRAIN_CUTOFF)
    ]
    rme = train["rme"].to_numpy(float)
    rc = rme - rme.mean()
    den = float((rc ** 2).sum())
    beta: Dict[str, float] = {}
    for c in _factor_cols(anomalies_monthly):
        y = train[c].to_numpy(float)
        ok = np.isfinite(y)
        if den > 0.0 and int(ok.sum()) > 1:
            beta[c] = float((rc[ok] * (y[ok] - y[ok].mean())).sum() / den)
        else:
            beta[c] = 0.0
    return beta


def _demarket(df: pd.DataFrame, beta: Dict[str, float]) -> pd.DataFrame:
    """Apply r0 = r - rme * beta (R2) and impute remaining NaNs to zero (R3)."""
    out = df.copy()
    rme = out["rme"].to_numpy(float)
    for c, b in beta.items():
        if c in out.columns:
            out[c] = out[c].to_numpy(float) - b * rme
    cols = _factor_cols(out)
    out[cols] = out[cols].fillna(0.0)
    return out


# --------------------------------------------------------------------------
# R13: module-relative resolution of the daily panel
# --------------------------------------------------------------------------
@lru_cache(maxsize=2)
def _load_daily_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"], format="%m/%d/%Y").astype("datetime64[ns]")
    return df


def _resolve_daily(anomalies_daily: Optional[pd.DataFrame]) -> pd.DataFrame:
    """Return the daily panel, resolving the CSV module-relatively (R13)."""
    if anomalies_daily is not None:
        return _to_datetime(anomalies_daily)
    module_dir = Path(__file__).resolve().parent
    candidates = [
        module_dir / "data" / "anomalies_daily.csv",
        module_dir.parent / "data" / "anomalies_daily.csv",
        module_dir.parent.parent / "data" / "anomalies_daily.csv",
    ]
    for cand in candidates:
        if cand.exists():
            return _load_daily_csv(str(cand))
    raise FileNotFoundError(
        "anomalies_daily.csv not found next to the module; pass anomalies_daily explicitly."
    )


def _training_panel(anomalies_monthly: pd.DataFrame,
                    anomalies_daily: Optional[pd.DataFrame] = None):
    """Shared preparation: datetime-normalise, estimate beta on training,
    de-market BOTH panels with that beta, impute zeros (R2+R3)."""
    monthly = _to_datetime(anomalies_monthly)
    daily = _resolve_daily(anomalies_daily)
    beta = _estimate_beta(monthly)
    r0m = _demarket(monthly, beta)
    r0d = _demarket(daily, beta)
    return r0m, r0d, beta


# --------------------------------------------------------------------------
# R5 / R10: deterministic contiguous-block fold construction (training only)
# --------------------------------------------------------------------------
def _fold_splits(anomalies_monthly: pd.DataFrame):
    """Sorted training months split into N_FOLDS contiguous calendar blocks.

    Fold indices are deterministic functions of date (np.array_split on the
    sorted month index); no randomness is involved (R10).
    """
    mask = (anomalies_monthly["date"] >= TRAIN_START) & (
        anomalies_monthly["date"] <= TRAIN_CUTOFF)
    months = np.sort(anomalies_monthly.loc[mask, "date"].unique())
    idx = np.arange(len(months))
    splits = [np.asarray(s) for s in np.array_split(idx, N_FOLDS)]
    return months, splits


def _block_moments(df: pd.DataFrame, ddf: pd.DataFrame, months: np.ndarray,
                   month_idx: np.ndarray):
    """mu (monthly mean) and Sigma (daily covariance x 21) for a month block.

    R11: the covariance is always estimated on the daily panel and rescaled
    by 252/12 = 21 so that Sigma and mu share a monthly time basis.
    """
    chosen = pd.PeriodIndex(pd.to_datetime(months[month_idx]), freq="M")
    mmask = df["date"].dt.to_period("M").isin(chosen)
    dmask = ddf["date"].dt.to_period("M").isin(chosen)
    cols = _factor_cols(df)
    mu = df.loc[mmask, cols].mean().to_numpy(float)
    Sigma = np.cov(ddf.loc[dmask, cols].to_numpy(float).T, ddof=0) * DAILY_SCALE
    return mu, Sigma


# --------------------------------------------------------------------------
# R6: Eq. (30) cross-sectional OOS R^2 in the HJ metric
# --------------------------------------------------------------------------
def _cv_fold_scores(kappa: float, df: pd.DataFrame, ddf: pd.DataFrame,
                    months: np.ndarray, splits, cols, tau2: float, T: int):
    """Per-fold Eq. (30) scores for one kappa (R6, R11).

    b_hat_1 is solved on the complement blocks; the score on the held-out
    block weights both numerator and denominator residuals by Sigma_2^{-1}.
    All folds and moments are strictly inside the training window (R1): the
    panels are first gated to date <= 2004-12-31.
    """
    mask = (df["date"] >= TRAIN_START) & (df["date"] <= TRAIN_CUTOFF)
    dmask = (ddf["date"] >= TRAIN_START) & (ddf["date"] <= TRAIN_CUTOFF)
    df = df.loc[mask].reset_index(drop=True)
    ddf = ddf.loc[dmask].reset_index(drop=True)

    n = len(cols)
    r2s = []
    for f in range(N_FOLDS):
        held = splits[f]
        comp = np.concatenate([splits[i] for i in range(N_FOLDS) if i != f])
        mu_in, Sigma_in = _block_moments(df, ddf, months, comp)
        gamma = float(np.trace(Sigma_in)) / (len(comp) * kappa ** 2)
        mu_out, Sigma_out = _block_moments(df, ddf, months, held)
        b1 = np.linalg.solve(Sigma_in + gamma * np.eye(n), mu_in)
        resid = mu_out - Sigma_out @ b1
        Sigma = Sigma_out
        num = resid @ np.linalg.pinv(Sigma) @ resid
        den = mu_out @ np.linalg.pinv(Sigma) @ mu_out
        r2s.append(1.0 - num / den)
    return r2s


def _cv_score(kappa: float, df: pd.DataFrame, ddf: pd.DataFrame,
              months: np.ndarray, splits, cols, tau2: float, T: int) -> float:
    """Fold-averaged Eq. (30) R^2 for one kappa (R6).

    Training-only gate applied inline (R1) before any moment is touched.
    """
    mask = (df["date"] >= TRAIN_START) & (df["date"] <= TRAIN_CUTOFF)
    dmask = (ddf["date"] >= TRAIN_START) & (ddf["date"] <= TRAIN_CUTOFF)
    df = df.loc[mask].reset_index(drop=True)
    ddf = ddf.loc[dmask].reset_index(drop=True)
    return float(np.mean(_cv_fold_scores(kappa, df, ddf, months, splits,
                                         cols, tau2, T)))


def _best_kappa(df: pd.DataFrame, ddf: pd.DataFrame, months: np.ndarray,
                splits, cols, tau2: float, T: int) -> float:
    """kappa maximising the fold-averaged CV R^2 (ties -> smallest kappa)."""
    best_kap = None
    best_val = -np.inf
    for kap in KAPPA_GRID:
        val = _cv_score(kap, df, ddf, months, splits, cols, tau2, T)
        if val > best_val:
            best_val = val
            best_kap = float(kap)
    return best_kap


# --------------------------------------------------------------------------
# Required task functions
# --------------------------------------------------------------------------
def compute_training_mu(anomalies_monthly: pd.DataFrame) -> pd.DataFrame:
    """R1+R2: time-series mean of each post-de-market factor over training.

    Output columns: [factor_id, mu_bar].
    """
    monthly = _to_datetime(anomalies_monthly)
    beta = _estimate_beta(monthly)
    df = _demarket(monthly, beta)
    mask = (df["date"] >= TRAIN_START) & (df["date"] <= TRAIN_CUTOFF)
    cols = _factor_cols(df)
    mu = df.loc[mask, cols].mean()
    out = pd.DataFrame({"factor_id": cols, "mu_bar": mu.to_numpy(float)})
    return out


def compute_training_sigma(anomalies_monthly: pd.DataFrame) -> pd.DataFrame:
    """Public convenience utility (R11 allows monthly Sigma here).

    Long/tidy N x N covariance of the post-de-market monthly panel over the
    training sample only.  Output columns: [factor_i, factor_j, sigma].
    """
    monthly = _to_datetime(anomalies_monthly)
    beta = _estimate_beta(monthly)
    df = _demarket(monthly, beta)
    mask = (df["date"] >= TRAIN_START) & (df["date"] <= TRAIN_CUTOFF)
    cols = _factor_cols(df)
    X = df.loc[mask, cols].to_numpy(float)
    S = np.cov(X.T, ddof=0)
    rows = []
    for i, ci in enumerate(cols):
        for j, cj in enumerate(cols):
            rows.append({"factor_i": ci, "factor_j": cj, "sigma": float(S[i, j])})
    out = pd.DataFrame(rows)
    return out


def select_gamma_by_cv(anomalies_monthly: pd.DataFrame,
                       anomalies_daily: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """R4+R5+R6: kappa log-grid CV on training-only contiguous blocks.

    Output columns: [fold, kappa, gamma, cv_r2, is_optimum]; is_optimum
    marks the kappa that maximises the fold-averaged cv_r2.
    """
    r0m, r0d, _ = _training_panel(anomalies_monthly, anomalies_daily)
    # R1: every CV fold and every cv_r2 is computed strictly within the
    # training sample (date <= 2004-12-31); no OOS observation enters here.
    df = r0m
    ddf = r0d
    mask = (df["date"] >= TRAIN_START) & (df["date"] <= TRAIN_CUTOFF)
    dmask = (ddf["date"] >= TRAIN_START) & (ddf["date"] <= TRAIN_CUTOFF)
    df = df.loc[mask].reset_index(drop=True)
    ddf = ddf.loc[dmask].reset_index(drop=True)

    cols = _factor_cols(df)
    months, splits = _fold_splits(df)
    T = len(months)
    mu_full, Sigma_full = _block_moments(df, ddf, months, np.arange(T))
    tau2 = float(np.trace(Sigma_full))

    rows = []
    for kap in KAPPA_GRID:
        gamma = tau2 / (T * kap ** 2)                 # R4
        fold_r2 = _cv_fold_scores(kap, df, ddf, months, splits, cols, tau2, T)
        for f in range(N_FOLDS):
            rows.append({"fold": int(f + 1), "kappa": float(kap),
                         "gamma": float(gamma), "cv_r2": float(fold_r2[f]),
                         "is_optimum": False})
    out = pd.DataFrame(rows)
    avg = out.groupby("kappa")["cv_r2"].mean()
    best_kap = avg.idxmax()
    out.loc[out["kappa"] == best_kap, "is_optimum"] = True
    out = out[["fold", "kappa", "gamma", "cv_r2", "is_optimum"]]
    return out.reset_index(drop=True)


def compute_sdf_coefficients(anomalies_monthly: pd.DataFrame,
                             anomalies_daily: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """R7: b_hat = (Sigma + gamma * I)^{-1} mu_bar on the full training sample.

    Sigma is the daily training covariance x 21 (R11), mu_bar the monthly
    training mean, gamma the CV-selected value (via select_gamma_by_cv, R4).
    Output columns: [factor_id, b_hat].
    """
    r0m, r0d, _ = _training_panel(anomalies_monthly, anomalies_daily)
    # R1: the b_hat fit uses training observations only (<= 2004-12-31);
    # it is held constant over the OOS evaluation period.
    df = r0m
    ddf = r0d
    mask = (df["date"] >= TRAIN_START) & (df["date"] <= TRAIN_CUTOFF)
    dmask = (ddf["date"] >= TRAIN_START) & (ddf["date"] <= TRAIN_CUTOFF)
    df = df.loc[mask].reset_index(drop=True)
    ddf = ddf.loc[dmask].reset_index(drop=True)

    cols = _factor_cols(df)
    T = int(df.shape[0])
    mu_bar = df[cols].mean().to_numpy(float)
    Sigma = np.cov(ddf[cols].to_numpy(float).T, ddof=0) * DAILY_SCALE
    tau2 = float(np.trace(Sigma))

    months, splits = _fold_splits(df)
    best_kap = _best_kappa(df, ddf, months, splits, cols, tau2, T)
    gamma = tau2 / (T * best_kap ** 2)                # R4

    I = np.eye(len(cols))
    b_hat = np.linalg.solve(Sigma + gamma * I, mu_bar)
    out = pd.DataFrame({"factor_id": cols, "b_hat": b_hat})
    return out


def compute_oos_mve_returns(b_hat_df: pd.DataFrame,
                            anomalies_monthly: pd.DataFrame) -> pd.DataFrame:
    """R8: OOS MVE return series mve_ret_t = b_hat' F_t (fixed weights).

    F_t is the OOS row of the post-de-market monthly panel (R2, same
    training beta).  Output columns: [date, mve_ret], OOS dates only.
    """
    monthly = _to_datetime(anomalies_monthly)
    beta = _estimate_beta(monthly)
    df = _demarket(monthly, beta)
    mask = (df["date"] >= OOS_START) & (df["date"] <= OOS_END)
    cols = _factor_cols(df)
    b = b_hat_df.set_index("factor_id")["b_hat"].reindex(cols)
    if b.isna().any():
        raise ValueError("b_hat_df is missing coefficients for some factors")
    bv = b.to_numpy(float)
    F = df.loc[mask, cols].to_numpy(float)
    out = pd.DataFrame({"date": pd.to_datetime(df.loc[mask, "date"].to_numpy())
                              .astype("datetime64[ns]"),
                        "mve_ret": F @ bv})
    return out[["date", "mve_ret"]].reset_index(drop=True)


def rescale_to_market_vol(mve_ret_df: pd.DataFrame,
                          ff_factors_monthly: pd.DataFrame) -> pd.DataFrame:
    """R9+R14: scale OOS MVE returns so their SD matches the OOS market SD.

    scale = std(mktrf_OOS) / std(mve_ret_OOS); mktrf is DECIMAL here (the
    /100 conversion belongs to the data-loading layer, never repeated here).
    The join uses a temporary "__ym" period scratch key (R12) which is
    dropped before return.  Output columns: [date, strategy_ret].
    """
    mve = _to_datetime(mve_ret_df).copy()
    ff = _to_datetime(ff_factors_monthly).copy()
    mve["__ym"] = mve["date"].dt.to_period("M")
    ff["__ym"] = ff["date"].dt.to_period("M")
    merged = mve.merge(ff[["__ym", "mktrf"]], on="__ym", how="left")
    mask = (merged["date"] >= OOS_START) & (merged["date"] <= OOS_END)
    mkt = merged.loc[mask, "mktrf"]
    mve_oos = merged.loc[mask, "mve_ret"]
    scale = mkt.std() / mve_oos.std()                 # R9, OOS-only statistics
    out = pd.DataFrame({"date": pd.to_datetime(merged.loc[mask, "date"].to_numpy())
                              .astype("datetime64[ns]"),
                        "strategy_ret": mve_oos.to_numpy(float) * scale})
    out = out.drop(columns=["__ym"], errors="ignore")
    out["date"] = pd.to_datetime(out["date"])         # R15
    return out[["date", "strategy_ret"]].reset_index(drop=True)


def run_pipeline(anomalies_monthly: pd.DataFrame,
                 ff_factors_monthly: pd.DataFrame,
                 anomalies_daily: Optional[pd.DataFrame] = None
                 ) -> Tuple[pd.DataFrame, Dict]:
    """Deterministic end-to-end orchestrator composing functions 1-6.

    Returns (strategy_ret_df [date, strategy_ret] over OOS, intermediates).
    """
    monthly = _to_datetime(anomalies_monthly)
    mu_df = compute_training_mu(monthly)
    gamma_cv = select_gamma_by_cv(monthly, anomalies_daily)
    b_df = compute_sdf_coefficients(monthly, anomalies_daily)
    mve_df = compute_oos_mve_returns(b_df, monthly)
    strat_df = rescale_to_market_vol(mve_df, ff_factors_monthly)
    intermediates = {
        "b_hat": b_df,
        "mu_bar": mu_df,
        "cv_trace": gamma_cv,
        "mve_ret": mve_df,
        "oos_window": (OOS_START, OOS_END),
    }
    return strat_df, intermediates


# --------------------------------------------------------------------------
# Data-loading layer: percent -> decimal conversion happens HERE (R14)
# --------------------------------------------------------------------------
def _data_dir() -> Path:
    module_dir = Path(__file__).resolve().parent
    for cand in (module_dir.parent / "data", module_dir / "data"):
        if cand.exists():
            return cand
    return module_dir


def main() -> None:
    data_dir = _data_dir()

    monthly = pd.read_csv(data_dir / "anomalies_monthly.csv")
    monthly["date"] = pd.to_datetime(monthly["date"], format="%m/%Y").astype("datetime64[ns]")

    daily = pd.read_csv(data_dir / "anomalies_daily.csv")
    daily["date"] = pd.to_datetime(daily["date"], format="%m/%d/%Y").astype("datetime64[ns]")

    ff = pd.read_csv(data_dir / "ff_factors_monthly.csv", skiprows=3)
    ff.columns = ["date", "mktrf", "smb", "hml", "rf"]
    ff["date"] = pd.to_datetime(ff["date"]).astype("datetime64[ns]")
    for col in _FF_DECIMAL_COLS:                      # R14: percent -> decimal
        ff[col] = ff[col].astype(float) / 100.0

    strat_df, inter = run_pipeline(monthly, ff, daily)

    out_dir = Path(__file__).resolve().parent
    out_dir.mkdir(parents=True, exist_ok=True)
    strat_df.to_csv(out_dir / "strategy_returns.csv", index=False)
    inter["b_hat"].to_csv(out_dir / "sdf_coefficients.csv", index=False)
    inter["cv_trace"].to_csv(out_dir / "cv_trace.csv", index=False)
    inter["mu_bar"].to_csv(out_dir / "mu_bar.csv", index=False)

    best = inter["cv_trace"].loc[inter["cv_trace"]["is_optimum"]].iloc[0]
    print("kappa* = %.4f  gamma* = %.6f  cv_r2* = %.4f" % (
        best["kappa"], best["gamma"], best["cv_r2"]))
    print("OOS months: %d" % len(strat_df))
    print("strategy_ret mean = %.6f  std = %.6f" % (
        strat_df["strategy_ret"].mean(), strat_df["strategy_ret"].std()))
    print("annualized OOS mean = %.4f" % ((1.0 + strat_df["strategy_ret"].mean()) ** 12 - 1.0))


if __name__ == "__main__":
    main()
