"""
Coverage & Guidance Views for Site Auditing.

This module provides RESTful API endpoints for real-time guidance, contextual questions,
and coverage tracking during site audit sessions. Extracted from site_audit_views.py
(lines 720-853, 1458-1506).

Key Features:
- Contextual question generation based on current zone
- Coverage map visualization with critical gaps
- Text-to-speech for voice guidance (optional)
- Real-time progress tracking

Following .claude/rules.md:
- Rule #8: View methods < 30 lines (delegate to services)
- Rule #11: Specific exception handling
- Rule #12: Query optimization with select_related()/prefetch_related()

Refactoring Date: 2025-10-12
Original Source: apps/onboarding_api/views/site_audit_views.py
"""

import logging
from typing import Dict, Any

from django.db.models import Count

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.onboarding.models import (
from apps.core.exceptions.patterns import NETWORK_EXCEPTIONS

    ConversationSession,
    OnboardingSite,
)

from ...serializer_modules.site_audit_serializers import (
    NextQuestionsSerializer,
    CoverageMapSerializer,
)

from ...services.domain.security_banking import BankingSecurityExpertise
from ...services.multimodal_fusion import get_multimodal_fusion_service

logger = logging.getLogger(__name__)


# ============================================================
# GUIDANCE & COVERAGE APIs
# ============================================================

class NextQuestionsView(APIView):
    """
    GET /api/v1/onboarding/site-audit/{session_id}/next-questions/

    Get contextual next questions based on coverage.

    Source: site_audit_views.py lines 724-779
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

    Source: site_audit_views.py lines 781-853
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
# UTILITY FUNCTIONS
# ============================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def speak_text(request, session_id):
    """
    POST /api/v1/onboarding/site-audit/{session_id}/speak/

    Optional TTS for voice guidance.

    Source: site_audit_views.py lines 1462-1506
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
        from ...services.tts_service import get_tts_service
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

    except NETWORK_EXCEPTIONS as e:
        logger.error(f"TTS error: {str(e)}", exc_info=True)
        return Response(
            {'error': 'Speech synthesis failed'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
