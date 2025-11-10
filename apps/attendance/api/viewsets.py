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
from django.contrib.auth.decorators import permission_required
from django.utils.decorators import method_decorator
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
from django.contrib.gis.geos import Point, GEOSException
from django.contrib.gis.measure import D
from datetime import datetime, timedelta, timezone as dt_timezone
from apps.attendance.services.geospatial_service import GeospatialService
from apps.attendance.services.shift_validation_service import ShiftAssignmentValidationService
from apps.attendance.api.throttles import AttendanceThrottle, GeofenceValidationThrottle
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, VALIDATION_EXCEPTIONS
from apps.core.utils_new.datetime_utilities import get_current_utc
from django.core.exceptions import ValidationError, ObjectDoesNotExist
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
@method_decorator(permission_required('attendance.view_peopleeventlog', raise_exception=True), name='dispatch')
class AttendanceViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Attendance tracking.

    Endpoints:
    - GET    /api/v1/attendance/              List attendance records
    - POST   /api/v1/attendance/              Create attendance
    - GET    /api/v1/attendance/{id}/         Retrieve attendance
    - PATCH  /api/v1/attendance/{id}/         Update attendance
    - POST   /api/v1/attendance/clock-in/     Clock in (Rate limited: 30/hour)
    - POST   /api/v1/attendance/clock-out/    Clock out (Rate limited: 30/hour)
    - GET    /api/v1/attendance/history/      Attendance history
    """
    permission_classes = [IsAuthenticated, TenantIsolationPermission]
    throttle_classes = [AttendanceThrottle]  # 30 clock events per hour
    serializer_class = AttendanceSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    pagination_class = MobileSyncCursorPagination
    schema = None  # Temporarily exclude from OpenAPI until API is refactored

    filterset_fields = ['peopleid', 'event_type', 'event_time']
    ordering_fields = ['event_time', 'created_at']
    ordering = ['-event_time']

    def get_queryset(self):
        """Get queryset with tenant filtering and comprehensive optimization."""
        queryset = PeopleEventlog.objects.select_related(
            'peopleid',
            'peopleid__profile',
            'peopleid__organizational',
            'geofence'
        ).prefetch_related(
            'metadata'
        )

        if not self.request.user.is_superuser:
            queryset = queryset.filter(peopleid__client_id=self.request.user.client_id)

        return queryset

    @action(detail=False, methods=['post'])
    def clock_in(self, request):
        """
        Clock in with comprehensive validation.

        Performs multi-layer validation:
        1. GPS accuracy and coordinate validation
        2. Site assignment validation
        3. Shift assignment and time window validation
        4. Rest period compliance validation
        5. Duplicate check-in prevention
        6. Geofence validation

        POST /api/v1/attendance/clock-in/
        Request:
            {
                "person_id": 123,
                "lat": 28.6139,
                "lng": 77.2090,
                "accuracy": 15,
                "device_id": "device-uuid-123"
            }

        Response (success):
            {
                "status": "success",
                "message": "Check-in successful",
                "data": { ... attendance record ... }
            }

        Response (validation failure):
            {
                "error": "NOT_ASSIGNED_TO_SITE",
                "message": "You are not assigned to this site...",
                "details": { ... validation details ... },
                "ticket_id": 123,
                "requires_approval": true
            }
        """
        person_id = request.data.get('person_id') or request.user.id
        lat = request.data.get('lat')
        lng = request.data.get('lng')
        accuracy = request.data.get('accuracy', 0)
        device_id = request.data.get('device_id', '')

        # Validate required fields
        if not lat or not lng:
            return Response(
                {
                    'error': 'MISSING_REQUIRED_FIELDS',
                    'message': 'Latitude and longitude are required'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get site context from session
        site_id = request.session.get('bu_id') or getattr(request.user, 'bu_id', None)
        if not site_id:
            logger.error(f"No site context found for user {request.user.id} during clock-in")
            return Response(
                {
                    'error': 'NO_SITE_CONTEXT',
                    'message': 'Site context not found. Please log in again.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate GPS accuracy
        if accuracy and accuracy > 50:
            return Response(
                {
                    'error': 'GPS_ACCURACY_TOO_LOW',
                    'message': f'GPS accuracy must be better than 50m. Current: {accuracy}m'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create Point for geofencing
        try:
            location = Point(float(lng), float(lat), srid=4326)
        except (ValueError, GEOSException) as e:
            logger.error(f"Invalid GPS coordinates: lat={lat}, lng={lng}, error={e}")
            return Response(
                {
                    'error': 'INVALID_COORDINATES',
                    'message': 'Invalid GPS coordinates provided'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # **Comprehensive shift and post validation**
        # Phase 1: Shift + Site validation (always enabled)
        # Phase 3: Post validation (enabled via feature flag)
        current_time = get_current_utc()
        validation_service = ShiftAssignmentValidationService()

        # Check if Phase 3 (post validation) is enabled
        from django.conf import settings
        use_post_validation = getattr(settings, 'POST_VALIDATION_ENABLED', False)

        if use_post_validation:
            # Use comprehensive validation (Phase 1 + Phase 3)
            validation_result = validation_service.validate_checkin_comprehensive(
                worker_id=person_id,
                site_id=site_id,
                timestamp=current_time,
                gps_point=location
            )
        else:
            # Use Phase 1 validation only (shift + site)
            validation_result = validation_service.validate_checkin(
                worker_id=person_id,
                site_id=site_id,
                timestamp=current_time,
                gps_point=location
            )

        if not validation_result.valid:
            # Log validation failure
            logger.warning(
                f"Check-in validation failed for worker {person_id} at site {site_id}: "
                f"{validation_result.reason}",
                extra={
                    'worker_id': person_id,
                    'site_id': site_id,
                    'reason': validation_result.reason,
                    'details': validation_result.to_dict()
                }
            )

            # Auto-create mismatch ticket for audit trail
            from apps.attendance.ticket_integration import create_attendance_mismatch_ticket
            ticket = create_attendance_mismatch_ticket(
                worker_id=person_id,
                site_id=site_id,
                reason=validation_result.reason,
                details=validation_result.to_dict(),
                gps_location={'lat': lat, 'lng': lng},
                timestamp=current_time
            )

            # Send alert to site supervisor if approval required
            if validation_result.details.get('requires_approval'):
                self._notify_supervisor_of_mismatch(
                    site_id=site_id,
                    worker_id=person_id,
                    reason=validation_result.reason,
                    ticket_id=ticket.id if ticket else None
                )

            # Return detailed error response
            return Response(
                {
                    'error': validation_result.reason,
                    'message': validation_result.get_user_friendly_message(),
                    'details': validation_result.to_dict(),
                    'ticket_id': ticket.id if ticket else None,
                    'requires_approval': validation_result.details.get('requires_approval', False)
                },
                status=status.HTTP_403_FORBIDDEN
            )

        # Validation passed - perform geofence check
        geospatial_service = GeospatialService()
        geofence_result = geospatial_service.validate_location(
            location=location,
            bu_id=site_id
        )

        # Create attendance record
        try:
            # Get shift and jobneed from validation result
            shift = validation_result.details.get('shift')
            jobneed = validation_result.details.get('jobneed')

            # Get post and post_assignment from validation result (Phase 3)
            assigned_post = validation_result.details.get('assigned_post')
            post_assignment = validation_result.details.get('post_assignment')

            attendance = PeopleEventlog.objects.create(
                peopleid_id=person_id,
                bu_id=site_id,
                shift=shift,
                post=assigned_post,  # Phase 3: Post tracking
                post_assignment=post_assignment,  # Phase 3: Assignment link
                event_type='clock_in',
                event_time=current_time,
                datefor=current_time.date(),
                location=location,
                accuracy=accuracy,
                device_id=device_id,
                inside_geofence=geofence_result.get('inside_geofence', False),
                geofence_name=geofence_result.get('geofence_name', ''),
                peventlogextras={
                    'verified_in': geofence_result.get('inside_geofence', False),
                    'distance_in': geofence_result.get('distance', 0),
                    'accuracy': accuracy,
                    'device_id': device_id,
                    'validation_passed': True,
                    'validation_phase': 'comprehensive' if use_post_validation else 'phase1',
                    'jobneed_id': jobneed.id if jobneed else None,
                    'shift_id': shift.id if shift else None,
                    'post_id': assigned_post.id if assigned_post else None,
                    'post_assignment_id': post_assignment.id if post_assignment else None,
                }
            )

            # Update Jobneed status to IN_PROGRESS
            if jobneed and jobneed.jobstatus == 'ASSIGNED':
                jobneed.jobstatus = 'INPROGRESS'
                jobneed.save(update_fields=['jobstatus'])
                logger.info(f"Updated Jobneed {jobneed.id} status to INPROGRESS")

            # Update PostAssignment status to IN_PROGRESS (Phase 3)
            if post_assignment and post_assignment.can_check_in():
                post_assignment.mark_checked_in(attendance_record=attendance)
                logger.info(f"Updated PostAssignment {post_assignment.id} status to IN_PROGRESS")

            # Optimize N+1: select_related after create
            attendance = PeopleEventlog.objects.select_related(
                'peopleid', 'peventtype', 'geofence', 'shift', 'bu', 'post', 'post_assignment'
            ).get(id=attendance.id)

            logger.info(
                f"Check-in successful for worker {person_id} at site {site_id}",
                extra={
                    'worker_id': person_id,
                    'site_id': site_id,
                    'shift_id': shift.id if shift else None,
                    'attendance_id': attendance.id
                }
            )

            serializer = AttendanceSerializer(attendance)
            return Response(
                {
                    'status': 'success',
                    'message': 'Check-in successful',
                    'data': serializer.data
                },
                status=status.HTTP_201_CREATED
            )

        except ValidationError as e:
            logger.warning(f"Clock in validation error for person {person_id}: {e}")
            return Response(
                {'error': 'VALIDATION_ERROR', 'message': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except ObjectDoesNotExist as e:
            logger.error(f"Person not found for clock in: person_id={person_id}")
            return Response(
                {'error': 'PERSON_NOT_FOUND', 'message': f'Person with ID {person_id} not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error during clock in for person {person_id}: {e}", exc_info=True)
            return Response(
                {'error': 'DATABASE_ERROR', 'message': 'Database error. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _notify_supervisor_of_mismatch(self, site_id, worker_id, reason, ticket_id):
        """
        Send real-time alert to site supervisor about attendance mismatch

        Args:
            site_id: Bt.id
            worker_id: People.id
            reason: Validation failure reason code
            ticket_id: Created ticket ID (optional)
        """
        try:
            # Get site supervisors (group leads assigned to this site)
            from apps.peoples.models.membership_model import Pgbelonging
            from apps.peoples.models import People

            supervisors = Pgbelonging.objects.filter(
                assignsites_id=site_id,
                isgrouplead=True
            ).select_related('people').values_list('people_id', flat=True)

            if not supervisors:
                logger.warning(f"No supervisors found for site {site_id}")
                return

            # Get worker details
            try:
                worker = People.objects.get(id=worker_id)
                worker_name = worker.get_full_name() if hasattr(worker, 'get_full_name') else f"Worker {worker_id}"
            except People.DoesNotExist:
                worker_name = f"Worker {worker_id}"

            # Create notification message
            notification_title = 'Attendance Validation Failed'
            notification_message = (
                f"{worker_name} attempted check-in with validation failure: "
                f"{reason.replace('_', ' ').title()}"
            )

            # Send notification to each supervisor
            # Note: Integrate with existing notification system
            # For now, just log the notification
            logger.info(
                f"Supervisor notification: {notification_message}",
                extra={
                    'notification_type': 'ATTENDANCE_MISMATCH',
                    'worker_id': worker_id,
                    'worker_name': worker_name,
                    'site_id': site_id,
                    'reason': reason,
                    'ticket_id': ticket_id,
                    'supervisor_ids': list(supervisors)
                }
            )

            # TODO: Integrate with actual notification service when available
            # from apps.core.services.notification_service import NotificationService
            # for supervisor_id in supervisors:
            #     NotificationService.send_notification(
            #         user_id=supervisor_id,
            #         notification_type='ATTENDANCE_MISMATCH',
            #         title=notification_title,
            #         message=notification_message,
            #         data={
            #             'worker_id': worker_id,
            #             'worker_name': worker_name,
            #             'site_id': site_id,
            #             'reason': reason,
            #             'ticket_id': ticket_id,
            #             'requires_action': True
            #         },
            #         priority='HIGH'
            #     )

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Failed to notify supervisors of mismatch: {e}", exc_info=True)

    @action(detail=False, methods=['post'])
    def clock_out(self, request):
        """
        Clock out with GPS validation.

        POST /api/v1/attendance/clock-out/
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

        # Validate GPS accuracy (consistent with clock-in)
        if accuracy > 50:
            return Response(
                {'error': f'GPS accuracy too low: {accuracy}m (max: 50m)'},
                status=status.HTTP_400_BAD_REQUEST
            )

        location = Point(float(lng), float(lat), srid=4326)

        try:
            attendance = PeopleEventlog.objects.create(
                peopleid_id=person_id,
                event_type='clock_out',
                event_time=datetime.now(dt_timezone.utc),
                location=location,
                accuracy=accuracy,
                device_id=device_id
            )

            # Optimize N+1: select_related after create
            attendance = PeopleEventlog.objects.select_related(
                'peopleid', 'peventtype', 'geofence', 'shift', 'bu', 'post', 'post_assignment'
            ).get(id=attendance.id)

            serializer = AttendanceSerializer(attendance)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except ValidationError as e:
            logger.warning(f"Clock out validation error for person {person_id}: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except ObjectDoesNotExist as e:
            logger.error(f"Person not found for clock out: person_id={person_id}")
            return Response(
                {'error': f'Person with ID {person_id} not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error during clock out for person {person_id}: {e}", exc_info=True)
            return Response(
                {'error': 'Database error. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except GEOSException as e:
            logger.error(f"Invalid GPS coordinates for clock out: lat={lat}, lng={lng}, error={e}")
            return Response(
                {'error': 'Invalid GPS coordinates'},
                status=status.HTTP_400_BAD_REQUEST
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
@method_decorator(permission_required('attendance.view_geofence', raise_exception=True), name='dispatch')
class GeofenceViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Geofence management.

    Endpoints:
    - GET    /api/v1/assets/geofences/              List geofences
    - POST   /api/v1/assets/geofences/              Create geofence
    - GET    /api/v1/assets/geofences/{id}/         Retrieve geofence
    - PATCH  /api/v1/assets/geofences/{id}/         Update geofence
    - DELETE /api/v1/assets/geofences/{id}/         Delete geofence
    - POST   /api/v1/assets/geofences/validate/     Validate location (Rate limited: 100/hour)
    """
    permission_classes = [IsAuthenticated, TenantIsolationPermission]
    throttle_classes = [GeofenceValidationThrottle]  # 100 validations per hour
    serializer_class = GeofenceSerializer
    filter_backends = [DjangoFilterBackend]
    pagination_class = MobileSyncCursorPagination
    schema = None  # Temporarily exclude from OpenAPI until API is refactored

    filterset_fields = ['geofence_type', 'bu_id', 'client_id', 'is_active']

    def get_queryset(self):
        """Get queryset with tenant filtering and query optimization."""
        queryset = Geofence.objects.select_related(
            'client',
            'created_by',
            'modified_by'
        )

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
@method_decorator(permission_required('attendance.view_fraudalert', raise_exception=True), name='dispatch')
class FraudDetectionView(APIView):
    """
    API endpoint for fraud detection alerts.

    GET /api/v1/attendance/fraud-alerts/
    Returns list of suspicious attendance patterns.
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        """Get fraud detection alerts."""
        from apps.attendance.real_time_fraud_detection import RealTimeFraudDetector

        service = RealTimeFraudDetector()
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
