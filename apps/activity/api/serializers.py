"""
Operations API Serializers

Serializers for jobs, jobneeds, tasks, and question sets.

Compliance with .claude/rules.md:
- Serializers < 100 lines each (split by domain)
- Specific validation
"""

from rest_framework import serializers
from apps.activity.models import Job, Jobneed, JobneedDetails, QuestionSet, Question
from apps.activity.models.job_model import JobneedDetails as JobneedDetailsModel
from django.db import transaction
import logging

logger = logging.getLogger(__name__)


class JobListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for job list views."""

    class Meta:
        model = Job
        fields = [
            'id', 'job_number', 'job_type', 'status',
            'assigned_to', 'bu_id', 'client_id',
            'scheduled_date', 'created_at', 'modified_at'
        ]
        read_only_fields = ['id', 'created_at', 'modified_at']


class JobDetailSerializer(serializers.ModelSerializer):
    """Comprehensive serializer for job detail views."""

    assigned_to_name = serializers.CharField(
        source='assigned_to.get_full_name',
        read_only=True
    )

    class Meta:
        model = Job
        fields = [
            'id', 'job_number', 'job_type', 'status',
            'assigned_to', 'assigned_to_name',
            'bu_id', 'client_id', 'location',
            'scheduled_date', 'completed_date',
            'description', 'notes',
            'created_at', 'modified_at', 'created_by'
        ]
        read_only_fields = ['id', 'created_at', 'modified_at', 'created_by']


class JobneedListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for jobneed list views."""

    class Meta:
        model = Jobneed
        fields = [
            'id', 'jobneed_number', 'jobneed_type', 'status',
            'bu_id', 'client_id', 'frequency',
            'next_generation_date', 'is_active',
            'created_at', 'modified_at'
        ]
        read_only_fields = ['id', 'created_at', 'modified_at']


class JobneedDetailSerializer(serializers.ModelSerializer):
    """Comprehensive serializer for jobneed detail views."""

    class Meta:
        model = Jobneed
        fields = [
            'id', 'jobneed_number', 'jobneed_type', 'status',
            'bu_id', 'client_id', 'location',
            'frequency', 'cron_expression',
            'next_generation_date', 'last_generated_date',
            'is_active', 'description',
            'created_at', 'modified_at', 'created_by'
        ]
        read_only_fields = ['id', 'created_at', 'modified_at', 'created_by']

    def validate_cron_expression(self, value):
        """Validate cron expression format."""
        if value:
            from croniter import croniter
            from datetime import datetime

            try:
                croniter(value, datetime.now())
            except (ValueError, KeyError) as e:
                raise serializers.ValidationError(
                    f'Invalid cron expression: {str(e)}'
                )
        return value


class JobneedDetailsSerializer(serializers.ModelSerializer):
    """Serializer for jobneed details (PPM schedules)."""

    class Meta:
        model = JobneedDetails
        fields = [
            'id', 'jobneed', 'detail_type', 'value',
            'is_active', 'created_at', 'modified_at'
        ]
        read_only_fields = ['id', 'created_at', 'modified_at']


class QuestionSerializer(serializers.ModelSerializer):
    """Serializer for question operations."""

    class Meta:
        model = Question
        fields = [
            'id', 'question_text', 'question_type',
            'is_required', 'order', 'options',
            'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class QuestionSetSerializer(serializers.ModelSerializer):
    """Serializer for question set operations."""

    questions = QuestionSerializer(many=True, read_only=True)

    class Meta:
        model = QuestionSet
        fields = [
            'id', 'name', 'description',
            'is_active', 'questions',
            'created_at', 'modified_at'
        ]
        read_only_fields = ['id', 'created_at', 'modified_at']


__all__ = [
    'JobListSerializer',
    'JobDetailSerializer',
    'JobneedListSerializer',
    'JobneedDetailSerializer',
    'JobneedDetailsSerializer',
    'QuestionSerializer',
    'QuestionSetSerializer',
]
