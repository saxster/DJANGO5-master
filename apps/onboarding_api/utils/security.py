"""
Security enhancements for Conversational Onboarding API

This module provides advanced security features including tenant scoping,
idempotency protection, and enhanced security validations.
"""
import hashlib
import hmac
import logging
import uuid
from functools import wraps


logger = logging.getLogger(__name__)


class SecurityValidationError(Exception):
    """Exception raised when security validation fails"""
    pass


class TenantScopeValidator:
    """
    Enhanced tenant scoping validation with allowlist support

    Provides comprehensive tenant-level security controls to prevent
    cross-tenant data access and ensure proper authorization.
    """

    def __init__(self):
        self.tenant_allowlist_cache_timeout = 3600  # 1 hour

    def validate_tenant_scope(self, user, client, operation: str) -> Dict[str, Any]:
        """
        Validate that user has access to the specified client for the given operation

        Args:
            user: User instance making the request
            client: Client/tenant instance being accessed
            operation: Type of operation (read, write, admin, etc.)

        Returns:
            Dict with validation results
        """
        validation_result = {
            'is_valid': True,
            'tenant_id': client.id if client else None,
            'user_id': user.id if user else None,
            'operation': operation,
            'scope_level': 'user',
            'warnings': [],
            'violations': []
        }

        try:
            # Basic tenant membership validation
            if not client:
                validation_result['is_valid'] = False
                validation_result['violations'].append('No client specified')
                return validation_result

            if not user:
                validation_result['is_valid'] = False
                validation_result['violations'].append('No user specified')
                return validation_result

            # Check if user belongs to the client
            if hasattr(user, 'client') and user.client != client:
                validation_result['is_valid'] = False
                validation_result['violations'].append(f'User {user.id} does not belong to client {client.id}')
                return validation_result

            # Enhanced operation-specific validation
            if operation == 'admin' or operation.startswith('admin_'):
                if not user.is_staff and not self._has_admin_capability(user, client):
                    validation_result['is_valid'] = False
                    validation_result['violations'].append(f'User {user.id} lacks admin privileges for operation {operation}')
                    return validation_result
                validation_result['scope_level'] = 'admin'

            elif operation.startswith('approve_'):
                if not self._has_approval_capability(user, client):
                    validation_result['is_valid'] = False
                    validation_result['violations'].append(f'User {user.id} lacks approval privileges')
                    return validation_result
                validation_result['scope_level'] = 'approver'

            # Check tenant allowlist if configured
            allowlist_validation = self._validate_tenant_allowlist(client)
            if not allowlist_validation['is_valid']:
                validation_result['is_valid'] = False
                validation_result['violations'].extend(allowlist_validation['violations'])

            # Check for suspended or disabled tenants
            if hasattr(client, 'is_active') and not client.is_active:
                validation_result['is_valid'] = False
                validation_result['violations'].append(f'Client {client.id} is inactive')

            # Add security metadata
            validation_result['validation_timestamp'] = timezone.now().isoformat()
            validation_result['client_info'] = {
                'id': client.id,
                'name': getattr(client, 'buname', 'Unknown'),
                'code': getattr(client, 'bucode', 'Unknown')
            }

            logger.debug(
                f"Tenant scope validation: {validation_result['is_valid']} "
                f"for user {user.id} on client {client.id} for operation {operation}"
            )

        except (TypeError, ValidationError, ValueError) as e:
            logger.error(f"Tenant scope validation error: {str(e)}")
            validation_result['is_valid'] = False
            validation_result['violations'].append(f'Validation error: {str(e)}')

        return validation_result

    def _validate_tenant_allowlist(self, client) -> Dict[str, Any]:
        """Validate tenant against allowlist if configured"""
        result = {
            'is_valid': True,
            'violations': []
        }

        try:
            # Check for tenant allowlist configuration
            tenant_allowlist = getattr(settings, 'ONBOARDING_TENANT_ALLOWLIST', None)

            if tenant_allowlist is None:
                # No allowlist configured - allow all active tenants
                return result

            # Check if client is in allowlist
            client_identifier = getattr(client, 'bucode', str(client.id))

            if client_identifier not in tenant_allowlist:
                result['is_valid'] = False
                result['violations'].append(f'Client {client_identifier} not in tenant allowlist')

        except (TypeError, ValidationError, ValueError) as e:
            logger.error(f"Tenant allowlist validation error: {str(e)}")
            result['violations'].append(f'Allowlist check failed: {str(e)}')

        return result

    def _has_admin_capability(self, user, client) -> bool:
        """Check if user has admin capabilities for the client"""
        try:
            if hasattr(user, 'get_capability'):
                return user.get_capability('can_access_admin_endpoints') or user.get_capability('can_manage_onboarding')
            return user.is_staff
        except:
            return user.is_staff

    def _has_approval_capability(self, user, client) -> bool:
        """Check if user has approval capabilities for the client"""
        try:
            if hasattr(user, 'get_capability'):
                return user.get_capability('can_approve_ai_recommendations')
            return user.is_staff
        except:
            return False


class IdempotencyManager:
    """
    Enhanced idempotency protection with persistent storage

    Provides robust idempotency keys to prevent duplicate operations
    and ensure consistent behavior across distributed systems.
    """

    def __init__(self, cache_timeout: int = 86400):  # 24 hours
        self.cache_timeout = cache_timeout
        self.idempotency_prefix = "onboarding_idempotency"

    def generate_idempotency_key(self, user, operation: str, data: Dict[str, Any] = None) -> str:
        """
        Generate a deterministic idempotency key

        Args:
            user: User making the request
            operation: Operation being performed
            data: Request data to include in key generation

        Returns:
            Idempotency key string
        """
        # Create deterministic key based on user, operation, and data
        key_components = [
            str(user.id),
            operation,
            timezone.now().date().isoformat(),  # Include date for daily reset
        ]

        # Include relevant data in key generation
        if data:
            # Sort keys for deterministic ordering
            sorted_data = sorted(data.items()) if isinstance(data, dict) else str(data)
            key_components.append(str(sorted_data))

        key_string = ":".join(key_components)
        key_hash = hashlib.sha256(key_string.encode()).hexdigest()[:16]

        return f"{self.idempotency_prefix}:{key_hash}"

    def check_idempotency(self, idempotency_key: str, operation_result: Any = None) -> Dict[str, Any]:
        """
        Check idempotency and store result if new operation

        Args:
            idempotency_key: Unique key for the operation
            operation_result: Result to store for future duplicate requests

        Returns:
            Dict with idempotency status and cached result if available
        """
        try:
            cached_result = cache.get(idempotency_key)

            if cached_result is not None:
                logger.info(f"Idempotent request detected: {idempotency_key}")
                return {
                    'is_duplicate': True,
                    'cached_result': cached_result,
                    'cached_at': cached_result.get('timestamp', 'unknown'),
                    'key': idempotency_key
                }

            # Store the operation result for future idempotency checks
            if operation_result is not None:
                cached_data = {
                    'result': operation_result,
                    'timestamp': timezone.now().isoformat(),
                    'key': idempotency_key
                }
                cache.set(idempotency_key, cached_data, self.cache_timeout)

            return {
                'is_duplicate': False,
                'key': idempotency_key,
                'stored_at': timezone.now().isoformat()
            }

        except (ConnectionError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Idempotency check failed: {str(e)}")
            return {
                'is_duplicate': False,  # Fail open for availability
                'error': str(e),
                'key': idempotency_key
            }

    def invalidate_idempotency_key(self, idempotency_key: str) -> bool:
        """
        Invalidate an idempotency key (for error handling)

        Args:
            idempotency_key: Key to invalidate

        Returns:
            True if successfully invalidated
        """
        try:
            cache.delete(idempotency_key)
            return True
        except (ConnectionError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Failed to invalidate idempotency key {idempotency_key}: {str(e)}")
            return False


class SecurityAuditLogger:
    """
    Enhanced security audit logging with structured events

    Provides comprehensive audit trails for security-relevant events
    with proper categorization and metadata.
    """

    def __init__(self):
        self.audit_logger = logging.getLogger("audit")
        self.security_logger = logging.getLogger("security")

    def log_security_event(
        self,
        event_type: str,
        user,
        details: Dict[str, Any],
        severity: str = 'info'
    ) -> None:
        """
        Log a security-relevant event

        Args:
            event_type: Type of security event (access_denied, privilege_escalation, etc.)
            user: User involved in the event
            details: Additional event details
            severity: Severity level (info, warning, critical)
        """
        try:
            audit_entry = {
                'event_type': event_type,
                'user_id': user.id if user else None,
                'user_email': user.email if user and hasattr(user, 'email') else None,
                'timestamp': timezone.now().isoformat(),
                'severity': severity,
                'details': details,
                'source': 'onboarding_api',
                'correlation_id': details.get('correlation_id', str(uuid.uuid4()))
            }

            # Log to appropriate logger based on severity
            log_message = f"Security Event: {event_type} - User: {user.id if user else 'None'}"

            if severity == 'critical':
                self.security_logger.critical(log_message, extra=audit_entry)
            elif severity == 'warning':
                self.security_logger.warning(log_message, extra=audit_entry)
            else:
                self.audit_logger.info(log_message, extra=audit_entry)

        except (ConnectionError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Failed to log security event: {str(e)}")

    def log_access_attempt(
        self,
        user,
        resource: str,
        operation: str,
        granted: bool,
        reason: str = None,
        additional_context: Dict[str, Any] = None
    ) -> None:
        """Log access attempt for audit purposes"""
        details = {
            'resource': resource,
            'operation': operation,
            'access_granted': granted,
            'reason': reason,
            'client_ip': additional_context.get('client_ip') if additional_context else None,
            'user_agent': additional_context.get('user_agent') if additional_context else None
        }

        if additional_context:
            details.update(additional_context)

        event_type = 'access_granted' if granted else 'access_denied'
        severity = 'info' if granted else 'warning'

        self.log_security_event(event_type, user, details, severity)

    def log_privilege_escalation(
        self,
        user,
        from_role: str,
        to_role: str,
        granted: bool,
        justification: str = None
    ) -> None:
        """Log privilege escalation attempts"""
        details = {
            'from_role': from_role,
            'to_role': to_role,
            'escalation_granted': granted,
            'justification': justification
        }

        event_type = 'privilege_escalation'
        severity = 'critical' if granted else 'warning'

        self.log_security_event(event_type, user, details, severity)


# Global instances
tenant_scope_validator = TenantScopeValidator()
idempotency_manager = IdempotencyManager()
security_audit_logger = SecurityAuditLogger()


def require_tenant_scope(operation: str):
    """
    Decorator to enforce tenant scoping on view functions

    Args:
        operation: Operation type being performed

    Usage:
        @require_tenant_scope('read')
        def my_view(request):
            # View implementation
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            try:
                # Get user and client from request
                user = request.user
                client = getattr(user, 'client', None) if hasattr(user, 'client') else None

                # Validate tenant scope
                validation = tenant_scope_validator.validate_tenant_scope(user, client, operation)

                if not validation['is_valid']:
                    # Log security violation
                    security_audit_logger.log_access_attempt(
                        user=user,
                        resource=request.path,
                        operation=operation,
                        granted=False,
                        reason='; '.join(validation['violations']),
                        additional_context={
                            'client_ip': request.META.get('REMOTE_ADDR'),
                            'user_agent': request.META.get('HTTP_USER_AGENT'),
                            'tenant_validation': validation
                        }
                    )

                    from rest_framework.response import Response
                    from rest_framework import status

                    return Response({
                        'error': 'Insufficient tenant permissions',
                        'violations': validation['violations'],
                        'operation': operation
                    }, status=status.HTTP_403_FORBIDDEN)

                # Add validation context to request for use in view
                request.tenant_validation = validation

                # Log successful access
                security_audit_logger.log_access_attempt(
                    user=user,
                    resource=request.path,
                    operation=operation,
                    granted=True,
                    additional_context={
                        'client_ip': request.META.get('REMOTE_ADDR'),
                        'scope_level': validation['scope_level']
                    }
                )

                return view_func(request, *args, **kwargs)

            except (DatabaseError, IntegrityError, TypeError, ValidationError, ValueError) as e:
                logger.error(f"Tenant scope validation error: {str(e)}")

                from rest_framework.response import Response
                from rest_framework import status

                return Response({
                    'error': 'Security validation failed',
                    'details': str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return wrapper
    return decorator


def with_idempotency(operation: str, data_extractor=None):
    """
    Decorator to add idempotency protection to view functions

    Args:
        operation: Operation type for key generation
        data_extractor: Function to extract relevant data from request

    Usage:
        @with_idempotency('create_session')
        def my_view(request):
            # View implementation
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            try:
                # Extract data for idempotency key generation
                data = data_extractor(request) if data_extractor else None

                # Generate idempotency key
                idempotency_key = idempotency_manager.generate_idempotency_key(
                    user=request.user,
                    operation=operation,
                    data=data
                )

                # Check for existing operation
                idempotency_check = idempotency_manager.check_idempotency(idempotency_key)

                if idempotency_check['is_duplicate']:
                    logger.info(f"Returning cached result for idempotent operation: {idempotency_key}")

                    cached_result = idempotency_check['cached_result']['result']

                    from rest_framework.response import Response
                    return Response(cached_result)

                # Execute the view function
                response = view_func(request, *args, **kwargs)

                # Store result for future idempotency checks
                if hasattr(response, 'data') and response.status_code < 400:
                    idempotency_manager.check_idempotency(idempotency_key, response.data)

                # Add idempotency headers
                response['X-Idempotency-Key'] = idempotency_key
                response['X-Idempotency-Duplicate'] = 'false'

                return response

            except (DatabaseError, IntegrityError, TypeError, ValidationError, ValueError) as e:
                logger.error(f"Idempotency handling error: {str(e)}")
                # Continue without idempotency protection to maintain availability
                return view_func(request, *args, **kwargs)

        return wrapper
    return decorator


# Utility functions for manual security validation
def validate_request_signature(request: HttpRequest, secret_key: str) -> bool:
    """
    Validate HMAC signature for high-security API endpoints

    Args:
        request: HTTP request to validate
        secret_key: Secret key for HMAC generation

    Returns:
        True if signature is valid
    """
    try:
        signature_header = request.META.get('HTTP_X_SIGNATURE')
        if not signature_header:
            return False

        # Extract signature
        if not signature_header.startswith('sha256='):
            return False

        provided_signature = signature_header[7:]  # Remove 'sha256=' prefix

        # Generate expected signature
        body = request.body
        expected_signature = hmac.new(
            secret_key.encode(),
            body,
            hashlib.sha256
        ).hexdigest()

        # Constant-time comparison
        return hmac.compare_digest(provided_signature, expected_signature)

    except (ConnectionError, DatabaseError, IntegrityError, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Signature validation error: {str(e)}")
        return False


def get_client_ip(request: HttpRequest) -> str:
    """
    Extract client IP address from request headers

    Args:
        request: HTTP request

    Returns:
        Client IP address string
    """
    # Check for forwarded headers (behind proxy/load balancer)
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()

    forwarded = request.META.get('HTTP_X_FORWARDED')
    if forwarded:
        return forwarded

    real_ip = request.META.get('HTTP_X_REAL_IP')
    if real_ip:
        return real_ip

    # Fallback to REMOTE_ADDR
    return request.META.get('REMOTE_ADDR', 'unknown')