from django.apps import AppConfig


class FeatureFlagsConfig(AppConfig):
    """Application config for core feature flag metadata."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core.feature_flags"
    label = "core_feature_flags"
    verbose_name = "Core Feature Flags"
