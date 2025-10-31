"""
Reusable Celery Configuration Components

This module provides centralized Celery configuration components that are
imported by intelliwiz_config/celery.py (single source of truth).

DO NOT create new Celery app instances here. This is for configuration only.

Extracted from: apps/core/tasks/celery_config.py (2025-10-10)
Used by: intelliwiz_config/celery.py

Architecture:
- Queue definitions with proper routing
- Task routing rules by domain
- Priority mappings
- Enhanced configuration presets
"""

import os
from kombu import Queue, Exchange

from apps.core.constants.datetime_constants import SECONDS_IN_MINUTE, SECONDS_IN_HOUR


# ============================================================================
# QUEUE DEFINITIONS
# ============================================================================

CELERY_QUEUES = [
    # High priority queues
    Queue('critical', Exchange('critical', type='direct'), routing_key='critical'),
    Queue('high_priority', Exchange('high_priority', type='direct'), routing_key='high_priority'),

    # Standard queues
    Queue('default', Exchange('default', type='direct'), routing_key='default'),
    Queue('email', Exchange('email', type='direct'), routing_key='email'),
    Queue('reports', Exchange('reports', type='direct'), routing_key='reports'),

    # Specialized queues
    Queue('external_api', Exchange('external_api', type='direct'), routing_key='external_api'),
    Queue('maintenance', Exchange('maintenance', type='direct'), routing_key='maintenance'),
    Queue('analytics', Exchange('analytics', type='direct'), routing_key='analytics'),

    # Heavy computation queues
    Queue('heavy_compute', Exchange('heavy_compute', type='direct'), routing_key='heavy_compute'),
    Queue('batch_processing', Exchange('batch_processing', type='direct'), routing_key='batch_processing'),

    # AI and ML queues
    Queue('ai_processing', Exchange('ai_processing', type='direct'), routing_key='ai_processing'),
    Queue('ml_training', Exchange('ml_training', type='direct'), routing_key='ml_training'),
]


# ============================================================================
# TASK ROUTING RULES
# ============================================================================

CELERY_TASK_ROUTES = {
    # Critical tasks (crisis intervention, security alerts)
    'background_tasks.journal_wellness_tasks.process_crisis_intervention_alert': {'queue': 'critical'},
    'background_tasks.security_tasks.*': {'queue': 'critical'},
    'auto_close_jobs': {'queue': 'critical'},
    'ticket_escalation': {'queue': 'critical'},

    # High priority tasks
    'background_tasks.tasks.send_ticket_email': {'queue': 'high_priority'},
    'background_tasks.tasks.alert_sendmail': {'queue': 'high_priority'},
    'background_tasks.notifications.*': {'queue': 'high_priority'},
    'create_ppm_job': {'queue': 'high_priority'},
    'create_job': {'queue': 'high_priority'},

    # Email tasks
    'background_tasks.tasks.send_*_email*': {'queue': 'email'},
    'background_tasks.journal_wellness_tasks.notify_support_team': {'queue': 'email'},
    'send_reminder_email': {'queue': 'email'},
    'send_generated_report_on_mail': {'queue': 'email'},

    # Report generation tasks
    'background_tasks.tasks.create_*_report*': {'queue': 'reports'},
    'background_tasks.tasks.send_generated_report*': {'queue': 'reports'},
    'background_tasks.report_tasks.*': {'queue': 'reports'},
    'create_scheduled_reports': {'queue': 'reports'},

    # External API calls
    'background_tasks.tasks.publish_mqtt': {'queue': 'external_api'},
    'background_tasks.onboarding_tasks.*_api_*': {'queue': 'external_api'},

    # Maintenance and cleanup tasks
    'background_tasks.tasks.cleanup_*': {'queue': 'maintenance'},
    'move_media_to_cloud_storage': {'queue': 'maintenance'},

    # Analytics and heavy computation
    'background_tasks.journal_wellness_tasks.update_user_analytics': {'queue': 'analytics'},
    'background_tasks.ai_testing_tasks.*': {'queue': 'ai_processing'},

    # Batch processing
    'background_tasks.tasks.insert_json_records_async': {'queue': 'batch_processing'},
}


# ============================================================================
# QUEUE PRIORITIES
# ============================================================================

def get_queue_priorities():
    """
    Get queue priority mapping for task routing.

    Returns:
        dict: Queue name to priority level (0-10, higher = more important)
    """
    return {
        'critical': 10,
        'high_priority': 8,
        'email': 7,
        'reports': 6,
        'default': 5,
        'analytics': 4,
        'external_api': 4,
        'maintenance': 3,
        'batch_processing': 2,
        'heavy_compute': 1,
        'ai_processing': 1,
        'ml_training': 0
    }


# ============================================================================
# ENHANCED CONFIGURATION PRESETS
# ============================================================================

def _build_base_celery_config():
    """Base Celery configuration shared across environments."""
    return {
        # Broker and Result Backend
        'broker_url': os.environ.get('CELERY_BROKER_URL', 'redis://127.0.0.1:6379/0'),
        'result_backend': os.environ.get('CELERY_RESULT_BACKEND', 'redis://127.0.0.1:6379/1'),

        # Task Serialization (Security)
        'task_serializer': 'json',
        'result_serializer': 'json',
        'accept_content': ['json'],
        'result_accept_content': ['json'],

        # Task Configuration
        'task_track_started': True,
        'task_send_sent_event': True,
        'task_ignore_result': False,
        'task_store_errors_even_if_ignored': True,

        # Worker Configuration
        'worker_prefetch_multiplier': 4,  # Optimal for mixed workload
        'worker_max_tasks_per_child': 1000,  # Restart workers periodically
        'worker_disable_rate_limits': False,
        'worker_send_task_events': True,

        # Task Execution
        'task_acks_late': True,  # Acknowledge after completion
        'task_reject_on_worker_lost': True,  # Reject tasks if worker dies
        'task_soft_time_limit': 1800,  # 30 minutes soft limit
        'task_time_limit': 3600,  # 1 hour hard limit

        # Enhanced Retry Configuration
        'task_default_retry_delay': 60,  # 1 minute default
        'task_max_retries': 3,
        'task_retry_backoff': True,
        'task_retry_backoff_max': 600,  # 10 minutes max
        'task_retry_jitter': True,

        # Queue Configuration
        'task_default_queue': 'default',

        # Result Backend Configuration
        'result_expires': 3600,  # 1 hour
        'result_backend_transport_options': {
            'master_name': 'mymaster',
            'visibility_timeout': 3600,
        },

        # Broker Transport Options (Redis-specific optimizations)
        'broker_transport_options': {
            'visibility_timeout': 3600,
            'fanout_prefix': True,
            'fanout_patterns': True,
            'priority_steps': list(range(11)),  # Enable priority 0-10
            'sep': ':',
            'queue_order_strategy': 'priority',
        },

        # Security Configuration
        'worker_hijack_root_logger': False,
        'worker_log_color': False,

        # Monitoring and Logging
        'worker_log_format': '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
        'worker_task_log_format': '[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',

        # Timezone Configuration
        'timezone': 'UTC',
        'enable_utc': True,

        # Task Compression (for large payloads)
        'task_compression': 'gzip',
        'result_compression': 'gzip',

        # Database Connection Optimization
        'database_short_lived_sessions': True,
        'database_engine_options': {
            'pool_recycle': 3600,
            'pool_pre_ping': True,
        }
    }


ENHANCED_CELERY_CONFIG = _build_base_celery_config()


def get_celery_config(environment='development'):
    """
    Get Celery configuration for a specific environment.

    Args:
        environment: Environment name ('base', 'development', 'production', 'testing')

    Returns:
        dict: Celery configuration dictionary
    """
    config = ENHANCED_CELERY_CONFIG.copy()

    if environment in (None, 'base'):
        return config

    if environment == 'development':
        config.update({
            'task_always_eager': False,
            'task_eager_propagates': True,
            'worker_log_color': True,
            'worker_pool': 'solo',  # Single-threaded for debugging
        })

    elif environment == 'production':
        config.update({
            'task_always_eager': False,
            'worker_pool': 'prefork',
            'worker_concurrency': 8,  # Adjust based on server capacity
            'worker_max_memory_per_child': 200000,  # 200MB
            'broker_connection_retry_on_startup': True,
            'result_backend_transport_options': {
                **config['result_backend_transport_options'],
                'retry_policy': {
                    'timeout': 5.0,
                    'max_retries': 10,
                    'interval_start': 0,
                    'interval_step': 0.2,
                    'interval_max': 0.2,
                }
            }
        })

    elif environment == 'testing':
        config.update({
            'task_always_eager': True,
            'task_eager_propagates': True,
            'broker_url': 'memory://',
            'result_backend': 'cache+memory://',
        })

    return config


# Backwards compatibility alias (was previously exported)
get_enhanced_celery_config = get_celery_config


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def setup_task_monitoring():
    """
    Setup enhanced task monitoring and observability.

    This function configures additional monitoring for production environments.
    Import and call from main Celery app if needed.

    Returns:
        bool: True if monitoring setup successful, False otherwise
    """
    try:
        from celery.signals import task_sent, task_received, task_prerun

        def on_task_sent(sender=None, task_id=None, task=None, args=None, kwargs=None, **kwds):
            """Handle task sent events"""
            from apps.core.tasks import TaskMetrics
            TaskMetrics.increment_counter('task_sent', {'task_name': task})

        def on_task_received(sender=None, task=None, **kwds):
            """Handle task received events"""
            from apps.core.tasks import TaskMetrics
            TaskMetrics.increment_counter('task_received', {'task_name': task.name})

        def on_task_started(sender=None, task_id=None, task=None, **kwds):
            """Handle task started events"""
            from apps.core.tasks import TaskMetrics
            TaskMetrics.increment_counter('task_started', {'task_name': task.name})

        # Register event handlers
        task_sent.connect(on_task_sent)
        task_received.connect(on_task_received)
        task_prerun.connect(on_task_started)

        return True

    except Exception as exc:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to setup task monitoring: {exc}")
        return False
