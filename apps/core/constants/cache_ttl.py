"""
Cache Time-To-Live (TTL) Constants

Centralized cache timeout and expiration values. Provides consistent
cache behavior across all layers: Redis, Django cache, application caches.

Usage:
    from apps.core.constants.cache_ttl import (
        CACHE_TTL_SHORT,
        CACHE_TTL_DEFAULT,
        CACHE_TTL_API_RESPONSE
    )

    cache.set('key', value, timeout=CACHE_TTL_DEFAULT)

Compliance:
- Eliminates magic numbers from cache operations
- Enables easy adjustment of cache policies
- Ensures consistency between different cache layers
"""

from typing import Final

# =============================================================================
# GENERAL CACHE TTL VALUES (in seconds)
# =============================================================================

# Very short term - volatile data that changes frequently
CACHE_TTL_VERY_SHORT: Final[int] = 60  # 1 minute

# Short term - data that may change within minutes
CACHE_TTL_SHORT: Final[int] = 300  # 5 minutes

# Medium term - standard cache duration
CACHE_TTL_MEDIUM: Final[int] = 900  # 15 minutes

# Default TTL - general purpose caching
CACHE_TTL_DEFAULT: Final[int] = 1800  # 30 minutes

# Long term - relatively stable data
CACHE_TTL_LONG: Final[int] = 3600  # 1 hour

# Very long term - data that rarely changes
CACHE_TTL_VERY_LONG: Final[int] = 7200  # 2 hours

# Daily cache - data valid for a full day
CACHE_TTL_DAILY: Final[int] = 86400  # 24 hours

# =============================================================================
# APPLICATION-SPECIFIC CACHE TIMEOUTS (in seconds)
# =============================================================================

# HelpBot Configuration
HELPBOT_CACHE_TIMEOUT: Final[int] = 3600  # 1 hour
HELPBOT_ANALYTICS_CACHE_TIMEOUT: Final[int] = 1800  # 30 minutes

# NOC/Operational Intelligence
NOC_TELEMETRY_CACHE_TTL: Final[int] = 60  # Real-time data
NOC_ALERT_CACHE_TTL: Final[int] = 300  # 5 minutes

# Reports and Analytics
REPORT_GENERATION_CACHE_TIMEOUT: Final[int] = 3600  # 1 hour
FRAPPE_CONNECTION_CACHE_TIMEOUT: Final[int] = 300  # 5 minutes

# API Responses
API_RESPONSE_CACHE_TIMEOUT: Final[int] = 3600  # 1 hour (from performance config)

# Navigation/Menu Cache (from settings_ia)
NAV_MENU_CACHE_TIMEOUT: Final[int] = 1800  # 30 minutes
IA_CACHE_TIMEOUT: Final[int] = 3600  # 1 hour

# Learning Features (from onboarding)
LEARNING_FEATURE_CACHE_TIMEOUT: Final[int] = 300  # 5 minutes
RERANK_CACHE_TIMEOUT: Final[int] = 300  # 5 minutes

# =============================================================================
# IDEMPOTENCY CACHE TIMEOUTS (in seconds)
# =============================================================================

# Idempotency keys expire after this time (prevents stale duplicate detection)
IDEMPOTENCY_TTL_SHORT: Final[int] = 300  # 5 minutes
IDEMPOTENCY_TTL_MEDIUM: Final[int] = 900  # 15 minutes
IDEMPOTENCY_TTL_STANDARD: Final[int] = 7200  # 2 hours
IDEMPOTENCY_TTL_LONG: Final[int] = 86400  # 24 hours

# Idempotency specific application timeouts
SITE_AUDIT_IDEMPOTENCY_TTL: Final[int] = 300  # 5 minutes
TICKET_IDEMPOTENCY_TTL: Final[int] = 900  # 15 minutes
REPORT_IDEMPOTENCY_TTL: Final[int] = 900  # 15 minutes

# =============================================================================
# DATABASE QUERY RESULT CACHE (in seconds)
# =============================================================================

# Query result caching for performance optimization
QUERY_RESULT_CACHE_SHORT: Final[int] = 60  # 1 minute
QUERY_RESULT_CACHE_DEFAULT: Final[int] = 300  # 5 minutes
QUERY_RESULT_CACHE_LONG: Final[int] = 3600  # 1 hour

# Database/ORM specific caches
DATABASE_QUERY_CACHE_TIMEOUT: Final[int] = 300  # 5 minutes
QUERY_OPTIMIZATION_CACHE_TIMEOUT: Final[int] = 300  # 5 minutes

# =============================================================================
# SESSION & AUTHENTICATION CACHES (in seconds)
# =============================================================================

# Session management (from datetime constants)
SESSION_CACHE_TIMEOUT: Final[int] = 7200  # 2 hours (from BUSINESS_TIMEDELTAS)

# API token cache
API_TOKEN_CACHE_TIMEOUT: Final[int] = 3600  # 1 hour

# Refresh token cache
REFRESH_TOKEN_CACHE_TIMEOUT: Final[int] = 604800  # 7 days

# =============================================================================
# RATE LIMITING WINDOWS (in seconds)
# =============================================================================

# Rate limiting window for various endpoints
RATE_LIMIT_WINDOW_SHORT: Final[int] = 300  # 5 minutes
RATE_LIMIT_WINDOW_MEDIUM: Final[int] = 900  # 15 minutes
RATE_LIMIT_WINDOW_STANDARD: Final[int] = 3600  # 1 hour

# Report generation rate limiting
REPORT_GENERATION_RATE_LIMIT_WINDOW: Final[int] = 300  # 5 minutes

# =============================================================================
# DATA RETENTION CACHE (in seconds)
# =============================================================================

# How long to cache data that will be retained
LOG_CACHE_RETENTION: Final[int] = 2592000  # 30 days
METRICS_CACHE_RETENTION: Final[int] = 7776000  # 90 days
ARCHIVE_CACHE_RETENTION: Final[int] = 31536000  # 365 days

# =============================================================================
# TEMPERATURE-BASED CACHE STRATEGY (in seconds)
# =============================================================================

# "Hot" cache - very frequently accessed data
HOT_CACHE_TTL: Final[int] = 300  # 5 minutes

# "Warm" cache - moderately accessed data
WARM_CACHE_TTL: Final[int] = 1800  # 30 minutes

# "Cold" cache - infrequently accessed data
COLD_CACHE_TTL: Final[int] = 3600  # 1 hour

# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    # General TTL values
    'CACHE_TTL_VERY_SHORT',
    'CACHE_TTL_SHORT',
    'CACHE_TTL_MEDIUM',
    'CACHE_TTL_DEFAULT',
    'CACHE_TTL_LONG',
    'CACHE_TTL_VERY_LONG',
    'CACHE_TTL_DAILY',

    # Application-specific timeouts
    'HELPBOT_CACHE_TIMEOUT',
    'HELPBOT_ANALYTICS_CACHE_TIMEOUT',
    'NOC_TELEMETRY_CACHE_TTL',
    'NOC_ALERT_CACHE_TTL',
    'REPORT_GENERATION_CACHE_TIMEOUT',
    'FRAPPE_CONNECTION_CACHE_TIMEOUT',
    'API_RESPONSE_CACHE_TIMEOUT',
    'NAV_MENU_CACHE_TIMEOUT',
    'IA_CACHE_TIMEOUT',
    'LEARNING_FEATURE_CACHE_TIMEOUT',
    'RERANK_CACHE_TIMEOUT',

    # Idempotency timeouts
    'IDEMPOTENCY_TTL_SHORT',
    'IDEMPOTENCY_TTL_MEDIUM',
    'IDEMPOTENCY_TTL_STANDARD',
    'IDEMPOTENCY_TTL_LONG',
    'SITE_AUDIT_IDEMPOTENCY_TTL',
    'TICKET_IDEMPOTENCY_TTL',
    'REPORT_IDEMPOTENCY_TTL',

    # Query result caching
    'QUERY_RESULT_CACHE_SHORT',
    'QUERY_RESULT_CACHE_DEFAULT',
    'QUERY_RESULT_CACHE_LONG',
    'DATABASE_QUERY_CACHE_TIMEOUT',
    'QUERY_OPTIMIZATION_CACHE_TIMEOUT',

    # Session & authentication
    'SESSION_CACHE_TIMEOUT',
    'API_TOKEN_CACHE_TIMEOUT',
    'REFRESH_TOKEN_CACHE_TIMEOUT',

    # Rate limiting windows
    'RATE_LIMIT_WINDOW_SHORT',
    'RATE_LIMIT_WINDOW_MEDIUM',
    'RATE_LIMIT_WINDOW_STANDARD',
    'REPORT_GENERATION_RATE_LIMIT_WINDOW',

    # Data retention
    'LOG_CACHE_RETENTION',
    'METRICS_CACHE_RETENTION',
    'ARCHIVE_CACHE_RETENTION',

    # Temperature-based strategy
    'HOT_CACHE_TTL',
    'WARM_CACHE_TTL',
    'COLD_CACHE_TTL',
]
