"""
HelpBot Knowledge Base Model

HelpBot-specific knowledge base entries.

Complies with .claude/rules.md Rule #7: Model classes < 150 lines
"""

import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.postgres.fields import ArrayField

from apps.tenants.models import TenantAwareModel
from apps.peoples.models import BaseModel


class HelpBotKnowledge(BaseModel, TenantAwareModel):
    """
    HelpBot-specific knowledge base entries.
    Extends existing AuthoritativeKnowledge with HelpBot-specific features.
    """

    class KnowledgeTypeChoices(models.TextChoices):
        DOCUMENTATION = "documentation", _("Documentation")
        FAQ = "faq", _("FAQ")
        TUTORIAL = "tutorial", _("Tutorial")
        API_REFERENCE = "api_reference", _("API Reference")
        TROUBLESHOOTING = "troubleshooting", _("Troubleshooting")
        FEATURE_GUIDE = "feature_guide", _("Feature Guide")
        ERROR_SOLUTION = "error_solution", _("Error Solution")

    class CategoryChoices(models.TextChoices):
        OPERATIONS = "operations", _("Operations")
        ASSETS = "assets", _("Assets")
        PEOPLE = "people", _("People")
        HELPDESK = "helpdesk", _("Help Desk")
        REPORTS = "reports", _("Reports")
        ADMINISTRATION = "administration", _("Administration")
        TECHNICAL = "technical", _("Technical")
        GENERAL = "general", _("General")

    knowledge_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    title = models.CharField(
        _("Title"),
        max_length=500,
        help_text="Human-readable title for this knowledge entry"
    )
    content = models.TextField(
        _("Content"),
        help_text="The actual help content (markdown supported)"
    )
    knowledge_type = models.CharField(
        _("Knowledge Type"),
        max_length=30,
        choices=KnowledgeTypeChoices.choices,
        default=KnowledgeTypeChoices.DOCUMENTATION
    )
    category = models.CharField(
        _("Category"),
        max_length=30,
        choices=CategoryChoices.choices,
        default=CategoryChoices.GENERAL
    )
    tags = ArrayField(
        models.CharField(max_length=50),
        verbose_name=_("Tags"),
        default=list,
        blank=True,
        help_text="Search tags and keywords"
    )
    related_urls = ArrayField(
        models.URLField(max_length=500),
        verbose_name=_("Related URLs"),
        default=list,
        blank=True,
        help_text="Related application URLs or external links"
    )
    search_keywords = ArrayField(
        models.CharField(max_length=100),
        verbose_name=_("Search Keywords"),
        default=list,
        blank=True,
        help_text="Keywords that should trigger this knowledge"
    )
    embedding_vector = ArrayField(
        models.FloatField(),
        verbose_name=_("Embedding Vector"),
        null=True,
        blank=True,
        help_text="Vector embedding for semantic search"
    )
    usage_count = models.IntegerField(
        _("Usage Count"),
        default=0,
        help_text="Number of times this knowledge has been accessed"
    )
    effectiveness_score = models.FloatField(
        _("Effectiveness Score"),
        default=0.5,
        help_text="How effective this knowledge is based on user feedback (0.0 to 1.0)"
    )
    is_active = models.BooleanField(
        _("Is Active"),
        default=True,
        help_text="Whether this knowledge entry is active and searchable"
    )
    source_file = models.CharField(
        _("Source File"),
        max_length=500,
        blank=True,
        null=True,
        help_text="Original file path if imported from documentation"
    )
    last_updated = models.DateTimeField(
        _("Last Updated"),
        auto_now=True,
        help_text="When this knowledge was last updated"
    )

    class Meta(BaseModel.Meta):
        db_table = "helpbot_knowledge"
        verbose_name = "HelpBot Knowledge"
        verbose_name_plural = "HelpBot Knowledge"
        get_latest_by = ["last_updated", "mdtz"]
        indexes = [
            models.Index(fields=['category', 'knowledge_type'], name='hb_knowledge_cat_type_idx'),
            models.Index(fields=['is_active', 'effectiveness_score'], name='hb_knowledge_active_idx'),
            models.Index(fields=['usage_count'], name='hb_knowledge_usage_idx'),
        ]

    def __str__(self):
        return f"{self.title} ({self.category})"
