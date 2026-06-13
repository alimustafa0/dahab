"""GoldAPI payloads → stored quotes, plus the daily analytical row."""

from datetime import datetime, timezone as dt_timezone
from decimal import Decimal

from django.utils import timezone

from prices.models import (
    GoldQuote,
    Source,
    FxRate,
    DailyObservation,
    LocalMarketPrice,
    Karat,
    GRAMS_PER_TROY_OUNCE,
)


def _date_from_timestamp(unix_ts):
    """Convert a GoldAPI Unix timestamp (seconds, UTC) to a date."""
    return datetime.fromtimestamp(unix_ts, tz=dt_timezone.utc).date()


def store_quote(payload):
    """
    Map a GoldAPI payload to a GoldQuote, upserting by (quote_date, currency, source).
    Returns (quote, created). The full payload is saved in raw_payload, so we keep
    every field GoldAPI returned — even ones the model has no column for.
    """
    currency = payload["currency"]
    quote_date = _date_from_timestamp(payload["timestamp"])

    defaults = {
        "price_per_oz": payload["price"],
        "open_price": payload.get("open_price"),
        "high_price": payload.get("high_price"),
        "low_price": payload.get("low_price"),
        "prev_close_price": payload.get("prev_close_price"),
        "change_abs": payload.get("ch"),
        "change_pct": payload.get("chp"),
        "price_gram_24k": payload.get("price_gram_24k"),
        "price_gram_22k": payload.get("price_gram_22k"),
        "price_gram_21k": payload.get("price_gram_21k"),
        "price_gram_18k": payload.get("price_gram_18k"),
        "raw_payload": payload,
        "fetched_at": timezone.now(),
    }

    quote, created = GoldQuote.objects.update_or_create(
        quote_date=quote_date,
        currency=currency,
        source=Source.GOLDAPI,
        defaults=defaults,
    )
    return quote, created


PURITY_21K = Decimal("0.875")


def compute_implied_fx(obs_date):
    """
    Derive USD/EGP from the same day's EGP and USD ounce quotes (EGP_oz / USD_oz),
    store it as an IMPLIED FxRate, and return the rate as a Decimal (or None).
    """
    egp = GoldQuote.objects.filter(
        quote_date=obs_date, currency="EGP", source=Source.GOLDAPI
    ).first()
    usd = GoldQuote.objects.filter(
        quote_date=obs_date, currency="USD", source=Source.GOLDAPI
    ).first()
    if not (egp and usd) or not usd.price_per_oz:
        return None

    rate = (egp.price_per_oz / usd.price_per_oz).quantize(Decimal("0.0001"))
    FxRate.objects.update_or_create(
        rate_date=obs_date,
        rate_type=FxRate.RateType.IMPLIED,
        source=Source.COMPUTED,
        defaults={"usd_to_egp": rate},
    )
    return rate


def build_daily_observation(obs_date, fx_rate=None):
    """
    Build/refresh the DailyObservation for a date:
      - spot from the USD ounce quote
      - usd_to_egp from the implied FX rate
      - fair 21k from the import-parity identity (spot / g_per_oz * fx * 0.875)
      - actual 21k + premium ONLY if a local retail price exists (else left null,
        because GoldAPI's EGP price is itself fair value, not the local market price)
    """
    usd = GoldQuote.objects.filter(
        quote_date=obs_date, currency="USD", source=Source.GOLDAPI
    ).first()
    if not usd:
        return None

    if fx_rate is None:
        fx_rate = compute_implied_fx(obs_date)
    if fx_rate is None:
        return None

    spot = usd.price_per_oz
    fair_21k = (
        spot / Decimal(str(GRAMS_PER_TROY_OUNCE)) * fx_rate * PURITY_21K
    ).quantize(Decimal("0.0001"))

    actual_21k = None
    premium = None
    local = (
        LocalMarketPrice.objects.filter(price_date=obs_date, karat=Karat.K21)
        .order_by("-created_at")
        .first()
    )
    if local:
        actual_21k = local.price_egp_per_gram
        premium = ((actual_21k / fair_21k) - 1).quantize(Decimal("0.0001"))

    obs, _ = DailyObservation.objects.update_or_create(
        obs_date=obs_date,
        defaults={
            "spot_usd_per_oz": spot,
            "usd_to_egp": fx_rate,
            "fair_egp_gram_21k": fair_21k,
            "actual_egp_gram_21k": actual_21k,
            "premium_pct": premium,
        },
    )
    return obs