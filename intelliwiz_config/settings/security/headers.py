"""
Security headers and core security settings.
SSL/HSTS, security cookies, and basic security headers configuration.
"""

import environ

env = environ.Env()

# CORE SECURITY SETTINGS

# ============================================================================
# COOKIE SECURITY CONFIGURATION (CENTRALIZED)
# ============================================================================
# All cookie security settings are centralized here to prevent configuration drift.
# Environment-specific overrides can be done in development.py/production.py.
# ============================================================================

# CSRF Cookie Security
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=False)  # Override: True in production
CSRF_COOKIE_HTTPONLY = True  # Prevent JavaScript access
CSRF_COOKIE_SAMESITE = "Lax"  # CSRF protection

# Session Cookie Security
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=False)  # Override: True in production
SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript access
SESSION_COOKIE_SAMESITE = "Lax"  # Session hijacking protection

# Language Cookie Security (i18n/l10n)
LANGUAGE_COOKIE_NAME = 'django_language'
LANGUAGE_COOKIE_AGE = 60 * 60 * 24 * 365  # 1 year
LANGUAGE_COOKIE_DOMAIN = None  # Use default domain
LANGUAGE_COOKIE_PATH = '/'
LANGUAGE_COOKIE_SECURE = env.bool("LANGUAGE_COOKIE_SECURE", default=False)  # Override: True in production
LANGUAGE_COOKIE_HTTPONLY = True  # CHANGED: Prevent XSS attacks on language preference (was False)
LANGUAGE_COOKIE_SAMESITE = 'Lax'  # CSRF protection

# NOTE: LANGUAGE_COOKIE_HTTPONLY changed from False to True for security.
# If client-side language switching is needed, use a server-side endpoint instead.
# Recommendation: /api/set-language/ endpoint for language changes

# Language Session Key
LANGUAGE_SESSION_KEY = 'django_language'

# SSL/TLS Redirect
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=False)  # Override: True in production

# HSTS settings (when SSL is enabled)
if env.bool("SECURE_SSL_REDIRECT", default=False):
    SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# Additional security headers
if env.bool("ENABLE_SECURITY_HEADERS", default=False):
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# Security headers settings
REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"
PERMISSIONS_POLICY = {
    "geolocation": "()",
    "camera": "()",
    "microphone": "()",
    "payment": "()",
    "usb": "()",
}

# Security reporting
SECURITY_REPORT_URI = "/api/security-report/"
NEL_REPORT_URI = "/api/nel-report/"

# ============================================================================
# EXPLICIT EXPORTS (Rule #16: No Uncontrolled Wildcard Imports)
# ============================================================================

__all__ = [
    # CSRF Cookie Security
    'CSRF_COOKIE_SECURE',
    'CSRF_COOKIE_HTTPONLY',
    'CSRF_COOKIE_SAMESITE',

    # Session Cookie Security
    'SESSION_COOKIE_SECURE',
    'SESSION_COOKIE_HTTPONLY',
    'SESSION_COOKIE_SAMESITE',

    # Language Cookie Security
    'LANGUAGE_COOKIE_NAME',
    'LANGUAGE_COOKIE_AGE',
    'LANGUAGE_COOKIE_DOMAIN',
    'LANGUAGE_COOKIE_PATH',
    'LANGUAGE_COOKIE_SECURE',
    'LANGUAGE_COOKIE_HTTPONLY',
    'LANGUAGE_COOKIE_SAMESITE',
    'LANGUAGE_SESSION_KEY',

    # SSL/TLS Configuration
    'SECURE_SSL_REDIRECT',

    # Security Headers
    'REFERRER_POLICY',
    'X_FRAME_OPTIONS',
    'PERMISSIONS_POLICY',

    # Security Reporting
    'SECURITY_REPORT_URI',
    'NEL_REPORT_URI',
]