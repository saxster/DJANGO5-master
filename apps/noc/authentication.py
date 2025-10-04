"""
NOC API Key Authentication.

DRF authentication classes for NOC API key access.
Follows .claude/rules.md Rule #3 (alternative to CSRF), Rule #11 (specific exceptions).
Follows .claude/rules.md Rule #15 (logging data sanitization).
"""

import hashlib
import logging
from rest_framework import authentication, permissions
from rest_framework.exceptions import AuthenticationFailed
from apps.core.models.monitoring_api_key import MonitoringAPIKey, MonitoringAPIAccessLog
from apps.noc.models import NOCAuditLog
from apps.noc.utils import sanitize_api_key_log

__all__ = [
    'NOCAPIKeyAuthentication',
    'NOCAPIKeyPermission',
]

logger = logging.getLogger('noc.authentication')


class NOCAPIKeyAuthentication(authentication.BaseAuthentication):
    """
    API Key authentication for NOC endpoints.

    Provides secure alternative to CSRF protection for external monitoring tools.
    Complies with .claude/rules.md Rule #3 (documented alternative authentication).

    Usage:
        Add to view: authentication_classes = [NOCAPIKeyAuthentication]
        Request header: X-API-Key: <api_key>
    """

    def authenticate(self, request):
        """
        Authenticate request using API key.

        Args:
            request: Django request object

        Returns:
            tuple: (user, api_key) if authenticated
            None: if no API key provided (try other auth methods)

        Raises:
            AuthenticationFailed: if invalid key
        """
        api_key = self._get_api_key_from_request(request)

        if not api_key:
            return None

        try:
            monitoring_key = self._validate_api_key(api_key, request)

            if not monitoring_key.created_by:
                raise AuthenticationFailed(
                    'API key has no associated user'
                )

            self._check_ip_whitelist(monitoring_key, request)

            self._check_noc_permissions(monitoring_key)

            monitoring_key.record_usage()

            self._create_audit_log(monitoring_key, request)

            return (monitoring_key.created_by, monitoring_key)

        except MonitoringAPIKey.DoesNotExist:
            raise AuthenticationFailed('Invalid API key')
        except (ValueError, AttributeError) as e:
            logger.error(
                f"API key authentication error: {e}",
                extra={'api_key_prefix': api_key[:8]}
            )
            raise AuthenticationFailed('Authentication failed')

    def authenticate_header(self, request):
        """
        Return authentication scheme for WWW-Authenticate header.

        Returns:
            str: Authentication scheme name
        """
        return 'X-API-Key'

    @staticmethod
    def _get_api_key_from_request(request):
        """Extract API key from request headers."""
        return request.META.get('HTTP_X_API_KEY')

    @staticmethod
    def _validate_api_key(api_key: str, request) -> MonitoringAPIKey:
        """
        Validate and retrieve API key.

        Args:
            api_key: Raw API key string
            request: Django request

        Returns:
            MonitoringAPIKey instance

        Raises:
            MonitoringAPIKey.DoesNotExist: if key not found
            AuthenticationFailed: if key invalid
        """
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        monitoring_key = MonitoringAPIKey.objects.select_related(
            'created_by'
        ).get(key_hash=key_hash)

        if not monitoring_key.is_active:
            raise AuthenticationFailed('API key is inactive')

        if monitoring_key.is_expired():
            raise AuthenticationFailed('API key has expired')

        return monitoring_key

    @staticmethod
    def _check_ip_whitelist(monitoring_key: MonitoringAPIKey, request):
        """
        Check IP whitelist if configured.

        Args:
            monitoring_key: MonitoringAPIKey instance
            request: Django request

        Raises:
            AuthenticationFailed: if IP not whitelisted
        """
        if not monitoring_key.allowed_ips:
            return

        client_ip = request.META.get('REMOTE_ADDR')

        if client_ip not in monitoring_key.allowed_ips:
            # Sanitize sensitive data for logging
            sanitized = sanitize_api_key_log(
                api_key_id=monitoring_key.id,
                allowed_ips=monitoring_key.allowed_ips,
                client_ip=client_ip,
                correlation_id=getattr(request, 'correlation_id', None)
            )

            logger.warning(
                "API key access from non-whitelisted IP",
                extra=sanitized
            )
            raise AuthenticationFailed(
                'Access denied: IP address not whitelisted'
            )

    @staticmethod
    def _check_noc_permissions(monitoring_key: MonitoringAPIKey):
        """
        Verify key has NOC-specific permissions.

        Args:
            monitoring_key: MonitoringAPIKey instance

        Raises:
            AuthenticationFailed: if no NOC permissions
        """
        from apps.core.models.monitoring_api_key import MonitoringPermission

        noc_permissions = [
            MonitoringPermission.HEALTH.value,
            MonitoringPermission.METRICS.value,
            MonitoringPermission.ALERTS.value,
            MonitoringPermission.DASHBOARD.value,
            MonitoringPermission.ADMIN.value,
        ]

        has_noc_permission = any(
            perm in monitoring_key.permissions
            for perm in noc_permissions
        )

        if not has_noc_permission:
            raise AuthenticationFailed(
                'API key does not have NOC permissions'
            )

    @staticmethod
    def _create_audit_log(monitoring_key: MonitoringAPIKey, request):
        """
        Create audit log for API key access.

        Args:
            monitoring_key: MonitoringAPIKey instance
            request: Django request
        """
        try:
            if monitoring_key.created_by:
                # Sanitize API key info for audit metadata
                sanitized = sanitize_api_key_log(
                    api_key_id=monitoring_key.id,
                    api_key_name=monitoring_key.name,
                    permissions=monitoring_key.permissions,
                    client_ip=request.META.get('REMOTE_ADDR'),
                    correlation_id=getattr(request, 'correlation_id', None)
                )

                NOCAuditLog.objects.create(
                    tenant=monitoring_key.created_by.tenant,
                    action='API_KEY_ACCESS',
                    actor=monitoring_key.created_by,
                    entity_type='api_key',
                    entity_id=monitoring_key.id,
                    metadata={
                        'endpoint': request.path,
                        'method': request.method,
                        'api_key_hash': sanitized.get('api_key_hash'),
                        'api_key_name_hash': sanitized.get('api_key_name_hash'),
                        'permissions': sanitized.get('permissions'),
                        'correlation_id': sanitized.get('correlation_id')
                    },
                    ip_address=request.META.get('REMOTE_ADDR')
                )
        except (ValueError, AttributeError) as e:
            # Sanitize for error logging
            sanitized = sanitize_api_key_log(
                api_key_id=monitoring_key.id,
                correlation_id=getattr(request, 'correlation_id', None)
            )
            logger.error(
                f"Failed to create audit log: {e}",
                extra=sanitized
            )


class NOCAPIKeyPermission(permissions.BasePermission):
    """
    Permission class for NOC API key access.

    Verifies API key has required NOC permission for the endpoint.
    """

    permission_map = {
        'GET': 'health',
        'POST': 'metrics',
        'PUT': 'admin',
        'PATCH': 'admin',
        'DELETE': 'admin',
    }

    def has_permission(self, request, view):
        """
        Check if API key has required permission.

        Args:
            request: Django request
            view: View being accessed

        Returns:
            bool: True if permitted
        """
        if not hasattr(request, 'auth'):
            return False

        if not isinstance(request.auth, MonitoringAPIKey):
            return True

        api_key = request.auth

        required_permission = self.permission_map.get(
            request.method,
            'health'
        )

        if view.__class__.__name__.startswith('Export'):
            required_permission = 'metrics'

        return api_key.has_permission(required_permission)