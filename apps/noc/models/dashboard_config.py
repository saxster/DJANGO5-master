"""
NOC Dashboard Configuration Model.

User-specific dashboard customization settings.
Follows .claude/rules.md Rule #7 (models <150 lines).
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.tenants.models import TenantAwareModel
from apps.peoples.models import BaseModel

__all__ = ['NOCDashboardConfig']


class NOCDashboardConfig(TenantAwareModel, BaseModel):
    """
    Per-user NOC dashboard configuration.

    Stores personalization settings for:
    - Widget visibility and layout
    - Default filters
    - Refresh intervals
    - Alert notification preferences
    """

    user = models.OneToOneField(
        'peoples.People',
        on_delete=models.CASCADE,
        verbose_name=_("User"),
        related_name='noc_dashboard_config'
    )

    widget_preferences = models.JSONField(
        default=dict,
        verbose_name=_("Widget Preferences"),
        help_text=_("Widget visibility, order, and size settings")
    )

    default_filters = models.JSONField(
        default=dict,
        verbose_name=_("Default Filters"),
        help_text=_("Default client, severity, status filters")
    )

    refresh_interval_seconds = models.IntegerField(
        default=30,
        verbose_name=_("Refresh Interval (seconds)"),
        help_text=_("Dashboard auto-refresh interval")
    )

    alert_notification_enabled = models.BooleanField(
        default=True,
        verbose_name=_("Alert Notifications Enabled")
    )
    notification_severities = models.JSONField(
        default=list,
        verbose_name=_("Notification Severities"),
        help_text=_("Severities to receive notifications for (e.g., ['HIGH', 'CRITICAL'])")
    )

    show_resolved_alerts = models.BooleanField(
        default=False,
        verbose_name=_("Show Resolved Alerts")
    )
    alerts_per_page = models.IntegerField(
        default=25,
        verbose_name=_("Alerts Per Page")
    )

    theme = models.CharField(
        max_length=20,
        default='light',
        choices=[('light', 'Light'), ('dark', 'Dark')],
        verbose_name=_("Theme")
    )

    class Meta:
        db_table = 'noc_dashboard_config'
        verbose_name = _("NOC Dashboard Config")
        verbose_name_plural = _("NOC Dashboard Configs")

    def __str__(self) -> str:
        return f"Dashboard Config: {self.user.peoplename}"

    @classmethod
    def get_or_create_for_user(cls, user):
        """Get or create dashboard config for user with defaults."""
        config, created = cls.objects.get_or_create(
            user=user,
            tenant=user.tenant,
            defaults={
                'widget_preferences': {},
                'default_filters': {},
                'refresh_interval_seconds': 30,
                'alert_notification_enabled': True,
                'notification_severities': ['HIGH', 'CRITICAL'],
                'show_resolved_alerts': False,
                'alerts_per_page': 25,
                'theme': 'light',
            }
        )
        return config