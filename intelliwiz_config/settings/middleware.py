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

Author: Claude Code
Date: 2025-10-01
"""

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
    "apps.core.sql_security.SQLInjectionProtectionMiddleware",
    "apps.core.xss_protection.XSSProtectionMiddleware",

    # ========================================================================
    # Layer 5: Session and Multi-Tenancy
    # ========================================================================
    "django.contrib.sessions.middleware.SessionMiddleware",
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
    "apps.onboarding_api.middleware.OnboardingAPIMiddleware",
    "apps.onboarding_api.middleware.OnboardingAuditMiddleware",
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

__all__ = [
    'MIDDLEWARE',
    'MIDDLEWARE_NOTES',
]
