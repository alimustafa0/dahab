"""
Dahab — prices app data layer.

GoldQuote is the API-credit firewall: every user-facing read comes from the DB,
and GoldAPI is touched only by the scheduled ingest job. Import-parity identity:

    fair_EGP_per_gram(karat) = (spot_USD_per_oz / 31.1034768) * usd_to_egp * purity

21K (عيار 21) is the primary traded karat in Egypt, so it's our main target.
"""

from django.db import models
from django.utils import timezone


# Grams per troy ounce — conversion constant for the fair-value identity.
GRAMS_PER_TROY_OUNCE = 31.1034768


class Source(models.TextChoices):
    GOLDAPI = "GOLDAPI", "GoldAPI.io (live tick)"
    STOOQ = "STOOQ", "Stooq (free historical seed)"
    YFINANCE = "YFINANCE", "Yahoo Finance (free historical seed)"
    COMPUTED = "COMPUTED", "Computed / derived"
    MANUAL = "MANUAL", "Manual entry"
    GOLD_DIVISION = "GOLD_DIVISION", "Egyptian Gold Division (retail)"


class Currency(models.TextChoices):
    USD = "USD", "US Dollar"
    EGP = "EGP", "Egyptian Pound"


class Karat(models.IntegerChoices):
    K24 = 24, "24K (999)"
    K22 = 22, "22K (916)"
    K21 = 21, "21K (875) — Egyptian standard"
    K18 = 18, "18K (750)"


class GoldQuote(models.Model):
    """Cached XAU snapshot from GoldAPI (or a seeded source). The API-credit firewall."""

    quote_date = models.DateField(db_index=True, help_text="Trading date the quote represents.")
    currency = models.CharField(max_length=3, choices=Currency.choices)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.GOLDAPI)

    # Ounce-level pricing (XAU per troy ounce, in `currency`).
    price_per_oz = models.DecimalField(max_digits=14, decimal_places=4)
    open_price = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    high_price = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    low_price = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    prev_close_price = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    change_abs = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    change_pct = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)

    # Per-gram karat breakdown (in `currency`) — GoldAPI returns these directly.
    price_gram_24k = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    price_gram_22k = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    price_gram_21k = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    price_gram_18k = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)

    raw_payload = models.JSONField(null=True, blank=True, help_text="Full API response, kept so we never re-call.")
    fetched_at = models.DateTimeField(default=timezone.now, help_text="When we hit the API (cache-TTL anchor).")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-quote_date", "currency")
        constraints = [
            models.UniqueConstraint(
                fields=["quote_date", "currency", "source"],
                name="uniq_goldquote_day_currency_source",
            ),
        ]
        indexes = [models.Index(fields=["currency", "-quote_date"])]

    def __str__(self):
        return f"{self.currency} XAU @ {self.price_per_oz} ({self.quote_date})"


class FxRate(models.Model):
    """USD/EGP rate. OFFICIAL vs PARALLEL diverge in Egypt; IMPLIED is back-computed from XAU EGP÷USD."""

    class RateType(models.TextChoices):
        OFFICIAL = "OFFICIAL", "Official / CBE"
        PARALLEL = "PARALLEL", "Parallel / black market"
        IMPLIED = "IMPLIED", "Implied from XAU (EGP ÷ USD)"

    rate_date = models.DateField(db_index=True)
    usd_to_egp = models.DecimalField(max_digits=10, decimal_places=4, help_text="EGP per 1 USD.")
    rate_type = models.CharField(max_length=10, choices=RateType.choices, default=RateType.OFFICIAL)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.COMPUTED)
    fetched_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-rate_date", "rate_type")
        constraints = [
            models.UniqueConstraint(
                fields=["rate_date", "rate_type", "source"],
                name="uniq_fxrate_day_type_source",
            ),
        ]

    def __str__(self):
        return f"USD/EGP {self.usd_to_egp} [{self.rate_type}] ({self.rate_date})"


class LocalMarketPrice(models.Model):
    """Optional ground-truth retail price per gram (includes local premium). Manual / local feed."""

    price_date = models.DateField(db_index=True)
    karat = models.IntegerField(choices=Karat.choices, default=Karat.K21)
    price_egp_per_gram = models.DecimalField(max_digits=12, decimal_places=2)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.MANUAL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-price_date", "karat")
        constraints = [
            models.UniqueConstraint(
                fields=["price_date", "karat", "source"],
                name="uniq_localprice_day_karat_source",
            ),
        ]

    def __str__(self):
        return f"{self.karat}K {self.price_egp_per_gram} EGP/g ({self.price_date})"


class DailyObservation(models.Model):
    """The cleaned, joined daily series the models train on — one row per date."""

    obs_date = models.DateField(unique=True, db_index=True)

    spot_usd_per_oz = models.DecimalField(max_digits=14, decimal_places=4)
    usd_to_egp = models.DecimalField(max_digits=10, decimal_places=4)

    fair_egp_gram_21k = models.DecimalField(max_digits=12, decimal_places=4, help_text="Import-parity fair value.")
    actual_egp_gram_21k = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    premium_pct = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True, help_text="actual/fair - 1.")

    is_interpolated = models.BooleanField(default=False, help_text="True if any field was gap-filled.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-obs_date",)

    def __str__(self):
        return f"Obs {self.obs_date}: fair 21K = {self.fair_egp_gram_21k} EGP/g"
    
class ApiCallLog(models.Model):
    """One row per GoldAPI request, so the monthly budget guard counts real calls."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    endpoint = models.CharField(max_length=64, help_text='e.g. "XAU/EGP".')
    status = models.CharField(max_length=16, help_text='"OK" or "ERROR".')
    detail = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.endpoint} [{self.status}] {self.created_at:%Y-%m-%d %H:%M}"