"""
Configuration settings for the GeofenceService

This file provides default settings and allows for easy customization
of geofence-related parameters.
"""

from django.conf import settings

# Cache settings
GEOFENCE_CACHE_TIMEOUT = getattr(settings, 'GEOFENCE_CACHE_TIMEOUT', 3600)  # 1 hour
GEOFENCE_CACHE_KEY_PREFIX = getattr(settings, 'GEOFENCE_CACHE_KEY_PREFIX', 'geofence')

# Hysteresis settings (in meters)
GEOFENCE_HYSTERESIS_DISTANCE = getattr(settings, 'GEOFENCE_HYSTERESIS_DISTANCE', 50)

# Performance settings
GEOFENCE_BATCH_SIZE = getattr(settings, 'GEOFENCE_BATCH_SIZE', 100)
GEOFENCE_MAX_CONCURRENT_CHECKS = getattr(settings, 'GEOFENCE_MAX_CONCURRENT_CHECKS', 10)

# Audit settings
GEOFENCE_AUDIT_RETENTION_DAYS = getattr(settings, 'GEOFENCE_AUDIT_RETENTION_DAYS', 30)
GEOFENCE_VIOLATION_CACHE_LIMIT = getattr(settings, 'GEOFENCE_VIOLATION_CACHE_LIMIT', 1000)

# Alert settings
GEOFENCE_ALERT_RATE_LIMIT = getattr(settings, 'GEOFENCE_ALERT_RATE_LIMIT', 60)  # seconds
GEOFENCE_ALERT_RETRY_COUNT = getattr(settings, 'GEOFENCE_ALERT_RETRY_COUNT', 3)

# Logging settings
GEOFENCE_LOG_LEVEL = getattr(settings, 'GEOFENCE_LOG_LEVEL', 'INFO')
GEOFENCE_LOG_VIOLATIONS = getattr(settings, 'GEOFENCE_LOG_VIOLATIONS', True)
GEOFENCE_LOG_PERFORMANCE = getattr(settings, 'GEOFENCE_LOG_PERFORMANCE', False)

# Feature flags
GEOFENCE_ENABLE_CACHING = getattr(settings, 'GEOFENCE_ENABLE_CACHING', True)
GEOFENCE_ENABLE_HYSTERESIS = getattr(settings, 'GEOFENCE_ENABLE_HYSTERESIS', True)
GEOFENCE_ENABLE_BATCH_OPERATIONS = getattr(settings, 'GEOFENCE_ENABLE_BATCH_OPERATIONS', True)
GEOFENCE_ENABLE_AUDIT_TRAIL = getattr(settings, 'GEOFENCE_ENABLE_AUDIT_TRAIL', True)

# Redis settings (if using Redis for caching)
GEOFENCE_REDIS_URL = getattr(settings, 'GEOFENCE_REDIS_URL', None)
GEOFENCE_REDIS_DB = getattr(settings, 'GEOFENCE_REDIS_DB', 0)

# Performance monitoring
GEOFENCE_ENABLE_METRICS = getattr(settings, 'GEOFENCE_ENABLE_METRICS', False)
GEOFENCE_METRICS_SAMPLE_RATE = getattr(settings, 'GEOFENCE_METRICS_SAMPLE_RATE', 0.1)

# Example settings that could be added to settings.py:
EXAMPLE_SETTINGS = """
# Add these to your settings.py for custom geofence configuration:

# Cache timeout in seconds (default: 3600 = 1 hour)
GEOFENCE_CACHE_TIMEOUT = 3600

# Hysteresis distance in meters to prevent GPS jitter (default: 50)
GEOFENCE_HYSTERESIS_DISTANCE = 50

# Maximum number of points to process in batch (default: 100)
GEOFENCE_BATCH_SIZE = 100

# Rate limit for alerts in seconds (default: 60)
GEOFENCE_ALERT_RATE_LIMIT = 60

# Enable/disable features
GEOFENCE_ENABLE_CACHING = True
GEOFENCE_ENABLE_HYSTERESIS = True
GEOFENCE_ENABLE_AUDIT_TRAIL = True

# Logging
GEOFENCE_LOG_VIOLATIONS = True
GEOFENCE_LOG_PERFORMANCE = False
"""