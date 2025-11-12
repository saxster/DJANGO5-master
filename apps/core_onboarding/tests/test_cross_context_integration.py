"""
Cross-Context Integration Tests for Bounded Contexts Refactoring

Tests the integration between three bounded contexts:
- Client context (apps.client_onboarding)
- Site context (apps.site_onboarding)
- Worker context (apps.people_onboarding)

Validates:
- Entity creation flows
- Multimodal observation attachments
- Cross-context relationships
- Media uploads with GPS metadata

Following .claude/rules.md:
- Rule #7: Test files organized by concern
- Rule #11: Specific exception testing
- Rule #19: Integration test best practices
"""
import uuid
import pytest
from datetime import datetime
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.client_onboarding.models import Bt
from apps.site_onboarding.models import OnboardingSite
from apps.people_onboarding.models import OnboardingRequest
from apps.core_onboarding.models import (
    OnboardingObservation,
    OnboardingMedia,
    ConversationSession
)

People = get_user_model()


@pytest.fixture
def test_user(db):
    """Create test user for observations"""
    return People.objects.create_user(
        peoplecode='TESTUSER001',
        loginid='testuser',
        peoplename='Test User',
        email='test@example.com'
    )


@pytest.fixture
def test_client(db, test_user):
    """Create test client (business unit)"""
    return Bt.objects.create(
        bucode='TESTCLIENT001',
        buname='Test Client Corporation',
        description='Integration test client',
        active=True
    )


@pytest.fixture
def test_site(db, test_client):
    """Create test site linked to client"""
    site = OnboardingSite.objects.create(
        site_name='Test Site Alpha',
        client=test_client,
        address='123 Test Street',
        city='Test City',
        state='TS',
        country='TestCountry',
        status='ACTIVE'
    )
    return site


@pytest.fixture
def test_worker_request(db, test_client, test_user):
    """Create test worker onboarding request"""
    return OnboardingRequest.objects.create(
        request_number=f'WKR-{uuid.uuid4().hex[:8].upper()}',
        person_type=OnboardingRequest.PersonType.EMPLOYEE_FULLTIME,
        current_state=OnboardingRequest.WorkflowState.DRAFT
    )


@pytest.fixture
def conversation_session(db, test_user):
    """Create conversation session for AI interactions"""
    return ConversationSession.objects.create(
        session_id=uuid.uuid4(),
        user=test_user,
        conversation_type='ONBOARDING',
        status='ACTIVE'
    )


@pytest.mark.django_db
class TestCrossContextIntegration:
    """Integration tests for bounded contexts working together"""

    def test_client_creation_with_observations(self, test_client, test_user):
        """Test creating client with text observation and no media"""
        # Create text-only observation
        observation = OnboardingObservation.objects.create(
            context_type='CLIENT',
            context_object_id=test_client.bucode,
            text_input='Client has modern office space with good lighting. '
                       'Reception area is professional.',
            created_by=test_user,
            severity='INFO',
            confidence_score=0.85
        )

        # Validate
        assert observation.context_type == 'CLIENT'
        assert observation.context_object_id == test_client.bucode
        assert observation.text_input != ''
        assert observation.audio_file.name == ''  # No voice
        assert not observation.has_media()
        assert observation.media_count() == 0

    def test_site_with_single_photo_observation(self, test_site, test_user):
        """Test site observation with text + 1 photo"""
        # Create photo media
        photo_file = SimpleUploadedFile(
            "entrance.jpg",
            b"fake image content",
            content_type="image/jpeg"
        )

        media = OnboardingMedia.objects.create(
            context_type='SITE',
            context_object_id=str(test_site.uuid),
            media_type='PHOTO',
            file=photo_file,
            gps_latitude=12.9716,
            gps_longitude=77.5946,
            gps_accuracy=5.0,
            compass_direction=90.0,
            text_description='Main entrance gate',
            uploaded_by=test_user
        )

        # Create observation linked to media
        observation = OnboardingObservation.objects.create(
            context_type='SITE',
            context_object_id=str(test_site.uuid),
            text_input='Main entrance has automated gate with CCTV coverage.',
            created_by=test_user,
            severity='INFO'
        )
        observation.media.add(media)

        # Validate
        assert observation.has_media()
        assert observation.media_count() == 1
        attached_media = observation.media.first()
        assert attached_media.media_type == 'PHOTO'
        assert attached_media.gps_latitude == 12.9716
        assert attached_media.compass_direction == 90.0

    def test_site_with_multiple_photos(self, test_site, test_user):
        """Test site observation with text + N photos (3)"""
        # Create 3 photos
        photos = []
        for i in range(3):
            photo_file = SimpleUploadedFile(
                f"zone_{i}.jpg",
                b"fake image content",
                content_type="image/jpeg"
            )

            media = OnboardingMedia.objects.create(
                context_type='SITE',
                context_object_id=str(test_site.uuid),
                media_type='PHOTO',
                file=photo_file,
                gps_latitude=12.9716 + (i * 0.001),
                gps_longitude=77.5946 + (i * 0.001),
                text_description=f'Zone {i+1} coverage',
                uploaded_by=test_user
            )
            photos.append(media)

        # Create observation
        observation = OnboardingObservation.objects.create(
            context_type='SITE',
            context_object_id=str(test_site.uuid),
            text_input='Site has three distinct security zones with camera coverage.',
            created_by=test_user,
            severity='MEDIUM'
        )

        # Attach all photos
        observation.media.add(*photos)

        # Validate
        assert observation.media_count() == 3
        media_list = list(observation.media.all().order_by('uploaded_at'))
        assert len(media_list) == 3
        for i, media_item in enumerate(media_list):
            assert media_item.media_type == 'PHOTO'
            assert f'Zone {i+1}' in media_item.text_description

    def test_voice_only_observation(self, test_site, test_user):
        """Test voice-only observation (audio file + transcript, no media)"""
        audio_file = SimpleUploadedFile(
            "observation.mp3",
            b"fake audio content",
            content_type="audio/mpeg"
        )

        observation = OnboardingObservation.objects.create(
            context_type='SITE',
            context_object_id=str(test_site.uuid),
            audio_file=audio_file,
            original_transcript='North perimeter has fence damage at section B3.',
            created_by=test_user,
            severity='HIGH',
            confidence_score=0.92
        )

        # Validate
        assert observation.audio_file.name != ''
        assert observation.original_transcript != ''
        assert observation.text_input == ''  # No text input
        assert not observation.has_media()  # No photos/videos

    def test_voice_with_single_video(self, test_site, test_user):
        """Test voice observation + 1 video attachment"""
        # Create audio
        audio_file = SimpleUploadedFile(
            "narration.mp3",
            b"fake audio content",
            content_type="audio/mpeg"
        )

        # Create video
        video_file = SimpleUploadedFile(
            "patrol_route.mp4",
            b"fake video content",
            content_type="video/mp4"
        )

        video_media = OnboardingMedia.objects.create(
            context_type='SITE',
            context_object_id=str(test_site.uuid),
            media_type='VIDEO',
            file=video_file,
            gps_latitude=12.9716,
            gps_longitude=77.5946,
            voice_transcript='Walking the perimeter fence line.',
            uploaded_by=test_user
        )

        # Create observation
        observation = OnboardingObservation.objects.create(
            context_type='SITE',
            context_object_id=str(test_site.uuid),
            audio_file=audio_file,
            original_transcript='Perimeter patrol route video. Fence is intact.',
            created_by=test_user,
            severity='INFO'
        )
        observation.media.add(video_media)

        # Validate
        assert observation.audio_file.name != ''
        assert observation.has_media()
        assert observation.media_count() == 1
        assert observation.media.first().media_type == 'VIDEO'

    def test_voice_with_mixed_media(self, test_site, test_user):
        """Test voice + N photos + videos (2 photos + 1 video)"""
        # Create audio
        audio_file = SimpleUploadedFile(
            "site_walkthrough.mp3",
            b"fake audio content",
            content_type="audio/mpeg"
        )

        # Create 2 photos
        photos = []
        for i in range(2):
            photo_file = SimpleUploadedFile(
                f"checkpoint_{i}.jpg",
                b"fake image content",
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
            "walkthrough.mp4",
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
            original_transcript='Complete site walkthrough with checkpoints and video.',
            created_by=test_user,
            severity='MEDIUM'
        )

        # Attach all media
        observation.media.add(*photos)
        observation.media.add(video)

        # Validate
        assert observation.audio_file.name != ''
        assert observation.media_count() == 3
        media_types = [m.media_type for m in observation.media.all()]
        assert media_types.count('PHOTO') == 2
        assert media_types.count('VIDEO') == 1

    def test_worker_onboarding_with_documents(self, test_worker_request, test_user):
        """Test worker context with document media"""
        # Create document media (ID scan)
        id_doc = SimpleUploadedFile(
            "national_id.pdf",
            b"fake pdf content",
            content_type="application/pdf"
        )

        media = OnboardingMedia.objects.create(
            context_type='WORKER',
            context_object_id=str(test_worker_request.uuid),
            media_type='DOCUMENT',
            file=id_doc,
            text_description='National ID - Front and Back',
            uploaded_by=test_user
        )

        # Create observation
        observation = OnboardingObservation.objects.create(
            context_type='WORKER',
            context_object_id=str(test_worker_request.uuid),
            text_input='ID verified. Document is clear and legible.',
            created_by=test_user,
            severity='INFO'
        )
        observation.media.add(media)

        # Validate
        assert observation.context_type == 'WORKER'
        assert observation.has_media()
        assert observation.media.first().media_type == 'DOCUMENT'

    def test_conversation_linked_observations(
        self,
        test_site,
        test_user,
        conversation_session
    ):
        """Test observations linked to conversation session"""
        # Create multiple observations in a conversation
        observations = []
        for i in range(3):
            obs = OnboardingObservation.objects.create(
                context_type='SITE',
                context_object_id=str(test_site.uuid),
                conversation_session=conversation_session,
                text_input=f'Observation {i+1} during AI-guided survey.',
                created_by=test_user
            )
            observations.append(obs)

        # Validate
        assert conversation_session.observations.count() == 3
        session_obs = list(conversation_session.observations.all())
        assert len(session_obs) == 3
        for obs in session_obs:
            assert obs.conversation_session == conversation_session

    def test_entity_extraction_in_observations(self, test_site, test_user):
        """Test entity extraction storage in observations"""
        observation = OnboardingObservation.objects.create(
            context_type='SITE',
            context_object_id=str(test_site.uuid),
            text_input='CCTV camera at Gate 3 shows motion detection issues.',
            entities={
                'location': 'Gate 3',
                'asset': 'CCTV camera',
                'issue': 'motion detection failure'
            },
            created_by=test_user,
            severity='HIGH',
            confidence_score=0.88
        )

        # Validate
        assert 'location' in observation.entities
        assert observation.entities['location'] == 'Gate 3'
        assert observation.entities['asset'] == 'CCTV camera'

    def test_ai_enhancement_flow(self, test_site, test_user):
        """Test observation with AI enhancement"""
        observation = OnboardingObservation.objects.create(
            context_type='SITE',
            context_object_id=str(test_site.uuid),
            text_input='puertas tiene daños',
            english_translation='Gates have damage',
            enhanced_observation=(
                'Site security assessment: Main entrance gates show physical damage. '
                'Recommend immediate inspection and repair to maintain perimeter security.'
            ),
            created_by=test_user,
            severity='MEDIUM',
            confidence_score=0.91
        )

        # Validate
        assert observation.text_input != observation.english_translation
        assert observation.enhanced_observation != ''
        assert 'security' in observation.enhanced_observation.lower()

    def test_cross_context_media_isolation(self, test_client, test_site, test_user):
        """Test media is correctly isolated by context"""
        # Create client media
        client_media = OnboardingMedia.objects.create(
            context_type='CLIENT',
            context_object_id=test_client.bucode,
            media_type='PHOTO',
            file=SimpleUploadedFile("client.jpg", b"client", content_type="image/jpeg"),
            uploaded_by=test_user
        )

        # Create site media
        site_media = OnboardingMedia.objects.create(
            context_type='SITE',
            context_object_id=str(test_site.uuid),
            media_type='PHOTO',
            file=SimpleUploadedFile("site.jpg", b"site", content_type="image/jpeg"),
            uploaded_by=test_user
        )

        # Query by context
        client_media_qs = OnboardingMedia.objects.filter(context_type='CLIENT')
        site_media_qs = OnboardingMedia.objects.filter(context_type='SITE')

        # Validate isolation
        assert client_media_qs.count() == 1
        assert site_media_qs.count() == 1
        assert client_media_qs.first().context_object_id == test_client.bucode
        assert site_media_qs.first().context_object_id == str(test_site.uuid)

    def test_gps_metadata_capture(self, test_site, test_user):
        """Test GPS and compass metadata is captured correctly"""
        media = OnboardingMedia.objects.create(
            context_type='SITE',
            context_object_id=str(test_site.uuid),
            media_type='PHOTO',
            file=SimpleUploadedFile("gps_test.jpg", b"photo", content_type="image/jpeg"),
            gps_latitude=12.9716,
            gps_longitude=77.5946,
            gps_accuracy=3.5,
            compass_direction=135.0,  # Southeast
            uploaded_by=test_user
        )

        # Validate GPS data
        assert media.gps_latitude == 12.9716
        assert media.gps_longitude == 77.5946
        assert media.gps_accuracy == 3.5
        assert media.compass_direction == 135.0
        assert 0 <= media.compass_direction <= 360

    def test_observation_severity_levels(self, test_site, test_user):
        """Test all severity levels are properly stored"""
        severities = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO']

        for severity in severities:
            obs = OnboardingObservation.objects.create(
                context_type='SITE',
                context_object_id=str(test_site.uuid),
                text_input=f'Test observation with {severity} severity',
                severity=severity,
                created_by=test_user
            )
            assert obs.severity == severity

        # Validate count
        assert OnboardingObservation.objects.filter(
            context_type='SITE'
        ).count() == len(severities)
