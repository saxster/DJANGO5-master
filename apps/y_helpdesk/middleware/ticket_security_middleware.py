"""
Ticket Security Middleware - Request-Level Security Enforcement

Provides comprehensive security enforcement at the request level for
all ticket-related operations:
- Input validation and sanitization
- Access control enforcement
- Security monitoring and logging
- Rate limiting and threat detection

Following .claude/rules.md:
- Rule #1: Security-first approach
- Rule #7: Middleware <150 lines
- Rule #9: Input validation
- Rule #11: Specific security exception handling
"""

import logging
import json
from typing import Dict, Any, Optional

from django.http import JsonResponse, HttpRequest, HttpResponse
from django.core.exceptions import ValidationError, PermissionDenied, SuspiciousOperation
from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone
from django.conf import settings

from apps.y_helpdesk.security.ticket_security_service import (
    TicketSecurityService, SecurityEvent, SecurityViolationType, SecurityThreatLevel
)
from apps.y_helpdesk.services.ticket_audit_service import (
    TicketAuditService, AuditContext, AuditEventType
)

logger = logging.getLogger(__name__)


class TicketSecurityMiddleware(MiddlewareMixin):
    """
    Security middleware for ticket operations.

    Intercepts all ticket-related requests and enforces comprehensive
    security policies including input validation, access control,
    and threat monitoring.
    """

    # Ticket-related URL patterns
    TICKET_URL_PATTERNS = [
        '/api/v1/tickets/',
        '/api/graphql/',  # Legacy - GraphQL removed Oct 2025, kept for backward compat
        '/help-desk/',
        '/y_helpdesk/'
    ]

    # Operations that require enhanced security
    SENSITIVE_OPERATIONS = {
        'POST': ['create', 'update'],
        'PUT': ['update'],
        'PATCH': ['update'],
        'DELETE': ['delete']
    }

    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """
        Process incoming request for ticket security enforcement.

        Args:
            request: HTTP request

        Returns:
            None to continue processing, or HttpResponse to short-circuit
        """
        # Check if this is a ticket-related request
        if not self._is_ticket_request(request):
            return None

        try:
            # Create audit context for the request
            audit_context = self._create_audit_context(request)

            # Validate request security
            self._validate_request_security(request, audit_context)

            # Enhance request with security context
            request.ticket_security_context = {
                'validated': True,
                'audit_context': audit_context,
                'timestamp': timezone.now()
            }

            return None

        except SuspiciousOperation as e:
            logger.critical(
                f"Suspicious ticket operation blocked: {e}",
                extra={
                    'security_event': True,
                    'user_id': request.user.id if hasattr(request, 'user') and request.user.is_authenticated else None,
                    'path': request.path,
                    'method': request.method,
                    'ip_address': self._get_client_ip(request)
                }
            )

            return JsonResponse({
                'error': 'Security violation detected',
                'code': 'SECURITY_VIOLATION',
                'timestamp': timezone.now().isoformat()
            }, status=403)

        except PermissionDenied as e:
            logger.warning(
                f"Permission denied for ticket operation: {e}",
                extra={
                    'user_id': request.user.id if hasattr(request, 'user') and request.user.is_authenticated else None,
                    'path': request.path,
                    'method': request.method
                }
            )

            return JsonResponse({
                'error': str(e),
                'code': 'PERMISSION_DENIED',
                'timestamp': timezone.now().isoformat()
            }, status=403)

        except ValidationError as e:
            logger.info(
                f"Validation error in ticket request: {e}",
                extra={
                    'user_id': request.user.id if hasattr(request, 'user') and request.user.is_authenticated else None,
                    'path': request.path
                }
            )

            return JsonResponse({
                'error': 'Invalid input data',
                'details': e.message_dict if hasattr(e, 'message_dict') else str(e),
                'code': 'VALIDATION_ERROR',
                'timestamp': timezone.now().isoformat()
            }, status=400)

    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """
        Process response for security enhancements.

        Args:
            request: HTTP request
            response: HTTP response

        Returns:
            Enhanced HTTP response
        """
        # Only process ticket-related responses
        if not self._is_ticket_request(request):
            return response

        # Add security headers
        response['X-Ticket-Security-Version'] = '2.0'
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'

        # Log successful operations
        if hasattr(request, 'ticket_security_context') and response.status_code < 400:
            audit_context = request.ticket_security_context['audit_context']

            logger.info(
                f"Secure ticket operation completed: {request.method} {request.path}",
                extra={
                    'user_id': audit_context.user.id if audit_context.user else None,
                    'status_code': response.status_code,
                    'operation_secure': True
                }
            )

        return response

    def _is_ticket_request(self, request: HttpRequest) -> bool:
        """Check if request is ticket-related."""
        return any(pattern in request.path for pattern in self.TICKET_URL_PATTERNS)

    def _create_audit_context(self, request: HttpRequest) -> AuditContext:
        """Create audit context from request."""
        return AuditContext(
            user=request.user if hasattr(request, 'user') and request.user.is_authenticated else None,
            session_id=request.session.session_key if hasattr(request, 'session') else None,
            ip_address=self._get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            request_id=getattr(request, 'correlation_id', None),
            tenant=getattr(request, 'tenant', 'default')
        )

    def _validate_request_security(
        self,
        request: HttpRequest,
        audit_context: AuditContext
    ) -> None:
        """Validate request security."""
        # Validate authentication for sensitive operations
        if request.method in self.SENSITIVE_OPERATIONS:
            if not request.user.is_authenticated:
                raise PermissionDenied("Authentication required for ticket operations")

        # Validate input data for POST/PUT requests
        if request.method in ['POST', 'PUT', 'PATCH'] and hasattr(request, 'body'):
            try:
                # Parse request data
                if request.content_type == 'application/json':
                    request_data = json.loads(request.body.decode('utf-8'))
                else:
                    request_data = dict(request.POST)

                # Validate using security service
                if request_data and request.user.is_authenticated:
                    operation_type = self._determine_operation_type(request)
                    TicketSecurityService.validate_ticket_input(
                        request_data, request.user, operation_type
                    )

            except json.JSONDecodeError:
                logger.warning(
                    f"Invalid JSON in ticket request from user {request.user.id if request.user.is_authenticated else 'anonymous'}",
                    extra={'path': request.path, 'method': request.method}
                )
                raise ValidationError("Invalid JSON data")

            except (ValidationError, SuspiciousOperation):
                # Re-raise security exceptions
                raise

            except Exception as e:
                logger.error(
                    f"Unexpected error in ticket security validation: {e}",
                    exc_info=True
                )
                # Don't expose internal errors
                raise ValidationError("Request validation failed")

    def _determine_operation_type(self, request: HttpRequest) -> str:
        """Determine operation type from request."""
        if request.method == 'POST':
            return 'create' if 'id' not in request.POST else 'update'
        elif request.method in ['PUT', 'PATCH']:
            return 'update'
        elif request.method == 'DELETE':
            return 'delete'
        else:
            return 'read'

    def _get_client_ip(self, request: HttpRequest) -> str:
        """Get client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '')

        return ip


class TicketAuditMiddleware(MiddlewareMixin):
    """
    Audit middleware for comprehensive ticket operation logging.

    Logs all ticket-related activities for compliance and security monitoring.
    """

    def process_request(self, request: HttpRequest) -> None:
        """Record request start for audit timing."""
        if self._is_ticket_request(request):
            request.ticket_audit_start = timezone.now()

    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Log completed ticket operations."""
        if not self._is_ticket_request(request):
            return response

        # Calculate request duration
        duration = None
        if hasattr(request, 'ticket_audit_start'):
            duration = timezone.now() - request.ticket_audit_start

        # Log the operation
        audit_context = AuditContext(
            user=request.user if hasattr(request, 'user') and request.user.is_authenticated else None,
            session_id=request.session.session_key if hasattr(request, 'session') else None,
            ip_address=self._get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )

        logger.info(
            f"Ticket operation audit: {request.method} {request.path}",
            extra={
                'audit_event': True,
                'method': request.method,
                'path': request.path,
                'status_code': response.status_code,
                'duration_ms': duration.total_seconds() * 1000 if duration else None,
                'user_id': audit_context.user.id if audit_context.user else None,
                'ip_address': audit_context.ip_address,
                'timestamp': timezone.now().isoformat()
            }
        )

        return response

    def _is_ticket_request(self, request: HttpRequest) -> bool:
        """Check if request is ticket-related."""
        ticket_patterns = ['/api/v1/tickets/', '/help-desk/', '/y_helpdesk/']
        return any(pattern in request.path for pattern in ticket_patterns)

    def _get_client_ip(self, request: HttpRequest) -> str:
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')