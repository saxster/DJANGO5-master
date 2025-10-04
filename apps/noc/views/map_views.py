"""
NOC Map Views.

REST API endpoint for GeoJSON site health data visualization.
Follows .claude/rules.md Rule #8 (view methods <30 lines), Rule #12 (query optimization).
"""

import logging
from datetime import timedelta
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from apps.noc.decorators import require_noc_capability
from apps.noc.models import NOCMetricSnapshot
from apps.noc.services import NOCRBACService
from apps.attendance.services.geospatial_service import GeospatialService
from .utils import success_response, error_response, parse_filter_params

__all__ = ['NOCMapDataView']

logger = logging.getLogger('noc.views.map')


class NOCMapDataView(APIView):
    """GeoJSON site health data for map visualization."""

    permission_classes = [IsAuthenticated]

    @require_noc_capability('noc:view')
    def get(self, request):
        """Get GeoJSON formatted site health data."""
        try:
            filters = parse_filter_params(request)
            allowed_clients = NOCRBACService.get_visible_clients(request.user)

            if client_ids := filters.get('client_ids'):
                allowed_clients = allowed_clients.filter(id__in=client_ids)

            window_start = timezone.now() - timedelta(hours=1)

            snapshots = NOCMetricSnapshot.objects.filter(
                client__in=allowed_clients,
                window_end__gte=window_start,
                bu__gpslocation__isnull=False
            ).select_related('bu', 'client')

            geojson = self._build_geojson(snapshots)

            return success_response(geojson)

        except (ValueError, AttributeError) as e:
            logger.error(f"Error generating map data", extra={'error': str(e), 'user_id': request.user.id})
            return error_response("Failed to generate map data", {'detail': str(e)})

    def _build_geojson(self, snapshots):
        """Build GeoJSON FeatureCollection from snapshots."""
        features = []

        for snapshot in snapshots:
            if not snapshot.bu or not snapshot.bu.gpslocation:
                continue

            status = self._calculate_site_status(snapshot)

            # Extract coordinates using centralized service
            # GeoJSON format requires [longitude, latitude] order
            lon, lat = GeospatialService.extract_coordinates(snapshot.bu.gpslocation)

            feature = {
                'type': 'Feature',
                'geometry': {
                    'type': 'Point',
                    'coordinates': [lon, lat]
                },
                'properties': {
                    'site_id': snapshot.bu.id,
                    'site_name': snapshot.bu.buname,
                    'site_code': snapshot.bu.bucode,
                    'client_name': snapshot.client.buname,
                    'status': status,
                    'tickets_open': snapshot.tickets_open,
                    'tickets_overdue': snapshot.tickets_overdue,
                    'device_offline': snapshot.device_health_offline,
                    'attendance_ratio': f"{snapshot.attendance_present}/{snapshot.attendance_expected}",
                    'city': snapshot.city,
                    'state': snapshot.state,
                }
            }

            features.append(feature)

        return {
            'type': 'FeatureCollection',
            'features': features
        }

    def _calculate_site_status(self, snapshot):
        """Calculate overall site health status."""
        if snapshot.tickets_overdue > 5 or snapshot.device_health_offline > 10:
            return 'critical'
        elif snapshot.tickets_overdue > 0 or snapshot.tickets_open > 20:
            return 'warning'
        elif snapshot.work_orders_overdue > 0:
            return 'attention'
        else:
            return 'healthy'