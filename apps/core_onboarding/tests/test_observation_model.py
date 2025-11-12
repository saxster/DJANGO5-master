import pytest
from apps.core_onboarding.models import OnboardingObservation, OnboardingMedia


@pytest.mark.django_db
class TestOnboardingObservation:

    def test_create_text_observation_no_media(self, test_user):
        """Test text-only observation with 0 media (flexibility)"""
        obs = OnboardingObservation.objects.create(
            context_type='CLIENT',
            context_object_id='client-123',
            text_input='Client confirmed security requirements',
            created_by=test_user
        )

        assert obs.observation_id is not None
        assert obs.text_input == 'Client confirmed security requirements'
        assert obs.media.count() == 0  # Zero media

    def test_create_voice_observation_with_multiple_photos(self, test_user):
        """Test voice observation with N photos"""
        from django.core.files.uploadedfile import SimpleUploadedFile

        obs = OnboardingObservation.objects.create(
            context_type='SITE',
            context_object_id='site-789',
            audio_file=SimpleUploadedFile("voice.mp3", b"audio data"),
            original_transcript='Gate 3 has broken lock',
            created_by=test_user
        )

        # Add 3 photos
        for i in range(3):
            media = OnboardingMedia.objects.create(
                context_type='SITE',
                context_object_id='site-789',
                media_type='PHOTO',
                file=SimpleUploadedFile(f"photo{i}.jpg", b"image"),
                uploaded_by=test_user
            )
            obs.media.add(media)

        assert obs.media.count() == 3  # Multiple media
        assert obs.original_transcript == 'Gate 3 has broken lock'
