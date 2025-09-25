"""
Settings configuration for Information Architecture optimization
Add these settings to your main settings.py or import this file
"""

# ========== INFORMATION ARCHITECTURE SETTINGS ==========

# Enable/disable optimized URL structure
USE_OPTIMIZED_URLS = True

# Keep legacy URLs active during migration (set to False after full migration)
ENABLE_LEGACY_URLS = True

# Show deprecation warnings to users on legacy URLs
SHOW_DEPRECATION_WARNINGS = True

# Enable navigation tracking middleware
ENABLE_NAVIGATION_TRACKING = True

# Redirect type for legacy URLs (302 during migration, 301 after)
LEGACY_REDIRECT_TYPE = 'temporary'  # 'temporary' or 'permanent'

# Cache settings for IA analytics
IA_CACHE_TIMEOUT = 3600  # 1 hour
IA_ANALYTICS_RETENTION_DAYS = 30

# Navigation menu settings
NAV_MENU_CACHE_TIMEOUT = 1800  # 30 minutes
NAV_BREADCRUMB_MAX_LENGTH = 5

# Performance monitoring thresholds
IA_PERFORMANCE_THRESHOLDS = {
    'slow_page_threshold': 3.0,  # seconds
    'high_bounce_rate': 70.0,    # percentage
    'max_404_errors': 50,        # count
    'low_adoption_rate': 50.0,   # percentage
}

# URL validation settings
IA_VALIDATION = {
    'check_external_links': False,
    'validate_ssl_certs': False,
    'timeout_seconds': 10,
    'max_redirects': 5,
}

# Monitoring dashboard settings
IA_MONITORING = {
    'auto_refresh_interval': 30000,  # milliseconds
    'max_chart_data_points': 30,
    'enable_real_time_updates': True,
    'dashboard_access_level': 'staff',  # 'staff', 'superuser', or 'all'
}

# Feature flags for gradual rollout
IA_FEATURE_FLAGS = {
    'enable_smart_redirects': True,
    'enable_breadcrumbs': True,
    'enable_navigation_analytics': True,
    'enable_performance_monitoring': True,
    'enable_deprecation_warnings': True,
    'enable_user_flow_tracking': True,
}

# Migration phase settings
IA_MIGRATION_PHASE = 'active'  # 'planning', 'active', 'complete'

# Logging configuration for IA
IA_LOGGING = {
    'log_redirect_usage': True,
    'log_404_errors': True,
    'log_performance_issues': True,
    'log_level': 'INFO',
}

# Rate limiting for IA endpoints
IA_RATE_LIMITS = {
    'monitoring_api': '100/hour',
    'analytics_export': '10/hour',
    'validation_command': '5/hour',
}

# URL patterns to exclude from tracking
IA_EXCLUDE_PATTERNS = [
    r'^/static/',
    r'^/media/',
    r'^/__debug__/',
    r'^/admin/jsi18n/',
    r'\.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$',
    r'^/api/internal/',
]

# Database settings for IA models (if using database storage)
IA_DATABASE_SETTINGS = {
    'use_database': False,  # Use cache by default
    'cleanup_interval_days': 7,
    'max_records_per_table': 10000,
}

# Integration settings
IA_INTEGRATIONS = {
    'google_analytics': {
        'enabled': False,
        'tracking_id': '',
        'track_navigation': True,
    },
    'slack': {
        'enabled': False,
        'webhook_url': '',
        'alert_threshold': 10,  # Number of 404s to trigger alert
    },
}

# Custom error pages for IA
IA_ERROR_PAGES = {
    '404': 'core/errors/404_ia.html',
    '500': 'core/errors/500_ia.html',
    'redirect': 'core/redirects/smart_redirect.html',
}

# SEO settings
IA_SEO_SETTINGS = {
    'generate_sitemap': True,
    'sitemap_priority': {
        'dashboard': 1.0,
        'operations': 0.9,
        'assets': 0.8,
        'people': 0.8,
        'help_desk': 0.7,
        'reports': 0.7,
        'admin': 0.5,
    },
    'canonical_urls': True,
    'meta_descriptions': True,
}

# API settings
IA_API_SETTINGS = {
    'version': 'v1',
    'enable_cors': True,
    'authentication_required': True,
    'throttling': {
        'anon': '100/day',
        'user': '1000/day',
        'staff': '10000/day',
    },
}

# ========== DJANGO SETTINGS INTEGRATION ==========

def apply_ia_settings(settings_module):
    """
    Apply IA settings to Django settings module
    
    Usage in settings.py:
    from intelliwiz_config.settings_ia import apply_ia_settings
    apply_ia_settings(locals())
    """
    
    # Add IA apps if not already present
    if 'INSTALLED_APPS' in settings_module:
        ia_apps = [
            'apps.core',
        ]
        
        for app in ia_apps:
            if app not in settings_module['INSTALLED_APPS']:
                settings_module['INSTALLED_APPS'].append(app)
    
    # Add IA middleware
    if USE_OPTIMIZED_URLS and ENABLE_NAVIGATION_TRACKING:
        if 'MIDDLEWARE' in settings_module:
            middleware_class = 'apps.core.middleware.navigation_tracking.NavigationTrackingMiddleware'
            if middleware_class not in settings_module['MIDDLEWARE']:
                # Add after Django's common middleware
                common_middleware_index = next(
                    (i for i, m in enumerate(settings_module['MIDDLEWARE']) 
                     if 'CommonMiddleware' in m), 
                    len(settings_module['MIDDLEWARE'])
                )
                settings_module['MIDDLEWARE'].insert(
                    common_middleware_index + 1, 
                    middleware_class
                )
    
    # Add IA cache settings
    if 'CACHES' in settings_module:
        # Ensure we have a cache backend for IA
        if 'ia_cache' not in settings_module['CACHES']:
            settings_module['CACHES']['ia_cache'] = {
                'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                'LOCATION': 'ia-cache',
                'TIMEOUT': IA_CACHE_TIMEOUT,
                'OPTIONS': {
                    'MAX_ENTRIES': 10000,
                }
            }
    
    # Add IA logging configuration
    if 'LOGGING' in settings_module:
        ia_logger = {
            'handlers': ['console'],
            'level': IA_LOGGING['log_level'],
            'propagate': True,
        }
        
        if 'loggers' not in settings_module['LOGGING']:
            settings_module['LOGGING']['loggers'] = {}
        
        settings_module['LOGGING']['loggers']['apps.core.ia'] = ia_logger
    
    # Add IA context processors
    if 'TEMPLATES' in settings_module:
        for template_config in settings_module['TEMPLATES']:
            if 'context_processors' in template_config.get('OPTIONS', {}):
                ia_processor = 'apps.core.context_processors.ia_context'
                if ia_processor not in template_config['OPTIONS']['context_processors']:
                    template_config['OPTIONS']['context_processors'].append(ia_processor)
    
    # Set all IA settings as module-level variables
    for key, value in globals().items():
        if key.startswith('IA_') or key in [
            'USE_OPTIMIZED_URLS', 'ENABLE_LEGACY_URLS', 
            'SHOW_DEPRECATION_WARNINGS', 'ENABLE_NAVIGATION_TRACKING'
        ]:
            settings_module[key] = value


# ========== ENVIRONMENT-SPECIFIC SETTINGS ==========

def get_development_settings():
    """Settings for development environment"""
    return {
        'USE_OPTIMIZED_URLS': True,
        'ENABLE_LEGACY_URLS': True,
        'SHOW_DEPRECATION_WARNINGS': True,
        'LEGACY_REDIRECT_TYPE': 'temporary',
        'IA_LOGGING': {**IA_LOGGING, 'log_level': 'DEBUG'},
        'IA_MONITORING': {**IA_MONITORING, 'enable_real_time_updates': True},
    }

def get_staging_settings():
    """Settings for staging environment"""
    return {
        'USE_OPTIMIZED_URLS': True,
        'ENABLE_LEGACY_URLS': True,
        'SHOW_DEPRECATION_WARNINGS': False,
        'LEGACY_REDIRECT_TYPE': 'temporary',
        'IA_VALIDATION': {**IA_VALIDATION, 'check_external_links': True},
    }

def get_production_settings():
    """Settings for production environment"""
    return {
        'USE_OPTIMIZED_URLS': True,
        'ENABLE_LEGACY_URLS': False,  # After migration complete
        'SHOW_DEPRECATION_WARNINGS': False,
        'LEGACY_REDIRECT_TYPE': 'permanent',
        'IA_LOGGING': {**IA_LOGGING, 'log_level': 'WARNING'},
        'IA_MONITORING': {**IA_MONITORING, 'auto_refresh_interval': 60000},
    }


# ========== SETTINGS VALIDATION ==========

def validate_ia_settings():
    """Validate IA settings configuration"""
    errors = []
    warnings = []
    
    # Check required settings
    if USE_OPTIMIZED_URLS and not ENABLE_LEGACY_URLS:
        warnings.append(
            "USE_OPTIMIZED_URLS is True but ENABLE_LEGACY_URLS is False. "
            "Ensure migration is complete before disabling legacy URLs."
        )
    
    # Check cache configuration
    try:
        from django.core.cache import cache
        cache.set('ia_test', 'test', 1)
        if cache.get('ia_test') != 'test':
            warnings.append("Cache backend may not be working properly for IA features")
    except Exception as e:
        errors.append(f"Cache configuration error: {e}")
    
    # Check middleware order
    from django.conf import settings
    if hasattr(settings, 'MIDDLEWARE'):
        nav_middleware = 'apps.core.middleware.navigation_tracking.NavigationTrackingMiddleware'
        if nav_middleware in settings.MIDDLEWARE:
            index = settings.MIDDLEWARE.index(nav_middleware)
            if index == 0:
                warnings.append("NavigationTrackingMiddleware should not be first in middleware stack")
    
    return {'errors': errors, 'warnings': warnings}


# ========== EXAMPLE USAGE ==========

"""
Example usage in your main settings.py:

# Import and apply IA settings
from intelliwiz_config.settings_ia import *
from intelliwiz_config.settings_ia import apply_ia_settings

# Apply IA configuration
apply_ia_settings(locals())

# Environment-specific overrides
if DEBUG:
    # Development settings
    locals().update(get_development_settings())
else:
    # Production settings  
    locals().update(get_production_settings())

# Validate configuration
validation_result = validate_ia_settings()
if validation_result['errors']:
    raise ImproperlyConfigured(f"IA Settings errors: {validation_result['errors']}")
if validation_result['warnings']:
    import warnings
    for warning in validation_result['warnings']:
        warnings.warn(f"IA Settings: {warning}")
"""