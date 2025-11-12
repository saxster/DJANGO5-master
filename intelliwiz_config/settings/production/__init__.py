"""
Production settings initialization.

Aggregates security and performance settings for production environment.
"""

from .security import (
    get_production_security_config,
    get_email_settings,
    get_database_settings,
)
from .performance import (
    get_performance_settings,
    get_cache_settings,
    get_feature_flags,
)

__all__ = [
    'get_production_security_config',
    'get_email_settings',
    'get_database_settings',
    'get_performance_settings',
    'get_cache_settings',
    'get_feature_flags',
]
