"""Estimate drift + volatility of a price series from its log-returns."""

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class DriftVol:
    last_value: float   # most recent price level
    mu: float           # mean daily log-return (drift)
    sigma: float        # std of daily log-return (volatility)
    n: int              # number of returns used


def fit_drift_vol(series, lookback=250):
    """
    Fit a random-walk-with-drift to a price series via its log-returns over the
    last `lookback` observations (≈1 trading year by default). Returns a DriftVol.
    """
    s = pd.Series(series).dropna().astype(float)
    log_returns = np.log(s / s.shift(1)).dropna()
    if lookback:
        log_returns = log_returns.tail(lookback)
    return DriftVol(
        last_value=float(s.iloc[-1]),
        mu=float(log_returns.mean()),
        sigma=float(log_returns.std(ddof=1)),
        n=int(len(log_returns)),
    )