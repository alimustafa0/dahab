"""Backfill realized prices into matured predictions and summarize accuracy."""

from datetime import date
from decimal import Decimal

from prices.models import DailyObservation
from predictions.models import Prediction


def _realized_for(pred):
    """
    Realized 21K price for a matured prediction's target date.
    Uses the actual local retail price if recorded; otherwise scales that day's fair
    value by the premium the prediction assumed, so the error reflects spot/FX
    forecasting accuracy rather than missing local data. Returns Decimal or None.
    """
    obs = DailyObservation.objects.filter(obs_date=pred.target_date).first()
    if obs is None:
        return None
    if obs.actual_egp_gram_21k is not None:
        return obs.actual_egp_gram_21k
    prem = pred.component_premium_pct or Decimal("0")
    return (obs.fair_egp_gram_21k * (Decimal("1") + prem)).quantize(Decimal("0.0001"))


def backfill_actuals(today=None):
    """
    Fill `actual_egp_per_gram` on every prediction whose target_date has arrived and
    whose realized price we can now determine. Returns the count updated.
    """
    today = today or date.today()
    pending = Prediction.objects.filter(
        actual_egp_per_gram__isnull=True,
        target_date__lte=today,
    )
    updated = 0
    for pred in pending:
        realized = _realized_for(pred)
        if realized is None:
            continue
        pred.actual_egp_per_gram = realized
        pred.save(update_fields=["actual_egp_per_gram"])
        updated += 1
    return updated


def accuracy_summary(limit=20):
    """
    Recent matured predictions (newest first) plus the mean absolute % error.
    Returns (rows, mae_pct, n).
    """
    qs = (
        Prediction.objects.filter(actual_egp_per_gram__isnull=False)
        .order_by("-target_date")[:limit]
    )
    rows, errs = [], []
    for p in qs:
        predicted = float(p.predicted_egp_per_gram)
        actual = float(p.actual_egp_per_gram)
        err = (predicted - actual) / actual * 100.0 if actual else None
        if err is not None:
            errs.append(abs(err))
        rows.append({
            "target_date": p.target_date,
            "horizon_days": p.horizon_days,
            "predicted": predicted,
            "actual": actual,
            "error_pct": err,
        })
    mae_pct = sum(errs) / len(errs) if errs else None
    return rows, mae_pct, len(errs)