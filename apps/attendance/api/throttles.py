"""
Attendance API Rate Limiting

Custom throttle classes for attendance endpoints to prevent abuse.

Compliance with .claude/rules.md:
- Rate limiting for all public endpoints (Rule 9)
- DoS prevention via resource exhaustion blocking

Ontology: rate_limiting=True, security=True, api_protection=True
Category: throttles, security, api
Domain: attendance_tracking, fraud_prevention
Responsibility: Rate limit attendance operations to prevent abuse
Security: Prevents GPS spam attacks, attendance fraud, DoS attacks
"""

from rest_framework.throttling import UserRateThrottle


class AttendanceThrottle(UserRateThrottle):
    """
    Rate limiter for attendance clock-in/out endpoints.

    Limits: 30 clock events per hour per user

    Ontology: rate_limiting=True, security=True
    Purpose: Prevent attendance fraud and GPS spam attacks
    Scope: user (authenticated user-specific)
    Rate: 30 requests per hour (0.5 per minute average)
    Enforcement: DRF throttling middleware

    Rationale:
    - Legitimate use case: 2 clock events per day (clock-in + clock-out)
    - Buffer: 15x normal usage allows retries and corrections
    - Attack prevention: Blocks GPS spam attacks (>30 events/hour)

    Usage:
        class AttendanceViewSet(viewsets.ModelViewSet):
            throttle_classes = [AttendanceThrottle]
    """
    rate = '30/hour'
    scope = 'attendance'


class GeofenceValidationThrottle(UserRateThrottle):
    """
    Rate limiter for geofence validation queries.

    Limits: 100 validation requests per hour per user

    Ontology: rate_limiting=True, security=True
    Purpose: Prevent geofence query abuse
    Scope: user (authenticated user-specific)
    Rate: 100 requests per hour (~1.7 per minute)
    Enforcement: DRF throttling middleware

    Rationale:
    - Legitimate use case: Periodic location checks (e.g., every 5 minutes)
    - Buffer: Allows for real-time location tracking use cases
    - Attack prevention: Blocks brute-force geofence enumeration

    Usage:
        @action(detail=False, methods=['post'])
        def validate(self, request):
            # Applied via throttle_classes
    """
    rate = '100/hour'
    scope = 'geofence_validation'


class PostManagementThrottle(UserRateThrottle):
    """
    Rate limiter for post management endpoints (Phase 2-3).

    Limits: 100 requests per hour per user

    Purpose: Prevent abuse of post CRUD operations
    Scope: Supervisors/admins creating/updating posts
    Rate: 100 requests per hour (~1.7 per minute)

    Usage:
        class PostViewSet(viewsets.ModelViewSet):
            throttle_classes = [PostManagementThrottle]
    """
    rate = '100/hour'
    scope = 'post_management'


class PostAssignmentThrottle(UserRateThrottle):
    """
    Rate limiter for post assignment endpoints (roster management).

    Limits: 200 requests per hour per user

    Purpose: Allow bulk roster operations while preventing abuse
    Scope: Supervisors creating/updating assignments
    Rate: 200 requests per hour (~3.3 per minute)

    Rationale:
    - Legitimate use: Creating assignments for 20-30 workers
    - Bulk operations: Need higher limit than single operations
    - Attack prevention: Still blocks excessive API calls
    """
    rate = '200/hour'
    scope = 'post_assignment'


class PostOrderAcknowledgementThrottle(UserRateThrottle):
    """
    Rate limiter for post order acknowledgement endpoints.

    Limits: 50 requests per hour per user

    Purpose: Prevent acknowledgement abuse/automation
    Scope: Workers acknowledging post orders
    Rate: 50 requests per hour (~0.8 per minute)

    Rationale:
    - Legitimate use: 1-3 acknowledgements per day
    - Generous buffer: 15x normal usage
    - Prevents automated acknowledgement bypasses
    """
    rate = '50/hour'
    scope = 'post_acknowledgement'


__all__ = [
    'AttendanceThrottle',
    'GeofenceValidationThrottle',
    'PostManagementThrottle',
    'PostAssignmentThrottle',
    'PostOrderAcknowledgementThrottle',
]
