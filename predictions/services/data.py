"""Load DailyObservation into clean pandas series for modeling."""

import pandas as pd

from prices.models import DailyObservation


def load_series():
    """
    Daily DataFrame indexed by date with columns:
      spot   - gold USD/oz
      fx     - USD/EGP
      fair21 - fair value EGP/gram 21k

    Reindexed to a continuous business-day calendar and forward-filled, so the
    time-series models see an even grid (no weekend/holiday gaps).
    """
    rows = (
        DailyObservation.objects.order_by("obs_date")
        .values_list("obs_date", "spot_usd_per_oz", "usd_to_egp", "fair_egp_gram_21k")
    )
    if not rows:
        return pd.DataFrame(columns=["spot", "fx", "fair21"])

    df = pd.DataFrame(list(rows), columns=["date", "spot", "fx", "fair21"])
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").astype(float).sort_index()

    full = pd.date_range(df.index.min(), df.index.max(), freq="B")
    df = df.reindex(full).ffill().dropna()
    df.index.name = "date"
    return df