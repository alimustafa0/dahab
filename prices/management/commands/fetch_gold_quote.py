"""Fetch the daily XAU quotes (EGP + USD) from GoldAPI, protected for the free tier."""

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from prices.models import ApiCallLog, GoldQuote, Source
from prices.services.goldapi import GoldApiClient, GoldApiError
from prices.services.ingest import store_quote, build_daily_observation

CURRENCIES = ["EGP", "USD"]


class Command(BaseCommand):
    help = "Fetch XAU/EGP and XAU/USD from GoldAPI, cache them, and build the daily observation."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Ignore the cache-TTL guard (the monthly budget guard still applies).",
        )

    def handle(self, *args, **options):
        force = options["force"]
        now = timezone.now()

        # --- Guard 1: cache TTL — don't re-fetch if we just did ---
        if not force:
            ttl = timedelta(hours=settings.GOLDAPI_CACHE_TTL_HOURS)
            latest = (
                GoldQuote.objects.filter(source=Source.GOLDAPI)
                .order_by("-fetched_at")
                .first()
            )
            if latest and now - latest.fetched_at < ttl:
                age = now - latest.fetched_at
                self.stdout.write(self.style.WARNING(
                    f"Skipped: last fetch was {age} ago "
                    f"(TTL is {settings.GOLDAPI_CACHE_TTL_HOURS}h). Use --force to override."
                ))
                return

        # --- Guard 2: monthly budget — never exceed the free-tier limit ---
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        used = ApiCallLog.objects.filter(created_at__gte=month_start, status="OK").count()
        remaining = settings.GOLDAPI_MONTHLY_CALL_BUDGET - used
        if remaining < len(CURRENCIES):
            self.stdout.write(self.style.ERROR(
                f"Refused: monthly budget reached "
                f"({used}/{settings.GOLDAPI_MONTHLY_CALL_BUDGET} calls used). "
                f"Need {len(CURRENCIES)}, only {remaining} left."
            ))
            return

        # --- Fetch each currency, logging every call ---
        client = GoldApiClient()
        fetched_dates = set()
        for currency in CURRENCIES:
            endpoint = f"XAU/{currency}"
            try:
                payload = client.fetch_quote(currency)
            except GoldApiError as exc:
                ApiCallLog.objects.create(endpoint=endpoint, status="ERROR", detail=str(exc)[:255])
                self.stdout.write(self.style.ERROR(f"{endpoint} failed: {exc}"))
                continue

            ApiCallLog.objects.create(endpoint=endpoint, status="OK")
            quote, created = store_quote(payload)
            fetched_dates.add(quote.quote_date)
            verb = "Created" if created else "Updated"
            self.stdout.write(self.style.SUCCESS(
                f"{verb} {currency}: {quote.price_per_oz}/oz, 21k = {quote.price_gram_21k}/g "
                f"({quote.quote_date})"
            ))

        # --- Build the analytical row(s) from the quotes we just stored ---
        for obs_date in sorted(fetched_dates):
            obs = build_daily_observation(obs_date)
            if obs:
                self.stdout.write(self.style.SUCCESS(
                    f"Observation {obs.obs_date}: fair 21k = {obs.fair_egp_gram_21k}/g, "
                    f"FX = {obs.usd_to_egp}"
                ))

        self.stdout.write(self.style.SUCCESS("Done."))