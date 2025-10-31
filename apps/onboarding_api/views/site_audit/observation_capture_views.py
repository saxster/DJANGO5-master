"""
Site Audit Observation Capture Views.

This module handles multimodal observation capture including voice, photo, and GPS processing
with upload throttling security controls.

Extracted from: apps/onboarding_api/views/site_audit_views.py (lines 341-718)
Refactoring Date: 2025-10-11
Part of: Phase C - God file elimination (CLAUDE.md compliance)

View Classes:
- ObservationCaptureView: Capture multimodal observations with throttling (SECURITY CRITICAL)
- ObservationListView: List and filter observations

Following .claude/rules.md:
- Rule #8: View methods < 30 lines (delegate to services)
- Rule #11: Specific exception handling
- Rule #17: Transaction management with atomic()
- Rule #12: Query optimization with select_related()/prefetch_related()
- Rule #14: Secure file upload validation (upload throttling)
"""

import logging
from decimal import Decimal
from typing import Dict, Any, List, Optional

from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction, IntegrityError, DatabaseError

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.onboarding.models import (
    OnboardingSite,
    OnboardingZone,
    Observation,
    SitePhoto,
    ConversationSession
)

from ...serializer_modules.site_audit_serializers import (
    ObservationCreateSerializer,
    ObservationSerializer
)

from apps.onboarding_api.services.speech_service import OnboardingSpeechService
from apps.onboarding_api.services.image_analysis import get_image_analysis_service
from apps.onboarding_api.services.ocr_service import get_ocr_service
from apps.onboarding_api.services.multimodal_fusion import get_multimodal_fusion_service
from apps.onboarding_api.services.domain.security_banking import BankingSecurityExpertise
from apps.onboarding_api.services.upload_throttling import get_upload_throttling_service
from apps.core.utils_new.db_utils import get_current_db_name

logger = logging.getLogger(__name__)


class ObservationCaptureView(APIView):
    """
    POST /api/v1/onboarding/site-audit/{session_id}/observation/

    Capture multimodal observation (voice + photo + GPS).

    SECURITY CRITICAL: Implements upload throttling to prevent abuse.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        """Capture observation with multimodal processing and upload throttling."""
        serializer = ObservationCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Check upload throttling for photos
            if request.FILES.get('photo') or serializer.validated_data.get('photo'):
                throttling_service = get_upload_throttling_service()

                # Get photo file
                photo_file = request.FILES.get('photo') or serializer.validated_data.get('photo')
                if hasattr(photo_file, 'size') and hasattr(photo_file, 'content_type'):
                    # Check if upload is allowed
                    allowed, error_info = throttling_service.check_upload_allowed(
                        session_id=session_id,
                        user_id=str(request.user.id),
                        upload_type='photos',
                        file_size=photo_file.size,
                        content_type=photo_file.content_type
                    )

                    if not allowed:
                        logger.warning(
                            f"Upload throttled for session {session_id}",
                            extra={'error_info': error_info, 'user_id': request.user.id}
                        )
                        return Response(
                            error_info,
                            status=status.HTTP_429_TOO_MANY_REQUESTS
                        )

            # Process observation
            result = self._process_observation(
                session_id,
                serializer.validated_data,
                request.user
            )

            # Increment upload counters on success
            if request.FILES.get('photo') or serializer.validated_data.get('photo'):
                photo_file = request.FILES.get('photo') or serializer.validated_data.get('photo')
                if hasattr(photo_file, 'size'):
                    throttling_service.increment_upload_count(
                        session_id=session_id,
                        user_id=str(request.user.id),
                        upload_type='photos',
                        file_size=photo_file.size
                    )

            return Response(result, status=status.HTTP_201_CREATED)

        except ConversationSession.DoesNotExist:
            return Response(
                {'error': 'Audit session not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except (ValueError, DjangoValidationError) as e:
            logger.error(f"Validation error in observation: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error processing observation: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Failed to process observation'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _process_observation(
        self,
        session_id: str,
        data: Dict[str, Any],
        user
    ) -> Dict[str, Any]:
        """Process multimodal observation with transaction."""
        with transaction.atomic(using=get_current_db_name()):
            # Get session and site
            session = ConversationSession.objects.select_related(
                'onboarding_site'
            ).get(session_id=session_id, user=user)

            site = session.onboarding_site

            # Process multimodal inputs
            fusion_result = self._process_multimodal_input(data, site, user)

            # Create observation record
            observation = self._create_observation(site, fusion_result, data, user)

            # Create photo record if photo provided
            if data.get('photo'):
                self._create_photo_record(site, fusion_result, data, user)

            # Generate next questions
            next_questions = self._generate_next_questions(site, fusion_result)

            logger.info(
                f"Observation captured: id={observation.observation_id}, "
                f"zone={fusion_result.get('identified_zone')}, "
                f"confidence={fusion_result['confidence_score']}"
            )

            return {
                'observation_id': str(observation.observation_id),
                'enhanced': fusion_result.get('enhanced', {}),
                'confidence': float(fusion_result['confidence_score']),
                'identified_zone': self._format_zone_details(fusion_result.get('identified_zone')),
                'next_questions': next_questions,
                'inconsistencies': fusion_result.get('inconsistencies', [])
            }

    def _process_multimodal_input(
        self,
        data: Dict[str, Any],
        site: OnboardingSite,
        user
    ) -> Dict[str, Any]:
        """Process all input modalities and fuse results."""
        voice_data = {}
        photo_data = {}

        # Process audio if provided
        if data.get('audio'):
            voice_data = self._process_audio(data['audio'], site.language)

        # Process photo if provided
        if data.get('photo'):
            photo_data = self._process_photo(data['photo'])

        # Use text input if provided
        if data.get('text_input'):
            voice_data = {
                'transcript_en': data['text_input'],
                'transcript_original': data['text_input'],
                'confidence': 1.0
            }

        # Multimodal fusion
        fusion_service = get_multimodal_fusion_service()
        fused = fusion_service.correlate_observation(
            voice_data=voice_data,
            photo_data=photo_data,
            gps_data={
                'latitude': data['gps_latitude'],
                'longitude': data['gps_longitude']
            },
            zone_hint=data.get('zone_hint'),
            site=site
        )

        # Domain enhancement if zone identified
        if fused.get('identified_zone'):
            domain_service = BankingSecurityExpertise()
            enhanced = domain_service.enhance_observation(
                fused['unified_observation'],
                fused['identified_zone'].zone_type
            )
            fused['enhanced'] = enhanced

        return fused

    def _process_audio(self, audio_file, language: str) -> Dict[str, Any]:
        """Process audio with STT and translation."""
        speech_service = OnboardingSpeechService()

        # Convert language code (ISO 639-1 to BCP-47)
        language_map = {
            'en': 'en-US',
            'hi': 'hi-IN',
            'mr': 'mr-IN',
            'ta': 'ta-IN',
            'te': 'te-IN'
        }
        language_code = language_map.get(language, 'en-US')

        # Transcribe
        result = speech_service.transcribe_voice_input(
            audio_file,
            language_code=language_code
        )

        if not result.get('success'):
            raise ValueError(f"Speech recognition failed: {result.get('error')}")

        voice_data = {
            'transcript_original': result['transcript'],
            'confidence': result['confidence']
        }

        # Translate to English if not English
        if language != 'en':
            from apps.onboarding_api.services.translation import get_conversation_translator
            translator = get_conversation_translator()
            translated = translator.translate_text(
                result['transcript'],
                source_lang=language,
                target_lang='en'
            )
            voice_data['transcript_en'] = translated
        else:
            voice_data['transcript_en'] = result['transcript']

        return voice_data

    def _process_photo(self, photo_file) -> Dict[str, Any]:
        """Process photo with Vision API and OCR."""
        image_service = get_image_analysis_service()
        ocr_service = get_ocr_service()

        # Vision API analysis
        vision_result = image_service.analyze_security_scene(photo_file)

        # OCR for text extraction
        ocr_result = ocr_service.extract_text_from_image(photo_file)

        return {
            'objects': vision_result.get('detected_objects', []),
            'security_equipment': vision_result.get('security_equipment', []),
            'safety_concerns': vision_result.get('safety_concerns', []),
            'confidence': vision_result.get('confidence', 0.0),
            'ocr_text': ocr_result.get('text', ''),
            'vision_analysis': vision_result
        }

    def _create_observation(
        self,
        site: OnboardingSite,
        fusion_result: Dict,
        data: Dict,
        user
    ) -> Observation:
        """Create observation database record."""
        unified = fusion_result['unified_observation']
        enhanced = fusion_result.get('enhanced', {})

        observation = Observation.objects.create(
            site=site,
            zone=fusion_result.get('identified_zone'),
            transcript_original=unified.get('transcript_original', ''),
            transcript_english=unified.get('transcript', ''),
            enhanced_observation=enhanced,
            entities=enhanced.get('entities', []) if enhanced else [],
            severity=enhanced.get('risk_level', 'info') if enhanced else 'info',
            confidence_score=fusion_result['confidence_score'],
            gps_at_capture=Point(
                data['gps_longitude'],
                data['gps_latitude'],
                srid=4326
            ),
            media_links=[],
            captured_by=user
        )

        return observation

    def _create_photo_record(
        self,
        site: OnboardingSite,
        fusion_result: Dict,
        data: Dict,
        user
    ) -> SitePhoto:
        """Create photo database record."""
        photo_data = fusion_result.get('unified_observation', {})

        site_photo = SitePhoto.objects.create(
            site=site,
            zone=fusion_result.get('identified_zone'),
            image=data['photo'],
            gps_coordinates=Point(
                data['gps_longitude'],
                data['gps_latitude'],
                srid=4326
            ),
            compass_direction=Decimal(str(data['compass_direction'])) if data.get('compass_direction') else None,
            vision_analysis=photo_data.get('vision_analysis', {}),
            detected_objects=photo_data.get('detected_objects', []),
            safety_concerns=photo_data.get('safety_concerns', []),
            uploaded_by=user
        )

        return site_photo

    def _generate_next_questions(
        self,
        site: OnboardingSite,
        fusion_result: Dict
    ) -> List[Dict]:
        """Generate contextual next questions."""
        domain_service = BankingSecurityExpertise()

        if fusion_result.get('identified_zone'):
            return domain_service.get_zone_questions(
                fusion_result['identified_zone'].zone_type
            )

        return []

    def _format_zone_details(self, zone: Optional[OnboardingZone]) -> Optional[Dict]:
        """Format zone details for response."""
        if zone:
            return {
                'zone_id': str(zone.zone_id),
                'zone_name': zone.zone_name,
                'zone_type': zone.zone_type,
                'importance_level': zone.importance_level
            }
        return None


class ObservationListView(APIView):
    """
    GET /api/v1/onboarding/site-audit/{session_id}/observations/

    List all observations with filtering.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        """List observations with filters."""
        try:
            session = ConversationSession.objects.select_related(
                'onboarding_site'
            ).get(session_id=session_id, user=request.user)

            observations = self._get_filtered_observations(
                session.onboarding_site,
                request.query_params
            )

            serializer = ObservationSerializer(observations, many=True)
            return Response({
                'count': observations.count(),
                'observations': serializer.data
            })

        except ConversationSession.DoesNotExist:
            return Response(
                {'error': 'Audit session not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    def _get_filtered_observations(self, site: OnboardingSite, params):
        """Apply filters to observations queryset."""
        observations = site.observations.select_related(
            'zone',
            'captured_by'
        ).order_by('-cdtz')

        # Filter by zone
        if 'zone_id' in params:
            observations = observations.filter(zone__zone_id=params['zone_id'])

        # Filter by severity
        if 'severity' in params:
            observations = observations.filter(severity=params['severity'])

        # Filter by photo presence
        if params.get('has_photo') == 'true':
            observations = observations.exclude(media_links=[])

        return observations
