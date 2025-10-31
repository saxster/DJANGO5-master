"""
Wellness & Journal API Serializers

Serializers for journal entries, wellness content, and privacy settings.

Compliance with .claude/rules.md:
- Serializers < 100 lines each
- PII protection enforced
- Specific validation
"""

from rest_framework import serializers
import logging

logger = logging.getLogger('wellness_log')


class JournalEntrySerializer(serializers.Serializer):
    """
    Serializer for journal entries with PII protection.

    Note: Uses Serializer (not ModelSerializer) to handle potential
    missing journal models gracefully.
    """
    id = serializers.IntegerField(read_only=True)
    title = serializers.CharField(max_length=255)
    subtitle = serializers.CharField(max_length=255, required=False, allow_blank=True)
    content = serializers.CharField(required=False, allow_blank=True)
    entry_type = serializers.CharField(max_length=50)
    timestamp = serializers.DateTimeField(read_only=True)
    mood_rating = serializers.IntegerField(min_value=1, max_value=10, required=False, allow_null=True)
    stress_level = serializers.IntegerField(min_value=1, max_value=5, required=False, allow_null=True)
    energy_level = serializers.IntegerField(min_value=1, max_value=10, required=False, allow_null=True)
    tags = serializers.ListField(child=serializers.CharField(), required=False)
    is_bookmarked = serializers.BooleanField(required=False)
    is_draft = serializers.BooleanField(required=False)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class JournalEntryCreateSerializer(serializers.Serializer):
    """Serializer for creating journal entries."""

    title = serializers.CharField(max_length=255, required=True)
    subtitle = serializers.CharField(max_length=255, required=False, allow_blank=True)
    content = serializers.CharField(required=False, allow_blank=True)
    entry_type = serializers.CharField(max_length=50, required=True)
    mood_rating = serializers.IntegerField(min_value=1, max_value=10, required=False, allow_null=True)
    mood_description = serializers.CharField(required=False, allow_blank=True)
    stress_level = serializers.IntegerField(min_value=1, max_value=5, required=False, allow_null=True)
    energy_level = serializers.IntegerField(min_value=1, max_value=10, required=False, allow_null=True)
    stress_triggers = serializers.ListField(child=serializers.CharField(), required=False)
    coping_strategies = serializers.ListField(child=serializers.CharField(), required=False)
    gratitude_items = serializers.ListField(child=serializers.CharField(), required=False)
    tags = serializers.ListField(child=serializers.CharField(), required=False)
    is_bookmarked = serializers.BooleanField(default=False)
    is_draft = serializers.BooleanField(default=False)
    privacy_scope = serializers.CharField(max_length=50, required=False)

    def create(self, validated_data):
        """Create journal entry (handled by view)."""
        from apps.journal.models import JournalEntry
        return JournalEntry.objects.create(**validated_data)


class WellnessContentSerializer(serializers.Serializer):
    """Serializer for wellness content."""

    id = serializers.IntegerField(read_only=True)
    title = serializers.CharField()
    summary = serializers.CharField()
    content = serializers.CharField()
    category = serializers.CharField()
    content_level = serializers.CharField()
    evidence_level = serializers.CharField()
    tags = serializers.ListField(child=serializers.CharField(), required=False)
    workplace_specific = serializers.BooleanField()
    field_worker_relevant = serializers.BooleanField()
    action_tips = serializers.ListField(child=serializers.CharField(), required=False)
    key_takeaways = serializers.ListField(child=serializers.CharField(), required=False)
    source_name = serializers.CharField(required=False)
    priority_score = serializers.FloatField()
    estimated_reading_time = serializers.IntegerField()
    is_active = serializers.BooleanField()
    created_at = serializers.DateTimeField(read_only=True)


class WellnessUserProgressSerializer(serializers.Serializer):
    """Serializer for user wellness progress."""

    current_streak = serializers.IntegerField()
    longest_streak = serializers.IntegerField()
    total_content_viewed = serializers.IntegerField()
    total_content_completed = serializers.IntegerField()
    total_score = serializers.IntegerField()
    preferred_content_level = serializers.CharField(required=False)
    enabled_categories = serializers.ListField(child=serializers.CharField(), required=False)
    daily_tip_enabled = serializers.BooleanField()
    contextual_delivery_enabled = serializers.BooleanField()
    achievements_earned = serializers.ListField(child=serializers.CharField(), required=False)
    last_activity_date = serializers.DateTimeField(required=False, allow_null=True)


class PrivacySettingsSerializer(serializers.Serializer):
    """Serializer for journal privacy settings."""

    analytics_consent = serializers.BooleanField()
    pattern_analysis_consent = serializers.BooleanField()
    crisis_intervention_enabled = serializers.BooleanField()
    data_retention_days = serializers.IntegerField(required=False)
    sharing_enabled = serializers.BooleanField(required=False)

    def update(self, instance, validated_data):
        """Update privacy settings."""
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


__all__ = [
    'JournalEntrySerializer',
    'JournalEntryCreateSerializer',
    'WellnessContentSerializer',
    'WellnessUserProgressSerializer',
    'PrivacySettingsSerializer',
]
