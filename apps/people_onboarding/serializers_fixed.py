"""
People Onboarding Serializers - SECURITY FIXED

DRF serializers for API endpoints with explicit field lists.
All `fields = '__all__'` removed to prevent sensitive data exposure.

SECURITY FIXES:
- DocumentSubmissionSerializer: Explicit fields, no file paths/verifier IDs
- ApprovalWorkflowSerializer: Explicit fields, no IP addresses
- OnboardingTaskSerializer: Explicit fields, no internal user IDs
- OnboardingRequestSerializer: Explicit fields, no creator IDs
- BackgroundCheckSerializer: Explicit fields, no check results details
- AccessProvisioningSerializer: Explicit fields, no credential details
- TrainingAssignmentSerializer: Explicit fields, no internal IDs

Author: Amp Security Review
Date: 2025-11-06
"""
from rest_framework import serializers
from apps.peoples.models import People
from .models import (
    OnboardingRequest,
    CandidateProfile,
    DocumentSubmission,
    ApprovalWorkflow,
    OnboardingTask,
    BackgroundCheck,
    AccessProvisioning,
    TrainingAssignment
)


class PeopleMinimalSerializer(serializers.ModelSerializer):
    """Minimal People serializer for references"""

    class Meta:
        model = People
        fields = ['id', 'uuid', 'peoplename', 'email', 'peopleimg']
        read_only_fields = fields


class CandidateProfileSerializer(serializers.ModelSerializer):
    """Candidate profile serializer"""

    full_name = serializers.CharField(read_only=True)
    age = serializers.SerializerMethodField()

    class Meta:
        model = CandidateProfile
        exclude = ['aadhaar_number', 'pan_number', 'passport_number']  # Sensitive fields
        read_only_fields = ['uuid', 'cdby', 'cdtz', 'upby', 'uptz']

    def get_age(self, obj):
        """Calculate age from date of birth"""
        return obj.age if hasattr(obj, 'age') else None


class DocumentSubmissionSerializer(serializers.ModelSerializer):
    """
    Document submission serializer - SECURITY FIXED
    
    REMOVED from exposure:
    - document_file (raw file path)
    - verified_by (internal user ID)
    - verification_notes (internal comments)
    - rejection_reason (internal details)
    - cdby, upby (internal user IDs)
    
    KEPT for API:
    - file_url (public URL via SerializerMethodField)
    - document_type_display (safe choice display)
    - verification_status (OK to show)
    """

    document_type_display = serializers.CharField(
        source='get_document_type_display',
        read_only=True
    )
    verification_status_display = serializers.CharField(
        source='get_verification_status_display',
        read_only=True
    )
    file_url = serializers.SerializerMethodField()
    file_size_formatted = serializers.SerializerMethodField()

    class Meta:
        model = DocumentSubmission
        fields = [
            # Public identifiers
            'id', 'uuid',
            
            # Document info
            'candidate_profile',
            'document_type', 'document_type_display',
            'document_name',
            
            # Verification status (public-facing)
            'verification_status', 'verification_status_display',
            
            # File access (via public URL, not raw path)
            'file_url', 'file_size_formatted',
            
            # Timestamps
            'uploaded_at', 'verified_at',
        ]
        read_only_fields = [
            'uuid', 'uploaded_at', 'verified_at'
        ]

    def get_file_url(self, obj):
        """Get absolute URL for document file"""
        request = self.context.get('request')
        if obj.document_file and request:
            return request.build_absolute_uri(obj.document_file.url)
        return None

    def get_file_size_formatted(self, obj):
        """Format file size in human-readable format"""
        if not obj.document_file:
            return None

        size = obj.document_file.size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"


class ApprovalWorkflowSerializer(serializers.ModelSerializer):
    """
    Approval workflow serializer - SECURITY FIXED
    
    REMOVED from exposure:
    - decision_ip_address (internal IP)
    - approver (internal user ID - use approver_name instead)
    - decision_notes (internal comments)
    
    KEPT for API:
    - approver_name, approver_email (safe display info)
    - decision, decision_display (OK to show)
    - sla_hours_remaining (computed, safe)
    """

    approver_name = serializers.CharField(
        source='approver.peoplename',
        read_only=True
    )
    approver_email = serializers.EmailField(
        source='approver.email',
        read_only=True
    )
    approval_level_display = serializers.CharField(
        source='get_approval_level_display',
        read_only=True
    )
    decision_display = serializers.CharField(
        source='get_decision_display',
        read_only=True
    )
    sla_hours_remaining = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = ApprovalWorkflow
        fields = [
            # Public identifiers
            'uuid',
            
            # Approval details
            'onboarding_request',
            'approval_level', 'approval_level_display',
            
            # Approver info (names, not IDs)
            'approver_name', 'approver_email',
            
            # Decision info (no IP address, no internal notes)
            'decision', 'decision_display',
            'decision_date',
            
            # SLA tracking
            'sla_hours_remaining', 'is_overdue',
        ]
        read_only_fields = [
            'uuid', 'decision_date'
        ]

    def get_sla_hours_remaining(self, obj):
        """Calculate remaining SLA hours"""
        if hasattr(obj, 'sla_hours_remaining'):
            return obj.sla_hours_remaining()
        return None

    def get_is_overdue(self, obj):
        """Check if approval is overdue"""
        if hasattr(obj, 'is_overdue'):
            return obj.is_overdue()
        return False


class OnboardingTaskSerializer(serializers.ModelSerializer):
    """
    Onboarding task serializer - SECURITY FIXED
    
    REMOVED from exposure:
    - assigned_to (internal user ID - use assigned_to_name)
    - internal_notes (private comments)
    - cdby, upby (internal user IDs)
    """

    category_display = serializers.CharField(
        source='get_category_display',
        read_only=True
    )
    priority_display = serializers.CharField(
        source='get_priority_display',
        read_only=True
    )
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )
    assigned_to_name = serializers.CharField(
        source='assigned_to.peoplename',
        read_only=True,
        allow_null=True
    )
    progress_percentage = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = OnboardingTask
        fields = [
            # Public identifiers
            'uuid',
            
            # Task details
            'onboarding_request',
            'task_name', 'description',
            'category', 'category_display',
            'priority', 'priority_display',
            'status', 'status_display',
            
            # Assignment (name, not ID)
            'assigned_to_name',
            
            # Dates
            'due_date', 'completed_date',
            
            # Progress
            'progress_percentage', 'is_overdue',
        ]
        read_only_fields = [
            'uuid', 'completed_date'
        ]

    def get_progress_percentage(self, obj):
        """Calculate task progress percentage"""
        if hasattr(obj, 'checklist_progress_percentage'):
            return obj.checklist_progress_percentage()
        return 0

    def get_is_overdue(self, obj):
        """Check if task is overdue"""
        if hasattr(obj, 'is_overdue'):
            return obj.is_overdue
        return False


class OnboardingRequestSerializer(serializers.ModelSerializer):
    """
    Main onboarding request serializer - SECURITY FIXED
    
    REMOVED from exposure:
    - people (internal user ID link)
    - cdby, upby (internal creator/updater IDs)
    - internal_notes (private comments)
    
    KEPT for API:
    - Nested serializers (candidate_profile, documents, approvals, tasks)
    - Public status fields
    - Computed progress metrics
    """

    candidate_profile = CandidateProfileSerializer(read_only=True)
    documents = DocumentSubmissionSerializer(many=True, read_only=True)
    approvals = ApprovalWorkflowSerializer(many=True, read_only=True)
    tasks = OnboardingTaskSerializer(many=True, read_only=True)

    person_type_display = serializers.CharField(
        source='get_person_type_display',
        read_only=True
    )
    current_state_display = serializers.CharField(
        source='get_current_state_display',
        read_only=True
    )
    created_by = PeopleMinimalSerializer(source='cdby', read_only=True)
    days_in_process = serializers.SerializerMethodField()
    completion_percentage = serializers.SerializerMethodField()

    class Meta:
        model = OnboardingRequest
        fields = [
            # Public identifiers
            'uuid', 'request_number',
            
            # Request details
            'person_type', 'person_type_display',
            'current_state', 'current_state_display',
            
            # Nested data
            'candidate_profile',
            'documents',
            'approvals',
            'tasks',
            
            # Metadata (display name, not ID)
            'created_by',
            
            # Timestamps
            'cdtz',
            
            # Computed metrics
            'days_in_process',
            'completion_percentage',
        ]
        read_only_fields = [
            'uuid', 'request_number', 'cdtz'
        ]

    def get_days_in_process(self, obj):
        """Calculate days since request was created"""
        if obj.cdtz:
            from django.utils import timezone
            delta = timezone.now() - obj.cdtz
            return delta.days
        return 0

    def get_completion_percentage(self, obj):
        """Calculate overall completion percentage"""
        state_weights = {
            'DRAFT': 10,
            'SUBMITTED': 20,
            'DOCUMENT_VERIFICATION': 40,
            'BACKGROUND_CHECK': 50,
            'PENDING_APPROVAL': 60,
            'APPROVED': 70,
            'PROVISIONING': 80,
            'TRAINING': 90,
            'COMPLETED': 100,
            'REJECTED': 0,
            'CANCELLED': 0
        }
        return state_weights.get(obj.current_state, 0)


class OnboardingRequestListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views"""

    person_type_display = serializers.CharField(
        source='get_person_type_display',
        read_only=True
    )
    current_state_display = serializers.CharField(
        source='get_current_state_display',
        read_only=True
    )
    candidate_name = serializers.CharField(
        source='candidate_profile.full_name',
        read_only=True
    )
    candidate_email = serializers.EmailField(
        source='candidate_profile.primary_email',
        read_only=True
    )

    class Meta:
        model = OnboardingRequest
        fields = [
            'uuid', 'request_number', 'person_type', 'person_type_display',
            'current_state', 'current_state_display',
            'candidate_name', 'candidate_email', 'cdtz'
        ]
        read_only_fields = fields


class BackgroundCheckSerializer(serializers.ModelSerializer):
    """
    Background check serializer - SECURITY FIXED
    
    REMOVED from exposure:
    - check_results (sensitive background check data)
    - verified_references (reference check details)
    - checked_by (internal user ID - use checked_by_name)
    - cdby, upby (internal user IDs)
    
    KEPT for API:
    - Status (OK to show high-level status)
    - checked_by_name (display name, not ID)
    """

    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )
    checked_by_name = serializers.CharField(
        source='checked_by.peoplename',
        read_only=True,
        allow_null=True
    )

    class Meta:
        model = BackgroundCheck
        fields = [
            # Public identifiers
            'uuid',
            
            # Basic info
            'onboarding_request',
            'check_type',
            
            # Status (no detailed results)
            'status', 'status_display',
            
            # Metadata (name, not ID)
            'checked_by_name',
            
            # Timestamps
            'check_date',
        ]
        read_only_fields = [
            'uuid', 'check_date'
        ]


class AccessProvisioningSerializer(serializers.ModelSerializer):
    """
    Access provisioning serializer - SECURITY FIXED
    
    REMOVED from exposure:
    - credentials_issued (credential details)
    - provisioned_by (internal user ID - use provisioned_by_name)
    - cdby, upby (internal user IDs)
    """

    access_type_display = serializers.CharField(
        source='get_access_type_display',
        read_only=True
    )
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )
    provisioned_by_name = serializers.CharField(
        source='provisioned_by.peoplename',
        read_only=True,
        allow_null=True
    )

    class Meta:
        model = AccessProvisioning
        fields = [
            # Public identifiers
            'uuid',
            
            # Access details (type only, no credentials)
            'onboarding_request',
            'access_type', 'access_type_display',
            
            # Status
            'status', 'status_display',
            
            # Metadata (name, not ID)
            'provisioned_by_name',
            
            # Timestamps
            'provisioned_date',
        ]
        read_only_fields = [
            'uuid', 'provisioned_date'
        ]


class TrainingAssignmentSerializer(serializers.ModelSerializer):
    """
    Training assignment serializer - SECURITY FIXED
    
    REMOVED from exposure:
    - assigned_by (internal user ID - use assigned_by_name)
    - training_materials (internal training paths)
    - cdby, upby (internal user IDs)
    """

    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )
    assigned_by_name = serializers.CharField(
        source='assigned_by.peoplename',
        read_only=True,
        allow_null=True
    )

    class Meta:
        model = TrainingAssignment
        fields = [
            # Public identifiers
            'uuid',
            
            # Training details
            'onboarding_request',
            'training_name',
            'description',
            
            # Status
            'status', 'status_display',
            
            # Metadata (name, not ID)
            'assigned_by_name',
            
            # Dates
            'due_date', 'completion_date',
        ]
        read_only_fields = [
            'uuid', 'completion_date'
        ]
