"""
Asset & Zone Management Views for Site Auditing.

This module provides RESTful API endpoints for managing zones, assets, and meter points
during site audit sessions. Extracted from site_audit_views.py (lines 855-1046).

Key Features:
- Zone creation and management with GPS coordinates
- Asset registration (cameras, alarms, sensors, etc.)
- Meter point setup for reading schedules
- Bulk operations with transaction management

Following .claude/rules.md:
- Rule #8: View methods < 30 lines (delegate to services)
- Rule #11: Specific exception handling
- Rule #17: Transaction management with atomic()
- Rule #12: Query optimization with select_related()/prefetch_related()

Refactoring Date: 2025-10-12
Original Source: apps/onboarding_api/views/site_audit_views.py
"""

import logging
from typing import Dict, List, Any

from django.contrib.gis.geos import Point
from django.db import transaction, IntegrityError
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.site_onboarding.models import (
    OnboardingSite,
    OnboardingZone,
    Asset,
    MeterPoint
)

from ...serializer_modules.site_audit_serializers import (
    ZoneSerializer,
    ZoneCreateSerializer,
    AssetCreateSerializer,
    MeterPointCreateSerializer,
)

from apps.core.utils_new.db_utils import get_current_db_name

logger = logging.getLogger(__name__)


# ============================================================
# ZONE & ASSET MANAGEMENT APIs
# ============================================================

class ZoneManagementView(APIView):
    """
    POST /api/v1/onboarding/site/{site_id}/zones/

    Create/update zones for a site.

    Source: site_audit_views.py lines 859-922
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

    Source: site_audit_views.py lines 924-986
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

    Source: site_audit_views.py lines 988-1046
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
