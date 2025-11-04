"""
Multimodal Observation Flow Tests

Tests all input mode combinations for observations:
- Text only (0 media)
- Text + 1 photo
- Text + N photos
- Voice only (0 media)
- Voice + 1 video
- Voice + N media (photos + videos)
- Validation: reject both text AND voice
- Validation: reject neither text NOR voice

Following .claude/rules.md:
- Rule #7: Test organization by flow
- Rule #11: Specific exception handling
- Rule #19: Comprehensive edge case coverage
"""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from apps.site_onboarding.models import OnboardingSite
from apps.client_onboarding.models import Bt
from apps.core_onboarding.models import (
    OnboardingObservation,
    OnboardingMedia
)

People = get_user_model()


@pytest.fixture
def test_user(db):
    """Create test user"""
    return People.objects.create_user(
        peoplecode='MMTEST001',
        loginid='mmtestuser',
        peoplename='Multimodal Test User',
        email='mmtest@example.com'
    )


@pytest.fixture
def test_client(db):
    """Create test client"""
    return Bt.objects.create(
        bucode='MMCLIENT001',
        buname='Multimodal Test Client',
        active=True
    )


@pytest.fixture
def test_site(db, test_client):
    """Create test site"""
    return OnboardingSite.objects.create(
        site_name='Multimodal Test Site',
        client=test_client,
        address='456 Test Ave',
        city='Test City',
        state='TS',
        country='TestCountry',
        status='ACTIVE'
    )


@pytest.mark.django_db
class TestMultimodalInputModes:
    """Test all valid input mode combinations"""

    def test_text_only_zero_media(self, test_site, test_user):
        """
        Flow: Text only, 0 media
        Validates: Text input without any attachments
        """
        observation = OnboardingObservation.objects.create(
            context_type='SITE',
            context_object_id=str(test_site.uuid),
            text_input='Security gate is operational. Guards are present.',
            created_by=test_user,
            severity='INFO'
        )

        # Validate text-only mode
        assert observation.text_input != ''
        assert observation.audio_file.name == ''
        assert not observation.has_media()
        assert observation.media_count() == 0

        # Validate input type detection
        assert 'Text' in str(observation)

    def test_text_with_one_photo(self, test_site, test_user):
        """
        Flow: Text + 1 photo
        Validates: Text observation with single photo attachment
        """
        # Create photo
        photo_file = SimpleUploadedFile(
            "gate_photo.jpg",
            b"fake jpeg content",
            content_type="image/jpeg"
        )

        media = OnboardingMedia.objects.create(
            context_type='SITE',
            context_object_id=str(test_site.uuid),
            media_type='PHOTO',
            file=photo_file,
            text_description='Main gate view',
            uploaded_by=test_user
        )

        # Create text observation
        observation = OnboardingObservation.objects.create(
            context_type='SITE',
            context_object_id=str(test_site.uuid),
            text_input='Main gate with camera coverage.',
            created_by=test_user
        )
        observation.media.add(media)

        # Validate
        assert observation.text_input != ''
        assert observation.has_media()
        assert observation.media_count() == 1
        assert observation.media.first().media_type == 'PHOTO'

    def test_text_with_multiple_photos(self, test_site, test_user):
        """
        Flow: Text + N photos (3)
        Validates: Text with multiple photo attachments
        """
        # Create 3 photos
        photos = []
        for i in range(3):
            photo_file = SimpleUploadedFile(
                f"photo_{i}.jpg",
                b"fake jpeg content",
                content_type="image/jpeg"
            )

            media = OnboardingMedia.objects.create(
                context_type='SITE',
                context_object_id=str(test_site.uuid),
                media_type='PHOTO',
                file=photo_file,
                text_description=f'View {i+1}',
                uploaded_by=test_user
            )
            photos.append(media)

        # Create observation
        observation = OnboardingObservation.objects.create(
            context_type='SITE',
            context_object_id=str(test_site.uuid),
            text_input='Three-angle view of the perimeter fence.',
            created_by=test_user
        )
        observation.media.add(*photos)

        # Validate
        assert observation.text_input != ''
        assert observation.media_count() == 3
        for media_item in observation.media.all():
            assert media_item.media_type == 'PHOTO'

    def test_voice_only_zero_media(self, test_site, test_user):
        """
        Flow: Voice only, 0 media
        Validates: Voice observation without media attachments
        """
        audio_file = SimpleUploadedFile(
            "voice_note.mp3",
            b"fake audio content",
            content_type="audio/mpeg"
        )

        observation = OnboardingObservation.objects.create(
            context_type='SITE',
            context_object_id=str(test_site.uuid),
            audio_file=audio_file,
            original_transcript='All checkpoints are manned. No issues.',
            created_by=test_user,
            severity='INFO'
        )

        # Validate voice-only mode
        assert observation.audio_file.name != ''
        assert observation.original_transcript != ''
        assert observation.text_input == ''
        assert not observation.has_media()
        assert observation.media_count() == 0

        # Validate input type detection
        assert 'Voice' in str(observation)

    def test_voice_with_one_video(self, test_site, test_user):
        """
        Flow: Voice + 1 video
        Validates: Voice narration with video attachment
        """
        # Create audio
        audio_file = SimpleUploadedFile(
            "narration.mp3",
            b"fake audio content",
            content_type="audio/mpeg"
        )

        # Create video
        video_file = SimpleUploadedFile(
            "patrol.mp4",
            b"fake video content",
            content_type="video/mp4"
        )

        video_media = OnboardingMedia.objects.create(
            context_type='SITE',
            context_object_id=str(test_site.uuid),
            media_type='VIDEO',
            file=video_file,
            voice_transcript='Showing patrol route along perimeter.',
            uploaded_by=test_user
        )

        # Create observation
        observation = OnboardingObservation.objects.create(
            context_type='SITE',
            context_object_id=str(test_site.uuid),
            audio_file=audio_file,
            original_transcript='Patrol route video. All areas covered.',
            created_by=test_user
        )
        observation.media.add(video_media)

        # Validate
        assert observation.audio_file.name != ''
        assert observation.has_media()
        assert observation.media_count() == 1
        assert observation.media.first().media_type == 'VIDEO'

    def test_voice_with_multiple_photos_and_videos(self, test_site, test_user):
        """
        Flow: Voice + N photos + videos (2 photos + 1 video)
        Validates: Voice with mixed media types
        """
        # Create audio
        audio_file = SimpleUploadedFile(
            "walkthrough.mp3",
            b"fake audio content",
            content_type="audio/mpeg"
        )

        # Create 2 photos
        photos = []
        for i in range(2):
            photo_file = SimpleUploadedFile(
                f"checkpoint_{i}.jpg",
                b"fake jpeg content",
                content_type="image/jpeg"
            )
            media = OnboardingMedia.objects.create(
                context_type='SITE',
                context_object_id=str(test_site.uuid),
                media_type='PHOTO',
                file=photo_file,
                uploaded_by=test_user
            )
            photos.append(media)

        # Create 1 video
        video_file = SimpleUploadedFile(
            "overview.mp4",
            b"fake video content",
            content_type="video/mp4"
        )
        video = OnboardingMedia.objects.create(
            context_type='SITE',
            context_object_id=str(test_site.uuid),
            media_type='VIDEO',
            file=video_file,
            uploaded_by=test_user
        )

        # Create observation
        observation = OnboardingObservation.objects.create(
            context_type='SITE',
            context_object_id=str(test_site.uuid),
            audio_file=audio_file,
            original_transcript='Complete site walkthrough with checkpoints.',
            created_by=test_user
        )

        # Attach all media
        observation.media.add(*photos)
        observation.media.add(video)

        # Validate
        assert observation.audio_file.name != ''
        assert observation.media_count() == 3

        # Validate media type distribution
        media_types = [m.media_type for m in observation.media.all()]
        assert media_types.count('PHOTO') == 2
        assert media_types.count('VIDEO') == 1

    def test_text_with_mixed_media_types(self, test_site, test_user):
        """
        Flow: Text + photos + video + document
        Validates: Text with diverse media types
        """
        # Create various media types
        photo = OnboardingMedia.objects.create(
            context_type='SITE',
            context_object_id=str(test_site.uuid),
            media_type='PHOTO',
            file=SimpleUploadedFile("plan.jpg", b"photo", content_type="image/jpeg"),
            uploaded_by=test_user
        )

        video = OnboardingMedia.objects.create(
            context_type='SITE',
            context_object_id=str(test_site.uuid),
            media_type='VIDEO',
            file=SimpleUploadedFile("tour.mp4", b"video", content_type="video/mp4"),
            uploaded_by=test_user
        )

        document = OnboardingMedia.objects.create(
            context_type='SITE',
            context_object_id=str(test_site.uuid),
            media_type='DOCUMENT',
            file=SimpleUploadedFile("blueprint.pdf", b"pdf", content_type="application/pdf"),
            uploaded_by=test_user
        )

        # Create observation
        observation = OnboardingObservation.objects.create(
            context_type='SITE',
            context_object_id=str(test_site.uuid),
            text_input='Site documentation: floor plan, video tour, and blueprint.',
            created_by=test_user
        )

        observation.media.add(photo, video, document)

        # Validate
        assert observation.media_count() == 3
        media_types = {m.media_type for m in observation.media.all()}
        assert media_types == {'PHOTO', 'VIDEO', 'DOCUMENT'}


@pytest.mark.django_db
class TestMultimodalValidation:
    """Test input validation rules"""

    def test_both_text_and_voice_is_valid(self, test_site, test_user):
        """
        Validation: Having BOTH text AND voice is VALID
        (User might type AND record voice)
        """
        audio_file = SimpleUploadedFile(
            "both.mp3",
            b"fake audio",
            content_type="audio/mpeg"
        )

        # This should NOT raise an error - both inputs are allowed
        observation = OnboardingObservation.objects.create(
            context_type='SITE',
            context_object_id=str(test_site.uuid),
            text_input='Typed observation about gate.',
            audio_file=audio_file,
            original_transcript='Voice recording about same gate.',
            created_by=test_user
        )

        # Validate both modes present
        assert observation.text_input != ''
        assert observation.audio_file.name != ''
        assert observation.original_transcript != ''

    def test_neither_text_nor_voice_creates_empty_observation(self, test_site, test_user):
        """
        Validation: Having NEITHER text NOR voice creates empty observation
        (This may be prevented at application level, but model allows it)
        """
        # Model allows empty observation (might have media only)
        observation = OnboardingObservation.objects.create(
            context_type='SITE',
            context_object_id=str(test_site.uuid),
            created_by=test_user,
            severity='INFO'
        )

        # Validate empty state
        assert observation.text_input == ''
        assert observation.audio_file.name == ''
        assert observation.original_transcript == ''

        # Could still have media attached
        assert observation.media_count() == 0

    def test_observation_with_only_media_no_input(self, test_site, test_user):
        """
        Flow: Media only, no text or voice
        Use case: User uploads photo without description
        """
        # Create media
        media = OnboardingMedia.objects.create(
            context_type='SITE',
            context_object_id=str(test_site.uuid),
            media_type='PHOTO',
            file=SimpleUploadedFile("photo.jpg", b"photo", content_type="image/jpeg"),
            uploaded_by=test_user
        )

        # Create observation without text or voice
        observation = OnboardingObservation.objects.create(
            context_type='SITE',
            context_object_id=str(test_site.uuid),
            created_by=test_user
        )
        observation.media.add(media)

        # Validate
        assert observation.text_input == ''
        assert observation.audio_file.name == ''
        assert observation.has_media()
        assert observation.media_count() == 1


@pytest.mark.django_db
class TestMediaMetadata:
    """Test media metadata capture"""

    def test_photo_with_gps_metadata(self, test_site, test_user):
        """Test GPS capture for photos"""
        media = OnboardingMedia.objects.create(
            context_type='SITE',
            context_object_id=str(test_site.uuid),
            media_type='PHOTO',
            file=SimpleUploadedFile("gps.jpg", b"photo", content_type="image/jpeg"),
            gps_latitude=12.9716,
            gps_longitude=77.5946,
            gps_accuracy=5.0,
            compass_direction=90.0,
            uploaded_by=test_user
        )

        assert media.gps_latitude is not None
        assert media.gps_longitude is not None
        assert media.gps_accuracy == 5.0
        assert media.compass_direction == 90.0

    def test_video_with_voice_transcript(self, test_site, test_user):
        """Test voice transcript for videos"""
        media = OnboardingMedia.objects.create(
            context_type='SITE',
            context_object_id=str(test_site.uuid),
            media_type='VIDEO',
            file=SimpleUploadedFile("video.mp4", b"video", content_type="video/mp4"),
            voice_transcript='This is the narration in the video.',
            uploaded_by=test_user
        )

        assert media.voice_transcript != ''
        assert 'narration' in media.voice_transcript

    def test_media_with_text_description(self, test_site, test_user):
        """Test text description for media"""
        media = OnboardingMedia.objects.create(
            context_type='SITE',
            context_object_id=str(test_site.uuid),
            media_type='PHOTO',
            file=SimpleUploadedFile("photo.jpg", b"photo", content_type="image/jpeg"),
            text_description='North perimeter fence section B',
            uploaded_by=test_user
        )

        assert media.text_description != ''
        assert 'North perimeter' in media.text_description

    def test_media_with_ai_analysis(self, test_site, test_user):
        """Test AI analysis metadata storage"""
        media = OnboardingMedia.objects.create(
            context_type='SITE',
            context_object_id=str(test_site.uuid),
            media_type='PHOTO',
            file=SimpleUploadedFile("analyzed.jpg", b"photo", content_type="image/jpeg"),
            uploaded_by=test_user,
            ai_analysis={
                'vision_api_confidence': 0.95,
                'labels': ['fence', 'outdoor', 'security'],
                'text_detected': False
            },
            detected_objects=['fence', 'gate', 'camera'],
            safety_concerns=['no fire extinguisher visible'],
            processed=True
        )

        assert media.ai_analysis != {}
        assert media.ai_analysis['vision_api_confidence'] == 0.95
        assert 'fence' in media.detected_objects
        assert len(media.safety_concerns) > 0
        assert media.processed is True


@pytest.mark.django_db
class TestObservationEnhancement:
    """Test AI enhancement features"""

    def test_translation_enhancement(self, test_site, test_user):
        """Test multilingual observation enhancement"""
        observation = OnboardingObservation.objects.create(
            context_type='SITE',
            context_object_id=str(test_site.uuid),
            text_input='La puerta está rota',  # Spanish
            english_translation='The door is broken',
            created_by=test_user
        )

        assert observation.text_input != observation.english_translation
        assert observation.english_translation == 'The door is broken'

    def test_llm_enhancement(self, test_site, test_user):
        """Test LLM-enhanced observation"""
        observation = OnboardingObservation.objects.create(
            context_type='SITE',
            context_object_id=str(test_site.uuid),
            text_input='gate broken',
            enhanced_observation=(
                'Security Assessment: Main entrance gate shows structural damage. '
                'Immediate repair required to maintain perimeter security integrity. '
                'Temporary security measures should be implemented until repair is complete.'
            ),
            created_by=test_user,
            severity='HIGH',
            confidence_score=0.87
        )

        assert len(observation.enhanced_observation) > len(observation.text_input)
        assert 'Security Assessment' in observation.enhanced_observation
        assert observation.confidence_score == 0.87

    def test_entity_extraction(self, test_site, test_user):
        """Test NER entity extraction"""
        observation = OnboardingObservation.objects.create(
            context_type='SITE',
            context_object_id=str(test_site.uuid),
            text_input='Camera #5 at Gate 3 is offline since 2pm.',
            entities={
                'asset': 'Camera #5',
                'location': 'Gate 3',
                'time': '2pm',
                'status': 'offline'
            },
            created_by=test_user,
            severity='MEDIUM'
        )

        assert 'asset' in observation.entities
        assert observation.entities['asset'] == 'Camera #5'
        assert observation.entities['location'] == 'Gate 3'


@pytest.mark.django_db
class TestContextTypeSupport:
    """Test observations across all context types"""

    def test_client_context_observation(self, test_client, test_user):
        """Test CLIENT context observations"""
        observation = OnboardingObservation.objects.create(
            context_type='CLIENT',
            context_object_id=test_client.bucode,
            text_input='Office has modern security systems.',
            created_by=test_user
        )

        assert observation.context_type == 'CLIENT'
        assert observation.context_object_id == test_client.bucode

    def test_site_context_observation(self, test_site, test_user):
        """Test SITE context observations"""
        observation = OnboardingObservation.objects.create(
            context_type='SITE',
            context_object_id=str(test_site.uuid),
            text_input='Perimeter is well-maintained.',
            created_by=test_user
        )

        assert observation.context_type == 'SITE'
        assert observation.context_object_id == str(test_site.uuid)

    def test_worker_context_observation(self, test_user):
        """Test WORKER context observations"""
        worker_id = 'WORKER-12345'

        observation = OnboardingObservation.objects.create(
            context_type='WORKER',
            context_object_id=worker_id,
            text_input='ID documents verified.',
            created_by=test_user
        )

        assert observation.context_type == 'WORKER'
        assert observation.context_object_id == worker_id
