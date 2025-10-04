"""
Site Audit API Views for Phase C: Multimodal Site Security Auditing.

This module provides RESTful API endpoints for voice-first, multimodal site auditing
with real-time guidance, coverage tracking, and AI-powered analysis.

Key Features:
- Session management (start, status, progress)
- Multimodal observation capture (voice + photo + GPS)
- Real-time guidance and coverage tracking
- Zone and asset management
- Dual-LLM consensus analysis
- Multilingual SOP generation
- Comprehensive report generation

Following .claude/rules.md:
- Rule #8: View methods < 30 lines (delegate to services)
- Rule #11: Specific exception handling
- Rule #17: Transaction management with atomic()
- Rule #12: Query optimization with select_related()/prefetch_related()
"""

import logging
import uuid
import time
from decimal import Decimal
from datetime import datetime, time as datetime_time
from typing import Dict, Any, List, Optional

from django.conf import settings
from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction, IntegrityError, DatabaseError
from django.db.models import Count, Q, Prefetch
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.text import get_valid_filename

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.onboarding.models import (
    OnboardingSite,
    OnboardingZone,
    Observation,
    SitePhoto,
    Asset,
    Checkpoint,
    MeterPoint,
    SOP,
    CoveragePlan,
    ConversationSession,
    LLMRecommendation
)
from apps.onboarding.models.business_unit import Bt

from ..serializers.site_audit_serializers import (
    SiteAuditStartSerializer,
    ObservationCreateSerializer,
    ObservationSerializer,
    SitePhotoSerializer,
    ZoneSerializer,
    ZoneCreateSerializer,
    AssetCreateSerializer,
    MeterPointCreateSerializer,
    CoveragePlanSerializer,
    SOPSerializer,
    AuditAnalysisSerializer,
    ReportGenerationSerializer,
    AuditSessionStatusSerializer,
    NextQuestionsSerializer,
    CoverageMapSerializer
)

from apps.onboarding_api.services.speech_service import OnboardingSpeechService
from apps.onboarding_api.services.image_analysis import get_image_analysis_service
from apps.onboarding_api.services.ocr_service import get_ocr_service
from apps.onboarding_api.services.multimodal_fusion import get_multimodal_fusion_service
from apps.onboarding_api.services.site_coverage import get_coverage_planner_service
from apps.onboarding_api.services.sop_generator import SOPGeneratorService
from apps.onboarding_api.services.reporting import get_reporting_service
from apps.onboarding_api.services.llm import get_llm_service, get_checker_service, get_consensus_engine
from apps.onboarding_api.services.knowledge import get_knowledge_service
from apps.onboarding_api.services.domain.security_banking import BankingSecurityExpertise
from apps.onboarding_api.services.upload_throttling import get_upload_throttling_service
from apps.core.utils_new.db_utils import get_current_db_name

logger = logging.getLogger(__name__)


# ============================================================
# SESSION MANAGEMENT APIs
# ============================================================

class SiteAuditStartView(APIView):
    """
    POST /api/v1/onboarding/site-audit/start/

    Initialize a new site audit session with zones and checklist.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Start new site audit session."""
        serializer = SiteAuditStartSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = self._create_audit_session(
                serializer.validated_data,
                request.user
            )
            return Response(result, status=status.HTTP_201_CREATED)

        except (ValueError, DjangoValidationError) as e:
            logger.error(f"Validation error starting audit: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error starting audit: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Failed to create audit session'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _create_audit_session(self, data: Dict[str, Any], user) -> Dict[str, Any]:
        """Create audit session with transaction management."""
        with transaction.atomic(using=get_current_db_name()):
            # Get business unit
            business_unit = get_object_or_404(
                Bt,
                buuid=data['business_unit_id']
            )

            # Create conversation session
            conversation_session = ConversationSession.objects.create(
                user=user,
                client=business_unit,
                language=data.get('language', 'en'),
                conversation_type=ConversationSession.ConversationTypeChoices.INITIAL_SETUP,
                current_state=ConversationSession.StateChoices.IN_PROGRESS
            )

            # Create onboarding site
            site_data = {
                'business_unit': business_unit,
                'conversation_session': conversation_session,
                'site_type': data['site_type'],
                'language': data.get('language', 'en')
            }

            # Add operating hours if provided
            if 'operating_hours' in data:
                site_data['operating_hours_start'] = datetime.strptime(
                    data['operating_hours']['start'],
                    '%H:%M'
                ).time()
                site_data['operating_hours_end'] = datetime.strptime(
                    data['operating_hours']['end'],
                    '%H:%M'
                ).time()

            # Add GPS location if provided
            if 'gps_location' in data:
                site_data['primary_gps'] = Point(
                    data['gps_location']['longitude'],
                    data['gps_location']['latitude'],
                    srid=4326
                )

            onboarding_site = OnboardingSite.objects.create(**site_data)

            # Generate zones and checklist
            zones_data = self._generate_zones(onboarding_site)
            checklist = self._generate_checklist(onboarding_site)
            route = self._calculate_optimal_route(zones_data)

            logger.info(
                f"Audit session started: site={onboarding_site.site_id}, "
                f"zones={len(zones_data)}, user={user.loginid}"
            )

            return {
                'audit_session_id': str(conversation_session.session_id),
                'site_id': str(onboarding_site.site_id),
                'checklist': checklist,
                'zones': zones_data,
                'suggested_route': route,
                'estimated_duration_minutes': self._estimate_duration(len(zones_data))
            }

    def _generate_zones(self, site: OnboardingSite) -> List[Dict]:
        """Generate default zones based on site type."""
        domain_expertise = BankingSecurityExpertise()
        zone_templates = domain_expertise.get_zone_templates(site.site_type)

        zones_data = []
        for template in zone_templates:
            zone = OnboardingZone.objects.create(
                site=site,
                zone_type=template['zone_type'],
                zone_name=template['zone_name'],
                importance_level=template['importance_level'],
                risk_level=template.get('risk_level', 'moderate'),
                coverage_required=template.get('coverage_required', True),
                compliance_notes=template.get('compliance_notes', '')
            )
            zones_data.append({
                'zone_id': str(zone.zone_id),
                'zone_name': zone.zone_name,
                'zone_type': zone.zone_type,
                'importance_level': zone.importance_level
            })

        return zones_data

    def _generate_checklist(self, site: OnboardingSite) -> List[Dict]:
        """Generate audit checklist."""
        domain_expertise = BankingSecurityExpertise()
        return domain_expertise.get_audit_checklist(site.site_type)

    def _calculate_optimal_route(self, zones: List[Dict]) -> List[Dict]:
        """Calculate optimal audit route prioritizing critical zones."""
        # Sort by importance: critical → high → medium → low
        importance_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        sorted_zones = sorted(
            zones,
            key=lambda z: importance_order.get(z.get('importance_level', 'medium'), 2)
        )

        return [
            {
                'order': idx + 1,
                'zone_id': z['zone_id'],
                'zone_name': z['zone_name'],
                'estimated_minutes': 5
            }
            for idx, z in enumerate(sorted_zones)
        ]

    def _estimate_duration(self, zone_count: int) -> int:
        """Estimate audit duration in minutes."""
        return zone_count * 5 + 15  # 5 min per zone + 15 min setup


class SiteAuditStatusView(APIView):
    """
    GET /api/v1/onboarding/site-audit/{session_id}/status/

    Get current audit session status and progress.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        """Get audit session status."""
        try:
            session = self._get_session_with_details(session_id, request.user)
            status_data = self._calculate_status(session)

            serializer = AuditSessionStatusSerializer(data=status_data)
            serializer.is_valid(raise_exception=True)

            return Response(serializer.validated_data)

        except ConversationSession.DoesNotExist:
            return Response(
                {'error': 'Audit session not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error getting audit status: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Failed to get audit status'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _get_session_with_details(self, session_id: str, user):
        """Get session with related data optimized."""
        return ConversationSession.objects.select_related(
            'onboarding_site',
            'onboarding_site__business_unit'
        ).prefetch_related(
            'onboarding_site__zones',
            'onboarding_site__observations'
        ).get(
            session_id=session_id,
            user=user
        )

    def _calculate_status(self, session: ConversationSession) -> Dict[str, Any]:
        """Calculate comprehensive audit status."""
        site = session.onboarding_site

        # Get coverage stats
        fusion_service = get_multimodal_fusion_service()
        coverage = fusion_service.track_coverage(site)

        # Find current zone (last observation)
        last_observation = site.observations.select_related('zone').order_by('-cdtz').first()
        current_zone = last_observation.zone.zone_name if last_observation and last_observation.zone else None

        # Calculate next recommended zone
        next_zone = self._recommend_next_zone(site)

        return {
            'state': session.current_state,
            'progress_percentage': coverage['coverage_percentage'],
            'coverage': {
                'total_zones': coverage['total_zones'],
                'visited_zones': coverage['zones_visited'],
                'critical_gaps': coverage['critical_gaps']
            },
            'current_zone': current_zone,
            'next_recommended_zone': next_zone,
            'observations_count': site.observations.count(),
            'estimated_completion_minutes': self._estimate_remaining_time(coverage)
        }

    def _recommend_next_zone(self, site: OnboardingSite) -> Optional[str]:
        """Recommend next zone to visit."""
        unvisited_zones = site.zones.annotate(
            obs_count=Count('observations')
        ).filter(obs_count=0).order_by('-importance_level')

        if unvisited_zones.exists():
            return unvisited_zones.first().zone_name
        return None

    def _estimate_remaining_time(self, coverage: Dict) -> int:
        """Estimate remaining audit time in minutes."""
        remaining_zones = coverage['total_zones'] - coverage['zones_visited']
        return remaining_zones * 5


# ============================================================
# OBSERVATION CAPTURE APIs
# ============================================================

class ObservationCaptureView(APIView):
    """
    POST /api/v1/onboarding/site-audit/{session_id}/observation/

    Capture multimodal observation (voice + photo + GPS).
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


# ============================================================
# GUIDANCE & COVERAGE APIs
# ============================================================

class NextQuestionsView(APIView):
    """
    GET /api/v1/onboarding/site-audit/{session_id}/next-questions/

    Get contextual next questions based on coverage.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        """Get next recommended questions."""
        try:
            session = ConversationSession.objects.select_related(
                'onboarding_site'
            ).prefetch_related(
                'onboarding_site__zones',
                'onboarding_site__observations'
            ).get(session_id=session_id, user=request.user)

            questions_data = self._generate_questions(session.onboarding_site)

            serializer = NextQuestionsSerializer(data=questions_data)
            serializer.is_valid(raise_exception=True)

            return Response(serializer.validated_data)

        except ConversationSession.DoesNotExist:
            return Response(
                {'error': 'Audit session not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    def _generate_questions(self, site: OnboardingSite) -> Dict[str, Any]:
        """Generate contextual questions."""
        domain_service = BankingSecurityExpertise()
        fusion_service = get_multimodal_fusion_service()

        # Get coverage stats
        coverage = fusion_service.track_coverage(site)

        # Get current zone (last observation)
        last_obs = site.observations.select_related('zone').order_by('-cdtz').first()
        current_zone = last_obs.zone if last_obs and last_obs.zone else None

        # Generate questions
        if current_zone:
            questions = domain_service.get_zone_questions(current_zone.zone_type)
        else:
            questions = domain_service.get_general_questions()

        return {
            'current_zone': current_zone.zone_name if current_zone else None,
            'questions': questions,
            'completion_percentage': coverage['coverage_percentage'],
            'critical_gaps': coverage['critical_gaps']
        }


class CoverageMapView(APIView):
    """
    GET /api/v1/onboarding/site-audit/{session_id}/coverage/

    Get coverage map with gaps visualization.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        """Get coverage map."""
        try:
            session = ConversationSession.objects.select_related(
                'onboarding_site'
            ).get(session_id=session_id, user=request.user)

            coverage_data = self._build_coverage_map(session.onboarding_site)

            serializer = CoverageMapSerializer(data=coverage_data)
            serializer.is_valid(raise_exception=True)

            return Response(serializer.validated_data)

        except ConversationSession.DoesNotExist:
            return Response(
                {'error': 'Audit session not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    def _build_coverage_map(self, site: OnboardingSite) -> Dict[str, Any]:
        """Build comprehensive coverage map."""
        fusion_service = get_multimodal_fusion_service()
        coverage = fusion_service.track_coverage(site)

        # Get zones with counts
        zones = site.zones.annotate(
            observations_count=Count('observations'),
            photos_count=Count('photos')
        ).order_by('-importance_level')

        zones_data = []
        critical_gaps = []

        for zone in zones:
            zone_data = {
                'zone_id': str(zone.zone_id),
                'zone_name': zone.zone_name,
                'zone_type': zone.zone_type,
                'importance': zone.importance_level,
                'observations_count': zone.observations_count,
                'photos_count': zone.photos_count,
                'status': 'complete' if zone.observations_count > 0 else 'pending'
            }
            zones_data.append(zone_data)

            # Track critical gaps
            if zone.importance_level == 'critical' and zone.observations_count == 0:
                critical_gaps.append({
                    'zone_name': zone.zone_name,
                    'importance': zone.importance_level,
                    'reason': 'No observations recorded',
                    'urgency': 'high'
                })

        return {
            'coverage_map': {
                'total_zones': coverage['total_zones'],
                'visited': coverage['zones_visited'],
                'percentage': float(coverage['coverage_percentage'])
            },
            'zones': zones_data,
            'critical_gaps': critical_gaps
        }


# ============================================================
# ZONE & ASSET MANAGEMENT APIs
# ============================================================

class ZoneManagementView(APIView):
    """
    POST /api/v1/onboarding/site/{site_id}/zones/

    Create/update zones for a site.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, site_id):
        """Create multiple zones."""
        serializer = ZoneCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            zones = self._create_zones(site_id, serializer.validated_data, request.user)
            return Response({
                'zones_created': len(zones),
                'zones': ZoneSerializer(zones, many=True).data
            }, status=status.HTTP_201_CREATED)

        except OnboardingSite.DoesNotExist:
            return Response(
                {'error': 'Site not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except (ValueError, IntegrityError) as e:
            logger.error(f"Error creating zones: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def _create_zones(self, site_id: str, data: Dict, user) -> List[OnboardingZone]:
        """Create zones with transaction."""
        with transaction.atomic(using=get_current_db_name()):
            site = OnboardingSite.objects.get(site_id=site_id)

            zones = []
            for zone_data in data['zones']:
                # Parse GPS if provided
                gps = None
                if 'gps_coordinates' in zone_data:
                    gps = Point(
                        zone_data['gps_coordinates']['longitude'],
                        zone_data['gps_coordinates']['latitude'],
                        srid=4326
                    )

                zone = OnboardingZone.objects.create(
                    site=site,
                    zone_type=zone_data['zone_type'],
                    zone_name=zone_data['zone_name'],
                    importance_level=zone_data['importance_level'],
                    risk_level=zone_data.get('risk_level', 'moderate'),
                    gps_coordinates=gps,
                    coverage_required=zone_data.get('coverage_required', True),
                    compliance_notes=zone_data.get('compliance_notes', '')
                )
                zones.append(zone)

            logger.info(f"Created {len(zones)} zones for site {site_id}")
            return zones


class AssetManagementView(APIView):
    """
    POST /api/v1/onboarding/site/{site_id}/assets/

    Register assets for a site.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, site_id):
        """Create multiple assets."""
        serializer = AssetCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            assets = self._create_assets(site_id, serializer.validated_data)
            return Response({
                'assets_created': len(assets),
                'message': 'Assets registered successfully'
            }, status=status.HTTP_201_CREATED)

        except OnboardingSite.DoesNotExist:
            return Response(
                {'error': 'Site not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except OnboardingZone.DoesNotExist:
            return Response(
                {'error': 'Zone not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except (ValueError, IntegrityError) as e:
            logger.error(f"Error creating assets: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def _create_assets(self, site_id: str, data: Dict) -> List[Asset]:
        """Create assets with transaction."""
        with transaction.atomic(using=get_current_db_name()):
            site = OnboardingSite.objects.get(site_id=site_id)

            assets = []
            for asset_data in data['assets']:
                zone = OnboardingZone.objects.get(
                    zone_id=asset_data['zone_id'],
                    site=site
                )

                asset = Asset.objects.create(
                    zone=zone,
                    asset_type=asset_data['asset_type'],
                    asset_name=asset_data['asset_name'],
                    status=asset_data['status'],
                    specifications=asset_data.get('specifications', {}),
                    linked_photos=asset_data.get('linked_photos', [])
                )
                assets.append(asset)

            logger.info(f"Created {len(assets)} assets for site {site_id}")
            return assets


class MeterPointManagementView(APIView):
    """
    POST /api/v1/onboarding/site/{site_id}/meter-points/

    Add meter reading points.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, site_id):
        """Create multiple meter points."""
        serializer = MeterPointCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            meters = self._create_meter_points(site_id, serializer.validated_data)
            return Response({
                'meter_points_created': len(meters),
                'message': 'Meter points registered successfully'
            }, status=status.HTTP_201_CREATED)

        except (OnboardingSite.DoesNotExist, OnboardingZone.DoesNotExist):
            return Response(
                {'error': 'Site or zone not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except (ValueError, IntegrityError) as e:
            logger.error(f"Error creating meter points: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def _create_meter_points(self, site_id: str, data: Dict) -> List[MeterPoint]:
        """Create meter points with transaction."""
        with transaction.atomic(using=get_current_db_name()):
            site = OnboardingSite.objects.get(site_id=site_id)

            meters = []
            for meter_data in data['meter_points']:
                zone = OnboardingZone.objects.get(
                    zone_id=meter_data['zone_id'],
                    site=site
                )

                meter = MeterPoint.objects.create(
                    zone=zone,
                    meter_type=meter_data['meter_type'],
                    meter_name=meter_data['meter_name'],
                    reading_frequency=meter_data['reading_frequency'],
                    reading_template=meter_data.get('reading_template', {}),
                    requires_photo_ocr=meter_data.get('requires_photo_ocr', True),
                    sop_instructions=meter_data.get('sop_instructions', '')
                )
                meters.append(meter)

            logger.info(f"Created {len(meters)} meter points for site {site_id}")
            return meters


# ============================================================
# ANALYSIS & PLANNING APIs
# ============================================================

class AuditAnalysisView(APIView):
    """
    POST /api/v1/onboarding/site-audit/{session_id}/analyze/

    Trigger dual-LLM consensus analysis.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        """Trigger comprehensive audit analysis."""
        serializer = AuditAnalysisSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Check if should run async (long-running task)
            if self._should_run_async(session_id):
                task_result = self._enqueue_analysis_task(
                    session_id,
                    serializer.validated_data,
                    request.user
                )
                return Response(task_result, status=status.HTTP_202_ACCEPTED)
            else:
                result = self._run_analysis_sync(
                    session_id,
                    serializer.validated_data,
                    request.user
                )
                return Response(result)

        except ConversationSession.DoesNotExist:
            return Response(
                {'error': 'Audit session not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Analysis failed: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Analysis failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _should_run_async(self, session_id: str) -> bool:
        """Determine if analysis should run async."""
        session = ConversationSession.objects.get(session_id=session_id)
        observation_count = session.onboarding_site.observations.count()
        return observation_count > 10  # Async for >10 observations

    def _run_analysis_sync(
        self,
        session_id: str,
        config: Dict,
        user
    ) -> Dict[str, Any]:
        """Run analysis synchronously."""
        start_time = time.time()

        with transaction.atomic(using=get_current_db_name()):
            session = ConversationSession.objects.select_related(
                'onboarding_site'
            ).get(session_id=session_id, user=user)

            site = session.onboarding_site

            # Aggregate observations
            observations = site.observations.select_related('zone').all()
            aggregated_data = self._aggregate_observations(observations)

            # Retrieve knowledge for grounding
            knowledge_service = get_knowledge_service()
            knowledge_hits = knowledge_service.retrieve_grounded_context(
                query=aggregated_data['summary'],
                top_k=5,
                authority_filter=['high', 'official']
            )

            # Maker LLM
            llm_service = get_llm_service()
            maker_output = llm_service.analyze_site_audit(
                observations=aggregated_data,
                site_type=site.site_type
            )

            # Checker LLM
            checker_service = get_checker_service()
            checker_output = checker_service.validate_site_audit_analysis(
                maker_output=maker_output,
                knowledge_hits=knowledge_hits
            )

            # Consensus
            consensus_engine = get_consensus_engine()
            consensus = consensus_engine.create_consensus(
                maker_output=maker_output,
                checker_output=checker_output,
                knowledge_hits=knowledge_hits,
                context={'site_type': site.site_type}
            )

            # Store recommendation
            processing_time = int((time.time() - start_time) * 1000)
            recommendation = LLMRecommendation.objects.create(
                session=session,
                maker_output=maker_output,
                checker_output=checker_output,
                consensus=consensus,
                authoritative_sources=knowledge_hits,
                confidence_score=consensus.get('consensus_confidence', 0.0),
                status=LLMRecommendation.StatusChoices.VALIDATED,
                latency_ms=processing_time,
                trace_id=str(uuid.uuid4())
            )

            # Generate SOPs if requested
            sops = []
            if config.get('include_sops', True):
                sops = self._generate_sops(site, config.get('target_languages', []))

            # Generate coverage plan if requested
            coverage_plan = None
            if config.get('include_coverage_plan', True):
                coverage_plan = self._generate_coverage_plan(site)

            logger.info(f"Analysis complete for session {session_id}")

            return {
                'analysis_id': str(recommendation.recommendation_id),
                'maker_output': maker_output,
                'checker_output': checker_output,
                'consensus': consensus,
                'citations': knowledge_hits[:3],
                'processing_time_ms': processing_time,
                'trace_id': recommendation.trace_id,
                'sops_generated': len(sops),
                'coverage_plan_generated': coverage_plan is not None
            }

    def _aggregate_observations(self, observations) -> Dict[str, Any]:
        """Aggregate all observations into analysis input."""
        all_transcripts = []
        all_entities = []
        risk_summary = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}

        for obs in observations:
            if obs.transcript_english:
                all_transcripts.append(obs.transcript_english)
            if obs.entities:
                all_entities.extend(obs.entities)
            if obs.severity:
                risk_summary[obs.severity] = risk_summary.get(obs.severity, 0) + 1

        return {
            'summary': ' '.join(all_transcripts),
            'entities': all_entities,
            'risk_summary': risk_summary,
            'total_observations': observations.count()
        }

    def _generate_sops(self, site: OnboardingSite, target_languages: List[str]) -> List[SOP]:
        """Generate SOPs for all zones."""
        sop_service = SOPGeneratorService()
        sops = []

        for zone in site.zones.all():
            observations = zone.observations.all()
            if observations.exists():
                sop_data = sop_service.generate_zone_sop(
                    zone=zone,
                    observations=[],  # Already in DB
                    target_languages=target_languages
                )

                sop = SOP.objects.create(
                    site=site,
                    zone=zone,
                    sop_title=sop_data['sop_title'],
                    purpose=sop_data['purpose'],
                    steps=sop_data['steps'],
                    staffing_required=sop_data['staffing_required'],
                    compliance_references=sop_data['compliance_references'],
                    frequency=sop_data['frequency'],
                    translated_texts=sop_data.get('translated_texts', {}),
                    escalation_triggers=sop_data.get('escalation_triggers', []),
                    llm_generated=True
                )
                sops.append(sop)

        return sops

    def _generate_coverage_plan(self, site: OnboardingSite) -> CoveragePlan:
        """Generate guard coverage plan."""
        coverage_service = get_coverage_planner_service()
        plan_data = coverage_service.calculate_coverage_plan(site)

        coverage_plan = CoveragePlan.objects.create(
            site=site,
            guard_posts=plan_data['guard_posts'],
            shift_assignments=plan_data['shift_assignments'],
            patrol_routes=plan_data['patrol_routes'],
            risk_windows=plan_data['risk_windows'],
            compliance_notes=plan_data['compliance_notes'],
            generated_by='ai'
        )

        return coverage_plan

    def _enqueue_analysis_task(self, session_id: str, config: Dict, user):
        """Enqueue async analysis task."""
        task_id = str(uuid.uuid4())
        # Import background task
        from background_tasks.onboarding_tasks_phase2 import process_site_audit_analysis

        process_site_audit_analysis.delay(
            str(session_id),
            config,
            task_id,
            user.id
        )

        return {
            'status': 'processing',
            'task_id': task_id,
            'status_url': f'/api/v1/onboarding/tasks/{task_id}/status/',
            'estimated_completion': '30-90 seconds'
        }


class CoveragePlanView(APIView):
    """
    GET /api/v1/onboarding/site-audit/{session_id}/coverage-plan/

    Get guard coverage and shift plan.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        """Get coverage plan."""
        try:
            session = ConversationSession.objects.select_related(
                'onboarding_site',
                'onboarding_site__coverage_plan'
            ).get(session_id=session_id, user=request.user)

            if not hasattr(session.onboarding_site, 'coverage_plan'):
                return Response(
                    {'error': 'Coverage plan not yet generated. Run analysis first.'},
                    status=status.HTTP_404_NOT_FOUND
                )

            serializer = CoveragePlanSerializer(session.onboarding_site.coverage_plan)
            return Response(serializer.data)

        except ConversationSession.DoesNotExist:
            return Response(
                {'error': 'Audit session not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class SOPListView(APIView):
    """
    GET /api/v1/onboarding/site-audit/{session_id}/sops/

    Get generated SOPs with optional filtering.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        """List SOPs."""
        try:
            session = ConversationSession.objects.select_related(
                'onboarding_site'
            ).get(session_id=session_id, user=request.user)

            sops = self._get_filtered_sops(session.onboarding_site, request.query_params)
            serializer = SOPSerializer(sops, many=True)

            return Response({
                'count': sops.count(),
                'sops': serializer.data
            })

        except ConversationSession.DoesNotExist:
            return Response(
                {'error': 'Audit session not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    def _get_filtered_sops(self, site: OnboardingSite, params):
        """Filter SOPs based on query params."""
        sops = site.sops.select_related('zone', 'asset').all()

        if 'zone_id' in params:
            sops = sops.filter(zone__zone_id=params['zone_id'])

        if 'language' in params:
            # Filter is for display purposes - all SOPs have translations
            pass

        return sops


# ============================================================
# REPORTING APIs
# ============================================================

class AuditReportView(APIView):
    """
    GET /api/v1/onboarding/site-audit/{session_id}/report/

    Generate comprehensive audit report.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        """Generate audit report."""
        serializer = ReportGenerationSerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            report_data = self._generate_report(
                session_id,
                serializer.validated_data,
                request.user
            )
            return Response(report_data)

        except ConversationSession.DoesNotExist:
            return Response(
                {'error': 'Audit session not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Report generation failed: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Report generation failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _generate_report(
        self,
        session_id: str,
        config: Dict,
        user
    ) -> Dict[str, Any]:
        """Generate comprehensive report."""
        with transaction.atomic(using=get_current_db_name()):
            session = ConversationSession.objects.select_related(
                'onboarding_site'
            ).prefetch_related(
                'onboarding_site__zones',
                'onboarding_site__observations',
                'onboarding_site__sops',
                'onboarding_site__photos'
            ).get(session_id=session_id, user=user)

            site = session.onboarding_site

            # Generate report
            reporting_service = get_reporting_service()
            report_result = reporting_service.generate_site_audit_report(
                site=site,
                language=config.get('lang', 'en'),
                format=config.get('format', 'html'),
                include_photos=config.get('include_photos', True),
                include_sops=config.get('include_sops', True),
                include_coverage_plan=config.get('include_coverage_plan', True)
            )

            # Save to knowledge base if requested
            knowledge_id = None
            if config.get('save_to_kb', True):
                knowledge_service = get_knowledge_service()
                knowledge_id = knowledge_service.add_document_with_chunking(
                    source_org=site.business_unit.buname,
                    title=f"Site Audit Report - {site.business_unit.buname}",
                    content_summary=report_result.get('summary', ''),
                    full_content=report_result.get('report_html', ''),
                    authority_level='medium',
                    tags={'site_type': site.site_type, 'audit_date': str(timezone.now().date())}
                )

                # Update site with knowledge ID
                site.knowledge_base_id = knowledge_id
                site.report_generated_at = timezone.now()
                site.save()

            logger.info(f"Report generated for session {session_id}, KB ID: {knowledge_id}")

            return {
                'report_html': report_result.get('report_html', ''),
                'report_url': report_result.get('report_url'),
                'knowledge_id': str(knowledge_id) if knowledge_id else None,
                'summary': {
                    'total_zones': site.zones.count(),
                    'observations': site.observations.count(),
                    'compliance_score': report_result.get('compliance_score', 0.0),
                    'critical_issues': report_result.get('critical_issues', 0),
                    'recommendations': report_result.get('recommendations_count', 0)
                },
                'generated_at': timezone.now().isoformat()
            }


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def speak_text(request, session_id):
    """
    POST /api/v1/onboarding/site-audit/{session_id}/speak/

    Optional TTS for voice guidance.
    """
    try:
        text = request.data.get('text')
        language = request.data.get('language', 'en')

        if not text:
            return Response(
                {'error': 'Text required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Use TTS service
        from apps.onboarding_api.services.tts_service import get_tts_service
        tts_service = get_tts_service()

        audio_result = tts_service.synthesize_speech(
            text=text,
            language=language
        )

        if audio_result.get('success'):
            return Response({
                'audio_url': audio_result.get('audio_url'),
                'audio_base64': audio_result.get('audio_base64'),
                'duration_seconds': audio_result.get('duration_seconds')
            })
        else:
            return Response(
                {'error': 'TTS failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    except Exception as e:
        logger.error(f"TTS error: {str(e)}", exc_info=True)
        return Response(
            {'error': 'Speech synthesis failed'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )