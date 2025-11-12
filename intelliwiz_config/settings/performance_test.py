"""
Performance test settings.

Unlike unit test settings, performance tests need full app configuration
to measure realistic latencies under production-like conditions.
"""

from .test import *

# Re-enable apps that were removed for unit tests but are needed for performance tests
PERFORMANCE_TEST_APPS = [
    'apps.helpbot',
    'apps.ontology',
]

# Convert to list if needed and add performance test apps
INSTALLED_APPS = list(INSTALLED_APPS)
for app in PERFORMANCE_TEST_APPS:
    if app not in INSTALLED_APPS:
        INSTALLED_APPS.append(app)

# Use local memory cache (Redis not needed for performance measurement)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'phase2-performance-test',
    }
}

# Enable features for performance testing
try:
    FEATURES['HELPBOT_USE_ONTOLOGY'] = True
except NameError:
    FEATURES = {'HELPBOT_USE_ONTOLOGY': True}

print(f"[PERFORMANCE TEST SETTINGS] Loaded with apps: {', '.join(PERFORMANCE_TEST_APPS)}")
