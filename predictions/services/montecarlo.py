"""Monte Carlo: simulate spot × FX forward and recombine into 21k price forecasts."""

from dataclasses import dataclass

import numpy as np

from prices.models import GRAMS_PER_TROY_OUNCE
from .forecast import DriftVol

PURITY_21K = 0.875


@dataclass
class HorizonForecast:
    horizon_days: int
    median: float        # actual local price (fair × (1 + premium))
    lower: float         # p5
    upper: float         # p95
    spot_median: float
    fx_median: float
    fair_median: float   # fair value before the premium, for transparency


def simulate(spot: DriftVol, fx: DriftVol, horizons, n_sims=10000,
             lower_pct=5, upper_pct=95, seed=None, premium=0.0):
    """
    For each horizon (in trading days), draw `n_sims` joint spot/FX outcomes from
    each component's random-walk-with-drift, recombine into the 21k fair value, and
    apply the local premium to get the actual market price. Returns HorizonForecasts.
    """
    rng = np.random.default_rng(seed)
    g = float(GRAMS_PER_TROY_OUNCE)
    mult = 1.0 + premium
    results = []

    for h in horizons:
        spot_h = spot.last_value * np.exp(rng.normal(h * spot.mu, np.sqrt(h) * spot.sigma, n_sims))
        fx_h = fx.last_value * np.exp(rng.normal(h * fx.mu, np.sqrt(h) * fx.sigma, n_sims))
        fair_h = (spot_h / g) * fx_h * PURITY_21K
        price_h = fair_h * mult

        results.append(HorizonForecast(
            horizon_days=h,
            median=float(np.percentile(price_h, 50)),
            lower=float(np.percentile(price_h, lower_pct)),
            upper=float(np.percentile(price_h, upper_pct)),
            spot_median=float(np.percentile(spot_h, 50)),
            fx_median=float(np.percentile(fx_h, 50)),
            fair_median=float(np.percentile(fair_h, 50)),
        ))
    return results