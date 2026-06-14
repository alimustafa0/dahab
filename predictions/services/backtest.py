"""Walk-forward backtest of the median fair-value forecast."""

import numpy as np

from .data import load_series


def backtest_horizon(fair, log_returns, horizon, lookback=250, step=5, min_train=250):
    """MAE (EGP/g) and MAPE (%) for one horizon. Returns (mae, mape, n_points)."""
    abs_errs, pct_errs = [], []
    for i in range(min_train, len(fair) - horizon, step):
        window = log_returns[max(0, i - lookback):i]
        if len(window) < 2:
            continue
        mu = window.mean()
        forecast = fair[i] * np.exp(horizon * mu)   # median RW-with-drift forecast
        actual = fair[i + horizon]
        abs_errs.append(abs(forecast - actual))
        pct_errs.append(abs(forecast - actual) / actual * 100.0)
    if not abs_errs:
        return None, None, 0
    return float(np.mean(abs_errs)), float(np.mean(pct_errs)), len(abs_errs)


def backtest(horizons, lookback=250, step=5):
    """Backtest each horizon. Returns {horizon: {'mae':.., 'mape':.., 'n':..}}."""
    df = load_series()
    fair = df["fair21"].astype(float).values
    if len(fair) < lookback + max(horizons) + 1:
        return {}
    log_returns = np.diff(np.log(fair))
    return {
        h: dict(zip(("mae", "mape", "n"), backtest_horizon(fair, log_returns, h, lookback, step)))
        for h in horizons
    }