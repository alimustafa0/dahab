"""One-off: backfill historical spot + FX into DailyObservation from free Yahoo data."""

from django.core.management.base import BaseCommand

from prices.services.seed import seed_history


class Command(BaseCommand):
    help = "Backfill DailyObservation with historical spot + FX (free, key-less, via yfinance)."

    def add_arguments(self, parser):
        parser.add_argument("--years", type=int, default=5, help="How many years back to seed.")

    def handle(self, *args, **options):
        years = options["years"]
        self.stdout.write(f"Downloading ~{years}y of gold + USD/EGP history from Yahoo...")
        try:
            created, skipped = seed_history(years=years)
        except RuntimeError as exc:
            self.stdout.write(self.style.ERROR(str(exc)))
            return
        self.stdout.write(self.style.SUCCESS(
            f"Done. Created {created} observations, left {skipped} existing/unmatched untouched."
        ))