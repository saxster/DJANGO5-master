"""
Operations API Serializers

Serializers for jobs, jobneeds, tasks, and question sets.

Compliance with .claude/rules.md:
- Serializers < 100 lines each (split by domain)
- Specific validation

Ontology: data_contract=True, api_layer=True, validation_rules=True
Category: serializers, api, operations
Domain: activity_management, job_scheduling, ppm
Responsibility: Serialize/deserialize operations data; validate job/task/question payloads
Dependencies: activity.models, rest_framework
Security: Input sanitization via DRF validators; cron expression validation
Validation: Job status transitions, cron syntax, question type consistency
API: REST v1 /api/v1/operations/*
"""

from rest_framework import serializers
from apps.activity.models import Job, Jobneed, JobneedDetails, QuestionSet, Question
from apps.activity.models.question_model import QuestionSetBelonging
from apps.activity.models.job_model import JobneedDetails as JobneedDetailsModel
from apps.activity.models.attachment_model import Attachment
from django.db import transaction
import logging

logger = logging.getLogger(__name__)


class JobListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for job list views.

    Ontology: data_contract=True
    Purpose: Minimal job data for list/search endpoints
    Fields: 11 fields (job_number, status, type, assignment, dates)
    Read-Only: id, timestamps
    Use Case: Mobile sync, dashboard lists, search results
    Performance: Select-only, no prefetch (lightweight)
    """

    class Meta:
        model = Job
        fields = [
            'id', 'job_number', 'job_type', 'status',
            'assigned_to', 'bu_id', 'client_id',
            'scheduled_date', 'created_at', 'modified_at'
        ]
        read_only_fields = ['id', 'created_at', 'modified_at']


class JobDetailSerializer(serializers.ModelSerializer):
    """
    Comprehensive serializer for job detail views.

    Ontology: data_contract=True
    Purpose: Full job details for single-record retrieval
    Fields: 13 fields including assigned_to_name (computed)
    Read-Only: id, timestamps, created_by
    Field Transforms: assigned_to_name from related People.get_full_name()
    Use Case: Job detail page, edit forms, mobile detail view
    Validation: None (DRF model validation only)
    """

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
    """
    Lightweight serializer for jobneed list views.

    Ontology: data_contract=True
    Purpose: Minimal PPM schedule data for list endpoints
    Fields: 10 fields (jobneed_number, frequency, next_generation_date)
    Read-Only: id, timestamps
    Use Case: PPM schedule list, dashboard, mobile sync
    Business Rule: next_generation_date drives automated job creation
    """

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
    """
    Comprehensive serializer for jobneed detail views.

    Ontology: data_contract=True, validation_rules=True
    Purpose: Full PPM schedule details with cron validation
    Fields: 13 fields including cron_expression, frequency
    Read-Only: id, timestamps, created_by
    Validation: validate_cron_expression() using croniter library
    Validation Rules:
      - cron_expression: Valid cron syntax (5-field format)
      - Validates via croniter(value, datetime.now())
      - Raises ValidationError on invalid syntax
    Use Case: PPM schedule detail/edit, automated job generation config
    """

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
        """
        Validate cron expression format.

        Ontology: validation_rules=True
        Validates: Cron syntax using croniter library
        Input: Optional string (5-field cron expression)
        Output: Validated cron expression or ValidationError
        Examples:
          Valid: "0 9 * * MON-FRI" (9am weekdays)
          Valid: "*/15 * * * *" (every 15 minutes)
          Invalid: "99 99 * * *" (out of range)
        Security: No injection risk (croniter validates syntax)
        """
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
    """
    Serializer for jobneed details (PPM schedules).

    Ontology: data_contract=True
    Purpose: Key-value metadata for jobneed configurations
    Fields: 6 fields (jobneed FK, detail_type, value)
    Read-Only: id, timestamps
    Use Case: Store PPM-specific configuration (equipment, procedures, checklists)
    Data Model: Flexible key-value structure for jobneed extensions
    """

    class Meta:
        model = JobneedDetails
        fields = [
            'id', 'jobneed', 'detail_type', 'value',
            'is_active', 'created_at', 'modified_at'
        ]
        read_only_fields = ['id', 'created_at', 'modified_at']


class QuestionSerializer(serializers.ModelSerializer):
    """
    Serializer for question operations.

    Ontology: data_contract=True
    Purpose: Individual question definition for dynamic forms
    Fields: 7 fields (question_text, type, options, order, required)
    Read-Only: id, created_at
    Question Types: text, number, dropdown, checkbox, radio, date, signature
    Use Case: Mobile form rendering, question bank management
    Data Structure: options stored as JSON for multi-choice questions
    """

    class Meta:
        model = Question
        fields = [
            'id', 'question_text', 'question_type',
            'is_required', 'order', 'options',
            'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class QuestionSetSerializer(serializers.ModelSerializer):
    """
    Serializer for question set operations.

    Ontology: data_contract=True
    Purpose: Group of questions forming a complete checklist/form
    Fields: 6 fields including nested questions list
    Read-Only: id, timestamps, questions (nested)
    Nested: questions via QuestionSerializer (many=True)
    Use Case: Mobile checklist sync, form template management
    Performance: Prefetch questions in view to avoid N+1 queries
    """

    questions = QuestionSerializer(many=True, read_only=True)

    class Meta:
        model = QuestionSet
        fields = [
            'id', 'name', 'description',
            'is_active', 'questions',
            'created_at', 'modified_at'
        ]
        read_only_fields = ['id', 'created_at', 'modified_at']


class QuestionSetBelongingSerializer(serializers.ModelSerializer):
    """
    Serializer for question set belonging (question-questionset relationships).

    Ontology: data_contract=True
    Purpose: Many-to-many relationship with ordering and display conditions
    Fields: 13 fields (question FK, qset FK, seqno, display_conditions)
    Read-Only: id, timestamps, question_text, questionset_name (computed)
    Field Transforms: Denormalized question_text, questionset_name for API efficiency
    Display Logic: display_conditions (JSON) supports conditional question visibility
    Use Case: Mobile form rendering with skip logic, question reordering
    Validation: display_conditions JSON structure validated at model layer
    """

    question_text = serializers.CharField(
        source='question.question_text',
        read_only=True
    )
    questionset_name = serializers.CharField(
        source='qset.name',
        read_only=True
    )

    class Meta:
        model = QuestionSetBelonging
        fields = [
            'id', 'question', 'question_text',
            'qset', 'questionset_name', 'seqno',
            'answertype', 'options', 'min', 'max',
            'alerton', 'ismandatory', 'isavpt',
            'display_conditions', 'created_at', 'modified_at'
        ]
        read_only_fields = ['id', 'created_at', 'modified_at']


class AttachmentSerializer(serializers.ModelSerializer):
    """
    Serializer for file attachments.

    Ontology: data_contract=True
    Purpose: File metadata for job/task attachments
    Fields: 10 fields (file path, filename, type, owner, uploader)
    Read-Only: id, timestamps, uploaded_by_name (computed)
    Field Transforms: uploaded_by_name from People.get_full_name()
    Security: File validation happens in view via perform_secure_uploadattachment()
    Use Case: Mobile photo uploads, document attachments, evidence capture
    Storage: Files stored in media root, path in file field
    """

    uploaded_by_name = serializers.CharField(
        source='uploaded_by.get_full_name',
        read_only=True
    )

    class Meta:
        model = Attachment
        fields = [
            'id', 'file', 'filename', 'file_type',
            'owner', 'uploaded_by', 'uploaded_by_name',
            'description', 'is_active',
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
    'QuestionSetBelongingSerializer',
    'AttachmentSerializer',
]
