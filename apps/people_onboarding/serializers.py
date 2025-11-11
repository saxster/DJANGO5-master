"""
People Onboarding Serializers

DRF serializers for API endpoints.
Complies with Rule #7: < 150 lines per class

Security Note (Nov 11, 2025):
- Uses 'exclude' pattern for sensitive fields (validated as secure)
- Alternative 'fields' whitelist approach deprecated (serializers_fixed.py)
- See DEPRECATED_SERIALIZERS_NOTICE.md for details

Author: Claude Code
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
    """Document submission serializer"""

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
        exclude = ['ssn_document', 'background_check_details', 'internal_notes']  # Security: Explicit exclusion instead of '__all__'
        read_only_fields = ['uuid', 'cdby', 'cdtz', 'upby', 'uptz', 'verified_by', 'verified_at']

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
    """Approval workflow serializer"""

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
        exclude = ['internal_notes', 'reviewer_comments_internal', 'salary_details']  # Security: Explicit exclusion instead of '__all__'
        read_only_fields = ['uuid', 'decision_date', 'decision_ip_address']

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
    """Onboarding task serializer"""

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
        exclude = ['internal_notes', 'sensitive_data']  # Security: Explicit exclusion instead of '__all__'
        read_only_fields = ['uuid', 'completed_date', 'cdby', 'cdtz', 'upby', 'uptz']

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
    """Main onboarding request serializer"""

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
        exclude = ['internal_notes', 'ssn', 'salary_details']  # Security: Explicit exclusion instead of '__all__'
        read_only_fields = ['uuid', 'request_number', 'people', 'cdby', 'cdtz', 'upby', 'uptz']

    def get_days_in_process(self, obj):
        """Calculate days since request was created"""
        if obj.cdtz:
            from django.utils import timezone
            delta = timezone.now() - obj.cdtz
            return delta.days
        return 0

    def get_completion_percentage(self, obj):
        """Calculate overall completion percentage"""
        # Simple calculation based on workflow state
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
    """Background check serializer"""

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
        exclude = ['ssn', 'background_check_result', 'criminal_record', 'internal_notes']  # Security: CRITICAL - Background check data is highly sensitive
        read_only_fields = ['uuid', 'cdby', 'cdtz', 'upby', 'uptz']


class AccessProvisioningSerializer(serializers.ModelSerializer):
    """Access provisioning serializer"""

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
        exclude = ['internal_notes', 'credentials', 'api_keys']  # Security: Explicit exclusion instead of '__all__'
        read_only_fields = ['uuid', 'provisioned_date', 'cdby', 'cdtz', 'upby', 'uptz']


class TrainingAssignmentSerializer(serializers.ModelSerializer):
    """Training assignment serializer"""

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
        exclude = ['internal_notes', 'assessment_results']  # Security: Explicit exclusion instead of '__all__'
        read_only_fields = ['uuid', 'completion_date', 'cdby', 'cdtz', 'upby', 'uptz']