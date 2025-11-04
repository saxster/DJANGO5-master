"""
Site Audit Session Management Views.

This module handles audit session lifecycle operations including session initialization,
status tracking, and progress monitoring.

Extracted from: apps/onboarding_api/views/site_audit_views.py (lines 94-339)
Refactoring Date: 2025-10-11
Part of: Phase C - God file elimination (CLAUDE.md compliance)

View Classes:
- SiteAuditStartView: Initialize new audit sessions with zones and checklists
- SiteAuditStatusView: Get current audit session status and progress

Following .claude/rules.md:
- Rule #8: View methods < 30 lines (delegate to services)
- Rule #11: Specific exception handling
- Rule #17: Transaction management with atomic()
- Rule #12: Query optimization with select_related()/prefetch_related()
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction, IntegrityError, DatabaseError
from django.db.models import Count
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.onboarding.models import (
    OnboardingSite,
    OnboardingZone,
    ConversationSession
)
from apps.client_onboarding.models.business_unit import Bt

from ...serializer_modules.site_audit_serializers import (
    SiteAuditStartSerializer,
    AuditSessionStatusSerializer
)

from apps.onboarding_api.services.multimodal_fusion import get_multimodal_fusion_service
from apps.onboarding_api.services.domain.security_banking import BankingSecurityExpertise
from apps.core.utils_new.db_utils import get_current_db_name

logger = logging.getLogger(__name__)


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
