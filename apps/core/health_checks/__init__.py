"""
Health checks module - comprehensive system health monitoring.
Follows Rule 16: Explicit __all__ control for wildcard imports.

NOTE: View functions (health_check, readiness_check, etc.) are defined in
      apps/core/health_checks.py (file) and re-exported here for convenience.
"""

from .manager import HealthCheckManager, global_health_manager
from .database import (
    check_database_connectivity,
    check_postgis_extension,
    check_database_performance,
    check_connection_pool,
    check_custom_postgresql_functions,
)
from .cache import (
    check_redis_connectivity,
    check_default_cache,
    check_select2_cache,
)
from .system import (
    check_disk_space,
    check_memory_usage,
    check_cpu_load,
)
from .channels import check_channel_layer
from .mqtt import check_mqtt_broker
from .external_apis import (
    check_aws_ses,
    check_google_maps_api,
    check_openai_api,
    check_anthropic_api,
)
from .background_tasks import (
    check_task_queue,
    check_pending_tasks,
    check_failed_tasks,
    check_task_workers,
)
from .filesystem import check_directory_permissions
from .utils import CircuitBreaker, timeout_check, cache_health_check, format_check_result

__all__ = [
    'HealthCheckManager',
    'global_health_manager',
    'check_database_connectivity',
    'check_postgis_extension',
    'check_database_performance',
    'check_connection_pool',
    'check_custom_postgresql_functions',
    'check_redis_connectivity',
    'check_default_cache',
    'check_select2_cache',
    'check_disk_space',
    'check_memory_usage',
    'check_cpu_load',
    'check_channel_layer',
    'check_mqtt_broker',
    'check_aws_ses',
    'check_google_maps_api',
    'check_openai_api',
    'check_anthropic_api',
    'check_task_queue',
    'check_pending_tasks',
    'check_failed_tasks',
    'check_task_workers',
    'check_directory_permissions',
    'CircuitBreaker',
    'timeout_check',
    'cache_health_check',
    'format_check_result',
]


def register_all_checks():
    """Register all health checks with the global manager."""
    global_health_manager.register_check(
        "database_connectivity", check_database_connectivity, critical=True
    )
    global_health_manager.register_check(
        "postgis_extension", check_postgis_extension, critical=True
    )
    global_health_manager.register_check(
        "database_performance", check_database_performance, critical=False
    )
    global_health_manager.register_check(
        "connection_pool", check_connection_pool, critical=False
    )
    global_health_manager.register_check(
        "postgresql_functions", check_custom_postgresql_functions, critical=True
    )
    global_health_manager.register_check(
        "redis_connectivity", check_redis_connectivity, critical=True
    )
    global_health_manager.register_check(
        "default_cache", check_default_cache, critical=True
    )
    global_health_manager.register_check(
        "select2_cache", check_select2_cache, critical=False
    )
    global_health_manager.register_check(
        "disk_space", check_disk_space, critical=True
    )
    global_health_manager.register_check(
        "memory_usage", check_memory_usage, critical=False
    )
    global_health_manager.register_check(
        "cpu_load", check_cpu_load, critical=False
    )
    global_health_manager.register_check(
        "channel_layer", check_channel_layer, critical=False
    )
    global_health_manager.register_check(
        "mqtt_broker", check_mqtt_broker, critical=False
    )
    global_health_manager.register_check(
        "aws_ses", check_aws_ses, critical=False
    )
    global_health_manager.register_check(
        "google_maps_api", check_google_maps_api, critical=False
    )
    global_health_manager.register_check(
        "openai_api", check_openai_api, critical=False
    )
    global_health_manager.register_check(
        "anthropic_api", check_anthropic_api, critical=False
    )
    global_health_manager.register_check(
        "task_queue", check_task_queue, critical=True
    )
    global_health_manager.register_check(
        "pending_tasks", check_pending_tasks, critical=False
    )
    global_health_manager.register_check(
        "failed_tasks", check_failed_tasks, critical=False
    )
    global_health_manager.register_check(
        "task_workers", check_task_workers, critical=False
    )
    global_health_manager.register_check(
        "directory_permissions", check_directory_permissions, critical=True
    )


register_all_checks()