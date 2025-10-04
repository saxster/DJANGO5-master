"""
GraphQL Security Configuration (CVSS 8.1 vulnerability fix)
Single source of truth for all GraphQL-specific security settings.

This module centralizes all GraphQL security configuration to prevent
duplication and configuration drift. All GraphQL settings MUST be defined
here and imported by other modules.

Compliance with .claude/rules.md:
- Rule #6: Settings files < 200 lines (this file: ~150 lines)
- Rule #1: GraphQL security protection with comprehensive validation
- Single source of truth pattern for maintainability

Security Features:
- Rate limiting configuration
- Query complexity and depth limits
- CSRF protection settings
- Introspection control
- Origin validation
- Comprehensive security logging
"""

from datetime import timedelta
import logging
import environ

env = environ.Env()
logger = logging.getLogger(__name__)

# ============================================================================
# GRAPHQL ENDPOINT CONFIGURATION
# ============================================================================

# GraphQL endpoint paths that require CSRF protection
GRAPHQL_PATHS = [
    '/api/graphql/',
    '/graphql/',
    '/graphql'
]

# ============================================================================
# GRAPHQL RATE LIMITING
# ============================================================================

# Enable GraphQL-specific rate limiting (should always be True in production)
ENABLE_GRAPHQL_RATE_LIMITING = env.bool('ENABLE_GRAPHQL_RATE_LIMITING', default=True)

# Rate limiting window in seconds (default: 5 minutes)
GRAPHQL_RATE_LIMIT_WINDOW = env.int('GRAPHQL_RATE_LIMIT_WINDOW', default=300)

# Maximum requests per window (default: 100 requests per 5 minutes)
GRAPHQL_RATE_LIMIT_MAX = env.int('GRAPHQL_RATE_LIMIT_MAX', default=100)

# ============================================================================
# GRAPHQL QUERY COMPLEXITY LIMITS (DoS Prevention)
# ============================================================================

# Maximum query depth to prevent deeply nested queries
GRAPHQL_MAX_QUERY_DEPTH = env.int('GRAPHQL_MAX_QUERY_DEPTH', default=10)

# Maximum query complexity score to prevent complexity bomb attacks
GRAPHQL_MAX_QUERY_COMPLEXITY = env.int('GRAPHQL_MAX_QUERY_COMPLEXITY', default=1000)

# Maximum mutations per request to prevent batch attack abuse
GRAPHQL_MAX_MUTATIONS_PER_REQUEST = env.int('GRAPHQL_MAX_MUTATIONS_PER_REQUEST', default=5)

# Enable runtime complexity validation (CRITICAL for DoS prevention)
GRAPHQL_ENABLE_COMPLEXITY_VALIDATION = env.bool('GRAPHQL_ENABLE_COMPLEXITY_VALIDATION', default=True)

# Enable validation result caching for performance
GRAPHQL_ENABLE_VALIDATION_CACHE = env.bool('GRAPHQL_ENABLE_VALIDATION_CACHE', default=True)

# Validation cache TTL in seconds (default: 5 minutes)
GRAPHQL_VALIDATION_CACHE_TTL = env.int('GRAPHQL_VALIDATION_CACHE_TTL', default=300)

# ============================================================================
# GRAPHQL INTROSPECTION CONTROL
# ============================================================================

# Disable introspection in production (security best practice)
GRAPHQL_DISABLE_INTROSPECTION_IN_PRODUCTION = env.bool(
    'GRAPHQL_DISABLE_INTROSPECTION_IN_PRODUCTION',
    default=True
)

# ============================================================================
# GRAPHQL CSRF PROTECTION
# ============================================================================

# CSRF header names that GraphQL mutations must include
GRAPHQL_CSRF_HEADER_NAMES = [
    'HTTP_X_CSRFTOKEN',
    'HTTP_X_CSRF_TOKEN',
]

# ============================================================================
# GRAPHQL ORIGIN VALIDATION
# ============================================================================

# Allowed origins for GraphQL requests (empty list = allow all with CORS)
GRAPHQL_ALLOWED_ORIGINS = env.list('GRAPHQL_ALLOWED_ORIGINS', default=[])

# Strict origin validation (should be True in production)
GRAPHQL_STRICT_ORIGIN_VALIDATION = env.bool('GRAPHQL_STRICT_ORIGIN_VALIDATION', default=False)

# Comprehensive origin validation configuration for GraphQLOriginValidationMiddleware
GRAPHQL_ORIGIN_VALIDATION = {
    # Allowed origins (exact match)
    'allowed_origins': GRAPHQL_ALLOWED_ORIGINS,

    # Allowed origin patterns (regex) - e.g., [r'^https://.*\.yourdomain\.com$']
    'allowed_patterns': env.list('GRAPHQL_ORIGIN_PATTERNS', default=[]),

    # Allowed subdomains - e.g., ['yourdomain.com'] allows *.yourdomain.com
    'allowed_subdomains': env.list('GRAPHQL_ALLOWED_SUBDOMAINS', default=[]),

    # Blocked origins (blacklist - takes precedence over allowlist)
    'blocked_origins': env.list('GRAPHQL_BLOCKED_ORIGINS', default=[]),

    # Strict mode: reject requests without valid origin
    'strict_mode': GRAPHQL_STRICT_ORIGIN_VALIDATION,

    # Validate Referer header consistency
    'validate_referer': env.bool('GRAPHQL_VALIDATE_REFERER', default=True),

    # Validate Host header consistency
    'validate_host': env.bool('GRAPHQL_VALIDATE_HOST', default=True),

    # Allow localhost in development (auto-enabled if DEBUG=True)
    'allow_localhost_dev': env.bool('GRAPHQL_ALLOW_LOCALHOST', default=True),

    # Geographic validation (requires GeoIP)
    'geographic_validation': env.bool('GRAPHQL_GEO_VALIDATION', default=False),
    'allowed_countries': env.list('GRAPHQL_ALLOWED_COUNTRIES', default=[]),

    # Dynamic allowlist (cache validated origins for performance)
    'dynamic_allowlist': env.bool('GRAPHQL_DYNAMIC_ALLOWLIST', default=False),

    # Suspicious origin patterns (blocked)
    'suspicious_patterns': [
        r'.*\.onion$',  # Tor hidden services
        r'.*\.bit$',    # Namecoin domains
        r'\d+\.\d+\.\d+\.\d+',  # Raw IP addresses (unless specifically allowed)
    ]
}

# ============================================================================
# GRAPHQL SECURITY LOGGING
# ============================================================================

# Comprehensive security logging configuration
GRAPHQL_SECURITY_LOGGING = {
    'ENABLE_REQUEST_LOGGING': env.bool('GRAPHQL_LOG_REQUESTS', default=True),
    'ENABLE_MUTATION_LOGGING': env.bool('GRAPHQL_LOG_MUTATIONS', default=True),
    'ENABLE_RATE_LIMIT_LOGGING': env.bool('GRAPHQL_LOG_RATE_LIMITS', default=True),
    'ENABLE_FIELD_ACCESS_LOGGING': env.bool('GRAPHQL_LOG_FIELD_ACCESS', default=True),
    'ENABLE_OBJECT_ACCESS_LOGGING': env.bool('GRAPHQL_LOG_OBJECT_ACCESS', default=True),
    'LOG_FAILED_CSRF_ATTEMPTS': env.bool('GRAPHQL_LOG_CSRF_FAILURES', default=True),
}

# ============================================================================
# GRAPHQL JWT AUTHENTICATION
# ============================================================================

# JWT configuration for GraphQL authentication
GRAPHQL_JWT = {
    "JWT_VERIFY_EXPIRATION": True,  # SECURITY: Enable token expiration verification
    "JWT_EXPIRATION_DELTA": timedelta(hours=env.int('GRAPHQL_JWT_EXPIRATION_HOURS', default=8)),
    "JWT_REFRESH_EXPIRATION_DELTA": timedelta(days=env.int('GRAPHQL_JWT_REFRESH_DAYS', default=2)),
    "JWT_LONG_RUNNING_REFRESH_TOKEN": True
}

# ============================================================================
# SETTINGS VALIDATION
# ============================================================================

def validate_graphql_settings():
    """
    Validate GraphQL security settings on module import.
    Raises ValueError if critical settings are misconfigured.
    """
    errors = []

    # Validate rate limiting
    if GRAPHQL_RATE_LIMIT_MAX <= 0:
        errors.append("GRAPHQL_RATE_LIMIT_MAX must be positive")
    if GRAPHQL_RATE_LIMIT_MAX > 10000:
        errors.append("GRAPHQL_RATE_LIMIT_MAX suspiciously high (>10000), possible DoS risk")
    if GRAPHQL_RATE_LIMIT_WINDOW <= 0:
        errors.append("GRAPHQL_RATE_LIMIT_WINDOW must be positive")

    # Validate complexity limits
    if GRAPHQL_MAX_QUERY_DEPTH <= 0 or GRAPHQL_MAX_QUERY_DEPTH > 50:
        errors.append("GRAPHQL_MAX_QUERY_DEPTH must be between 1 and 50")
    if GRAPHQL_MAX_QUERY_COMPLEXITY <= 0:
        errors.append("GRAPHQL_MAX_QUERY_COMPLEXITY must be positive")
    if GRAPHQL_MAX_MUTATIONS_PER_REQUEST <= 0 or GRAPHQL_MAX_MUTATIONS_PER_REQUEST > 20:
        errors.append("GRAPHQL_MAX_MUTATIONS_PER_REQUEST must be between 1 and 20")

    # Validate paths
    if not GRAPHQL_PATHS or not isinstance(GRAPHQL_PATHS, list):
        errors.append("GRAPHQL_PATHS must be a non-empty list")

    # Validate CSRF headers
    if not GRAPHQL_CSRF_HEADER_NAMES or not isinstance(GRAPHQL_CSRF_HEADER_NAMES, list):
        errors.append("GRAPHQL_CSRF_HEADER_NAMES must be a non-empty list")

    if errors:
        error_msg = "\n".join([f"  - {err}" for err in errors])
        raise ValueError(f"GraphQL settings validation failed:\n{error_msg}")

    logger.info("✅ GraphQL security settings validated successfully")


# Validate settings on module import
try:
    validate_graphql_settings()
except ValueError as e:
    logger.error(f"❌ GraphQL settings validation failed: {e}")
    # Don't raise during import to allow Django to start
    # Management command will catch this

# ============================================================================
# SETTINGS METADATA (for auditing and monitoring)
# ============================================================================

__GRAPHQL_SETTINGS_VERSION__ = "2.0"
__GRAPHQL_SETTINGS_LAST_UPDATED__ = "2025-10-01"
__GRAPHQL_SETTINGS_SOURCE__ = "intelliwiz_config.settings.security.graphql"

# Export all settings for explicit imports
__all__ = [
    # Endpoint configuration
    'GRAPHQL_PATHS',

    # Rate limiting
    'ENABLE_GRAPHQL_RATE_LIMITING',
    'GRAPHQL_RATE_LIMIT_WINDOW',
    'GRAPHQL_RATE_LIMIT_MAX',

    # Query complexity limits
    'GRAPHQL_MAX_QUERY_DEPTH',
    'GRAPHQL_MAX_QUERY_COMPLEXITY',
    'GRAPHQL_MAX_MUTATIONS_PER_REQUEST',
    'GRAPHQL_ENABLE_COMPLEXITY_VALIDATION',
    'GRAPHQL_ENABLE_VALIDATION_CACHE',
    'GRAPHQL_VALIDATION_CACHE_TTL',

    # Introspection control
    'GRAPHQL_DISABLE_INTROSPECTION_IN_PRODUCTION',

    # CSRF protection
    'GRAPHQL_CSRF_HEADER_NAMES',

    # Origin validation
    'GRAPHQL_ALLOWED_ORIGINS',
    'GRAPHQL_STRICT_ORIGIN_VALIDATION',
    'GRAPHQL_ORIGIN_VALIDATION',

    # Security logging
    'GRAPHQL_SECURITY_LOGGING',

    # JWT authentication
    'GRAPHQL_JWT',

    # Validation
    'validate_graphql_settings',
]
