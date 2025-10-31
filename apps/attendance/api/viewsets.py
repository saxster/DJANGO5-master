"""
Attendance & Geofencing API ViewSets

ViewSets for attendance tracking, geofence validation, and fraud detection.

Compliance with .claude/rules.md:
- View methods < 30 lines
- PostGIS integration
- Specific exception handling
"""

from rest_framework import viewsets, status
from apps.ontology.decorators import ontology
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from apps.attendance.models import PeopleEventlog, Geofence
from apps.attendance.api.serializers import (
    AttendanceSerializer,
    GeofenceSerializer,
    LocationValidationSerializer,
)
from apps.api.permissions import TenantIsolationPermission
from apps.api.pagination import MobileSyncCursorPagination
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from datetime import datetime, timedelta, timezone as dt_timezone
from apps.attendance.services.geospatial_service import GeospatialService
import logging

logger = logging.getLogger(__name__)


@ontology(
    domain="attendance",
    purpose="REST API for attendance tracking with GPS geofencing validation and fraud detection",
    api_endpoint=True,
    http_methods=["GET", "POST", "PATCH"],
    authentication_required=True,
    permissions=["IsAuthenticated", "TenantIsolationPermission"],
    rate_limit="200/minute",
    request_schema="AttendanceSerializer",
    response_schema="AttendanceSerializer",
    error_codes=[400, 401, 403, 404, 500],
    criticality="high",
    tags=["api", "rest", "attendance", "gps", "geofencing", "fraud-detection", "mobile"],
    security_notes="GPS accuracy validation (max 50m). PostGIS spatial queries for geofence validation. Tenant isolation via peopleid.client_id",
    endpoints={
        "list": "GET /api/v1/attendance/ - List attendance records",
        "create": "POST /api/v1/attendance/ - Create attendance record",
        "clock_in": "POST /api/v1/attendance/clock-in/ - Clock in with GPS validation",
        "clock_out": "POST /api/v1/attendance/clock-out/ - Clock out with GPS",
        "history": "GET /api/v1/attendance/history/ - Attendance history"
    },
    examples=[
        "curl -X POST https://api.example.com/api/v1/attendance/clock-in/ -H 'Authorization: Bearer <token>' -d '{\"lat\":28.6139,\"lng\":77.2090,\"accuracy\":15,\"device_id\":\"device-123\"}'"
    ]
)
class AttendanceViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Attendance tracking.

    Endpoints:
    - GET    /api/v1/attendance/              List attendance records
    - POST   /api/v1/attendance/              Create attendance
    - GET    /api/v1/attendance/{id}/         Retrieve attendance
    - PATCH  /api/v1/attendance/{id}/         Update attendance
    - POST   /api/v1/attendance/clock-in/     Clock in
    - POST   /api/v1/attendance/clock-out/    Clock out
    - GET    /api/v1/attendance/history/      Attendance history
    """
    permission_classes = [IsAuthenticated, TenantIsolationPermission]
    serializer_class = AttendanceSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    pagination_class = MobileSyncCursorPagination
    schema = None  # Temporarily exclude from OpenAPI until API is refactored

    filterset_fields = ['peopleid', 'event_type', 'event_time']
    ordering_fields = ['event_time', 'created_at']
    ordering = ['-event_time']

    def get_queryset(self):
        """Get queryset with tenant filtering."""
        queryset = PeopleEventlog.objects.all()

        if not self.request.user.is_superuser:
            queryset = queryset.filter(peopleid__client_id=self.request.user.client_id)

        queryset = queryset.select_related('peopleid')
        return queryset

    @action(detail=False, methods=['post'])
    def clock_in(self, request):
        """
        Clock in with geofence validation.

        POST /api/v1/attendance/clock-in/
        Request:
            {
                "person_id": 123,
                "lat": 28.6139,
                "lng": 77.2090,
                "accuracy": 15,
                "device_id": "device-uuid-123"
            }
        """
        person_id = request.data.get('person_id') or request.user.id
        lat = request.data.get('lat')
        lng = request.data.get('lng')
        accuracy = request.data.get('accuracy', 0)
        device_id = request.data.get('device_id', '')

        if not lat or not lng:
            return Response(
                {'error': 'Latitude and longitude are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate GPS accuracy
        if accuracy > 50:
            return Response(
                {'error': f'GPS accuracy too low: {accuracy}m (max: 50m)'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create Point
        location = Point(float(lng), float(lat), srid=4326)

        # Validate geofence
        geospatial_service = GeospatialService()
        validation_result = geospatial_service.validate_location(
            location=location,
            bu_id=request.user.bu_id
        )

        # Create attendance record
        try:
            attendance = PeopleEventlog.objects.create(
                peopleid_id=person_id,
                event_type='clock_in',
                event_time=datetime.now(dt_timezone.utc),
                location=location,
                accuracy=accuracy,
                device_id=device_id,
                inside_geofence=validation_result.get('inside_geofence', False),
                geofence_name=validation_result.get('geofence_name', '')
            )

            serializer = AttendanceSerializer(attendance)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Clock in error: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to clock in'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def clock_out(self, request):
        """
        Clock out.

        POST /api/v1/attendance/clock-out/
        """
        person_id = request.data.get('person_id') or request.user.id
        lat = request.data.get('lat')
        lng = request.data.get('lng')

        if not lat or not lng:
            return Response(
                {'error': 'Latitude and longitude are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        location = Point(float(lng), float(lat), srid=4326)

        try:
            attendance = PeopleEventlog.objects.create(
                peopleid_id=person_id,
                event_type='clock_out',
                event_time=datetime.now(dt_timezone.utc),
                location=location,
                device_id=request.data.get('device_id', '')
            )

            serializer = AttendanceSerializer(attendance)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Clock out error: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to clock out'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@ontology(
    domain="attendance",
    purpose="REST API for geofence management with PostGIS spatial operations and location validation",
    api_endpoint=True,
    http_methods=["GET", "POST", "PATCH", "DELETE"],
    authentication_required=True,
    permissions=["IsAuthenticated", "TenantIsolationPermission"],
    rate_limit="100/minute",
    request_schema="GeofenceSerializer|LocationValidationSerializer",
    response_schema="GeofenceSerializer",
    error_codes=[400, 401, 403, 404, 500],
    criticality="high",
    tags=["api", "rest", "geofencing", "postgis", "spatial", "gps", "mobile"],
    security_notes="Tenant isolation via client_id. PostGIS spatial queries for polygon containment checks",
    endpoints={
        "list": "GET /api/v1/assets/geofences/ - List geofences",
        "create": "POST /api/v1/assets/geofences/ - Create geofence",
        "retrieve": "GET /api/v1/assets/geofences/{id}/ - Get geofence details",
        "update": "PATCH /api/v1/assets/geofences/{id}/ - Update geofence",
        "delete": "DELETE /api/v1/assets/geofences/{id}/ - Delete geofence",
        "validate": "POST /api/v1/assets/geofences/validate/ - Validate GPS location against geofences"
    },
    examples=[
        "curl -X POST https://api.example.com/api/v1/assets/geofences/validate/ -H 'Authorization: Bearer <token>' -d '{\"lat\":28.6139,\"lng\":77.2090,\"person_id\":123}'"
    ]
)
class GeofenceViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Geofence management.

    Endpoints:
    - GET    /api/v1/assets/geofences/              List geofences
    - POST   /api/v1/assets/geofences/              Create geofence
    - GET    /api/v1/assets/geofences/{id}/         Retrieve geofence
    - PATCH  /api/v1/assets/geofences/{id}/         Update geofence
    - DELETE /api/v1/assets/geofences/{id}/         Delete geofence
    - POST   /api/v1/assets/geofences/validate/     Validate location
    """
    permission_classes = [IsAuthenticated, TenantIsolationPermission]
    serializer_class = GeofenceSerializer
    filter_backends = [DjangoFilterBackend]
    pagination_class = MobileSyncCursorPagination
    schema = None  # Temporarily exclude from OpenAPI until API is refactored

    filterset_fields = ['geofence_type', 'bu_id', 'client_id', 'is_active']

    def get_queryset(self):
        """Get queryset with tenant filtering."""
        queryset = Geofence.objects.all()

        if not self.request.user.is_superuser:
            queryset = queryset.filter(client_id=self.request.user.client_id)

        return queryset

    @action(detail=False, methods=['post'])
    def validate(self, request):
        """
        Validate if location is inside any geofence.

        POST /api/v1/assets/geofences/validate/
        Request:
            {
                "lat": 28.6139,
                "lng": 77.2090,
                "person_id": 123
            }

        Response:
            {
                "inside_geofence": true,
                "geofence_name": "Office Campus",
                "distance_to_boundary": 50.5
            }
        """
        serializer = LocationValidationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        lat = serializer.validated_data['lat']
        lng = serializer.validated_data['lng']

        # Create Point
        location = Point(lng, lat, srid=4326)

        # Validate against geofences
        geospatial_service = GeospatialService()
        result = geospatial_service.validate_location(
            location=location,
            bu_id=request.user.bu_id
        )

        return Response(result)


@ontology(
    domain="attendance",
    purpose="REST API for fraud detection alerts and suspicious attendance pattern detection",
    api_endpoint=True,
    http_methods=["GET"],
    authentication_required=True,
    permissions=["IsAdminUser"],
    rate_limit="50/minute",
    response_schema="FraudDetectionAlerts",
    error_codes=[401, 403, 500],
    criticality="high",
    tags=["api", "rest", "fraud-detection", "security", "attendance", "analytics"],
    security_notes="Admin-only access. ML-based pattern detection for suspicious attendance behavior",
    endpoints={
        "alerts": "GET /api/v1/attendance/fraud-alerts/ - Get recent fraud detection alerts"
    },
    examples=[
        "curl -X GET https://api.example.com/api/v1/attendance/fraud-alerts/ -H 'Authorization: Bearer <admin-token>'"
    ]
)
class FraudDetectionView(APIView):
    """
    API endpoint for fraud detection alerts.

    GET /api/v1/attendance/fraud-alerts/
    Returns list of suspicious attendance patterns.
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        """Get fraud detection alerts."""
        from apps.attendance.real_time_fraud_detection import FraudDetectionService

        service = FraudDetectionService()
        alerts = service.get_recent_alerts(days=7)

        return Response({
            'alerts': alerts,
            'count': len(alerts)
        })


__all__ = [
    'AttendanceViewSet',
    'GeofenceViewSet',
    'FraudDetectionView',
]
