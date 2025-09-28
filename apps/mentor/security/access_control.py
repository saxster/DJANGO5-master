"""
Enhanced access control for AI Mentor system.

This module provides:
- Staff-only access controls
- Group/permission-based security
- API key management
- Rate limiting
- Audit logging
"""

import hashlib
import secrets
import time
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from django.core.cache import cache
from django.conf import settings
from django.utils import timezone

from apps.peoples.models import People


class MentorPermission(Enum):
    """AI Mentor specific permissions."""
    VIEW_MENTOR = "mentor.view_mentor"
    USE_PLAN_GENERATOR = "mentor.use_plan_generator"
    USE_PATCH_GENERATOR = "mentor.use_patch_generator"
    APPLY_PATCHES = "mentor.apply_patches"
    USE_TEST_RUNNER = "mentor.use_test_runner"
    VIEW_SENSITIVE_CODE = "mentor.view_sensitive_code"
    BYPASS_SAFETY_CHECKS = "mentor.bypass_safety_checks"
    ADMIN_MENTOR = "mentor.admin_mentor"


class SecurityLevel(Enum):
    """Security levels for mentor operations."""
    PUBLIC = "public"          # No authentication required
    AUTHENTICATED = "authenticated"  # Basic authentication
    STAFF = "staff"           # Staff members only
    TRUSTED = "trusted"       # Trusted staff with mentor permissions
    ADMIN = "admin"          # Mentor administrators


@dataclass
class AccessAttempt:
    """Record of an access attempt."""
    user_id: Optional[int]
    ip_address: str
    endpoint: str
    permission_required: str
    granted: bool
    timestamp: datetime
    user_agent: Optional[str] = None
    additional_data: Dict[str, str] = None


class MentorAccessControl:
    """Enhanced access control for AI Mentor operations."""

    def __init__(self):
        self.rate_limit_cache_prefix = "mentor_rate_limit"
        self.audit_cache_prefix = "mentor_audit"

    def check_access(self, user: People, permission: MentorPermission,
                    request_ip: str = None, endpoint: str = None) -> bool:
        """Check if user has access to a specific mentor feature."""
        try:
            # Log the access attempt
            self._log_access_attempt(user, permission, request_ip, endpoint, granted=None)

            # Basic authentication check
            if not user or not user.is_authenticated:
                self._log_access_attempt(user, permission, request_ip, endpoint, granted=False)
                return False

            # Check if mentor is enabled for this user
            if not self._is_mentor_enabled_for_user(user):
                self._log_access_attempt(user, permission, request_ip, endpoint, granted=False)
                return False

            # Check rate limiting
            if not self._check_rate_limit(user, endpoint):
                self._log_access_attempt(user, permission, request_ip, endpoint, granted=False)
                return False

            # Check specific permission requirements
            has_permission = self._check_permission(user, permission)

            self._log_access_attempt(user, permission, request_ip, endpoint, granted=has_permission)
            return has_permission

        except (ValueError, TypeError) as e:
            print(f"Access control error: {e}")
            # Fail secure - deny access on errors
            self._log_access_attempt(user, permission, request_ip, endpoint, granted=False)
            return False

    def _is_mentor_enabled_for_user(self, user: People) -> bool:
        """Check if AI Mentor is enabled for this specific user."""
        # Check global setting
        if not getattr(settings, 'MENTOR_ENABLED', False):
            return False

        # Check user-specific settings
        user_capabilities = user.capabilities or {}
        mentor_settings = user_capabilities.get('mentor', {})

        # If explicitly disabled for user, deny
        if mentor_settings.get('enabled') is False:
            return False

        # Check if user is in mentor beta group
        if hasattr(user, 'groups'):
            if user.groups.filter(name='mentor_beta_users').exists():
                return True

        # Check if user is staff (staff get access by default when enabled)
        if user.is_staff:
            return True

        # Check if user has any mentor permissions
        mentor_permissions = [perm.value for perm in MentorPermission]
        if user.has_any_perm(mentor_permissions):
            return True

        return False

    def _check_permission(self, user: People, permission: MentorPermission) -> bool:
        """Check if user has specific mentor permission."""
        permission_mapping = {
            MentorPermission.VIEW_MENTOR: SecurityLevel.AUTHENTICATED,
            MentorPermission.USE_PLAN_GENERATOR: SecurityLevel.STAFF,
            MentorPermission.USE_PATCH_GENERATOR: SecurityLevel.TRUSTED,
            MentorPermission.APPLY_PATCHES: SecurityLevel.TRUSTED,
            MentorPermission.USE_TEST_RUNNER: SecurityLevel.STAFF,
            MentorPermission.VIEW_SENSITIVE_CODE: SecurityLevel.TRUSTED,
            MentorPermission.BYPASS_SAFETY_CHECKS: SecurityLevel.ADMIN,
            MentorPermission.ADMIN_MENTOR: SecurityLevel.ADMIN
        }

        required_level = permission_mapping.get(permission, SecurityLevel.STAFF)

        return self._user_meets_security_level(user, required_level)

    def _user_meets_security_level(self, user: People, required_level: SecurityLevel) -> bool:
        """Check if user meets the required security level."""
        if required_level == SecurityLevel.PUBLIC:
            return True

        if required_level == SecurityLevel.AUTHENTICATED:
            return user.is_authenticated

        if required_level == SecurityLevel.STAFF:
            return user.is_staff

        if required_level == SecurityLevel.TRUSTED:
            # Trusted users are staff with mentor permissions
            if not user.is_staff:
                return False

            # Check for trusted mentor group
            if hasattr(user, 'groups') and user.groups.filter(name='mentor_trusted_users').exists():
                return True

            # Check for specific mentor permissions
            trusted_permissions = [
                'mentor.use_patch_generator',
                'mentor.apply_patches',
                'mentor.view_sensitive_code'
            ]

            return any(user.has_perm(perm) for perm in trusted_permissions)

        if required_level == SecurityLevel.ADMIN:
            # Admin users are superusers or mentor admins
            if user.is_superuser:
                return True

            if hasattr(user, 'groups') and user.groups.filter(name='mentor_administrators').exists():
                return True

            return user.has_perm('mentor.admin_mentor')

        return False

    def _check_rate_limit(self, user: People, endpoint: str) -> bool:
        """Check rate limiting for user and endpoint."""
        if not endpoint:
            return True

        # Different rate limits for different endpoints
        rate_limits = {
            '/api/mentor/plan/': {'requests': 10, 'window_minutes': 60},
            '/api/mentor/patch/': {'requests': 5, 'window_minutes': 60},
            '/api/mentor/test/': {'requests': 20, 'window_minutes': 60},
            '/api/mentor/explain/': {'requests': 30, 'window_minutes': 60}
        }

        # Get rate limit for endpoint (default to conservative limit)
        limit_config = rate_limits.get(endpoint, {'requests': 5, 'window_minutes': 60})

        # Check user's current usage
        cache_key = f"{self.rate_limit_cache_prefix}_{user.id}_{endpoint}"
        current_usage = cache.get(cache_key, 0)

        if current_usage >= limit_config['requests']:
            return False

        # Increment usage counter
        cache.set(
            cache_key,
            current_usage + 1,
            timeout=limit_config['window_minutes'] * 60
        )

        return True

    def _log_access_attempt(self, user: Optional[People], permission: MentorPermission,
                          request_ip: str, endpoint: str, granted: Optional[bool]):
        """Log access attempt for audit purposes."""
        attempt = AccessAttempt(
            user_id=user.id if user else None,
            ip_address=request_ip or 'unknown',
            endpoint=endpoint or 'unknown',
            permission_required=permission.value,
            granted=granted if granted is not None else False,
            timestamp=timezone.now()
        )

        # Store in cache (in production, use database)
        audit_key = f"{self.audit_cache_prefix}_{int(time.time())}"
        attempt_data = {
            'user_id': attempt.user_id,
            'ip_address': attempt.ip_address,
            'endpoint': attempt.endpoint,
            'permission_required': attempt.permission_required,
            'granted': attempt.granted,
            'timestamp': attempt.timestamp.isoformat()
        }

        cache.set(audit_key, attempt_data, timeout=7 * 24 * 3600)  # Keep for 7 days

    def get_security_report(self, user_id: Optional[int] = None,
                          hours: int = 24) -> Dict[str, Any]:
        """Generate security report for access attempts."""
        # This is a simplified implementation
        # In production, you'd query the database

        cutoff_time = timezone.now() - timedelta(hours=hours)

        # Get all audit entries from cache
        audit_keys = cache.keys(f"{self.audit_cache_prefix}_*")
        attempts = []

        for key in audit_keys:
            attempt_data = cache.get(key)
            if attempt_data:
                attempt_time = datetime.fromisoformat(attempt_data['timestamp'])
                if attempt_time >= cutoff_time:
                    if user_id is None or attempt_data['user_id'] == user_id:
                        attempts.append(attempt_data)

        # Analyze attempts
        total_attempts = len(attempts)
        granted_attempts = len([a for a in attempts if a['granted']])
        denied_attempts = total_attempts - granted_attempts

        # Group by endpoint
        endpoint_stats = {}
        for attempt in attempts:
            endpoint = attempt['endpoint']
            if endpoint not in endpoint_stats:
                endpoint_stats[endpoint] = {'total': 0, 'granted': 0, 'denied': 0}

            endpoint_stats[endpoint]['total'] += 1
            if attempt['granted']:
                endpoint_stats[endpoint]['granted'] += 1
            else:
                endpoint_stats[endpoint]['denied'] += 1

        # Group by user
        user_stats = {}
        for attempt in attempts:
            user_id = attempt['user_id']
            if user_id not in user_stats:
                user_stats[user_id] = {'total': 0, 'granted': 0, 'denied': 0}

            user_stats[user_id]['total'] += 1
            if attempt['granted']:
                user_stats[user_id]['granted'] += 1
            else:
                user_stats[user_id]['denied'] += 1

        return {
            'period_hours': hours,
            'total_attempts': total_attempts,
            'granted_attempts': granted_attempts,
            'denied_attempts': denied_attempts,
            'success_rate': granted_attempts / total_attempts if total_attempts > 0 else 0,
            'endpoint_breakdown': endpoint_stats,
            'user_breakdown': user_stats,
            'high_risk_indicators': self._identify_high_risk_indicators(attempts)
        }

    def _identify_high_risk_indicators(self, attempts: List[Dict[str, Any]]) -> List[str]:
        """Identify high-risk patterns in access attempts."""
        indicators = []

        # Check for high denial rates
        total_attempts = len(attempts)
        denied_attempts = len([a for a in attempts if not a['granted']])

        if total_attempts > 0:
            denial_rate = denied_attempts / total_attempts
            if denial_rate > 0.3:  # More than 30% denied
                indicators.append(f"High denial rate: {denial_rate:.1%}")

        # Check for repeated denials from same IP
        ip_denials = {}
        for attempt in attempts:
            if not attempt['granted']:
                ip = attempt['ip_address']
                ip_denials[ip] = ip_denials.get(ip, 0) + 1

        for ip, count in ip_denials.items():
            if count > 5:  # More than 5 denials from same IP
                indicators.append(f"Multiple denials from IP {ip}: {count} attempts")

        # Check for attempts on sensitive endpoints
        sensitive_endpoints = ['/api/mentor/patch/', '/api/mentor/admin/']
        sensitive_attempts = [a for a in attempts if any(endpoint in a['endpoint'] for endpoint in sensitive_endpoints)]

        if len(sensitive_attempts) > len(attempts) * 0.5:  # More than 50% on sensitive endpoints
            indicators.append("High proportion of sensitive endpoint access")

        return indicators


class APIKeyManager:
    """Management for API keys with mentor access."""

    def __init__(self):
        self.cache_prefix = "mentor_api_keys"

    def generate_api_key(self, user: People, name: str, permissions: List[MentorPermission],
                        expires_days: int = 365) -> str:
        """Generate a new API key for a user."""
        # Generate secure random key
        key_bytes = secrets.token_bytes(32)
        api_key = f"mentor_{hashlib.sha256(key_bytes).hexdigest()[:32]}"

        # Store key metadata
        key_data = {
            'user_id': user.id,
            'name': name,
            'permissions': [perm.value for perm in permissions],
            'created_at': timezone.now().isoformat(),
            'expires_at': (timezone.now() + timedelta(days=expires_days)).isoformat(),
            'last_used_at': None,
            'usage_count': 0,
            'is_active': True
        }

        cache_key = f"{self.cache_prefix}_{api_key}"
        cache.set(cache_key, key_data, timeout=expires_days * 24 * 3600)

        return api_key

    def validate_api_key(self, api_key: str, required_permission: MentorPermission) -> Optional[People]:
        """Validate API key and check permissions."""
        if not api_key or not api_key.startswith('mentor_'):
            return None

        cache_key = f"{self.cache_prefix}_{api_key}"
        key_data = cache.get(cache_key)

        if not key_data:
            return None

        # Check if key is active
        if not key_data.get('is_active', True):
            return None

        # Check expiration
        expires_at = datetime.fromisoformat(key_data['expires_at'])
        if timezone.now() > expires_at:
            return None

        # Check permissions
        key_permissions = key_data.get('permissions', [])
        if required_permission.value not in key_permissions:
            return None

        # Get user
        try:
            user = People.objects.get(id=key_data['user_id'])
        except People.DoesNotExist:
            return None

        # Update usage statistics
        key_data['last_used_at'] = timezone.now().isoformat()
        key_data['usage_count'] = key_data.get('usage_count', 0) + 1
        cache.set(cache_key, key_data, timeout=None)  # Preserve existing timeout

        return user

    def revoke_api_key(self, api_key: str) -> bool:
        """Revoke an API key."""
        cache_key = f"{self.cache_prefix}_{api_key}"
        key_data = cache.get(cache_key)

        if not key_data:
            return False

        key_data['is_active'] = False
        key_data['revoked_at'] = timezone.now().isoformat()
        cache.set(cache_key, key_data, timeout=None)

        return True

    def list_user_api_keys(self, user: People) -> List[Dict[str, Any]]:
        """List all API keys for a user."""
        # This is a simplified implementation
        # In production, you'd query the database
        user_keys = []

        # Search through cache keys (not efficient for production)
        all_keys = cache.keys(f"{self.cache_prefix}_mentor_*")
        for cache_key in all_keys:
            key_data = cache.get(cache_key)
            if key_data and key_data.get('user_id') == user.id:
                api_key = cache_key.replace(f"{self.cache_prefix}_", "")
                user_keys.append({
                    'api_key': api_key[:16] + '...',  # Masked for security
                    'name': key_data.get('name'),
                    'permissions': key_data.get('permissions', []),
                    'created_at': key_data.get('created_at'),
                    'expires_at': key_data.get('expires_at'),
                    'last_used_at': key_data.get('last_used_at'),
                    'usage_count': key_data.get('usage_count', 0),
                    'is_active': key_data.get('is_active', True)
                })

        return sorted(user_keys, key=lambda k: k['created_at'], reverse=True)


class GroupBasedPermissions:
    """Group-based permission management for mentor features."""

    MENTOR_GROUPS = {
        'mentor_beta_users': {
            'description': 'Beta users testing mentor features',
            'permissions': [
                MentorPermission.VIEW_MENTOR,
                MentorPermission.USE_PLAN_GENERATOR
            ]
        },
        'mentor_developers': {
            'description': 'Developers using mentor for coding assistance',
            'permissions': [
                MentorPermission.VIEW_MENTOR,
                MentorPermission.USE_PLAN_GENERATOR,
                MentorPermission.USE_PATCH_GENERATOR,
                MentorPermission.USE_TEST_RUNNER
            ]
        },
        'mentor_trusted_users': {
            'description': 'Trusted users who can apply patches',
            'permissions': [
                MentorPermission.VIEW_MENTOR,
                MentorPermission.USE_PLAN_GENERATOR,
                MentorPermission.USE_PATCH_GENERATOR,
                MentorPermission.APPLY_PATCHES,
                MentorPermission.USE_TEST_RUNNER,
                MentorPermission.VIEW_SENSITIVE_CODE
            ]
        },
        'mentor_administrators': {
            'description': 'Full mentor system administrators',
            'permissions': list(MentorPermission)
        }
    }

    @classmethod
    def setup_mentor_groups(cls):
        """Set up mentor groups and permissions (run during deployment)."""
        for group_name, group_config in cls.MENTOR_GROUPS.items():
            group, created = Group.objects.get_or_create(name=group_name)

            if created:
                print(f"Created mentor group: {group_name}")

            # Note: In a real implementation, you'd create custom permissions
            # For now, we'll rely on checking group membership directly

    @classmethod
    def add_user_to_group(cls, user: People, group_name: str) -> bool:
        """Add user to a mentor group."""
        if group_name not in cls.MENTOR_GROUPS:
            return False

        try:
            group = Group.objects.get(name=group_name)
            user.groups.add(group)
            return True
        except Group.DoesNotExist:
            return False

    @classmethod
    def remove_user_from_group(cls, user: People, group_name: str) -> bool:
        """Remove user from a mentor group."""
        try:
            group = Group.objects.get(name=group_name)
            user.groups.remove(group)
            return True
        except Group.DoesNotExist:
            return False

    @classmethod
    def get_user_mentor_permissions(cls, user: People) -> List[MentorPermission]:
        """Get all mentor permissions for a user based on group membership."""
        permissions = set()

        for group in user.groups.all():
            group_config = cls.MENTOR_GROUPS.get(group.name)
            if group_config:
                permissions.update(group_config['permissions'])

        return list(permissions)


# Middleware integration
class MentorAccessControlMiddleware:
    """Django middleware for mentor access control."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.access_control = MentorAccessControl()

    def __call__(self, request):
        # Check if this is a mentor API request
        if request.path.startswith('/api/mentor/'):
            self._check_mentor_access(request)

        response = self.get_response(request)
        return response

    def _check_mentor_access(self, request):
        """Check access for mentor API requests."""
        user = getattr(request, 'user', None)

        # Map endpoints to required permissions
        endpoint_permissions = {
            '/api/mentor/plan/': MentorPermission.USE_PLAN_GENERATOR,
            '/api/mentor/patch/': MentorPermission.USE_PATCH_GENERATOR,
            '/api/mentor/test/': MentorPermission.USE_TEST_RUNNER,
            '/api/mentor/explain/': MentorPermission.VIEW_MENTOR,
            '/api/mentor/admin/': MentorPermission.ADMIN_MENTOR
        }

        # Find required permission for this endpoint
        required_permission = None
        for endpoint_prefix, permission in endpoint_permissions.items():
            if request.path.startswith(endpoint_prefix):
                required_permission = permission
                break

        if required_permission:
            # Get client IP
            client_ip = self._get_client_ip(request)

            # Check access
            has_access = self.access_control.check_access(
                user=user,
                permission=required_permission,
                request_ip=client_ip,
                endpoint=request.path
            )

            if not has_access:
                raise PermissionDenied("Access denied to AI Mentor feature")

    def _get_client_ip(self, request) -> str:
        """Get client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR', 'unknown')
        return ip


# Global instances
_access_control = MentorAccessControl()
_api_key_manager = APIKeyManager()

def get_access_control() -> MentorAccessControl:
    """Get global access control instance."""
    return _access_control

def get_api_key_manager() -> APIKeyManager:
    """Get global API key manager instance."""
    return _api_key_manager