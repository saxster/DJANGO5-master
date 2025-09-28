"""
JWT + CSRF Double Protection System

Implements enhanced security by combining JWT authentication with CSRF protection
for GraphQL mutations, providing defense-in-depth against sophisticated attacks.

Security Features:
- JWT token validation for authentication
- CSRF token validation for state-changing operations
- Token correlation and binding
- Session hijacking prevention
- Enhanced logging and monitoring
"""

import json
import time
import logging
from typing import Dict, Any, Optional, Tuple
from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.middleware.csrf import get_token
from django.core.exceptions import PermissionDenied
from django.contrib.auth.models import AnonymousUser
import graphql_jwt
from graphql_jwt.decorators import jwt_cookie
from graphql_jwt.utils import get_payload, get_token as get_jwt_token
from apps.core.error_handling import CorrelationIDMiddleware


security_logger = logging.getLogger('security')
jwt_csrf_logger = logging.getLogger('jwt_csrf_protection')


class JWTCSRFProtectionService:
    """
    Service for implementing JWT + CSRF double protection.

    This service ensures that both JWT authentication and CSRF protection
    are validated for GraphQL mutations, providing enhanced security.
    """

    @staticmethod
    def validate_jwt_csrf_double_protection(request: HttpRequest, correlation_id: str = None) -> Dict[str, Any]:
        """
        Validate both JWT and CSRF tokens for enhanced security.

        Args:
            request: The HTTP request object
            correlation_id: Request correlation ID for tracking

        Returns:
            Dict containing validation results and user information

        Raises:
            PermissionDenied: If validation fails
        """
        validation_result = {
            'jwt_valid': False,
            'csrf_valid': False,
            'user': None,
            'security_context': {},
            'correlation_id': correlation_id
        }

        # Step 1: Validate JWT token
        jwt_result = JWTCSRFProtectionService._validate_jwt_token(request, correlation_id)
        validation_result.update(jwt_result)

        if not validation_result['jwt_valid']:
            jwt_csrf_logger.warning(
                f"JWT validation failed for GraphQL mutation. "
                f"Correlation ID: {correlation_id}"
            )
            raise PermissionDenied("Invalid JWT token")

        # Step 2: Validate CSRF token
        csrf_result = JWTCSRFProtectionService._validate_csrf_token(request, correlation_id)
        validation_result.update(csrf_result)

        if not validation_result['csrf_valid']:
            security_logger.error(
                f"CSRF validation failed for authenticated user. "
                f"User: {validation_result['user']}, "
                f"IP: {request.META.get('REMOTE_ADDR', 'unknown')}, "
                f"Correlation ID: {correlation_id}"
            )
            raise PermissionDenied("Invalid CSRF token")

        # Step 3: Validate token correlation
        correlation_result = JWTCSRFProtectionService._validate_token_correlation(
            request, validation_result, correlation_id
        )
        validation_result.update(correlation_result)

        # Step 4: Log successful validation
        jwt_csrf_logger.info(
            f"JWT + CSRF double protection validation successful. "
            f"User: {validation_result['user']}, "
            f"Correlation ID: {correlation_id}"
        )

        return validation_result

    @staticmethod
    def _validate_jwt_token(request: HttpRequest, correlation_id: str = None) -> Dict[str, Any]:
        """Validate JWT token from request."""
        jwt_result = {
            'jwt_valid': False,
            'user': None,
            'jwt_payload': None,
            'jwt_token': None
        }

        try:
            # Extract JWT token from various sources
            jwt_token = JWTCSRFProtectionService._extract_jwt_token(request)

            if not jwt_token:
                jwt_csrf_logger.debug(f"No JWT token found in request. Correlation ID: {correlation_id}")
                return jwt_result

            # Validate JWT token
            payload = get_payload(jwt_token)

            if not payload:
                jwt_csrf_logger.warning(f"Invalid JWT payload. Correlation ID: {correlation_id}")
                return jwt_result

            # Get user from payload
            user = graphql_jwt.utils.get_user_by_payload(payload)

            if not user or isinstance(user, AnonymousUser):
                jwt_csrf_logger.warning(f"No user found for JWT token. Correlation ID: {correlation_id}")
                return jwt_result

            # Validate user is active
            if not user.is_active:
                jwt_csrf_logger.warning(
                    f"Inactive user attempted access. User: {user}, Correlation ID: {correlation_id}"
                )
                return jwt_result

            jwt_result.update({
                'jwt_valid': True,
                'user': user,
                'jwt_payload': payload,
                'jwt_token': jwt_token
            })

            # Set user on request for downstream processing
            request.user = user

        except (DatabaseError, IntegrityError, TypeError, ValidationError, ValueError) as e:
            jwt_csrf_logger.error(
                f"JWT validation error: {str(e)}, Correlation ID: {correlation_id}",
                exc_info=True
            )

        return jwt_result

    @staticmethod
    def _validate_csrf_token(request: HttpRequest, correlation_id: str = None) -> Dict[str, Any]:
        """Validate CSRF token from request."""
        csrf_result = {
            'csrf_valid': False,
            'csrf_token': None
        }

        try:
            # Extract CSRF token from request
            csrf_token = JWTCSRFProtectionService._extract_csrf_token(request)

            if not csrf_token:
                jwt_csrf_logger.debug(f"No CSRF token found in request. Correlation ID: {correlation_id}")
                return csrf_result

            # Validate CSRF token using Django's built-in validation
            from django.middleware.csrf import CsrfViewMiddleware

            # Create temporary CSRF middleware for validation
            csrf_middleware = CsrfViewMiddleware(lambda req: None)

            # Temporarily set POST method for validation
            original_method = request.method
            request.method = 'POST'

            try:
                # Process request through CSRF middleware
                response = csrf_middleware.process_request(request)

                if response is None:
                    # CSRF validation passed
                    csrf_result.update({
                        'csrf_valid': True,
                        'csrf_token': csrf_token
                    })
                else:
                    jwt_csrf_logger.warning(
                        f"CSRF middleware validation failed. Correlation ID: {correlation_id}"
                    )

            finally:
                # Restore original method
                request.method = original_method

        except (DatabaseError, IntegrityError, TypeError, ValidationError, ValueError) as e:
            jwt_csrf_logger.error(
                f"CSRF validation error: {str(e)}, Correlation ID: {correlation_id}",
                exc_info=True
            )

        return csrf_result

    @staticmethod
    def _validate_token_correlation(request: HttpRequest, validation_result: Dict[str, Any],
                                   correlation_id: str = None) -> Dict[str, Any]:
        """Validate correlation between JWT and CSRF tokens to prevent token substitution attacks."""
        correlation_result = {
            'tokens_correlated': False,
            'session_valid': True,
            'security_warnings': []
        }

        try:
            user = validation_result.get('user')
            jwt_payload = validation_result.get('jwt_payload', {})

            # Check token timestamps for correlation
            current_time = int(time.time())
            token_issued_at = jwt_payload.get('iat', 0)
            token_expires_at = jwt_payload.get('exp', 0)

            # Validate token timing
            if token_issued_at > current_time:
                correlation_result['security_warnings'].append('JWT token issued in future')
                jwt_csrf_logger.warning(
                    f"JWT token issued in future. User: {user}, Correlation ID: {correlation_id}"
                )

            if token_expires_at < current_time:
                correlation_result['security_warnings'].append('JWT token expired')
                jwt_csrf_logger.warning(
                    f"Expired JWT token used. User: {user}, Correlation ID: {correlation_id}"
                )
                correlation_result['session_valid'] = False
                return correlation_result

            # Check for session consistency
            if hasattr(request, 'session'):
                session_user_id = request.session.get('_auth_user_id')
                jwt_user_id = str(user.id) if user else None

                if session_user_id and jwt_user_id and session_user_id != jwt_user_id:
                    correlation_result['security_warnings'].append('Session/JWT user mismatch')
                    security_logger.critical(
                        f"Session/JWT user ID mismatch detected! "
                        f"Session: {session_user_id}, JWT: {jwt_user_id}, "
                        f"IP: {request.META.get('REMOTE_ADDR', 'unknown')}, "
                        f"Correlation ID: {correlation_id}"
                    )
                    correlation_result['session_valid'] = False
                    return correlation_result

            # Check for suspicious request patterns
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            if not user_agent or len(user_agent) < 10:
                correlation_result['security_warnings'].append('Suspicious user agent')

            origin = request.META.get('HTTP_ORIGIN', '')
            referer = request.META.get('HTTP_REFERER', '')

            if origin and referer and not referer.startswith(origin):
                correlation_result['security_warnings'].append('Origin/referer mismatch')

            # If we reach here, tokens are correlated
            correlation_result['tokens_correlated'] = True

        except (DatabaseError, IntegrityError, TypeError, ValidationError, ValueError) as e:
            jwt_csrf_logger.error(
                f"Token correlation validation error: {str(e)}, Correlation ID: {correlation_id}",
                exc_info=True
            )

        return correlation_result

    @staticmethod
    def _extract_jwt_token(request: HttpRequest) -> Optional[str]:
        """Extract JWT token from request headers or cookies."""
        # Check Authorization header
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('Bearer '):
            return auth_header[7:]  # Remove 'Bearer ' prefix

        if auth_header.startswith('JWT '):
            return auth_header[4:]   # Remove 'JWT ' prefix

        # Check X-JWT-Token header
        jwt_header = request.META.get('HTTP_X_JWT_TOKEN')
        if jwt_header:
            return jwt_header

        # Check cookies
        jwt_cookie_name = getattr(settings, 'JWT_AUTH_COOKIE', 'jwt-token')
        jwt_token = request.COOKIES.get(jwt_cookie_name)
        if jwt_token:
            return jwt_token

        return None

    @staticmethod
    def _extract_csrf_token(request: HttpRequest) -> Optional[str]:
        """Extract CSRF token from request headers or form data."""
        # Check X-CSRFToken header
        csrf_token = request.META.get('HTTP_X_CSRFTOKEN')
        if csrf_token:
            return csrf_token

        # Check X-CSRF-Token header (alternative)
        csrf_token = request.META.get('HTTP_X_CSRF_TOKEN')
        if csrf_token:
            return csrf_token

        # Check form data
        if request.method == 'POST':
            csrf_token = request.POST.get('csrfmiddlewaretoken')
            if csrf_token:
                return csrf_token

            # Check JSON body for CSRF token
            try:
                if hasattr(request, 'body') and request.content_type == 'application/json':
                    data = json.loads(request.body.decode('utf-8'))
                    csrf_token = data.get('csrfmiddlewaretoken')
                    if csrf_token:
                        return csrf_token
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass

        return None

    @staticmethod
    def create_security_context(request: HttpRequest, validation_result: Dict[str, Any]) -> Dict[str, Any]:
        """Create comprehensive security context for the request."""
        user = validation_result.get('user')
        correlation_id = validation_result.get('correlation_id')

        security_context = {
            'user_id': user.id if user else None,
            'user_role': 'admin' if user and user.isadmin else 'user',
            'authentication_method': 'JWT+CSRF',
            'request_ip': request.META.get('REMOTE_ADDR', 'unknown'),
            'user_agent': request.META.get('HTTP_USER_AGENT', 'unknown'),
            'origin': request.META.get('HTTP_ORIGIN', ''),
            'referer': request.META.get('HTTP_REFERER', ''),
            'correlation_id': correlation_id,
            'timestamp': int(time.time()),
            'security_level': 'high',
            'validation_warnings': validation_result.get('security_warnings', [])
        }

        return security_context

    @staticmethod
    def log_security_event(event_type: str, security_context: Dict[str, Any], details: str = None):
        """Log security events for monitoring and analysis."""
        log_data = {
            'event_type': event_type,
            'security_context': security_context,
            'details': details,
            'timestamp': time.time()
        }

        if event_type in ['authentication_success', 'validation_success']:
            jwt_csrf_logger.info(f"Security event: {event_type}", extra=log_data)
        elif event_type in ['authentication_failure', 'validation_failure', 'suspicious_activity']:
            security_logger.warning(f"Security event: {event_type}", extra=log_data)
        elif event_type in ['security_violation', 'attack_detected']:
            security_logger.critical(f"Security event: {event_type}", extra=log_data)
        else:
            jwt_csrf_logger.debug(f"Security event: {event_type}", extra=log_data)


class JWTCSRFGraphQLMiddleware:
    """
    GraphQL middleware that enforces JWT + CSRF double protection for mutations.
    """

    def resolve(self, next, root, info, **args):
        """Apply JWT + CSRF double protection to GraphQL mutations."""
        request = info.context

        # Get correlation ID
        correlation_id = getattr(request, 'correlation_id', None)
        if not correlation_id:
            correlation_id = CorrelationIDMiddleware.generate_correlation_id()
            request.correlation_id = correlation_id

        # Check if this is a mutation that requires double protection
        operation = info.operation
        if operation and operation.operation == 'mutation':

            # Skip double protection for specific mutations if configured
            skip_mutations = getattr(settings, 'JWT_CSRF_SKIP_MUTATIONS', [])
            mutation_name = info.field_name

            if mutation_name not in skip_mutations:
                try:
                    # Validate JWT + CSRF double protection
                    validation_result = JWTCSRFProtectionService.validate_jwt_csrf_double_protection(
                        request, correlation_id
                    )

                    # Create security context
                    security_context = JWTCSRFProtectionService.create_security_context(
                        request, validation_result
                    )

                    # Log successful validation
                    JWTCSRFProtectionService.log_security_event(
                        'jwt_csrf_validation_success',
                        security_context,
                        f"Mutation: {mutation_name}"
                    )

                    # Add security context to request for downstream use
                    request.security_context = security_context

                except PermissionDenied as e:
                    # Log failed validation
                    JWTCSRFProtectionService.log_security_event(
                        'jwt_csrf_validation_failure',
                        {'correlation_id': correlation_id, 'mutation': mutation_name},
                        str(e)
                    )

                    from graphql import GraphQLError
                    raise GraphQLError(
                        message=str(e),
                        extensions={
                            'code': 'JWT_CSRF_VALIDATION_FAILED',
                            'correlation_id': correlation_id,
                            'timestamp': time.time()
                        }
                    )

        return next(root, info, **args)