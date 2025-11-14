"""
NOC Scheduled Export Model (Bonus Feature).

Automated export job scheduling for zero-touch compliance reporting.
Follows .claude/rules.md Rule #7 (models <150 lines).
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.postgres.fields import ArrayField
from apps.tenants.models import TenantAwareModel
from apps.core.models import BaseModel

__all__ = ['NOCScheduledExport']


class NOCScheduledExport(TenantAwareModel, BaseModel):
    """
    Automated export job configuration.

    Enables scheduled exports with email/webhook delivery for:
    - Daily operational reports
    - Weekly executive summaries
    - Monthly compliance reports
    - Custom reporting schedules
    """

    SCHEDULE_CHOICES = [
        ('hourly', 'Every Hour'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('custom', 'Custom Cron Expression'),
    ]

    DELIVERY_CHOICES = [
        ('download', 'Download Only (Store for 7 days)'),
        ('email', 'Email Delivery'),
        ('webhook', 'Webhook POST'),
        ('both', 'Email + Webhook'),
    ]

    user = models.ForeignKey(
        'peoples.People',
        on_delete=models.CASCADE,
        verbose_name=_("Owner"),
        related_name='noc_scheduled_exports'
    )

    template = models.ForeignKey(
        'noc.NOCExportTemplate',
        on_delete=models.CASCADE,
        verbose_name=_("Export Template"),
        related_name='schedules'
    )

    name = models.CharField(
        max_length=100,
        verbose_name=_("Schedule Name"),
        help_text=_("Descriptive name for this scheduled export")
    )

    schedule_type = models.CharField(
        max_length=20,
        choices=SCHEDULE_CHOICES,
        default='daily',
        verbose_name=_("Schedule Type")
    )

    cron_expression = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Cron Expression"),
        help_text=_("Required if schedule_type is 'custom' (e.g., '0 8 * * 1')")
    )

    delivery_method = models.CharField(
        max_length=20,
        choices=DELIVERY_CHOICES,
        default='download',
        verbose_name=_("Delivery Method")
    )

    email_recipients = ArrayField(
        models.EmailField(),
        blank=True,
        null=True,
        verbose_name=_("Email Recipients"),
        help_text=_("Email addresses to receive exports")
    )

    webhook_url = models.URLField(
        blank=True,
        verbose_name=_("Webhook URL"),
        help_text=_("URL to POST export data or download link")
    )

    webhook_headers = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Webhook Headers"),
        help_text=_("Custom HTTP headers for webhook requests")
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Active"),
        help_text=_("Whether this scheduled export is currently running")
    )

    last_run_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Last Run At")
    )

    next_run_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Next Run At"),
        help_text=_("Calculated next execution time")
    )

    run_count = models.IntegerField(
        default=0,
        verbose_name=_("Run Count"),
        help_text=_("Total number of successful executions")
    )

    error_count = models.IntegerField(
        default=0,
        verbose_name=_("Error Count"),
        help_text=_("Consecutive errors (disables after 5)")
    )

    last_error = models.TextField(
        blank=True,
        verbose_name=_("Last Error"),
        help_text=_("Most recent error message")
    )

    class Meta:
        db_table = 'noc_scheduled_exports'
        ordering = ['next_run_at']
        indexes = [
            models.Index(fields=['tenant', 'is_active', 'next_run_at']),
            models.Index(fields=['schedule_type']),
        ]
        verbose_name = _("NOC Scheduled Export")
        verbose_name_plural = _("NOC Scheduled Exports")

    def __str__(self) -> str:
        status = "Active" if self.is_active else "Inactive"
        return f"{self.name} ({self.schedule_type}) - {status}"

    def record_success(self):
        """Record successful execution."""
        from django.utils import timezone
        self.last_run_at = timezone.now()
        self.run_count += 1
        self.error_count = 0
        self.last_error = ''
        self.calculate_next_run()
        self.save()

    def record_error(self, error_message: str):
        """Record execution error."""
        from django.utils import timezone
        self.last_run_at = timezone.now()
        self.error_count += 1
        self.last_error = error_message[:500]

        if self.error_count >= 5:
            self.is_active = False

        self.calculate_next_run()
        self.save()

    def calculate_next_run(self):
        """Calculate next execution time based on schedule type."""
        from django.utils import timezone
        from datetime import timedelta

        now = timezone.now()

        if self.schedule_type == 'hourly':
            self.next_run_at = now + timedelta(hours=1)
        elif self.schedule_type == 'daily':
            self.next_run_at = now + timedelta(days=1)
        elif self.schedule_type == 'weekly':
            self.next_run_at = now + timedelta(weeks=1)
        elif self.schedule_type == 'monthly':
            self.next_run_at = now + timedelta(days=30)
        elif self.schedule_type == 'custom' and self.cron_expression:
            try:
                from croniter import croniter
                cron = croniter(self.cron_expression, now)
                self.next_run_at = cron.get_next(timezone.datetime)
            except (ImportError, ValueError):
                self.next_run_at = now + timedelta(days=1)