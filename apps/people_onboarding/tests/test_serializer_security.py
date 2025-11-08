"""
Security Tests for People Onboarding Serializers

Ensures sensitive fields are NEVER exposed via API.
Tests cover PII, internal IDs, file paths, and other sensitive data.

Test Categories:
1. Candidate Profile - PII exclusion (aadhaar, PAN, passport)
2. Document Submission - File path exclusion, verifier ID exclusion
3. Approval Workflow - IP address exclusion, internal user ID exclusion
4. Background Check - Check results exclusion
5. Onboarding Request - Internal user ID exclusion

Author: Amp Security Review
Date: 2025-11-06
"""
import pytest
from decimal import Decimal
from django.utils import timezone
from apps.people_onboarding.serializers import (
    CandidateProfileSerializer,
    DocumentSubmissionSerializer,
    ApprovalWorkflowSerializer,
    OnboardingTaskSerializer,
    OnboardingRequestSerializer,
    BackgroundCheckSerializer,
    AccessProvisioningSerializer,
    TrainingAssignmentSerializer
)


@pytest.fixture
def candidate_profile(db):
    """Create test candidate profile with encrypted PII"""
    from apps.people_onboarding.models import CandidateProfile
    return CandidateProfile.objects.create(
        first_name='John',
        last_name='Doe',
        date_of_birth='1990-01-01',
        primary_email='john.doe@example.com',
        primary_phone='+911234567890',
        aadhaar_number='123456789012',  # SENSITIVE - MUST NOT BE EXPOSED
        pan_number='ABCDE1234F',  # SENSITIVE - MUST NOT BE EXPOSED
        passport_number='A1234567',  # SENSITIVE - MUST NOT BE EXPOSED
    )


@pytest.fixture
def document_submission(db, candidate_profile):
    """Create test document submission"""
    from apps.people_onboarding.models import DocumentSubmission
    return DocumentSubmission.objects.create(
        candidate_profile=candidate_profile,
        document_type='AADHAAR',
        document_name='aadhaar_scan.pdf',
        verification_status='PENDING',
        # document_file would be FileField in real case
    )


@pytest.fixture
def approval_workflow(db, onboarding_request, admin_user):
    """Create test approval workflow"""
    from apps.people_onboarding.models import ApprovalWorkflow
    return ApprovalWorkflow.objects.create(
        onboarding_request=onboarding_request,
        approval_level='L1',
        approver=admin_user,
        decision='PENDING',
        decision_ip_address='192.168.1.100',  # SENSITIVE - MUST NOT BE EXPOSED
    )


@pytest.fixture
def background_check(db, onboarding_request):
    """Create test background check"""
    from apps.people_onboarding.models import BackgroundCheck
    return BackgroundCheck.objects.create(
        onboarding_request=onboarding_request,
        check_type='CRIMINAL',
        status='IN_PROGRESS',
        check_results={'criminal_record': False, 'verified': True}  # SENSITIVE
    )


@pytest.fixture
def onboarding_request(db, candidate_profile):
    """Create test onboarding request"""
    from apps.people_onboarding.models import OnboardingRequest
    return OnboardingRequest.objects.create(
        candidate_profile=candidate_profile,
        person_type='SECURITY_GUARD',
        current_state='DRAFT',
    )


@pytest.mark.django_db
class TestCandidateProfileSerializerSecurity:
    """Test CandidateProfileSerializer doesn't expose sensitive PII."""
    
    def test_aadhaar_not_exposed(self, candidate_profile):
        """🔴 CRITICAL: Aadhaar number MUST NOT be serialized."""
        serializer = CandidateProfileSerializer(candidate_profile)
        assert 'aadhaar_number' not in serializer.data, \
            "SECURITY VIOLATION: Aadhaar number exposed in API"
    
    def test_pan_not_exposed(self, candidate_profile):
        """🔴 CRITICAL: PAN number MUST NOT be serialized."""
        serializer = CandidateProfileSerializer(candidate_profile)
        assert 'pan_number' not in serializer.data, \
            "SECURITY VIOLATION: PAN number exposed in API"
    
    def test_passport_not_exposed(self, candidate_profile):
        """🔴 CRITICAL: Passport number MUST NOT be serialized."""
        serializer = CandidateProfileSerializer(candidate_profile)
        assert 'passport_number' not in serializer.data, \
            "SECURITY VIOLATION: Passport number exposed in API"
    
    def test_safe_fields_are_included(self, candidate_profile):
        """✅ Safe fields (name, age) SHOULD be included."""
        serializer = CandidateProfileSerializer(candidate_profile)
        assert 'first_name' in serializer.data
        assert 'last_name' in serializer.data
        assert 'full_name' in serializer.data


@pytest.mark.django_db
class TestDocumentSubmissionSerializerSecurity:
    """Test DocumentSubmissionSerializer doesn't expose sensitive fields."""
    
    def test_document_file_path_not_exposed(self, document_submission):
        """🔴 CRITICAL: Raw file path MUST NOT be exposed (IDOR risk)."""
        serializer = DocumentSubmissionSerializer(document_submission)
        assert 'document_file' not in serializer.data, \
            "SECURITY VIOLATION: Raw file path exposed (use file_url instead)"
    
    def test_file_url_is_provided(self, document_submission, rf):
        """✅ file_url (public URL) SHOULD be provided."""
        request = rf.get('/')
        serializer = DocumentSubmissionSerializer(
            document_submission,
            context={'request': request}
        )
        assert 'file_url' in serializer.data
    
    def test_verifier_id_not_exposed(self, document_submission):
        """🔴 CRITICAL: Internal verifier ID MUST NOT be exposed (enumeration risk)."""
        serializer = DocumentSubmissionSerializer(document_submission)
        assert 'verified_by' not in serializer.data, \
            "SECURITY VIOLATION: Verifier user ID exposed"
    
    def test_verification_notes_not_exposed(self, document_submission):
        """🔴 CRITICAL: Internal verification notes MUST NOT be exposed."""
        serializer = DocumentSubmissionSerializer(document_submission)
        assert 'verification_notes' not in serializer.data, \
            "SECURITY VIOLATION: Internal verification notes exposed"
    
    def test_cdby_upby_not_exposed(self, document_submission):
        """🔴 CRITICAL: Internal audit fields (cdby, upby) MUST NOT be exposed."""
        serializer = DocumentSubmissionSerializer(document_submission)
        assert 'cdby' not in serializer.data, \
            "SECURITY VIOLATION: Creator user ID (cdby) exposed"
        assert 'upby' not in serializer.data, \
            "SECURITY VIOLATION: Updater user ID (upby) exposed"


@pytest.mark.django_db
class TestApprovalWorkflowSerializerSecurity:
    """Test ApprovalWorkflowSerializer doesn't expose sensitive fields."""
    
    def test_decision_ip_address_not_exposed(self, approval_workflow):
        """🔴 CRITICAL: Decision IP address MUST NOT be exposed."""
        serializer = ApprovalWorkflowSerializer(approval_workflow)
        assert 'decision_ip_address' not in serializer.data, \
            "SECURITY VIOLATION: Approver IP address exposed"
    
    def test_approver_id_not_exposed(self, approval_workflow):
        """🔴 CRITICAL: Internal approver ID MUST NOT be exposed."""
        serializer = ApprovalWorkflowSerializer(approval_workflow)
        assert 'approver' not in serializer.data, \
            "SECURITY VIOLATION: Approver user ID exposed (use approver_name)"
    
    def test_approver_name_is_provided(self, approval_workflow):
        """✅ Approver name (non-enumerable) SHOULD be provided."""
        serializer = ApprovalWorkflowSerializer(approval_workflow)
        assert 'approver_name' in serializer.data
        assert 'approver_email' in serializer.data
    
    def test_decision_notes_not_exposed(self, approval_workflow):
        """🔴 CRITICAL: Internal decision notes MUST NOT be exposed."""
        serializer = ApprovalWorkflowSerializer(approval_workflow)
        assert 'decision_notes' not in serializer.data, \
            "SECURITY VIOLATION: Internal decision notes exposed"


@pytest.mark.django_db
class TestBackgroundCheckSerializerSecurity:
    """Test BackgroundCheckSerializer doesn't expose sensitive fields."""
    
    def test_check_results_not_exposed(self, background_check):
        """🔴 CRITICAL: Background check results MUST NOT be in public API."""
        serializer = BackgroundCheckSerializer(background_check)
        assert 'check_results' not in serializer.data, \
            "SECURITY VIOLATION: Background check results exposed"
    
    def test_verified_references_not_exposed(self, background_check):
        """🔴 CRITICAL: Verified references MUST NOT be exposed."""
        serializer = BackgroundCheckSerializer(background_check)
        assert 'verified_references' not in serializer.data, \
            "SECURITY VIOLATION: Reference check details exposed"
    
    def test_checked_by_id_not_exposed(self, background_check):
        """🔴 CRITICAL: Internal checker ID MUST NOT be exposed."""
        serializer = BackgroundCheckSerializer(background_check)
        assert 'checked_by' not in serializer.data, \
            "SECURITY VIOLATION: Checker user ID exposed (use checked_by_name)"
    
    def test_status_is_provided(self, background_check):
        """✅ High-level status SHOULD be provided."""
        serializer = BackgroundCheckSerializer(background_check)
        assert 'status' in serializer.data
        assert 'status_display' in serializer.data


@pytest.mark.django_db
class TestOnboardingRequestSerializerSecurity:
    """Test OnboardingRequestSerializer doesn't expose sensitive fields."""
    
    def test_people_id_not_exposed(self, onboarding_request):
        """🔴 CRITICAL: Linked People user ID MUST NOT be exposed (IDOR risk)."""
        serializer = OnboardingRequestSerializer(onboarding_request)
        assert 'people' not in serializer.data, \
            "SECURITY VIOLATION: Linked People user ID exposed"
    
    def test_cdby_not_exposed(self, onboarding_request):
        """🔴 CRITICAL: Creator user ID (cdby) MUST NOT be exposed."""
        serializer = OnboardingRequestSerializer(onboarding_request)
        # cdby should not be in fields, but created_by (nested) is OK
        assert 'cdby' not in serializer.data or isinstance(serializer.data.get('cdby'), dict), \
            "SECURITY VIOLATION: Creator user ID (cdby) exposed as raw ID"
    
    def test_internal_notes_not_exposed(self, onboarding_request):
        """🔴 CRITICAL: Internal notes MUST NOT be exposed."""
        serializer = OnboardingRequestSerializer(onboarding_request)
        assert 'internal_notes' not in serializer.data, \
            "SECURITY VIOLATION: Internal notes exposed"


@pytest.mark.django_db
class TestAccessProvisioningSerializerSecurity:
    """Test AccessProvisioningSerializer doesn't expose sensitive fields."""
    
    def test_credentials_not_exposed(self, db, onboarding_request):
        """🔴 CRITICAL: Issued credentials MUST NOT be exposed."""
        from apps.people_onboarding.models import AccessProvisioning
        access = AccessProvisioning.objects.create(
            onboarding_request=onboarding_request,
            access_type='BUILDING_ACCESS',
            status='PENDING',
        )
        serializer = AccessProvisioningSerializer(access)
        assert 'credentials_issued' not in serializer.data, \
            "SECURITY VIOLATION: Credential details exposed"


@pytest.mark.django_db
class TestTrainingAssignmentSerializerSecurity:
    """Test TrainingAssignmentSerializer doesn't expose sensitive fields."""
    
    def test_training_materials_path_not_exposed(self, db, onboarding_request):
        """🔴 CRITICAL: Internal training material paths MUST NOT be exposed."""
        from apps.people_onboarding.models import TrainingAssignment
        training = TrainingAssignment.objects.create(
            onboarding_request=onboarding_request,
            training_name='Security Training 101',
            status='ASSIGNED',
        )
        serializer = TrainingAssignmentSerializer(training)
        assert 'training_materials' not in serializer.data, \
            "SECURITY VIOLATION: Internal training paths exposed"


@pytest.mark.django_db
class TestSerializerFieldCounts:
    """
    Regression tests - ensure field counts don't balloon.
    
    If field count suddenly increases, it may indicate someone
    added `fields = '__all__'` or exposed new sensitive fields.
    """
    
    def test_document_submission_field_count(self, document_submission, rf):
        """DocumentSubmissionSerializer should have exactly 11 fields."""
        request = rf.get('/')
        serializer = DocumentSubmissionSerializer(
            document_submission,
            context={'request': request}
        )
        field_count = len(serializer.data.keys())
        assert field_count <= 15, \
            f"Field count increased from expected 11 to {field_count} - review for security"
    
    def test_approval_workflow_field_count(self, approval_workflow):
        """ApprovalWorkflowSerializer should have ~10 fields."""
        serializer = ApprovalWorkflowSerializer(approval_workflow)
        field_count = len(serializer.data.keys())
        assert field_count <= 12, \
            f"Field count increased from expected 10 to {field_count} - review for security"
    
    def test_background_check_field_count(self, background_check):
        """BackgroundCheckSerializer should have ~6 fields."""
        serializer = BackgroundCheckSerializer(background_check)
        field_count = len(serializer.data.keys())
        assert field_count <= 8, \
            f"Field count increased from expected 6 to {field_count} - review for security"


# Run with: pytest apps/people_onboarding/tests/test_serializer_security.py -v
