"""
Core caching utilities for YOUTILITY5
Advanced caching decorators with tenant-aware keys and intelligent invalidation
"""

from .decorators import (
    smart_cache_view,
    cache_dropdown_data,
    cache_dashboard_metrics,
    cache_with_invalidation
)
from .invalidation import (
    CacheInvalidationManager,
    invalidate_cache_pattern,
    invalidate_model_caches
)
from .utils import (
    get_tenant_cache_key,
    get_user_cache_key,
    cache_key_generator
)
from .versioning import (
    CacheVersionManager,
    get_versioned_cache_key,
    bump_cache_version
)
from .security import (
    validate_cache_key,
    sanitize_cache_key,
    CacheRateLimiter
)
from .ttl_monitor import (
    TTLMonitor,
    get_ttl_health_report,
    detect_ttl_anomalies
)
from .ttl_optimizer import (
    recommend_ttl_adjustments,
    generate_ttl_recommendation
)
from .validators import (
    validate_cache_operation,
    is_safe_cache_pattern
)
from .distributed_invalidation import (
    publish_invalidation_event,
    subscribe_to_invalidation_events
)

__all__ = [
    'smart_cache_view',
    'cache_dropdown_data',
    'cache_dashboard_metrics',
    'cache_with_invalidation',
    'CacheInvalidationManager',
    'invalidate_cache_pattern',
    'invalidate_model_caches',
    'get_tenant_cache_key',
    'get_user_cache_key',
    'cache_key_generator',
    'CacheVersionManager',
    'get_versioned_cache_key',
    'bump_cache_version',
    'validate_cache_key',
    'sanitize_cache_key',
    'CacheRateLimiter',
    'TTLMonitor',
    'get_ttl_health_report',
    'detect_ttl_anomalies',
    'recommend_ttl_adjustments',
    'generate_ttl_recommendation',
    'validate_cache_operation',
    'is_safe_cache_pattern',
    'publish_invalidation_event',
    'subscribe_to_invalidation_events',
]