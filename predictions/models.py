"""
Dahab — predictions app data layer.

ModelRun tracks each trained model version + its backtest metrics.
Prediction stores one forecast point with its interval and component breakdown.
"""

from django.db import models
from django.utils import timezone

from prices.models import Karat


class ModelRun(models.Model):
    """One trained-model version, its backtest metrics, and its artifact path."""

    class ModelType(models.TextChoices):
        RANDOM_WALK = "RW", "Random walk + drift (baseline)"
        ARIMA = "ARIMA", "ARIMA / SARIMA"
        PROPHET = "PROPHET", "Prophet"
        HYBRID = "HYBRID", "Hybrid (spot × FX × premium)"

    model_type = models.CharField(max_length=10, choices=ModelType.choices)
    trained_at = models.DateTimeField(default=timezone.now)
    training_start = models.DateField(null=True, blank=True)
    training_end = models.DateField(null=True, blank=True)

    mae = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True, help_text="Backtest MAE (EGP/gram).")
    mape = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True, help_text="Backtest MAPE (%).")
    params = models.JSONField(null=True, blank=True, help_text="Hyperparameters, e.g. ARIMA (p, d, q).")
    artifact_path = models.CharField(max_length=512, blank=True, help_text="Path to the pickled model.")
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=False, help_text="The run currently serving predictions.")

    class Meta:
        ordering = ("-trained_at",)
        indexes = [models.Index(fields=["model_type", "-trained_at"])]

    def __str__(self):
        return f"{self.get_model_type_display()} @ {self.trained_at:%Y-%m-%d} (MAPE {self.mape})"


class Prediction(models.Model):
    """A single forecast point from a ModelRun, with interval and component decomposition."""

    model_run = models.ForeignKey(ModelRun, on_delete=models.CASCADE, related_name="predictions")
    karat = models.IntegerField(choices=Karat.choices, default=Karat.K21)

    generated_at = models.DateTimeField(default=timezone.now)
    target_date = models.DateField(db_index=True, help_text="The date this prediction is for.")
    horizon_days = models.PositiveIntegerField(help_text="target_date minus generation date, in days.")

    predicted_egp_per_gram = models.DecimalField(max_digits=12, decimal_places=4)
    lower_bound = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True, help_text="e.g. 5th pct.")
    upper_bound = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True, help_text="e.g. 95th pct.")

    # Forecast component breakdown (the log-space decomposition).
    component_spot_usd = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    component_fx = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    component_premium_pct = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)

    actual_egp_per_gram = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True, help_text="Backfilled for accuracy tracking.")

    class Meta:
        ordering = ("-target_date", "karat")
        constraints = [
            models.UniqueConstraint(
                fields=["model_run", "target_date", "karat"],
                name="uniq_prediction_run_date_karat",
            ),
        ]
        indexes = [models.Index(fields=["-target_date", "karat"])]

    def __str__(self):
        return f"{self.karat}K → {self.predicted_egp_per_gram} EGP/g for {self.target_date}"