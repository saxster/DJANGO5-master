"""
Journal App Serializers

Comprehensive serializers for journal and wellness system with:
- Privacy-aware data serialization
- Nested relationships with media attachments
- Analytics data transformation
- Mobile sync support with conflict resolution
- Validation for wellbeing metrics and privacy settings
"""

from typing import Any, Dict, Optional

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from ..models import JournalEntry, JournalMediaAttachment, JournalPrivacySettings
from .validation_mixins import (
    ComprehensiveJournalValidationMixin,
    WellbeingMetricsValidationMixin,
    PrivacyValidationMixin
)
from .pii_redaction_mixin import PIIRedactionMixin
from ..logging import get_journal_logger

User = get_user_model()
logger = get_journal_logger(__name__)


class JournalMediaAttachmentSerializer(serializers.ModelSerializer):
    """Serializer for journal media attachments"""

    file_url = serializers.SerializerMethodField()
    file_size_display = serializers.SerializerMethodField()

    class Meta:
        model = JournalMediaAttachment
        fields = [
            'id', 'media_type', 'file', 'file_url', 'original_filename',
            'mime_type', 'file_size', 'file_size_display', 'caption',
            'display_order', 'is_hero_image', 'mobile_id', 'sync_status',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'file_size', 'mime_type', 'created_at', 'updated_at']

    def get_file_url(self, obj) -> Optional[str]:
        """Get full URL for media file"""
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None

    def get_file_size_display(self, obj) -> str:
        """Human readable file size"""
        if obj.file_size:
            if obj.file_size > 1024 * 1024:  # MB
                return f"{obj.file_size / (1024 * 1024):.1f} MB"
            elif obj.file_size > 1024:  # KB
                return f"{obj.file_size / 1024:.1f} KB"
            else:
                return f"{obj.file_size} bytes"
        return "Unknown"


class JournalPrivacySettingsSerializer(PrivacyValidationMixin, serializers.ModelSerializer):
    """Serializer for user privacy settings"""

    class Meta:
        model = JournalPrivacySettings
        fields = [
            'default_privacy_scope', 'wellbeing_sharing_consent',
            'manager_access_consent', 'analytics_consent',
            'crisis_intervention_consent', 'data_retention_days',
            'auto_delete_enabled', 'consent_timestamp', 'updated_at'
        ]
        read_only_fields = ['consent_timestamp', 'updated_at']

    def validate_data_retention_days(self, value):
        """Validate data retention period"""
        if value < 30:
            raise serializers.ValidationError("Data retention must be at least 30 days")
        if value > 3650:
            raise serializers.ValidationError("Data retention cannot exceed 10 years")
        return value

    def validate(self, data):
        """Enhanced privacy validation"""
        # Run privacy validation from mixin
        return super().validate(data)


class JournalEntryListSerializer(PIIRedactionMixin, serializers.ModelSerializer):
    """Lightweight serializer for journal entry lists"""

    # PII redaction configuration
    PII_FIELDS = ['title', 'subtitle']  # Always redact for non-owners
    PII_ADMIN_FIELDS = ['user_name']  # Partially redact for admins

    user_name = serializers.CharField(source='user.peoplename', read_only=True)
    media_count = serializers.SerializerMethodField()
    wellbeing_summary = serializers.SerializerMethodField()
    privacy_display = serializers.CharField(source='get_privacy_scope_display', read_only=True)

    class Meta:
        model = JournalEntry
        fields = [
            'id', 'title', 'subtitle', 'entry_type', 'timestamp',
            'privacy_scope', 'privacy_display', 'mood_rating',
            'stress_level', 'energy_level', 'location_site_name',
            'is_bookmarked', 'is_draft', 'sync_status',
            'user_name', 'media_count', 'wellbeing_summary',
            'created_at', 'updated_at'
        ]

    def get_media_count(self, obj) -> int:
        """Get count of media attachments"""
        return obj.media_attachments.count()

    def get_wellbeing_summary(self, obj) -> Optional[Dict[str, Any]]:
        """Get wellbeing metrics summary"""
        if not obj.has_wellbeing_metrics:
            return None

        summary = {}
        if obj.mood_rating:
            summary['mood'] = f"{obj.mood_rating}/10"
        if obj.stress_level:
            summary['stress'] = f"{obj.stress_level}/5"
        if obj.energy_level:
            summary['energy'] = f"{obj.energy_level}/10"

        return summary


class JournalEntryDetailSerializer(PIIRedactionMixin, ComprehensiveJournalValidationMixin, serializers.ModelSerializer):
    """Comprehensive serializer for journal entry details"""

    # PII redaction configuration
    PII_FIELDS = [
        'content', 'gratitude_items', 'affirmations', 'learnings',
        'challenges', 'stress_triggers', 'coping_strategies',
        'daily_goals', 'achievements', 'mood_description'
    ]  # Always redact for non-owners
    PII_ADMIN_FIELDS = ['title', 'subtitle', 'user_name']  # Partially redact for admins

    user_name = serializers.CharField(source='user.peoplename', read_only=True)
    media_attachments = JournalMediaAttachmentSerializer(many=True, read_only=True)
    privacy_display = serializers.CharField(source='get_privacy_scope_display', read_only=True)
    entry_type_display = serializers.CharField(source='get_entry_type_display', read_only=True)
    is_wellbeing_entry = serializers.BooleanField(read_only=True)
    has_wellbeing_metrics = serializers.BooleanField(read_only=True)

    class Meta:
        model = JournalEntry
        fields = [
            # Core fields
            'id', 'title', 'subtitle', 'content', 'entry_type',
            'entry_type_display', 'timestamp', 'duration_minutes',

            # Privacy and consent
            'privacy_scope', 'privacy_display', 'consent_given',
            'consent_timestamp', 'sharing_permissions',

            # Wellbeing metrics
            'mood_rating', 'mood_description', 'stress_level',
            'energy_level', 'stress_triggers', 'coping_strategies',

            # Positive psychology
            'gratitude_items', 'daily_goals', 'affirmations',
            'achievements', 'learnings', 'challenges',

            # Location and work context
            'location_site_name', 'location_address', 'location_coordinates',
            'location_area_type', 'team_members',

            # Categorization
            'tags', 'priority', 'severity',

            # Performance metrics
            'completion_rate', 'efficiency_score', 'quality_score',
            'items_processed',

            # Entry state
            'is_bookmarked', 'is_draft',

            # Sync fields
            'sync_status', 'mobile_id', 'version', 'last_sync_timestamp',

            # Computed fields
            'user_name', 'is_wellbeing_entry', 'has_wellbeing_metrics',

            # Relationships
            'media_attachments',

            # Audit
            'created_at', 'updated_at', 'metadata'
        ]
        read_only_fields = [
            'id', 'user_name', 'is_wellbeing_entry', 'has_wellbeing_metrics',
            'version', 'created_at', 'updated_at'
        ]

    # Validation methods moved to ComprehensiveJournalValidationMixin
    # This reduces code duplication and improves maintainability


class JournalEntryCreateSerializer(ComprehensiveJournalValidationMixin, serializers.ModelSerializer):
    """Serializer for creating new journal entries"""

    class Meta:
        model = JournalEntry
        fields = [
            'title', 'subtitle', 'content', 'entry_type', 'timestamp',
            'duration_minutes', 'privacy_scope', 'consent_given',
            'mood_rating', 'mood_description', 'stress_level',
            'energy_level', 'stress_triggers', 'coping_strategies',
            'gratitude_items', 'daily_goals', 'affirmations',
            'achievements', 'learnings', 'challenges',
            'location_site_name', 'location_address', 'location_coordinates',
            'location_area_type', 'team_members', 'tags', 'priority',
            'severity', 'completion_rate', 'efficiency_score',
            'quality_score', 'items_processed', 'is_bookmarked',
            'is_draft', 'mobile_id', 'metadata'
        ]

    def validate(self, data):
        """Validation for new entries"""
        # Set default timestamp if not provided
        if not data.get('timestamp'):
            data['timestamp'] = timezone.now()

        # Set consent timestamp if consent is given
        if data.get('consent_given') and not data.get('consent_timestamp'):
            data['consent_timestamp'] = timezone.now()

        # Run comprehensive validation from mixin
        return super().validate(data)

    def create(self, validated_data):
        """Create journal entry with proper user and tenant assignment"""
        user = self.context['request'].user
        validated_data['user'] = user
        validated_data['tenant'] = getattr(user, 'tenant', None)

        return super().create(validated_data)


class JournalEntryUpdateSerializer(ComprehensiveJournalValidationMixin, serializers.ModelSerializer):
    """Serializer for updating journal entries"""

    class Meta:
        model = JournalEntry
        fields = [
            'title', 'subtitle', 'content', 'mood_rating', 'mood_description',
            'stress_level', 'energy_level', 'stress_triggers', 'coping_strategies',
            'gratitude_items', 'daily_goals', 'affirmations', 'achievements',
            'learnings', 'challenges', 'location_site_name', 'location_address',
            'location_coordinates', 'location_area_type', 'team_members',
            'tags', 'priority', 'severity', 'completion_rate', 'efficiency_score',
            'quality_score', 'items_processed', 'is_bookmarked', 'is_draft',
            'privacy_scope', 'sharing_permissions', 'metadata'
        ]

    def update(self, instance, validated_data):
        """Update entry with version tracking"""
        # Increment version for conflict resolution
        instance.version += 1
        instance.last_sync_timestamp = timezone.now()

        return super().update(instance, validated_data)


class JournalSyncSerializer(serializers.Serializer):
    """Serializer for mobile client sync operations"""

    entries = serializers.ListField(
        child=serializers.DictField(),
        help_text="List of journal entries to sync"
    )
    last_sync_timestamp = serializers.DateTimeField(
        required=False,
        help_text="Last sync timestamp from client"
    )
    client_id = serializers.UUIDField(
        required=False,
        help_text="Client identifier for conflict resolution"
    )

    def validate_entries(self, entries):
        """Validate sync entries format"""
        required_fields = ['mobile_id', 'timestamp', 'entry_type', 'title']

        for entry in entries:
            for field in required_fields:
                if field not in entry:
                    raise serializers.ValidationError(
                        f"Missing required field '{field}' in sync entry"
                    )

        return entries


class JournalSearchSerializer(serializers.Serializer):
    """Serializer for journal search requests"""

    query = serializers.CharField(
        max_length=500,
        help_text="Search query text"
    )
    entry_types = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="Filter by entry types"
    )
    date_from = serializers.DateTimeField(
        required=False,
        help_text="Start date for date range filter"
    )
    date_to = serializers.DateTimeField(
        required=False,
        help_text="End date for date range filter"
    )
    mood_min = serializers.IntegerField(
        min_value=1,
        max_value=10,
        required=False,
        help_text="Minimum mood rating filter"
    )
    mood_max = serializers.IntegerField(
        min_value=1,
        max_value=10,
        required=False,
        help_text="Maximum mood rating filter"
    )
    stress_min = serializers.IntegerField(
        min_value=1,
        max_value=5,
        required=False,
        help_text="Minimum stress level filter"
    )
    stress_max = serializers.IntegerField(
        min_value=1,
        max_value=5,
        required=False,
        help_text="Maximum stress level filter"
    )
    location = serializers.CharField(
        max_length=200,
        required=False,
        help_text="Location filter"
    )
    tags = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="Tag filters"
    )
    sort_by = serializers.ChoiceField(
        choices=[
            ('relevance', 'Relevance'),
            ('timestamp', 'Date (Newest First)'),
            ('-timestamp', 'Date (Oldest First)'),
            ('mood_rating', 'Mood Rating'),
            ('stress_level', 'Stress Level'),
        ],
        default='relevance',
        help_text="Sort order for results"
    )

    def validate(self, data):
        """Cross-field validation for search parameters"""
        # Validate date range
        date_from = data.get('date_from')
        date_to = data.get('date_to')

        if date_from and date_to and date_from > date_to:
            raise serializers.ValidationError("date_from must be before date_to")

        # Validate mood range
        mood_min = data.get('mood_min')
        mood_max = data.get('mood_max')

        if mood_min and mood_max and mood_min > mood_max:
            raise serializers.ValidationError("mood_min must be less than or equal to mood_max")

        # Validate stress range
        stress_min = data.get('stress_min')
        stress_max = data.get('stress_max')

        if stress_min and stress_max and stress_min > stress_max:
            raise serializers.ValidationError("stress_min must be less than or equal to stress_max")

        return data


class JournalAnalyticsSerializer(serializers.Serializer):
    """Serializer for journal analytics responses"""

    wellbeing_trends = serializers.DictField(read_only=True)
    behavioral_patterns = serializers.DictField(read_only=True)
    predictive_insights = serializers.DictField(read_only=True)
    recommendations = serializers.ListField(read_only=True)
    overall_wellbeing_score = serializers.FloatField(read_only=True)
    analysis_metadata = serializers.DictField(read_only=True)

    class Meta:
        fields = [
            'wellbeing_trends', 'behavioral_patterns', 'predictive_insights',
            'recommendations', 'overall_wellbeing_score', 'analysis_metadata'
        ]
