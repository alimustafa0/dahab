"""Estimate drift + volatility of a price series from its log-returns."""

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class DriftVol:
    last_value: float   # most recent price level
    mu: float           # mean daily log-return (drift)
    sigma: float        # EWMA daily volatility (std of log-return)
    n: int              # number of returns used


def fit_drift_vol(series, lookback=250, vol_lambda=0.94):
    """
    Fit a random-walk-with-drift to a price series via its log-returns over the
    last `lookback` observations (≈1 trading year by default).

    Drift (mu) is the simple mean — deliberately smooth, so a calm recent stretch
    isn't extrapolated into a runaway trend (this is what keeps FX drift sane).

    Volatility (sigma) is an exponentially-weighted estimate (RiskMetrics decay
    `vol_lambda` = 0.94, ~16-day effective memory), so the prediction band tracks
    the *current* volatility regime rather than averaging a turbulent month with a
    calm one. Returns a DriftVol.
    """
    s = pd.Series(series).dropna().astype(float)
    log_returns = np.log(s / s.shift(1)).dropna()
    if lookback:
        log_returns = log_returns.tail(lookback)

    mu = float(log_returns.mean())
    demeaned = log_returns - mu
    ewm_var = demeaned.pow(2).ewm(alpha=1.0 - vol_lambda, adjust=False).mean().iloc[-1]
    sigma = float(np.sqrt(ewm_var))

    return DriftVol(
        last_value=float(s.iloc[-1]),
        mu=mu,
        sigma=sigma,
        n=int(len(log_returns)),
    )