from django.contrib import admin

from .models import ModelRun, Prediction


@admin.register(ModelRun)
class ModelRunAdmin(admin.ModelAdmin):
    list_display = ("model_type", "trained_at", "mae", "mape", "is_active")
    list_filter = ("model_type", "is_active")
    ordering = ("-trained_at",)


@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    list_display = ("target_date", "karat", "predicted_egp_per_gram", "lower_bound", "upper_bound", "horizon_days")
    list_filter = ("karat", "model_run__model_type")
    date_hierarchy = "target_date"
    ordering = ("-target_date",)
    list_select_related = ("model_run",)