"""
Security validation utilities.
Validates security configuration settings and checks for common issues.
"""

from .headers import SECURE_SSL_REDIRECT, CSRF_COOKIE_SECURE, SESSION_COOKIE_SECURE
from .csp import CSP_ENABLE_NONCE, CSP_DIRECTIVES
from .authentication import ENABLE_API_AUTH, API_AUTH_PATHS

# SECURITY VALIDATION

def validate_security_settings():
    """Validate security configuration."""
    errors, warnings = [], []

    if SECURE_SSL_REDIRECT and (not CSRF_COOKIE_SECURE or not SESSION_COOKIE_SECURE):
        errors.append("SSL redirect enabled but secure cookies not configured")

    if not CSP_ENABLE_NONCE and "'unsafe-inline'" in CSP_DIRECTIVES.get("script-src", []):
        warnings.append("CSP allows unsafe-inline scripts without nonce protection")

    if not ENABLE_API_AUTH and "/api/" in API_AUTH_PATHS:
        warnings.append("API authentication disabled but API paths configured")

    return {'errors': errors, 'warnings': warnings}