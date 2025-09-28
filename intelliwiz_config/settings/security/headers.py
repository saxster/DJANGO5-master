"""
Security headers and core security settings.
SSL/HSTS, security cookies, and basic security headers configuration.
"""

import environ

env = environ.Env()

# CORE SECURITY SETTINGS

# Security cookies and redirects
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=False)
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=False)
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=False)
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

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