"""
Security configuration settings.
CSP, CORS, authentication, rate limiting, and security headers.
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

# CONTENT SECURITY POLICY (CSP) CONFIGURATION

CSP_ENABLE_NONCE = True
CSP_NONCE_LENGTH = 32
CSP_REPORT_ONLY = False
CSP_REPORT_URI = "/api/csp-report/"
CSP_STORE_VIOLATIONS = True

# CSP Monitoring and Directives
CSP_MONITORING = {
    'ENABLE_ALERTING': True, 'ALERT_THRESHOLD_PER_HOUR': 10,
    'ALERT_THRESHOLD_UNIQUE_VIOLATIONS': 5, 'ENABLE_DAILY_REPORTS': True,
    'MAX_VIOLATION_AGE_DAYS': 30, 'BLOCKED_USER_AGENTS': [
        'googlebot', 'bingbot', 'slurp', 'duckduckbot', 'baiduspider',
        'yandexbot', 'facebookexternalhit', 'twitterbot'
    ]
}

CSP_DIRECTIVES = {
    "default-src": ["'self'"], "frame-ancestors": ["'none'"], "base-uri": ["'self'"], "form-action": ["'self'"],
    "script-src": ["'self'", "https://fonts.googleapis.com", "https://ajax.googleapis.com",
                   "https://cdn.jsdelivr.net", "https://cdnjs.cloudflare.com"],
    "style-src": ["'self'", "https://fonts.googleapis.com", "https://cdn.jsdelivr.net", "https://cdnjs.cloudflare.com"],
    "img-src": ["'self'", "data:", "https:", "blob:"],
    "font-src": ["'self'", "data:", "https://fonts.googleapis.com", "https://fonts.gstatic.com",
                 "https://cdn.jsdelivr.net", "https://cdnjs.cloudflare.com"],
    "connect-src": ["'self'", "https:"],
}

# CORS Configuration
CORS_ALLOWED_ORIGINS = ["https://django5.youtility.in"]
CORS_ALLOWED_ORIGIN_REGEXES = [r"^https://\w+\.youtility\.in$"]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ["DELETE", "GET", "OPTIONS", "PATCH", "POST", "PUT"]
CORS_ALLOW_HEADERS = ["accept", "accept-encoding", "authorization", "content-type",
                      "dnt", "origin", "user-agent", "x-csrftoken", "x-requested-with"]
CORS_EXPOSE_HEADERS = ["Content-Type", "X-CSRFToken"]
CORS_PREFLIGHT_MAX_AGE = 86400

# API AUTHENTICATION SETTINGS

ENABLE_API_AUTH = True
API_AUTH_PATHS = ["/api/", "/graphql/"]
API_REQUIRE_SIGNING = False

# RATE LIMITING CONFIGURATION

ENABLE_RATE_LIMITING = True
RATE_LIMIT_WINDOW_MINUTES = 15
RATE_LIMIT_MAX_ATTEMPTS = 5
RATE_LIMIT_PATHS = [
    "/login/",
    "/accounts/login/",
    "/api/",
    "/reset-password/",
    "/password-reset/",
    "/api/upload/",  # File upload endpoints
]

# SESSION SECURITY

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_AGE = 8 * 60 * 60  # 8 hours
SESSION_SAVE_EVERY_REQUEST = False

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
        'CSP_REPORT_ONLY': True, 'ENABLE_API_AUTH': False, 'ENABLE_RATE_LIMITING': False,
        'CSP_DIRECTIVES': {**CSP_DIRECTIVES,
                          "script-src": CSP_DIRECTIVES["script-src"] + ["'unsafe-inline'", "'unsafe-eval'"],
                          "style-src": CSP_DIRECTIVES["style-src"] + ["'unsafe-inline'"],
                          "connect-src": ["'self'", "https:", "ws:", "wss:"]},
        'CORS_ALLOWED_ORIGINS': ["http://localhost:3000", "http://127.0.0.1:3000",
                                "http://localhost:8000", "http://127.0.0.1:8000"] + CORS_ALLOWED_ORIGINS,
        'RATE_LIMIT_MAX_ATTEMPTS': 100
    }

def get_production_security_settings():
    """Security settings for production environment (strict)."""
    return {
        'CSP_REPORT_ONLY': False, 'ENABLE_API_AUTH': True, 'ENABLE_RATE_LIMITING': True,
        'API_REQUIRE_SIGNING': env.bool("API_REQUIRE_SIGNING", default=True),
        'CSP_MONITORING': {**CSP_MONITORING, 'MAX_VIOLATION_AGE_DAYS': 90},
        'CSP_DIRECTIVES': {**CSP_DIRECTIVES, "object-src": ["'none'"]},
        'RATE_LIMIT_MAX_ATTEMPTS': 5
    }

def get_test_security_settings():
    """Security settings for test environment (minimal)."""
    return {
        'CSP_REPORT_ONLY': True, 'ENABLE_API_AUTH': False, 'ENABLE_RATE_LIMITING': False,
        'CSRF_COOKIE_SECURE': False, 'SESSION_COOKIE_SECURE': False, 'SECURE_SSL_REDIRECT': False
    }

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

# SECURITY MIDDLEWARE CONFIGURATION

SECURITY_MIDDLEWARE = [
    'apps.core.error_handling.CorrelationIDMiddleware',
    'apps.core.sql_security.SQLInjectionProtectionMiddleware',
    'apps.core.middleware.file_upload_security_middleware.FileUploadSecurityMiddleware',  # File upload security (CVSS 8.1 fix)
    'apps.core.xss_protection.XSSProtectionMiddleware',
    'apps.core.middleware.csp_nonce.CSPNonceMiddleware',
    'apps.core.xss_protection.CSRFHeaderMiddleware',
    'apps.core.error_handling.GlobalExceptionMiddleware',
]

# GRAPHQL SECURITY CONFIGURATION (CVSS 8.1 vulnerability fix)

# GraphQL endpoint paths that require CSRF protection
GRAPHQL_PATHS = [
    '/api/graphql/',
    '/graphql/',
    '/graphql'
]

# GraphQL-specific rate limiting
ENABLE_GRAPHQL_RATE_LIMITING = True
GRAPHQL_RATE_LIMIT_WINDOW = 300  # 5 minutes
GRAPHQL_RATE_LIMIT_MAX = 100     # Max requests per window

# GraphQL query complexity limits
GRAPHQL_MAX_QUERY_DEPTH = 10
GRAPHQL_MAX_QUERY_COMPLEXITY = 1000

# GraphQL introspection settings
GRAPHQL_DISABLE_INTROSPECTION_IN_PRODUCTION = True

# GraphQL CSRF protection settings
GRAPHQL_CSRF_HEADER_NAMES = [
    'HTTP_X_CSRFTOKEN',
    'HTTP_X_CSRF_TOKEN',
]

# GraphQL security logging
GRAPHQL_SECURITY_LOGGING = {
    'ENABLE_REQUEST_LOGGING': True,
    'ENABLE_MUTATION_LOGGING': True,
    'ENABLE_RATE_LIMIT_LOGGING': True,
    'LOG_FAILED_CSRF_ATTEMPTS': True,
}

# GraphQL origin validation
GRAPHQL_ALLOWED_ORIGINS = env.list('GRAPHQL_ALLOWED_ORIGINS', default=[])
GRAPHQL_STRICT_ORIGIN_VALIDATION = env.bool('GRAPHQL_STRICT_ORIGIN_VALIDATION', default=False)

# FILE UPLOAD SECURITY CONFIGURATION (CVSS 8.1 vulnerability fix)

# File upload rate limiting (more restrictive than general API rate limits)
FILE_UPLOAD_RATE_LIMITING = {
    'ENABLE': True,
    'WINDOW_MINUTES': 5,     # Shorter window for file uploads
    'MAX_ATTEMPTS': 10,      # Lower max attempts
    'MAX_SIZE_PER_WINDOW': 50 * 1024 * 1024,  # 50MB total per window
}

# File upload paths that require additional security
FILE_UPLOAD_PATHS = [
    '/api/upload/att_file/',
    '/api/upload/',
]

# File upload CSRF protection
FILE_UPLOAD_CSRF_PROTECTION = {
    'ENABLE': True,
    'REQUIRE_CSRF_TOKEN': True,
    'ALLOWED_CONTENT_TYPES': [
        'multipart/form-data',
        'application/octet-stream',
    ]
}

# File upload monitoring and alerting
FILE_UPLOAD_MONITORING = {
    'ENABLE_UPLOAD_LOGGING': True,
    'ENABLE_SECURITY_ALERTING': True,
    'LOG_VALIDATION_FAILURES': True,
    'LOG_PATH_TRAVERSAL_ATTEMPTS': True,
    'LOG_OVERSIZED_UPLOADS': True,
    'ALERT_ON_SUSPICIOUS_UPLOADS': True,
    'MAX_FAILED_UPLOADS_PER_USER': 5,
    'FAILED_UPLOAD_WINDOW_MINUTES': 10,
}

# File upload content security
FILE_UPLOAD_CONTENT_SECURITY = {
    'ENABLE_MAGIC_NUMBER_VALIDATION': True,
    'ENABLE_FILENAME_SANITIZATION': True,
    'ENABLE_PATH_TRAVERSAL_PROTECTION': True,
    'ENABLE_MALWARE_SCANNING': env.bool('ENABLE_MALWARE_SCANNING', default=False),
    'QUARANTINE_SUSPICIOUS_FILES': True,
}

# File upload size and type restrictions per user role
FILE_UPLOAD_RESTRICTIONS = {
    'admin': {
        'max_file_size': 100 * 1024 * 1024,  # 100MB
        'allowed_types': ['image', 'pdf', 'document', 'archive'],
        'max_files_per_day': 1000,
    },
    'staff': {
        'max_file_size': 50 * 1024 * 1024,   # 50MB
        'allowed_types': ['image', 'pdf', 'document'],
        'max_files_per_day': 500,
    },
    'user': {
        'max_file_size': 10 * 1024 * 1024,   # 10MB
        'allowed_types': ['image', 'pdf'],
        'max_files_per_day': 100,
    }
}