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
        media_ids: List[str] = None,
        user=None,
        conversation_session_id: str = None
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
            user: Authenticated user (REQUIRED for authorization)
            conversation_session_id: Conversation session for ownership validation

        Returns:
            Dict with observation details

        Raises:
            ValueError: If user is None
            PermissionDenied: If user doesn't own the site
            ValidationError: If site doesn't exist or conversation mismatch

        Security:
            - Validates site ownership via conversation session
            - Validates media ownership before linking
            - Enforces tenant isolation
        """
        from apps.core_onboarding.models import OnboardingMedia, ConversationSession
        from django.core.exceptions import PermissionDenied, ValidationError

        if not user:
            raise ValueError("User is required for observation creation")

        # ✅ VALIDATE: Site ownership via conversation session
        try:
            site = OnboardingSite.objects.select_related('conversation_session').get(
                site_id=site_id
            )

            # Check user owns the conversation session
            if site.conversation_session.user != user:
                raise PermissionDenied(
                    f"User {user.id} does not own site {site_id}"
                )

            # Optional: Validate conversation_session_id matches
            if conversation_session_id and str(site.conversation_session.session_id) != conversation_session_id:
                raise ValidationError(
                    f"Site {site_id} belongs to different conversation session"
                )

        except OnboardingSite.DoesNotExist:
            raise ValidationError(f"Site {site_id} not found")

        if observation_id:
            # ✅ VALIDATE: Observation belongs to this site and user
            try:
                obs = OnboardingObservation.objects.get(
                    observation_id=observation_id,
                    context_type='SITE',
                    context_object_id=site_id
                )
                # TODO: Add created_by field to OnboardingObservation model
                # For now, we validate via site ownership (already checked above)
            except OnboardingObservation.DoesNotExist:
                raise ValidationError(f"Observation {observation_id} not found for site {site_id}")
        else:
            # Create new observation
            obs = OnboardingObservation.objects.create(
                context_type='SITE',
                context_object_id=site_id,
                text_input=text_input or '',
                audio_file=audio_file
            )

        # ✅ VALIDATE: Media ownership before linking
        if media_ids:
            # Only allow media that exists and belongs to this site context
            media_objects = OnboardingMedia.objects.filter(
                media_id__in=media_ids,
                context_type='SITE',
                context_object_id=site_id
            )

            # Verify all media_ids were valid and owned
            if media_objects.count() != len(media_ids):
                found_ids = set(str(m.media_id) for m in media_objects)
                invalid_ids = set(media_ids) - found_ids
                raise PermissionDenied(
                    f"Media not found or not owned by user: {invalid_ids}"
                )

            obs.media.add(*media_objects)

        return {
            'observation_id': str(obs.observation_id),
            'media_count': obs.media_count(),
            'has_media': obs.has_media()
        }
