"""
Middleware Configuration

Centralized middleware stack configuration.
Extracted from base.py for Rule #6 compliance.

Middleware Order (CRITICAL):
1. Security middleware (first line of defense)
2. Correlation ID and logging
3. Rate limiting and DoS protection
4. SQL injection and XSS protection
5. Session and tenant middleware
6. CSRF protection
7. Authentication
8. Application middleware

Django Best Practice: Programmatically enforce middleware ordering.

Author: Claude Code
Date: 2025-10-01
"""

from django.core.exceptions import ImproperlyConfigured

# Base middleware configuration
# Order is CRITICAL for security and functionality
MIDDLEWARE = [
    # ========================================================================
    # Layer 1: Core Security (Must be first)
    # ========================================================================
    "django.middleware.security.SecurityMiddleware",

    # ========================================================================
    # Layer 2: Request Tracking and Logging
    # ========================================================================
    "apps.core.error_handling.CorrelationIDMiddleware",
    "apps.core.middleware.tracing_middleware.TracingMiddleware",  # OTEL distributed tracing
    "apps.core.middleware.logging_sanitization.LogSanitizationMiddleware",
    "apps.core.middleware.api_deprecation.APIDeprecationMiddleware",

    # ========================================================================
    # Layer 3: Rate Limiting and DoS Protection
    # ========================================================================
    "apps.core.middleware.path_based_rate_limiting.PathBasedRateLimitMiddleware",
    "apps.core.middleware.path_based_rate_limiting.RateLimitMonitoringMiddleware",

    # ========================================================================
    # Layer 4: Input Validation and Attack Prevention
    # ========================================================================
    "apps.core.middleware.input_sanitization_middleware.InputSanitizationMiddleware",  # XSS/Injection prevention (Nov 2025)
    "apps.core.sql_security.SQLInjectionProtectionMiddleware",
    "apps.core.xss_protection.XSSProtectionMiddleware",

    # ========================================================================
    # Layer 5: Session and Multi-Tenancy
    # ========================================================================
    "django.contrib.sessions.middleware.SessionMiddleware",

    # Layer 5.5: Cache Security
    "apps.core.middleware.cache_security_middleware.CacheSecurityMiddleware",

    "waffle.middleware.WaffleMiddleware",
    "apps.tenants.middleware_unified.UnifiedTenantMiddleware",  # CRITICAL: Must be after SessionMiddleware
    "django.middleware.locale.LocaleMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "apps.core.middleware.timezone_middleware.TimezoneMiddleware",

    # ========================================================================
    # Layer 6: Content Security and Static Files
    # ========================================================================
    "apps.core.middleware.csp_nonce.CSPNonceMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",

    # ========================================================================
    # Layer 7: CSRF Protection
    # ========================================================================
    "django.middleware.csrf.CsrfViewMiddleware",

    # ========================================================================
    # Layer 8: File Upload Security
    # ========================================================================
    "apps.core.middleware.file_upload_security_middleware.FileUploadSecurityMiddleware",  # Rule #14 compliance

    # ========================================================================
    # Layer 9: Authentication and Authorization
    # ========================================================================
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Removed: apps.onboarding_api middleware (orphaned app, not in INSTALLED_APPS)
    # See: apps/onboarding_api/DEPRECATION_NOTICE.md
    "apps.attendance.middleware.AttendanceAuditMiddleware",  # Attendance access audit logging (Nov 2025)

    # ========================================================================
    # Layer 10: Application Middleware
    # ========================================================================
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    'apps.core.xss_protection.CSRFHeaderMiddleware',

    # ========================================================================
    # Layer 10.5: PII Protection (NEW - 2025-10-01)
    # ========================================================================
    "apps.journal.middleware.pii_redaction_middleware.JournalPIIRedactionMiddleware",
    "apps.wellness.middleware.pii_redaction_middleware.WellnessPIIRedactionMiddleware",
    "apps.journal.exceptions.pii_safe_exception_handler.PIISafeExceptionMiddleware",

    # ========================================================================
    # Layer 11: Error Handling (Must be last)
    # ========================================================================
    "apps.core.error_handling.GlobalExceptionMiddleware",
]

# Middleware configuration notes
MIDDLEWARE_NOTES = """
CRITICAL MIDDLEWARE ORDERING RULES:

1. SecurityMiddleware MUST be first (sets security headers)
2. CorrelationIDMiddleware MUST be second (request tracking)
3. Rate limiting MUST come before origin validation
4. Origin validation MUST come before SQL injection protection
5. SQL/XSS protection MUST come before CSRF
6. SessionMiddleware MUST come before UnifiedTenantMiddleware
7. UnifiedTenantMiddleware MUST come before any DB access
8. CsrfViewMiddleware MUST come before AuthenticationMiddleware
9. GlobalExceptionMiddleware MUST be last (catch-all error handler)

PII PROTECTION (2025-10-01): Added Journal and Wellness PII redaction middleware
to automatically sanitize API responses and protect sensitive user data. These
middleware components intercept responses and redact PII based on user permissions.

OBSERVABILITY ENHANCEMENT (2025-10-01): Added OTEL distributed tracing middleware:
- TracingMiddleware: Creates spans for all HTTP requests with timing and attributes
- These middleware integrate with Jaeger for distributed tracing and correlation ID propagation.

DO NOT change middleware order without security team approval!
"""

def validate_middleware_order():
    """
    Enforce critical middleware ordering constraints.

    Raises:
        ImproperlyConfigured: If middleware ordering violates security/functional requirements

    Django Best Practice: Programmatically validate middleware order to prevent
    configuration errors that could introduce security vulnerabilities.

    Date: 2025-11-12
    """
    # Define critical ordering constraints
    # Format: (middleware_class, expected_position, error_message)
    constraints = [
        (
            'django.middleware.security.SecurityMiddleware',
            0,
            "SecurityMiddleware must be first (sets security headers before any processing)"
        ),
        (
            'apps.core.error_handling.CorrelationIDMiddleware',
            1,
            "CorrelationIDMiddleware must be second (request tracking before any business logic)"
        ),
        (
            'django.contrib.sessions.middleware.SessionMiddleware',
            None,  # Just validate presence, not position
            "SessionMiddleware is required for tenant middleware and authentication"
        ),
        (
            'apps.core.error_handling.GlobalExceptionMiddleware',
            -1,  # Last position
            "GlobalExceptionMiddleware must be last (catch-all error handler)"
        ),
    ]

    # Validate constraints
    for middleware_class, expected_pos, error_msg in constraints:
        if expected_pos is None:
            # Just check presence
            if middleware_class not in MIDDLEWARE:
                raise ImproperlyConfigured(
                    f"MIDDLEWARE configuration error: {error_msg}"
                )
        else:
            # Check specific position
            try:
                if MIDDLEWARE[expected_pos] != middleware_class:
                    raise ImproperlyConfigured(
                        f"MIDDLEWARE order violation at position {expected_pos}: {error_msg}\n"
                        f"Expected: {middleware_class}\n"
                        f"Found: {MIDDLEWARE[expected_pos]}"
                    )
            except IndexError:
                raise ImproperlyConfigured(
                    f"MIDDLEWARE list too short: {error_msg}\n"
                    f"Expected {middleware_class} at position {expected_pos}"
                )

    # Validate relative ordering (A must come before B)
    relative_constraints = [
        (
            'django.contrib.sessions.middleware.SessionMiddleware',
            'apps.tenants.middleware_unified.UnifiedTenantMiddleware',
            "SessionMiddleware must come before UnifiedTenantMiddleware (tenant needs session)"
        ),
        (
            'apps.tenants.middleware_unified.UnifiedTenantMiddleware',
            'django.contrib.auth.middleware.AuthenticationMiddleware',
            "UnifiedTenantMiddleware must come before AuthenticationMiddleware (auth needs tenant context)"
        ),
        (
            'django.middleware.csrf.CsrfViewMiddleware',
            'django.contrib.auth.middleware.AuthenticationMiddleware',
            "CsrfViewMiddleware must come before AuthenticationMiddleware"
        ),
    ]

    for before_mw, after_mw, error_msg in relative_constraints:
        try:
            before_idx = MIDDLEWARE.index(before_mw)
            after_idx = MIDDLEWARE.index(after_mw)
            if before_idx >= after_idx:
                raise ImproperlyConfigured(
                    f"MIDDLEWARE relative order violation: {error_msg}\n"
                    f"{before_mw} at position {before_idx}\n"
                    f"{after_mw} at position {after_idx}"
                )
        except ValueError as e:
            raise ImproperlyConfigured(
                f"MIDDLEWARE configuration error: {error_msg}\n"
                f"Missing middleware: {str(e)}"
            )


# Validate middleware order on settings load
# This ensures configuration errors are caught at startup, not at runtime
validate_middleware_order()


__all__ = [
    'MIDDLEWARE',
    'MIDDLEWARE_NOTES',
    'validate_middleware_order',
]
