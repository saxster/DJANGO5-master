"""
Site Onboarding Service - Public API

Manages site surveys, zones, observations with multimodal capture.
"""
from typing import Dict, List
from django.db import transaction
from apps.site_onboarding.models import OnboardingSite, OnboardingZone
from apps.core_onboarding.models import ConversationSession, OnboardingObservation


class SiteService:
    """Public API for site onboarding context"""

    def create_site(
        self,
        client_id: str,
        site_type: str,
        conversation_session_id: str
    ) -> str:
        """
        Create new site for client.

        Args:
            client_id: Client UUID string (from client context)
            site_type: Site type (OFFICE, WAREHOUSE, etc.)
            conversation_session_id: Conversation UUID (REQUIRED)

        Returns:
            site_id (UUID string)
        """
        with transaction.atomic():
            # Fetch conversation session BEFORE creating site
            session = ConversationSession.objects.get(session_id=conversation_session_id)

            # Create site with required FK
            site = OnboardingSite.objects.create(
                business_unit_id=client_id,  # FK by ID
                conversation_session=session,  # Required OneToOneField
                site_type=site_type
            )

            # Link conversation to site context
            session.context_object_id = str(site.site_id)
            session.save()

            return str(site.site_id)

    def add_observation(
        self,
        site_id: str,
        zone_id: str = None,
        observation_id: str = None,
        text_input: str = None,
        audio_file=None,
        media_ids: List[str] = None
    ) -> Dict:
        """
        Add observation to site with 0-N media attachments.

        Args:
            site_id: Site UUID
            zone_id: Optional zone UUID
            observation_id: Existing observation UUID, or create new
            text_input: Text description (if not voice)
            audio_file: Audio file (if not text)
            media_ids: List of OnboardingMedia UUIDs (0 to N)

        Returns:
            Dict with observation details
        """
        from apps.core_onboarding.models import OnboardingMedia

        if observation_id:
            obs = OnboardingObservation.objects.get(observation_id=observation_id)
        else:
            # Create new observation
            obs = OnboardingObservation.objects.create(
                context_type='SITE',
                context_object_id=site_id,
                text_input=text_input or '',
                audio_file=audio_file
            )

        # Link 0-N media
        if media_ids:
            media_objects = OnboardingMedia.objects.filter(media_id__in=media_ids)
            obs.media.add(*media_objects)

        return {
            'observation_id': str(obs.observation_id),
            'media_count': obs.media_count(),
            'has_media': obs.has_media()
        }
