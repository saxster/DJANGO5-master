"""
JobneedDetails Model - Per-Question Checklist Details

Tied to specific Jobneed execution.
Stores question answers, validations, attachments, alerts.
seqno: Display order within the jobneed's checklist.
"""

import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.activity.managers.job import JobneedDetailsManager
from apps.activity.models.question_model import QuestionSet
from apps.core.models import BaseModel
from apps.tenants.models import TenantAwareModel


class JobneedDetails(BaseModel, TenantAwareModel):
    """
    JobneedDetails - Per-question details for checklist items

    Tied to specific Jobneed execution.
    Unique constraints: (jobneed, question) and (jobneed, seqno).
    """

    # Import enums locally to avoid circular imports
    from .enums import AnswerType, AvptType

    # Expose enums as nested classes for backward compatibility
    AnswerType = AnswerType
    AvptType = AvptType

    uuid = models.UUIDField(unique=True, editable=True, blank=True, default=uuid.uuid4)
    seqno = models.SmallIntegerField(_("SL No."))
    question = models.ForeignKey(
        "activity.Question",
        verbose_name=_("Question"),
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
    )
    answertype = models.CharField(
        _("Answer Type"), max_length=50, choices=AnswerType.choices, null=True
    )
    answer = models.CharField(_("Answer"), max_length=250, default="", null=True)
    isavpt = models.BooleanField(_("Attachement Required"), default=False)
    avpttype = models.CharField(
        _("Attachment Type"),
        max_length=50,
        choices=AvptType.choices,
        null=True,
        blank=True,
    )
    options = models.CharField(_("Option"), max_length=2000, null=True, blank=True)
    min = models.DecimalField(_("Min"), max_digits=18, decimal_places=4, null=True)
    max = models.DecimalField(_("Max"), max_digits=18, decimal_places=4, null=True)
    alerton = models.CharField(_("Alert On"), null=True, blank=True, max_length=300)
    qset = models.ForeignKey(
        QuestionSet,
        verbose_name=("Question Set"),
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="questions_qset",
    )
    ismandatory = models.BooleanField(_("Mandatory"), default=True)
    jobneed = models.ForeignKey(
        "activity.Jobneed",
        verbose_name=_("Jobneed"),
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
    )
    alerts = models.BooleanField(_("Alerts"), default=False)
    attachmentcount = models.IntegerField(_("Attachment count"), default=0)
    transcript = models.TextField(_("Audio Transcript"), null=True, blank=True)
    transcript_status = models.CharField(
        _("Transcript Status"),
        max_length=20,
        choices=[
            ('PENDING', 'Pending'),
            ('PROCESSING', 'Processing'),
            ('COMPLETED', 'Completed'),
            ('FAILED', 'Failed'),
        ],
        null=True,
        blank=True
    )
    transcript_language = models.CharField(
        _("Transcript Language"),
        max_length=10,
        default='en-US',
        null=True,
        blank=True,
        help_text="Language code used for transcription (e.g., 'en-US', 'hi-IN')"
    )
    transcript_processed_at = models.DateTimeField(
        _("Transcript Processed At"),
        null=True,
        blank=True,
        help_text="Timestamp when transcript processing completed"
    )

    objects = JobneedDetailsManager()

    class Meta(BaseModel.Meta):
        db_table = "jobneeddetails"
        verbose_name = "JobneedDetails"
        verbose_name_plural = "Jobneed Details"
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'jobneed', 'question'],
                name='tenant_jobneeddetails_jobneed_question_uk',
                violation_error_message=(
                    "Duplicate question not allowed for the same jobneed. "
                    "Each question can only appear once per jobneed."
                )
            ),
            models.UniqueConstraint(
                fields=['tenant', 'jobneed', 'seqno'],
                name='tenant_jobneeddetails_jobneed_seqno_uk',
                violation_error_message=(
                    "Duplicate sequence number not allowed for the same jobneed. "
                    "Each seqno must be unique within a jobneed."
                )
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'jobneed'], name='jnd_tenant_jobneed_idx'),
            models.Index(fields=['tenant', 'question'], name='jnd_tenant_question_idx'),
        ]


__all__ = ['JobneedDetails']
