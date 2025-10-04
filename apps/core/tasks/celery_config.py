"""
Enhanced Celery Configuration

Provides optimized Celery configuration with:
- Improved retry patterns and error handling
- Better queue management and routing
- Enhanced monitoring and observability
- Security and performance optimizations
- Integration with custom task base classes

This configuration can be imported and used in both celery.py files.
"""

import os
from datetime import timedelta
from celery.schedules import crontab
from kombu import Queue, Exchange

from apps.core.constants.datetime_constants import SECONDS_IN_MINUTE, SECONDS_IN_HOUR


# Enhanced queue configuration with proper routing
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

    # AI and ML queues (if needed)
    Queue('ai_processing', Exchange('ai_processing', type='direct'), routing_key='ai_processing'),
    Queue('ml_training', Exchange('ml_training', type='direct'), routing_key='ml_training'),
]


# Enhanced task routing with intelligent queue assignment
CELERY_TASK_ROUTES = {
    # Critical tasks (crisis intervention, security alerts)
    'background_tasks.journal_wellness_tasks.process_crisis_intervention_alert': {'queue': 'critical'},
    'background_tasks.security_tasks.*': {'queue': 'critical'},

    # High priority tasks
    'background_tasks.tasks.send_ticket_email': {'queue': 'high_priority'},
    'background_tasks.tasks.alert_sendmail': {'queue': 'high_priority'},
    'background_tasks.notifications.*': {'queue': 'high_priority'},

    # Email tasks
    'background_tasks.tasks.send_*_email*': {'queue': 'email'},
    'background_tasks.journal_wellness_tasks.notify_support_team': {'queue': 'email'},

    # Report generation tasks
    'background_tasks.tasks.create_*_report*': {'queue': 'reports'},
    'background_tasks.tasks.send_generated_report*': {'queue': 'reports'},
    'background_tasks.report_tasks.*': {'queue': 'reports'},

    # External API calls
    'background_tasks.tasks.publish_mqtt': {'queue': 'external_api'},
    'background_tasks.onboarding_tasks.*_api_*': {'queue': 'external_api'},

    # Maintenance and cleanup tasks
    'background_tasks.tasks.auto_close_jobs': {'queue': 'maintenance'},
    'background_tasks.tasks.cleanup_*': {'queue': 'maintenance'},
    'background_tasks.tasks.move_media_to_cloud_storage': {'queue': 'maintenance'},

    # Analytics and heavy computation
    'background_tasks.journal_wellness_tasks.update_user_analytics': {'queue': 'analytics'},
    'background_tasks.ai_testing_tasks.*': {'queue': 'ai_processing'},

    # Batch processing
    'background_tasks.tasks.insert_json_records_async': {'queue': 'batch_processing'},
}


# Enhanced Celery configuration
ENHANCED_CELERY_CONFIG = {
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
    'worker_prefetch_multiplier': 1,  # Important for fair task distribution
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
    'task_queues': CELERY_QUEUES,
    'task_routes': CELERY_TASK_ROUTES,

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
        'priority_steps': list(range(10)),  # Enable priority support
        'sep': ':',
        'queue_order_strategy': 'priority',
    },

    # Security Configuration
    'worker_hijack_root_logger': False,
    'worker_log_color': False,
    'security_key': os.environ.get('CELERY_SECURITY_KEY'),
    'security_certificate': os.environ.get('CELERY_SECURITY_CERT'),
    'security_cert_store': os.environ.get('CELERY_CERT_STORE'),

    # Monitoring and Logging
    'worker_log_format': '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
    'worker_task_log_format': '[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',

    # Timezone Configuration
    'timezone': 'UTC',
    'enable_utc': True,

    # Beat Schedule (will be enhanced with task configs)
    'beat_schedule': {},
    'beat_schedule_filename': 'celerybeat-schedule',

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


# Enhanced beat schedule with standardized task configurations
ENHANCED_BEAT_SCHEDULE = {
    # High frequency tasks (every few minutes)
    'cache-warming-frequent': {
        'task': 'background_tasks.core_tasks_refactored.cache_warming_scheduled',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
        'options': {
            'queue': 'maintenance',
            'expires': 600,
            'priority': 7
        }
    },

    # Redis memory monitoring (every 10 minutes)
    'redis-memory-monitor': {
        'task': 'apps.core.tasks.redis_memory_tasks.monitor_redis_memory',
        'schedule': crontab(minute='*/10'),  # Every 10 minutes
        'options': {
            'queue': 'maintenance',
            'expires': 300,
            'priority': 6
        }
    },

    # Regular maintenance (hourly)
    'cleanup-expired-sessions': {
        'task': 'background_tasks.core_tasks_refactored.cleanup_expired_uploads',
        'schedule': crontab(minute=0),  # Every hour
        'options': {
            'queue': 'maintenance',
            'expires': 3600,
            'priority': 5
        }
    },

    # Hourly tasks
    'redis-memory-optimization': {
        'task': 'apps.core.tasks.redis_memory_tasks.optimize_redis_memory',
        'schedule': crontab(minute=30),  # Every hour at 30 minutes
        'options': {
            'queue': 'maintenance',
            'expires': 1800,
            'priority': 5
        }
    },

    # Daily tasks
    'daily-analytics-update': {
        'task': 'background_tasks.journal_wellness_tasks_refactored.update_user_analytics',
        'schedule': crontab(hour=2, minute=0),  # 2 AM daily
        'options': {
            'queue': 'analytics',
            'expires': 7200,
            'priority': 6
        }
    },

    'daily-wellness-content': {
        'task': 'background_tasks.journal_wellness_tasks_refactored.schedule_daily_wellness_content',
        'schedule': crontab(hour=8, minute=0),  # 8 AM daily
        'options': {
            'queue': 'default',
            'expires': 3600,
            'priority': 6
        }
    },

    'daily-redis-memory-report': {
        'task': 'apps.core.tasks.redis_memory_tasks.generate_redis_memory_report',
        'schedule': crontab(hour=1, minute=0),  # 1 AM daily
        'options': {
            'queue': 'maintenance',
            'expires': 3600,
            'priority': 4
        }
    },

    # Redis Backup Tasks
    'daily-redis-full-backup': {
        'task': 'apps.core.tasks.redis_backup_tasks.create_scheduled_redis_backup',
        'schedule': crontab(hour=3, minute=30),  # 3:30 AM daily
        'kwargs': {'backup_type': 'full', 'compression': True},
        'options': {
            'queue': 'maintenance',
            'expires': 7200,
            'priority': 7
        }
    },

    'hourly-redis-rdb-backup': {
        'task': 'apps.core.tasks.redis_backup_tasks.create_scheduled_redis_backup',
        'schedule': crontab(minute=0),  # Every hour at 0 minutes
        'kwargs': {'backup_type': 'rdb', 'compression': True},
        'options': {
            'queue': 'maintenance',
            'expires': 1800,
            'priority': 6
        }
    },

    'weekly-redis-backup-cleanup': {
        'task': 'apps.core.tasks.redis_backup_tasks.cleanup_old_redis_backups',
        'schedule': crontab(day_of_week=0, hour=2, minute=0),  # Sunday 2 AM
        'options': {
            'queue': 'maintenance',
            'expires': 3600,
            'priority': 4
        }
    },

    'daily-redis-backup-verification': {
        'task': 'apps.core.tasks.redis_backup_tasks.verify_redis_backups',
        'schedule': crontab(hour=5, minute=0),  # 5 AM daily
        'kwargs': {'days_back': 7},
        'options': {
            'queue': 'maintenance',
            'expires': 1800,
            'priority': 5
        }
    },

    'weekly-redis-backup-status-report': {
        'task': 'apps.core.tasks.redis_backup_tasks.generate_backup_status_report',
        'schedule': crontab(day_of_week=1, hour=6, minute=0),  # Monday 6 AM
        'options': {
            'queue': 'maintenance',
            'expires': 1800,
            'priority': 4
        }
    },

    # Redis Performance Monitoring Tasks
    'redis-metrics-collection': {
        'task': 'apps.core.tasks.redis_monitoring_tasks.collect_redis_performance_metrics',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
        'kwargs': {'instance_name': 'main'},
        'options': {
            'queue': 'maintenance',
            'expires': 240,
            'priority': 6
        }
    },

    'redis-performance-trends-analysis': {
        'task': 'apps.core.tasks.redis_monitoring_tasks.analyze_redis_performance_trends',
        'schedule': crontab(hour='*/6', minute=15),  # Every 6 hours
        'kwargs': {'hours_back': 24},
        'options': {
            'queue': 'maintenance',
            'expires': 3600,
            'priority': 5
        }
    },

    'weekly-redis-capacity-report': {
        'task': 'apps.core.tasks.redis_monitoring_tasks.generate_redis_capacity_report',
        'schedule': crontab(day_of_week=2, hour=4, minute=0),  # Tuesday 4 AM
        'options': {
            'queue': 'maintenance',
            'expires': 7200,
            'priority': 4
        }
    },

    # Weekly tasks
    'weekly-maintenance': {
        'task': 'background_tasks.core_tasks_refactored.cleanup_expired_uploads',
        'schedule': crontab(day_of_week=1, hour=3, minute=0),  # Monday 3 AM
        'kwargs': {'days_old': 30},
        'options': {
            'queue': 'maintenance',
            'expires': 7200,
            'priority': 4
        }
    },

    # Legacy tasks (maintain compatibility)
    'ppm-schedule': {
        'task': 'create_ppm_job',
        'schedule': crontab(minute='3', hour='3,16'),
        'options': {'queue': 'default', 'expires': 3600}
    },

    'reminder-emails': {
        'task': 'send_reminder_email',
        'schedule': crontab(hour='*/8', minute='10'),
        'options': {'queue': 'email', 'expires': 3600}
    },

    'auto-close-jobs': {
        'task': 'auto_close_jobs',
        'schedule': crontab(minute='*/30'),
        'options': {'queue': 'maintenance', 'expires': 1800}
    },

    'ticket-escalation': {
        'task': 'ticket_escalation',
        'schedule': crontab(minute='*/30'),
        'options': {'queue': 'high_priority', 'expires': 1800}
    },

    'create-scheduled-reports': {
        'task': 'create_scheduled_reports',
        'schedule': crontab(minute='*/15'),
        'options': {'queue': 'reports', 'expires': 900}
    },

    'send-generated-reports': {
        'task': 'send_generated_report_on_mail',
        'schedule': crontab(minute='*/27'),
        'options': {'queue': 'email', 'expires': 1620}
    },

    'move-media-to-cloud': {
        'task': 'move_media_to_cloud_storage',
        'schedule': crontab(minute=0, hour=0, day_of_week='monday'),
        'options': {'queue': 'maintenance', 'expires': 7200}
    }
}


def get_celery_config(environment='development'):
    """
    Get Celery configuration for specific environment.

    Args:
        environment: Environment name ('development', 'production', 'testing')

    Returns:
        dict: Celery configuration dictionary
    """
    config = ENHANCED_CELERY_CONFIG.copy()

    if environment == 'development':
        config.update({
            'task_always_eager': False,  # Changed from True to test actual async behavior
            'task_eager_propagates': True,
            'worker_log_color': True,
            'worker_pool': 'solo',  # Single-threaded for debugging
        })

    elif environment == 'production':
        config.update({
            'task_always_eager': False,
            'worker_pool': 'prefork',
            'worker_concurrency': 4,
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

    # Add beat schedule
    config['beat_schedule'] = ENHANCED_BEAT_SCHEDULE

    return config


def setup_task_monitoring():
    """
    Setup enhanced task monitoring and observability.

    This function configures additional monitoring for production environments.
    """
    try:
        # Configure Celery events monitoring
        from celery.events import Events

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
        from celery.signals import task_sent, task_received, task_prerun
        task_sent.connect(on_task_sent)
        task_received.connect(on_task_received)
        task_prerun.connect(on_task_started)

        return True

    except Exception as exc:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to setup task monitoring: {exc}")
        return False


def get_queue_priorities():
    """
    Get queue priority mapping for task routing.

    Returns:
        dict: Queue to priority mapping
    """
    return {
        'critical': 9,
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