from django.shortcuts import render

from prices.models import GoldQuote, DailyObservation, Currency
from prices.i18n import TRANSLATIONS, get_lang
from predictions.models import ModelRun
from predictions.services.accuracy import accuracy_summary


def dashboard(request):
    lang = get_lang(request)
    t = TRANSLATIONS[lang]
    toggle_lang = "ar" if lang == "en" else "en"

    latest_quote = (
        GoldQuote.objects.filter(currency=Currency.EGP)
        .order_by("-quote_date", "-fetched_at")
        .first()
    )
    gold_pound = None
    if latest_quote and latest_quote.price_gram_21k:
        gold_pound = latest_quote.price_gram_21k * 8   # Egyptian gold pound = 8g of 21K

    karat_prices = {}
    if latest_quote:
        karat_prices = {
            "24": float(latest_quote.price_gram_24k or 0),
            "22": float(latest_quote.price_gram_22k or 0),
            "21": float(latest_quote.price_gram_21k or 0),
            "18": float(latest_quote.price_gram_18k or 0),
        }

    premium_obs = (
        DailyObservation.objects.filter(premium_pct__isnull=False)
        .order_by("-obs_date")
        .first()
    )
    local_price = premium_obs.actual_egp_gram_21k if premium_obs else None
    premium_date = premium_obs.obs_date if premium_obs else None
    premium_str = None
    if premium_obs and premium_obs.premium_pct is not None:
        premium_str = f"{float(premium_obs.premium_pct) * 100:+.2f}%"

    active_run = ModelRun.objects.filter(is_active=True).first()
    predictions = (
        list(active_run.predictions.order_by("horizon_days")) if active_run else []
    )

    accuracy_rows, accuracy_mae, accuracy_n = accuracy_summary(limit=20)

    history = list(
        DailyObservation.objects.order_by("-obs_date")
        .values_list("obs_date", "fair_egp_gram_21k")[:180]
    )[::-1]

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
        "t": t,
        "lang": lang,
        "toggle_lang": toggle_lang,
        "latest_quote": latest_quote,
        "gold_pound": gold_pound,
        "karat_prices": karat_prices,
        "local_price": local_price,
        "premium_date": premium_date,
        "premium_str": premium_str,
        "active_run": active_run,
        "predictions": predictions,
        "accuracy_rows": accuracy_rows,
        "accuracy_mae": accuracy_mae,
        "accuracy_n": accuracy_n,
        "chart": chart,
    })