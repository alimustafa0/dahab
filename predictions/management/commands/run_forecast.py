"""Fit the hybrid model and write predictions for the standard horizons."""

from django.core.management.base import BaseCommand

from predictions.services.run import run_forecast


class Command(BaseCommand):
    help = "Fit the hybrid spot×FX model and store a new active ModelRun with predictions."

    def add_arguments(self, parser):
        parser.add_argument("--sims", type=int, default=10000, help="Monte Carlo simulations.")
        parser.add_argument("--lookback", type=int, default=250, help="Trading days for drift/vol.")

    def handle(self, *args, **options):
        run = run_forecast(n_sims=options["sims"], lookback=options["lookback"])
        if run is None:
            self.stdout.write(self.style.ERROR("No data — seed history first."))
            return

        self.stdout.write(self.style.SUCCESS(
            f"Created {run} with {run.predictions.count()} predictions:"
        ))
        for p in run.predictions.order_by("horizon_days"):
            self.stdout.write(
                f"  +{p.horizon_days}d ({p.target_date}): "
                f"{p.predicted_egp_per_gram:.2f}  [{p.lower_bound:.2f} - {p.upper_bound:.2f}]"
            )

        self.stdout.write("Backtest (walk-forward) by horizon:")
        for h, m in sorted(run.params.get("backtest", {}).items(), key=lambda kv: int(kv[0])):
            if m.get("mape") is not None:
                self.stdout.write(
                    f"  +{h}d: MAPE {m['mape']:.2f}%  MAE {m['mae']:.2f} EGP/g  (n={m['n']})"
                )