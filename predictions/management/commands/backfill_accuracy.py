"""Backfill realized prices into matured predictions for the accuracy tracker."""

from django.core.management.base import BaseCommand

from predictions.services.accuracy import backfill_actuals


class Command(BaseCommand):
    help = "Fill realized prices into predictions whose target date has passed."

    def handle(self, *args, **options):
        updated = backfill_actuals()
        self.stdout.write(self.style.SUCCESS(
            f"Backfilled {updated} prediction(s) with realized prices."
        ))