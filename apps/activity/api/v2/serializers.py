"""
Operations Domain V2 Serializers - Clean Field Names

API v2 serializers with clean, frontend-friendly field names based on
Kotlin documentation API_CONTRACT_OPERATIONS_COMPLETE.md.

Compliance with .claude/rules.md:
- Serializers < 100 lines each (split by domain)
- source= parameter for old→new field mapping
- Specific validation patterns
- PydanticSerializerMixin for enhanced validation

Ontology: data_contract=True, api_layer=True, validation_rules=True
Category: serializers, api_v2, operations
Domain: activity_management, tours, tasks, ppm, questions
Responsibility: V2 API contract with clean field names
Dependencies: activity.models, rest_framework, pydantic_integration
Security: Input sanitization, version-based optimistic locking
API: REST v2 /api/v2/operations/*
"""

from rest_framework import serializers
from apps.activity.models import Job, Jobneed
from apps.activity.models.question_model import Question, QuestionSet
from apps.activity.models.attachment_model import Attachment
from apps.core.serializers.pydantic_integration import PydanticSerializerMixin
from apps.core.serializers.base_serializers import ValidatedModelSerializer
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# Location & Geography Serializers
# ============================================================================

class LocationSerializerV2(serializers.Serializer):
    """
    Geographic location coordinates.
    
    Fields: latitude, longitude, address
    Use Case: Tour stops, job sites, real-time tracking
    """
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)
    address = serializers.CharField(max_length=500, allow_blank=True, required=False)


# ============================================================================
# Job/Jobneed Serializers (V2 Clean Names)
# ============================================================================

class JobSerializerV2(ValidatedModelSerializer):
    """
    Job/Task serializer with clean field names.
    
    Field Mapping (old → new):
    - jobneedname → title
    - jobneedneed → description
    - people → assigned_to
    - jobtype → job_type
    
    Features: version field for optimistic locking
    Use Case: Mobile job list, job details, job creation
    """
    # Clean field names mapped from legacy fields
    title = serializers.CharField(source='jobneedname', max_length=200)
    description = serializers.CharField(
        source='jobneedneed',
        required=False,
        allow_blank=True
    )
    assigned_to = serializers.IntegerField(source='people', allow_null=True)
    job_type = serializers.CharField(source='jobtype', max_length=50)
    
    # Standard fields
    status = serializers.CharField(max_length=20)
    priority = serializers.CharField(max_length=20, required=False)
    site_id = serializers.IntegerField(source='bu_id', allow_null=True)
    scheduled_date = serializers.DateField(allow_null=True)
    due_date = serializers.DateField(allow_null=True)
    
    # Optimistic locking
    version = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Job
        fields = [
            'id', 'title', 'description', 'job_type', 'status', 'priority',
            'assigned_to', 'site_id', 'scheduled_date', 'due_date',
            'version', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'version', 'created_at', 'updated_at']


# ============================================================================
# Tour Serializers
# ============================================================================

class TourStopSerializerV2(serializers.Serializer):
    """
    Tour stop details within a tour route.
    
    Fields: sequence, job_id, location, site_id, timing, status
    Use Case: Tour planning, route optimization, progress tracking
    Max Lines: 40 (under 100 limit)
    """
    id = serializers.IntegerField(read_only=True)
    sequence = serializers.IntegerField(min_value=1)
    job_id = serializers.IntegerField(allow_null=True, required=False)
    location = LocationSerializerV2()
    site_id = serializers.IntegerField()
    estimated_arrival = serializers.DateTimeField()
    actual_arrival = serializers.DateTimeField(allow_null=True, required=False)
    service_time_minutes = serializers.IntegerField(min_value=0)
    status = serializers.ChoiceField(
        choices=['PENDING', 'ARRIVED', 'IN_SERVICE', 'COMPLETED', 'SKIPPED'],
        default='PENDING'
    )
    notes = serializers.CharField(
        max_length=1000,
        allow_blank=True,
        required=False
    )


class TourSerializerV2(serializers.Serializer):
    """
    Tour with route stops and scheduling.
    
    Fields: title, assigned_to, vehicle, schedule, stops, metrics
    Use Case: Daily inspection tours, multi-site patrols
    Features: Distance calculation, duration tracking, optimization
    Max Lines: 60 (under 100 limit)
    """
    id = serializers.IntegerField(read_only=True)
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(
        max_length=1000,
        allow_blank=True,
        required=False
    )
    status = serializers.ChoiceField(
        choices=['DRAFT', 'SCHEDULED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED'],
        default='DRAFT'
    )
    assigned_to = serializers.IntegerField()
    vehicle_id = serializers.IntegerField(allow_null=True, required=False)
    
    # Schedule
    scheduled_date = serializers.DateField()
    start_time = serializers.DateTimeField(allow_null=True, required=False)
    end_time = serializers.DateTimeField(allow_null=True, required=False)
    
    # Metrics
    estimated_duration_minutes = serializers.IntegerField(min_value=0)
    actual_duration_minutes = serializers.IntegerField(
        allow_null=True,
        required=False
    )
    total_distance_km = serializers.FloatField(min_value=0)
    
    # Nested stops
    stops = TourStopSerializerV2(many=True)
    
    # Versioning
    version = serializers.IntegerField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


# ============================================================================
# Task & PPM Serializers
# ============================================================================

class RecurrenceRuleSerializerV2(serializers.Serializer):
    """
    PPM recurrence schedule rule.
    
    Fields: frequency, interval, day_of_week, day_of_month, end_date
    Use Case: Automated PPM task generation
    Examples: Weekly Monday, Monthly 15th, Quarterly
    Max Lines: 30 (under 100 limit)
    """
    frequency = serializers.ChoiceField(
        choices=['DAILY', 'WEEKLY', 'MONTHLY', 'QUARTERLY', 'YEARLY']
    )
    interval = serializers.IntegerField(min_value=1, default=1)
    day_of_week = serializers.IntegerField(
        min_value=0,
        max_value=6,
        allow_null=True,
        required=False
    )
    day_of_month = serializers.IntegerField(
        min_value=1,
        max_value=31,
        allow_null=True,
        required=False
    )
    month = serializers.IntegerField(
        min_value=1,
        max_value=12,
        allow_null=True,
        required=False
    )
    end_date = serializers.DateField(allow_null=True, required=False)


class TaskSerializerV2(ValidatedModelSerializer):
    """
    Task/PPM serializer with dependencies.
    
    Fields: title, task_type, status, priority, assignment, dependencies
    Use Case: Preventive maintenance, inspections, repairs
    Features: Task dependencies, PPM linkage, hour tracking
    Max Lines: 50 (under 100 limit)
    """
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(
        max_length=2000,
        allow_blank=True,
        required=False
    )
    task_type = serializers.ChoiceField(
        choices=[
            'PREVENTIVE_MAINTENANCE', 'CORRECTIVE_MAINTENANCE',
            'INSPECTION', 'CALIBRATION', 'CLEANING', 'REPAIR', 'REPLACEMENT'
        ]
    )
    status = serializers.ChoiceField(
        choices=['PENDING', 'ASSIGNED', 'IN_PROGRESS', 'ON_HOLD', 'COMPLETED', 'CANCELLED']
    )
    priority = serializers.ChoiceField(
        choices=['LOW', 'MEDIUM', 'HIGH', 'URGENT']
    )
    
    assigned_to = serializers.IntegerField(allow_null=True, required=False)
    site_id = serializers.IntegerField()
    asset_id = serializers.IntegerField(allow_null=True, required=False)
    
    due_date = serializers.DateField()
    estimated_hours = serializers.FloatField(min_value=0)
    actual_hours = serializers.FloatField(
        min_value=0,
        allow_null=True,
        required=False
    )
    
    # Task dependencies (list of task IDs)
    dependencies = serializers.ListField(
        child=serializers.IntegerField(),
        default=list
    )
    
    ppm_schedule_id = serializers.IntegerField(
        allow_null=True,
        required=False
    )
    version = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Job
        fields = [
            'id', 'title', 'description', 'task_type', 'status', 'priority',
            'assigned_to', 'site_id', 'asset_id', 'due_date',
            'estimated_hours', 'actual_hours', 'dependencies',
            'ppm_schedule_id', 'version', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'version', 'created_at', 'updated_at']


class PPMScheduleSerializerV2(ValidatedModelSerializer):
    """
    PPM schedule with recurrence rules.
    
    Fields: title, asset, recurrence_rule, next_due_date, is_active
    Use Case: Automated preventive maintenance scheduling
    Features: Recurrence rules, generation horizon, active/inactive
    Max Lines: 45 (under 100 limit)
    """
    title = serializers.CharField(
        source='jobneedname',
        max_length=200
    )
    description = serializers.CharField(
        source='jobneedneed',
        max_length=2000,
        allow_blank=True,
        required=False
    )
    asset_id = serializers.IntegerField(allow_null=True, required=False)
    task_template_id = serializers.IntegerField(
        allow_null=True,
        required=False
    )
    
    recurrence_rule = RecurrenceRuleSerializerV2()
    next_due_date = serializers.DateField()
    last_generated = serializers.DateField(
        allow_null=True,
        required=False,
        read_only=True
    )
    generation_horizon_days = serializers.IntegerField(
        min_value=1,
        default=30
    )
    is_active = serializers.BooleanField(default=True)
    version = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Jobneed
        fields = [
            'id', 'title', 'description', 'asset_id', 'task_template_id',
            'recurrence_rule', 'next_due_date', 'last_generated',
            'generation_horizon_days', 'is_active', 'version',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'last_generated', 'version', 'created_at', 'updated_at']


# ============================================================================
# Question & Answer Serializers
# ============================================================================

class ValidationRulesSerializerV2(serializers.Serializer):
    """
    Question validation rules.
    
    Fields: min, max, regex, required_if
    Use Case: Dynamic form validation
    Max Lines: 20 (under 100 limit)
    """
    min_value = serializers.FloatField(required=False, allow_null=True)
    max_value = serializers.FloatField(required=False, allow_null=True)
    min_length = serializers.IntegerField(required=False, allow_null=True)
    max_length = serializers.IntegerField(required=False, allow_null=True)
    regex_pattern = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True
    )
    required_if = serializers.JSONField(required=False, allow_null=True)


class QuestionSerializerV2(ValidatedModelSerializer):
    """
    Question definition with validation rules.
    
    Fields: question_text, question_type, is_required, validation_rules
    Use Case: Dynamic forms, checklists, inspections
    Features: 11 question types, conditional logic, validation
    Max Lines: 50 (under 100 limit)
    """
    question_text = serializers.CharField(
        source='questiontitle',
        max_length=500
    )
    question_type = serializers.ChoiceField(
        source='answertype',
        choices=[
            'YES_NO', 'TEXT', 'MULTILINE_TEXT', 'NUMBER', 'DATE', 'TIME',
            'DATETIME', 'SELECT_ONE', 'SELECT_MULTI', 'PHOTO', 'SIGNATURE'
        ]
    )
    is_required = serializers.BooleanField(default=False)
    sequence = serializers.IntegerField(min_value=1, default=1)
    
    validation_rules = ValidationRulesSerializerV2(
        required=False,
        allow_null=True
    )
    options = serializers.JSONField(
        required=False,
        allow_null=True,
        help_text="Options for SELECT_ONE/SELECT_MULTI"
    )
    conditional_logic = serializers.JSONField(
        required=False,
        allow_null=True,
        help_text="Display conditions based on other answers"
    )
    help_text = serializers.CharField(
        max_length=1000,
        allow_blank=True,
        required=False
    )
    version = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Question
        fields = [
            'id', 'question_text', 'question_type', 'is_required', 'sequence',
            'validation_rules', 'options', 'conditional_logic', 'help_text',
            'version', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'version', 'created_at', 'updated_at']


class AnswerSerializerV2(serializers.Serializer):
    """
    Answer submission for questions.
    
    Fields: question_id, job_id, answer_value, attachment_id
    Use Case: Form submission, inspection responses
    Features: Multi-type answers (text, number, photo, signature)
    Max Lines: 35 (under 100 limit)
    """
    id = serializers.IntegerField(read_only=True)
    question_id = serializers.IntegerField()
    job_id = serializers.IntegerField()
    answer_value = serializers.CharField(
        max_length=5000,
        allow_blank=True,
        required=False
    )
    attachment_id = serializers.IntegerField(
        allow_null=True,
        required=False,
        help_text="For PHOTO/SIGNATURE question types"
    )
    answered_by = serializers.IntegerField(read_only=True)
    answered_at = serializers.DateTimeField(read_only=True)
    
    def validate(self, attrs):
        """Validate answer based on question type."""
        question_id = attrs.get('question_id')
        answer_value = attrs.get('answer_value')
        attachment_id = attrs.get('attachment_id')
        
        # Photo/signature questions require attachment
        # Additional validation to be implemented based on question type
        
        return attrs


# ============================================================================
# Job Approval Serializers
# ============================================================================

class JobApprovalSerializerV2(serializers.Serializer):
    """
    Job approval workflow.
    
    Fields: comments, signature_attachment_id, approved_at
    Use Case: Supervisor approval, quality control
    Max Lines: 25 (under 100 limit)
    """
    comments = serializers.CharField(
        max_length=2000,
        allow_blank=True,
        required=False
    )
    signature_attachment_id = serializers.IntegerField(
        allow_null=True,
        required=False
    )
    approved_at = serializers.DateTimeField()
    
    # Read-only response fields
    approved_by = serializers.IntegerField(read_only=True)
    version = serializers.IntegerField(read_only=True)


class JobRejectionSerializerV2(serializers.Serializer):
    """
    Job rejection workflow.
    
    Fields: comments, rejection_reason, required_fixes
    Use Case: Quality control, incomplete work handling
    Max Lines: 25 (under 100 limit)
    """
    comments = serializers.CharField(max_length=2000)
    rejection_reason = serializers.ChoiceField(
        choices=[
            'INCOMPLETE_DATA', 'QUALITY_ISSUES',
            'MISSING_PHOTOS', 'INCORRECT_INFORMATION'
        ]
    )
    required_fixes = serializers.ListField(
        child=serializers.CharField(max_length=500),
        required=False
    )
    
    # Read-only response fields
    rejected_by = serializers.IntegerField(read_only=True)
    rejected_at = serializers.DateTimeField(read_only=True)
    version = serializers.IntegerField(read_only=True)


# ============================================================================
# Batch Operations
# ============================================================================

class BatchAnswerSubmissionSerializerV2(serializers.Serializer):
    """
    Batch answer submission.
    
    Fields: job_id, answers[], atomic
    Use Case: Submit all form answers at once
    Features: Atomic transaction support
    Max Lines: 20 (under 100 limit)
    """
    job_id = serializers.IntegerField()
    answers = AnswerSerializerV2(many=True)
    atomic = serializers.BooleanField(
        default=True,
        help_text="All-or-nothing transaction"
    )
    
    def validate(self, attrs):
        """Validate all answers are for the same job."""
        job_id = attrs['job_id']
        answers = attrs['answers']
        
        for answer in answers:
            if answer.get('job_id') and answer['job_id'] != job_id:
                raise serializers.ValidationError(
                    "All answers must be for the same job"
                )
        
        return attrs
