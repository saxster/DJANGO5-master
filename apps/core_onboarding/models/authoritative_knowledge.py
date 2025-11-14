"""
Authoritative Knowledge Model - Grounding knowledge for LLMs.

Stores authoritative knowledge sources for LLM validation and grounding.
Part of the shared kernel for conversational AI onboarding.
"""

import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.postgres.fields import ArrayField

from apps.tenants.models import TenantAwareModel
from apps.core.models import BaseModel


class AuthoritativeKnowledge(BaseModel, TenantAwareModel):
    """Stores authoritative knowledge for LLM grounding and validation."""

    class AuthorityLevelChoices(models.TextChoices):
        LOW = "low", _("Low")
        MEDIUM = "medium", _("Medium")
        HIGH = "high", _("High")
        OFFICIAL = "official", _("Official")

    knowledge_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    source_organization = models.CharField(
        _("Source Organization"),
        max_length=200,
        help_text="Organization that published this knowledge"
    )
    document_title = models.CharField(
        _("Document Title"),
        max_length=500,
        help_text="Title of the source document"
    )
    document_version = models.CharField(
        _("Document Version"),
        max_length=50,
        blank=True,
        help_text="Version of the document"
    )
    authority_level = models.CharField(
        _("Authority Level"),
        max_length=20,
        choices=AuthorityLevelChoices.choices,
        default=AuthorityLevelChoices.MEDIUM
    )
    content_vector = ArrayField(
        models.FloatField(),
        verbose_name=_("Content Vector"),
        help_text="Vector embedding of the content",
        null=True,
        blank=True
    )
    content_summary = models.TextField(
        _("Content Summary"),
        help_text="Summary of the knowledge content"
    )
    publication_date = models.DateTimeField(
        _("Publication Date"),
        help_text="When this knowledge was published"
    )
    last_verified = models.DateTimeField(
        _("Last Verified"),
        auto_now=True,
        help_text="When this knowledge was last verified"
    )
    is_current = models.BooleanField(
        _("Is Current"),
        default=True,
        help_text="Whether this knowledge is still current"
    )

    class Meta(BaseModel.Meta):
        db_table = "authoritative_knowledge"
        verbose_name = "Authoritative Knowledge"
        verbose_name_plural = "Authoritative Knowledge"
        get_latest_by = ["publication_date", "mdtz"]
        indexes = [
            models.Index(fields=['cdtz'], name='auth_know_cdtz_idx'),
            models.Index(fields=['mdtz'], name='auth_know_mdtz_idx'),
        ]

    def __str__(self):
        return f"{self.document_title} - {self.source_organization}"
