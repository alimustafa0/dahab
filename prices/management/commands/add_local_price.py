"""Record a local retail gold price (the real Egyptian market price, incl. premium)."""

from datetime import date as date_cls

from django.core.management.base import BaseCommand, CommandError

from prices.models import LocalMarketPrice, Source
from prices.services.ingest import refresh_premium


class Command(BaseCommand):
    help = "Record a local retail price (EGP/gram) and recompute that day's premium."

    def add_arguments(self, parser):
        parser.add_argument("price", type=float, help="Local retail price, EGP per gram.")
        parser.add_argument("--karat", type=int, default=21, choices=[24, 22, 21, 18])
        parser.add_argument("--date", help="YYYY-MM-DD (default: today).")

    def handle(self, *args, **options):
        if options["date"]:
            try:
                d = date_cls.fromisoformat(options["date"])
            except ValueError:
                raise CommandError("Date must be in YYYY-MM-DD format.")
        else:
            d = date_cls.today()

        _, created = LocalMarketPrice.objects.update_or_create(
            price_date=d,
            karat=options["karat"],
            source=Source.MANUAL,
            defaults={"price_egp_per_gram": options["price"]},
        )
        verb = "Added" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(
            f"{verb} local {options['karat']}K price for {d}: {options['price']} EGP/g"
        ))

        obs = refresh_premium(d)
        if obs and obs.premium_pct is not None:
            self.stdout.write(self.style.SUCCESS(
                f"Premium for {d}: {obs.premium_pct} "
                f"(fair {obs.fair_egp_gram_21k}, actual {obs.actual_egp_gram_21k})"
            ))
        elif obs:
            self.stdout.write(self.style.WARNING(
                "Saved, but couldn't compute a premium — no fair value for that date. "
                "Use a recent date that already has an observation."
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f"Saved the price, but there's no DailyObservation for {d} to attach it to."
            ))