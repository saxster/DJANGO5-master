"""
Conversation Memory Models for Help Center AI Assistant.

Implements short-term and long-term memory for better context awareness.

Based on 2025 RAG best practices:
- Short-term: Last 5 messages in current session
- Long-term: User preferences, common issues, past solutions
- Context carryover: "As we discussed earlier..." references

Model: HelpConversationMemory (<150 lines)

Following CLAUDE.md Rule #7
"""

from django.db import models
from django.utils import timezone
from datetime import timedelta
from apps.tenants.models import TenantAwareModel
from apps.peoples.models import People


class HelpConversationMemory(TenantAwareModel):
    """
    AI conversation memory for context preservation.

    Memory Types:
    - SHORT_TERM: Current session context (expires after session)
    - LONG_TERM: User preferences, repeated issues (expires after 90 days)
    - FACT: Learned facts about user (never expires)
    """

    class MemoryType(models.TextChoices):
        SHORT_TERM = 'SHORT_TERM', 'Short-term (current session)'
        LONG_TERM = 'LONG_TERM', 'Long-term (user preferences)'
        FACT = 'FACT', 'Fact (permanent)'

    user = models.ForeignKey(
        People,
        on_delete=models.CASCADE,
        related_name='help_memories'
    )

    session_id = models.UUIDField(
        db_index=True,
        help_text="Session UUID for grouping memories"
    )

    memory_type = models.CharField(
        max_length=20,
        choices=MemoryType.choices,
        default=MemoryType.SHORT_TERM,
        db_index=True
    )

    key = models.CharField(
        max_length=200,
        db_index=True,
        help_text="Memory key (e.g., 'preferred_language', 'common_issue')"
    )

    value = models.JSONField(
        help_text="Memory value (can be string, number, object, array)"
    )

    confidence = models.FloatField(
        default=1.0,
        help_text="Confidence score (0-1) for this memory"
    )

    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="When memory expires (null = never)"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'help_center_conversation_memory'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'session_id'], name='help_memory_user_session_idx'),
            models.Index(fields=['memory_type', 'expires_at'], name='help_memory_type_expires_idx'),
            models.Index(fields=['key'], name='help_memory_key_idx'),
        ]
        unique_together = [['user', 'session_id', 'key']]

    @classmethod
    def store(cls, user, session_id, key, value, memory_type='SHORT_TERM', ttl_days=None):
        """
        Store memory for user.

        Args:
            user: People instance
            session_id: UUID
            key: Memory key
            value: Memory value (JSON-serializable)
            memory_type: SHORT_TERM, LONG_TERM, or FACT
            ttl_days: Days until expiration (None = never)

        Returns:
            HelpConversationMemory instance
        """
        expires_at = None
        if ttl_days:
            expires_at = timezone.now() + timedelta(days=ttl_days)
        elif memory_type == 'SHORT_TERM':
            expires_at = timezone.now() + timedelta(hours=24)
        elif memory_type == 'LONG_TERM':
            expires_at = timezone.now() + timedelta(days=90)

        memory, created = cls.objects.update_or_create(
            user=user,
            session_id=session_id,
            key=key,
            defaults={
                'value': value,
                'memory_type': memory_type,
                'expires_at': expires_at,
                'tenant': user.tenant
            }
        )

        return memory

    @classmethod
    def recall(cls, user, session_id, key):
        """
        Recall memory for user.

        Args:
            user: People instance
            session_id: UUID
            key: Memory key

        Returns:
            Memory value or None if not found/expired
        """
        try:
            memory = cls.objects.get(
                user=user,
                session_id=session_id,
                key=key
            )

            if memory.expires_at and memory.expires_at < timezone.now():
                memory.delete()
                return None

            return memory.value

        except cls.DoesNotExist:
            return None

    @classmethod
    def get_session_context(cls, user, session_id):
        """
        Get all active memories for session.

        Returns dict of {key: value} for use in AI context.
        """
        memories = cls.objects.filter(
            user=user,
            session_id=session_id
        ).filter(
            models.Q(expires_at__isnull=True) |
            models.Q(expires_at__gte=timezone.now())
        )

        return {mem.key: mem.value for mem in memories}

    def __str__(self):
        return f"{self.user.username} - {self.key}: {self.value}"
