"""Monte Carlo: simulate spot × FX forward and recombine into 21k fair-value forecasts."""

from dataclasses import dataclass

import numpy as np

from prices.models import GRAMS_PER_TROY_OUNCE
from .forecast import DriftVol

PURITY_21K = 0.875


@dataclass
class HorizonForecast:
    horizon_days: int
    median: float
    lower: float        # p5
    upper: float        # p95
    spot_median: float
    fx_median: float


def simulate(spot: DriftVol, fx: DriftVol, horizons, n_sims=10000,
             lower_pct=5, upper_pct=95, seed=None):
    """
    For each horizon (in trading days), draw `n_sims` joint spot/FX outcomes from
    each component's random-walk-with-drift and recombine into the 21k fair value.
    Returns a list of HorizonForecast.
    """
    rng = np.random.default_rng(seed)
    g = float(GRAMS_PER_TROY_OUNCE)
    results = []

    for h in horizons:
        # h-day cumulative log-return ~ Normal(h*mu, h*sigma^2)  (sum of iid daily returns)
        spot_h = spot.last_value * np.exp(rng.normal(h * spot.mu, np.sqrt(h) * spot.sigma, n_sims))
        fx_h = fx.last_value * np.exp(rng.normal(h * fx.mu, np.sqrt(h) * fx.sigma, n_sims))
        fair_h = (spot_h / g) * fx_h * PURITY_21K

        results.append(HorizonForecast(
            horizon_days=h,
            median=float(np.percentile(fair_h, 50)),
            lower=float(np.percentile(fair_h, lower_pct)),
            upper=float(np.percentile(fair_h, upper_pct)),
            spot_median=float(np.percentile(spot_h, 50)),
            fx_median=float(np.percentile(fx_h, 50)),
        ))
    return results