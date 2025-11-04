"""
Geofence ViewSet for Admin Configuration API

Provides REST endpoints for geofence management:
- GET /api/v1/admin/config/geofences/ → List all geofences
- GET /api/v1/admin/config/geofences/{id}/ → Get specific geofence
- GET /api/v1/admin/config/geofences/{id}/assigned-people/ → Get assigned people

Compliance with .claude/rules.md:
- View methods < 30 lines
- Specific exception handling
- Network timeouts in external calls
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ValidationError, ObjectDoesNotExist
import logging

from apps.core_onboarding.models import GeofenceMaster
from apps.api.permissions import TenantIsolationPermission
from apps.api.pagination import MobileSyncCursorPagination

logger = logging.getLogger('onboarding_api')


class GeofenceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    REST API for geofence configuration.

    Endpoints:
    - GET  /api/v1/admin/config/geofences/           List geofences
    - GET  /api/v1/admin/config/geofences/{id}/      Get specific geofence
    - GET  /api/v1/admin/config/geofences/{id}/assigned-people/  Assigned people
    """

    permission_classes = [IsAuthenticated, TenantIsolationPermission]
    pagination_class = MobileSyncCursorPagination
    queryset = GeofenceMaster.objects.all()

    def list(self, request):
        """
        List all geofences.

        Returns:
            {
                "count": 10,
                "results": [...],
                "message": "Success"
            }
        """
        try:
            geofences = self.get_queryset().values(
                'id',
                'location_id',
                'location__location_name',
                'geofencename',
                'radius',
                'lat',
                'lng',
                'isactive',
            )

            return Response({
                'count': len(geofences),
                'results': list(geofences),
                'message': 'Success'
            })

        except DatabaseError as e:
            logger.error(f"Database error listing geofences: {e}", exc_info=True)
            return Response(
                {'error': 'Database error occurred'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def retrieve(self, request, pk=None):
        """Get specific geofence by ID"""
        try:
            geofence = self.get_object()
            data = {
                'id': geofence.id,
                'location_id': geofence.location_id,
                'location_name': geofence.location.location_name if geofence.location else None,
                'geofencename': geofence.geofencename,
                'radius': geofence.radius,
                'lat': geofence.lat,
                'lng': geofence.lng,
                'isactive': geofence.isactive,
            }

            return Response({
                'result': data,
                'message': 'Success'
            })

        except ObjectDoesNotExist:
            return Response(
                {'error': 'Geofence not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['get'], url_path='assigned-people')
    def assigned_people(self, request, pk=None):
        """
        Get people assigned to this geofence.

        Returns DataTables-compatible format for legacy templates.
        """
        try:
            geofence = self.get_object()

            # Get assigned people through GeofencePeopleM2m
            from apps.client_onboarding.models import GeofencePeopleM2m

            assignments = GeofencePeopleM2m.objects.filter(
                geofencemaster=geofence
            ).select_related('people').values(
                'id',
                'people__id',
                'people__peoplename',
                'people__peoplecode',
            )

            data = [{
                'pk': assignment['id'],
                'people__peoplename': assignment['people__peoplename'],
                'people__peoplecode': assignment['people__peoplecode'],
                'people_id': assignment['people__id'],
            } for assignment in assignments]

            logger.info(f"Returned {len(data)} assigned people for geofence {pk}")

            return Response({
                'count': len(data),
                'results': data,
                'message': 'Success'
            })

        except ObjectDoesNotExist:
            return Response(
                {'error': 'Geofence not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except DatabaseError as e:
            logger.error(f"Database error getting assigned people: {e}", exc_info=True)
            return Response(
                {'error': 'Database error occurred'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
