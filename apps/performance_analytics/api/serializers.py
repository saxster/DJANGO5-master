"""
Performance Analytics Serializers.

DRF serializers for performance analytics models.
"""

from rest_framework import serializers
from apps.performance_analytics.models import (
    WorkerDailyMetrics,
    TeamDailyMetrics,
    Kudos,
    Achievement,
    WorkerAchievement,
    CoachingSession,
)

__all__ = [
    'WorkerMetricsSerializer',
    'TeamMetricsSerializer',
    'KudosSerializer',
    'AchievementSerializer',
    'WorkerAchievementSerializer',
    'CoachingSessionSerializer',
]


class WorkerMetricsSerializer(serializers.ModelSerializer):
    """Serializer for worker daily metrics."""

    worker_name = serializers.CharField(source='worker.get_full_name', read_only=True)
    percentile_rank = serializers.SerializerMethodField()

    class Meta:
        model = WorkerDailyMetrics
        fields = [
            'id',
            'worker',
            'worker_name',
            'date',
            'base_performance_index',
            'tasks_completed',
            'tasks_on_time',
            'quality_score',
            'attendance_rate',
            'compliance_score',
            'patrol_completion_rate',
            'work_order_efficiency',
            'percentile_rank',
            'created_at',
        ]
        read_only_fields = ['created_at']

    def get_percentile_rank(self, obj):
        return round(obj.percentile_rank, 2) if obj.percentile_rank else None


class TeamMetricsSerializer(serializers.ModelSerializer):
    """Serializer for team daily metrics."""

    site_name = serializers.CharField(source='site.sitename', read_only=True)

    class Meta:
        model = TeamDailyMetrics
        fields = [
            'id',
            'site',
            'site_name',
            'date',
            'team_size',
            'avg_bpi',
            'avg_quality_score',
            'avg_attendance_rate',
            'top_performer_bpi',
            'bottom_performer_bpi',
            'coaching_opportunities',
            'created_at',
        ]
        read_only_fields = ['created_at']


class KudosSerializer(serializers.ModelSerializer):
    """Serializer for kudos."""

    giver_name = serializers.CharField(source='given_by.get_full_name', read_only=True)
    recipient_name = serializers.CharField(source='recipient.get_full_name', read_only=True)

    class Meta:
        model = Kudos
        fields = [
            'id',
            'recipient',
            'recipient_name',
            'given_by',
            'giver_name',
            'kudos_type',
            'message',
            'created_at',
        ]
        read_only_fields = ['given_by', 'created_at']

    def create(self, validated_data):
        validated_data['given_by'] = self.context['request'].user
        return super().create(validated_data)


class AchievementSerializer(serializers.ModelSerializer):
    """Serializer for achievements."""

    class Meta:
        model = Achievement
        fields = [
            'id',
            'name',
            'description',
            'badge_icon',
            'achievement_type',
            'threshold_value',
            'points',
            'is_active',
        ]


class WorkerAchievementSerializer(serializers.ModelSerializer):
    """Serializer for worker achievements."""

    achievement = AchievementSerializer(read_only=True)
    worker_name = serializers.CharField(source='worker.get_full_name', read_only=True)

    class Meta:
        model = WorkerAchievement
        fields = [
            'id',
            'worker',
            'worker_name',
            'achievement',
            'earned_at',
            'is_displayed',
        ]
        read_only_fields = ['earned_at']


class CoachingSessionSerializer(serializers.ModelSerializer):
    """Serializer for coaching sessions."""

    worker_name = serializers.CharField(source='worker.get_full_name', read_only=True)
    coach_name = serializers.CharField(source='coach.get_full_name', read_only=True)

    class Meta:
        model = CoachingSession
        fields = [
            'id',
            'worker',
            'worker_name',
            'coach',
            'coach_name',
            'session_type',
            'focus_areas',
            'notes',
            'action_items',
            'scheduled_at',
            'completed_at',
            'follow_up_required',
            'created_at',
        ]
        read_only_fields = ['created_at']
