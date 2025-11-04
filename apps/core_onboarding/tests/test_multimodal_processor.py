import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from apps.core_onboarding.services.media import MultimodalInputProcessor


@pytest.mark.django_db
class TestMultimodalInputProcessor:

    def test_process_text_only_no_media(self, test_user):
        """Test text input with 0 media (minimum case)"""
        processor = MultimodalInputProcessor()

        result = processor.process_input(
            context_type='CLIENT',
            context_object_id='client-123',
            text_input='Client confirmed requirements',
            audio_file=None,
            photos=[],
            videos=[],
            created_by=test_user
        )

        assert result['observation_id'] is not None
        assert result['media_count'] == 0
        assert result['input_type'] == 'text'

    def test_process_voice_with_multiple_photos(self, test_user):
        """Test voice input with N photos"""
        processor = MultimodalInputProcessor()

        audio = SimpleUploadedFile("voice.mp3", b"audio data", content_type="audio/mp3")
        photos = [
            SimpleUploadedFile("photo1.jpg", b"image1", content_type="image/jpeg"),
            SimpleUploadedFile("photo2.jpg", b"image2", content_type="image/jpeg"),
            SimpleUploadedFile("photo3.jpg", b"image3", content_type="image/jpeg"),
        ]

        result = processor.process_input(
            context_type='SITE',
            context_object_id='site-789',
            text_input=None,
            audio_file=audio,
            photos=photos,
            videos=[],
            gps_location={'lat': 12.34, 'lng': 56.78},
            created_by=test_user
        )

        assert result['media_count'] == 3
        assert result['input_type'] == 'voice'

    def test_rejects_both_text_and_voice(self, test_user):
        """Test validation: cannot provide both text and voice"""
        processor = MultimodalInputProcessor()

        with pytest.raises(ValidationError, match='Provide text OR audio'):
            processor.process_input(
                context_type='SITE',
                context_object_id='site-123',
                text_input='Some text',
                audio_file=SimpleUploadedFile("voice.mp3", b"audio"),
                photos=[],
                videos=[],
                created_by=test_user
            )
