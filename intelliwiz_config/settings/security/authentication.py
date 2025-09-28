"""
Authentication and session security configuration.
API authentication, session settings, and environment-specific security policies.
"""

import environ
from .csp import CSP_DIRECTIVES, CSP_MONITORING
from .cors import CORS_ALLOWED_ORIGINS

env = environ.Env()

# API AUTHENTICATION SETTINGS

ENABLE_API_AUTH = True
API_AUTH_PATHS = ["/api/", "/graphql/"]
API_REQUIRE_SIGNING = False

# SESSION SECURITY

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_AGE = 2 * 60 * 60  # 2 hours (Rule #10: Session Security Standards)
SESSION_SAVE_EVERY_REQUEST = True  # Security first (Rule #10)

# PostgreSQL session optimization
DATABASE_SESSION_OPTIMIZATIONS = {
    "USE_INDEX_ON_SESSION_KEY": True,
    "USE_INDEX_ON_EXPIRE_DATE": True,
    "ENABLE_SESSION_CLEANUP": True,
}

# ENVIRONMENT-SPECIFIC SECURITY OVERRIDES

def get_development_security_settings():
    """Security settings for development environment (less restrictive)."""
    return {
        'CSP_REPORT_ONLY': True,
        'ENABLE_API_AUTH': False,
        'ENABLE_RATE_LIMITING': False,
        'CSP_DIRECTIVES': {
            **CSP_DIRECTIVES,
            "script-src": CSP_DIRECTIVES["script-src"] + ["'unsafe-inline'", "'unsafe-eval'"],
            "style-src": CSP_DIRECTIVES["style-src"] + ["'unsafe-inline'"],
            "connect-src": ["'self'", "https:", "ws:", "wss:"]
        },
        'CORS_ALLOWED_ORIGINS': [
            "http://localhost:3000", "http://127.0.0.1:3000",
            "http://localhost:8000", "http://127.0.0.1:8000"
        ] + CORS_ALLOWED_ORIGINS,
        'RATE_LIMIT_MAX_ATTEMPTS': 100
    }

def get_production_security_settings():
    """Security settings for production environment (strict)."""
    return {
        'CSP_REPORT_ONLY': False,
        'ENABLE_API_AUTH': True,
        'ENABLE_RATE_LIMITING': True,
        'API_REQUIRE_SIGNING': env.bool("API_REQUIRE_SIGNING", default=True),
        'CSP_MONITORING': {**CSP_MONITORING, 'MAX_VIOLATION_AGE_DAYS': 90},
        'CSP_DIRECTIVES': {**CSP_DIRECTIVES, "object-src": ["'none'"]},
        'RATE_LIMIT_MAX_ATTEMPTS': 5
    }

def get_test_security_settings():
    """Security settings for test environment (minimal)."""
    return {
        'CSP_REPORT_ONLY': True,
        'ENABLE_API_AUTH': False,
        'ENABLE_RATE_LIMITING': False,
        'CSRF_COOKIE_SECURE': False,
        'SESSION_COOKIE_SECURE': False,
        'SECURE_SSL_REDIRECT': False
    }