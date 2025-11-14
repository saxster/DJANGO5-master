"""
Reminder Model

Manages email reminders for scheduled jobs (PPM, tours, tasks).

Migrated from apps.reminder (Nov 11, 2025):
- Backend-only model (no UI)
- Used exclusively by apps/scheduler/utils.py
- Handles reminder notifications for maintenance jobs

Architecture Note:
This was originally a separate app but had no views/tests/URLs.
Merged into scheduler for better co-location with its only consumer.
"""

from django.db import models
from django.db.models import Q, F, ExpressionWrapper
from django.db.models.functions import Cast
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from datetime import datetime, timezone as dt_timezone, timedelta
from apps.core.models import BaseModel


class ReminderManager(models.Manager):
    """Manager for Reminder model with custom queries."""

    use_in_migrations = True

    def get_all_due_reminders(self):
        """
        Get all due reminders that haven't been sent successfully.

        Returns queryset with related fields and timezone-adjusted dates.
        """
        qset = self.select_related(
            'bu', 'job', 'asset', 'qset', 'group', 'people'
        ).annotate(
            rdate=ExpressionWrapper(
                F('reminderdate') + timedelta(minutes=1) * Cast('ctzoffset', models.IntegerField()),
                output_field=models.DateTimeField(),
            ),
            pdate=ExpressionWrapper(
                F('plandatetime') + timedelta(minutes=1) * Cast('ctzoffset', models.IntegerField()),
                output_field=models.DateTimeField(),
            ),
        ).filter(
            ~Q(status='SUCCESS'),
            reminderdate__gt=timezone.now(),
        ).values(
            'rdate', 'pdate', 'job__jobname', 'bu__buname', 'asset__assetname', 'job__jobdesc',
            'qset__qsetname', 'priority', 'reminderin', 'people__peoplename', 'cuser__peoplename',
            'group__groupname', 'people_id', 'group_id', 'cuser_id', 'muser_id', 'mailids',
            'muser__peoplename', 'id'
        ).distinct()

        return qset or self.none()


class Reminder(BaseModel):
    """
    Reminder model for scheduled maintenance jobs.

    Sends email notifications before PPM jobs, tours, or other scheduled work.
    Supports recurring reminders with various frequencies.
    """

    class Priority(models.TextChoices):
        HIGH = "HIGH", _('High')
        LOW = "LOW", _('Low')
        MEDIUM = "MEDIU", _('Medium')

    class Frequency(models.TextChoices):
        NONE = "NONE", _('None')
        DAILY = "DAILY", _("Daily")
        WEEKLY = "WEEKLY", _("Weekly")
        MONTHLY = "MONTHLY", _("Monthly")
        BIMONTHLY = "BIMONTHLY", _("Bimonthly")
        QUARTERLY = "QUARTERLY", _("Quarterly")
        HALFYEARLY = "HALFYEARLY", _("Half Yearly")
        YEARLY = "YEARLY", _("Yearly")
        FORTNIGHTLY = "FORTNIGHTLY", _("Fort Nightly")

    class StatusChoices(models.TextChoices):
        SUCCESS = "SUCCESS", _("Success")
        FAILED = 'FAILED', _('Failed')

    description = models.TextField(_('Description'), max_length=500)
    bu = models.ForeignKey(
        "client_onboarding.Bt",
        verbose_name=_("Site"),
        on_delete=models.RESTRICT,
        blank=True
    )
    asset = models.ForeignKey(
        "activity.Asset",
        verbose_name=_("Asset"),
        on_delete=models.RESTRICT,
        blank=True
    )
    qset = models.ForeignKey(
        "activity.Questionset",
        verbose_name=_("Question Set"),
        on_delete=models.RESTRICT,
        blank=True
    )
    people = models.ForeignKey(
        "peoples.People",
        verbose_name=_("People"),
        on_delete=models.RESTRICT,
        blank=True
    )
    group = models.ForeignKey(
        "peoples.Pgroup",
        verbose_name=_("Group"),
        on_delete=models.RESTRICT,
        blank=True
    )
    priority = models.CharField(
        _("Priority"),
        max_length=50,
        choices=Priority.choices
    )
    reminderdate = models.DateTimeField(_("Reminder Date"), null=True)
    reminderin = models.CharField(
        _("Reminder In"),
        choices=Frequency.choices,
        max_length=20
    )
    reminderbefore = models.IntegerField(_("Reminder Before"))
    job = models.ForeignKey(
        "activity.Job",
        verbose_name=_("Job"),
        on_delete=models.RESTRICT,
        blank=True
    )
    jobneed = models.ForeignKey(
        "activity.Jobneed",
        verbose_name=_("Jobneed"),
        on_delete=models.RESTRICT,
        blank=True
    )
    plandatetime = models.DateTimeField(_("Plan Datetime"), null=True)
    mailids = models.TextField(_("Mail Ids"), max_length=500)
    status = models.CharField(
        _("Status"),
        choices=StatusChoices.choices,
        max_length=50
    )

    objects = ReminderManager()

    class Meta(BaseModel.Meta):
        db_table = 'reminder'  # Keep existing table name
        verbose_name = 'Reminder'
        verbose_name_plural = 'Reminders'

    def __str__(self):
        return f'{self.asset}'
