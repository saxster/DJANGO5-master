"""
Work Order Management - Work Order Details Model

Checklist questions and answers for work order verification.
Links to QuestionSet and provides response capture.
"""
import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from concurrency.fields import VersionField

from apps.peoples.models import BaseModel
from apps.tenants.models import TenantAwareModel
from ..managers import WOMDetailsManager
from .enums import AnswerType, AvptType


class WomDetails(BaseModel, TenantAwareModel):
    """
    Work order checklist details - questions and answers.

    Captures responses to inspection checklist items for work order
    verification and quality scoring.
    """

    # Enum classes for backward compatibility
    AnswerType = AnswerType
    AvptType = AvptType

    uuid = models.UUIDField(unique=True, editable=False, blank=True, default=uuid.uuid4)
    seqno = models.SmallIntegerField(_("SL #"))
    question = models.ForeignKey(
        "activity.Question", verbose_name=_(""), on_delete=models.RESTRICT
    )
    answertype = models.CharField(
        _("Answer Type"), max_length=50, choices=AnswerType.choices, null=True
    )
    qset = models.ForeignKey(
        "activity.QuestionSet",
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="qset_answers",
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
    alerton = models.CharField(_("Alert On"), null=True, blank=True, max_length=50)
    ismandatory = models.BooleanField(_("Mandatory"), default=True)
    wom = models.ForeignKey(
        "Wom", verbose_name=_("Jobneed"), null=True, blank=True, on_delete=models.RESTRICT
    )
    alerts = models.BooleanField(_("Alerts"), default=False)
    attachmentcount = models.IntegerField(_("Attachment count"), default=0)

    # Optimistic locking for concurrent updates (Rule #17)
    version = VersionField()

    objects = WOMDetailsManager()

    class Meta(BaseModel.Meta):
        db_table = "womdetails"
        verbose_name = "Wom Details"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "question", "wom"],
                name="tenant_question_client"
            )
        ]
        indexes = [
            models.Index(fields=['tenant', 'wom'], name='womdetails_tenant_wom_idx'),
            models.Index(fields=['tenant', 'question'], name='womdetails_tenant_question_idx'),
        ]
