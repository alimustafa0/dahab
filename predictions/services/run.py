"""Fit the hybrid model, simulate, backtest, and persist a ModelRun + its Predictions."""

import pandas as pd
from django.utils import timezone

from prices.models import Karat, DailyObservation
from predictions.models import ModelRun, Prediction
from .data import load_series
from .forecast import fit_drift_vol
from .montecarlo import simulate
from .backtest import backtest

DEFAULT_HORIZONS = [1, 7, 30, 90]


def latest_premium():
    """Most recent observed local premium (Decimal), or None if no local data yet."""
    obs = (
        DailyObservation.objects.filter(premium_pct__isnull=False)
        .order_by("-obs_date")
        .first()
    )
    return obs.premium_pct if obs else None


def run_forecast(horizons=None, n_sims=10000, lookback=250, seed=None):
    """
    Load data -> fit drift/vol for spot & FX -> Monte Carlo (with the latest local
    premium applied) -> backtest -> store a new active ModelRun and one Prediction
    per horizon. Returns the ModelRun (or None if there's no data).
    """
    horizons = horizons or DEFAULT_HORIZONS
    df = load_series()
    if df.empty:
        return None

    spot = fit_drift_vol(df["spot"], lookback=lookback)
    fx = fit_drift_vol(df["fx"], lookback=lookback)

    premium = latest_premium()                 # Decimal or None
    premium_f = float(premium) if premium is not None else 0.0
    forecasts = simulate(spot, fx, horizons, n_sims=n_sims, seed=seed, premium=premium_f)

    anchor = df.index.max()
    now = timezone.now()

    metrics = backtest(horizons, lookback=lookback, step=5)
    headline = metrics.get(30) or (metrics.get(horizons[-1]) if metrics else {}) or {}

    ModelRun.objects.filter(is_active=True).update(is_active=False)
    run = ModelRun.objects.create(
        model_type=ModelRun.ModelType.HYBRID,
        trained_at=now,
        training_start=df.index.min().date(),
        training_end=anchor.date(),
        mae=headline.get("mae"),
        mape=headline.get("mape"),
        params={
            "lookback": lookback,
            "n_sims": n_sims,
            "premium_pct": premium_f,
            "spot_mu": spot.mu, "spot_sigma": spot.sigma,
            "fx_mu": fx.mu, "fx_sigma": fx.sigma,
            "backtest": {str(h): m for h, m in metrics.items()},
        },
        is_active=True,
    )

    for f in forecasts:
        target_date = (anchor + pd.offsets.BusinessDay(f.horizon_days)).date()
        Prediction.objects.create(
            model_run=run,
            karat=Karat.K21,
            generated_at=now,
            target_date=target_date,
            horizon_days=f.horizon_days,
            predicted_egp_per_gram=f.median,
            lower_bound=f.lower,
            upper_bound=f.upper,
            component_spot_usd=f.spot_median,
            component_fx=f.fx_median,
            component_premium_pct=premium,     # Decimal or None
        )

    return run