"""
HelpBot API Serializers

Serializers for helpbot sessions, messages, and knowledge base.

Compliance with .claude/rules.md:
- Serializers < 100 lines
"""

from rest_framework import serializers


class HelpBotSessionSerializer(serializers.Serializer):
    """Serializer for helpbot sessions."""

    session_id = serializers.UUIDField()
    session_type = serializers.CharField()
    current_state = serializers.CharField()
    language = serializers.CharField(default='en')
    total_messages = serializers.IntegerField()
    satisfaction_rating = serializers.IntegerField(required=False, allow_null=True)
    last_activity = serializers.DateTimeField()


class HelpBotMessageSerializer(serializers.Serializer):
    """Serializer for helpbot messages."""

    message_id = serializers.UUIDField()
    message_type = serializers.CharField()
    content = serializers.CharField()
    confidence_score = serializers.FloatField(required=False)
    created_at = serializers.DateTimeField()


class HelpBotKnowledgeSerializer(serializers.Serializer):
    """Serializer for knowledge base articles."""

    id = serializers.IntegerField()
    title = serializers.CharField()
    content = serializers.CharField()
    category = serializers.CharField()
    tags = serializers.ListField(child=serializers.CharField(), required=False)
    effectiveness_score = serializers.FloatField()
    is_active = serializers.BooleanField()


__all__ = [
    'HelpBotSessionSerializer',
    'HelpBotMessageSerializer',
    'HelpBotKnowledgeSerializer',
]
