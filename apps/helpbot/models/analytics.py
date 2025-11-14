"""
HelpBot Analytics Model

Analytics and metrics for HelpBot usage and performance.

Complies with .claude/rules.md Rule #7: Model classes < 150 lines
"""

import uuid
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.tenants.models import TenantAwareModel
from apps.core.models import BaseModel


class HelpBotAnalytics(BaseModel, TenantAwareModel):
    """
    Analytics and metrics for HelpBot usage and performance.
    Used for monitoring and continuous improvement.
    """

    class MetricTypeChoices(models.TextChoices):
        SESSION_COUNT = "session_count", _("Session Count")
        MESSAGE_COUNT = "message_count", _("Message Count")
        RESPONSE_TIME = "response_time", _("Response Time")
        USER_SATISFACTION = "user_satisfaction", _("User Satisfaction")
        KNOWLEDGE_USAGE = "knowledge_usage", _("Knowledge Usage")
        ERROR_RATE = "error_rate", _("Error Rate")

    analytics_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    metric_type = models.CharField(
        _("Metric Type"),
        max_length=30,
        choices=MetricTypeChoices.choices
    )
    value = models.FloatField(
        _("Value"),
        help_text="Numeric value of the metric"
    )
    dimension_data = models.JSONField(
        _("Dimension Data"),
        default=dict,
        blank=True,
        help_text="Breakdown dimensions (e.g., by category, user type, time period)"
    )
    date = models.DateField(
        _("Date"),
        default=timezone.now,
        help_text="Date for this metric"
    )
    hour = models.IntegerField(
        _("Hour"),
        null=True,
        blank=True,
        help_text="Hour of day (0-23) for hourly metrics"
    )

    class Meta(BaseModel.Meta):
        db_table = "helpbot_analytics"
        verbose_name = "HelpBot Analytics"
        verbose_name_plural = "HelpBot Analytics"
        get_latest_by = ["date", "cdtz"]
        indexes = [
            models.Index(fields=['metric_type', 'date'], name='hb_analytics_metric_dt_idx'),
            models.Index(fields=['date', 'hour'], name='hb_analytics_date_hr_idx'),
        ]
        unique_together = [
            ('metric_type', 'date', 'hour')
        ]

    def __str__(self):
        return f"{self.metric_type}: {self.value} on {self.date}"
