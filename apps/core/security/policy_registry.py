"""
Security Policy Registry

Centralized security policy validation and startup checks.

Features:
- Validate all security configurations at startup
- Detect configuration drift from recommended settings
- Health check endpoint for monitoring
- Comprehensive policy documentation
- Integration with Django system checks framework

Policies Validated:
1. Rate limiting configurations
2. CSRF protection status
3. SQL security patterns
4. Session security
5. Middleware ordering
6. Secret validation

Author: Claude Code
Date: 2025-10-01
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from django.conf import settings
from django.core.checks import Error, Warning as DjangoWarning, register
from django.http import JsonResponse, HttpRequest
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone

logger = logging.getLogger('security.policy_registry')


class PolicySeverity(Enum):
    """Security policy violation severity levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class SecurityPolicy:
    """Represents a single security policy"""
    name: str
    category: str
    severity: PolicySeverity
    description: str
    check_function: callable
    remediation: str
    enabled: bool = True
    tags: List[str] = field(default_factory=list)


@dataclass
class PolicyViolation:
    """Represents a policy violation"""
    policy_name: str
    severity: PolicySeverity
    message: str
    current_value: Any
    recommended_value: Any
    remediation: str
    timestamp: str


class SecurityPolicyRegistry:
    """
    Central registry for all security policies.

    Validates security configurations and provides health checks.
    """

    def __init__(self):
        self.policies: Dict[str, SecurityPolicy] = {}
        self._register_default_policies()

    def _register_default_policies(self):
        """Register all default security policies"""

        # Rate Limiting Policies
        self.register(SecurityPolicy(
            name="comprehensive_rate_limiting",
            category="Rate Limiting",
            severity=PolicySeverity.HIGH,
            description="All public endpoints must have rate limiting",
            check_function=self._check_comprehensive_rate_limiting,
            remediation="Ensure RATE_LIMIT_PATHS includes /api/, /admin/, /login/",
            tags=["rate-limiting", "brute-force-prevention"]
        ))

        # CSRF Protection Policies
        self.register(SecurityPolicy(
            name="csrf_middleware_enabled",
            category="CSRF Protection",
            severity=PolicySeverity.CRITICAL,
            description="CSRF middleware must be enabled",
            check_function=self._check_csrf_middleware,
            remediation="Add 'django.middleware.csrf.CsrfViewMiddleware' to MIDDLEWARE",
            tags=["csrf", "session-security"]
        ))

        # SQL Security Policies
        self.register(SecurityPolicy(
            name="sql_injection_middleware_enabled",
            category="SQL Security",
            severity=PolicySeverity.HIGH,
            description="SQL injection protection middleware must be enabled",
            check_function=self._check_sql_injection_middleware,
            remediation="Add SQLInjectionProtectionMiddleware to MIDDLEWARE",
            tags=["sql-injection", "input-validation"]
        ))

        self.register(SecurityPolicy(
            name="sql_security_body_size_limit",
            category="SQL Security",
            severity=PolicySeverity.MEDIUM,
            description="SQL security should have reasonable body size limits",
            check_function=self._check_sql_body_size_limit,
            remediation="Set SQL_SECURITY_MAX_BODY_SIZE (recommended: 1MB)",
            tags=["sql-injection", "dos-prevention"]
        ))

        # Session Security Policies
        self.register(SecurityPolicy(
            name="session_cookie_secure",
            category="Session Security",
            severity=PolicySeverity.CRITICAL,
            description="Session cookies must be secure (HTTPS only) in production",
            check_function=self._check_session_cookie_secure,
            remediation="Set SESSION_COOKIE_SECURE = True in production",
            tags=["session", "https", "production"]
        ))

        self.register(SecurityPolicy(
            name="session_cookie_httponly",
            category="Session Security",
            severity=PolicySeverity.HIGH,
            description="Session cookies must be HTTPOnly (no JavaScript access)",
            check_function=self._check_session_cookie_httponly,
            remediation="Set SESSION_COOKIE_HTTPONLY = True",
            tags=["session", "xss-prevention"]
        ))

        # Middleware Ordering Policies
        self.register(SecurityPolicy(
            name="security_middleware_ordering",
            category="Middleware",
            severity=PolicySeverity.MEDIUM,
            description="Security middleware must be in correct order",
            check_function=self._check_middleware_ordering,
            remediation="Ensure security middleware comes before application middleware",
            tags=["middleware", "configuration"]
        ))

        # Secret Management Policies
        self.register(SecurityPolicy(
            name="secret_key_strength",
            category="Secrets",
            severity=PolicySeverity.CRITICAL,
            description="SECRET_KEY must be strong (50+ characters)",
            check_function=self._check_secret_key_strength,
            remediation="Generate a strong SECRET_KEY with cryptographic randomness",
            tags=["secrets", "cryptography"]
        ))

    def register(self, policy: SecurityPolicy):
        """Register a security policy"""
        self.policies[policy.name] = policy
        logger.info(f"Registered security policy: {policy.name}")

    def validate_all(self) -> Tuple[List[PolicyViolation], List[SecurityPolicy]]:
        """
        Validate all enabled policies.

        Returns:
            Tuple of (violations, passed_policies)
        """
        violations = []
        passed = []

        for policy_name, policy in self.policies.items():
            if not policy.enabled:
                continue

            try:
                is_valid, message, current_value, recommended_value = policy.check_function()

                if not is_valid:
                    violation = PolicyViolation(
                        policy_name=policy.name,
                        severity=policy.severity,
                        message=message,
                        current_value=current_value,
                        recommended_value=recommended_value,
                        remediation=policy.remediation,
                        timestamp=timezone.now().isoformat()
                    )
                    violations.append(violation)
                    logger.warning(
                        f"Policy violation: {policy.name} - {message}",
                        extra={'policy': policy_name, 'severity': policy.severity.value}
                    )
                else:
                    passed.append(policy)

            except (ValueError, TypeError, AttributeError) as e:
                logger.error(
                    f"Error checking policy {policy_name}: {e}",
                    exc_info=True,
                    extra={'policy': policy_name}
                )

        return violations, passed

    # ========================================================================
    # Policy Check Functions
    # ========================================================================

    def _check_comprehensive_rate_limiting(self) -> Tuple[bool, str, Any, Any]:
        """Check if rate limiting covers all critical paths"""
        rate_limit_paths = getattr(settings, 'RATE_LIMIT_PATHS', [])

        required_paths = ['/api/', '/admin/', '/login/']
        missing_paths = [path for path in required_paths if not any(
            path.startswith(rl_path) or rl_path.startswith(path)
            for rl_path in rate_limit_paths
        )]

        if missing_paths:
            return (
                False,
                f"Rate limiting missing for critical paths: {missing_paths}",
                rate_limit_paths,
                required_paths
            )

        return (True, "Comprehensive rate limiting enabled", True, True)

    def _check_csrf_middleware(self) -> Tuple[bool, str, Any, Any]:
        """Check if CSRF middleware is enabled"""
        middleware_classes = settings.MIDDLEWARE

        if 'django.middleware.csrf.CsrfViewMiddleware' not in middleware_classes:
            return (
                False,
                "CSRF middleware not enabled - critical security risk",
                False,
                True
            )

        return (True, "CSRF middleware enabled", True, True)

    def _check_sql_injection_middleware(self) -> Tuple[bool, str, Any, Any]:
        """Check if SQL injection protection is enabled"""
        middleware_classes = settings.MIDDLEWARE

        if 'apps.core.sql_security.SQLInjectionProtectionMiddleware' not in middleware_classes:
            return (
                False,
                "SQL injection protection middleware not enabled",
                False,
                True
            )

        return (True, "SQL injection protection enabled", True, True)

    def _check_sql_body_size_limit(self) -> Tuple[bool, str, Any, Any]:
        """Check if SQL security has reasonable body size limits"""
        max_body_size = getattr(settings, 'SQL_SECURITY_MAX_BODY_SIZE', None)

        if not max_body_size:
            return (
                False,
                "SQL security body size limit not configured",
                None,
                1048576  # 1MB
            )

        if max_body_size > 10485760:  # 10MB
            return (
                False,
                f"SQL security body size limit too high: {max_body_size} bytes",
                max_body_size,
                1048576
            )

        return (True, "SQL security body size limit properly configured", max_body_size, 1048576)

    def _check_session_cookie_secure(self) -> Tuple[bool, str, Any, Any]:
        """Check if session cookies are secure in production"""
        is_production = not settings.DEBUG
        session_cookie_secure = getattr(settings, 'SESSION_COOKIE_SECURE', False)

        if is_production and not session_cookie_secure:
            return (
                False,
                "SESSION_COOKIE_SECURE must be True in production",
                session_cookie_secure,
                True
            )

        return (True, "Session cookie security properly configured", True, True)

    def _check_session_cookie_httponly(self) -> Tuple[bool, str, Any, Any]:
        """Check if session cookies are HTTPOnly"""
        session_cookie_httponly = getattr(settings, 'SESSION_COOKIE_HTTPONLY', False)

        if not session_cookie_httponly:
            return (
                False,
                "SESSION_COOKIE_HTTPONLY should be True to prevent XSS attacks",
                session_cookie_httponly,
                True
            )

        return (True, "Session cookie HTTPOnly properly configured", True, True)

    def _check_middleware_ordering(self) -> Tuple[bool, str, Any, Any]:
        """Check if security middleware is in correct order"""
        middleware_classes = settings.MIDDLEWARE

        # Security middleware should come early
        security_middleware = [
            'django.middleware.security.SecurityMiddleware',
            'apps.core.sql_security.SQLInjectionProtectionMiddleware',
            'apps.core.xss_protection.XSSProtectionMiddleware',
        ]

        # Find position of first application middleware
        app_middleware_idx = None
        for idx, middleware in enumerate(middleware_classes):
            if middleware.startswith('apps.') and not any(
                sec_mw in middleware for sec_mw in security_middleware
            ):
                app_middleware_idx = idx
                break

        if app_middleware_idx is None:
            return (True, "Middleware ordering acceptable", True, True)

        # Check all security middleware comes before application middleware
        for sec_middleware in security_middleware:
            if sec_middleware in middleware_classes:
                sec_idx = middleware_classes.index(sec_middleware)
                if sec_idx > app_middleware_idx:
                    return (
                        False,
                        f"{sec_middleware} should come before application middleware",
                        sec_idx,
                        app_middleware_idx
                    )

        return (True, "Middleware ordering correct", True, True)

    def _check_secret_key_strength(self) -> Tuple[bool, str, Any, Any]:
        """Check if SECRET_KEY is strong enough"""
        secret_key = getattr(settings, 'SECRET_KEY', '')

        if len(secret_key) < 50:
            return (
                False,
                f"SECRET_KEY too short: {len(secret_key)} characters (minimum: 50)",
                len(secret_key),
                50
            )

        # Check for common patterns (testing keys)
        weak_patterns = ['django-insecure-', 'test', 'development', '1234']
        if any(pattern in secret_key.lower() for pattern in weak_patterns):
            return (
                False,
                "SECRET_KEY appears to be a weak/test key",
                "weak",
                "strong"
            )

        return (True, "SECRET_KEY strength acceptable", len(secret_key), 50)


# Singleton instance
policy_registry = SecurityPolicyRegistry()


# ============================================================================
# Django System Checks Integration
# ============================================================================

@register()
def check_security_policies(app_configs, **kwargs):
    """
    Django system check for security policies.

    Run with: python manage.py check
    """
    errors = []
    warnings = []

    violations, _ = policy_registry.validate_all()

    for violation in violations:
        if violation.severity in [PolicySeverity.CRITICAL, PolicySeverity.HIGH]:
            errors.append(Error(
                f"{violation.policy_name}: {violation.message}",
                hint=violation.remediation,
                id=f'security.{violation.policy_name}'
            ))
        else:
            warnings.append(DjangoWarning(
                f"{violation.policy_name}: {violation.message}",
                hint=violation.remediation,
                id=f'security.{violation.policy_name}'
            ))

    return errors + warnings


# ============================================================================
# API Views
# ============================================================================

@staff_member_required
def security_policy_status(request: HttpRequest) -> JsonResponse:
    """
    API endpoint for security policy status.

    Returns JSON with all policy violations and passed checks.
    """
    violations, passed = policy_registry.validate_all()

    response_data = {
        'timestamp': timezone.now().isoformat(),
        'total_policies': len(policy_registry.policies),
        'violations_count': len(violations),
        'passed_count': len(passed),
        'violations': [
            {
                'policy_name': v.policy_name,
                'severity': v.severity.value,
                'message': v.message,
                'current_value': str(v.current_value),
                'recommended_value': str(v.recommended_value),
                'remediation': v.remediation
            }
            for v in violations
        ],
        'passed': [
            {
                'policy_name': p.name,
                'category': p.category,
                'description': p.description
            }
            for p in passed
        ],
        'summary_by_severity': _get_violations_by_severity(violations),
        'summary_by_category': _get_violations_by_category(violations)
    }

    return JsonResponse(response_data)


def _get_violations_by_severity(violations: List[PolicyViolation]) -> Dict[str, int]:
    """Group violations by severity"""
    summary = {severity.value: 0 for severity in PolicySeverity}

    for violation in violations:
        summary[violation.severity.value] += 1

    return summary


def _get_violations_by_category(violations: List[PolicyViolation]) -> Dict[str, int]:
    """Group violations by category"""
    summary = {}

    for violation in violations:
        policy = policy_registry.policies.get(violation.policy_name)
        if policy:
            category = policy.category
            summary[category] = summary.get(category, 0) + 1

    return summary
