"""
Schema validation tests to ensure backend responses match mobile DTOs exactly.

These tests prevent mobile integration breakage by validating that all required
fields are present with correct types and structure.
"""
import pytest
from rest_framework.test import APIClient
from django.utils import timezone
from apps.peoples.models import People, PeopleProfile


@pytest.fixture
def api_client():
    """REST API client for testing."""
    return APIClient()


@pytest.fixture
def user_with_onboarding_capability(basic_user):
    """User with onboarding capability enabled."""
    basic_user.capabilities = {
        'canAccessOnboarding': True,
        'canUseVoiceFeatures': False,
        'canUseVoiceBiometrics': False,
    }
    basic_user.save()
    return basic_user


@pytest.mark.django_db
class TestProfileCompletionSchema:
    """Validate ProfileCompletionDto schema alignment."""

    REQUIRED_FIELDS = [
        'is_complete',
        'completion_percentage',
        'missing_fields',
        'has_completed_onboarding',
        'onboarding_completed_at',
        'onboarding_skipped',
        'first_login_completed',
        'can_skip_onboarding',
        'required_documents',
        'onboarding_workflow_state',
    ]

    def test_completion_status_has_all_required_fields(self, api_client, user_with_onboarding_capability):
        """Response must contain all fields mobile expects."""
        api_client.force_authenticate(user=user_with_onboarding_capability)

        response = api_client.get('/api/v2/people/profile/completion-status/')

        assert response.status_code == 200
        for field in self.REQUIRED_FIELDS:
            assert field in response.data, f"Missing required field: {field}"

    def test_completion_percentage_is_integer(self, api_client, user_with_onboarding_capability):
        """completion_percentage must be integer 0-100."""
        api_client.force_authenticate(user=user_with_onboarding_capability)

        response = api_client.get('/api/v2/people/profile/completion-status/')

        assert isinstance(response.data['completion_percentage'], int)
        assert 0 <= response.data['completion_percentage'] <= 100

    def test_missing_fields_structure(self, api_client, user_with_onboarding_capability):
        """missing_fields must be list of dicts with 'field' and 'display_name'."""
        api_client.force_authenticate(user=user_with_onboarding_capability)

        response = api_client.get('/api/v2/people/profile/completion-status/')

        assert isinstance(response.data['missing_fields'], list)
        for item in response.data['missing_fields']:
            assert 'field' in item
            assert 'display_name' in item
            assert isinstance(item['field'], str)
            assert isinstance(item['display_name'], str)

    def test_boolean_fields_are_boolean(self, api_client, user_with_onboarding_capability):
        """All boolean fields must be actual booleans."""
        api_client.force_authenticate(user=user_with_onboarding_capability)

        response = api_client.get('/api/v2/people/profile/completion-status/')

        boolean_fields = [
            'is_complete',
            'has_completed_onboarding',
            'onboarding_skipped',
            'first_login_completed',
            'can_skip_onboarding',
        ]

        for field in boolean_fields:
            assert isinstance(response.data[field], bool), f"{field} must be boolean"


@pytest.mark.django_db
class TestMarkOnboardingCompleteSchema:
    """Validate MarkOnboardingCompleteResponseDto schema alignment."""

    REQUIRED_FIELDS = [
        'success',
        'onboarding_completed_at',
        'onboarding_skipped',
        'first_login_completed',
    ]

    def test_mark_complete_response_schema(self, api_client, user_with_onboarding_capability):
        """Response must match mobile DTO structure."""
        api_client.force_authenticate(user=user_with_onboarding_capability)

        response = api_client.post('/api/v2/people/profile/mark-onboarding-complete/', {
            'skipped': False,
            'completed_steps': ['welcome', 'permissions']
        }, format='json')

        assert response.status_code == 200
        for field in self.REQUIRED_FIELDS:
            assert field in response.data, f"Missing required field: {field}"

    def test_success_is_boolean(self, api_client, user_with_onboarding_capability):
        """success field must be boolean."""
        api_client.force_authenticate(user=user_with_onboarding_capability)

        response = api_client.post('/api/v2/people/profile/mark-onboarding-complete/', {
            'skipped': False,
            'completed_steps': []
        }, format='json')

        assert isinstance(response.data['success'], bool)
        assert response.data['success'] is True

    def test_timestamp_or_null(self, api_client, user_with_onboarding_capability):
        """onboarding_completed_at must be ISO string or null."""
        api_client.force_authenticate(user=user_with_onboarding_capability)

        # Complete onboarding
        response = api_client.post('/api/v2/people/profile/mark-onboarding-complete/', {
            'skipped': False,
            'completed_steps': ['welcome']
        }, format='json')

        assert response.data['onboarding_completed_at'] is not None
        assert 'T' in response.data['onboarding_completed_at']  # ISO 8601 format


@pytest.mark.django_db
class TestProfileImageResponseSchema:
    """Validate ProfileImageResponseDto schema alignment."""

    def test_image_upload_response_schema(self, api_client, basic_user):
        """Response must have image_url and profile_completion_percentage."""
        from PIL import Image
        from io import BytesIO
        from django.core.files.uploadedfile import SimpleUploadedFile

        api_client.force_authenticate(user=basic_user)

        # Create valid test image
        image = Image.new('RGB', (500, 500), color='red')
        buffer = BytesIO()
        image.save(buffer, format='JPEG')
        buffer.seek(0)

        uploaded_file = SimpleUploadedFile(
            name='test.jpg',
            content=buffer.read(),
            content_type='image/jpeg'
        )

        response = api_client.post('/api/v2/people/profile/me/image/', {
            'image': uploaded_file
        }, format='multipart')

        assert response.status_code == 200
        assert 'image_url' in response.data
        assert 'profile_completion_percentage' in response.data
        assert isinstance(response.data['profile_completion_percentage'], int)


@pytest.mark.django_db
class TestProfileRetrieveSchema:
    """Validate profile retrieval schema."""

    def test_profile_me_has_capabilities(self, api_client, basic_user):
        """GET /profile/me/ must include capabilities dict."""
        api_client.force_authenticate(user=basic_user)

        response = api_client.get('/api/v2/people/profile/me/')

        assert response.status_code == 200
        assert 'capabilities' in response.data
        assert isinstance(response.data['capabilities'], dict)

        # Verify all 13 capability flags present
        required_capabilities = [
            'canAccessPeople',
            'canAccessAttendance',
            'canAccessOperations',
            'canAccessHelpdesk',
            'canAccessJournal',
            'canAccessReports',
            'canAccessCalendar',
            'canAccessOnboarding',
            'canUseVoiceFeatures',
            'canUseVoiceBiometrics',
            'canApproveJobs',
            'canManageTeam',
            'canViewAnalytics',
        ]

        for cap in required_capabilities:
            assert cap in response.data['capabilities'], f"Missing capability: {cap}"

    def test_profile_me_has_onboarding_status(self, api_client, basic_user):
        """GET /profile/me/ must include onboarding_status."""
        api_client.force_authenticate(user=basic_user)

        response = api_client.get('/api/v2/people/profile/me/')

        assert response.status_code == 200
        assert 'onboarding_status' in response.data
        assert 'first_login_completed' in response.data['onboarding_status']
        assert 'onboarding_completed_at' in response.data['onboarding_status']
        assert 'onboarding_skipped' in response.data['onboarding_status']


@pytest.mark.django_db
class TestLoginResponseSchema:
    """Validate login response includes capabilities."""

    def test_login_response_includes_capabilities(self, api_client, basic_user):
        """Login response must include capabilities in user object."""
        # Set password for authentication
        basic_user.set_password('TestPassword123!')
        basic_user.save()

        response = api_client.post('/api/v2/auth/login/', {
            'username': basic_user.loginid,
            'password': 'TestPassword123!'
        }, format='json')

        assert response.status_code == 200
        assert 'user' in response.data['data']
        assert 'capabilities' in response.data['data']['user']
        assert isinstance(response.data['data']['user']['capabilities'], dict)

    def test_login_response_includes_onboarding_fields(self, api_client, basic_user):
        """Login response must include onboarding tracking fields."""
        basic_user.set_password('TestPassword123!')
        basic_user.save()

        response = api_client.post('/api/v2/auth/login/', {
            'username': basic_user.loginid,
            'password': 'TestPassword123!'
        }, format='json')

        assert response.status_code == 200
        user_data = response.data['data']['user']
        assert 'first_login_completed' in user_data
        assert 'onboarding_completed_at' in user_data
        assert 'profile_completion_percentage' in user_data
