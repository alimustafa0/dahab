"""Backfill historical spot + FX into DailyObservation, free and key-less (yfinance)."""

from datetime import date, timedelta
from decimal import Decimal

import yfinance as yf

from prices.models import DailyObservation, FxRate, Source, GRAMS_PER_TROY_OUNCE
from .ingest import PURITY_21K

GOLD_SYMBOL = "GC=F"   # COMEX gold futures, USD per troy ounce (close proxy for spot)
FX_SYMBOL = "EGP=X"    # USD -> EGP (how many EGP per 1 USD)


def _download_close(symbol, start, end):
    """Return a date -> Decimal close-price dict for a Yahoo symbol."""
    df = yf.download(symbol, start=start, end=end, interval="1d", progress=False, auto_adjust=False)
    if df.empty:
        return {}
    closes = df["Close"]
    if hasattr(closes, "columns"):          # newer yfinance returns a 1-col frame
        closes = closes.iloc[:, 0]
    return {
        ts.date(): Decimal(str(round(float(v), 4)))
        for ts, v in closes.items()
        if v == v                            # drops NaN (NaN != NaN)
    }


def seed_history(years=5):
    """Build DailyObservation rows for the last `years` years. Returns (created, skipped)."""
    end = date.today() + timedelta(days=1)
    start = end - timedelta(days=365 * years + 7)

    gold = _download_close(GOLD_SYMBOL, start, end)
    fx = _download_close(FX_SYMBOL, start, end)
    if not gold or not fx:
        raise RuntimeError("Yahoo returned no data — check your internet connection and retry.")

    fx_dates = sorted(fx)
    g_per_oz = Decimal(str(GRAMS_PER_TROY_OUNCE))
    created = skipped = 0

    for d in sorted(gold):
        spot = gold[d]
        rate = fx.get(d)
        interpolated = False
        if rate is None:                      # FX missing that day -> carry last known
            prior = [x for x in fx_dates if x <= d]
            if not prior:
                skipped += 1
                continue
            rate = fx[prior[-1]]
            interpolated = True

        FxRate.objects.update_or_create(
            rate_date=d,
            rate_type=FxRate.RateType.OFFICIAL,
            source=Source.YFINANCE,
            defaults={"usd_to_egp": rate},
        )

        fair_21k = (spot / g_per_oz * rate * PURITY_21K).quantize(Decimal("0.0001"))
        # get_or_create: never overwrite a live (GoldAPI-based) observation.
        _, was_created = DailyObservation.objects.get_or_create(
            obs_date=d,
            defaults={
                "spot_usd_per_oz": spot,
                "usd_to_egp": rate,
                "fair_egp_gram_21k": fair_21k,
                "is_interpolated": interpolated,
            },
        )
        created += was_created
        skipped += not was_created

    return created, skipped