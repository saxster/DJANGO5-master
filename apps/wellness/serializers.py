"""
Wellness App Serializers

Comprehensive serializers for wellness education system with:
- Evidence-based content with WHO/CDC compliance tracking
- ML-powered personalization and recommendation engines
- User progress tracking with gamification elements
- Contextual content delivery based on journal patterns
- Effectiveness analytics and engagement metrics
"""

from typing import Any, Dict

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db import models
from .models import (
    WellnessContent,
    WellnessUserProgress,
    WellnessContentInteraction,
    WellnessContentCategory,
    WellnessContentLevel,
    WellnessDeliveryContext,
    EvidenceLevel,
)
# Lazy import to avoid circular dependency: from apps.journal.serializers.pii_redaction_mixin import PIIRedactionMixin
from apps.wellness.logging import get_wellness_logger

User = get_user_model()
logger = get_wellness_logger(__name__)


class WellnessContentListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for wellness content lists
    
    N+1 Query Optimization: ViewSets should use optimized queryset:
        WellnessContent.objects.annotate(interaction_count=Count('interactions'))
    Alternative (less efficient):
        WellnessContent.objects.prefetch_related('interactions')
    """

    category_display = serializers.CharField(source='get_category_display', read_only=True)
    delivery_context_display = serializers.CharField(source='get_delivery_context_display', read_only=True)
    content_level_display = serializers.CharField(source='get_content_level_display', read_only=True)
    evidence_level_display = serializers.CharField(source='get_evidence_level_display', read_only=True)
    is_high_evidence = serializers.BooleanField(read_only=True)
    needs_verification = serializers.BooleanField(read_only=True)
    interaction_count = serializers.SerializerMethodField()

    class Meta:
        model = WellnessContent
        fields = [
            'id', 'title', 'summary', 'category', 'category_display',
            'delivery_context', 'delivery_context_display',
            'content_level', 'content_level_display',
            'evidence_level', 'evidence_level_display',
            'is_high_evidence', 'needs_verification',
            'workplace_specific', 'field_worker_relevant',
            'priority_score', 'estimated_reading_time',
            'complexity_score', 'is_active',
            'interaction_count', 'created_at', 'updated_at'
        ]

    def get_interaction_count(self, obj) -> int:
        """Get total interaction count for this content"""
        # Use annotated count if available, else count prefetched interactions
        if hasattr(obj, 'interaction_count'):
            return obj.interaction_count
        return obj.interactions.count()


class WellnessContentDetailSerializer(serializers.ModelSerializer):
    """
    Comprehensive serializer for wellness content details
    
    N+1 Query Optimization: ViewSets should use optimized queryset:
        WellnessContent.objects.select_related('created_by')
                               .prefetch_related('interactions')
    """

    category_display = serializers.CharField(source='get_category_display', read_only=True)
    delivery_context_display = serializers.CharField(source='get_delivery_context_display', read_only=True)
    content_level_display = serializers.CharField(source='get_content_level_display', read_only=True)
    evidence_level_display = serializers.CharField(source='get_evidence_level_display', read_only=True)
    is_high_evidence = serializers.BooleanField(read_only=True)
    needs_verification = serializers.BooleanField(read_only=True)
    created_by_name = serializers.CharField(source='created_by.peoplename', read_only=True)
    effectiveness_metrics = serializers.SerializerMethodField()

    class Meta:
        model = WellnessContent
        fields = [
            # Core content
            'id', 'title', 'summary', 'content',

            # Classification
            'category', 'category_display', 'delivery_context', 'delivery_context_display',
            'content_level', 'content_level_display', 'evidence_level', 'evidence_level_display',

            # Targeting
            'tags', 'trigger_patterns', 'workplace_specific', 'field_worker_relevant',

            # Educational structure
            'action_tips', 'key_takeaways', 'related_topics',

            # Evidence and credibility
            'source_name', 'source_url', 'evidence_summary', 'citations',
            'last_verified_date', 'is_high_evidence', 'needs_verification',

            # Content management
            'is_active', 'priority_score', 'seasonal_relevance', 'frequency_limit_days',

            # Publishing metadata
            'estimated_reading_time', 'complexity_score', 'content_version',

            # Relationships and audit
            'created_by', 'created_by_name', 'created_at', 'updated_at',

            # Analytics
            'effectiveness_metrics'
        ]
        read_only_fields = [
            'id', 'created_by', 'created_by_name', 'created_at', 'updated_at',
            'is_high_evidence', 'needs_verification', 'effectiveness_metrics'
        ]

    def get_effectiveness_metrics(self, obj) -> Dict[str, Any]:
        """Calculate content effectiveness metrics"""
        interactions = obj.interactions.all()
        if not interactions:
            return {
                'total_interactions': 0,
                'effectiveness_score': 0.0,
                'avg_rating': None,
                'completion_rate': 0.0
            }

        total = interactions.count()
        completed = interactions.filter(interaction_type='completed').count()
        positive = interactions.filter(
            interaction_type__in=['completed', 'bookmarked', 'acted_upon', 'requested_more']
        ).count()
        rated = interactions.exclude(user_rating__isnull=True)

        return {
            'total_interactions': total,
            'effectiveness_score': (positive / total * 100) if total > 0 else 0,
            'avg_rating': rated.aggregate(avg=models.Avg('user_rating'))['avg'] if rated else None,
            'completion_rate': (completed / total * 100) if total > 0 else 0,
            'engagement_distribution': {
                'viewed': interactions.filter(interaction_type='viewed').count(),
                'completed': completed,
                'bookmarked': interactions.filter(interaction_type='bookmarked').count(),
                'acted_upon': interactions.filter(interaction_type='acted_upon').count(),
                'dismissed': interactions.filter(interaction_type='dismissed').count(),
            }
        }

    def validate_priority_score(self, value):
        """Validate priority score range"""
        if value < 1 or value > 100:
            raise serializers.ValidationError("Priority score must be between 1 and 100")
        return value

    def validate_complexity_score(self, value):
        """Validate complexity score range"""
        if value < 1 or value > 5:
            raise serializers.ValidationError("Complexity score must be between 1 and 5")
        return value

    def validate_estimated_reading_time(self, value):
        """Validate reading time is positive"""
        if value <= 0:
            raise serializers.ValidationError("Estimated reading time must be positive")
        return value

    def validate_seasonal_relevance(self, value):
        """Validate seasonal relevance months"""
        if value:
            for month in value:
                if not isinstance(month, int) or month < 1 or month > 12:
                    raise serializers.ValidationError("Seasonal relevance must contain months 1-12")
        return value


class WellnessUserProgressSerializer(PIIRedactionMixin, serializers.ModelSerializer):
    """
    Serializer for user wellness progress and gamification
    
    N+1 Query Optimization: ViewSets should use optimized queryset:
        WellnessUserProgress.objects.select_related('user')
    """

    # PII redaction configuration
    PII_ADMIN_FIELDS = ['user_name']  # Partially redact for admins

    user_name = serializers.CharField(source='user.peoplename', read_only=True)
    is_active_user = serializers.BooleanField(read_only=True)
    completion_rate = serializers.FloatField(read_only=True)
    achievement_count = serializers.SerializerMethodField()
    category_progress_summary = serializers.SerializerMethodField()
    next_milestone = serializers.SerializerMethodField()

    class Meta:
        model = WellnessUserProgress
        fields = [
            # User info
            'user', 'user_name', 'is_active_user',

            # Streak tracking
            'current_streak', 'longest_streak', 'last_activity_date',

            # Learning metrics
            'total_content_viewed', 'total_content_completed',
            'total_time_spent_minutes', 'total_score', 'completion_rate',

            # Category progress
            'mental_health_progress', 'physical_wellness_progress',
            'workplace_health_progress', 'substance_awareness_progress',
            'preventive_care_progress', 'category_progress_summary',

            # Preferences
            'preferred_content_level', 'preferred_delivery_time',
            'enabled_categories', 'daily_tip_enabled', 'contextual_delivery_enabled',

            # Gamification
            'achievements_earned', 'achievement_count', 'milestone_alerts_enabled',
            'next_milestone',

            # Audit
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'user_name', 'is_active_user', 'completion_rate',
            'achievement_count', 'category_progress_summary', 'next_milestone',
            'created_at', 'updated_at'
        ]

    def get_achievement_count(self, obj):
        """Get count of achievements earned"""
        return len(obj.achievements_earned)

    def get_category_progress_summary(self, obj):
        """Get summary of progress across categories"""
        categories = {
            'Mental Health': obj.mental_health_progress,
            'Physical Wellness': obj.physical_wellness_progress,
            'Workplace Health': obj.workplace_health_progress,
            'Substance Awareness': obj.substance_awareness_progress,
            'Preventive Care': obj.preventive_care_progress,
        }

        total_progress = sum(categories.values())
        top_category = max(categories.items(), key=lambda x: x[1])

        return {
            'total_progress': total_progress,
            'top_category': top_category[0],
            'top_category_score': top_category[1],
            'categories': categories
        }

    def get_next_milestone(self, obj):
        """Get next achievement milestone for user"""
        streak_milestones = [
            (7, 'week_streak', 'Week Streak'),
            (30, 'month_streak', 'Month Streak'),
            (100, 'hundred_day_streak', '100-Day Streak')
        ]

        content_milestones = [
            (10, 'content_explorer', 'Content Explorer'),
            (50, 'wellness_scholar', 'Wellness Scholar'),
            (100, 'wellness_master', 'Wellness Master')
        ]

        # Check streak milestones
        for threshold, achievement_id, name in streak_milestones:
            if achievement_id not in obj.achievements_earned and obj.current_streak < threshold:
                return {
                    'type': 'streak',
                    'name': name,
                    'description': f'Maintain wellness engagement for {threshold} consecutive days',
                    'current_progress': obj.current_streak,
                    'target': threshold,
                    'progress_percentage': (obj.current_streak / threshold * 100)
                }

        # Check content milestones
        for threshold, achievement_id, name in content_milestones:
            if achievement_id not in obj.achievements_earned and obj.total_content_viewed < threshold:
                return {
                    'type': 'content',
                    'name': name,
                    'description': f'View {threshold} wellness content items',
                    'current_progress': obj.total_content_viewed,
                    'target': threshold,
                    'progress_percentage': (obj.total_content_viewed / threshold * 100)
                }

        return None

    def validate_enabled_categories(self, value):
        """Validate enabled categories"""
        valid_categories = [choice[0] for choice in WellnessContentCategory.choices]
        for category in value:
            if category not in valid_categories:
                raise serializers.ValidationError(f"Invalid category: {category}")
        return value


class WellnessContentInteractionSerializer(PIIRedactionMixin, serializers.ModelSerializer):
    """
    Serializer for wellness content interactions
    
    N+1 Query Optimization: ViewSets should use optimized queryset:
        WellnessContentInteraction.objects.select_related('user', 'content', 
                                                          'trigger_journal_entry')
    """

    # PII redaction configuration
    PII_FIELDS = ['user_feedback', 'journal_entry_title']  # Always redact for non-owners
    PII_ADMIN_FIELDS = ['user_name']  # Partially redact for admins

    user_name = serializers.CharField(source='user.peoplename', read_only=True)
    content_title = serializers.CharField(source='content.title', read_only=True)
    content_category = serializers.CharField(source='content.category', read_only=True)
    interaction_type_display = serializers.CharField(source='get_interaction_type_display', read_only=True)
    delivery_context_display = serializers.CharField(source='get_delivery_context_display', read_only=True)
    is_positive_interaction = serializers.BooleanField(read_only=True)
    engagement_score = serializers.IntegerField(read_only=True)
    journal_entry_title = serializers.CharField(source='trigger_journal_entry.title', read_only=True)

    class Meta:
        model = WellnessContentInteraction
        fields = [
            # Core interaction data
            'id', 'user', 'user_name', 'content', 'content_title',
            'content_category', 'interaction_type', 'interaction_type_display',
            'delivery_context', 'delivery_context_display',

            # Engagement metrics
            'time_spent_seconds', 'completion_percentage', 'user_rating',
            'user_feedback', 'action_taken', 'is_positive_interaction',
            'engagement_score',

            # Delivery context
            'trigger_journal_entry', 'journal_entry_title',
            'user_mood_at_delivery', 'user_stress_at_delivery',

            # Metadata
            'interaction_date', 'metadata'
        ]
        read_only_fields = [
            'id', 'user_name', 'content_title', 'content_category',
            'interaction_type_display', 'delivery_context_display',
            'is_positive_interaction', 'engagement_score', 'journal_entry_title',
            'interaction_date'
        ]

    def validate_completion_percentage(self, value):
        """Validate completion percentage range"""
        if value is not None and (value < 0 or value > 100):
            raise serializers.ValidationError("Completion percentage must be between 0 and 100")
        return value

    def validate_user_rating(self, value):
        """Validate user rating range"""
        if value is not None and (value < 1 or value > 5):
            raise serializers.ValidationError("User rating must be between 1 and 5")
        return value


class WellnessContentInteractionCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating wellness content interactions"""

    class Meta:
        model = WellnessContentInteraction
        fields = [
            'content', 'interaction_type', 'delivery_context',
            'time_spent_seconds', 'completion_percentage', 'user_rating',
            'user_feedback', 'action_taken', 'trigger_journal_entry',
            'user_mood_at_delivery', 'user_stress_at_delivery', 'metadata'
        ]

    def create(self, validated_data):
        """Create interaction with proper user assignment"""
        user = self.context['request'].user
        validated_data['user'] = user
        return super().create(validated_data)


class DailyWellnessTipRequestSerializer(serializers.Serializer):
    """Serializer for daily wellness tip requests"""

    preferred_category = serializers.ChoiceField(
        choices=WellnessContentCategory.choices,
        required=False,
        help_text="Preferred wellness category for the tip"
    )
    content_level = serializers.ChoiceField(
        choices=WellnessContentLevel.choices,
        required=False,
        help_text="Preferred content complexity level"
    )
    exclude_recent = serializers.BooleanField(
        default=True,
        help_text="Exclude recently viewed content"
    )


class ContextualWellnessContentRequestSerializer(serializers.Serializer):
    """Serializer for contextual wellness content requests"""

    journal_entry = serializers.DictField(
        help_text="Journal entry data that triggered the request"
    )
    user_context = serializers.DictField(
        required=False,
        default=dict,
        help_text="Additional user context for content selection"
    )
    max_content_items = serializers.IntegerField(
        default=3,
        min_value=1,
        max_value=10,
        help_text="Maximum number of content items to return"
    )

    def validate_journal_entry(self, value):
        """Validate journal entry format"""
        required_fields = ['entry_type', 'timestamp']
        for field in required_fields:
            if field not in value:
                raise serializers.ValidationError(f"Missing required field: {field}")

        # Validate mood/stress if present
        if 'mood_rating' in value:
            mood = value['mood_rating']
            if not (1 <= mood <= 10):
                raise serializers.ValidationError("mood_rating must be between 1 and 10")

        if 'stress_level' in value:
            stress = value['stress_level']
            if not (1 <= stress <= 5):
                raise serializers.ValidationError("stress_level must be between 1 and 5")

        return value


class PersonalizedContentRequestSerializer(serializers.Serializer):
    """Serializer for personalized wellness content requests"""

    limit = serializers.IntegerField(
        default=5,
        min_value=1,
        max_value=20,
        help_text="Number of personalized content items to return"
    )
    categories = serializers.ListField(
        child=serializers.ChoiceField(choices=WellnessContentCategory.choices),
        required=False,
        help_text="Filter by specific wellness categories"
    )
    exclude_viewed = serializers.BooleanField(
        default=True,
        help_text="Exclude recently viewed content"
    )
    diversity_enabled = serializers.BooleanField(
        default=True,
        help_text="Enable diversity constraints to avoid content clustering"
    )


class WellnessRecommendationSerializer(serializers.Serializer):
    """Serializer for wellness content recommendations with ML scores"""

    content = WellnessContentDetailSerializer(read_only=True)
    personalization_score = serializers.FloatField(
        read_only=True,
        help_text="ML-generated personalization score (0-1)"
    )
    recommendation_reason = serializers.CharField(
        read_only=True,
        help_text="Explanation for why this content was recommended"
    )
    predicted_effectiveness = serializers.FloatField(
        read_only=True,
        help_text="Predicted effectiveness for this user (0-1)"
    )
    estimated_value = serializers.FloatField(
        read_only=True,
        help_text="Estimated value/impact score (0-1)"
    )
    delivery_context = serializers.CharField(
        read_only=True,
        help_text="Recommended delivery context"
    )


class WellnessAnalyticsSerializer(serializers.Serializer):
    """Serializer for wellness engagement analytics"""

    engagement_summary = serializers.DictField(read_only=True)
    content_effectiveness = serializers.DictField(read_only=True)
    user_preferences = serializers.DictField(read_only=True)
    trend_analysis = serializers.DictField(read_only=True)
    recommendations = serializers.ListField(read_only=True)
    analysis_metadata = serializers.DictField(read_only=True)


class WellnessCategoryStatsSerializer(serializers.Serializer):
    """Serializer for wellness category statistics"""

    category = serializers.CharField(read_only=True)
    category_display = serializers.CharField(read_only=True)
    content_count = serializers.IntegerField(read_only=True)
    user_progress = serializers.IntegerField(read_only=True)
    avg_effectiveness = serializers.FloatField(read_only=True)
    popular_content = serializers.ListField(read_only=True)
    recommended_next = serializers.DictField(read_only=True)
