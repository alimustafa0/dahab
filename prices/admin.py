from django.contrib import admin

from .models import GoldQuote, FxRate, LocalMarketPrice, DailyObservation


@admin.register(GoldQuote)
class GoldQuoteAdmin(admin.ModelAdmin):
    list_display = ("quote_date", "currency", "price_per_oz", "price_gram_21k", "source", "fetched_at")
    list_filter = ("currency", "source")
    date_hierarchy = "quote_date"
    ordering = ("-quote_date",)


@admin.register(FxRate)
class FxRateAdmin(admin.ModelAdmin):
    list_display = ("rate_date", "usd_to_egp", "rate_type", "source")
    list_filter = ("rate_type", "source")
    date_hierarchy = "rate_date"
    ordering = ("-rate_date",)


@admin.register(LocalMarketPrice)
class LocalMarketPriceAdmin(admin.ModelAdmin):
    list_display = ("price_date", "karat", "price_egp_per_gram", "source")
    list_filter = ("karat", "source")
    date_hierarchy = "price_date"
    ordering = ("-price_date",)


@admin.register(DailyObservation)
class DailyObservationAdmin(admin.ModelAdmin):
    list_display = ("obs_date", "spot_usd_per_oz", "usd_to_egp", "fair_egp_gram_21k", "actual_egp_gram_21k", "premium_pct")
    list_filter = ("is_interpolated",)
    date_hierarchy = "obs_date"
    ordering = ("-obs_date",)