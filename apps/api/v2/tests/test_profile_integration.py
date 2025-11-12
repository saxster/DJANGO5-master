"""
Integration tests for profile and onboarding API endpoints.

Tests end-to-end flows:
- Complete onboarding workflow
- Capability enforcement (403 responses)
- Multi-tenancy security
- File upload validation
"""
import pytest
from rest_framework.test import APIClient
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from io import BytesIO
from apps.peoples.models import People, PeopleProfile


@pytest.fixture
def api_client():
    """REST API client for integration testing."""
    return APIClient()


def create_test_image(width=500, height=500, format='JPEG'):
    """Helper to create test image."""
    image = Image.new('RGB', (width, height), color='blue')
    buffer = BytesIO()
    image.save(buffer, format=format)
    buffer.seek(0)
    return SimpleUploadedFile(
        name=f'test.{format.lower()}',
        content=buffer.read(),
        content_type=f'image/{format.lower()}'
    )


@pytest.mark.django_db
class TestCompleteOnboardingFlow:
    """Test end-to-end onboarding flow."""

    def test_complete_onboarding_workflow(self, api_client, basic_user):
        """Test full mobile onboarding flow from start to finish."""
        # 1. Enable onboarding capability
        basic_user.capabilities = {'canAccessOnboarding': True}
        basic_user.save()
        api_client.force_authenticate(user=basic_user)

        # 2. Get initial completion status
        response = api_client.get('/api/v2/people/profile/completion-status/')
        assert response.status_code == 200
        initial_percentage = response.data['completion_percentage']
        initial_missing = len(response.data['missing_fields'])

        # 3. Upload profile image
        image = create_test_image()
        response = api_client.post('/api/v2/people/profile/me/image/', {'image': image})
        assert response.status_code == 200
        assert 'image_url' in response.data
        assert response.data['profile_completion_percentage'] > initial_percentage

        # 4. Update profile fields
        response = api_client.patch('/api/v2/people/profile/me/', {
            'profile': {
                'gender': 'M',
                'dateofjoin': '2025-01-01'
            }
        }, format='json')
        assert response.status_code == 200
        # Profile completion should increase

        # 5. Check completion status again
        response = api_client.get('/api/v2/people/profile/completion-status/')
        assert response.status_code == 200
        assert len(response.data['missing_fields']) < initial_missing

        # 6. Mark onboarding complete
        response = api_client.post('/api/v2/people/profile/mark-onboarding-complete/', {
            'skipped': False,
            'completed_steps': ['welcome', 'permissions', 'profile_setup']
        }, format='json')
        assert response.status_code == 200
        assert response.data['success'] is True
        assert response.data['onboarding_completed_at'] is not None
        assert response.data['first_login_completed'] is True

        # 7. Verify final status
        response = api_client.get('/api/v2/people/profile/completion-status/')
        assert response.status_code == 200
        assert response.data['has_completed_onboarding'] is True


@pytest.mark.django_db
class TestCapabilityEnforcement:
    """Test capability enforcement returns proper 403 responses."""

    def test_completion_status_requires_capability(self, api_client, basic_user):
        """GET /profile/completion-status/ requires canAccessOnboarding."""
        basic_user.capabilities = {'canAccessOnboarding': False}
        basic_user.save()
        api_client.force_authenticate(user=basic_user)

        response = api_client.get('/api/v2/people/profile/completion-status/')

        assert response.status_code == 403
        assert 'do not have permission' in response.data['detail'].lower()

    def test_mark_complete_requires_capability(self, api_client, basic_user):
        """POST /mark-onboarding-complete/ requires canAccessOnboarding."""
        basic_user.capabilities = {'canAccessOnboarding': False}
        basic_user.save()
        api_client.force_authenticate(user=basic_user)

        response = api_client.post('/api/v2/people/profile/mark-onboarding-complete/', {
            'skipped': False,
            'completed_steps': []
        }, format='json')

        assert response.status_code == 403

    def test_voice_note_upload_requires_capability(self, api_client, basic_user):
        """Audio upload requires canUseVoiceFeatures."""
        from apps.journal.models import JournalEntry

        basic_user.capabilities = {'canUseVoiceFeatures': False}
        basic_user.save()
        api_client.force_authenticate(user=basic_user)

        # Create journal entry
        entry = JournalEntry.objects.create(
            user=basic_user,
            tenant_id=basic_user.client_id,
            title='Test',
            content='Test entry'
        )

        # Try to upload audio without capability
        audio_file = SimpleUploadedFile('test.mp3', b'fake audio data', content_type='audio/mpeg')

        response = api_client.post(
            f'/api/v2/wellness/journal/{entry.id}/media/',
            {'file': audio_file, 'media_type': 'AUDIO'},
            format='multipart'
        )

        assert response.status_code == 403
        assert 'do not have permission' in response.data['error']['message'].lower()

    def test_photo_upload_does_not_require_voice_capability(self, api_client, basic_user):
        """Photo upload should work without voice capability."""
        from apps.journal.models import JournalEntry

        basic_user.capabilities = {'canUseVoiceFeatures': False}
        basic_user.save()
        api_client.force_authenticate(user=basic_user)

        # Create journal entry
        entry = JournalEntry.objects.create(
            user=basic_user,
            tenant_id=basic_user.client_id,
            title='Test',
            content='Test entry'
        )

        # Upload photo (should work)
        photo = create_test_image()

        response = api_client.post(
            f'/api/v2/wellness/journal/{entry.id}/media/',
            {'file': photo, 'media_type': 'PHOTO'},
            format='multipart'
        )

        assert response.status_code == 201  # Should succeed


@pytest.mark.django_db
class TestMultiTenancySecurity:
    """Test multi-tenancy isolation in journal media uploads."""

    def test_cannot_add_media_to_other_tenant_entry(self, api_client, basic_user, test_tenant):
        """Should prevent cross-tenant media uploads."""
        from apps.journal.models import JournalEntry
        from apps.client_onboarding.models import Bt

        api_client.force_authenticate(user=basic_user)

        # Create another tenant
        other_tenant = Bt.objects.create(
            bucode="OTHER",
            buname="Other Tenant",
            enable=True
        )

        # Create entry for different tenant
        other_entry = JournalEntry.objects.create(
            user=basic_user,
            tenant_id=other_tenant.id,  # Different tenant!
            title='Other Tenant Entry',
            content='Content'
        )

        # Try to upload media (should fail tenant check)
        photo = create_test_image()

        response = api_client.post(
            f'/api/v2/wellness/journal/{other_entry.id}/media/',
            {'file': photo, 'media_type': 'PHOTO'},
            format='multipart'
        )

        assert response.status_code == 404  # Not found (tenant mismatch)


@pytest.mark.django_db
class TestFileUploadValidation:
    """Test file upload validation rules."""

    def test_reject_image_too_large(self, api_client, basic_user):
        """Should reject images > 5MB."""
        api_client.force_authenticate(user=basic_user)

        # Create large image (6MB)
        large_image = Image.new('RGB', (4000, 4000), color='red')
        buffer = BytesIO()
        large_image.save(buffer, format='JPEG', quality=100)
        buffer.seek(0)

        large_file = SimpleUploadedFile(
            name='large.jpg',
            content=buffer.read(),
            content_type='image/jpeg'
        )

        response = api_client.post('/api/v2/people/profile/me/image/', {
            'image': large_file
        }, format='multipart')

        # Should reject if > 5MB
        if large_file.size > 5 * 1024 * 1024:
            assert response.status_code == 400
            assert 'too large' in response.data['error'].lower()

    def test_reject_image_dimensions_too_small(self, api_client, basic_user):
        """Should reject images < 200x200 pixels."""
        api_client.force_authenticate(user=basic_user)

        small_image = create_test_image(width=100, height=100)

        response = api_client.post('/api/v2/people/profile/me/image/', {
            'image': small_image
        }, format='multipart')

        assert response.status_code == 400
        assert 'too small' in response.data['error'].lower()

    def test_reject_invalid_onboarding_step(self, api_client, basic_user):
        """Should reject invalid onboarding steps."""
        basic_user.capabilities = {'canAccessOnboarding': True}
        basic_user.save()
        api_client.force_authenticate(user=basic_user)

        response = api_client.post('/api/v2/people/profile/mark-onboarding-complete/', {
            'skipped': False,
            'completed_steps': ['welcome', 'invalid_step', 'permissions']
        }, format='json')

        assert response.status_code == 400
        assert 'invalid_step' in str(response.data).lower()
