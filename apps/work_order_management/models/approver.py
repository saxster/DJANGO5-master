"""
Work Order Management - Approver Model

Approver and verifier configuration for work order approval flows.
"""
from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.utils.translation import gettext_lazy as _
from django.conf import settings

from apps.core.models import BaseModel
from apps.tenants.models import TenantAwareModel
from ..managers import ApproverManager
from .enums import ApproverIdentifier


class Approver(BaseModel, TenantAwareModel):
    """
    Approver/Verifier configuration model.

    Defines who can approve/verify work orders for specific categories
    and sites. Supports both site-specific and global approvers.
    """

    # Enum class for backward compatibility
    Identifier = ApproverIdentifier

    approverfor = ArrayField(
        models.CharField(_("Approver/Verifier For"), max_length=50, blank=True),
        null=True,
        blank=True,
    )
    sites = ArrayField(
        models.CharField(max_length=50, blank=True),
        null=True,
        blank=True,
        verbose_name=_("Sites"),
    )
    forallsites = models.BooleanField(_("For all sites"), default=True)
    people = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Approver"),
        on_delete=models.RESTRICT,
        null=True,
    )
    bu = models.ForeignKey(
        "client_onboarding.Bt", verbose_name=_(""), on_delete=models.RESTRICT, null=True
    )
    client = models.ForeignKey(
        "client_onboarding.Bt",
        on_delete=models.RESTRICT,
        null=True,
        related_name="approver_clients",
    )
    identifier = models.CharField(
        _("Approver/Verifier"),
        choices=ApproverIdentifier.choices,
        max_length=250,
        null=True,
        blank=True,
    )

    objects = ApproverManager()

    class Meta(BaseModel.Meta):
        db_table = "approver"
        verbose_name = "approver"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "people", "approverfor", "sites"],
                name="tenant_people_approverfor_sites_uk",
            )
        ]
        indexes = [
            models.Index(fields=['tenant', 'people'], name='approver_tenant_people_idx'),
            models.Index(fields=['tenant', 'identifier'], name='approver_tenant_identifier_idx'),
        ]
