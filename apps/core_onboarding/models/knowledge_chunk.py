"""
Knowledge Chunk Model - Chunked content for RAG retrieval.

Stores chunked knowledge content for efficient RAG retrieval.
Part of the shared kernel for conversational AI onboarding (Phase 2).
"""

import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.postgres.fields import ArrayField

from apps.tenants.models import TenantAwareModel
from apps.peoples.models import BaseModel
from .authoritative_knowledge import AuthoritativeKnowledge


class AuthoritativeKnowledgeChunk(BaseModel, TenantAwareModel):
    """Chunked knowledge content for RAG retrieval (Phase 2)."""

    chunk_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    knowledge = models.ForeignKey(
        AuthoritativeKnowledge,
        on_delete=models.CASCADE,
        related_name="chunks",
        verbose_name=_("Knowledge Document")
    )
    chunk_index = models.IntegerField(
        _("Chunk Index"),
        help_text="Sequential chunk number within the document"
    )
    content_text = models.TextField(
        _("Content Text"),
        help_text="Text content of this chunk"
    )
    content_vector = ArrayField(
        models.FloatField(),
        verbose_name=_("Content Vector"),
        help_text="Vector embedding of the chunk content",
        null=True,
        blank=True
    )
    tags = models.JSONField(
        _("Tags"),
        default=dict,
        blank=True,
        help_text="Metadata tags for filtering and categorization"
    )
    last_verified = models.DateTimeField(
        _("Last Verified"),
        auto_now=True,
        help_text="When this chunk was last verified for accuracy"
    )
    is_current = models.BooleanField(
        _("Is Current"),
        default=True,
        help_text="Whether this chunk is still current and valid"
    )

    class Meta(BaseModel.Meta):
        db_table = "authoritative_knowledge_chunk"
        verbose_name = "Knowledge Chunk"
        verbose_name_plural = "Knowledge Chunks"
        get_latest_by = ["last_verified", "mdtz"]
        indexes = [
            models.Index(fields=['knowledge', 'chunk_index'], name='knowledge_chunk_idx'),
            models.Index(fields=['is_current'], name='chunk_current_idx'),
        ]

    def __str__(self):
        return f"Chunk {self.chunk_index} of {self.knowledge.document_title}"
