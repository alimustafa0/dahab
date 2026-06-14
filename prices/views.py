from django.shortcuts import render

from prices.models import GoldQuote, DailyObservation, Currency
from predictions.models import ModelRun


def dashboard(request):
    latest_quote = (
        GoldQuote.objects.filter(currency=Currency.EGP)
        .order_by("-quote_date", "-fetched_at")
        .first()
    )
    active_run = ModelRun.objects.filter(is_active=True).first()
    predictions = (
        list(active_run.predictions.order_by("horizon_days")) if active_run else []
    )

    history = list(
        DailyObservation.objects.order_by("-obs_date")
        .values_list("obs_date", "fair_egp_gram_21k")[:180]
    )[::-1]  # oldest -> newest

    chart = {
        "labels": [d.isoformat() for d, _ in history],
        "values": [float(v) for _, v in history],
        "forecast": [
            {
                "date": p.target_date.isoformat(),
                "median": float(p.predicted_egp_per_gram),
                "lower": float(p.lower_bound),
                "upper": float(p.upper_bound),
            }
            for p in predictions
        ],
    }

    return render(request, "dashboard.html", {
        "latest_quote": latest_quote,
        "active_run": active_run,
        "predictions": predictions,
        "chart": chart,
    })