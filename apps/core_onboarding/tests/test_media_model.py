import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.core_onboarding.models import OnboardingMedia
from apps.peoples.models import People


@pytest.mark.django_db
class TestOnboardingMedia:

    def test_create_photo_media(self, test_user):
        """Test creating photo media with GPS"""
        media = OnboardingMedia.objects.create(
            context_type='SITE',
            context_object_id='test-site-123',
            media_type='PHOTO',
            file=SimpleUploadedFile("test.jpg", b"fake image content", content_type="image/jpeg"),
            gps_latitude=12.9716,
            gps_longitude=77.5946,
            uploaded_by=test_user
        )

        assert media.media_id is not None
        assert media.context_type == 'SITE'
        assert media.media_type == 'PHOTO'
        assert media.gps_latitude == 12.9716

    def test_create_media_without_gps(self, test_user):
        """Test creating media without GPS (0-N media flexibility)"""
        media = OnboardingMedia.objects.create(
            context_type='WORKER',
            context_object_id='worker-456',
            media_type='DOCUMENT',
            file=SimpleUploadedFile("id.pdf", b"fake pdf", content_type="application/pdf"),
            uploaded_by=test_user
        )

        assert media.gps_latitude is None
        assert media.gps_longitude is None
